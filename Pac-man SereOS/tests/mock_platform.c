/* Mock de plataforma para el harness del core de PAC-MAN SereOS.
 *
 * Framebuffer en memoria, reloj simulado, teclado/raton por eventos,
 * audio/storage/log capturados. Sin OS ni SDL: valida la logica y el render
 * compartidos de forma determinista.
 */
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "pac_platform.h"
#include "mock_platform.h"
#include "legacy_font.h"

#define MOCK_W 1024
#define MOCK_H 768

static uint32_t fb[MOCK_W * MOCK_H];
static int win_w = 880, win_h = 560;
static int clip_x, clip_y, clip_w, clip_h;
static int focused = 1, minimized;
static uint32_t ticks;
static int audio_play_id = -1, audio_loop_id = -1, audio_play_calls;
static int audio_counts[PAC_SFX_COUNT];
/* secuencia de llamadas de audio para tests de orden/prioridad */
#define MOCK_AUDIO_LOG_MAX 512
#define MOCK_AUDIO_PLAY      0
#define MOCK_AUDIO_LOOP      1
#define MOCK_AUDIO_STOP_LOOP 2
#define MOCK_AUDIO_STOP      3
static int audio_log_kind[MOCK_AUDIO_LOG_MAX];
static int audio_log_sfx[MOCK_AUDIO_LOG_MAX];
static int audio_log_n;
static char serial_log[4096];
static int serial_len;
static char record_data[64];
static int record_len;

/* ------------------------------------------------------------------ */
/* helpers de test                                                     */
/* ------------------------------------------------------------------ */
void mock_set_size(int w, int h) { win_w = w; win_h = h; }
int mock_content_x(void) { return 1; }
int mock_content_y(void) { return 36; }
int mock_content_w(void) { return win_w - 2; }
int mock_content_h(void) { return win_h - 37; }
void mock_set_focused(int f) { focused = f; }
void mock_set_minimized(int m) { minimized = m; }
void mock_advance_tick(void) { ticks++; }
uint32_t mock_get_ticks(void) { return ticks; }
void mock_serial_clear(void) { serial_len = 0; serial_log[0] = 0; }
const char *mock_serial(void) { return serial_log; }
int mock_audio_last_play(void) { return audio_play_id; }
int mock_audio_last_loop(void) { return audio_loop_id; }
int mock_audio_play_count(void) { return audio_play_calls; }
int mock_audio_count(int sfx) { return (sfx > 0 && sfx < PAC_SFX_COUNT) ? audio_counts[sfx] : 0; }
void mock_audio_clear_counts(void) { memset(audio_counts, 0, sizeof(audio_counts)); audio_log_n = 0; }
const char *mock_record(void) { return record_data; }
int mock_record_len(void) { return record_len; }
void mock_record_seed(const char *txt)
{
	record_len = txt ? (int)strlen(txt) : 0;
	if (record_len > (int)sizeof(record_data) - 1)
		record_len = (int)sizeof(record_data) - 1;
	memcpy(record_data, txt, (size_t)record_len);
	record_data[record_len] = 0;
}

/* ------------------------------------------------------------------ */
/* primitivas de render                                                */
/* ------------------------------------------------------------------ */
static void px(int x, int y, uint32_t c)
{
	if (x < clip_x || y < clip_y || x >= clip_x + clip_w || y >= clip_y + clip_h)
		return;
	if (x < 0 || y < 0 || x >= MOCK_W || y >= MOCK_H)
		return;
	fb[y * MOCK_W + x] = c;
}

static uint32_t blend(uint32_t fg, uint32_t bg, int a)
{
	int r = (((fg >> 16) & 255) * a + ((bg >> 16) & 255) * (255 - a)) / 255;
	int g = (((fg >> 8) & 255) * a + ((bg >> 8) & 255) * (255 - a)) / 255;
	int b = ((fg & 255) * a + (bg & 255) * (255 - a)) / 255;
	return ((uint32_t)r << 16) | ((uint32_t)g << 8) | (uint32_t)b;
}

static void mix(int x, int y, uint32_t c, uint8_t a)
{
	if (x < clip_x || y < clip_y || x >= clip_x + clip_w || y >= clip_y + clip_h)
		return;
	if (x < 0 || y < 0 || x >= MOCK_W || y >= MOCK_H)
		return;
	if (a == 255) fb[y * MOCK_W + x] = c;
	else if (a) fb[y * MOCK_W + x] = blend(c, fb[y * MOCK_W + x], a);
}

void pac_set_clip(int x, int y, int w, int h) { clip_x = x; clip_y = y; clip_w = w; clip_h = h; }
void pac_reset_clip(void) { clip_x = 0; clip_y = 0; clip_w = MOCK_W; clip_h = MOCK_H; }
void pac_get_clip(pac_rect_t *out) { if (out) { out->x=clip_x; out->y=clip_y; out->w=clip_w; out->h=clip_h; } }

void pac_fill_rect(int x, int y, int w, int h, uint32_t c)
{
	int i, j;
	for (j = 0; j < h; j++) for (i = 0; i < w; i++) px(x + i, y + j, c);
}
void pac_fill_rect_alpha(int x, int y, int w, int h, uint32_t c, uint8_t a)
{
	int i, j;
	for (j = 0; j < h; j++) for (i = 0; i < w; i++) mix(x + i, y + j, c, a);
}
void pac_draw_rect(int x, int y, int w, int h, uint32_t c)
{
	pac_fill_rect(x, y, w, 1, c); pac_fill_rect(x, y + h - 1, w, 1, c);
	pac_fill_rect(x, y, 1, h, c); pac_fill_rect(x + w - 1, y, 1, h, c);
}
void pac_fill_round_rect(int x, int y, int w, int h, int r, uint32_t c) { (void)r; pac_fill_rect(x, y, w, h, c); }
void pac_fill_round_rect_alpha(int x, int y, int w, int h, int r, uint32_t c, uint8_t a) { (void)r; pac_fill_rect_alpha(x, y, w, h, c, a); }
void pac_draw_round_rect(int x, int y, int w, int h, int r, uint32_t c) { (void)r; pac_draw_rect(x, y, w, h, c); }

void pac_blit_rgb(int x, int y, int w, int h, const uint32_t *pixels)
{
	int i, j;
	if (!pixels) return;
	for (j = 0; j < h; j++) for (i = 0; i < w; i++) px(x + i, y + j, pixels[j * w + i]);
}

static uint32_t c565(uint16_t v)
{
	uint32_t r = (v >> 11) & 0x1F, g = (v >> 5) & 0x3F, b = v & 0x1F;
	return ((r * 255 / 31) << 16) | ((g * 255 / 63) << 8) | (b * 255 / 31);
}

void pac_blit_alpha8(int x, int y, int w, int h, const uint8_t *mask,
                     uint32_t color)
{
	int i, j;
	if (!mask) return;
	for (j = 0; j < h; j++) for (i = 0; i < w; i++) {
		uint8_t a = mask[j * w + i];
		if (a) mix(x + i, y + j, color, a);
	}
}

void pac_sprite(int x, int y, const uint16_t *pixels, int w, int h)
{
	int i, j;
	if (!pixels) return;
	for (j = 0; j < h; j++) for (i = 0; i < w; i++) {
		uint16_t v = pixels[j * w + i];
		if (v != 0xF81F) px(x + i, y + j, c565(v));
	}
}
void pac_sprite_alpha(int x, int y, const uint16_t *pixels, int w, int h, uint8_t a)
{
	int i, j;
	if (!pixels) return;
	for (j = 0; j < h; j++) for (i = 0; i < w; i++) {
		uint16_t v = pixels[j * w + i];
		if (v != 0xF81F) mix(x + i, y + j, c565(v), a);
	}
}
void pac_mark_dirty(int x, int y, int w, int h) { (void)x; (void)y; (void)w; (void)h; }
void pac_present(void) { }

/* ------------------------------------------------------------------ */
/* texto (metricas aproximadas + fuente bitmap legacy solo para capturas) */
/* ------------------------------------------------------------------ */
typedef struct { int h, ascent, adv; } mock_style_t;
static const mock_style_t mock_styles[PAC_TEXT_STYLE_COUNT] = {
	{10, 8, 6}, {11, 8, 6}, {13, 10, 7}, {12, 9, 7}, {16, 12, 9},
	{20, 15, 11}, {30, 23, 16}, {13, 10, 8}, {11, 8, 7}
};

static int mock_cp(const char *s, int *used)
{
	unsigned char c = (unsigned char)s[0];
	if (c < 0x80) { *used = 1; return c; }
	if ((c & 0xE0) == 0xC0 && s[1]) { *used = 2; return ((c & 0x1F) << 6) | ((unsigned char)s[1] & 0x3F); }
	if ((c & 0xF0) == 0xE0 && s[1] && s[2]) { *used = 3; return ((c&15)<<12) | (((unsigned char)s[1]&63)<<6) | ((unsigned char)s[2]&63); }
	*used = 1; return '?';
}
static int mock_base_cp(int cp)
{
	if (cp >= 32 && cp <= 126) return cp;
	switch (cp) {
	case 0xE1: case 0xE0: return 'a';
	case 0xE9: case 0xE8: return 'e';
	case 0xED: return 'i';
	case 0xF3: return 'o';
	case 0xFA: case 0xFC: return 'u';
	case 0xF1: return 'n';
	case 0xC1: return 'A'; case 0xC9: return 'E'; case 0xCD: return 'I';
	case 0xD3: return 'O'; case 0xDA: return 'U'; case 0xD1: return 'N';
	case 0xBF: return '?'; case 0xA1: return '!';
	default: return '?';
	}
}
int pac_text_width(pac_text_style_t style, const char *text)
{
	int n = 0, used;
	if (!text) return 0;
	if (style >= PAC_TEXT_STYLE_COUNT) style = PAC_TEXT_BODY;
	while (*text) { (void)mock_cp(text, &used); text += used; n++; }
	return n * mock_styles[style].adv;
}
int pac_text_height(pac_text_style_t style) { return mock_styles[style >= PAC_TEXT_STYLE_COUNT ? PAC_TEXT_BODY : style].h; }
int pac_text_ascent(pac_text_style_t style) { return mock_styles[style >= PAC_TEXT_STYLE_COUNT ? PAC_TEXT_BODY : style].ascent; }
int pac_text_line_gap(pac_text_style_t style) { (void)style; return 2; }

static void mock_text(pac_text_style_t style, int x, int y, const char *text, uint32_t color, uint8_t alpha)
{
	int h, adv, n = 0, used, j, i;
	if (!text) return;
	if (style >= PAC_TEXT_STYLE_COUNT) style = PAC_TEXT_BODY;
	h = mock_styles[style].h;
	adv = mock_styles[style].adv;
	while (*text) {
		int gx = x + n * adv;
		int cp = mock_base_cp(mock_cp(text, &used));
		const uint8_t *gl = font_glyph((char)cp);
		text += used;
		n++;
		if (!gl) continue;
		for (j = 0; j < h; j++) {
			int sy = j * 16 / h;
			uint8_t row = gl[sy];
			for (i = 0; i < adv; i++) {
				int sx = i * 8 / adv;
				if (!(row & (0x80u >> sx))) continue;
				mix(gx + i, y + j, color, alpha);
			}
		}
	}
}
void pac_text_draw(pac_text_style_t s, int x, int y, const char *t, uint32_t c) { mock_text(s, x, y, t, c, 255); }
void pac_text_draw_alpha(pac_text_style_t s, int x, int y, const char *t, uint32_t c, uint8_t a) { mock_text(s, x, y, t, c, a); }
void pac_text_draw_center(pac_text_style_t s, int cx, int y, const char *t, uint32_t c) { pac_text_draw(s, cx - pac_text_width(s, t) / 2, y, t, c); }
void pac_text_draw_right(pac_text_style_t s, int rx, int y, const char *t, uint32_t c) { pac_text_draw(s, rx - pac_text_width(s, t), y, t, c); }

/* ------------------------------------------------------------------ */
/* plataforma                                                          */
/* ------------------------------------------------------------------ */
int pac_platform_init(void) { return 1; }
void pac_platform_shutdown(void) { }
int pac_platform_width(void) { return win_w; }
int pac_platform_height(void) { return win_h; }
void pac_platform_content_rect(pac_rect_t *out)
{
	if (!out) return;
	out->x = mock_content_x(); out->y = mock_content_y();
	out->w = mock_content_w(); out->h = mock_content_h();
}
int pac_platform_focused(void) { return focused; }
int pac_platform_minimized(void) { return minimized; }
void pac_platform_request_close(void) { }
int pac_platform_set_fullscreen(int enabled) { (void)enabled; return 1; }
int pac_platform_get_fullscreen(void) { return 0; }
void pac_platform_log(const char *marker)
{
	int n;
	if (!marker) return;
	n = (int)strlen(marker);
	if (serial_len > (int)sizeof(serial_log) - n - 2) return;
	memcpy(serial_log + serial_len, marker, (size_t)n);
	serial_len += n;
	serial_log[serial_len++] = '\n';
	serial_log[serial_len] = 0;
}
uint32_t pac_time_ms(void) { return ticks * 10u; }
void *pac_alloc(size_t size) { return calloc(1, size); }
void pac_free(void *ptr) { free(ptr); }

int pac_storage_read(const char *key, void *buf, int max_len)
{
	int n = 0;
	if (!key || max_len <= 0)
		return -1;
	if (strcmp(key, "record") == 0) {
		if (record_len <= 0) return -1;
		n = record_len < max_len ? record_len : max_len;
		memcpy(buf, record_data, (size_t)n);
		return n;
	}
	/* settings del mock: guardados en la propia clave para tests */
	if (strcmp(key, "sound") == 0) n = snprintf(buf, (size_t)max_len, "%d", 1);
	else if (strcmp(key, "fullscreen") == 0) n = snprintf(buf, (size_t)max_len, "%d", 0);
	else if (strcmp(key, "classic") == 0) n = snprintf(buf, (size_t)max_len, "%d", 1);
	return n > 0 ? n : -1;
}
int pac_storage_write(const char *key, const void *buf, int len)
{
	if (len <= 0) return 0;
	if (!key || strcmp(key, "record") != 0)
		return len;  /* settings del mock: no persistentes */
	if (len > (int)sizeof(record_data) - 1) len = (int)sizeof(record_data) - 1;
	memcpy(record_data, buf, (size_t)len);
	record_len = len;
	record_data[len] = 0;
	return len;
}

void pac_audio_init(void) { }
int pac_audio_available(void) { return 1; }
static void mock_audio_log_add(int kind, int sfx)
{
	if (audio_log_n < MOCK_AUDIO_LOG_MAX) {
		audio_log_kind[audio_log_n] = kind;
		audio_log_sfx[audio_log_n] = sfx;
		audio_log_n++;
	}
}
void pac_audio_play(int sfx) { audio_play_id = sfx; audio_play_calls++;
	mock_audio_log_add(MOCK_AUDIO_PLAY, sfx);
	if (sfx > 0 && sfx < PAC_SFX_COUNT) audio_counts[sfx]++; }
void pac_audio_loop(int sfx) { audio_loop_id = sfx; mock_audio_log_add(MOCK_AUDIO_LOOP, sfx); }
void pac_audio_stop_loop(void) { audio_loop_id = -1; mock_audio_log_add(MOCK_AUDIO_STOP_LOOP, -1); }
void pac_audio_stop(void) { audio_loop_id = -1; mock_audio_log_add(MOCK_AUDIO_STOP, -1); }
void pac_audio_update(void) { }

void mock_audio_log_clear(void) { audio_log_n = 0; }
int mock_audio_log_count(void) { return audio_log_n; }
int mock_audio_log_at(int i, int *kind, int *sfx)
{
	if (i < 0 || i >= audio_log_n)
		return 0;
	if (kind) *kind = audio_log_kind[i];
	if (sfx) *sfx = audio_log_sfx[i];
	return 1;
}

int pac_input_key_down(pac_key_t key) { (void)key; return 0; }
int pac_mouse_x(void) { return 0; }
int pac_mouse_y(void) { return 0; }

/* ------------------------------------------------------------------ */
/* lectura cruda del framebuffer                                       */
/* ------------------------------------------------------------------ */
uint32_t mock_fb_at(int x, int y)
{
	if (x < 0 || y < 0 || x >= MOCK_W || y >= MOCK_H)
		return 0;
	return fb[y * MOCK_W + x];
}

/* ------------------------------------------------------------------ */
/* dump PPM                                                            */
/* ------------------------------------------------------------------ */
void mock_dump_ppm(const char *path, int x, int y, int w, int h)
{
	FILE *f;
	int i, j;
	if (!path || w <= 0 || h <= 0) return;
	f = fopen(path, "wb");
	if (!f) return;
	fprintf(f, "P6\n%d %d\n255\n", w, h);
	for (j = 0; j < h; j++) for (i = 0; i < w; i++) {
		int xx = x + i, yy = y + j;
		uint32_t c = (xx >= 0 && yy >= 0 && xx < MOCK_W && yy < MOCK_H) ? fb[yy * MOCK_W + xx] : 0;
		fputc((int)((c >> 16) & 255), f);
		fputc((int)((c >> 8) & 255), f);
		fputc((int)(c & 255), f);
	}
	fclose(f);
}
