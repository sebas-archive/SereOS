/* PAC-MAN SereOS - tokens visuales compartidos (mismos valores que SereOS)
 *
 * El render comun usa estos tokens para que la interfaz del juego sea
 * identica en SereOS Desktop y en Linux. No incluye nada del OS: es una
 * copia autocontenida de gui/theme.h adaptada a nombres propios (`pac_theme`)
 * para evitar colisiones de simbolos al enlazar dentro del kernel.
 */
#ifndef PACMAN_THEME_H
#define PACMAN_THEME_H

#include <stdint.h>

typedef struct {
	uint32_t bg;
	uint32_t bg_elevated;
	uint32_t surface;
	uint32_t surface_2;
	uint32_t surface_3;
	uint32_t border;
	uint32_t border_strong;
	uint32_t shadow;
	uint32_t text;
	uint32_t text_dim;
	uint32_t text_faint;
	uint32_t accent;
	uint32_t accent_soft;
	uint32_t cyan;
	uint32_t green;
	uint32_t amber;
	uint32_t red;
	uint32_t white;
	uint32_t black;
} pac_theme_t;

extern const pac_theme_t pac_theme;

uint32_t pac_color_blend(uint32_t fg, uint32_t bg, uint8_t alpha);

/* escala de espaciado en multiplos de 4 px */
#define SP_0   0
#define SP_1   4
#define SP_2   8
#define SP_3   12
#define SP_4   16
#define SP_5   20
#define SP_6   24
#define SP_8   32
#define SP_10  40
#define SP_12  48

/* radios */
#define RADIUS_XS  4
#define RADIUS_SM  6
#define RADIUS_MD  10
#define RADIUS_LG  14
#define RADIUS_XL  18

#endif /* PACMAN_THEME_H */
