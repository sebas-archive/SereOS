/* graphics/text.h - motor tipografico de SereOS
 *
 * SereOS usa dos familias rasterizadas durante la compilacion (sin
 * dependencias en tiempo de ejecucion):
 *   - UI:     Inter (SIL Open Font License) con metricas proporcionales.
 *   - Codigo: JetBrains Mono (SIL Open Font License) para terminal/datos.
 *
 * Los atlases de cobertura alfa (8 bits) se generan con
 * tools/gen_ui_fonts.py y se compilan en graphics/text_data.c.
 * Soporta ASCII y Latin-1 (acentos y enie) via UTF-8.
 *
 * Coordenadas: y es la parte superior de la linea (line box). Use
 * text_ascent() para alinear una linea con otra.
 */
#ifndef SEREOS_TEXT_H
#define SEREOS_TEXT_H
#include <stdint.h>

typedef enum {
	TEXT_CAPTION = 0,   /* UI  10 px regular  - metadatos, ayudas */
	TEXT_SMALL,         /* UI  11 px regular  - texto secundario */
	TEXT_BODY,          /* UI  13 px regular  - texto normal */
	TEXT_LABEL,         /* UI  12 px semibold - etiquetas y titulos de ventana */
	TEXT_TITLE,         /* UI  16 px semibold - titulos de seccion */
	TEXT_HEADLINE,      /* UI  20 px semibold - cabeceras */
	TEXT_DISPLAY,       /* UI  30 px semibold - pantallas de inicio/error */
	TEXT_MONO,          /* mono 13 px regular - terminal, codigo, valores */
	TEXT_MONO_SMALL,    /* mono 11 px regular - detalles tecnicos */
	TEXT_STYLE_COUNT
} text_style_t;

void text_init(void);

/* metricas (todas en pixeles) */
int text_width(text_style_t style, const char *text);
int text_height(text_style_t style);     /* alto de la caja de linea */
int text_ascent(text_style_t style);     /* distancia de la parte superior a la base */
int text_line_gap(text_style_t style);   /* interlineado adicional recomendado */

/* dibujo. y = parte superior de la caja de linea */
void text_draw(text_style_t style, int x, int y, const char *text, uint32_t color);
void text_draw_alpha(text_style_t style, int x, int y, const char *text,
                     uint32_t color, uint8_t alpha);
void text_draw_center(text_style_t style, int cx, int y, const char *text, uint32_t color);
void text_draw_right(text_style_t style, int right_x, int y, const char *text, uint32_t color);

/* dibujo con recorte opcional (para listas con scroll) */
void text_draw_clipped(text_style_t style, int x, int y, const char *text,
                       uint32_t color, int clip_x, int clip_y, int clip_w, int clip_h);

#endif
