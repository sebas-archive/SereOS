/* assets/font_arcade.h - tipografia arcade (Press Start K) de PAC-MAN SereOS
 *
 * Atlas de cobertura alfa 8bpp generado en tiempo de build desde
 * prstartk.ttf (Press Start K, (c) 2001-2002 codeman38; recurso
 * user-supplied, ver assets/fonts/LICENSE_ARCADE.md).
 *
 * Formato acordado con game-dev:
 *   - celda 8x16 ASCII+Latin-1 (codepoints 32..255, 224 celdas)
 *   - glifo de 8x8 pixeles alineado arriba; baseline en la fila 8
 *   - avance fijo 8 px, line_height 16 px
 *   - `pac_arcade_font_present[cp-32]` indica si el glifo es real o '?'
 *     (los ausentes se rellenan con '?'; lista en
 *      pac_arcade_font_missing_cps / _count)
 * Uso (compositing por glyph):
 *   const uint8_t *cov = pac_arcade_font_cov[cp - PAC_ARCADEFONT_FIRST];
 *   para (fila 0..15) para (col 0..7): alfa = cov[fila*8+col];
 *   dibujar pixel (x+col, y+fila) con color y alfa (alpha blending).
 * Fallback de texto acentuado no cubierto: tipografia Inter del escritorio.
 */
#ifndef PACMAN_FONT_ARCADE_H
#define PACMAN_FONT_ARCADE_H
#include <stdint.h>

#define PAC_ARCADEFONT_W 8
#define PAC_ARCADEFONT_H 16
#define PAC_ARCADEFONT_FIRST 32
#define PAC_ARCADEFONT_LAST  255
#define PAC_ARCADEFONT_COUNT (PAC_ARCADEFONT_LAST - PAC_ARCADEFONT_FIRST + 1)
#define PAC_ARCADEFONT_BYTES_PER_GLYPH (PAC_ARCADEFONT_W * PAC_ARCADEFONT_H)

extern const uint8_t pac_arcade_font_cov[PAC_ARCADEFONT_COUNT]
                                        [PAC_ARCADEFONT_H][PAC_ARCADEFONT_W];
extern const uint8_t pac_arcade_font_present[PAC_ARCADEFONT_COUNT];
extern const uint8_t pac_arcade_font_missing_count;
extern const uint16_t pac_arcade_font_missing_cps[];
extern const uint8_t pac_arcade_font_advance;      /* 8 */
extern const uint8_t pac_arcade_font_ascent;       /* 8 (baseline desde el top) */
extern const uint8_t pac_arcade_font_line_height;  /* 16 */

static inline const uint8_t *pac_arcade_font_glyph(uint32_t codepoint)
{
	int index;
	if (codepoint < (uint32_t)PAC_ARCADEFONT_FIRST ||
	    codepoint > (uint32_t)PAC_ARCADEFONT_LAST) {
		codepoint = (uint32_t)'?';
	}
	index = (int)(codepoint - (uint32_t)PAC_ARCADEFONT_FIRST);
	return &pac_arcade_font_cov[index][0][0];
}

static inline int pac_arcade_font_covers(uint32_t codepoint)
{
	if (codepoint < (uint32_t)PAC_ARCADEFONT_FIRST ||
	    codepoint > (uint32_t)PAC_ARCADEFONT_LAST) {
		return 0;
	}
	return (int)pac_arcade_font_present[codepoint - (uint32_t)PAC_ARCADEFONT_FIRST];
}

#endif /* PACMAN_FONT_ARCADE_H */
