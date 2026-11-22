/* PAC-MAN SereOS - adaptador nativo: implementa pac_platform.h con el OS
 *
 * Es el UNICO punto que incluye cabeceras de SereOS. Traduce las primitivas
 * del kernel/escritorio (gfx, text, input, timer, audio, fs, serial, kmalloc,
 * window) al contrato compartido. No define simbolos del OS: solo los usa.
 */
#include <stdint.h>
#include <stddef.h>
#include <string.h>

#include "graphics.h"
#include "text.h"
#include "input.h"
#include "timer.h"
#include "serial.h"
#include "kmalloc.h"
#include "fs.h"
#include "window.h"
#include "audio.h"
#include "sb16.h"
#include "sfx_res.h"

#include "pac_platform.h"
#include "platform_sereos.h"

#define PAC_RECORD_PATH "/home/pacman_sereos.hi"

static struct window *g_win;

void pac_sereos_bind_window(struct window *w) { g_win = w; }
struct window *pac_sereos_window(void) { return g_win; }

/* ------------------------------------------------------------------ */
/* teclas                                                              */
/* ------------------------------------------------------------------ */
pac_key_t pac_sereos_map_keycode(int keycode)
{
	switch (keycode) {
	case KEY_ESC: return PAC_KEY_ESC;
	case KEY_ENTER: return PAC_KEY_ENTER;
	case KEY_SPACE: return PAC_KEY_SPACE;
	case KEY_UP: return PAC_KEY_UP;
	case KEY_DOWN: return PAC_KEY_DOWN;
	case KEY_LEFT: return PAC_KEY_LEFT;
	case KEY_RIGHT: return PAC_KEY_RIGHT;
	case KEY_A: return PAC_KEY_A;
	case KEY_B: return PAC_KEY_B;
	case KEY_C: return PAC_KEY_C;
	case KEY_D: return PAC_KEY_D;
	case KEY_E: return PAC_KEY_E;
	case KEY_F: return PAC_KEY_F;
	case KEY_G: return PAC_KEY_G;
	case KEY_H: return PAC_KEY_H;
	case KEY_I: return PAC_KEY_I;
	case KEY_J: return PAC_KEY_J;
	case KEY_K: return PAC_KEY_K;
	case KEY_L: return PAC_KEY_L;
	case KEY_M: return PAC_KEY_M;
	case KEY_N: return PAC_KEY_N;
	case KEY_O: return PAC_KEY_O;
	case KEY_P: return PAC_KEY_P;
	case KEY_Q: return PAC_KEY_Q;
	case KEY_R: return PAC_KEY_R;
	case KEY_S: return PAC_KEY_S;
	case KEY_T: return PAC_KEY_T;
	case KEY_U: return PAC_KEY_U;
	case KEY_V: return PAC_KEY_V;
	case KEY_W: return PAC_KEY_W;
	case KEY_X: return PAC_KEY_X;
	case KEY_Y: return PAC_KEY_Y;
	case KEY_Z: return PAC_KEY_Z;
	case KEY_0: return PAC_KEY_0;
	case KEY_1: return PAC_KEY_1;
	case KEY_2: return PAC_KEY_2;
	case KEY_3: return PAC_KEY_3;
	case KEY_4: return PAC_KEY_4;
	case KEY_5: return PAC_KEY_5;
	case KEY_6: return PAC_KEY_6;
	case KEY_7: return PAC_KEY_7;
	case KEY_8: return PAC_KEY_8;
	case KEY_9: return PAC_KEY_9;
	case KEY_F11: return PAC_KEY_F11;
	default: return PAC_KEY_NONE;
	}
}

static keycode_t key_from_pac(pac_key_t key)
{
	switch (key) {
	case PAC_KEY_ESC: return KEY_ESC;
	case PAC_KEY_ENTER: return KEY_ENTER;
	case PAC_KEY_SPACE: return KEY_SPACE;
	case PAC_KEY_UP: return KEY_UP;
	case PAC_KEY_DOWN: return KEY_DOWN;
	case PAC_KEY_LEFT: return KEY_LEFT;
	case PAC_KEY_RIGHT: return KEY_RIGHT;
	case PAC_KEY_A: return KEY_A;
	case PAC_KEY_B: return KEY_B;
	case PAC_KEY_C: return KEY_C;
	case PAC_KEY_D: return KEY_D;
	case PAC_KEY_E: return KEY_E;
	case PAC_KEY_F: return KEY_F;
	case PAC_KEY_G: return KEY_G;
	case PAC_KEY_H: return KEY_H;
	case PAC_KEY_I: return KEY_I;
	case PAC_KEY_J: return KEY_J;
	case PAC_KEY_K: return KEY_K;
	case PAC_KEY_L: return KEY_L;
	case PAC_KEY_M: return KEY_M;
	case PAC_KEY_N: return KEY_N;
	case PAC_KEY_O: return KEY_O;
	case PAC_KEY_P: return KEY_P;
	case PAC_KEY_Q: return KEY_Q;
	case PAC_KEY_R: return KEY_R;
	case PAC_KEY_S: return KEY_S;
	case PAC_KEY_T: return KEY_T;
	case PAC_KEY_U: return KEY_U;
	case PAC_KEY_V: return KEY_V;
	case PAC_KEY_W: return KEY_W;
	case PAC_KEY_X: return KEY_X;
	case PAC_KEY_Y: return KEY_Y;
	case PAC_KEY_Z: return KEY_Z;
	case PAC_KEY_0: return KEY_0;
	case PAC_KEY_1: return KEY_1;
	case PAC_KEY_2: return KEY_2;
	case PAC_KEY_3: return KEY_3;
	case PAC_KEY_4: return KEY_4;
	case PAC_KEY_5: return KEY_5;
	case PAC_KEY_6: return KEY_6;
	case PAC_KEY_7: return KEY_7;
	case PAC_KEY_8: return KEY_8;
	case PAC_KEY_9: return KEY_9;
	case PAC_KEY_F11: return KEY_F11;
	default: return KEY_NONE;
	}
}

int pac_input_key_down(pac_key_t key)
{
	keycode_t k = key_from_pac(key);
	if (k == KEY_NONE)
		return 0;
	return input_key_down(k) ? 1 : 0;
}

int pac_mouse_x(void) { return input_mouse_x(); }
int pac_mouse_y(void) { return input_mouse_y(); }

/* ------------------------------------------------------------------ */
/* ciclo de vida / ventana                                             */
/* ------------------------------------------------------------------ */
int pac_platform_init(void)
{
	/* el escritorio ya inicializa gfx/text/input/timer/audio */
	return 1;
}

void pac_platform_shutdown(void) { }

int pac_platform_width(void)
{
	return g_win ? window_content_w(g_win) : 878;
}

int pac_platform_height(void)
{
	return g_win ? window_content_h(g_win) : 523;
}

void pac_platform_content_rect(pac_rect_t *out)
{
	if (!out)
		return;
	if (!g_win) {
		out->x = 0;
		out->y = 0;
		out->w = 878;
		out->h = 523;
		return;
	}
	out->x = window_content_x(g_win);
	out->y = window_content_y(g_win);
	out->w = window_content_w(g_win);
	out->h = window_content_h(g_win);
}

int pac_platform_focused(void)
{
	return g_win && window_active(g_win) ? 1 : 0;
}

int pac_platform_minimized(void)
{
	return g_win && window_minimized(g_win) ? 1 : 0;
}

void pac_platform_request_close(void)
{
	if (g_win)
		window_close(g_win);
}

int pac_platform_set_fullscreen(int enabled)
{
	int now;
	if (!g_win)
		return 0;
	now = window_maximized(g_win) ? 1 : 0;
	if (now != (enabled ? 1 : 0))
		window_toggle_maximize(g_win);
	return 1;
}

int pac_platform_get_fullscreen(void)
{
	return (g_win && window_maximized(g_win)) ? 1 : 0;
}

void pac_platform_log(const char *marker)
{
	if (!marker)
		return;
	serial_write(marker);
	serial_write("\n");
}

uint32_t pac_time_ms(void) { return timer_uptime_ms(); }

void *pac_alloc(size_t size) { return kmalloc((uint32_t)size); }
void pac_free(void *ptr) { kfree(ptr); }

/* ------------------------------------------------------------------ */
/* persistencia                                                        */
/* ------------------------------------------------------------------ */
static const char *storage_path(const char *key)
{
	if (!key || strcmp(key, "record") == 0)
		return PAC_RECORD_PATH;
	if (strcmp(key, "sound") == 0)
		return "/home/pacman_sound.cfg";
	if (strcmp(key, "fullscreen") == 0)
		return "/home/pacman_fullscreen.cfg";
	if (strcmp(key, "classic") == 0)
		return "/home/pacman_classic.cfg";
	return PAC_RECORD_PATH;
}

int pac_storage_read(const char *key, void *buf, int max_len)
{
	int n;
	if (max_len <= 0)
		return -1;
	n = (int)fs_readfile(storage_path(key), (char *)buf, (uint32_t)max_len);
	return n > 0 ? n : -1;
}

int pac_storage_write(const char *key, const void *buf, int len)
{
	if (len <= 0)
		return 0;
	return (int)fs_writefile(storage_path(key), (const char *)buf, (uint32_t)len);
}

/* ------------------------------------------------------------------ */
/* render                                                              */
/* ------------------------------------------------------------------ */
void pac_set_clip(int x, int y, int w, int h) { gfx_set_clip(x, y, w, h); }
void pac_reset_clip(void) { gfx_reset_clip(); }
void pac_get_clip(pac_rect_t *out)
{
	int x, y, w, h;
	gfx_get_clip(&x, &y, &w, &h);
	if (out) {
		out->x = x;
		out->y = y;
		out->w = w;
		out->h = h;
	}
}

void pac_fill_rect(int x, int y, int w, int h, uint32_t color)
{
	gfx_fill_rect(x, y, w, h, color);
}

void pac_fill_rect_alpha(int x, int y, int w, int h, uint32_t color, uint8_t alpha)
{
	gfx_fill_rect_alpha(x, y, w, h, color, alpha);
}

void pac_draw_rect(int x, int y, int w, int h, uint32_t color)
{
	gfx_draw_rect(x, y, w, h, color);
}

void pac_fill_round_rect(int x, int y, int w, int h, int radius, uint32_t color)
{
	gfx_fill_round_rect(x, y, w, h, radius, color);
}

void pac_fill_round_rect_alpha(int x, int y, int w, int h, int radius,
                               uint32_t color, uint8_t alpha)
{
	gfx_fill_round_rect_alpha(x, y, w, h, radius, color, alpha);
}

void pac_draw_round_rect(int x, int y, int w, int h, int radius, uint32_t color)
{
	gfx_draw_round_rect(x, y, w, h, radius, color);
}

void pac_blit_rgb(int x, int y, int w, int h, const uint32_t *pixels)
{
	gfx_blit_rgb(x, y, w, h, pixels);
}

void pac_blit_alpha8(int x, int y, int w, int h, const uint8_t *mask,
                     uint32_t color)
{
	gfx_blit_alpha8(x, y, w, h, mask, color);
}

void pac_sprite(int x, int y, const uint16_t *pixels, int w, int h)
{
	gfx_draw_sprite(x, y, pixels, w, h);
}

void pac_sprite_alpha(int x, int y, const uint16_t *pixels, int w, int h,
                      uint8_t alpha)
{
	gfx_draw_sprite_alpha(x, y, pixels, w, h, alpha);
}

void pac_mark_dirty(int x, int y, int w, int h)
{
	(void)x; (void)y; (void)w; (void)h;
	if (g_win)
		window_invalidate(g_win);
}

void pac_present(void) { }

/* ------------------------------------------------------------------ */
/* texto                                                               */
/* ------------------------------------------------------------------ */
static text_style_t os_style(pac_text_style_t style)
{
	switch (style) {
	case PAC_TEXT_CAPTION: return TEXT_CAPTION;
	case PAC_TEXT_SMALL: return TEXT_SMALL;
	case PAC_TEXT_BODY: return TEXT_BODY;
	case PAC_TEXT_LABEL: return TEXT_LABEL;
	case PAC_TEXT_TITLE: return TEXT_TITLE;
	case PAC_TEXT_HEADLINE: return TEXT_HEADLINE;
	case PAC_TEXT_DISPLAY: return TEXT_DISPLAY;
	case PAC_TEXT_MONO: return TEXT_MONO;
	case PAC_TEXT_MONO_SMALL: return TEXT_MONO_SMALL;
	default: return TEXT_BODY;
	}
}

int pac_text_width(pac_text_style_t style, const char *text)
{
	return text_width(os_style(style), text);
}

int pac_text_height(pac_text_style_t style)
{
	return text_height(os_style(style));
}

int pac_text_ascent(pac_text_style_t style)
{
	return text_ascent(os_style(style));
}

int pac_text_line_gap(pac_text_style_t style)
{
	return text_line_gap(os_style(style));
}

void pac_text_draw(pac_text_style_t style, int x, int y,
                   const char *text, uint32_t color)
{
	text_draw(os_style(style), x, y, text, color);
}

void pac_text_draw_alpha(pac_text_style_t style, int x, int y,
                         const char *text, uint32_t color, uint8_t alpha)
{
	text_draw_alpha(os_style(style), x, y, text, color, alpha);
}

void pac_text_draw_center(pac_text_style_t style, int cx, int y,
                          const char *text, uint32_t color)
{
	text_draw_center(os_style(style), cx, y, text, color);
}

void pac_text_draw_right(pac_text_style_t style, int right_x, int y,
                         const char *text, uint32_t color)
{
	text_draw_right(os_style(style), right_x, y, text, color);
}

/* ------------------------------------------------------------------ */
/* audio: PCM real por SB16 para los WAV de Res, sintesis como fallback  */
/* ------------------------------------------------------------------ */
/* DMA 8237 de 8 bits: el bloque debe estar por debajo de 16 MiB y no puede
 * cruzar una pagina de 64 KiB (ver drivers/sb16.c: dma_program()). Los chunks
 * de los assets viven en .rodata SIN alineacion (p.ej. game_start_1 en
 * 0x32ff40 + 13908 cruzaba los 64 KiB y sb16_play() lo rechazaba, cortando
 * START a 2.97 s). Para no duplicar memoria ni depender de una segunda bounce
 * buffer en .bss (que quedo en 0x15b0000, por encima de los 16 MiB), se usa la
 * bounce buffer del kernel (audio_dma_bounce()): 32 KiB alineados a 64 KiB y
 * en direccion baja. Se copia cada chunk antes de programar el DMA. */
static int g_pcm_slot = -1;
static int g_pcm_chunk;
static int g_pcm_loop;
static int g_pcm_active;

static int pcm_play_chunk(void)
{
	const uint8_t *data;
	uint32_t len;

	if (g_pcm_slot < 0 || g_pcm_slot >= PACASSET_RES_SFX_SLOTS)
		return 0;
	if (g_pcm_chunk < 0 ||
	    g_pcm_chunk >= (int)PACASSET_RES_SFX_MAX_CHUNKS)
		return 0;
	data = pacasset_sfx_res_chunks[g_pcm_slot][g_pcm_chunk];
	len = pacasset_sfx_res_chunk_len[g_pcm_slot][g_pcm_chunk];
	if (!data || len == 0u || len > SB16_MAX_BUFFER)
		return 0;
	/* copia al bounce buffer DMA-safe del kernel antes de programar el
	 * 8237: el bloque resultante siempre cumple <16 MiB y no cruza 64 KiB */
	{
		uint32_t capacity = 0;
		uint8_t *dmabuf = audio_dma_bounce(&capacity);
		if (!dmabuf || len > capacity)
			return 0;
		memcpy(dmabuf, data, (size_t)len);
		return sb16_play(dmabuf, len, PACASSET_RES_SFX_RATE);
	}
}

static int pcm_start(int slot, int loop)
{
	if (!sb16_present())
		return 0;
	if (slot < 0 || slot >= PACASSET_RES_SFX_SLOTS)
		return 0;
	if (!pacasset_sfx_res_available(slot))
		return 0;
	/* una sola voz: corta el loop/efecto anterior antes de empezar */
	audio_stop();
	audio_stop_loop();
	sb16_stop();
	g_pcm_slot = slot;
	g_pcm_chunk = 0;
	g_pcm_loop = loop;
	g_pcm_active = 1;
	if (!pcm_play_chunk()) {
		g_pcm_active = 0;
		return 0;
	}
	return 1;
}

static void pcm_stop(void)
{
	sb16_stop();
	g_pcm_active = 0;
	g_pcm_slot = -1;
	g_pcm_loop = 0;
	g_pcm_chunk = 0;
}

void pac_audio_init(void)
{
	/* audio_init() ya sondea y arranca el SB16 (idempotente) */
	audio_init();
}

int pac_audio_available(void)
{
	return (audio_available() || sb16_present()) ? 1 : 0;
}

static audio_sfx_t os_sfx(int sfx)
{
	/* El enum del componente puede tener slots que el OS aun no define
	 * (p.ej. GHOST_RESPAWN); se aproximan al efecto nativo mas cercano. */
	if (sfx == PAC_SFX_GHOST_RESPAWN)
		return AUDIO_EAT_GHOST;
	if (sfx <= PAC_SFX_NONE || sfx >= (int)AUDIO_COUNT)
		return AUDIO_NONE;
	return (audio_sfx_t)sfx;
}

void pac_audio_play(int sfx)
{
	audio_sfx_t os = os_sfx(sfx);

	if (sb16_present() && sfx >= 0 && sfx < PACASSET_RES_SFX_SLOTS &&
	    pacasset_sfx_res_available(sfx)) {
		/* pac_audio_play() es SIEMPRE one-shot: no se honra el flag
		 * loop del asset (GHOST_RESPAWN solo se repite via
		 * pac_audio_loop()). Asi no quedan bucles eternos si el core
		 * pide un "play" de un slot marcado loopable. */
		if (pcm_start(sfx, 0))
			return;
	}
	if (os == AUDIO_NONE)
		return;
	/* fallback sintetizado del kernel: corta el motor PCM para que no
	 * siga rearmando el loop anterior por debajo de la sintesis */
	pcm_stop();
	audio_stop_loop();
	audio_play(os);
}

void pac_audio_loop(int sfx)
{
	audio_sfx_t os = os_sfx(sfx);

	if (sb16_present() && sfx >= 0 && sfx < PACASSET_RES_SFX_SLOTS &&
	    pacasset_sfx_res_available(sfx)) {
		if (pcm_start(sfx, 1))
			return;
	}
	/* sin asset Res: primero se apaga el motor PCM (p.ej. veniamos de
	 * SIREN_HUNT PCM) y el loop del kernel, y luego arranca el loop
	 * sintetizado; asi no suenan dos sirenas solapadas. */
	pcm_stop();
	audio_stop_loop();
	if (os == AUDIO_NONE)
		return;
	audio_loop(os);
}

void pac_audio_stop_loop(void)
{
	pcm_stop();
	audio_stop_loop();
}

void pac_audio_stop(void)
{
	pcm_stop();
	audio_stop();
}

void pac_audio_update(void)
{
	audio_update();
	if (!g_pcm_active)
		return;
	if (sb16_busy())
		return;
	g_pcm_chunk++;
	if (g_pcm_chunk >= (int)pacasset_sfx_res_chunk_count[g_pcm_slot]) {
		if (g_pcm_loop)
			g_pcm_chunk = 0;
		else {
			g_pcm_active = 0;
			return;
		}
	}
	if (!pcm_play_chunk())
		g_pcm_active = 0;
}
