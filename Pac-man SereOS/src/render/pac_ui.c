/* PAC-MAN SereOS - kit minimo de UI compartido (tarjetas y separadores) */
#include "pac_ui.h"
#include "pac_platform.h"

void pac_ui_surface(int x, int y, int w, int h, int radius,
                    uint32_t color, int border)
{
	if (w <= 0 || h <= 0)
		return;
	if (radius > 0) {
		pac_fill_round_rect(x, y, w, h, radius, color);
		if (border)
			pac_draw_round_rect(x, y, w, h, radius, pac_theme.border);
	} else {
		pac_fill_rect(x, y, w, h, color);
		if (border)
			pac_draw_rect(x, y, w, h, pac_theme.border);
	}
}

void pac_ui_card(int x, int y, int w, int h)
{
	pac_ui_surface(x, y, w, h, RADIUS_MD, pac_theme.surface_2, 1);
}

void pac_ui_card_alt(int x, int y, int w, int h)
{
	pac_ui_surface(x, y, w, h, RADIUS_MD, pac_theme.surface, 1);
}

void pac_ui_divider(int x, int y, int w)
{
	if (w > 0)
		pac_fill_rect(x, y, w, 1, pac_theme.border);
}

void pac_ui_divider_alpha(int x, int y, int w, uint8_t alpha)
{
	if (w > 0)
		pac_fill_rect_alpha(x, y, w, 1, pac_theme.border, alpha);
}
