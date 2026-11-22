/* graphics/text.c - motor tipografico de SereOS (Inter + JetBrains Mono)
 *
 * Dibuja texto usando los atlases de cobertura alfa generados en tiempo de
 * compilacion (graphics/text_data.c) y una unica llamada
 * gfx_blit_alpha8() por glifo.  Sin dependencias de runtime: no hay malloc,
 * no hay FPU, no se leen fuentes del sistema.
 *
 * Contrato (ver graphics/text.h):
 *   - y es la parte SUPERIOR de la caja de linea.
 *   - la baseline de la primera linea queda en y + text_ascent(style).
 *   - soporta ASCII + Latin-1 en UTF-8 (1-2 bytes); cualquier codepoint
 *     fuera de Latin-1 dibuja '?' y una secuencia UTF-8 invalida dibuja el
 *     glifo de reemplazo U+FFFD.
 *   - '\n' salta de linea (line_height + line_gap), '\r' se ignora y '\t'
 *     avanza cuatro espacios.
 *
 * Formato de los glifos: bitmap recortado con bearing_x/bearing_y relativo
 * al origen de avance y a la baseline; ver graphics/text_internal.h.
 */
#include <stdint.h>
#include "text.h"
#include "graphics.h"
#include "text_internal.h"

/* Tamano maximo de un glifo (en pixeles) para el buffer temporal de
 * text_draw_alpha().  El glifo mas grande generado (TEXT_DISPLAY) ocupa
 * menos de 800 pixeles; 1600 deja margen suficiente. */
#define TEXT_ALPHA_SCRATCH 1600

/* Codepoint centinela: secuencia UTF-8 invalida -> glifo de reemplazo. */
#define TEXT_CP_INVALID 0xFFFFFFFFu

/* Tabla de estilos.  La inicializacion es estatica: el motor funciona
 * aunque nadie llame a text_init() (gui_init lo hara igualmente). */
static const text_font_t *const g_fonts[TEXT_STYLE_COUNT] = {
	&text_font_caption,
	&text_font_small,
	&text_font_body,
	&text_font_label,
	&text_font_title,
	&text_font_headline,
	&text_font_display,
	&text_font_mono,
	&text_font_mono_small
};

/* 1 = tablas sanas.  text_init() lo recalcula; el valor inicial permite
 * dibujar antes de cualquier inicializacion explicita. */
static int g_text_ok = 1;

/* Buffer temporal para aplicar un alfa global al glifo antes de blitear.
 * El dibujo es cooperativo y de un solo hilo, asi que un buffer estatico
 * es suficiente y evita pila/malloc. */
static uint8_t g_alpha_scratch[TEXT_ALPHA_SCRATCH];

/* ---------------------------------------------------------------------- */
/* inicializacion y metricas                                              */
/* ---------------------------------------------------------------------- */

void text_init(void)
{
	int s;
	int ok = 1;

	for (s = 0; s < TEXT_STYLE_COUNT; s++) {
		const text_font_t *f = g_fonts[s];
		int i;

		if (f == 0 || f->glyphs == 0 || f->atlas == 0) {
			ok = 0;
			continue;
		}
		if (f->glyph_count != TEXT_GLYPHS_TOTAL || f->atlas_size == 0u) {
			ok = 0;
			continue;
		}
		if (f->ascent == 0u || f->line_height <= f->ascent) {
			ok = 0;
			continue;
		}
		if (f->glyphs[TEXT_GLYPH_FALLBACK].width == 0u ||
		    f->glyphs[TEXT_GLYPH_FALLBACK].height == 0u) {
			ok = 0;
			continue;
		}
		if (f->glyphs[0].advance == 0u) {
			ok = 0;                  /* el espacio no puede ser nulo */
			continue;
		}
		/* Cada glifo debe caber dentro de su atlas. */
		for (i = 0; i < TEXT_GLYPHS_TOTAL; i++) {
			const text_glyph_t *g = &f->glyphs[i];
			uint32_t bytes = (uint32_t)g->width *
			                 (uint32_t)g->height;
			if (bytes != 0u &&
			    (g->offset > f->atlas_size ||
			     bytes > f->atlas_size - g->offset)) {
				ok = 0;
				break;
			}
		}
	}

	g_text_ok = ok;
}

static const text_font_t *font_for(text_style_t style)
{
	unsigned int index = (unsigned int)style;

	if (index >= (unsigned int)TEXT_STYLE_COUNT) {
		index = (unsigned int)TEXT_BODY;
	}
	return g_fonts[index];
}

int text_height(text_style_t style)
{
	return (int)font_for(style)->line_height;
}

int text_ascent(text_style_t style)
{
	return (int)font_for(style)->ascent;
}

int text_line_gap(text_style_t style)
{
	return (int)font_for(style)->line_gap;
}

/* ---------------------------------------------------------------------- */
/* UTF-8 (ASCII + Latin-1)                                                */
/* ---------------------------------------------------------------------- */

/*
 * Decodifica el siguiente codepoint y avanza *text.  Acepta secuencias de
 * 1..4 bytes estructuralmente validas; los codepoints resultantes fuera de
 * Latin-1 se dibujan como '?' mas adelante.  Una secuencia mal formada
 * devuelve TEXT_CP_INVALID y consume un solo byte para poder resincronizar.
 */
static uint32_t utf8_next(const char **text)
{
	const uint8_t *s = (const uint8_t *)*text;
	uint8_t b0 = s[0];

	if (b0 < 0x80u) {
		*text += 1;
		return (uint32_t)b0;
	}
	if ((b0 & 0xE0u) == 0xC0u) {
		uint8_t b1 = s[1];
		if ((b1 & 0xC0u) == 0x80u) {
			*text += 2;
			return (((uint32_t)b0 & 0x1Fu) << 6) |
			       ((uint32_t)b1 & 0x3Fu);
		}
		*text += 1;
		return TEXT_CP_INVALID;
	}
	if ((b0 & 0xF0u) == 0xE0u) {
		uint8_t b1 = s[1];
		if (b1 != 0u && (b1 & 0xC0u) == 0x80u) {
			uint8_t b2 = s[2];
			if (b2 != 0u && (b2 & 0xC0u) == 0x80u) {
				*text += 3;
				return (((uint32_t)b0 & 0x0Fu) << 12) |
				       (((uint32_t)b1 & 0x3Fu) << 6) |
				       ((uint32_t)b2 & 0x3Fu);
			}
		}
		*text += 1;
		return TEXT_CP_INVALID;
	}
	if ((b0 & 0xF8u) == 0xF0u) {
		uint8_t b1 = s[1];
		if (b1 != 0u && (b1 & 0xC0u) == 0x80u) {
			uint8_t b2 = s[2];
			if (b2 != 0u && (b2 & 0xC0u) == 0x80u) {
				uint8_t b3 = s[3];
				if (b3 != 0u && (b3 & 0xC0u) == 0x80u) {
					*text += 4;
					return (((uint32_t)b0 & 0x07u) << 18) |
					       (((uint32_t)b1 & 0x3Fu) << 12) |
					       (((uint32_t)b2 & 0x3Fu) << 6) |
					       ((uint32_t)b3 & 0x3Fu);
				}
			}
		}
		*text += 1;
		return TEXT_CP_INVALID;
	}
	*text += 1;
	return TEXT_CP_INVALID;
}

/* Resuelve el glifo de un codepoint.  Los codepoints 127..159 (controles
 * C1) y todo lo que no sea Latin-1 usan el comodin '?'. */
static const text_glyph_t *glyph_for(const text_font_t *font, uint32_t cp)
{
	if (cp == TEXT_CP_INVALID) {
		return &font->glyphs[TEXT_GLYPH_REPLACEMENT];
	}
	if (cp >= (uint32_t)TEXT_FIRST && cp <= (uint32_t)TEXT_LAST) {
		if (cp >= 127u && cp <= 159u) {
			return &font->glyphs[TEXT_GLYPH_FALLBACK];
		}
		return &font->glyphs[(int)(cp - (uint32_t)TEXT_FIRST)];
	}
	{
		/* Signos tipograficos extendidos (guion largo, comillas, euro...). */
		int i;
		for (i = 0; i < TEXT_EXTRA_COUNT; i++) {
			if ((uint32_t)text_extra_codepoints[i] == cp) {
				return &font->glyphs[TEXT_GLYPH_EXTRA_FIRST + i];
			}
		}
	}
	return &font->glyphs[TEXT_GLYPH_FALLBACK];
}

/* ---------------------------------------------------------------------- */
/* dibujo                                                                 */
/* ---------------------------------------------------------------------- */

/* Dibuja un glifo en (gx, gy) = esquina superior izquierda de su bitmap. */
static void draw_glyph(const text_font_t *font, const text_glyph_t *g,
                       int gx, int gy, uint32_t color, uint32_t alpha)
{
	const uint8_t *mask = font->atlas + g->offset;

	if (g->width == 0u || g->height == 0u) {
		return;
	}

	if (alpha >= 255u) {
		gfx_blit_alpha8(gx, gy, (int)g->width, (int)g->height, mask, color);
		return;
	}

	{
		uint32_t pixels = (uint32_t)g->width * (uint32_t)g->height;
		uint32_t i;

		if (pixels <= (uint32_t)TEXT_ALPHA_SCRATCH) {
			/* Escala global del alfa en el buffer temporal y un solo
			 * blit por glifo (camino normal de las animaciones). */
			for (i = 0; i < pixels; i++) {
				uint32_t v = (uint32_t)mask[i] * alpha;
				g_alpha_scratch[i] = (uint8_t)((v + 1u + (v >> 8)) >> 8);
			}
			gfx_blit_alpha8(gx, gy, (int)g->width, (int)g->height,
			                g_alpha_scratch, color);
		} else {
			/* Glifo enorme (no ocurre con los estilos actuales): se
			 * degrada a mezcla pixel a pixel sin desbordar el buffer. */
			int row;
			for (row = 0; row < (int)g->height; row++) {
				int col;
				for (col = 0; col < (int)g->width; col++) {
					uint32_t m = (uint32_t)mask[(uint32_t)row *
					              (uint32_t)g->width + (uint32_t)col];
					if (m != 0u) {
						gfx_blend_pixel(gx + col, gy + row,
						                color,
						                (uint8_t)((m * alpha + 1u +
						                           ((m * alpha) >> 8)) >> 8));
					}
				}
			}
		}
	}
}

/* Recorre una cadena completa dibujando sus glifos. */
static void draw_string(const text_font_t *font, int x, int y,
                        const char *text, uint32_t color, uint32_t alpha)
{
	int clip_x, clip_y, clip_w, clip_h;
	int pen_x = x;
	int base_y = y + (int)font->ascent;
	uint32_t space_advance = (uint32_t)font->glyphs[0].advance;

	/* El clip se consulta una vez por cadena; ademas, cada glifo fuera del
	 * clip evita la llamada al motor grafico. */
	gfx_get_clip(&clip_x, &clip_y, &clip_w, &clip_h);
	if (clip_w <= 0 || clip_h <= 0) {
		return;
	}

	while (*text != '\0') {
		char c = *text;
		const text_glyph_t *g;

		if (c == '\n') {
			pen_x = x;
			base_y += (int)font->line_height + (int)font->line_gap;
			text++;
			continue;
		}
		if (c == '\r') {
			text++;
			continue;
		}
		if (c == '\t') {
			pen_x += 4 * (int)space_advance;
			text++;
			continue;
		}

		g = glyph_for(font, utf8_next(&text));
		if (g->width != 0u && g->height != 0u) {
			int gx = pen_x + (int)g->bearing_x;
			int gy = base_y - (int)g->bearing_y;
			if (gx + (int)g->width > clip_x && gx < clip_x + clip_w &&
			    gy + (int)g->height > clip_y && gy < clip_y + clip_h) {
				draw_glyph(font, g, gx, gy, color, alpha);
			}
		}
		pen_x += (int)g->advance;
	}
}

void text_draw(text_style_t style, int x, int y, const char *text,
               uint32_t color)
{
	if (!g_text_ok || text == 0) {
		return;
	}
	draw_string(font_for(style), x, y, text, color, 255u);
}

void text_draw_alpha(text_style_t style, int x, int y, const char *text,
                     uint32_t color, uint8_t alpha)
{
	if (!g_text_ok || text == 0 || alpha == 0u) {
		return;
	}
	draw_string(font_for(style), x, y, text, color, (uint32_t)alpha);
}

void text_draw_center(text_style_t style, int cx, int y, const char *text,
                      uint32_t color)
{
	int width;

	if (!g_text_ok || text == 0) {
		return;
	}
	width = text_width(style, text);
	draw_string(font_for(style), cx - width / 2, y, text, color, 255u);
}

void text_draw_right(text_style_t style, int right_x, int y, const char *text,
                     uint32_t color)
{
	int width;

	if (!g_text_ok || text == 0) {
		return;
	}
	width = text_width(style, text);
	draw_string(font_for(style), right_x - width, y, text, color, 255u);
}

void text_draw_clipped(text_style_t style, int x, int y, const char *text,
                       uint32_t color, int clip_x, int clip_y,
                       int clip_w, int clip_h)
{
	int old_x, old_y, old_w, old_h;
	int new_x0, new_y0, new_x1, new_y1;

	if (!g_text_ok || text == 0 || clip_w <= 0 || clip_h <= 0) {
		return;
	}
	gfx_get_clip(&old_x, &old_y, &old_w, &old_h);

	new_x0 = (clip_x > old_x) ? clip_x : old_x;
	new_y0 = (clip_y > old_y) ? clip_y : old_y;
	new_x1 = (clip_x + clip_w < old_x + old_w) ? clip_x + clip_w
	                                           : old_x + old_w;
	new_y1 = (clip_y + clip_h < old_y + old_h) ? clip_y + clip_h
	                                           : old_y + old_h;
	if (new_x1 <= new_x0 || new_y1 <= new_y0) {
		return;
	}

	gfx_set_clip(new_x0, new_y0, new_x1 - new_x0, new_y1 - new_y0);
	draw_string(font_for(style), x, y, text, color, 255u);
	gfx_set_clip(old_x, old_y, old_w, old_h);
}

int text_width(text_style_t style, const char *text)
{
	const text_font_t *font = font_for(style);
	int width = 0;
	uint32_t space_advance;

	if (!g_text_ok || text == 0) {
		return 0;
	}
	space_advance = (uint32_t)font->glyphs[0].advance;

	while (*text != '\0') {
		char c = *text;

		if (c == '\n') {
			break;                   /* ancho de la primera linea */
		}
		if (c == '\r') {
			text++;
			continue;
		}
		if (c == '\t') {
			width += 4 * (int)space_advance;
			text++;
			continue;
		}
		width += (int)glyph_for(font, utf8_next(&text))->advance;
	}
	return width;
}
