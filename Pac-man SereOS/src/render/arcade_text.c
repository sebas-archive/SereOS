/* PAC-MAN SereOS - render de la fuente arcade (atlas alpha 8x16)
 *
 * Fuente: assets/font_arcade.c (Press Start K, uso privado). Para cadenas con
 * codepoints no cubiertos se usa Inter como fallback (la UI en espanol usa
 * acentos Latin-1, que el atlas cubre).
 */
#include <stdint.h>
#include "pac_platform.h"
#include "font_arcade.h"
#include "arcade_text.h"

static int utf8_next(const char *s, int *used)
{
	unsigned char c = (unsigned char)s[0];
	if (c < 0x80) { *used = 1; return (int)c; }
	if ((c & 0xE0) == 0xC0 && s[1]) {
		*used = 2;
		return ((int)(c & 0x1F) << 6) | ((unsigned char)s[1] & 0x3F);
	}
	if ((c & 0xF0) == 0xE0 && s[1] && s[2]) {
		*used = 3;
		return ((int)(c & 0x0F) << 12) |
		       (((unsigned char)s[1] & 0x3F) << 6) |
		       ((unsigned char)s[2] & 0x3F);
	}
	*used = 1;
	return '?';
}

int pac_arcade_text_covers(const char *text)
{
	int used, cp;
	if (!text)
		return 1;
	while (*text) {
		cp = utf8_next(text, &used);
		text += used;
		if (!pac_arcade_font_covers((uint32_t)cp))
			return 0;
	}
	return 1;
}

int pac_arcade_text_width(const char *text, int scale)
{
	int n = 0, used;
	if (!text)
		return 0;
	while (*text) {
		(void)utf8_next(text, &used);
		text += used;
		n++;
	}
	if (scale < 1)
		scale = 1;
	return n * PAC_ARCADEFONT_W * scale;
}

static void draw_glyph(int x, int y, uint32_t cp, uint32_t color, int scale)
{
	const uint8_t *cov;
	/* buffer contiguo con stride = W*scale (no una matriz de stride fijo) */
	static uint8_t buf[PAC_ARCADEFONT_H * 4 * PAC_ARCADEFONT_W * 4];
	int i, j, sx, sy;
	int w, h;

	if (scale < 1)
		scale = 1;
	if (scale > 4)
		scale = 4;
	cov = pac_arcade_font_glyph(cp);
	if (scale == 1) {
		pac_blit_alpha8(x, y, PAC_ARCADEFONT_W, PAC_ARCADEFONT_H, cov, color);
		return;
	}
	w = PAC_ARCADEFONT_W * scale;
	h = PAC_ARCADEFONT_H * scale;
	for (j = 0; j < PAC_ARCADEFONT_H; j++) {
		for (i = 0; i < PAC_ARCADEFONT_W; i++) {
			uint8_t a = cov[j * PAC_ARCADEFONT_W + i];
			for (sy = 0; sy < scale; sy++)
				for (sx = 0; sx < scale; sx++)
					buf[(j * scale + sy) * w + i * scale + sx] = a;
		}
	}
	pac_blit_alpha8(x, y, w, h, buf, color);
}

void pac_arcade_text_draw(int x, int y, const char *text, uint32_t color,
                          int scale)
{
	int used, cp;
	if (!text)
		return;
	if (!pac_arcade_text_covers(text)) {
		pac_text_draw(PAC_TEXT_BODY, x, y + 2, text, color);
		return;
	}
	if (scale < 1)
		scale = 1;
	while (*text) {
		cp = utf8_next(text, &used);
		text += used;
		if (cp != ' ')
			draw_glyph(x, y, (uint32_t)cp, color, scale);
		x += PAC_ARCADEFONT_W * scale;
	}
}

void pac_arcade_text_draw_center(int cx, int y, const char *text,
                                 uint32_t color, int scale)
{
	pac_arcade_text_draw(cx - pac_arcade_text_width(text, scale) / 2, y,
	                     text, color, scale);
}

void pac_arcade_text_draw_right(int rx, int y, const char *text,
                                uint32_t color, int scale)
{
	pac_arcade_text_draw(rx - pac_arcade_text_width(text, scale), y,
	                     text, color, scale);
}
