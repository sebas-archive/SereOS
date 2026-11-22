/* graphics/text_internal.h - contrato interno entre text.c y text_data.c
 *
 * NO forma parte de la API publica (esa es graphics/text.h).  Define el
 * formato de los atlases de cobertura alfa 8bpp que genera en tiempo de
 * compilacion tools/gen_ui_fonts.py a partir de Inter (UI) y JetBrains Mono
 * (codigo), ambas con licencia SIL Open Font License 1.1.
 *
 * Cada estilo tiene:
 *   - un atlas: bytes consecutivos de cobertura (0 = transparente,
 *     255 = opaco) empaquetados por glifo como width*height bytes;
 *   - una tabla de 226 glifos: codepoints 32..255 en orden (indice
 *     cp - TEXT_FIRST, con los codepoints 127..159 sin glifo porque son
 *     controles C1), mas dos glifos especiales al final:
 *       TEXT_GLYPH_FALLBACK    -> '?'  (codepoint fuera de Latin-1)
 *       TEXT_GLYPH_REPLACEMENT -> U+FFFD (secuencia UTF-8 invalida)
 *   - metricas de la caja de linea (line_height, ascent, line_gap).
 *
 * El texto se dibuja con una unica llamada gfx_blit_alpha8() por glifo.
 */
#ifndef SEREOS_TEXT_INTERNAL_H
#define SEREOS_TEXT_INTERNAL_H
#include <stdint.h>

#define TEXT_FIRST        32
#define TEXT_LAST         255
#define TEXT_GLYPH_COUNT  (TEXT_LAST - TEXT_FIRST + 1)   /* 224: 32..255 */
#define TEXT_GLYPH_FALLBACK    TEXT_GLYPH_COUNT          /* 224: '?' */
#define TEXT_GLYPH_REPLACEMENT (TEXT_GLYPH_COUNT + 1)    /* 225: U+FFFD */

/* Pequeno juego de signos tipograficos habituales en la interfaz que no
 * estan en Latin-1 (guion largo, comillas, puntos suspensivos, euro, flechas,
 * marca registrada).  Se indexan en text_extra_codepoints[] y amplian el
 * contrato sin cambiar la API publica: el resto de codepoints sigue usando
 * el comodin '?'. */
#define TEXT_EXTRA_COUNT       12
#define TEXT_GLYPH_EXTRA_FIRST (TEXT_GLYPH_COUNT + 2)    /* 226 */
#define TEXT_GLYPHS_TOTAL      (TEXT_GLYPH_COUNT + 2 + TEXT_EXTRA_COUNT)

/* Un glifo recortado a su caja de tinta.  El origen de avance esta en
 * (0, baseline); el bitmap se dibuja en:
 *     x = pen_x + bearing_x
 *     y = baseline - bearing_y
 * donde bearing_y es la distancia (positiva hacia arriba) de la baseline a
 * la primera fila de tinta.  Los glifos con descendente pueden tener
 * bearing_y <= 0.
 */
typedef struct __attribute__((packed)) {
	uint32_t offset;      /* byte inicial dentro del atlas del estilo */
	uint8_t  width;       /* ancho del bitmap recortado (0 = sin tinta) */
	uint8_t  height;      /* alto del bitmap recortado */
	int8_t   bearing_x;   /* desplazamiento horizontal desde el origen */
	int8_t   bearing_y;   /* altura de la tinta sobre la baseline */
	uint8_t  advance;     /* avance horizontal en pixeles */
} text_glyph_t;

typedef struct {
	uint8_t  line_height; /* alto de la caja de linea (ascent + descent) */
	uint8_t  ascent;      /* top de la linea -> baseline */
	uint8_t  line_gap;    /* espaciado extra recomendado entre lineas */
	uint8_t  reserved;
	uint16_t glyph_count; /* TEXT_GLYPHS_TOTAL */
	uint32_t atlas_size;  /* bytes del atlas de cobertura */
	const text_glyph_t *glyphs;
	const uint8_t *atlas;
} text_font_t;

/* Codepoints extendidos (orden estable; indice = TEXT_GLYPH_EXTRA_FIRST + i) */
extern const uint16_t text_extra_codepoints[TEXT_EXTRA_COUNT];

/* Tablas generadas (graphics/text_data.c), una por estilo de text_style_t. */
extern const text_font_t text_font_caption;     /* Inter Regular    10 px */
extern const text_font_t text_font_small;       /* Inter Regular    11 px */
extern const text_font_t text_font_body;        /* Inter Regular    13 px */
extern const text_font_t text_font_label;       /* Inter SemiBold   12 px */
extern const text_font_t text_font_title;       /* Inter SemiBold   16 px */
extern const text_font_t text_font_headline;    /* Inter SemiBold   20 px */
extern const text_font_t text_font_display;     /* Inter SemiBold   30 px */
extern const text_font_t text_font_mono;        /* JetBrains Mono   13 px */
extern const text_font_t text_font_mono_small;  /* JetBrains Mono   11 px */

#endif /* SEREOS_TEXT_INTERNAL_H */
