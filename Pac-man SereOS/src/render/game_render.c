/* apps/game/game_render.c - interfaz de PAC-MAN SereOS (sistema de diseno)
 *
 * La capa de juego sigue siendo arcade (laberinto azul y sprites originales),
 * pero menu, instrucciones, record, pausa, game over, nivel completado y HUD
 * usan el lenguaje visual de SereOS: tipografia Inter/JetBrains Mono
 * (graphics/text.h), tokens de gui/pac_theme.h y el kit gui/ui.h (tarjetas,
 * separadores y superficies). Sin bordes dobles ni decoracion: jerarquia
 * clara, espaciado en multiplos de 4 y estados con color semantico.
 */
#include <stdint.h>
#include "string.h"
#include "pac_platform.h"
#include "pac_theme.h"
#include "pac_ui.h"
#include "arcade_text.h"
#include "font_arcade.h"
#include "sprites.h"
#include "pac_game.h"
#include "game_maze.h"
#include "game_ai.h"
#include "game_render.h"

#define C_BG        (pac_theme.bg)
#define C_BG_ALT    (pac_theme.bg_elevated)
#define C_SURFACE   (pac_theme.surface)
#define C_SURFACE2  (pac_theme.surface_2)
#define C_SURFACE3  (pac_theme.surface_3)
#define C_BORDER    (pac_theme.border)
#define C_TEXT      (pac_theme.text)
#define C_DIM       (pac_theme.text_dim)
#define C_FAINT     (pac_theme.text_faint)
#define C_ACCENT    (pac_theme.accent)
#define C_SOFT      (pac_theme.accent_soft)
#define C_CYAN      (pac_theme.cyan)
#define C_GREEN     (pac_theme.green)
#define C_AMBER     (pac_theme.amber)
#define C_RED       (pac_theme.red)
#define C_PINK      0x00FF6CC4u
#define C_ORANGE    0x00FF9C37u

/* colores arcade del tablero (se mantienen del juego original) */
#define C_DOT       0x00FFE0B0u
#define C_POWER     0x00FFD447u
#define C_POPUP     0x0075E8FFu
#define C_FRUITVAL  0x00FFD447u

typedef struct {
	int ox, oy, cw, ch;
	int mx, my;          /* origen del laberinto */
	int left_w, right_w;
	int side;            /* 1 si hay espacio para paneles laterales */
} rview_t;

static void utoi_small(char *buf, int value)
{
	char tmp[12];
	int i = 0, n = 0;
	unsigned int u;

	if (value < 0) {
		buf[n++] = '-';
		u = (unsigned int)(-value);
	} else {
		u = (unsigned int)value;
	}
	do {
		tmp[i++] = (char)('0' + u % 10u);
		u /= 10u;
	} while (u);
	while (i > 0)
		buf[n++] = tmp[--i];
	buf[n] = 0;
}

/* fila generica etiqueta/valor alineada al panel */
static void kv_row(int x, int y, int w, const char *label, const char *value,
                   pac_text_style_t vstyle, uint32_t vcolor)
{
	pac_text_draw(PAC_TEXT_LABEL, x, y, label, C_DIM);
	pac_text_draw_right(vstyle, x + w, y + (pac_text_height(PAC_TEXT_LABEL) - pac_text_height(vstyle)) / 2,
	                value, vcolor);
}

/* tecla en una tecla/badge del kit de forma contenida */
static int key_badge(int x, int y, const char *key)
{
	int w = pac_text_width(PAC_TEXT_CAPTION, key) + SP_3;
	int h = pac_text_height(PAC_TEXT_CAPTION) + SP_2;

	if (h < 20)
		h = 20;
	pac_fill_round_rect(x, y, w, h, RADIUS_XS, C_SURFACE3);
	pac_draw_round_rect(x, y, w, h, RADIUS_XS, C_BORDER);
	pac_text_draw_center(PAC_TEXT_CAPTION, x + w / 2, y + (h - pac_text_height(PAC_TEXT_CAPTION)) / 2,
	                 key, C_TEXT);
	return w;
}

static int action_row_height(void)
{
	int h = pac_text_height(PAC_TEXT_BODY) + SP_2;
	if (h < 26)
		h = 26;
	return h;
}

static void action_row(int x, int y, int w, const char *key, const char *label)
{
	int kw;
	(void)w;
	kw = key_badge(x, y, key);
	pac_text_draw(PAC_TEXT_BODY, x + kw + SP_3,
	          y + (pac_text_height(PAC_TEXT_CAPTION) + SP_2 - pac_text_height(PAC_TEXT_BODY)) / 2,
	          label, C_TEXT);
}

static void bg_fill(const rview_t *v)
{
	int bands = 16;
	int i;
	for (i = 0; i < bands; i++) {
		int y0 = v->oy + v->ch * i / bands;
		int y1 = v->oy + v->ch * (i + 1) / bands;
		uint8_t a = (uint8_t)(i * 255 / (bands - 1));
		uint32_t color = pac_color_blend(C_BG_ALT, C_BG, a);
		pac_fill_rect(v->ox, y0, v->cw, y1 - y0 + 1, color);
	}
}

/* ------------------------------------------------------------------ */
/* layout de la vista                                                  */
/* ------------------------------------------------------------------ */
static void view_get(pac_game_t *g, rview_t *v)
{
	v->ox = g->viewport.x;
	v->oy = g->viewport.y;
	v->cw = g->viewport.w;
	v->ch = g->viewport.h;
	if (v->cw < 1)
		v->cw = 1;
	if (v->ch < 1)
		v->ch = 1;

	v->mx = v->ox + (v->cw - PAC_MAZE_W) / 2;
	if (v->mx < v->ox + SP_2)
		v->mx = v->ox + SP_2;
	v->my = v->oy + (v->ch - PAC_MAZE_H) / 2;
	if (v->my < v->oy + SP_2)
		v->my = v->oy + SP_2;

	v->left_w = v->mx - v->ox - 2 * SP_3;
	v->right_w = v->ox + v->cw - (v->mx + PAC_MAZE_W) - 2 * SP_3;
	if (v->left_w < 0)
		v->left_w = 0;
	if (v->right_w < 0)
		v->right_w = 0;
	v->side = (v->left_w >= 112 && v->right_w >= 112 &&
	           v->ch >= 240);
}

/* ------------------------------------------------------------------ */
/* sprites                                                             */
/* ------------------------------------------------------------------ */
static int dir_asset_index(pac_dir_t d)
{
	switch (d) {
	case PAC_DIR_RIGHT: return 0;
	case PAC_DIR_LEFT:  return 1;
	case PAC_DIR_UP:    return 2;
	case PAC_DIR_DOWN:  return 3;
	default:            return 0;
	}
}

static const uint16_t *pacman_sprite(const pac_game_t *g)
{
	int dir = dir_asset_index(g->pac.facing != PAC_DIR_NONE ? g->pac.facing
	                                                       : g->pac.dir);
	int mouth = g->pac.mouth;
	if (mouth < 0 || mouth > 2)
		mouth = 1;
	return pacasset_pacman_frame[dir][mouth];
}

static const uint16_t *ghost_sprite(const pac_game_t *g, const ghost_t *gh)
{
	int idx = (int)(gh - g->ghosts);

	if (gh->state == PAC_GHOST_EATEN)
		return pacasset_ghost_eyes_frame[dir_asset_index(gh->facing)];
	if (gh->scared) {
		int flash = (g->fright_ms > 0 && g->fright_ms < 1800 &&
		             ((g->fright_ms / 200) & 1));
		if (flash)
			return pacasset_ghost_flash_frame[(gh->anim_ms / 120) & 1];
		return pacasset_ghost_fright_frame[(gh->anim_ms / 120) & 1];
	}
	return pacasset_ghost_frame[idx][(gh->anim_ms / 250) & 1];
}

/* ------------------------------------------------------------------ */
/* tablero de juego                                                    */
/* ------------------------------------------------------------------ */
static void draw_dots(pac_game_t *g, const rview_t *v)
{
	int row, col;
	for (row = 0; row < PAC_ROWS; row++) {
		for (col = 0; col < PAC_COLS; col++) {
			int t = pac_maze_tile(g, col, row);
			int cx = v->mx + col * PAC_TILE + PAC_TILE / 2;
			int cy = v->my + row * PAC_TILE + PAC_TILE / 2;
			if (t == PAC_TILE_DOT) {
				pac_fill_rect(cx - 1, cy - 1, 3, 3, C_DOT);
				pac_fill_rect(cx, cy, 1, 1, 0x00FFFFFFu);
			} else if (t == PAC_TILE_POWER) {
				int pulse = (int)(g->anim_ms % 400);
				int r = pulse < 200 ? 4 : 3;
				pac_fill_rect_alpha(cx - r - 2, cy - r - 2, (r + 2) * 2,
				                    (r + 2) * 2, C_POWER, 60);
				pac_fill_rect(cx - r, cy - r, r * 2 + 1, r * 2 + 1, C_POWER);
				pac_fill_rect(cx - r + 1, cy - r + 1, 2, 2, 0x00FFF9D0u);
			}
		}
	}
}

static void draw_entities(pac_game_t *g, const rview_t *v)
{
	int i;

	for (i = 0; i < PAC_GHOST_COUNT; i++) {
		const ghost_t *gh = &g->ghosts[i];
		int sx = v->mx + PAC_PX(gh->x) - PAC_TILE / 2;
		int sy = v->my + PAC_PX(gh->y) - PAC_TILE / 2;
		pac_sprite(sx, sy, ghost_sprite(g, gh), PAC_SPRITE_SIZE,
		                PAC_SPRITE_SIZE);
	}

	if (g->fruit_visible_ms > 0) {
		int idx = g->fruit_index;
		if (idx < 0 || idx >= PAC_FRUIT_COUNT)
			idx = 0;
		pac_sprite(v->mx + PAC_FRUIT_COL * PAC_TILE,
		                v->my + PAC_FRUIT_ROW * PAC_TILE,
		                pacasset_fruit_sprite[idx], PAC_SPRITE_SIZE, PAC_SPRITE_SIZE);
	}
	if (g->fruit_flash_ms > 0) {
		char buf[16];
		utoi_small(buf, g->fruit_value);
		pac_text_draw(PAC_TEXT_SMALL,
		          v->mx + PAC_FRUIT_COL * PAC_TILE + PAC_TILE + SP_1,
		          v->my + PAC_FRUIT_ROW * PAC_TILE + SP_1, buf, C_FRUITVAL);
	}

	{
		pacman_t *p = &g->pac;
		int sx = v->mx + PAC_PX(p->x) - PAC_TILE / 2;
		int sy = v->my + PAC_PX(p->y) - PAC_TILE / 2;
		if (p->death_ms > 0) {
			int elapsed = PAC_DEATH_MS - p->death_ms;
			pac_dir_t d = (pac_dir_t)(1 + (elapsed / 120) % 4);
			uint8_t alpha = 255;
			if (p->death_ms < 700)
				alpha = (uint8_t)(p->death_ms * 255 / 700);
			pac_sprite_alpha(sx, sy, pacasset_pacman_frame[dir_asset_index(d)][2],
			                      PAC_SPRITE_SIZE, PAC_SPRITE_SIZE, alpha);
		} else if (p->alive) {
			pac_sprite(sx, sy, pacman_sprite(g), PAC_SPRITE_SIZE,
			                PAC_SPRITE_SIZE);
		}
	}

	if (g->popup_ms > 0) {
		char buf[16];
		int x, y;
		utoi_small(buf, g->popup_value);
		x = v->mx + PAC_PX(g->popup_x);
		y = v->my + PAC_PX(g->popup_y);
		pac_text_draw_center(PAC_TEXT_MONO_SMALL, x, y, buf, C_POPUP);
	}
}

/* cartel retro READY!: caja oscura con borde blanco de 3 px, linea azul
 * interior y texto arcade amarillo con sombra, centrado en el viewport */
static void draw_ready_banner(const rview_t *v)
{
	const char *text = "READY!";
	const int scale = 2;
	int cx = v->ox + v->cw / 2;
	int cy = v->oy + v->ch / 2;
	int text_w = pac_arcade_text_width(text, scale);
	int text_h = PAC_ARCADEFONT_H * scale;
	int box_w = text_w + 2 * SP_6;
	int box_h = text_h + 2 * SP_3;
	int box_x = cx - box_w / 2;
	int box_y = cy - box_h / 2;
	int text_x = cx - text_w / 2;
	/* Press Start K pinta la tinta 8x8 arriba de la celda 8x16: el centro
	 * optico de la tinta queda media celda por debajo del centro de la celda */
	int text_y = cy - text_h / 2 + text_h / 4;

	if (box_w <= 6 || box_h <= 6)
		return;

	/* bordes rectos, sin redondeos: blanco de 3 px + relleno oscuro */
	pac_fill_rect(box_x, box_y, box_w, box_h, 0x00FFFFFFu);
	pac_fill_rect(box_x + 3, box_y + 3, box_w - 6, box_h - 6, 0x0005060Fu);
	pac_draw_rect(box_x + 3, box_y + 3, box_w - 6, box_h - 6, 0x002F6DF6u);

	/* sombra solida negra desplazada 2 px y texto amarillo encima */
	pac_arcade_text_draw(text_x + 2, text_y + 2, text, 0x00000000u, scale);
	pac_arcade_text_draw(text_x, text_y, text, 0x00FFD23Fu, scale);
}

static void draw_game_field(pac_game_t *g, const rview_t *v)
{
	pac_blit_rgb(v->mx, v->my, PAC_MAZE_W, PAC_MAZE_H, pac_maze_background());
	draw_dots(g, v);
	{
		/* Recorte del area del laberinto para los personajes: equivale a
		 * ctx.save(); ctx.rect(mx, my, PAC_MAZE_W, PAC_MAZE_H); ctx.clip();
		 * y, al final, ctx.restore(). El clip se compone a mano porque
		 * pac_set_clip() REEMPLAZA el clip en ambos backends: guardamos el
		 * clip vigente, calculamos su interseccion con el rect exacto del
		 * laberinto (solo v->mx/v->my, nunca viewport ni ventana) y luego
		 * restauramos el clip guardado. Asi fantasmas, fruta/popup y
		 * Pac-Man nunca pintan fuera del tablero. NO cubre READY!, HUD ni
		 * overlays, que se dibujan despues o con otro clip. */
		pac_rect_t clip_prev, clip_maze;
		int x0, y0, x1, y1;

		pac_get_clip(&clip_prev);

		/* interseccion manual: max de los origenes, min de los finales */
		x0 = clip_prev.x;
		if (v->mx > x0)
			x0 = v->mx;
		y0 = clip_prev.y;
		if (v->my > y0)
			y0 = v->my;
		x1 = clip_prev.x + clip_prev.w;
		if (v->mx + PAC_MAZE_W < x1)
			x1 = v->mx + PAC_MAZE_W;
		y1 = clip_prev.y + clip_prev.h;
		if (v->my + PAC_MAZE_H < y1)
			y1 = v->my + PAC_MAZE_H;
		if (x1 < x0)
			x1 = x0;
		if (y1 < y0)
			y1 = y0;

		clip_maze.x = x0;
		clip_maze.y = y0;
		clip_maze.w = x1 - x0;
		clip_maze.h = y1 - y0;
		pac_set_clip(clip_maze.x, clip_maze.y, clip_maze.w, clip_maze.h);

		draw_entities(g, v);

		/* ctx.restore(): devolver el clip anterior tal cual estaba */
		pac_set_clip(clip_prev.x, clip_prev.y, clip_prev.w, clip_prev.h);
	}
	if (g->ready_ms > 0)
		draw_ready_banner(v);
}

/* ------------------------------------------------------------------ */
/* HUD                                                                 */
/* ------------------------------------------------------------------ */
static const char *state_text(const pac_game_t *g, uint32_t *color)
{
	if (g->state == PAC_STATE_PAUSED) {
		*color = C_ACCENT;
		return "PAUSA";
	}
	if (g->ready_ms > 0) {
		*color = C_AMBER;
		return "READY";
	}
	if (g->fright_ms > 0) {
		*color = C_CYAN;
		return "FRIGHTENED";
	}
	if (g->mode == PAC_PHASE_CHASE) {
		*color = C_RED;
		return "CHASE";
	}
	*color = C_DIM;
	return "SCATTER";
}

static void draw_status_caption(int x, int y, const pac_game_t *g)
{
	uint32_t color;
	const char *s = state_text(g, &color);
	pac_text_draw(PAC_TEXT_CAPTION, x, y, s, color);
}

static void draw_hud_panels(pac_game_t *g, const rview_t *v)
{
	char buf[24];
	int x, y, w, h, i;

	/* panel izquierdo: marca, puntuacion, record y nivel */
	w = v->left_w;
	if (w > 220)
		w = 220;
	x = v->mx - SP_3 - w;
	y = v->my;
	h = v->ch - (v->my - v->oy);
	if (h > PAC_MAZE_H)
		h = PAC_MAZE_H;
	if (h < 200)
		return;
	pac_ui_surface(x, y, w, h, RADIUS_MD, C_SURFACE2, 1);

	y += SP_4;
	pac_arcade_text_draw(x + SP_4, y, PAC_APP_NAME, C_TEXT, 1);
	y += pac_text_height(PAC_TEXT_LABEL) + SP_3;
	pac_ui_divider(x + SP_4, y, w - 2 * SP_4);
	y += SP_3;

	pac_text_draw(PAC_TEXT_CAPTION, x + SP_4, y, "1UP", C_DIM);
	y += pac_text_height(PAC_TEXT_CAPTION) + SP_1;
	utoi_small(buf, g->score);
	pac_text_draw(PAC_TEXT_MONO, x + SP_4, y, buf, C_TEXT);
	y += pac_text_height(PAC_TEXT_MONO) + SP_2;

	pac_text_draw(PAC_TEXT_CAPTION, x + SP_4, y, "HI", C_DIM);
	y += pac_text_height(PAC_TEXT_CAPTION) + SP_1;
	utoi_small(buf, g->high_score);
	pac_text_draw(PAC_TEXT_MONO, x + SP_4, y, buf, C_AMBER);
	y += pac_text_height(PAC_TEXT_MONO) + SP_4;

	pac_ui_divider(x + SP_4, y, w - 2 * SP_4);
	y += SP_3;
	utoi_small(buf, g->level);
	/* la llave es un icono decorativo del indicador de nivel */
	pac_sprite(x + SP_4, y, pacasset_key_sprite, PAC_SPRITE_SIZE, PAC_SPRITE_SIZE);
	pac_text_draw(PAC_TEXT_LABEL, x + SP_4 + PAC_SPRITE_SIZE + SP_2,
	          y + (PAC_SPRITE_SIZE - pac_text_height(PAC_TEXT_LABEL)) / 2, "NIVEL", C_DIM);
	pac_text_draw_right(PAC_TEXT_MONO, x + w - SP_4,
	                y + (PAC_SPRITE_SIZE - pac_text_height(PAC_TEXT_MONO)) / 2, buf, C_TEXT);

	/* pie del panel: control de pausa */
	{
		int footer_y = v->my + h - SP_4 - pac_text_height(PAC_TEXT_CAPTION);
		if (footer_y > y + pac_text_height(PAC_TEXT_LABEL) + SP_4)
			pac_text_draw(PAC_TEXT_CAPTION, x + SP_4, footer_y, "Esc: pausa", C_FAINT);
	}

	/* panel derecho: vidas, frutas y estado */
	w = v->right_w;
	if (w > 220)
		w = 220;
	x = v->mx + PAC_MAZE_W + SP_3;
	y = v->my;
	pac_ui_surface(x, y, w, h, RADIUS_MD, C_SURFACE2, 1);

	y += SP_4;
	pac_text_draw(PAC_TEXT_LABEL, x + SP_4, y, "VIDAS", C_DIM);
	y += pac_text_height(PAC_TEXT_LABEL) + SP_2;
	for (i = 0; i < g->lives && i < 6; i++) {
		int sx = x + SP_4 + i * (PAC_SPRITE_SIZE + SP_1);
		if (sx + PAC_SPRITE_SIZE > x + w - SP_4)
			break;
		pac_sprite(sx, y, pacasset_life_sprite, PAC_SPRITE_SIZE, PAC_SPRITE_SIZE);
	}
	y += PAC_SPRITE_SIZE + SP_3;

	pac_ui_divider(x + SP_4, y, w - 2 * SP_4);
	y += SP_3;
	pac_text_draw(PAC_TEXT_LABEL, x + SP_4, y, "FRUTAS", C_DIM);
	y += pac_text_height(PAC_TEXT_LABEL) + SP_2;
	{
		int shown = 0;
		int col_w = (w - 2 * SP_4) / 2;

		/* historial de frutas comidas: sprite + "xN" por tipo (2 columnas) */
		for (i = 0; i < PAC_FRUIT_COUNT; i++) {
			int sx, sy;
			if (g->fruit_counts[i] == 0)
				continue;
			sx = x + SP_4 + (shown % 2) * col_w;
			sy = y + (shown / 2) * (PAC_SPRITE_SIZE + SP_1);
			pac_sprite(sx, sy, pacasset_fruit_sprite[i],
			                PAC_SPRITE_SIZE, PAC_SPRITE_SIZE);
			buf[0] = 'x';
			utoi_small(buf + 1, (int)g->fruit_counts[i]);
			pac_text_draw(PAC_TEXT_CAPTION,
			          sx + PAC_SPRITE_SIZE + SP_1,
			          sy + (PAC_SPRITE_SIZE - pac_text_height(PAC_TEXT_CAPTION)) / 2,
			          buf, C_TEXT);
			shown++;
		}
		if (shown > 0)
			y += ((shown + 1) / 2) * (PAC_SPRITE_SIZE + SP_1);
		if (g->fruit_eaten_count > 0) {
			int n = 0;
			const char *pre = "TOTAL: ";
			while (pre[n] != 0) {
				buf[n] = pre[n];
				n++;
			}
			utoi_small(buf + n, g->fruit_eaten_count);
			pac_text_draw(PAC_TEXT_CAPTION, x + SP_4, y, buf, C_DIM);
		} else {
			pac_text_draw(PAC_TEXT_CAPTION, x + SP_4, y, "Ninguna aun", C_FAINT);
		}
		y += pac_text_height(PAC_TEXT_CAPTION) + SP_2;
	}
	/* fruta en juego (si aparece) */
	if (g->fruit_visible_ms > 0) {
		int idx = g->fruit_index;
		if (idx < 0 || idx >= PAC_FRUIT_COUNT)
			idx = 0;
		pac_text_draw(PAC_TEXT_CAPTION, x + SP_4, y, "EN JUEGO", C_DIM);
		pac_sprite(x + SP_4 + pac_text_width(PAC_TEXT_CAPTION, "EN JUEGO") + SP_2, y - 1,
		                pacasset_fruit_sprite[idx], PAC_SPRITE_SIZE, PAC_SPRITE_SIZE);
		y += PAC_SPRITE_SIZE + SP_3;
	}

	pac_ui_divider(x + SP_4, y, w - 2 * SP_4);
	y += SP_3;
	pac_text_draw(PAC_TEXT_LABEL, x + SP_4, y, "ESTADO", C_DIM);
	y += pac_text_height(PAC_TEXT_LABEL) + SP_1;
	draw_status_caption(x + SP_4, y, g);
	y += pac_text_height(PAC_TEXT_CAPTION) + SP_1;
}

static void draw_hud_compact(pac_game_t *g, const rview_t *v)
{
	char buf[24];
	int x = v->ox + SP_2;
	int y = v->oy + SP_2;
	int w = v->cw - 2 * SP_2;
	int h = 60;
	int i;

	pac_ui_surface(x, y, w, h, RADIUS_MD, C_SURFACE2, 1);

	/* fila 1: puntuacion a la izquierda, record a la derecha */
	pac_text_draw(PAC_TEXT_CAPTION, x + SP_2, y + SP_2, "1UP", C_DIM);
	utoi_small(buf, g->score);
	pac_text_draw(PAC_TEXT_MONO, x + SP_2 + pac_text_width(PAC_TEXT_CAPTION, "1UP") + SP_2,
	          y + SP_2 - 2, buf, C_TEXT);
	utoi_small(buf, g->high_score);
	pac_text_draw_right(PAC_TEXT_MONO, x + w - SP_2, y + SP_2 - 2, buf, C_AMBER);
	pac_text_draw_right(PAC_TEXT_CAPTION, x + w - SP_2 - pac_text_width(PAC_TEXT_MONO, buf) - SP_2,
	                y + SP_2, "HI", C_DIM);

	/* fila 2: vidas, nivel y estado */
	y += SP_2 + pac_text_height(PAC_TEXT_MONO) + SP_1;
	for (i = 0; i < g->lives && i < 4; i++)
		pac_sprite(x + SP_2 + i * (PAC_SPRITE_SIZE + 1), y,
		                pacasset_life_sprite, PAC_SPRITE_SIZE, PAC_SPRITE_SIZE);
	utoi_small(buf, g->level);
	pac_text_draw(PAC_TEXT_MONO, x + SP_2 + 4 * (PAC_SPRITE_SIZE + 1) + SP_2, y - 1,
	          buf, C_TEXT);
	{
		uint32_t color;
		const char *st = state_text(g, &color);
		pac_text_draw_right(PAC_TEXT_CAPTION, x + w - SP_2,
		                y + (PAC_SPRITE_SIZE - pac_text_height(PAC_TEXT_CAPTION)) / 2,
		                st, color);
	}
}

/* ------------------------------------------------------------------ */
/* menu principal                                                      */
/* ------------------------------------------------------------------ */
typedef struct {
	int card_x, card_y, card_w, card_h;
	int row_x, row_y[PAC_MENU_ITEMS], row_w, row_h, row_gap;
	int brand_y, options_y, footer_y;
} menu_layout_t;

static void menu_layout(pac_game_t *g, menu_layout_t *L)
{
	rview_t v;
	int pad, brand_h, footer_h, options_top, options_bottom, row_h, gap;

	view_get(g, &v);
	pad = (v.ch >= 480) ? SP_6 : SP_4;
	L->card_w = 560;
	if (L->card_w > v.cw - 2 * SP_6)
		L->card_w = v.cw - 2 * SP_6;
	if (L->card_w < 240)
		L->card_w = 240;
	L->card_x = v.ox + (v.cw - L->card_w) / 2;

	brand_h = pac_text_height(PAC_TEXT_DISPLAY) + SP_2 +
	          pac_text_height(PAC_TEXT_CAPTION);
	footer_h = pac_text_height(PAC_TEXT_LABEL) + SP_2 + pac_text_height(PAC_TEXT_CAPTION);

	L->card_h = 2 * pad + brand_h + SP_4 + 16 + SP_4 + PAC_MENU_ITEMS * 34 +
	            (PAC_MENU_ITEMS - 1) * SP_1 + SP_4 + 1 + SP_3 + footer_h;
	if (L->card_h > v.ch - 2 * SP_4)
		L->card_h = v.ch - 2 * SP_4;
	if (L->card_h < 260)
		L->card_h = 260;
	L->card_y = v.oy + (v.ch - L->card_h) / 2;

	L->brand_y = L->card_y + pad;
	options_top = L->brand_y + brand_h + SP_5;
	L->footer_y = L->card_y + L->card_h - pad - footer_h;
	options_bottom = L->footer_y - SP_3 - 1 - SP_3;

	/* fila de sprites arcade si cabe comodamente */
	if (options_bottom - options_top > 4 * 28 + 3 * SP_1 + 16 + SP_4) {
		options_top += 16 + SP_4;
	}
	row_h = (options_bottom - options_top - (PAC_MENU_ITEMS - 1) * SP_1) /
	        PAC_MENU_ITEMS;
	gap = SP_1;
	if (row_h < 22) {
		row_h = 22;
		gap = 0;
	}
	if (row_h > 32)
		row_h = 32;
	L->row_h = row_h;
	L->row_gap = gap;
	L->options_y = options_top;
	L->row_x = L->card_x + SP_6;
	L->row_w = L->card_w - 2 * SP_6;
	{
		int i;
		for (i = 0; i < PAC_MENU_ITEMS; i++)
			L->row_y[i] = L->options_y + i * (row_h + gap);
	}
}

static void draw_attract(pac_game_t *g, const rview_t *v)
{
	char buf[24];
	int cx = v->ox + v->cw / 2;
	int y;

	bg_fill(v);
	pac_ui_card(v->ox + v->cw / 2 - 280, v->oy + v->ch / 2 - 210, 560, 420);

	y = v->oy + v->ch / 2 - 170;
	pac_arcade_text_draw_center(cx, y, PAC_APP_NAME, C_TEXT, 2);
	y += pac_text_height(PAC_TEXT_DISPLAY) + SP_2;
	pac_text_draw_center(PAC_TEXT_CAPTION, cx, y, "ARCADE ORIGINAL PARA SEREOS", C_DIM);
	y += pac_text_height(PAC_TEXT_CAPTION) + SP_4;

	pac_arcade_text_draw_center(cx, y, "CHARACTER / NICKNAME", C_DIM, 1);
	y += pac_text_height(PAC_TEXT_LABEL) + SP_2;
	{
		static const char *names[4] = { "SHADOW  BLINKY", "SPEEDY  PINKY",
		                                "BASHFUL  INKY", "POKEY  CLYDE" };
		uint32_t cols[4];
		cols[0] = C_RED; cols[1] = C_PINK; cols[2] = C_CYAN; cols[3] = C_ORANGE;
		int i;
		for (i = 0; i < 4; i++) {
			pac_sprite(cx - 28, y, pacasset_ghost_frame[i][(g->anim_ms / 250 + i) & 1],
			           PAC_SPRITE_SIZE, PAC_SPRITE_SIZE);
			pac_text_draw(PAC_TEXT_CAPTION, cx, y, names[i], cols[i]);
			y += PAC_SPRITE_SIZE + SP_1;
		}
	}
	pac_arcade_text_draw_center(cx, y + SP_2, "HIGH SCORE", C_DIM, 1);
	utoi_small(buf, g->high_score);
	pac_text_draw_center(PAC_TEXT_MONO, cx, y + SP_2 + pac_text_height(PAC_TEXT_LABEL),
	                 buf, C_AMBER);
	y += SP_2 + pac_text_height(PAC_TEXT_LABEL) + pac_text_height(PAC_TEXT_MONO) + SP_4;
	pac_arcade_text_draw_center(cx, y, "PRESS START", C_AMBER, 2);
	pac_text_draw_center(PAC_TEXT_CAPTION, cx, y + 2 * PAC_ARCADEFONT_H + SP_2,
	                 "Enter / Espacio para continuar", C_FAINT);
}

static void draw_settings(pac_game_t *g, const rview_t *v)
{
	static const char *labels[PAC_SETTINGS_ITEMS] = {
		"SONIDO", "PANTALLA COMPLETA"
	};
	int px, py, pw, ph, y, i;
	char buf[16];

	bg_fill(v);
	pw = 420;
	ph = SP_5 + pac_text_height(PAC_TEXT_TITLE) + SP_4 + SP_4 +
	     PAC_SETTINGS_ITEMS * (action_row_height() + SP_2) + SP_3 +
	     pac_text_height(PAC_TEXT_CAPTION) + SP_5;
	px = v->ox + (v->cw - pw) / 2;
	py = v->oy + (v->ch - ph) / 2;
	pac_ui_card(px, py, pw, ph);
	pac_arcade_text_draw_center(px + pw / 2, py + SP_5,
	                            "Configuración", C_TEXT, 2);
	pac_ui_divider(px + SP_6, py + SP_5 + pac_text_height(PAC_TEXT_TITLE) + SP_4,
	           pw - 2 * SP_6);
	y = py + SP_5 + pac_text_height(PAC_TEXT_TITLE) + SP_4 + SP_4;
	for (i = 0; i < PAC_SETTINGS_ITEMS; i++) {
		int on = (i == 0) ? g->sound_on : g->fullscreen;
		if (i == g->settings_sel) {
			pac_fill_round_rect(px + SP_4, y - SP_1, pw - 2 * SP_4,
			                    action_row_height() + SP_1, RADIUS_XS, C_SOFT);
			pac_fill_round_rect(px + SP_4, y - SP_1, 3,
			                    action_row_height() + SP_1, RADIUS_XS, C_ACCENT);
		}
		pac_text_draw(PAC_TEXT_BODY, px + SP_6, y +
		          (action_row_height() - pac_text_height(PAC_TEXT_BODY)) / 2,
		          labels[i], C_TEXT);
		pac_text_draw_right(PAC_TEXT_MONO, px + pw - SP_6,
		                y + (action_row_height() - pac_text_height(PAC_TEXT_MONO)) / 2,
		                on ? "SI" : "NO", on ? C_GREEN : C_DIM);
		y += action_row_height() + SP_2;
	}
	(void)buf;
	pac_text_draw_center(PAC_TEXT_CAPTION, px + pw / 2, y,
	                 "Flechas: elegir   Enter / Izq-Der: cambiar   Esc: volver",
	                 C_FAINT);
}

static void draw_menu(pac_game_t *g, const rview_t *v)
{
	static const char *labels[PAC_MENU_ITEMS] = {
		"Iniciar partida", "Continuar", "Récords", "Instrucciones",
		"Configuración", "Salir al escritorio"
	};
	menu_layout_t L;
	int i;
	int brand_y;
	char buf[24];

	bg_fill(v);
	menu_layout(g, &L);

	pac_ui_card(L.card_x, L.card_y, L.card_w, L.card_h);

	brand_y = L.brand_y;
	pac_arcade_text_draw_center(L.card_x + L.card_w / 2, brand_y,
	                            PAC_APP_NAME, C_TEXT, 2);
	brand_y += pac_text_height(PAC_TEXT_DISPLAY) + SP_2;
	pac_text_draw_center(PAC_TEXT_CAPTION, L.card_x + L.card_w / 2, brand_y,
	                 "ARCADE ORIGINAL PARA SEREOS", C_DIM);

	/* pequena fila de sprites como identidad del juego */
	{
		int sprite_y = L.brand_y + pac_text_height(PAC_TEXT_DISPLAY) + SP_1 +
		               pac_text_height(PAC_TEXT_HEADLINE) + SP_2 +
		               pac_text_height(PAC_TEXT_CAPTION) + SP_4;
		int total = PAC_SPRITE_SIZE + 4 * (PAC_SPRITE_SIZE + SP_1);
		int sx = L.card_x + (L.card_w - total) / 2;
		int mouth = (int)((g->anim_ms / 120) % 3);
		if (sprite_y + PAC_SPRITE_SIZE <= L.options_y - SP_2) {
			pac_sprite(sx, sprite_y, pacasset_pacman_frame[0][mouth],
			                PAC_SPRITE_SIZE, PAC_SPRITE_SIZE);
			for (i = 0; i < 4; i++)
				pac_sprite(sx + PAC_SPRITE_SIZE + SP_1 +
				                i * (PAC_SPRITE_SIZE + SP_1), sprite_y,
				                pacasset_ghost_frame[i][(g->anim_ms / 250 + i) & 1],
				                PAC_SPRITE_SIZE, PAC_SPRITE_SIZE);
		}
	}

	/* opciones: fila seleccionada con accent_soft y barra accent */
	for (i = 0; i < PAC_MENU_ITEMS; i++) {
		int rx = L.row_x;
		int ry = L.row_y[i];
		uint32_t color = (i == g->menu_sel) ? C_TEXT : C_DIM;
		if (i == g->menu_sel) {
			pac_fill_round_rect(rx, ry, L.row_w, L.row_h, RADIUS_SM, C_SOFT);
			pac_fill_round_rect(rx, ry, 3, L.row_h, RADIUS_XS, C_ACCENT);
		}
		pac_arcade_text_draw(rx + SP_5,
		          ry + (L.row_h - PAC_ARCADEFONT_H) / 2, labels[i], color, 1);
		if (!pac_menu_item_enabled(g, i))
			pac_text_draw_right(PAC_TEXT_CAPTION, rx + L.row_w - SP_3,
			                ry + (L.row_h - pac_text_height(PAC_TEXT_CAPTION)) / 2,
			                "sin partida", C_FAINT);
	}

	/* pie: record y ayuda */
	pac_ui_divider(L.card_x + SP_6, L.footer_y, L.card_w - 2 * SP_6);
	{
		int fy = L.footer_y + SP_1;
		pac_text_draw(PAC_TEXT_LABEL, L.card_x + SP_6, fy, "HIGH SCORE", C_DIM);
		utoi_small(buf, g->high_score);
		pac_text_draw_right(PAC_TEXT_MONO, L.card_x + L.card_w - SP_6, fy, buf, C_TEXT);
		fy += pac_text_height(PAC_TEXT_LABEL) + SP_2;
		if (v->cw >= 560) {
			pac_text_draw_center(PAC_TEXT_CAPTION, L.card_x + L.card_w / 2, fy,
			                 "Flechas / WASD: elegir   Enter: confirmar   Esc: salir",
			                 C_FAINT);
		} else {
			pac_text_draw_center(PAC_TEXT_CAPTION, L.card_x + L.card_w / 2, fy,
			                 "Flechas: elegir   Enter: confirmar", C_FAINT);
		}
	}
}

/* ------------------------------------------------------------------ */
/* instrucciones                                                       */
/* ------------------------------------------------------------------ */
typedef struct {
	const char *key;
	const char *label;
} control_row_t;

static void draw_instructions(pac_game_t *g, const rview_t *v)
{
	static const control_row_t controls[] = {
		{ "Flechas / WASD", "Mover a Pac-Man" },
		{ "Enter", "Confirmar en los menús" },
		{ "Esc", "Pausar / continuar" },
		{ "R", "Reiniciar la partida" },
		{ "Q", "Volver al título (en pausa)" },
	};
	static const char *rules[] = {
		"Come todos los dots y las cuatro power pills",
		"para completar el laberinto.",
		"Con una power pill los fantasmas se vuelven",
		"comestibles: 200, 400, 800 y 1600 puntos.",
		"Cada fruta da puntos extra y aparece dos veces",
		"por nivel. Hay una vida extra a los 10.000 puntos.",
		"Esc en el título vuelve al escritorio.",
	};
	int px, py, pw, ph;
	int pad, y, header_h;
	int cols = 1;
	int i;
	int content_h, footer_h;

	(void)g;
	bg_fill(v);
	pw = v->cw - 2 * SP_5;
	if (pw > 720)
		pw = 720;
	if (pw < 300)
		pw = 300;
	cols = (pw >= 600) ? 2 : 1;
	header_h = SP_5 + pac_text_height(PAC_TEXT_TITLE) + SP_1 +
	           pac_text_height(PAC_TEXT_CAPTION) + SP_4;
	footer_h = SP_4 + pac_text_height(PAC_TEXT_BODY) + SP_4;
	if (cols == 2) {
		int rows_h = 5 * (action_row_height() + SP_1);
		int rules_h = 7 * (pac_text_height(PAC_TEXT_SMALL) + SP_1);
		content_h = pac_text_height(PAC_TEXT_LABEL) + SP_3 +
		            (rows_h > rules_h ? rows_h : rules_h);
	} else {
		content_h = pac_text_height(PAC_TEXT_LABEL) + SP_3 +
		            5 * (action_row_height() + SP_1) + SP_2 +
		            pac_text_height(PAC_TEXT_LABEL) + SP_2 +
		            7 * (pac_text_height(PAC_TEXT_SMALL) + SP_1);
	}
	ph = header_h + SP_4 + content_h + SP_4 + footer_h;
	if (ph > v->ch - 2 * SP_4)
		ph = v->ch - 2 * SP_4;
	if (ph < 240)
		ph = 240;
	px = v->ox + (v->cw - pw) / 2;
	py = v->oy + (v->ch - ph) / 2;
	pac_ui_card(px, py, pw, ph);

	pad = SP_6;
	pac_text_draw(PAC_TEXT_TITLE, px + pad, py + SP_5, "Cómo jugar", C_TEXT);
	pac_text_draw(PAC_TEXT_CAPTION, px + pad, py + SP_5 + pac_text_height(PAC_TEXT_TITLE) + SP_1,
	          "Controles y reglas de PAC-MAN SereOS", C_DIM);
	header_h = SP_5 + pac_text_height(PAC_TEXT_TITLE) + SP_1 +
	           pac_text_height(PAC_TEXT_CAPTION) + SP_4;
	pac_ui_divider(px + pad, py + header_h, pw - 2 * pad);

	if (cols == 2) {
		int col_w = (pw - 3 * pad) / 2;
		int left_x = px + pad;
		int right_x = px + 2 * pad + col_w;
		int top = py + header_h + SP_4;

		pac_text_draw(PAC_TEXT_LABEL, left_x, top, "CONTROLES", C_DIM);
		y = top + pac_text_height(PAC_TEXT_LABEL) + SP_3;
		for (i = 0; i < (int)(sizeof(controls) / sizeof(controls[0])); i++) {
			action_row(left_x, y, col_w, controls[i].key, controls[i].label);
			y += action_row_height() + SP_1;
		}

		pac_text_draw(PAC_TEXT_LABEL, right_x, top, "OBJETIVO", C_DIM);
		y = top + pac_text_height(PAC_TEXT_LABEL) + SP_3;
		for (i = 0; i < (int)(sizeof(rules) / sizeof(rules[0])); i++) {
			pac_text_draw(PAC_TEXT_SMALL, right_x, y, rules[i], C_DIM);
			y += pac_text_height(PAC_TEXT_SMALL) + SP_1;
		}
	} else {
		int top = py + header_h + SP_4;
		pac_text_draw(PAC_TEXT_LABEL, px + pad, top, "CONTROLES", C_DIM);
		y = top + pac_text_height(PAC_TEXT_LABEL) + SP_3;
		for (i = 0; i < (int)(sizeof(controls) / sizeof(controls[0])); i++) {
			action_row(px + pad, y, pw - 2 * pad, controls[i].key,
			           controls[i].label);
			y += action_row_height() + SP_1;
		}
		y += SP_2;
		pac_text_draw(PAC_TEXT_LABEL, px + pad, y, "OBJETIVO", C_DIM);
		y += pac_text_height(PAC_TEXT_LABEL) + SP_2;
		for (i = 0; i < (int)(sizeof(rules) / sizeof(rules[0])); i++) {
			pac_text_draw(PAC_TEXT_SMALL, px + pad, y, rules[i], C_DIM);
			y += pac_text_height(PAC_TEXT_SMALL) + SP_1;
		}
	}

	pac_ui_divider(px + pad, py + ph - SP_6 - pac_text_height(PAC_TEXT_CAPTION) - SP_2,
	           pw - 2 * pad);
	{
		int fy = py + ph - SP_6 - pac_text_height(PAC_TEXT_CAPTION);
		int kw = key_badge(px + pad, fy - 4, "Enter / Esc");
		pac_text_draw(PAC_TEXT_BODY, px + pad + kw + SP_3,
		          fy + (pac_text_height(PAC_TEXT_CAPTION) - pac_text_height(PAC_TEXT_BODY)) / 2,
		          "Volver", C_TEXT);
	}
}

/* ------------------------------------------------------------------ */
/* record                                                              */
/* ------------------------------------------------------------------ */
static void draw_record_screen(pac_game_t *g, const rview_t *v)
{
	int px, py, pw, ph, y;
	char buf[24];

	bg_fill(v);
	pw = 440;
	if (pw > v->cw - 2 * SP_5)
		pw = v->cw - 2 * SP_5;
	if (pw < 280)
		pw = 280;
	ph = SP_5 + pac_text_height(PAC_TEXT_TITLE) + SP_4 + SP_4 +
	     pac_text_height(PAC_TEXT_LABEL) + SP_2 + pac_text_height(PAC_TEXT_HEADLINE) + SP_4 +
	     pac_text_height(PAC_TEXT_CAPTION) + SP_4 + 1 + SP_4 +
	     pac_text_height(PAC_TEXT_BODY) + SP_5;
	if (ph > v->ch - 2 * SP_4)
		ph = v->ch - 2 * SP_4;
	if (ph < 200)
		ph = 200;
	px = v->ox + (v->cw - pw) / 2;
	py = v->oy + (v->ch - ph) / 2;
	pac_ui_card(px, py, pw, ph);

	pac_text_draw_center(PAC_TEXT_TITLE, px + pw / 2, py + SP_5, "Récord", C_TEXT);
	pac_ui_divider(px + SP_6, py + SP_5 + pac_text_height(PAC_TEXT_TITLE) + SP_4,
	           pw - 2 * SP_6);

	y = py + SP_5 + pac_text_height(PAC_TEXT_TITLE) + SP_4 + SP_4;
	pac_text_draw_center(PAC_TEXT_LABEL, px + pw / 2, y, "MEJOR PUNTUACIÓN", C_DIM);
	y += pac_text_height(PAC_TEXT_LABEL) + SP_2;
	utoi_small(buf, g->high_score);
	pac_text_draw_center(PAC_TEXT_HEADLINE, px + pw / 2, y, buf, C_AMBER);
	y += pac_text_height(PAC_TEXT_HEADLINE) + SP_4;
	pac_text_draw_center(PAC_TEXT_CAPTION, px + pw / 2, y,
	                 g->high_score > 0 ? "Se guarda automáticamente en SereOS"
	                                   : "Aún no hay récord: ¡a jugar!",
	                 C_DIM);

	{
		int fy = py + ph - SP_5 - pac_text_height(PAC_TEXT_CAPTION);
		int kw;
		pac_ui_divider(px + SP_6, fy - SP_4, pw - 2 * SP_6);
		kw = key_badge(px + SP_6, fy - 4, "Enter / Esc");
		pac_text_draw(PAC_TEXT_BODY, px + SP_6 + kw + SP_3,
		          fy + (pac_text_height(PAC_TEXT_CAPTION) - pac_text_height(PAC_TEXT_BODY)) / 2,
		          "Volver", C_TEXT);
	}
}

/* ------------------------------------------------------------------ */
/* overlays                                                            */
/* ------------------------------------------------------------------ */
static void dim_game(const rview_t *v, uint8_t alpha)
{
	pac_fill_rect_alpha(v->ox, v->oy, v->cw, v->ch, C_BG, alpha);
}

static void draw_pause_overlay(pac_game_t *g, const rview_t *v)
{
	int px, py, pw, ph, y, i;
	int kw;

	(void)g;
	dim_game(v, 170);
	pw = 420;
	ph = SP_5 + pac_text_height(PAC_TEXT_TITLE) + SP_4 + SP_4 +
	     PAC_PAUSE_ITEMS * (action_row_height() + SP_2) + SP_3 +
	     pac_text_height(PAC_TEXT_CAPTION) + SP_5;
	if (pw > v->cw - 2 * SP_4)
		pw = v->cw - 2 * SP_4;
	if (ph > v->ch - 2 * SP_4)
		ph = v->ch - 2 * SP_4;
	if (pw < 260)
		pw = 260;
	if (ph < 180)
		ph = 180;
	px = v->ox + (v->cw - pw) / 2;
	py = v->oy + (v->ch - ph) / 2;
	pac_ui_card(px, py, pw, ph);

	static const char *opts[PAC_PAUSE_ITEMS] = {
		"Continuar", "Reiniciar partida", "Configuración",
		"Menú principal", "Salir al escritorio"
	};
	static const char *keys[PAC_PAUSE_ITEMS] = {
		"Enter", "R", "Enter", "Enter", "Esc"
	};
	pac_arcade_text_draw_center(px + pw / 2, py + SP_5, "Pausa", C_TEXT, 2);
	pac_ui_divider(px + SP_6, py + SP_5 + pac_text_height(PAC_TEXT_TITLE) + SP_4,
	           pw - 2 * SP_6);
	y = py + SP_5 + pac_text_height(PAC_TEXT_TITLE) + SP_4 + SP_4;
	for (i = 0; i < PAC_PAUSE_ITEMS; i++) {
		if (i == g->pause_sel) {
			pac_fill_round_rect(px + SP_4, y - SP_1, pw - 2 * SP_4,
			                    action_row_height() + SP_1, RADIUS_XS, C_SOFT);
			pac_fill_round_rect(px + SP_4, y - SP_1, 3,
			                    action_row_height() + SP_1, RADIUS_XS, C_ACCENT);
		}
		action_row(px + SP_6, y, pw - 2 * SP_6, keys[i], opts[i]);
		y += action_row_height() + SP_2;
	}
	y += SP_1;
	pac_text_draw_center(PAC_TEXT_CAPTION, px + pw / 2, y,
	                 "Flechas: elegir   Enter: confirmar   Esc: continuar",
	                 C_FAINT);
	(void)kw;
}

static void draw_gameover(pac_game_t *g, const rview_t *v)
{
	int px, py, pw, ph, y;
	char buf[24];

	dim_game(v, 180);
	pw = 480;
	ph = SP_5 + pac_text_height(PAC_TEXT_TITLE) + SP_4 + SP_4 +
	     3 * (pac_text_height(PAC_TEXT_LABEL) + SP_3) + SP_4 + 1 + SP_4 +
	     PAC_OVER_ITEMS * (action_row_height() + SP_2) + SP_5;
	if (pw > v->cw - 2 * SP_4)
		pw = v->cw - 2 * SP_4;
	if (ph > v->ch - 2 * SP_4)
		ph = v->ch - 2 * SP_4;
	if (pw < 280)
		pw = 280;
	if (ph < 230)
		ph = 230;
	px = v->ox + (v->cw - pw) / 2;
	py = v->oy + (v->ch - ph) / 2;
	pac_ui_card(px, py, pw, ph);

	pac_arcade_text_draw_center(px + pw / 2, py + SP_5, "Game Over", C_RED, 2);
	pac_ui_divider(px + SP_6, py + SP_5 + pac_text_height(PAC_TEXT_TITLE) + SP_4,
	           pw - 2 * SP_6);
	y = py + SP_5 + pac_text_height(PAC_TEXT_TITLE) + SP_4 + SP_4;
	utoi_small(buf, g->score);
	kv_row(px + SP_6, y, pw - 2 * SP_6, "PUNTUACIÓN", buf, PAC_TEXT_MONO, C_TEXT);
	y += pac_text_height(PAC_TEXT_LABEL) + SP_3;
	utoi_small(buf, g->high_score);
	kv_row(px + SP_6, y, pw - 2 * SP_6, "RÉCORD", buf, PAC_TEXT_MONO, C_AMBER);
	y += pac_text_height(PAC_TEXT_LABEL) + SP_3;
	utoi_small(buf, g->level);
	kv_row(px + SP_6, y, pw - 2 * SP_6, "NIVEL", buf, PAC_TEXT_MONO, C_DIM);
	y += pac_text_height(PAC_TEXT_LABEL) + SP_4;
	pac_ui_divider(px + SP_6, y, pw - 2 * SP_6);
	y += SP_4;
	{
		static const char *opts[PAC_OVER_ITEMS] = {
			"Reintentar", "Menú principal", "Salir al escritorio"
		};
		int i;
		for (i = 0; i < PAC_OVER_ITEMS; i++) {
			if (i == g->over_sel) {
				pac_fill_round_rect(px + SP_4, y - SP_1, pw - 2 * SP_4,
				                    action_row_height() + SP_1, RADIUS_XS, C_SOFT);
				pac_fill_round_rect(px + SP_4, y - SP_1, 3,
				                    action_row_height() + SP_1, RADIUS_XS, C_ACCENT);
			}
			action_row(px + SP_6, y, pw - 2 * SP_6,
			           i == 0 ? "Enter" : "Enter", opts[i]);
			y += action_row_height() + SP_2;
		}
	}
}

static void draw_level_clear(pac_game_t *g, const rview_t *v)
{
	int px, py, pw, ph, y;
	char buf[24];

	dim_game(v, 150);
	pw = 460;
	ph = SP_5 + pac_text_height(PAC_TEXT_TITLE) + SP_4 + SP_4 +
	     2 * (pac_text_height(PAC_TEXT_LABEL) + SP_3) + SP_4 +
	     pac_text_height(PAC_TEXT_CAPTION) + SP_5;
	if (pw > v->cw - 2 * SP_4)
		pw = v->cw - 2 * SP_4;
	if (ph > v->ch - 2 * SP_4)
		ph = v->ch - 2 * SP_4;
	if (pw < 280)
		pw = 280;
	if (ph < 210)
		ph = 210;
	px = v->ox + (v->cw - pw) / 2;
	py = v->oy + (v->ch - ph) / 2;
	pac_ui_card(px, py, pw, ph);

	pac_arcade_text_draw_center(px + pw / 2, py + SP_5,
	                            "Nivel completado", C_GREEN, 2);
	pac_ui_divider(px + SP_6, py + SP_5 + pac_text_height(PAC_TEXT_TITLE) + SP_4,
	           pw - 2 * SP_6);
	y = py + SP_5 + pac_text_height(PAC_TEXT_TITLE) + SP_4 + SP_4;
	utoi_small(buf, g->level);
	kv_row(px + SP_6, y, pw - 2 * SP_6, "NIVEL", buf, PAC_TEXT_MONO, C_TEXT);
	y += pac_text_height(PAC_TEXT_LABEL) + SP_3;
	utoi_small(buf, g->score);
	kv_row(px + SP_6, y, pw - 2 * SP_6, "PUNTUACIÓN", buf, PAC_TEXT_MONO, C_TEXT);
	y += pac_text_height(PAC_TEXT_LABEL) + SP_4;
	pac_text_draw_center(PAC_TEXT_CAPTION, px + pw / 2, y,
	                 "Siguiente nivel: los dots vuelven a aparecer", C_DIM);
}

/* ------------------------------------------------------------------ */
/* entrada principal                                                   */
/* ------------------------------------------------------------------ */
void pac_render_draw(pac_game_t *g)
{
	rview_t v;

	if (!g || g->viewport.w <= 0 || g->viewport.h <= 0)
		return;
	view_get(g, &v);
	bg_fill(&v);

	switch (g->state) {
	case PAC_STATE_ATTRACT:
		draw_attract(g, &v);
		break;
	case PAC_STATE_MENU:
		draw_menu(g, &v);
		break;
	case PAC_STATE_SETTINGS:
		draw_settings(g, &v);
		break;
	case PAC_STATE_INSTRUCTIONS:
		draw_instructions(g, &v);
		break;
	case PAC_STATE_RECORD:
		draw_record_screen(g, &v);
		break;
	case PAC_STATE_PLAYING:
		draw_game_field(g, &v);
		if (v.side) {
			draw_hud_panels(g, &v);
		} else {
			draw_hud_compact(g, &v);
		}
		break;
	case PAC_STATE_PAUSED:
		draw_game_field(g, &v);
		if (v.side)
			draw_hud_panels(g, &v);
		draw_pause_overlay(g, &v);
		break;
	case PAC_STATE_GAMEOVER:
		draw_game_field(g, &v);
		if (v.side)
			draw_hud_panels(g, &v);
		draw_gameover(g, &v);
		break;
	case PAC_STATE_LEVEL_CLEAR:
		draw_game_field(g, &v);
		if (v.side)
			draw_hud_panels(g, &v);
		draw_level_clear(g, &v);
		break;
	default:
		break;
	}

	pac_mark_dirty(v.ox, v.oy, v.cw, v.ch);
}

int pac_render_menu_hit(pac_game_t *g, int sx, int sy)
{
	menu_layout_t L;
	int i;
	if (!g || g->viewport.w <= 0 || g->viewport.h <= 0)
		return -1;
	menu_layout(g, &L);
	for (i = 0; i < PAC_MENU_ITEMS; i++) {
		int ry = L.row_y[i];
		if (sx >= L.row_x && sx < L.row_x + L.row_w &&
		    sy >= ry && sy < ry + L.row_h)
			return i;
	}
	return -1;
}
