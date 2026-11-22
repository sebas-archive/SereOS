/* apps/game/game_maze.c - laberinto real de Paku-Paku para PAC-MAN SereOS
 *
 * Mapa de 28x31 extraido de cMazeBuilder.cls (docs/reference/maze.c):
 *   O/o pared, p puerta, P casa, . dot, + power pill, T tunel, X exterior.
 * Se conserva la geometria exacta (240 dots + 4 power). El laberinto se
 * pre-renderiza una sola vez en un buffer 448x496 RGB32 y luego se copia con
 * gfx_blit_rgb() cada frame, evitando miles de primitivas por frame.
 */
#include <stdint.h>
#include "string.h"
#include "pac_game.h"
#include "game_maze.h"

/* Mapa ASCII original (fila 0 arriba, columna 0 izquierda). */
static const char *const maze_ascii[PAC_ROWS] = {
	"oooooooooooooooooooooooooooo",
	"o............OO............o",
	"o.OOOO.OOOOO.OO.OOOOO.OOOO.o",
	"o+OOOO.OOOOO.OO.OOOOO.OOOO+o",
	"o.OOOO.OOOOO.OO.OOOOO.OOOO.o",
	"o..........................o",
	"o.OOOO.OO.OOOOOOOO.OO.OOOO.o",
	"o.OOOO.OO.OOOOOOOO.OO.OOOO.o",
	"o......OO....OO....OO......o",
	"oooooo.OOOOO OO OOOOO.oooooo",
	"XXXXXo.OOOOO OO OOOOO.oXXXXX",
	"XXXXXo.OO          OO.oXXXXX",
	"XXXXXo.OO oooppooo OO.oXXXXX",
	"oooooo.OO oPPPPPPo OO.oooooo",
	"TTTTTT.   oPPPPPPo   .TTTTTT",
	"oooooo.OO oPPPPPPo OO.oooooo",
	"XXXXXo.OO oooooooo OO.oXXXXX",
	"XXXXXo.OO          OO.oXXXXX",
	"XXXXXo.OO OOOOOOOO OO.oXXXXX",
	"oooooo.OO OOOOOOOO OO.oooooo",
	"o............OO............o",
	"o.OOOO.OOOOO.OO.OOOOO.OOOO.o",
	"o.OOOO.OOOOO.OO.OOOOO.OOOO.o",
	"o+..OO.......  .......OO..+o",
	"oOO.OO.OO.OOOOOOOO.OO.OO.OOo",
	"oOO.OO.OO.OOOOOOOO.OO.OO.OOo",
	"o......OO....OO....OO......o",
	"o.OOOOOOOOOO.OO.OOOOOOOOOO.o",
	"o.OOOOOOOOOO.OO.OOOOOOOOOO.o",
	"o..........................o",
	"oooooooooooooooooooooooooooo",
};

/* fondo pre-renderizado (448x496 px, 0x00RRGGBB) */
static uint32_t maze_bg[PAC_MAZE_W * PAC_MAZE_H];
static int maze_bg_ready;
static int maze_dot_total;
static int maze_power_total;

/* ------------------------------------------------------------------ */
/* construccion de la tabla base                                       */
/* ------------------------------------------------------------------ */
static uint8_t classify(int col, int row)
{
	char c;

	if (row < 0 || row >= PAC_ROWS || col < 0 || col >= PAC_COLS)
		return PAC_TILE_VOID;
	c = maze_ascii[row][col];
	if (c == 'O' || c == 'o' || c == 'X')
		return PAC_TILE_WALL;
	if (c == 'P')
		return PAC_TILE_PEN;
	if (c == 'p')
		return PAC_TILE_GATE;
	if (c == 'T')
		return PAC_TILE_TUNNEL;
	if (c == '.')
		return PAC_TILE_DOT;
	if (c == '+')
		return PAC_TILE_POWER;
	return PAC_TILE_PATH;
}

static void build_base(pac_game_t *g)
{
	int row, col;

	maze_dot_total = 0;
	maze_power_total = 0;
	for (row = 0; row < PAC_ROWS; row++) {
		for (col = 0; col < PAC_COLS; col++) {
			uint8_t t = classify(col, row);
			g->maze.base[row * PAC_COLS + col] = t;
			if (t == PAC_TILE_DOT)
				maze_dot_total++;
			else if (t == PAC_TILE_POWER)
				maze_power_total++;
		}
	}
}

/* ------------------------------------------------------------------ */
/* fondo pre-renderizado                                               */
/* ------------------------------------------------------------------ */
#define BG_DEEP    0x00071226u   /* fondo detrás del laberinto */
#define BG_VOID    0x00101E38u   /* zonas exteriores X: superficie navy */
#define BG_ALLEY   0x000B1830u   /* pasillos */
#define WALL_FILL  0x001C3763u   /* cuerpo de pared azul */
#define WALL_EDGE  0x00448CF0u
#define WALL_HI    0x0078BCFFu
#define PEN_FILL   0x001B1230u
#define PEN_EDGE   0x00F06AA8u
#define GATE_PINK  0x00FF7AB8u
#define FRAME_COL  0x003060B0u

static void bg_rect(int x, int y, int w, int h, uint32_t c)
{
	int i, j;
	for (j = 0; j < h; j++) {
		int yy = y + j;
		if (yy < 0 || yy >= PAC_MAZE_H)
			continue;
		for (i = 0; i < w; i++) {
			int xx = x + i;
			if (xx < 0 || xx >= PAC_MAZE_W)
				continue;
			maze_bg[yy * PAC_MAZE_W + xx] = c;
		}
	}
}

static void bg_hline(int x, int y, int w, uint32_t c) { bg_rect(x, y, w, 1, c); }

static int ascii_is_wall(int col, int row)
{
	char c;
	if (row < 0 || row >= PAC_ROWS || col < 0 || col >= PAC_COLS)
		return 0;
	c = maze_ascii[row][col];
	return (c == 'O' || c == 'o' || c == 'X');
}

static int ascii_is_pen(int col, int row)
{
	if (row < 0 || row >= PAC_ROWS || col < 0 || col >= PAC_COLS)
		return 0;
	return maze_ascii[row][col] == 'P';
}

static void build_background(void)
{
	int row, col;

	if (maze_bg_ready)
		return;

	/* fondo general */
	bg_rect(0, 0, PAC_MAZE_W, PAC_MAZE_H, BG_DEEP);

	for (row = 0; row < PAC_ROWS; row++) {
		for (col = 0; col < PAC_COLS; col++) {
			int x = col * PAC_TILE;
			int y = row * PAC_TILE;
			char c = maze_ascii[row][col];

			if (c == 'X') {
				/* zona exterior: superficie navy, nunca negro puro */
				bg_rect(x, y, PAC_TILE, PAC_TILE, BG_VOID);
				continue;
			}
			if (c == 'O' || c == 'o') {
				bg_rect(x, y, PAC_TILE, PAC_TILE, WALL_FILL);
				/* contorno azul en los lados que dan a zona transitable */
				if (!ascii_is_wall(col, row - 1)) {
					bg_rect(x, y, PAC_TILE, 2, WALL_EDGE);
					bg_hline(x + 1, y, PAC_TILE - 2, WALL_HI);
				}
				if (!ascii_is_wall(col, row + 1))
					bg_rect(x, y + PAC_TILE - 2, PAC_TILE, 2, WALL_EDGE);
				if (!ascii_is_wall(col - 1, row))
					bg_rect(x, y, 2, PAC_TILE, WALL_EDGE);
				if (!ascii_is_wall(col + 1, row))
					bg_rect(x + PAC_TILE - 2, y, 2, PAC_TILE, WALL_EDGE);
				/* brillo interior sutil */
				bg_rect(x + 4, y + 4, PAC_TILE - 8, 2, 0x00193A6Cu);
			} else if (c == 'P') {
				bg_rect(x, y, PAC_TILE, PAC_TILE, PEN_FILL);
				if (!ascii_is_pen(col, row - 1))
					bg_rect(x, y, PAC_TILE, 2, PEN_EDGE);
				if (!ascii_is_pen(col, row + 1))
					bg_rect(x, y + PAC_TILE - 2, PAC_TILE, 2, PEN_EDGE);
				if (!ascii_is_pen(col - 1, row))
					bg_rect(x, y, 2, PAC_TILE, PEN_EDGE);
				if (!ascii_is_pen(col + 1, row))
					bg_rect(x + PAC_TILE - 2, y, 2, PAC_TILE, PEN_EDGE);
			} else if (c == 'p') {
				/* puerta de la casa: barra rosa */
				bg_rect(x, y + 5, PAC_TILE, 6, GATE_PINK);
				bg_rect(x, y + 7, PAC_TILE, 2, 0x00FFD0E8u);
			} else {
				/* pasillo: fondo de calle */
				bg_rect(x, y, PAC_TILE, PAC_TILE, BG_ALLEY);
			}
		}
	}

	/* marco exterior del laberinto */
	bg_rect(0, 0, PAC_MAZE_W, 2, FRAME_COL);
	bg_rect(0, PAC_MAZE_H - 2, PAC_MAZE_W, 2, FRAME_COL);
	bg_rect(0, 0, 2, PAC_MAZE_H, FRAME_COL);
	bg_rect(PAC_MAZE_W - 2, 0, 2, PAC_MAZE_H, FRAME_COL);

	maze_bg_ready = 1;
}

/* ------------------------------------------------------------------ */
/* API publica                                                         */
/* ------------------------------------------------------------------ */
void pac_maze_init(pac_game_t *g)
{
	/* base vive dentro de pac_game_t (una por open): se reconstruye SIEMPRE.
	 * El fondo pre-renderizado si es un buffer estatico compartido porque no
	 * depende del estado de la partida. */
	build_base(g);
	build_background();
	pac_maze_reset(g);
}

void pac_maze_reset(pac_game_t *g)
{
	int n = PAC_COLS * PAC_ROWS;

	memcpy(g->maze.tiles, g->maze.base, (size_t)n);
	g->dots_left = maze_dot_total;
	g->power_left = maze_power_total;
	g->dots_eaten = 0;
}

int pac_maze_tile(const pac_game_t *g, int col, int row)
{
	if (row < 0 || row >= PAC_ROWS || col < 0 || col >= PAC_COLS)
		return PAC_TILE_VOID;
	return g->maze.tiles[row * PAC_COLS + col];
}

int pac_maze_is_pen(int col, int row)
{
	return col >= PAC_PEN_COL0 && col <= PAC_PEN_COL1 &&
	       row >= PAC_PEN_ROW0 && row <= PAC_PEN_ROW1;
}

int pac_maze_is_gate(int col, int row)
{
	return row == PAC_DOOR_ROW && col >= PAC_DOOR_COL0 && col <= PAC_DOOR_COL1;
}

int pac_maze_is_tunnel(const pac_game_t *g, int col, int row)
{
	return pac_maze_tile(g, col, row) == PAC_TILE_TUNNEL;
}

int pac_maze_walkable_pac(const pac_game_t *g, int col, int row)
{
	int t;
	/* los extremos del tunel de la fila 14 son transitables (wrap) */
	if (row == 14 && (col == -1 || col == PAC_COLS))
		return 1;
	if (row < 0 || row >= PAC_ROWS || col < 0 || col >= PAC_COLS)
		return 0;
	t = g->maze.tiles[row * PAC_COLS + col];
	return (t == PAC_TILE_PATH || t == PAC_TILE_DOT ||
	        t == PAC_TILE_POWER || t == PAC_TILE_TUNNEL);
}

int pac_maze_walkable_ghost(const pac_game_t *g, int col, int row)
{
	return pac_maze_walkable_pac(g, col, row);
}

int pac_maze_walkable_eyes(const pac_game_t *g, int col, int row)
{
	int t;
	if (row < 0 || row >= PAC_ROWS || col < 0 || col >= PAC_COLS)
		return 0;
	t = g->maze.tiles[row * PAC_COLS + col];
	if (t == PAC_TILE_PEN || t == PAC_TILE_GATE)
		return 1;
	return pac_maze_walkable_pac(g, col, row);
}

int32_t pac_maze_center_x(int col)
{
	return PAC_SUBPX(col * PAC_TILE) + PAC_SUBPX(PAC_TILE / 2);
}

int32_t pac_maze_center_y(int row)
{
	return PAC_SUBPX(row * PAC_TILE) + PAC_SUBPX(PAC_TILE / 2);
}

int pac_maze_consume(pac_game_t *g, int col, int row)
{
	uint8_t *t;

	if (row < 0 || row >= PAC_ROWS || col < 0 || col >= PAC_COLS)
		return PAC_GAME_EVENT_NONE;
	t = &g->maze.tiles[row * PAC_COLS + col];
	if (*t == PAC_TILE_DOT) {
		*t = PAC_TILE_PATH;
		g->dots_left--;
		g->dots_eaten++;
		return PAC_GAME_EVENT_EAT_DOT;
	}
	if (*t == PAC_TILE_POWER) {
		*t = PAC_TILE_PATH;
		g->power_left--;
		g->dots_eaten++;
		return PAC_GAME_EVENT_EAT_POWER;
	}
	return PAC_GAME_EVENT_NONE;
}

const uint32_t *pac_maze_background(void)
{
	return maze_bg;
}

const char *const *pac_maze_ascii(void)
{
	return maze_ascii;
}

int pac_maze_dot_total(void)  { return maze_dot_total ? maze_dot_total : PAC_DOTS_TOTAL; }
int pac_maze_power_total(void) { return maze_power_total ? maze_power_total : PAC_POWER_TOTAL; }

/* ------------------------------------------------------------------ */
/* BFS para los ojos de los fantasmas (vuelta a la casa)               */
/* ------------------------------------------------------------------ */
#define BFS_NODES (PAC_COLS * PAC_ROWS)

int pac_maze_bfs(int start_col, int start_row, int goal_col, int goal_row,
                 uint8_t *dirs, int max_dirs)
{
	static int16_t queue[BFS_NODES];
	static int16_t parent[BFS_NODES];   /* direccion desde el padre */
	static uint8_t visited[BFS_NODES];
	int head = 0, tail = 0, start, goal, i;

	if (!dirs || max_dirs <= 0)
		return 0;
	if (start_col < 0 || start_col >= PAC_COLS ||
	    start_row < 0 || start_row >= PAC_ROWS)
		return 0;
	if (goal_col < 0 || goal_col >= PAC_COLS ||
	    goal_row < 0 || goal_row >= PAC_ROWS)
		return 0;

	memset(visited, 0, sizeof(visited));
	start = start_row * PAC_COLS + start_col;
	goal = goal_row * PAC_COLS + goal_col;
	parent[start] = PAC_DIR_NONE;
	visited[start] = 1;
	queue[tail++] = (int16_t)start;

	while (head < tail) {
		int node = queue[head++];
		int col = node % PAC_COLS;
		int row = node / PAC_COLS;
		static const pac_dir_t order[4] = {
			PAC_DIR_UP, PAC_DIR_LEFT, PAC_DIR_DOWN, PAC_DIR_RIGHT
		};
		if (node == goal)
			break;
		for (i = 0; i < 4; i++) {
			int nc = col + pac_dir_dx(order[i]);
			int nr = row + pac_dir_dy(order[i]);
			int nn;
			if (nc < 0 || nc >= PAC_COLS || nr < 0 || nr >= PAC_ROWS)
				continue;
			nn = nr * PAC_COLS + nc;
			if (visited[nn])
				continue;
			/* transitabilidad para ojos: camino, casa y puerta */
			{
				uint8_t tt = (uint8_t)(maze_ascii[nr][nc] == '.' ? 1 : 0);
				char c = maze_ascii[nr][nc];
				int walk = (c == '.' || c == '+' || c == ' ' || c == 'T' ||
				            c == 'P' || c == 'p');
				(void)tt;
				if (!walk)
					continue;
			}
			visited[nn] = 1;
			parent[nn] = (int16_t)order[i];
			queue[tail++] = (int16_t)nn;
		}
	}

	if (!visited[goal])
		return 0;

	/* reconstruir desde el objetivo hacia el inicio */
	{
		uint8_t rev[PAC_COLS * PAC_ROWS + 4];
		int len = 0, node = goal;
		while (node != start && len < max_dirs && len < BFS_NODES) {
			rev[len++] = (uint8_t)parent[node];
			switch ((pac_dir_t)parent[node]) {
			case PAC_DIR_UP:    node += PAC_COLS; break;
			case PAC_DIR_DOWN:  node -= PAC_COLS; break;
			case PAC_DIR_LEFT:  node += 1; break;
			case PAC_DIR_RIGHT: node -= 1; break;
			default: len = 0; node = start; break;
			}
		}
		for (i = 0; i < len; i++)
			dirs[i] = rev[len - 1 - i];
		return len;
	}
}
