/* kernel/shutdown.c - apagado real de SereOS (i686, freestanding, sin libc)
 *
 * El apagado se hace en tres fases, tolerantes a fallos:
 *
 *   1. PREPARACION: se silencia el audio, se cierran las ventanas abiertas
 *      (el cierre de la ventana de Pac-man guarda el record en RAMFS desde
 *      pac_game_destroy(), tal como hace el cierre normal del compositor),
 *      se avisa por COM1 y se muestra una pantalla de despedida (~1 s) con
 *      la tipografia real del escritorio (graphics/text.h), el logo oficial
 *      y el fondo del tema; sin framebuffer se usa la terminal VGA.
 *      sereos_restart() reutiliza exactamente la misma pantalla y despues
 *      reinicia por el controlador de teclado (outb(0x64, 0xFE)).
 *
 *   2. ACPI: se localiza el RSDP ("RSD PTR ") en el EBDA y en la BIOS ROM,
 *      se valida su checksum, se sigue el RSDT/XSDT hasta el FADT ("FACP"),
 *      se verifica su checksum y se leen PM1a_CNT_BLK/PM1b_CNT_BLK y el
 *      DSDT. Si el AML del DSDT expone el paquete _S5 se usa su SLP_TYPa/b;
 *      si no, se usa la aproximacion SLP_TYPa = SLP_TYPb = 5 (habitual en
 *      placas que no personalizan _S5). Finalmente se escribe en PM1a_CNT
 *      el valor (SLP_TYPa << 10) | SLP_EN (bit 13), que es lo que provoca
 *      el corte de alimentacion en hardware real.
 *
 *   3. CASCADA: si el equipo sigue vivo, se prueban los puertos con los
 *      que QEMU/Bochs/VirtualBox emulan el apagado:
 *         outw(0x604,  0x2000)  QEMU moderno (ACPI PM)
 *         outw(0xB004, 0x2000)  QEMU antiguo / Bochs
 *         outw(0x4004, 0x3400)  VirtualBox
 *         outl(0x501,  0x31)    isa-debug-exit (solo si QEMU lo expone)
 *
 *   4. Si nada apaga: se borra la pantalla, se avisa "Ya puedes apagar el
 *      equipo con seguridad", se escribe SEREOS_POWEROFF_SAFE en COM1 y se
 *      detiene la CPU con cli + hlt.
 *
 * Todos los sondeos de memoria y todos los timeouts estan acotados: este
 * codigo nunca debe colgarse esperando a un dispositivo. La tabla fisica se
 * lee con paginacion identidad PSE, que en SereOS cubre [0, 512 MiB) (ver
 * memory/page.c); cualquier puntero fuera de ese rango se descarta antes de
 * tocarlo para no provocar un page fault.
 */
#include <stdint.h>
#include "io.h"
#include "serial.h"
#include "audio.h"
#include "window.h"
#include "framebuffer.h"
#include "graphics.h"
#include "text.h"
#include "theme.h"
#include "logo.h"
#include "terminal.h"
#include "timer.h"
#include "string.h"
#include "shutdown.h"

/* window_process_pending() aplica los cierres diferidos del compositor.
 * No esta declarada en gui/window.h (cada consumidor la declara a mano en
 * gui/gui.c y gui/desktop.c), asi que se declara aqui igual que alli. */
void window_process_pending(void);

/* outl no esta en include/io.h; se necesita solo para isa-debug-exit */
static inline void shutdown_outl(uint16_t port, uint32_t value) {
	__asm__ volatile ("outl %0, %1" : : "a"(value), "Nd"(port));
}

/* ------------------------------------------------------------------ */
/* utilidades                                                          */
/* ------------------------------------------------------------------ */

/* Identidad virtual = fisica de SereOS: 512 MiB con paginas PSE. */
#define ACPI_IDENTITY_LIMIT 0x20000000u

#define ACPI_SLP_EN     (1u << 13)
#define ACPI_SLP_SHIFT  10
#define ACPI_SLP_FALLBACK 5   /* _S5 sin parsear: valor habitual */

/* tiempo de espera tras disparar el apagado: ~1 s real aprox. (io_wait es
 * una escritura al puerto 0x80, el retardo clasico de la ISA) */
static void shutdown_spin_ms(uint32_t ms) {
	uint32_t loops = ms * 1000u;
	while (loops--) io_wait();
}

/* ¿estan las interrupciones activas? si lo estan se puede usar el PIT para
 * esperar sin quemar CPU; si no, se usa el retardo por puerto 0x80. */
static int shutdown_irq_enabled(void) {
	uint32_t flags;

	__asm__ volatile ("pushfl; popl %0" : "=r"(flags));
	return (flags & 0x200u) != 0;
}

static void shutdown_delay_ms(uint32_t ms) {
	/* Con el PIT activo se duerme en hlt (preciso y sin quemar CPU); si no
	 * hay temporizador se usa el retardo acotado por el puerto 0x80. */
	if (timer_hz() != 0 && shutdown_irq_enabled()) timer_sleep_ms(ms);
	else shutdown_spin_ms(ms);
}

/* Durante la pantalla de despedida el kernel puede venir de un callback de
 * entrada con las IRQ desactivadas (despacho de eventos). Como ya vamos a
 * apagar o reiniciar, se habilitan para que timer_sleep_ms() pueda medir el
 * ~1 s con el PIT; si el PIT no esta activo se deja todo como estaba. */
static void shutdown_enable_timer(void) {
	if (timer_hz() != 0 && !shutdown_irq_enabled()) sti();
}

/* lecturas fisicas con bytes volatiles (las tablas ACPI pueden no estar
 * alineadas; no se tocan mapeos ni se asume acceso atomico) */
static __attribute__((noinline)) uint8_t acpi_rd8(uint32_t addr) {
	return *(const volatile uint8_t *)(uintptr_t)addr;
}

static uint16_t acpi_rd16(uint32_t addr) {
	return (uint16_t)((uint16_t)acpi_rd8(addr) |
	                  (uint16_t)((uint16_t)acpi_rd8(addr + 1) << 8));
}

static __attribute__((noinline)) uint32_t acpi_rd32(uint32_t addr) {
	return (uint32_t)acpi_rd8(addr) |
	       ((uint32_t)acpi_rd8(addr + 1) << 8) |
	       ((uint32_t)acpi_rd8(addr + 2) << 16) |
	       ((uint32_t)acpi_rd8(addr + 3) << 24);
}

/* ¿se puede leer `len` bytes fisicos en [addr] sin salir del rango que la
 * paginacion identidad tiene mapeado? */
static int acpi_readable(uint32_t addr, uint32_t len) {
	if (len == 0 || len > 0x100000u) return 0;
	if (addr < 0x400u) return 0;
	if (addr > ACPI_IDENTITY_LIMIT - len) return 0;
	return 1;
}

static uint8_t acpi_checksum(uint32_t addr, uint32_t len) {
	uint32_t i;
	uint8_t sum = 0;

	for (i = 0; i < len; i++)
		sum = (uint8_t)(sum + acpi_rd8(addr + i));
	return sum;
}

static int acpi_signature_is(uint32_t addr, const char *sig) {
	int i;

	for (i = 0; i < 4; i++) {
		if (acpi_rd8(addr + (uint32_t)i) != (uint8_t)sig[i])
			return 0;
	}
	return 1;
}

/* ------------------------------------------------------------------ */
/* preparacion del apagado                                             */
/* ------------------------------------------------------------------ */

/* Cierra todas las ventanas del compositor. window_close() solo marca el
 * cierre; window_process_pending() lo aplica (incluye app->close(), que es
 * donde el juego guarda el record en RAMFS). Se itera con un tope duro para
 * no quedarse atrapado si alguna aplicacion se niega a cerrar. */
static void shutdown_close_windows(void) {
	int guard;

	for (guard = 0; guard < WINDOW_MAX + 4 && window_count() > 0; guard++) {
		int i;

		for (i = window_count() - 1; i >= 0; i--) {
			struct window *w = window_get(i);

			if (w) window_close(w);
		}
		window_process_pending();
	}
}

/* ------------------------------------------------------------------ */
/* pantalla de despedida / reinicio                                    */
/* ------------------------------------------------------------------ */

/* metricas del bloque (px). El espaciado se calcula con text_height() real,
 * nunca con offsets fijos: logo + 24 + titulo + 12 + subtitulo. */
#define SHUTDOWN_LOGO_SIZE       68   /* lado del contenedor del logo */
#define SHUTDOWN_GAP_LOGO_TITLE  24   /* logo -> titulo */
#define SHUTDOWN_GAP_TITLE_SUB   12   /* titulo -> subtitulo */
#define SHUTDOWN_ANIM_STEP_MS    180  /* un punto de "Apagando..." */
#define SHUTDOWN_FADE_STEP_MS    50   /* paso del fundido final */

/* ¿se puede pintar la pantalla grafica? (en arranque de texto no hay fb) */
static int shutdown_screen_ready(void) {
	return fb_available() && fb_has_backbuffer() &&
	       gfx_width() > 0 && gfx_height() > 0;
}

/* Dibuja un fotograma de la pantalla de despedida.
 *   title    : "Apagando..." / "Reiniciando..." / mensaje final
 *   subtitle : linea secundaria (NULL si no hay)
 *   dots     : si >= 0 sustituye los "..." finales del titulo por ese numero
 *              de puntos (animacion); si < 0 usa el titulo tal cual
 *   fade     : opacidad 0..255 del velo negro de fundido final
 * La columna completa (logo + titulo + subtitulo) se centra horizontal y
 * verticalmente y cada linea se centra por su ancho real (text_draw_center). */
static void shutdown_draw_screen(const char *title, const char *subtitle,
                                 int dots, uint8_t fade) {
	char buf[72];
	const char *text = title;
	size_t base_len;
	size_t n;
	int cx, top;
	int title_h, sub_h, block_h;
	int title_y;

	if (!shutdown_screen_ready()) return;

	/* animacion de los puntos finales del titulo */
	if (dots >= 0) {
		int i;
		size_t len = strlen(title);

		base_len = len;
		if (len >= 3 && title[len - 1] == '.' && title[len - 2] == '.' &&
		    title[len - 3] == '.')
			base_len = len - 3;
		if (base_len > sizeof(buf) - 4) base_len = sizeof(buf) - 4;

		memcpy(buf, title, base_len);
		n = base_len;
		for (i = 0; i < dots && n + 1 < sizeof(buf); i++)
			buf[n++] = '.';
		buf[n] = 0;
		text = buf;
	}

	title_h = text_height(TEXT_DISPLAY);
	sub_h = subtitle ? text_height(TEXT_SMALL) : 0;
	block_h = SHUTDOWN_LOGO_SIZE + SHUTDOWN_GAP_LOGO_TITLE + title_h;
	if (subtitle)
		block_h += SHUTDOWN_GAP_TITLE_SUB + sub_h;

	top = ((int)gfx_height() - block_h) / 2;
	if (top < 8) top = 8;
	cx = (int)gfx_width() / 2;

	gfx_reset_clip();
	gfx_clear(theme.bg);
	logo_draw_about(cx, top + SHUTDOWN_LOGO_SIZE / 2, SHUTDOWN_LOGO_SIZE);

	title_y = top + SHUTDOWN_LOGO_SIZE + SHUTDOWN_GAP_LOGO_TITLE;
	text_draw_center(TEXT_DISPLAY, cx, title_y, text, theme.text);
	if (subtitle)
		text_draw_center(TEXT_SMALL, cx, title_y + title_h +
		                 SHUTDOWN_GAP_TITLE_SUB, subtitle, theme.text_dim);

	/* fundido a negro solo si queda algo de tiempo antes de apagar */
	if (fade > 0)
		gfx_fill_rect_alpha(0, 0, (int)gfx_width(),
		                    (int)gfx_height(), theme.black, fade);

	gfx_mark_all_dirty();
	gfx_present();
}

/* Muestra la pantalla durante ~1 s (con puntos animados y fundido si el
 * titulo termina en "..."), o solo en la terminal VGA si no hay framebuffer.
 * Si el PIT no estuviera operativo, shutdown_delay_ms() usa un retardo por
 * puerto; este camino nunca se queda colgado. */
static void shutdown_show_screen(const char *title, const char *subtitle) {
	int len, animated, i;

	shutdown_enable_timer();

	if (!shutdown_screen_ready()) {
		terminal_write(title);
		terminal_write("\n");
		if (subtitle) {
			terminal_write(subtitle);
			terminal_write("\n");
		}
		shutdown_delay_ms(1000);
		return;
	}

	len = (int)strlen(title);
	animated = (len >= 3 && title[len - 1] == '.' && title[len - 2] == '.' &&
	            title[len - 3] == '.');

	if (!animated) {
		/* mensaje final: se queda fijo en pantalla */
		shutdown_draw_screen(title, subtitle, -1, 0);
		shutdown_delay_ms(1000);
		return;
	}

	/* 4 fotogramas de puntos: 720 ms */
	for (i = 0; i <= 3; i++) {
		shutdown_draw_screen(title, subtitle, i, 0);
		shutdown_delay_ms(SHUTDOWN_ANIM_STEP_MS);
	}
	/* fundido a negro final: 4 x 50 ms = 200 ms */
	for (i = 1; i <= 4; i++) {
		shutdown_draw_screen(title, subtitle, 3,
		                     (uint8_t)(i * 255 / 4));
		shutdown_delay_ms(SHUTDOWN_FADE_STEP_MS);
	}
}

static void shutdown_prepare(void) {
	/* 1. silenciar el audio antes de tocar cualquier otra cosa */
	audio_stop();

	/* 2. cerrar ventanas (guarda el record de Pac-man via app->close) */
	shutdown_close_windows();

	/* 3. marcador estable para las pruebas/QA desde el host */
	serial_write("SEREOS_POWEROFF\n");

	/* 4. pantalla de apagado durante ~1 s (incluye su propia espera) */
	shutdown_show_screen("Apagando...",
	                     "SereOS esta cerrando el sistema");
}

/* ------------------------------------------------------------------ */
/* ACPI: RSDP -> RSDT/XSDT -> FADT -> PM1a_CNT_BLK                     */
/* ------------------------------------------------------------------ */

/* busca el RSDP en la zona clasica: primeros 1 KiB del EBDA, los ultimos
 * 1 KiB del EBDA (0x9FC00) y la BIOS ROM (0xE0000-0xFFFFF), paso de 16. */
static uint32_t acpi_find_rsdp(void) {
	uint32_t ebda = (uint32_t)acpi_rd16(0x40Eu) << 4;
	uint32_t ranges[3][2];
	uint32_t i;

	ranges[0][0] = ebda;
	ranges[0][1] = 1024u;
	ranges[1][0] = 0x9FC00u;
	ranges[1][1] = 0x400u;
	ranges[2][0] = 0xE0000u;
	ranges[2][1] = 0x20000u;

	for (i = 0; i < 3; i++) {
		uint32_t addr;

		for (addr = ranges[i][0]; addr + 20 <= ranges[i][0] + ranges[i][1];
		     addr += 16) {
			uint32_t rev;

			if (!acpi_readable(addr, 20)) continue;
			if (!acpi_signature_is(addr, "RSD ")) continue;
			/* la firma completa es "RSD PTR " */
			if (acpi_rd8(addr + 4) != 'P') continue;
			if (acpi_checksum(addr, 20) != 0) continue;

			rev = acpi_rd8(addr + 15);
			if (rev >= 2 && acpi_readable(addr, 36)) {
				uint32_t len = acpi_rd32(addr + 20);

				/* ACPI 2.0+ exige ademas el checksum extendido */
				if (len >= 36 && len <= 1024u &&
				    acpi_checksum(addr, len) == 0)
					return addr;
			}
			/* RSDP 1.0 (o extendido mal formado): la firma y el
			 * checksum de 20 bytes ya validaron; se usa igualmente */
			return addr;
		}
	}
	return 0;
}

/* del RSDP al FADT: usa el XSDT si existe (ACPI 2.0+) y si no el RSDT */
static uint32_t acpi_find_fadt(uint32_t rsdp) {
	uint32_t table = 0;
	uint32_t i;
	uint32_t table_len;
	uint32_t entsize;
	uint32_t count;
	int use_xsdt = 0;

	if (acpi_rd8(rsdp + 15) >= 2 && acpi_readable(rsdp, 36)) {
		uint32_t xsdt = acpi_rd32(rsdp + 24);

		if (xsdt && acpi_readable(xsdt, 36) &&
		    acpi_signature_is(xsdt, "XSDT")) {
			table = xsdt;
			use_xsdt = 1;
		}
	}
	if (!table) {
		uint32_t rsdt = acpi_rd32(rsdp + 16);

		if (!rsdt || !acpi_readable(rsdt, 36)) return 0;
		table = rsdt;
	}

	table_len = acpi_rd32(table + 4);
	if (table_len < 36 || table_len > 0x100000u) return 0;
	if (!acpi_readable(table, table_len)) return 0;
	if (acpi_checksum(table, table_len) != 0) return 0;

	entsize = use_xsdt ? 8u : 4u;
	count = (table_len - 36u) / entsize;
	for (i = 0; i < count; i++) {
		uint32_t entry = acpi_rd32(table + 36u + i * entsize);
		uint32_t fadt_len;

		if (!entry || !acpi_readable(entry, 36)) continue;
		if (!acpi_signature_is(entry, "FACP")) continue;

		fadt_len = acpi_rd32(entry + 4);
		if (fadt_len < 36 || fadt_len > 4096u) continue;
		if (!acpi_readable(entry, fadt_len)) continue;
		if (acpi_checksum(entry, fadt_len) != 0) continue;
		return entry;
	}
	return 0;
}

/* longitud del objeto AML PkgLength; devuelve 0 si no cabe en el buffer */
static uint32_t aml_pkg_length(const uint8_t *p, const uint8_t *end,
                               uint32_t *consumed) {
	uint32_t extra;
	uint32_t value;
	uint32_t i;

	if (p >= end) return 0;
	extra = (uint32_t)(p[0] >> 6);
	if (extra == 0) {
		*consumed = 1;
		return (uint32_t)(p[0] & 0x3Fu);
	}
	if (p + extra >= end) return 0;

	value = (uint32_t)(p[0] & 0x0Fu);
	for (i = 0; i < extra; i++)
		value |= (uint32_t)p[1 + i] << (4 + 8 * i);
	*consumed = 1 + extra;
	return value;
}

/* lee un entero AML constante (Byte/Word/DWord/Zero/One/Ones) */
static int aml_read_int(const uint8_t **pp, const uint8_t *end, uint8_t *out) {
	const uint8_t *p = *pp;
	uint32_t value;

	if (p >= end) return 0;
	switch (*p) {
	case 0x00: value = 0; p += 1; break;
	case 0x01: value = 1; p += 1; break;
	case 0xFF: value = 0xFF; p += 1; break;
	case 0x0A:
		if (p + 2 > end) return 0;
		value = p[1]; p += 2; break;
	case 0x0B:
		if (p + 3 > end) return 0;
		value = (uint32_t)p[1] | ((uint32_t)p[2] << 8);
		p += 3; break;
	case 0x0C:
		if (p + 5 > end) return 0;
		value = (uint32_t)p[1] | ((uint32_t)p[2] << 8) |
		        ((uint32_t)p[3] << 16) | ((uint32_t)p[4] << 24);
		p += 5; break;
	default:
		return 0;   /* referencia o expresion: no soportada */
	}
	*out = (uint8_t)value;
	*pp = p;
	return 1;
}

/* Busca el objeto Name(_S5_, Package(){SLP_TYPa, SLP_TYPb}) en el DSDT.
 * El parseo es deliberadamente conservador: si el AML no se entiende o los
 * valores no son de 3 bits, se descarta y el llamante usa el respaldo 5. */
static int acpi_find_s5(uint32_t dsdt, uint8_t *typa, uint8_t *typb) {
	const uint8_t *base;
	const uint8_t *end;
	uint32_t dsdt_len;
	uint32_t i;

	if (!acpi_readable(dsdt, 36)) return 0;
	dsdt_len = acpi_rd32(dsdt + 4);
	if (dsdt_len < 36 || dsdt_len > 0x100000u) return 0;
	if (!acpi_readable(dsdt, dsdt_len)) return 0;

	base = (const uint8_t *)(uintptr_t)dsdt;
	end = base + dsdt_len;

	for (i = 0; i + 8 < dsdt_len; i++) {
		const uint8_t *p;
		const uint8_t *pkg_end;
		uint32_t consumed = 0;
		uint32_t pkg_len;
		uint32_t guard;
		uint8_t a = 0, b = 0;
		uint8_t num_elements;

		if (!(base[i] == '_' && base[i + 1] == 'S' &&
		      base[i + 2] == '5' && base[i + 3] == '_'))
			continue;

		p = base + i + 4;
		/* localizar el PackageOp (0x12) sin salir del NameString */
		for (guard = 0; p < end && *p != 0x12 && guard < 32; guard++)
			p++;
		if (p >= end || *p != 0x12) continue;
		p++;

		/* PkgLength incluye sus propios bytes; el paquete termina en
		 * p + pkg_len (contando desde el byte de PkgLength) */
		consumed = 0;
		pkg_len = aml_pkg_length(p, end, &consumed);
		if (pkg_len < consumed + 1u) continue;
		pkg_end = p + pkg_len;
		if (pkg_end > end) continue;
		p += consumed;

		/* NumElements y despues los elementos (Normalmente dos: SLP_TYPa
		 * y SLP_TYPb; QEMU publica cuatro ceros). Solo interesan los dos
		 * primeros enteros constantes. */
		num_elements = *p++;
		if (num_elements < 2) continue;
		if (!aml_read_int(&p, pkg_end, &a)) continue;
		if (!aml_read_int(&p, pkg_end, &b)) continue;
		if ((a & 0xF8u) || (b & 0xF8u)) continue;  /* SLP_TYP: 3 bits */

		*typa = a;
		*typb = b;
		return 1;
	}
	return 0;
}

/* Intenta apagar via ACPI. Devuelve 1 si se disparo la escritura en PM1a
 * (aunque el equipo no se apague, cosa que el llamante comprobara) y 0 si
 * no hay ACPI utilizable. */
static int acpi_poweroff(void) {
	uint32_t rsdp;
	uint32_t fadt;
	uint32_t pm1a_cnt;
	uint32_t pm1b_cnt;
	uint32_t dsdt;
	uint32_t smi_cmd;
	uint8_t acpi_enable;
	uint8_t slp_typa = ACPI_SLP_FALLBACK;
	uint8_t slp_typb = ACPI_SLP_FALLBACK;
	uint16_t value;
	int s5_ok = 0;

	rsdp = acpi_find_rsdp();
	if (!rsdp) return 0;
	fadt = acpi_find_fadt(rsdp);
	if (!fadt) {
		serial_write("SEREOS_SHUTDOWN:no_fadt\n");
		return 0;
	}

	pm1a_cnt = acpi_rd32(fadt + 0x40);   /* PM1a_CNT_BLK */
	pm1b_cnt = acpi_rd32(fadt + 0x44);   /* PM1b_CNT_BLK */
	if (!pm1a_cnt || pm1a_cnt > 0xFFFFu) {
		serial_write("SEREOS_SHUTDOWN:no_pm1a\n");
		return 0;
	}

	/* Si el SMM aun no entrego el control de ACPI, pedirle que lo haga.
	 * Todo con timeout: no se espera indefinidamente a un SMI. */
	smi_cmd = acpi_rd32(fadt + 0x30);
	acpi_enable = acpi_rd8(fadt + 0x34);
	if (smi_cmd && acpi_enable && (inw((uint16_t)pm1a_cnt) & 1u) == 0) {
		uint32_t tries;

		outb((uint16_t)smi_cmd, acpi_enable);
		for (tries = 0; tries < 200000u; tries++) {
			if (inw((uint16_t)pm1a_cnt) & 1u) break;
			io_wait();
		}
	}

	/* _S5 del DSDT si el AML es parseable; si no, SLP_TYP = 5.
	 * DSDT esta en FADT+0x28; ACPI 2.0+ anade X_DSDT (64 bits) en
	 * FADT+0x8C, que se prefiere si su parte baja es accesible. */
	dsdt = acpi_rd32(fadt + 0x28);
	if (acpi_rd32(fadt + 4) >= 0x94u) {
		uint32_t x_dsdt = acpi_rd32(fadt + 0x8Cu);

		if (x_dsdt && acpi_readable(x_dsdt, 36)) dsdt = x_dsdt;
	}
	if (dsdt && acpi_readable(dsdt, 36))
		s5_ok = acpi_find_s5(dsdt, &slp_typa, &slp_typb);

	serial_printf("SEREOS_SHUTDOWN:acpi pm1a=0x%04x pm1b=0x%04x "
	              "slp_typ=%u/%u s5=%d\n",
	              (unsigned)pm1a_cnt, (unsigned)pm1b_cnt,
	              (unsigned)slp_typa, (unsigned)slp_typb, s5_ok);

	value = (uint16_t)(((uint16_t)(slp_typa & 7u) << ACPI_SLP_SHIFT) |
	                   ACPI_SLP_EN);
	outw((uint16_t)pm1a_cnt, value);
	if (pm1b_cnt && pm1b_cnt <= 0xFFFFu) {
		uint16_t value_b = (uint16_t)
			(((uint16_t)(slp_typb & 7u) << ACPI_SLP_SHIFT) |
			 ACPI_SLP_EN);

		outw((uint16_t)pm1b_cnt, value_b);
	}
	return 1;
}

/* ------------------------------------------------------------------ */
/* cascada de respaldo                                                 */
/* ------------------------------------------------------------------ */

static void shutdown_port_cascade(void) {
	serial_write("SEREOS_SHUTDOWN:port_0x604\n");
	outw(0x604, 0x2000);      /* QEMU moderno (ACPI PM en i440fx/q35) */
	shutdown_spin_ms(300);

	serial_write("SEREOS_SHUTDOWN:port_0xB004\n");
	outw(0xB004, 0x2000);     /* QEMU antiguo / Bochs */
	shutdown_spin_ms(300);

	serial_write("SEREOS_SHUTDOWN:port_0x4004\n");
	outw(0x4004, 0x3400);     /* VirtualBox */
	shutdown_spin_ms(300);
}

/* isa-debug-exit: QEMU solo lo emula si se arranca con
 * `-device isa-debug-exit`; sin el dispositivo la escritura se ignora. */
static void shutdown_isa_debug_exit(void) {
	serial_write("SEREOS_SHUTDOWN:isa_debug_exit\n");
	shutdown_outl(0x501, 0x31);
	shutdown_spin_ms(100);
}

/* ------------------------------------------------------------------ */
/* parada segura                                                       */
/* ------------------------------------------------------------------ */

static void shutdown_halt_safe(void) {
	serial_write("SEREOS_POWEROFF_SAFE\n");
	shutdown_show_screen("Ya puedes apagar el equipo con seguridad",
	                     "SereOS se ha detenido; ya no hay datos en uso");
	terminal_write("Ya puedes apagar el equipo con seguridad.\n");
	cli();
	for (;;) hlt();
}

/* ------------------------------------------------------------------ */
/* API publica                                                         */
/* ------------------------------------------------------------------ */

/* Reinicio real: misma pantalla de despedida, ~1 s, y pulso de reset por el
 * controlador de teclado 8042 (outb(0x64, 0xFE)), igual que hacia desktop.c.
 * Si el reset no llega a producirse, la CPU queda detenida con cli+hlt. */
void sereos_restart(void) {
	audio_stop();
	serial_write("SEREOS_RESTART\n");
	shutdown_show_screen("Reiniciando...",
	                     "SereOS esta reiniciando el sistema");
	outb(0x64, 0xFE);
	shutdown_spin_ms(200);
	cli();
	for (;;) hlt();
}

int sereos_shutdown_available(void) {
	/* SereOS siempre puede intentar el apagado: ACPI si la maquina lo
	 * expone y, en su defecto, la cascada de puertos y la parada segura. */
	return 1;
}

void sereos_shutdown(void) {
	shutdown_prepare();

	/* 1. ACPI: el mecanismo correcto en hardware real y en QEMU/VBox */
	if (acpi_poweroff()) {
		/* si la escritura funciono el equipo ya esta apagado; si no,
		 * dar un margen breve y seguir con la cascada */
		shutdown_spin_ms(700);
	}

	/* 2. puertos con los que los emuladores atienden el apagado */
	shutdown_port_cascade();

	/* 3. ultimo recurso en QEMU con -device isa-debug-exit */
	shutdown_isa_debug_exit();

	/* 4. no se pudo cortar la alimentacion: dejar el equipo en un estado
	 * seguro e indicarle al usuario que ya puede apagarlo a mano */
	shutdown_halt_safe();
}
