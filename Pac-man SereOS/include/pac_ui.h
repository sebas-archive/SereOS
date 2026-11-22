/* PAC-MAN SereOS - mini kit de UI compartido
 *
 * Tarjetas, superficies y separadores con los tokens de pac_theme.h. Se
 * implementa una sola vez en src/render/pac_ui.c sobre las primitivas de
 * pac_platform.h, de modo que SereOS y Linux dibujan exactamente igual.
 */
#ifndef PACMAN_UI_H
#define PACMAN_UI_H

#include <stdint.h>
#include "pac_theme.h"

/* superficie con radio y borde opcional */
void pac_ui_surface(int x, int y, int w, int h, int radius,
                    uint32_t color, int border);

/* tarjeta estandar: surface_2 + borde + sombra suave */
void pac_ui_card(int x, int y, int w, int h);
void pac_ui_card_alt(int x, int y, int w, int h);

/* separador de 1 px */
void pac_ui_divider(int x, int y, int w);
void pac_ui_divider_alpha(int x, int y, int w, uint8_t alpha);

#endif /* PACMAN_UI_H */
