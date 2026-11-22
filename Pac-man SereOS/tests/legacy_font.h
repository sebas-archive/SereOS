/* graphics/font.h - fuente bitmap 8x16 propia, ASCII 32..126 */
#ifndef SEREOS_FONT_H
#define SEREOS_FONT_H
#include <stdint.h>

#define FONT_GLYPH_W 8
#define FONT_GLYPH_H 16
#define FONT_FIRST   32
#define FONT_LAST    126
#define FONT_COUNT   (FONT_LAST - FONT_FIRST + 1)

extern const uint8_t font8x16[FONT_COUNT][FONT_GLYPH_H];

void           font_init(void);
const uint8_t *font_glyph(char c);          /* 16 filas, bit 7 = pixel izquierdo */
int            font_char_width(void);
int            font_char_height(void);
int            font_string_width(const char *s);

#endif
