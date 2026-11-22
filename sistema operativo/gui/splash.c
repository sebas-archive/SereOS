/* gui/splash.c - pantalla de arranque minimalista de SereOS.
 *
 * Rediseno v1.1: arranque rapido (~1.0 s total), fondo uniforme del tema,
 * logotipo OFICIAL de SereOS (assets/logo/official_logo.png) + wordmark,
 * version discreta, una linea de progreso fina y tres mensajes REALES del
 * klog revelados en orden. Termina
 * con un fundido de 150 ms por alfa hacia el color de fondo y deja que el
 * escritorio pinte su primer frame.
 *
 * Sin bloqueo de interrupciones: usa timer_ticks()/timer_sleep_ms() y
 * gfx_present() por frame. Cualquier tecla o clic salta la animacion
 * (tambien splash_skip()). Serial marker "SPLASH_DONE" siempre.
 */
#include <stdint.h>
#include "string.h"

#include "splash.h"
#include "gui.h"
#include "graphics.h"
#include "icons.h"
#include "logo.h"
#include "text.h"
#include "log.h"
#include "timer.h"
#include "input.h"
#include "serial.h"
#include "sereos_version.h"

#define SPLASH_INTRO_MS   850u
#define SPLASH_FADE_MS    150u
#define SPLASH_FADE_STEPS   6
#define SPLASH_FRAME_MS    10u
#define SPLASH_LOG_LINES    3

/* flag que fija splash_skip(); splash_run() la comprueba en cada frame */
static volatile int skip_flag;

void splash_skip(void) { skip_flag = 1; }

/* ------------------------------------------------------------------ */
/* tokens con respaldo mientras se migra el tema                       */
/* ------------------------------------------------------------------ */
static uint32_t splash_bg(void) {
	return theme.bg ? theme.bg : 0x0B0D12u;
}
static uint32_t splash_track(void) {
	return theme.surface_2 ? theme.surface_2 : 0x1A1E26u;
}
static uint32_t splash_faint(void) {
	return theme.text_faint ? theme.text_faint : 0x6E7788u;
}

/* ------------------------------------------------------------------ */
/* composicion                                                         */
/* ------------------------------------------------------------------ */
typedef struct {
	int w, h, cx;
	int logo_cy, logo_size;
	int word_y;
	int version_y;
	int bar_x, bar_y, bar_w, bar_h;
	int log_y, log_line_h;
} splash_ui_t;

static void splash_layout(splash_ui_t *u) {
	int logo, block_h, top;
	int word_h, cap_h, small_h;
	int logo_ext;              /* alto total del logo, anillo incluido */

	u->w = gfx_width();
	u->h = gfx_height();
	u->cx = u->w / 2;

	logo = (u->h < 600) ? SPLASH_LOGO_SMALL : SPLASH_LOGO;
	u->logo_size = logo;
	word_h = text_height(TEXT_DISPLAY);
	cap_h = text_height(TEXT_CAPTION);
	small_h = text_height(TEXT_SMALL);
	if (small_h < 12) small_h = 12;
	u->log_line_h = small_h + 2;

	/* el anillo exterior (lo dibuja logo_draw_splash con alfa 90) sobresale
	 * del contenedor; logo_extent() devuelve el lado total ocupado por lo
	 * que el bloque sigue centrado sin recortar el anillo */
	logo_ext = logo_extent(logo, 90);
	if (logo_ext < logo) logo_ext = logo;

	/* bloque: logo + wordmark + version + linea + mensajes */
	block_h = logo_ext + SP_4 + word_h + 2 + cap_h + SP_5 + 2 + SP_5 +
	          SPLASH_LOG_LINES * u->log_line_h;
	top = (u->h - block_h) / 2 - u->h / 24;   /* un poco por encima del centro */
	if (top < SP_4) top = SP_4;

	u->logo_cy = top + logo_ext / 2;
	u->word_y = top + logo_ext + SP_4;
	u->version_y = u->word_y + word_h + 2;
	u->bar_y = u->version_y + cap_h + SP_5;
	u->bar_h = 2;
	u->bar_w = 240;
	if (u->bar_w > u->w - SP_8 * 2) u->bar_w = u->w - SP_8 * 2;
	u->bar_x = u->cx - u->bar_w / 2;
	u->log_y = u->bar_y + SP_5;
}

static void splash_static(const splash_ui_t *u) {
	uint32_t bg = splash_bg();

	gfx_fill_rect(0, 0, u->w, u->h, bg);

	/* logotipo oficial en circulo, centrado; el anillo exterior ya lo
	 * dibuja el componente (discreto, 1 px) */
	logo_draw_splash(u->cx, u->logo_cy, u->logo_size);
	text_draw_center(TEXT_DISPLAY, u->cx, u->word_y, SEREOS_NAME, theme.text);
	text_draw_center(TEXT_CAPTION, u->cx, u->version_y, SEREOS_VERSION,
	                 splash_faint());

	/* pista de la linea de progreso (el relleno se dibuja por frame) */
	gfx_fill_round_rect(u->bar_x, u->bar_y, u->bar_w, u->bar_h, 1,
	                    splash_track());
}

static void splash_progress(const splash_ui_t *u, int progress) {
	int fill = (u->bar_w * progress) / 256;
	uint32_t bg = splash_bg();

	/* zona dinamica: pista + relleno (limpia por si el relleno se acorta) */
	gfx_fill_rect(u->bar_x - 1, u->bar_y - 1, u->bar_w + 2, u->bar_h + 2, bg);
	gfx_fill_round_rect(u->bar_x, u->bar_y, u->bar_w, u->bar_h, 1,
	                    splash_track());
	if (fill > 1) {
		if (fill > u->bar_w) fill = u->bar_w;
		gfx_fill_round_rect(u->bar_x, u->bar_y, fill, u->bar_h, 1,
		                    theme.accent);
	}
}

static void splash_messages(const splash_ui_t *u, int progress, int total) {
	int region_h = SPLASH_LOG_LINES * u->log_line_h + 4;
	int max_lines, revealed, first, i;

	/* limpiar la zona de mensajes (ancho completo: textos centrados) */
	gfx_fill_rect(0, u->log_y - 2, u->w, region_h, splash_bg());
	if (total <= 0)
		return;

	max_lines = (total < SPLASH_LOG_LINES) ? total : SPLASH_LOG_LINES;
	revealed = 0;
	for (i = 0; i < SPLASH_LOG_LINES; i++) {
		if (progress >= 56 + i * 76)
			revealed = i + 1;
	}
	if (revealed > max_lines)
		revealed = max_lines;
	first = total - revealed;

	for (i = 0; i < revealed; i++) {
		const char *line = klog_line(first + i);
		if (!line)
			continue;
		text_draw_center(TEXT_SMALL, u->cx, u->log_y + i * u->log_line_h,
		                 line, splash_faint());
	}
}

/* ------------------------------------------------------------------ */
/* entrada / salto                                                     */
/* ------------------------------------------------------------------ */
static int splash_poll_skip(void) {
	event_t ev;
	int skip = skip_flag ? 1 : 0;
	while (input_poll(&ev)) {
		if (ev.type == EVENT_KEY_DOWN || ev.type == EVENT_MOUSE_DOWN)
			skip = 1;
	}
	return skip;
}

/* ------------------------------------------------------------------ */
/* API publica                                                         */
/* ------------------------------------------------------------------ */
void splash_run(void) {
	splash_ui_t u;
	uint32_t start_tick, elapsed, tick_ms, frames = 0;
	int total, progress = 0, skipped = 0;
	int ox, oy, ow, oh;

	skip_flag = 0;
	gfx_get_clip(&ox, &oy, &ow, &oh);

	if (!gfx_ready()) {
		serial_write("SPLASH_DONE\n");
		return;
	}

	splash_layout(&u);
	if (u.w < 200 || u.h < 160) {
		serial_write("SPLASH_DONE\n");
		return;
	}

	total = klog_count();
	if (total < 0) total = 0;

	tick_ms = (timer_hz() > 0) ? (1000u / timer_hz()) : 10u;
	if (tick_ms == 0) tick_ms = 10u;

	gfx_reset_clip();

	/* fotograma estatico (fondo, marca, wordmark, version y pista) */
	splash_static(&u);
	gfx_present();

	start_tick = timer_ticks();
	for (;;) {
		if (splash_poll_skip()) {
			skipped = 1;
			break;
		}
		elapsed = (timer_ticks() - start_tick) * tick_ms;
		progress = (int)((elapsed * 256u) / SPLASH_INTRO_MS);
		if (progress > 256) progress = 256;

		splash_progress(&u, progress);
		splash_messages(&u, progress, total);
		gfx_present();

		if (elapsed >= SPLASH_INTRO_MS)
			break;
		if (++frames > 250u)
			break;
		timer_sleep_ms(SPLASH_FRAME_MS);
	}

	if (!skipped) {
		int step;
		/* estado final honesto: linea completa y los 3 mensajes reales */
		splash_progress(&u, 256);
		splash_messages(&u, 256, total);
		gfx_present();

		/* transicion de 150 ms por alfa hacia el fondo del escritorio */
		for (step = 1; step <= SPLASH_FADE_STEPS; step++) {
			int alpha = (255 * step) / SPLASH_FADE_STEPS;
			gfx_fill_rect_alpha(0, 0, u.w, u.h, splash_bg(),
			                    (uint8_t)alpha);
			gfx_present();
			timer_sleep_ms(SPLASH_FADE_MS / SPLASH_FADE_STEPS);
		}
	}

	serial_write("SPLASH_DONE\n");
	gfx_set_clip(ox, oy, ow, oh);
}
