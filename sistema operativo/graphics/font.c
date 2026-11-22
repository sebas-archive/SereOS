/* graphics/font.c - acceso a la fuente bitmap 8x16 propia de SereOS
 *
 * La tabla de glifos vive en graphics/font_data.c y la genera
 * tools/gen_font.py (ASCII 32..126).  Aqui solo se resuelve el glifo y se
 * exponen las metricas fijas que usa el motor grafico: cada caracter mide
 * 8x16 pixeles y el avance horizontal es de 8 pixeles (monoespaciada).
 *
 * Convencion de los datos (ver font.h): 16 filas por glifo, en cada fila el
 * bit 7 (0x80) es el pixel mas a la izquierda y el bit 0 el mas a la derecha.
 */
#include <stdint.h>
#include "font.h"

/* Glifo seguro de emergencia: una '?' de 8x16 dibujada a mano.  Solo se usa
 * si font_init() detecta que la tabla compilada esta corrupta. */
static const uint8_t font_fallback_glyph[FONT_GLYPH_H] = {
	0x00, 0x00, 0x3C, 0x42, 0x42, 0x04, 0x08, 0x10,
	0x10, 0x00, 0x10, 0x10, 0x00, 0x00, 0x00, 0x00
};

/* 1 = tabla confiable.  Arranca en 1 porque la tabla es constante y el motor
 * grafico puede dibujar antes de que alguien llame a font_init(); si
 * font_init() encuentra una tabla corrupta lo pone a 0. */
static int font_usable = 1;

void font_init(void)
{
	int i;
	int j;
	int nonempty = 0;
	int question_ink = 0;

	for (i = 0; i < FONT_COUNT; i++) {
		for (j = 0; j < FONT_GLYPH_H; j++) {
			if (font8x16[i][j] != 0) {
				nonempty++;
				break;
			}
		}
	}
	for (j = 0; j < FONT_GLYPH_H; j++) {
		if (font8x16[(int)('?' - FONT_FIRST)][j] != 0) {
			question_ink = 1;
			break;
		}
	}

	/* Solo el espacio (32) puede quedar vacio: exigimos 94 glifos con tinta
	 * y que el comodin '?' sea visible. */
	font_usable = (nonempty >= FONT_COUNT - 1 && question_ink) ? 1 : 0;
}

const uint8_t *font_glyph(char c)
{
	unsigned int index = (unsigned int)(unsigned char)c;

	if (!font_usable) {
		return font_fallback_glyph;
	}
	/* Caracteres fuera del rango imprimible: se dibuja '?' como comodin.
	 * El espacio (32) si existe como glifo vacio (ancho fijo de 8 px). */
	if (index < FONT_FIRST || index > FONT_LAST) {
		return font8x16[(unsigned int)('?' - FONT_FIRST)];
	}
	return font8x16[index - FONT_FIRST];
}

int font_char_width(void)
{
	return FONT_GLYPH_W;
}

int font_char_height(void)
{
	return FONT_GLYPH_H;
}

int font_string_width(const char *s)
{
	int width = 0;
	int i = 0;

	if (s == 0) {
		return 0;
	}
	while (s[i] != '\0' && s[i] != '\n') {
		width += (s[i] == '\t') ? (4 * FONT_GLYPH_W) : FONT_GLYPH_W;
		i++;
	}
	return width;
}
