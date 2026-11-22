/* gui/icons.c - iconografia lineal de SereOS.
 *
 * Iconos: set ORIGINAL geometrico y minimalista (trazo 1.75 px sobre rejilla
 * 24x24, esquinas redondeadas, sin 3D, sin emojis, sin texto). El arte se
 * define en tools/gen_ui_icons.py y se compila como atlas de cobertura alfa
 * 8bpp (gui/icons_data.c) para los tamanos 16/20/24/32/40/48/64 px. En tiempo
 * de ejecucion solo se tintan y componen mascaras con gfx_blit_alpha8.
 *
 * El logotipo oficial vive en su propio componente (gui/logo.c + logo.h), que
 * incluye la API anterior icons_draw_logo()/icons_logo_width() como
 * compatibilidad basada en el sprite oficial (LOGO_SHAPE_PLAIN).
 */
#include <stdint.h>
#include <string.h>

#include "icons.h"
#include "gui.h"
#include "graphics.h"

#define ICON_SIZES 7

typedef struct {
	const uint8_t *mask;
	uint16_t w, h;
} ui_icon_bitmap_t;

extern const ui_icon_bitmap_t ui_icon_bitmaps[36][ICON_SIZES];
extern const uint16_t ui_icon_dims[ICON_SIZES];
extern const char *const ui_icon_names[36];
extern const uint16_t ui_icon_public_count;

/* ------------------------------------------------------------------ */
/* tokens de color con respaldo durante la migracion del tema          */
/* ------------------------------------------------------------------ */
static uint32_t col_surface_2(void) {
	return theme.surface_2 ? theme.surface_2 : 0x1A1E26u;
}
static uint32_t col_surface_3(void) {
	return theme.surface_3 ? theme.surface_3 : 0x222732u;
}
static uint32_t col_border(void) {
	return theme.border ? theme.border : 0x2A3040u;
}
static uint32_t col_border_strong(void) {
	return theme.border_strong ? theme.border_strong : 0x3A4256u;
}

/* ------------------------------------------------------------------ */
/* atlas                                                               */
/* ------------------------------------------------------------------ */
void icons_init(void) {
	/* el atlas es estatico: no hay recursos que cargar en runtime */
}

static int icon_index(const char *id) {
	int i;
	if (!id) return -1;
	for (i = 0; i < (int)ui_icon_public_count; i++) {
		if (strcmp(ui_icon_names[i], id) == 0)
			return i;
	}
	return -1;
}

/* primer tamano del atlas >= solicitado (los tamanos son crecientes) */
static int pick_size_index(int size) {
	int i;
	for (i = 0; i < ICON_SIZES; i++) {
		if ((int)ui_icon_dims[i] >= size)
			return i;
	}
	return ICON_SIZES - 1;
}

static void blit_centered(const ui_icon_bitmap_t *bm, int x, int y,
                          uint32_t color) {
	if (!bm || !bm->mask || bm->w == 0 || bm->h == 0)
		return;
	gfx_blit_alpha8(x - (int)bm->w / 2, y - (int)bm->h / 2,
	                (int)bm->w, (int)bm->h, bm->mask, color);
}

/* ------------------------------------------------------------------ */
/* API publica                                                         */
/* ------------------------------------------------------------------ */
void icons_draw_color(const char *id, int x, int y, int size, uint32_t color) {
	int idx, si;
	if (size <= 0)
		return;
	idx = icon_index(id);
	if (idx < 0)
		return;
	si = pick_size_index(size);
	blit_centered(&ui_icon_bitmaps[idx][si], x, y, color);
}

void icons_draw(const char *id, int x, int y, int size, int hovered) {
	icons_draw_color(id, x, y, size,
	                 hovered ? theme.text : theme.text_dim);
}

/* RECURSO icono_info (solo ACCESOS): insignia "i" en circulo, trazo lineal,
 * tintada con el azul/celeste de la marca. Reutiliza el icono "about" del
 * atlas, que conserva el trazo y el radio relativos a cualquier tamano.
 *
 * Separacion de recursos: este simbolo identifica el ACCESO a la app
 * "Acerca de" (menu, dock, topnav). La MARCA y el contenido de la ventana
 * usan el recurso independiente logo_sereos (gui/logo.c: logo_draw_about,
 * logo_draw_topbar, logo_draw_brand). Cambiar uno no altera el otro. */
void icons_draw_info_badge(int cx, int cy, int size) {
	icons_draw_color("about", cx, cy, size,
	                 theme.cyan ? theme.cyan : 0x4CC9E0u);
}

void icons_draw_tile(const char *id, int cx, int cy, int tile_size,
                     uint32_t tint, int hovered) {
	int radius = RADIUS_SM;
	int x, y, icon_size;

	if (tile_size <= 0)
		return;
	if (radius * 2 > tile_size)
		radius = tile_size / 4;
	if (radius < 1)
		radius = 1;

	x = cx - tile_size / 2;
	y = cy - tile_size / 2;

	gfx_fill_round_rect(x, y, tile_size, tile_size, radius,
	                    hovered ? col_surface_3() : col_surface_2());
	gfx_draw_round_rect(x, y, tile_size, tile_size, radius,
	                    hovered ? col_border_strong() : col_border());

	icon_size = tile_size * 56 / 100;
	if (icon_size > tile_size - 6)
		icon_size = tile_size - 6;
	if (icon_size < 8)
		icon_size = 8;
	icons_draw_color(id, cx, cy, icon_size, tint);
}
