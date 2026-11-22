/* gui/cursor.c - cursor del raton compuesto sobre el backbuffer
 *
 * Flecha monocroma de 12x18 px con contorno oscuro y una sombra minima de
 * un pixel desplazada. Se guarda el fondo del backbuffer antes de pintar y se
 * restaura en el siguiente frame; cursor_restore() es idempotente.
 */
#include "cursor.h"
#include "theme.h"
#include "graphics.h"
#include "framebuffer.h"

#define CURSOR_W 12
#define CURSOR_H 18
#define CURSOR_SAVE_W (CURSOR_W + 1)   /* margen para la sombra desplazada */
#define CURSOR_SAVE_H (CURSOR_H + 1)

/* '#' = contorno oscuro, '*' = relleno claro, '.' = transparente */
static const char *const cursor_rows[CURSOR_H] = {
	"#...........",
	"##..........",
	"#*#.........",
	"#**#........",
	"#***#.......",
	"#****#......",
	"#*****#.....",
	"#******#....",
	"#*******#...",
	"#********#..",
	"#*****#####.",
	"#**#**#.....",
	"#*#.#**#....",
	"##..#**#....",
	"#....#**#...",
	".....#**#...",
	"......#**#..",
	"......###..."
};

static uint32_t cursor_saved[CURSOR_SAVE_H][CURSOR_SAVE_W];
static int      cursor_saved_x;
static int      cursor_saved_y;
static int      cursor_visible;
static int      cursor_ready;

static void cursor_put(int x, int y, uint32_t color) {
	int w = gfx_width();
	int h = gfx_height();

	if (x < 0 || y < 0 || x >= w || y >= h)
		return;
	gfx_put_pixel(x, y, color);
}

void cursor_init(void) {
	cursor_visible = 0;
	cursor_ready = 1;
	cursor_saved_x = 0;
	cursor_saved_y = 0;
}

void cursor_restore(void) {
	int x, y, dx, dy;
	int clip[4];

	if (!cursor_visible || !cursor_ready)
		return;
	x = cursor_saved_x;
	y = cursor_saved_y;

	gfx_get_clip(&clip[0], &clip[1], &clip[2], &clip[3]);
	gfx_reset_clip();
	for (dy = 0; dy < CURSOR_SAVE_H; dy++) {
		for (dx = 0; dx < CURSOR_SAVE_W; dx++)
			cursor_put(x + dx, y + dy, cursor_saved[dy][dx]);
	}
	gfx_mark_dirty(x, y, CURSOR_SAVE_W, CURSOR_SAVE_H);
	gfx_set_clip(clip[0], clip[1], clip[2], clip[3]);
	cursor_visible = 0;
}

void cursor_draw(int x, int y) {
	int sw, sh, dx, dy;
	int clip[4];
	uint32_t fill;
	uint32_t stroke;
	uint32_t shadow;

	if (!cursor_ready)
		return;
	if (cursor_visible)
		cursor_restore();

	sw = gfx_width();
	sh = gfx_height();
	if (sw <= 0 || sh <= 0)
		return;
	if (x < 0)
		x = 0;
	if (y < 0)
		y = 0;
	if (x >= sw)
		x = sw - 1;
	if (y >= sh)
		y = sh - 1;

	/* guardar fondo del sprite (flecha + sombra) */
	gfx_get_clip(&clip[0], &clip[1], &clip[2], &clip[3]);
	gfx_reset_clip();
	for (dy = 0; dy < CURSOR_SAVE_H; dy++) {
		for (dx = 0; dx < CURSOR_SAVE_W; dx++) {
			int gx = x + dx;
			int gy = y + dy;

			cursor_saved[dy][dx] = (gx < sw && gy < sh) ? gfx_get_pixel(gx, gy) : 0;
		}
	}
	cursor_saved_x = x;
	cursor_saved_y = y;

	fill = theme.text;
	stroke = theme.bg;
	shadow = gui_color_blend(theme.black, theme.bg, 128);

	/* sombra minima: solo el contorno desplazado 1 px */
	for (dy = 0; dy < CURSOR_H; dy++) {
		for (dx = 0; dx < CURSOR_W; dx++) {
			if (cursor_rows[dy][dx] == '#')
				cursor_put(x + dx + 1, y + dy + 1, shadow);
		}
	}
	/* flecha: relleno claro con contorno oscuro */
	for (dy = 0; dy < CURSOR_H; dy++) {
		for (dx = 0; dx < CURSOR_W; dx++) {
			char c = cursor_rows[dy][dx];

			if (c == '*')
				cursor_put(x + dx, y + dy, fill);
			else if (c == '#')
				cursor_put(x + dx, y + dy, stroke);
		}
	}
	gfx_mark_dirty(x, y, CURSOR_SAVE_W, CURSOR_SAVE_H);
	gfx_set_clip(clip[0], clip[1], clip[2], clip[3]);
	cursor_visible = 1;
}

int cursor_width(void) { return CURSOR_W; }
int cursor_height(void) { return CURSOR_H; }
