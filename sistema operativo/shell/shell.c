/* shell/shell.c - interprete de comandos reutilizable de SereOS
 *
 * La shell no escribe en ningun dispositivo directamente: emite texto y
 * cambios de color por shell_out_t. Asi comparten exactamente los mismos
 * comandos la terminal grafica del escritorio y la consola VGA de respaldo.
 *
 * Convenios de edicion (documentados para la app de terminal grafica):
 *   - los imprimibles se insertan al final de la linea y se devuelven por
 *     out->write (eco normal);
 *   - '\b' pide al frontend retroceder y borrar la celda anterior;
 *   - al pulsar Enter se emite "\n", se ejecuta y se imprime el nuevo prompt;
 *   - al historial (UP/DOWN) se reescribe la linea con '\b' * longitud;
 *   - el comando clear emite un unico caracter '\f' (0x0C) para que el
 *     frontend limpie su scrollback/pantalla;
 *   - no se usa ninguna secuencia ANSI.
 */
#include <stdint.h>
#include <stddef.h>
#include <stdarg.h>
#include "shell.h"
#include "terminal.h"
#include "input.h"
#include "timer.h"
#include "fs.h"
#include "log.h"
#include "rtc.h"
#include "page.h"
#include "kmalloc.h"
#include "task.h"
#include "scheduler.h"
#include "string.h"
#include "sereos_version.h"
#include "audio.h"
#include "sb16.h"
#include "serial.h"

/* ------------------------------------------------------------------ */
/* salida por callbacks                                               */
/* ------------------------------------------------------------------ */

static void out_write(shell_t *sh, const char *text) {
	if (!sh || !text || !sh->out.write) return;
	sh->out.write(sh->out.ctx, text);
}

static void out_color(shell_t *sh, shell_color_t color) {
	if (!sh || !sh->out.set_color) return;
	sh->out.set_color(sh->out.ctx, color);
}

static void out_line(shell_t *sh, const char *text) {
	out_write(sh, text);
	out_write(sh, "\n");
}

/* escribe una linea formateada con el color indicado (vuelve a DEFAULT) */
static void out_fmt(shell_t *sh, shell_color_t color, const char *fmt, ...) {
	char buf[192];
	va_list ap;
	va_start(ap, fmt);
	vsnprintf(buf, sizeof(buf), fmt, ap);
	va_end(ap);
	out_color(sh, color);
	out_write(sh, buf);
	out_color(sh, SH_COLOR_DEFAULT);
}

/* ------------------------------------------------------------------ */
/* utilidades de cadenas y numeros                                    */
/* ------------------------------------------------------------------ */

static void str_copy_limited(char *dst, const char *src) {
	size_t n = strlen(src);
	if (n > SHELL_LINE_MAX) n = SHELL_LINE_MAX;
	memcpy(dst, src, n);
	dst[n] = 0;
}

static char *skip_spaces(char *p) {
	while (*p == ' ') p++;
	return p;
}

/* toma el siguiente argumento (hasta espacio) de *args y lo termina en NUL */
static char *arg_next(char **args) {
	char *p = skip_spaces(*args);
	if (!*p) { *args = p; return 0; }
	char *start = p;
	while (*p && *p != ' ') p++;
	if (*p) { *p = 0; p++; }
	*args = p;
	return start;
}

static uint32_t percent_u32(uint32_t part, uint32_t total) {
	if (total == 0) return 0;
	if (part >= total) return 100;
	return (uint32_t)(((uint64_t)part * 100u) / total);
}

static uint32_t to_kib(uint32_t bytes) { return bytes / 1024u; }
static uint32_t to_mib(uint32_t bytes) { return bytes / (1024u * 1024u); }

/* ------------------------------------------------------------------ */
/* banner y prompt                                                     */
/* ------------------------------------------------------------------ */

void shell_attach(shell_t *sh, shell_out_t out) {
	if (!sh) return;
	sh->out = out;
	sh->len = 0;
	sh->cursor = 0;
	sh->line[0] = 0;
	sh->saved[0] = 0;
	sh->hist_count = 0;
	sh->hist_pos = -1;
	for (int i = 0; i < SHELL_HISTORY; i++) sh->history[i][0] = 0;
}

void shell_banner(shell_t *sh) {
	if (!sh) return;
	out_color(sh, SH_COLOR_ACCENT);
	out_write(sh, SEREOS_NAME " " SEREOS_VERSION " \"" SEREOS_CODENAME "\" - consola de comandos\n");
	out_color(sh, SH_COLOR_INFO);
	out_write(sh, "Distribucion US  |  Backspace borra  |  flechas ARRIBA/ABAJO: historial\n");
	out_write(sh, "Escriba 'help' para la lista de comandos y 'about' para informacion.\n");
	out_color(sh, SH_COLOR_DIM);
	out_write(sh, "Escritorio grafico: F1 Archivos  F2 Terminal  F3 Monitor  F4 Juego  F5 Acerca\n");
	out_color(sh, SH_COLOR_DEFAULT);
	out_write(sh, "\n");
}

void shell_prompt(shell_t *sh) {
	if (!sh) return;
	out_color(sh, SH_COLOR_ACCENT);
	out_write(sh, "sereos> ");
	out_color(sh, SH_COLOR_DEFAULT);
}

/* ------------------------------------------------------------------ */
/* edicion de linea e historial                                        */
/* ------------------------------------------------------------------ */

static void history_add(shell_t *sh, const char *line) {
	if (!line || !line[0]) return;

	/* no repetir el ultimo comando consecutivo */
	if (sh->hist_count > 0 &&
	    strncmp(sh->history[sh->hist_count - 1], line, SHELL_LINE_MAX) == 0)
		return;

	if (sh->hist_count < SHELL_HISTORY) {
		str_copy_limited(sh->history[sh->hist_count], line);
		sh->hist_count++;
	} else {
		for (int i = 1; i < SHELL_HISTORY; i++)
			strcpy(sh->history[i - 1], sh->history[i]);
		str_copy_limited(sh->history[SHELL_HISTORY - 1], line);
	}
}

/* reescribe la linea actual: retrocede con '\b' y escribe el texto nuevo */
static void line_replace(shell_t *sh, const char *text) {
	int old = sh->len;
	size_t n = strlen(text);
	if (n > SHELL_LINE_MAX) n = SHELL_LINE_MAX;

	for (int i = 0; i < old; i++) out_write(sh, "\b");

	memcpy(sh->line, text, n);
	sh->line[n] = 0;
	sh->len = (int)n;
	sh->cursor = sh->len;
	out_write(sh, sh->line);
}

static void history_navigate(shell_t *sh, int direction) {
	if (sh->hist_count == 0) return;

	if (direction < 0) {
		/* ARRIBA: primera vez guarda la linea actual sin ejecutar */
		if (sh->hist_pos == -1) {
			str_copy_limited(sh->saved, sh->line);
		}
		if (sh->hist_pos + 1 < sh->hist_count) sh->hist_pos++;
	} else {
		/* ABAJO */
		if (sh->hist_pos < 0) return;
		sh->hist_pos--;
	}

	const char *target;
	if (sh->hist_pos >= 0)
		target = sh->history[sh->hist_count - 1 - sh->hist_pos];
	else
		target = sh->saved;
	line_replace(sh, target);
}

void shell_feed(shell_t *sh, char ch) {
	if (!sh) return;

	if (ch == '\n' || ch == '\r') {
		out_write(sh, "\n");
		sh->line[sh->len] = 0;

		if (sh->len > 0) {
			char command[SHELL_LINE_MAX + 1];
			str_copy_limited(command, sh->line);
			history_add(sh, command);
			sh->len = 0;
			sh->cursor = 0;
			sh->hist_pos = -1;
			sh->line[0] = 0;
			shell_exec_line(sh, command);
		} else {
			sh->len = 0;
			sh->cursor = 0;
			sh->hist_pos = -1;
		}
		shell_prompt(sh);
		return;
	}

	if (ch == '\b') {
		if (sh->len > 0) {
			sh->len--;
			sh->cursor = sh->len;
			sh->line[sh->len] = 0;
			sh->hist_pos = -1;
			out_write(sh, "\b");
		}
		return;
	}

	if (ch >= 32 && ch < 127) {
		if (sh->len < SHELL_LINE_MAX) {
			char tmp[2];
			sh->line[sh->len++] = ch;
			sh->line[sh->len] = 0;
			sh->cursor = sh->len;
			sh->hist_pos = -1;
			tmp[0] = ch;
			tmp[1] = 0;
			out_write(sh, tmp);
		}
	}
}

void shell_feed_key(shell_t *sh, uint16_t key, char ch) {
	if (!sh) return;
	switch (key) {
	case KEY_ENTER:
		shell_feed(sh, '\n');
		break;
	case KEY_BACKSPACE:
		shell_feed(sh, '\b');
		break;
	case KEY_UP:
		history_navigate(sh, -1);
		break;
	case KEY_DOWN:
		history_navigate(sh, +1);
		break;
	case KEY_LEFT:
	case KEY_RIGHT:
		/* edicion solo al final de la linea: sin cursor intramedio */
		break;
	case KEY_TAB:
		break;
	default:
		if (ch >= 32 && ch < 127) shell_feed(sh, ch);
		break;
	}
}

/* ------------------------------------------------------------------ */
/* comandos                                                            */
/* ------------------------------------------------------------------ */

static void cmd_help(shell_t *sh) {
	static const char help_text[] =
		"  help              esta ayuda\n"
		"  clear             limpia la pantalla/scrollback\n"
		"  about             informacion de SereOS\n"
		"  version           version y datos de compilacion\n"
		"  sysinfo           resumen real del sistema\n"
		"  mem               memoria fisica detectada\n"
		"  free              memoria libre y heap del kernel\n"
		"  ticks             ticks del PIT y tiempo encendido\n"
		"  dmesg             registro del kernel con marcas de tiempo\n"
		"  date / time       fecha y hora del reloj CMOS\n"
		"  echo <texto>      repite el texto\n"
		"  scroll            imprime 30 lineas (prueba de scroll)\n"
		"  div0              provoca una division por cero (prueba de la IDT)\n"
		"  audio             backend de audio detectado (SB16/PC speaker)\n"
		"  beep [hz] [ms]    reproduce un tono (por defecto 880 Hz, 150 ms)\n"
		"  audiotest         secuencia de tonos + marca AUDIO_TEST en el puerto serie\n"
		"  pwd               directorio actual del RAMFS\n"
		"  ls [ruta]         lista un directorio\n"
		"  cd <ruta>         cambia de directorio\n"
		"  mkdir <ruta>      crea un directorio\n"
		"  touch <archivo>   crea un archivo vacio\n"
		"  cat <archivo>     muestra un archivo de texto\n"
		"  write <archivo> <texto>  escribe texto en un archivo\n"
		"  rm <ruta>         borra un archivo o directorio vacio\n";
	out_color(sh, SH_COLOR_ACCENT);
	out_write(sh, "Comandos disponibles:\n");
	out_color(sh, SH_COLOR_DEFAULT);
	out_write(sh, help_text);
}

static void cmd_about(shell_t *sh) {
	out_color(sh, SH_COLOR_ACCENT);
	out_write(sh, SEREOS_NAME " " SEREOS_VERSION " \"" SEREOS_CODENAME "\"\n");
	out_color(sh, SH_COLOR_DEFAULT);
	out_write(sh, "Sistema operativo propio para x86 de 32 bits, kernel monolitico.\n");
	out_write(sh, "Arranque " SEREOS_BOOT ", sin libc y sin dependencias de Linux.\n");
	out_write(sh, "Componentes: GDT, IDT con excepciones, PIC 8259, PIT, teclado y\n");
	out_write(sh, "raton PS/2, consola VGA, framebuffer, RAMFS, planificador cooperativo,\n");
	out_write(sh, "escritorio grafico y shell compartida.\n");
	out_write(sh, "Proyecto final de Sistemas Operativos - UMB 2026\n");
}

static void cmd_version(shell_t *sh) {
	out_fmt(sh, SH_COLOR_ACCENT, "%s %s \"%s\" (build %s)\n",
	        SEREOS_NAME, SEREOS_VERSION, SEREOS_CODENAME, SEREOS_BUILD);
	out_fmt(sh, SH_COLOR_DEFAULT, "Arquitectura : %s\n", SEREOS_ARCH);
	out_fmt(sh, SH_COLOR_DEFAULT, "Kernel       : %s\n", SEREOS_KERNEL);
	out_fmt(sh, SH_COLOR_DEFAULT, "Arranque     : %s\n", SEREOS_BOOT);
}

static void cmd_ticks(shell_t *sh) {
	uint32_t t = timer_ticks();
	uint32_t hz = timer_hz() ? timer_hz() : 100;
	out_fmt(sh, SH_COLOR_DEFAULT, "Ticks PIT    : %u a %u Hz\n", t, hz);
	out_fmt(sh, SH_COLOR_DEFAULT, "Tiempo       : %u ms (%u s)\n",
	        timer_uptime_ms(), timer_uptime_sec());
}

static void cmd_mem(shell_t *sh) {
	uint32_t total = page_total_bytes();
	uint32_t used = page_used_bytes();
	out_fmt(sh, SH_COLOR_ACCENT, "Memoria fisica detectada\n");
	out_fmt(sh, SH_COLOR_DEFAULT, "  Total : %u KiB (%u MiB)\n", to_kib(total), to_mib(total));
	out_fmt(sh, SH_COLOR_DEFAULT, "  Usada : %u KiB (%u MiB, %u %%)\n",
	        to_kib(used), to_mib(used), percent_u32(used, total));
	out_fmt(sh, SH_COLOR_DEFAULT, "  Libre : %u KiB (%u MiB)\n",
	        to_kib(total - used), to_mib(total - used));
	out_fmt(sh, SH_COLOR_DIM, "  Marcos de %u bytes: %u totales, %u libres, %u usados\n",
	        page_frame_size(), page_total_frames(), page_free_frames(), page_used_frames());
}

static void cmd_free(shell_t *sh) {
	uint32_t total = page_total_bytes();
	uint32_t used = page_used_bytes();
	uint32_t freeb = (total >= used) ? total - used : 0;

	out_fmt(sh, SH_COLOR_ACCENT, "Memoria fisica (page allocator)\n");
	out_fmt(sh, SH_COLOR_DEFAULT, "  Total : %u KiB (%u MiB)\n", to_kib(total), to_mib(total));
	out_fmt(sh, SH_COLOR_DEFAULT, "  Usada : %u KiB (%u %%)\n", to_kib(used), percent_u32(used, total));
	out_fmt(sh, SH_COLOR_DEFAULT, "  Libre : %u KiB (%u MiB)\n", to_kib(freeb), to_mib(freeb));
	out_fmt(sh, SH_COLOR_DIM, "  Marcos de %u bytes: %u totales, %u libres, %u usados\n",
	        page_frame_size(), page_total_frames(), page_free_frames(), page_used_frames());

	out_fmt(sh, SH_COLOR_ACCENT, "Heap del kernel (kmalloc)\n");
	out_fmt(sh, SH_COLOR_DEFAULT, "  Total : %u KiB\n", to_kib(heap_total()));
	out_fmt(sh, SH_COLOR_DEFAULT, "  Usado : %u KiB (%u %%), libre: %u KiB\n",
	        to_kib(heap_used()), percent_u32(heap_used(), heap_total()), to_kib(heap_free()));
	out_fmt(sh, SH_COLOR_DIM, "  Bloque libre mayor: %u KiB, asignaciones: %u\n",
	        to_kib(heap_largest_free()), heap_alloc_count());

	out_fmt(sh, SH_COLOR_ACCENT, "RAMFS\n");
	out_fmt(sh, SH_COLOR_DEFAULT, "  Nodos: %d, usado: %u B de %u B\n",
	        fs_node_count(), fs_used_bytes(), fs_capacity_bytes());
}

static void cmd_sysinfo(shell_t *sh) {
	out_fmt(sh, SH_COLOR_ACCENT, "Sistema : %s %s \"%s\" (%s)\n",
	        SEREOS_NAME, SEREOS_VERSION, SEREOS_CODENAME, SEREOS_ARCH);
	out_fmt(sh, SH_COLOR_DEFAULT, "Kernel  : %s, arranque %s, build %s\n",
	        SEREOS_KERNEL, SEREOS_BOOT, SEREOS_BUILD);

	uint32_t total = page_total_bytes();
	uint32_t used = page_used_bytes();
	out_fmt(sh, SH_COLOR_DEFAULT, "Memoria : %u KiB totales, %u KiB libres, %u KiB usadas (%u %%)\n",
	        to_kib(total), to_kib(total >= used ? total - used : 0), to_kib(used),
	        percent_u32(used, total));
	out_fmt(sh, SH_COLOR_DEFAULT, "Marcos  : %u de %u bytes (libres %u, usados %u)\n",
	        page_total_frames(), page_frame_size(), page_free_frames(), page_used_frames());
	out_fmt(sh, SH_COLOR_DEFAULT, "Heap    : %u KiB usados de %u KiB (%u asignaciones)\n",
	        to_kib(heap_used()), to_kib(heap_total()), heap_alloc_count());
	out_fmt(sh, SH_COLOR_DEFAULT, "RAMFS   : %d nodos, %u B usados de %u B\n",
	        fs_node_count(), fs_used_bytes(), fs_capacity_bytes());
	out_fmt(sh, SH_COLOR_DEFAULT, "Tareas  : %d activas de %d slots; scheduler: %u pasos, %u activaciones\n",
	        task_active_count(), task_total_slots(), scheduler_steps(), scheduler_activations());
	out_fmt(sh, SH_COLOR_DEFAULT, "Tiempo  : uptime %u s, PIT %u Hz, %u ticks\n",
	        timer_uptime_sec(), timer_hz(), timer_ticks());

	char datebuf[32], timebuf[32];
	if (rtc_available()) {
		rtc_date_string(datebuf, sizeof(datebuf));
		rtc_time_string(timebuf, sizeof(timebuf));
		out_fmt(sh, SH_COLOR_DEFAULT, "RTC     : %s %s\n", datebuf, timebuf);
	} else {
		out_fmt(sh, SH_COLOR_WARN, "RTC     : no disponible\n");
	}
}

static void cmd_dmesg(shell_t *sh) {
	int n = klog_count();
	uint32_t hz = timer_hz() ? timer_hz() : 100;

	if (n <= 0) {
		out_fmt(sh, SH_COLOR_DIM, "dmesg: el registro del kernel esta vacio\n");
		return;
	}

	out_fmt(sh, SH_COLOR_ACCENT, "Registro del kernel: %d entradas, %d errores\n",
	        n, klog_errors());
	for (int i = 0; i < n; i++) {
		uint32_t t = klog_entry_tick(i);
		uint32_t sec = t / hz;
		uint32_t frac = ((t % hz) * 100u) / hz;
		const char *text = klog_line(i);
		out_fmt(sh, SH_COLOR_DEFAULT, "[%5u.%02u] %s\n", sec, frac, text ? text : "");
	}
}

static void cmd_date(shell_t *sh) {
	if (!rtc_available()) {
		out_fmt(sh, SH_COLOR_ERR, "date: el RTC CMOS no esta disponible\n");
		return;
	}
	char buf[32];
	out_fmt(sh, SH_COLOR_DEFAULT, "%s\n", rtc_date_string(buf, sizeof(buf)));
}

static void cmd_time(shell_t *sh) {
	if (!rtc_available()) {
		out_fmt(sh, SH_COLOR_ERR, "time: el RTC CMOS no esta disponible\n");
		return;
	}
	char buf[32];
	out_fmt(sh, SH_COLOR_DEFAULT, "%s\n", rtc_time_string(buf, sizeof(buf)));
}

static void cmd_scroll(shell_t *sh) {
	for (uint32_t i = 1; i <= 30; i++)
		out_fmt(sh, SH_COLOR_DEFAULT, "Linea %u de 30 (prueba de desplazamiento)\n", i);
}

static void cmd_div0(shell_t *sh) {
	out_fmt(sh, SH_COLOR_WARN, "Provocando una division por cero real (prueba de la IDT)...\n");
	volatile int a = 10;
	volatile int b = 0;
	volatile int c = a / b;
	(void)c;
}

/* ------------------------------------------------------------------ */
/* audio: diagnostico visible (audio / beep / audiotest)              */
/* ------------------------------------------------------------------ */

static void cmd_audio(shell_t *sh) {
	out_fmt(sh, SH_COLOR_ACCENT, "Audio de SereOS\n");
	out_fmt(sh, SH_COLOR_DEFAULT, "  Backend : %s\n", audio_backend());
	out_fmt(sh, SH_COLOR_DEFAULT, "  Detalle : %s\n", audio_detail());
	out_fmt(sh, SH_COLOR_DEFAULT, "  PCM     : %u Hz (0 = el altavoz del PC no reproduce PCM)\n",
	        audio_sample_rate());
	out_fmt(sh, SH_COLOR_DEFAULT, "  SFX     : %u reproducciones, %u descartadas\n",
	        audio_play_count(), audio_underruns());
	if (sb16_present()) {
		uint16_t ver = sb16_version();
		out_fmt(sh, SH_COLOR_DEFAULT, "  DSP     : %u.%u, IRQ %d, DMA %d\n",
		        (unsigned)(ver >> 8), (unsigned)(ver & 0xFF),
		        sb16_irq(), (int)SB16_DMA);
		out_fmt(sh, SH_COLOR_DEFAULT, "  DMA fin : %u bloques terminados por IRQ\n",
		        sb16_irq_count());
	}
	out_fmt(sh, SH_COLOR_DIM, "  Pruebas : beep [hz] [ms]  |  audiotest\n");
}

static void cmd_beep(shell_t *sh, char *args) {
	char *a1 = arg_next(&args);
	char *a2 = arg_next(&args);
	uint32_t hz = a1 ? (uint32_t)atoi(a1) : 880u;
	uint32_t ms = a2 ? (uint32_t)atoi(a2) : 150u;

	if (hz < 19u) hz = 19u;
	if (hz > 20000u) hz = 20000u;
	if (ms == 0) ms = 150u;
	if (ms > 2000u) ms = 2000u;

	audio_init();
	if (!audio_available()) {
		out_fmt(sh, SH_COLOR_WARN, "beep: no hay backend de audio disponible\n");
		return;
	}
	audio_stop();
	if (!audio_test_tone(hz, ms)) {
		out_fmt(sh, SH_COLOR_ERR, "beep: el backend %s no pudo reproducir el tono\n",
		        audio_backend());
		return;
	}
	out_fmt(sh, SH_COLOR_OK, "beep: %u Hz durante %u ms por %s\n", hz, ms, audio_backend());
}

static void cmd_audiotest(shell_t *sh) {
	static const uint32_t tones[4] = { 440u, 660u, 880u, 1320u };
	uint32_t ticks0, ticks1, done = 0;
	int i;

	audio_init();
	out_fmt(sh, SH_COLOR_ACCENT, "Prueba de audio (%s)\n", audio_backend());
	out_fmt(sh, SH_COLOR_DEFAULT, "  %s\n", audio_detail());

	/* marcas para verificacion automatica desde el log serie */
	serial_printf("AUDIO_TEST:%s\n", audio_backend());
	serial_printf("AUDIO_DETAIL:%s\n", audio_detail());

	audio_stop();
	ticks0 = timer_ticks();
	for (i = 0; i < 4; i++) {
		if (audio_test_tone(tones[i], 200u)) done++;
	}
	ticks1 = timer_ticks();

	if (done == 0) {
		out_fmt(sh, SH_COLOR_ERR, "audiotest: ningun tono pudo reproducirse\n");
		serial_write("AUDIO_TEST_FAIL\n");
		return;
	}

	out_fmt(sh, SH_COLOR_OK, "  Tonos: %u/4 (440/660/880/1320 Hz, 200 ms)\n", done);
	/* el canal 2 del PIT no debe haber tocado el canal 0 (100 Hz) */
	out_fmt(sh, SH_COLOR_DEFAULT, "  PIT: %u Hz, %u ticks durante la prueba\n",
	        timer_hz(), ticks1 - ticks0);
	if (sb16_present())
		out_fmt(sh, SH_COLOR_DEFAULT, "  SB16: IRQ %d, %u fines de DMA por interrupcion\n",
		        sb16_irq(), sb16_irq_count());

	serial_printf("AUDIO_TEST_DONE tones=%u irq=%u pit_hz=%u pit_ticks=%u\n",
	              done, sb16_present() ? (unsigned)sb16_irq_count() : 0u,
	              timer_hz(), ticks1 - ticks0);
	out_fmt(sh, SH_COLOR_DIM,
	        "  En el anfitrion se oye con SB16 + audiodev (docs/AUDIO_VM.md)\n");
}

static void cmd_ls(shell_t *sh, char *args) {
	char *path = arg_next(&args);
	int dir = fs_cwd();

	if (path && path[0]) {
		dir = fs_lookup(path);
		if (dir < 0) {
			out_fmt(sh, SH_COLOR_ERR, "ls: no existe '%s'\n", path);
			return;
		}
	}
	if (!fs_is_dir(dir)) {
		out_fmt(sh, SH_COLOR_ERR, "ls: '%s' no es un directorio (use cat)\n", path ? path : ".");
		return;
	}

	fs_dirent_t entries[FS_MAX_NODES];
	int n = fs_list(dir, entries, FS_MAX_NODES);
	if (n < 0) {
		out_fmt(sh, SH_COLOR_ERR, "ls: no se pudo leer el directorio\n");
		return;
	}
	if (n == 0) {
		out_fmt(sh, SH_COLOR_DIM, "(directorio vacio)\n");
		return;
	}

	for (int i = 0; i < n; i++) {
		int is_dir = entries[i].is_dir ? 1 : 0;
		int nlen = (int)strlen(entries[i].name);
		int padn = 30 - nlen;
		char padding[40];

		if (padn < 1) padn = 1;
		if (padn > (int)sizeof(padding) - 1) padn = (int)sizeof(padding) - 1;
		for (int j = 0; j < padn; j++) padding[j] = ' ';
		padding[padn] = 0;

		out_color(sh, is_dir ? SH_COLOR_ACCENT : SH_COLOR_DEFAULT);
		out_write(sh, is_dir ? "d  " : "-  ");
		out_write(sh, entries[i].name);
		out_write(sh, padding);
		out_color(sh, SH_COLOR_DIM);
		out_fmt(sh, SH_COLOR_DIM, "%u B\n", entries[i].size);
		out_color(sh, SH_COLOR_DEFAULT);
	}
}

static void cmd_cd(shell_t *sh, char *args) {
	char *path = arg_next(&args);
	const char *target = (path && path[0]) ? path : "/";
	if (fs_chdir(target) < 0)
		out_fmt(sh, SH_COLOR_ERR, "cd: no se pudo entrar en '%s'\n", target);
}

static void cmd_pwd(shell_t *sh) {
	char buf[FS_PATH_MAX];
	fs_getcwd(buf, sizeof(buf));
	out_line(sh, buf);
}

static void cmd_mkdir(shell_t *sh, char *args) {
	char *path = arg_next(&args);
	if (!path) {
		out_fmt(sh, SH_COLOR_WARN, "uso: mkdir <ruta>\n");
		return;
	}
	if (fs_mkdir(path) < 0)
		out_fmt(sh, SH_COLOR_ERR, "mkdir: no se pudo crear '%s'\n", path);
}

static void cmd_touch(shell_t *sh, char *args) {
	char *path = arg_next(&args);
	if (!path) {
		out_fmt(sh, SH_COLOR_WARN, "uso: touch <archivo>\n");
		return;
	}
	if (fs_create(path) < 0)
		out_fmt(sh, SH_COLOR_ERR, "touch: no se pudo crear '%s'\n", path);
}

static void cmd_rm(shell_t *sh, char *args) {
	char *path = arg_next(&args);
	if (!path) {
		out_fmt(sh, SH_COLOR_WARN, "uso: rm <ruta>\n");
		return;
	}
	if (fs_delete(path) < 0)
		out_fmt(sh, SH_COLOR_ERR, "rm: no se pudo borrar '%s'\n", path);
}

static void cmd_cat(shell_t *sh, char *args) {
	char *path = arg_next(&args);
	if (!path) {
		out_fmt(sh, SH_COLOR_WARN, "uso: cat <archivo>\n");
		return;
	}

	char data[FS_DATA_MAX + 1];
	int n = fs_readfile(path, data, FS_DATA_MAX);
	if (n < 0) {
		out_fmt(sh, SH_COLOR_ERR, "cat: no se pudo leer '%s'\n", path);
		return;
	}

	char chunk[96];
	int used = 0;
	for (int i = 0; i < n; i++) {
		char c = data[i];
		if (c == '\0') c = '.';
		else if (c != '\n' && c != '\t' && (c < 32 || c > 126)) c = '.';
		chunk[used++] = c;
		if (used == (int)sizeof(chunk) - 1) {
			chunk[used] = 0;
			out_write(sh, chunk);
			used = 0;
		}
	}
	if (used > 0) {
		chunk[used] = 0;
		out_write(sh, chunk);
	}
	if (n == 0 || data[n - 1] != '\n') out_write(sh, "\n");
}

static void cmd_write(shell_t *sh, char *args) {
	char *path = arg_next(&args);
	if (!path) {
		out_fmt(sh, SH_COLOR_WARN, "uso: write <archivo> <texto>\n");
		return;
	}
	char *text = skip_spaces(args);
	uint32_t len = (uint32_t)strlen(text);

	if (!fs_exists(path) && fs_create(path) < 0) {
		out_fmt(sh, SH_COLOR_ERR, "write: no se pudo crear '%s'\n", path);
		return;
	}
	int wrote = fs_writefile(path, text, len);
	if (wrote < 0) {
		out_fmt(sh, SH_COLOR_ERR, "write: fallo al escribir en '%s'\n", path);
		return;
	}
	out_fmt(sh, SH_COLOR_OK, "Escritos %u bytes en '%s'\n", (uint32_t)wrote, path);
}

/* ------------------------------------------------------------------ */
/* despacho                                                            */
/* ------------------------------------------------------------------ */

void shell_exec_line(shell_t *sh, const char *line) {
	if (!sh || !line) return;

	char work[SHELL_LINE_MAX + 1];
	str_copy_limited(work, line);

	char *p = skip_spaces(work);
	if (!*p) return;

	char *cmd = p;
	while (*p && *p != ' ') p++;
	if (*p) {
		*p = 0;
		p++;
	}
	char *args = p;

	if (!strcmp(cmd, "help"))            cmd_help(sh);
	else if (!strcmp(cmd, "clear"))     out_write(sh, "\f");
	else if (!strcmp(cmd, "about"))     cmd_about(sh);
	else if (!strcmp(cmd, "version"))   cmd_version(sh);
	else if (!strcmp(cmd, "sysinfo"))   cmd_sysinfo(sh);
	else if (!strcmp(cmd, "mem"))       cmd_mem(sh);
	else if (!strcmp(cmd, "free"))      cmd_free(sh);
	else if (!strcmp(cmd, "ticks"))     cmd_ticks(sh);
	else if (!strcmp(cmd, "dmesg"))     cmd_dmesg(sh);
	else if (!strcmp(cmd, "date"))      cmd_date(sh);
	else if (!strcmp(cmd, "time"))      cmd_time(sh);
	else if (!strcmp(cmd, "scroll"))    cmd_scroll(sh);
	else if (!strcmp(cmd, "div0"))      cmd_div0(sh);
	else if (!strcmp(cmd, "audio"))     cmd_audio(sh);
	else if (!strcmp(cmd, "beep"))      cmd_beep(sh, args);
	else if (!strcmp(cmd, "audiotest")) cmd_audiotest(sh);
	else if (!strcmp(cmd, "pwd"))       cmd_pwd(sh);
	else if (!strcmp(cmd, "ls"))        cmd_ls(sh, args);
	else if (!strcmp(cmd, "cd"))        cmd_cd(sh, args);
	else if (!strcmp(cmd, "mkdir"))     cmd_mkdir(sh, args);
	else if (!strcmp(cmd, "touch"))     cmd_touch(sh, args);
	else if (!strcmp(cmd, "rm"))        cmd_rm(sh, args);
	else if (!strcmp(cmd, "cat"))       cmd_cat(sh, args);
	else if (!strcmp(cmd, "write"))     cmd_write(sh, args);
	else if (!strcmp(cmd, "echo")) {
		out_line(sh, skip_spaces(args));
	} else {
		out_fmt(sh, SH_COLOR_ERR, "Comando no reconocido: '%s' (escriba help)\n", cmd);
	}
}

uint32_t shell_uptime_sec(void) {
	return timer_uptime_sec();
}

/* ------------------------------------------------------------------ */
/* consola VGA de respaldo                                            */
/* ------------------------------------------------------------------ */

static enum vga_color text_out_fg = VGA_LIGHT_GREY;

static void text_out_write(void *ctx, const char *text) {
	(void)ctx;
	if (!text) return;
	for (const char *p = text; *p; p++) {
		if (*p == '\f') {
			terminal_clear();
			continue;
		}
		char one[2];
		one[0] = *p;
		one[1] = 0;
		terminal_write_color(one, text_out_fg);
	}
}

static void text_out_set_color(void *ctx, shell_color_t color) {
	(void)ctx;
	switch (color) {
	case SH_COLOR_OK:      text_out_fg = VGA_LIGHT_GREEN; break;
	case SH_COLOR_ERR:     text_out_fg = VGA_LIGHT_RED;   break;
	case SH_COLOR_INFO:    text_out_fg = VGA_LIGHT_CYAN;  break;
	case SH_COLOR_WARN:    text_out_fg = VGA_YELLOW;      break;
	case SH_COLOR_ACCENT:  text_out_fg = VGA_LIGHT_CYAN;  break;
	case SH_COLOR_DIM:     text_out_fg = VGA_DARK_GREY;   break;
	case SH_COLOR_DEFAULT:
	default:               text_out_fg = VGA_LIGHT_GREY;  break;
	}
}

void shell_run_text(void) {
	static shell_t sh;
	shell_out_t out;

	out.ctx = 0;
	out.write = text_out_write;
	out.set_color = text_out_set_color;

	terminal_clear();
	shell_attach(&sh, out);
	shell_banner(&sh);
	shell_prompt(&sh);

	static const char status_bar[] =
		" " SEREOS_NAME " " SEREOS_VERSION "  |  consola VGA de respaldo  |  help";
	terminal_status(status_bar, shell_uptime_sec());

	for (;;) {
		char c = keyboard_getchar();
		terminal_status(status_bar, shell_uptime_sec());
		shell_feed(&sh, c);
	}
}
