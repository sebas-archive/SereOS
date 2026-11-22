/* gui/ui.h - kit de componentes visuales comunes de SereOS
 *
 * Implementado una sola vez en gui/ui.c y reutilizado por TODAS las
 * aplicaciones para garantizar consistencia (radios, espaciado, tipografia,
 * estados). Las apps no dibujan sus propias tarjetas/botones.
 */
#ifndef SEREOS_UI_H
#define SEREOS_UI_H
#include <stdint.h>
#include "theme.h"

void ui_init(void);

/* superficies */
void ui_surface(int x, int y, int w, int h, int radius, uint32_t color, int border);
void ui_card(int x, int y, int w, int h);
void ui_card_alt(int x, int y, int w, int h);
void ui_divider(int x, int y, int w);
void ui_divider_alpha(int x, int y, int w, uint8_t alpha);

/* texto con estilos del sistema */
void ui_label(int x, int y, const char *text, text_style_t style, uint32_t color);
void ui_text_center(int cx, int y, const char *text, text_style_t style, uint32_t color);
void ui_section_title(int x, int y, const char *text);      /* caption mayusculas dim */
void ui_stat_value(int x, int y, const char *value, text_style_t style);

/* fila etiqueta/valor alineada a la derecha */
void ui_kv_row(int x, int y, int w, const char *label, const char *value);
void ui_kv_row_colored(int x, int y, int w, const char *label,
                       const char *value, uint32_t value_color);

/* indicadores */
void ui_status_dot(int x, int y, int diameter, uint32_t color);
void ui_badge(int x, int y, const char *text, uint32_t color);
int  ui_badge_width(const char *text);
void ui_pill(int x, int y, const char *text, uint32_t color);
int  ui_pill_width(const char *text);
void ui_progress_bar(int x, int y, int w, int h, int percent, uint32_t color);
void ui_progress_bar_soft(int x, int y, int w, int h, int percent, uint32_t color);

/* controles */
void ui_button(int x, int y, int w, int h, const char *label, int hovered, int primary);
int  ui_button_width(const char *label);
void ui_icon_tile(int cx, int cy, int size, const char *icon,
                  uint32_t tint, int hovered, int selected);

/* iconos con color (delegan en gui/icons.h) */
void ui_icon(const char *id, int cx, int cy, int size, uint32_t color);
void ui_icon_button(int cx, int cy, int size, const char *icon, int hovered);

#endif
