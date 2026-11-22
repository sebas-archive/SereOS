/* gui/ui.c - kit de componentes visuales comunes de SereOS
 *
 * Unica fuente de estilos para aplicaciones y escritorio: superficies,
 * tarjetas, separadores, tipografia con estilos del sistema, filas
 * etiqueta/valor, indicadores de estado, badges/pills, barras de progreso,
 * botones, tiles de icono e iconos con color.
 *
 * Todo usa los tokens de gui/theme.h (SP_*, RADIUS_*, CTRL_HEIGHT, BAR_*,
 * STATUS_DOT...) y el motor tipografico graphics/text.h. Las primitivas
 * graficas ya recortan por si solas al clip activo del compositor.
 */
#include "ui.h"
#include "icons.h"
#include "graphics.h"
#include "text.h"
#include "string.h"

#define BADGE_PAD_X   6
#define BADGE_H       16
#define PILL_PAD_X    8
#define PILL_H        20
#define ICON_TILE_PAD 10

void ui_init(void) {
	/* El motor de texto e iconos se inicializa en gui_init(); este kit no
	 * guarda estado global propio. Se mantiene por contrato. */
}

/* ------------------------------------------------------------------ */
/* superficies                                                        */
/* ------------------------------------------------------------------ */

void ui_surface(int x, int y, int w, int h, int radius, uint32_t color, int border) {
	if (w <= 0 || h <= 0)
		return;
	if (radius > 0) {
		gfx_fill_round_rect(x, y, w, h, radius, color);
		if (border)
			gfx_draw_round_rect(x, y, w, h, radius, theme.border);
	} else {
		gfx_fill_rect(x, y, w, h, color);
		if (border) {
			gfx_draw_rect(x, y, w, h, theme.border);
		}
	}
}

void ui_card(int x, int y, int w, int h) {
	ui_surface(x, y, w, h, CARD_RADIUS, theme.surface_2, 1);
}

void ui_card_alt(int x, int y, int w, int h) {
	ui_surface(x, y, w, h, CARD_RADIUS, theme.surface, 1);
}

void ui_divider(int x, int y, int w) {
	if (w > 0)
		gfx_fill_rect(x, y, w, 1, theme.border);
}

void ui_divider_alpha(int x, int y, int w, uint8_t alpha) {
	if (w > 0)
		gfx_fill_rect_alpha(x, y, w, 1, theme.border, alpha);
}

/* ------------------------------------------------------------------ */
/* texto                                                              */
/* ------------------------------------------------------------------ */

void ui_label(int x, int y, const char *text, text_style_t style, uint32_t color) {
	if (text)
		text_draw(style, x, y, text, color);
}

void ui_text_center(int cx, int y, const char *text, text_style_t style, uint32_t color) {
	if (text)
		text_draw_center(style, cx, y, text, color);
}

/* convierte a mayusculas ASCII en un buffer local para titulos de seccion */
static void upper_copy(char *dst, int cap, const char *src) {
	int i = 0;

	if (!dst || cap <= 1)
		return;
	while (src && src[i] && i < cap - 1) {
		char c = src[i];

		if (c >= 'a' && c <= 'z')
			c = (char)(c - 'a' + 'A');
		dst[i] = c;
		i++;
	}
	dst[i] = 0;
}

void ui_section_title(int x, int y, const char *text) {
	char buf[64];

	if (!text)
		return;
	upper_copy(buf, (int)sizeof(buf), text);
	text_draw(TEXT_CAPTION, x, y, buf, theme.text_dim);
}

void ui_stat_value(int x, int y, const char *value, text_style_t style) {
	if (value)
		text_draw(style, x, y, value, theme.text);
}

void ui_kv_row(int x, int y, int w, const char *label, const char *value) {
	ui_kv_row_colored(x, y, w, label, value, theme.text);
}

void ui_kv_row_colored(int x, int y, int w, const char *label,
                       const char *value, uint32_t value_color) {
	if (label)
		text_draw(TEXT_SMALL, x, y, label, theme.text_dim);
	if (value)
		text_draw_right(TEXT_SMALL, x + w, y, value, value_color);
}

/* ------------------------------------------------------------------ */
/* indicadores                                                        */
/* ------------------------------------------------------------------ */

void ui_status_dot(int x, int y, int diameter, uint32_t color) {
	int r;

	if (diameter <= 0)
		return;
	r = diameter / 2;
	if (r < 1)
		r = 1;
	gfx_fill_circle(x + diameter / 2, y + diameter / 2, r, color);
}

int ui_badge_width(const char *text) {
	return text_width(TEXT_CAPTION, text ? text : "") + BADGE_PAD_X * 2;
}

void ui_badge(int x, int y, const char *text, uint32_t color) {
	int w;

	if (!text)
		return;
	w = ui_badge_width(text);
	gfx_fill_round_rect_alpha(x, y, w, BADGE_H, RADIUS_XS, color, 46);
	gfx_draw_round_rect(x, y, w, BADGE_H, RADIUS_XS, gui_color_blend(color, theme.surface_2, 90));
	text_draw_center(TEXT_CAPTION, x + w / 2, y + (BADGE_H - text_height(TEXT_CAPTION)) / 2,
	                 text, color);
}

int ui_pill_width(const char *text) {
	return text_width(TEXT_SMALL, text ? text : "") + PILL_PAD_X * 2;
}

void ui_pill(int x, int y, const char *text, uint32_t color) {
	int w;

	if (!text)
		return;
	w = ui_pill_width(text);
	gfx_fill_round_rect_alpha(x, y, w, PILL_H, PILL_H / 2, color, 40);
	text_draw_center(TEXT_SMALL, x + w / 2, y + (PILL_H - text_height(TEXT_SMALL)) / 2,
	                 text, color);
}

void ui_progress_bar(int x, int y, int w, int h, int percent, uint32_t color) {
	int fill;

	if (w <= 0 || h <= 0)
		return;
	if (percent < 0)
		percent = 0;
	if (percent > 100)
		percent = 100;
	if (h < BAR_RADIUS * 2)
		h = BAR_RADIUS * 2;
	gfx_fill_round_rect(x, y, w, h, BAR_RADIUS, theme.surface_3);
	fill = (w * percent) / 100;
	if (fill > 0) {
		if (fill < h)
			fill = h;
		gfx_fill_round_rect(x, y, fill, h, BAR_RADIUS, color);
	}
}

void ui_progress_bar_soft(int x, int y, int w, int h, int percent, uint32_t color) {
	int fill;

	if (w <= 0 || h <= 0)
		return;
	if (percent < 0)
		percent = 0;
	if (percent > 100)
		percent = 100;
	if (h < BAR_RADIUS * 2)
		h = BAR_RADIUS * 2;
	gfx_fill_round_rect(x, y, w, h, BAR_RADIUS, theme.surface_2);
	fill = (w * percent) / 100;
	if (fill > 0) {
		if (fill < h)
			fill = h;
		gfx_fill_round_rect(x, y, fill, h, BAR_RADIUS,
		                    gui_color_blend(color, theme.surface_2, 120));
	}
}

/* ------------------------------------------------------------------ */
/* controles                                                          */
/* ------------------------------------------------------------------ */

void ui_button(int x, int y, int w, int h, const char *label, int hovered, int primary) {
	uint32_t bg, fg;
	uint32_t border;

	if (!label)
		label = "";
	if (primary)
		bg = hovered ? gui_color_blend(theme.accent, theme.white, 26) : theme.accent;
	else
		bg = hovered ? theme.surface_3 : theme.surface_2;
	fg = primary ? theme.white : (hovered ? theme.text : theme.text_dim);
	border = primary ? theme.accent : (hovered ? theme.border_strong : theme.border);

	gfx_fill_round_rect(x, y, w, h, CTRL_RADIUS, bg);
	gfx_draw_round_rect(x, y, w, h, CTRL_RADIUS, border);
	text_draw_center(TEXT_LABEL, x + w / 2, y + (h - text_height(TEXT_LABEL)) / 2,
	                 label, fg);
}

int ui_button_width(const char *label) {
	return text_width(TEXT_LABEL, label ? label : "") + SP_3 * 2;
}

void ui_icon_tile(int cx, int cy, int size, const char *icon,
                  uint32_t tint, int hovered, int selected) {
	int x, y;
	uint32_t bg, border, color;

	if (size <= 0)
		return;
	x = cx - size / 2;
	y = cy - size / 2;
	bg = selected ? theme.accent_soft : (hovered ? theme.surface_3 : theme.surface_2);
	border = selected ? theme.accent : (hovered ? theme.border_strong : theme.border);
	color = (hovered || selected) ? theme.text : tint;

	gfx_fill_round_rect(x, y, size, size, RADIUS_SM, bg);
	gfx_draw_round_rect(x, y, size, size, RADIUS_SM, border);
	if (icon && icon[0]) {
		int isz = size - ICON_TILE_PAD * 2;

		if (isz < 8)
			isz = size;
		icons_draw_color(icon, cx, cy, isz, color);
	}
}

/* ------------------------------------------------------------------ */
/* iconos                                                             */
/* ------------------------------------------------------------------ */

void ui_icon(const char *id, int cx, int cy, int size, uint32_t color) {
	if (id && id[0] && size > 0)
		icons_draw_color(id, cx, cy, size, color);
}

void ui_icon_button(int cx, int cy, int size, const char *icon, int hovered) {
	int pad = SP_1;
	int box = size + pad * 2;

	if (hovered) {
		gfx_fill_round_rect(cx - box / 2, cy - box / 2, box, box,
		                    RADIUS_SM, theme.surface_3);
	}
	ui_icon(icon, cx, cy, size, hovered ? theme.text : theme.text_dim);
}
