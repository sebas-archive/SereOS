/* apps/about/about.c - informacion de SereOS Desktop
 *
 * Rediseno con el sistema de diseno (theme.h/ui.h/text.h): logotipo y
 * jerarquia tipografica, filas de informacion en dos columnas, rejilla de
 * componentes con puntos de estado y pie con creditos. La disponibilidad se
 * consulta a las APIs reales (nunca valores inventados).
 */
#include <stdint.h>
#include "app.h"
#include "window.h"
#include "theme.h"
#include "ui.h"
#include "text.h"
#include "graphics.h"
#include "icons.h"
#include "logo.h"
#include "page.h"
#include "kmalloc.h"
#include "framebuffer.h"
#include "timer.h"
#include "rtc.h"
#include "input.h"
#include "fs.h"
#include "interrupts.h"
#include "task.h"
#include "scheduler.h"
#include "audio.h"
#include "sereos_version.h"
#include "string.h"
#include "about.h"

#define ABOUT_CHECK_TICKS 100   /* 1 s: solo para detectar cambios reales */

typedef struct {
	const char *name;
	int (*available)(void);
} about_component_t;

typedef struct {
	int      task_id;
	uint32_t last_check;
	uint32_t availability;   /* mascara real de componentes disponibles */
} about_state_t;

/* ------------------------------------------------------------------ */
/* comprobaciones reales de cada subsistema                            */
/* ------------------------------------------------------------------ */
static int av_paging(void)   { return paging_enabled() ? 1 : 0; }
static int av_fb(void)       { return (fb_available() && fb_has_backbuffer()) ? 1 : 0; }
static int av_gfx(void)      { return gfx_ready() ? 1 : 0; }
static int av_heap(void)     { return heap_total() > 0 ? 1 : 0; }
static int av_fs(void)       { return fs_capacity_bytes() > 0 ? 1 : 0; }
static int av_pit(void)      { return timer_hz() > 0 ? 1 : 0; }
static int av_keyboard(void) { return keyboard_available() ? 1 : 0; }
static int av_mouse(void)    { return mouse_present() ? 1 : 0; }
static int av_rtc(void)      { return rtc_available() ? 1 : 0; }
static int av_irq(void)      { return irq_count(0) > 0 ? 1 : 0; }
static int av_sched(void)    { return scheduler_steps() > 0 ? 1 : 0; }
static int av_shell(void)    { return 1; }
static int av_game(void)     { return app_find("game") ? 1 : 0; }
static int av_audio(void)    { return audio_available() ? 1 : 0; }

static const about_component_t about_components[] = {
	{ "Paginacion PSE",     av_paging },
	{ "Framebuffer",        av_fb },
	{ "Motor grafico",      av_gfx },
	{ "Heap kmalloc",       av_heap },
	{ "RAMFS",              av_fs },
	{ "PIT 100 Hz",         av_pit },
	{ "Teclado PS/2",       av_keyboard },
	{ "Raton PS/2",         av_mouse },
	{ "RTC CMOS",           av_rtc },
	{ "GDT/IDT/PIC",        av_irq },
	{ "Planificador",       av_sched },
	{ "Shell compartida",   av_shell },
	{ "PAC-MAN SereOS",      av_game },
	{ "Audio SB16/speaker", av_audio },
};

#define ABOUT_COMPONENT_COUNT ((int)(sizeof(about_components) / sizeof(about_components[0])))

static uint32_t about_availability(void) {
	uint32_t mask = 0;
	int i;
	for (i = 0; i < ABOUT_COMPONENT_COUNT && i < 32; i++) {
		if (about_components[i].available()) mask |= (1u << i);
	}
	return mask;
}

static int about_available_count(void) {
	uint32_t mask = about_availability();
	int i, n = 0;
	for (i = 0; i < ABOUT_COMPONENT_COUNT; i++) if (mask & (1u << i)) n++;
	return n;
}

/* ------------------------------------------------------------------ */
/* utilidades de texto                                                 */
/* ------------------------------------------------------------------ */
static void about_draw_fit(text_style_t style, int x, int y, int maxw,
                           const char *s, uint32_t color) {
	char buf[96];
	int len, lo, hi;

	if (!s || maxw <= 0) return;
	if (text_width(style, s) <= maxw) {
		text_draw(style, x, y, s, color);
		return;
	}
	len = (int)strlen(s);
	if (len > (int)sizeof(buf) - 4) len = (int)sizeof(buf) - 4;
	lo = 0;
	hi = len;
	while (lo < hi) {
		int mid = (lo + hi + 1) / 2;
		memcpy(buf, s, (size_t)mid);
		buf[mid] = '\0';
		strcat(buf, "...");
		if (text_width(style, buf) <= maxw) lo = mid;
		else hi = mid - 1;
	}
	memcpy(buf, s, (size_t)lo);
	buf[lo] = '\0';
	strcat(buf, "...");
	text_draw(style, x, y, buf, color);
}

/* ------------------------------------------------------------------ */
/* dibujo                                                              */
/* ------------------------------------------------------------------ */
static void about_draw(struct window *w) {
	about_state_t *st = (about_state_t *)window_data(w);
	int cx, cy, cw, ch, pad, gap, inner_w, inner_x;
	int logo, logo_w, logo_cx, logo_cy;
	int title_h, body_h, small_h, cap_h;
	int header_text_h, header_h, info_row_h, comp_row_h;
	int info_col_w, info_x0, col_w, comp_rows, block_h, fixed_h;
	int y, i, n_ok, rows, footer_h;
	char countbuf[48];

	if (!st) return;
	cx = window_content_x(w);
	cy = window_content_y(w);
	cw = window_content_w(w);
	ch = window_content_h(w);
	if (cw < 320 || ch < 220) return;

	pad = SP_4;
	gap = SP_4;
	ui_surface(cx, cy, cw, ch, 0, theme.surface, 0);

	/* contenido centrado con ancho maximo para que en maximizado no se
	 * estire en exceso ni queden margenes inconsistentes */
	inner_w = cw - 2 * pad;
	if (inner_w > 780) inner_w = 780;
	inner_x = cx + (cw - inner_w) / 2;

	/* metricas de la tipografia */
	title_h = text_height(TEXT_DISPLAY);
	body_h = text_height(TEXT_BODY);
	small_h = text_height(TEXT_SMALL);
	cap_h = text_height(TEXT_CAPTION);
	info_row_h = small_h + SP_2;
	comp_row_h = body_h + SP_1;
	footer_h = cap_h * 2 + SP_1;

	/* icono Acerca de: insignia "i" en circulo (misma que menu y dock).
	 * El logo S oficial se reserva para la top bar y la cabecera del menu. */
	logo = ABOUT_LOGO;
	logo_w = logo;
	header_text_h = title_h + SP_1 + body_h + SP_1 + small_h;
	header_h = (header_text_h > logo) ? header_text_h : logo;

	/* filas de componentes que caben segun el alto disponible */
	fixed_h = pad * 2 + header_h + SP_3 + 1 + SP_3 + info_row_h * 3 +
	          SP_3 + 1 + SP_2 + cap_h + SP_2 + SP_4 + footer_h;
	comp_rows = (ch - fixed_h) / comp_row_h;
	if (comp_rows > 7) comp_rows = 7;
	if (comp_rows < 0) comp_rows = 0;

	block_h = fixed_h + comp_rows * comp_row_h;
	y = cy + ((ch > block_h) ? (ch - block_h) / 2 : 0) + pad;

	/* ---- cabecera: logotipo + nombre + version + tagline ---- */
	/* RECURSO logo_sereos: la marca oficial (S blanca sobre cuadro azul
	 * redondeado) identifica el contenido de la ventana. El recurso
	 * icono_info (icons_draw_info_badge) es SOLO para los accesos de
	 * Acerca de en el menu, el dock y la topnav; no se usa aqui. */
	logo_cx = inner_x + logo_w / 2;
	logo_cy = y + header_h / 2;
	logo_draw_about(logo_cx, logo_cy, logo);
	{
		int ty = y + (header_h - header_text_h) / 2;
		int name_x = inner_x + logo_w + SP_3;   /* separacion >= SP_3 */

		text_draw(TEXT_DISPLAY, name_x, ty, SEREOS_NAME, theme.text);
		ty += title_h + SP_1;
		text_draw(TEXT_BODY, name_x, ty, SEREOS_VERSION " " SEREOS_CODENAME,
		          theme.text_dim);
		ty += body_h + SP_1;
		text_draw(TEXT_SMALL, name_x, ty, "Sistema operativo original",
		          theme.text_faint);
	}
	y += header_h + SP_3;
	ui_divider(inner_x, y, inner_w);
	y += 1 + SP_3;

	/* ---- filas de informacion en dos columnas de 300 px ---- */
	info_col_w = 300;
	if (info_col_w * 2 + gap > inner_w) info_col_w = (inner_w - gap) / 2;
	info_x0 = inner_x + (inner_w - (2 * info_col_w + gap)) / 2;
	{
		char memval[32], audval[32];

		if (page_total_bytes() > 0)
			snprintf(memval, sizeof(memval), "%u MB",
			         (unsigned)(page_total_bytes() / (1024u * 1024u)));
		else
			snprintf(memval, sizeof(memval), "no disponible");
		{
			const char *detail = audio_detail();

			if (audio_available() && detail && detail[0])
				snprintf(audval, sizeof(audval), "%s", detail);
			else
				snprintf(audval, sizeof(audval), "no disponible");
		}

		ui_kv_row(info_x0, y, info_col_w, "Arquitectura", SEREOS_ARCH);
		ui_kv_row(info_x0 + info_col_w + gap, y, info_col_w, "Kernel",
		          SEREOS_KERNEL);
		ui_kv_row(info_x0, y + info_row_h, info_col_w, "Bootloader",
		          SEREOS_BOOT);
		ui_kv_row(info_x0 + info_col_w + gap, y + info_row_h, info_col_w,
		          "Memoria detectada", memval);
		ui_kv_row(info_x0, y + 2 * info_row_h, info_col_w, "Build",
		          SEREOS_BUILD);
		ui_kv_row(info_x0 + info_col_w + gap, y + 2 * info_row_h,
		          info_col_w, "Audio", audval);
	}
	y += 3 * info_row_h + SP_3;
	ui_divider(inner_x, y, inner_w);
	y += 1 + SP_2;

	/* ---- seccion de componentes ---- */
	n_ok = about_available_count();
	ui_section_title(inner_x, y, "Componentes");
	snprintf(countbuf, sizeof(countbuf), "%d/%d disponibles",
	         n_ok, ABOUT_COMPONENT_COUNT);
	text_draw_right(TEXT_CAPTION, inner_x + inner_w, y, countbuf,
	                n_ok == ABOUT_COMPONENT_COUNT ? theme.green : theme.amber);
	y += cap_h + SP_2;

	rows = 7;   /* 14 componentes en 2 columnas */
	col_w = (inner_w - gap) / 2;
	for (i = 0; i < ABOUT_COMPONENT_COUNT && i < rows * 2; i++) {
		int col = i / rows;
		int row = i % rows;
		int col_x = inner_x + col * (col_w + gap);
		int row_y;
		int ok, ty, dot_y;

		if (row >= comp_rows) continue;
		row_y = y + row * comp_row_h;
		ok = about_components[i].available();
		ty = row_y + (comp_row_h - body_h) / 2;
		dot_y = row_y + (comp_row_h - STATUS_DOT) / 2;

		ui_status_dot(col_x + SP_1, dot_y, STATUS_DOT,
		              ok ? theme.green : theme.text_faint);
		about_draw_fit(TEXT_BODY, col_x + SP_1 + STATUS_DOT + SP_2, ty,
		               col_w - 90, about_components[i].name, theme.text);
		text_draw_right(TEXT_CAPTION, col_x + col_w - SP_1,
		                row_y + (comp_row_h - cap_h) / 2,
		                ok ? "OK" : "no disponible",
		                ok ? theme.text_faint : theme.amber);
	}
	y += comp_rows * comp_row_h + SP_4;

	/* ---- pie de pagina ---- */
	text_draw_center(TEXT_CAPTION, inner_x + inner_w / 2, y,
	                 "Proyecto final de Sistemas Operativos - UMB 2026",
	                 theme.text_dim);
	text_draw_center(TEXT_CAPTION, inner_x + inner_w / 2,
	                 y + cap_h + SP_1,
	                 "SO original - sin assets de terceros", theme.text_faint);
}

/* ------------------------------------------------------------------ */
/* ciclo de vida                                                       */
/* ------------------------------------------------------------------ */
static void about_step(void *arg) {
	struct window *w = (struct window *)arg;
	about_state_t *st = (about_state_t *)window_data(w);
	uint32_t now, mask;

	if (!st) return;
	now = timer_ticks();
	if ((int32_t)(now - st->last_check) < ABOUT_CHECK_TICKS) return;
	st->last_check = now;
	mask = about_availability();
	if (mask != st->availability) {
		st->availability = mask;
		window_invalidate(w);
	}
}

static void about_open(struct window *w) {
	about_state_t *st;
	static int audio_started = 0;

	/* audio_init es idempotente; la app lo asegura una vez para mostrar el
	 * backend real aunque el juego aun no se haya abierto */
	if (!audio_started) {
		audio_init();
		audio_started = 1;
	}

	st = (about_state_t *)kzalloc(sizeof(about_state_t));
	if (!st) return;
	st->task_id = -1;
	st->last_check = timer_ticks();
	st->availability = about_availability();
	window_set_data(w, st);
	st->task_id = task_create("about", about_step, w);
	window_invalidate(w);
}

static void about_close(struct window *w) {
	about_state_t *st = (about_state_t *)window_data(w);
	if (!st) return;
	if (st->task_id >= 0) task_kill(st->task_id);
	window_set_data(w, 0);
	kfree(st);
}

static void about_event(struct window *w, const event_t *ev) {
	(void)w;
	(void)ev;
}

static app_t about_app = {
	.id = "about",
	.name = "Acerca de",
	.icon = "about",
	.default_width = 680,
	.default_height = 500,
	.init = 0,
	.open = about_open,
	.close = about_close,
	.draw = about_draw,
	.event = about_event,
	.update = 0,
};

app_t *app_about(void) {
	return &about_app;
}
