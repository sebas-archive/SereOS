/* apps/game/game_ai.c - IA de los cuatro fantasmas de PAC-MAN SereOS
 *
 * Personalidades (Pac-Man Dossier / cGhost.cls):
 *   Blinky (rojo)   -> persigue directamente a Pac-Man; Cruise Elroy.
 *   Pinky  (rosa)   -> apunta 4 tiles delante, con el "bug" de mirar arriba.
 *   Inky   (cian)   -> vector 2*(2 delante de Pac-Man - Blinky).
 *   Clyde  (naranja)-> persigue si esta a mas de 8 tiles; si no, a su esquina.
 * Decision en interseccion: direccion valida sin invertir que minimiza la
 * distancia euclidea al tile objetivo (orden UP, LEFT, DOWN, RIGHT).
 */
#include <stdint.h>
#include "string.h"
#include "pac_game.h"
#include "game_maze.h"
#include "game_ai.h"

/* ------------------------------------------------------------------ */
/* tabla de niveles (docs/reference/levels.csv, niveles 1..21)         */
/* ------------------------------------------------------------------ */
typedef struct {
	uint8_t fruit;        /* 0..PAC_FRUIT_COUNT-1 (sprites.h fruit_sprite) */
	int     fruit_value;
	uint8_t pac_pct;
	uint8_t hunter_pct;   /* velocidad de Pac-Man con power pill */
	uint8_t ghost_pct;
	uint8_t fright_s;
	uint8_t phase_set;    /* 0: L1, 1: L2-4, 2: L5+ */
	uint8_t elroy1;
} level_def_t;

static const level_def_t level_defs[21] = {
	/* fruta, valor, pac, hunter, ghost, fright_s, phases, elroy1 */
	{ 0,  100,  80,  90, 75, 6, 0,  20 },
	{ 1,  300,  90,  95, 85, 5, 1,  30 },
	{ 2,  500,  90,  95, 85, 4, 1,  40 },
	{ 3,  700,  90,  95, 85, 3, 1,  40 },
	{ 4, 1000, 100, 100, 95, 2, 2,  40 },
	{ 0,  100, 100, 100, 95, 5, 2,  50 },
	{ 1,  300, 100, 100, 95, 2, 2,  50 },
	{ 2,  500, 100, 100, 95, 2, 2,  50 },
	{ 3,  700, 100, 100, 95, 1, 2,  60 },
	{ 4, 1000, 100, 100, 95, 5, 2,  60 },
	{ 0,  100, 100, 100, 95, 2, 2,  60 },
	{ 1,  300, 100, 100, 95, 1, 2,  80 },
	{ 2,  500, 100, 100, 95, 1, 2,  80 },
	{ 3,  700, 100, 100, 95, 3, 2,  80 },
	{ 4, 1000, 100, 100, 95, 1, 2, 100 },
	{ 0,  100, 100, 100, 95, 1, 2, 100 },
	{ 1,  300, 100, 100, 95, 0, 2, 100 },
	{ 2,  500, 100, 100, 95, 1, 2, 100 },
	{ 3,  700, 100, 100, 95, 0, 2, 120 },
	{ 4, 1000, 100, 100, 95, 0, 2, 120 },
	{ 0,  100,  90, 100, 95, 0, 2, 120 }
};

static const level_def_t *ai_level(const pac_game_t *g)
{
	int i = g->level;
	if (i < 1)
		i = 1;
	if (i > 21)
		i = 21;
	return &level_defs[i - 1];
}

int pac_ai_level_fruit(const pac_game_t *g) { return ai_level(g)->fruit; }
int pac_ai_level_fruit_value(const pac_game_t *g) { return ai_level(g)->fruit_value; }
int pac_ai_level_fright_ms(const pac_game_t *g) { return ai_level(g)->fright_s * 1000; }
int pac_ai_pacman_hunter(const pac_game_t *g) { return g->fright_ms > 0; }

int pac_ai_elroy(const pac_game_t *g)
{
	const level_def_t *l = ai_level(g);
	int elroy1 = l->elroy1;
	int elroy2 = elroy1 / 2;

	if (g->dots_left <= elroy2)
		return 2;
	if (g->dots_left <= elroy1)
		return 1;
	return 0;
}

/* ------------------------------------------------------------------ */
/* velocidades                                                         */
/* ------------------------------------------------------------------ */
int32_t pac_ai_pacman_speed(const pac_game_t *g)
{
	const level_def_t *l = ai_level(g);
	int pct = (g->fright_ms > 0) ? l->hunter_pct : l->pac_pct;

	return PAC_SPEED_BASE_Q * pct / 100;
}

int32_t pac_ai_ghost_speed(const pac_game_t *g, const ghost_t *gh)
{
	const level_def_t *l = ai_level(g);
	int pct;

	if (gh->state == PAC_GHOST_EATEN)
		return PAC_SPEED_BASE_Q * 160 / 100;           /* ojos: 160% */
	if (gh->state == PAC_GHOST_HOME || gh->state == PAC_GHOST_LEAVING ||
	    gh->state == PAC_GHOST_REVIVING)
		return PAC_SPEED_BASE_Q * 40 / 100;            /* casa: 40% */

	if (pac_maze_is_tunnel(g, pac_maze_col(gh->x), pac_maze_row(gh->y)))
		return PAC_SPEED_BASE_Q * ((int)l->ghost_pct + 5) / 2 / 100;

	if (gh->scared) {
		/* Paku-Paku: GhostSpeed/2 + 10 = 47,5/52,5/57,5 % */
		int per_mille = (int)l->ghost_pct * 5 + 100;
		return (int32_t)((int64_t)PAC_SPEED_BASE_Q * per_mille / 1000);
	}

	pct = l->ghost_pct;
	if ((gh - g->ghosts) == PAC_GHOST_BLINKY) {
		int e = pac_ai_elroy(g);
		if (e == 2)
			pct += 10;
		else if (e == 1)
			pct += 5;
	}
	return PAC_SPEED_BASE_Q * pct / 100;
}

/* ------------------------------------------------------------------ */
/* modos scatter/chase                                                 */
/* ------------------------------------------------------------------ */
static void mode_apply(pac_game_t *g)
{
	int chase = g->phase_is_chase[g->mode_phase];
	g->mode = chase ? PAC_PHASE_CHASE : PAC_PHASE_SCATTER;
	g->mode_timer_ms = g->phase_ms[g->mode_phase];
}

static void mode_next(pac_game_t *g)
{
	if (g->mode_phase + 1 >= g->mode_phase_count)
		return;
	g->mode_phase++;
	mode_apply(g);
	if (g->mode_timer_ms < 0) {
		/* fase final permanente (chase) */
		g->mode_timer_ms = -1;
	}
	pac_ai_reverse_all(g);
}

void pac_ai_reverse_all(pac_game_t *g)
{
	int i;
	for (i = 0; i < PAC_GHOST_COUNT; i++) {
		ghost_t *gh = &g->ghosts[i];
		if (gh->state == PAC_GHOST_NORMAL || gh->state == PAC_GHOST_LEAVING) {
			gh->dir = pac_opposite(gh->dir);
			gh->facing = gh->dir;
		}
	}
}

void pac_ai_level_init(pac_game_t *g)
{
	const level_def_t *l = ai_level(g);
	int i;

	g->mode_phase_count = 8;
	g->mode_phase = 0;
	g->fright_ms = 0;
	g->ghost_kill_index = 0;
	g->global_release_ms = 0;

	/* tabla de fases expandida (ms); -1 = fase final permanente */
	if (l->phase_set == 0) {
		static const int16_t chase[8] = { 0, 1, 0, 1, 0, 1, 0, 1 };
		static const int32_t dur[8] = { 7000, 20000, 7000, 20000, 5000,
		                                20000, 5000, -1 };
		for (i = 0; i < 8; i++) {
			g->phase_is_chase[i] = chase[i];
			g->phase_ms[i] = dur[i];
		}
	} else if (l->phase_set == 1) {
		static const int16_t chase[8] = { 0, 1, 0, 1, 0, 1, 0, 1 };
		static const int32_t dur[8] = { 7000, 20000, 7000, 20000, 5000,
		                                1033000, 17, -1 };
		for (i = 0; i < 8; i++) {
			g->phase_is_chase[i] = chase[i];
			g->phase_ms[i] = dur[i];
		}
	} else {
		static const int16_t chase[8] = { 0, 1, 0, 1, 0, 1, 0, 1 };
		static const int32_t dur[8] = { 5000, 20000, 5000, 20000, 5000,
		                                1037000, 17, -1 };
		for (i = 0; i < 8; i++) {
			g->phase_is_chase[i] = chase[i];
			g->phase_ms[i] = dur[i];
		}
	}
	mode_apply(g);

	/* contadores de salida de la casa por nivel (dots comidos) */
	if (g->level <= 1) {
		g->ghosts[PAC_GHOST_PINKY].exit_dots = 0;
		g->ghosts[PAC_GHOST_INKY].exit_dots = 30;
		g->ghosts[PAC_GHOST_CLYDE].exit_dots = 90;
	} else if (g->level == 2) {
		g->ghosts[PAC_GHOST_PINKY].exit_dots = 0;
		g->ghosts[PAC_GHOST_INKY].exit_dots = 0;
		g->ghosts[PAC_GHOST_CLYDE].exit_dots = 50;
	} else {
		g->ghosts[PAC_GHOST_PINKY].exit_dots = 0;
		g->ghosts[PAC_GHOST_INKY].exit_dots = 0;
		g->ghosts[PAC_GHOST_CLYDE].exit_dots = 0;
	}
}

/* Tras morir: NO se reinician las fases scatter/chase (fidelidad Paku-Paku).
 * Solo se limpian frightened, combo y temporizadores de liberacion. */
void pac_ai_after_death(pac_game_t *g)
{
	int i;

	if (!g)
		return;
	g->fright_ms = 0;
	g->ghost_kill_index = 0;
	g->global_release_ms = 0;
	for (i = 0; i < PAC_GHOST_COUNT; i++) {
		g->ghosts[i].scared = 0;
		g->ghosts[i].state_ms = 0;
		if (g->ghosts[i].state == PAC_GHOST_EATEN ||
		    g->ghosts[i].state == PAC_GHOST_REVIVING)
			g->ghosts[i].state = PAC_GHOST_HOME;
	}
}

void pac_ai_frighten(pac_game_t *g)
{
	int i;
	int ms = pac_ai_level_fright_ms(g);

	if (ms <= 0) {
		/* niveles sin frightened: solo se invierte la direccion */
		for (i = 0; i < PAC_GHOST_COUNT; i++) {
			ghost_t *gh = &g->ghosts[i];
			if (gh->state == PAC_GHOST_EATEN || gh->state == PAC_GHOST_REVIVING)
				continue;
			if (gh->state != PAC_GHOST_NORMAL && gh->state != PAC_GHOST_LEAVING)
				continue;
			if (pac_maze_is_pen(pac_maze_col(gh->x), pac_maze_row(gh->y)))
				continue;
			gh->dir = pac_opposite(gh->dir);
			gh->facing = gh->dir;
		}
		return;
	}
	g->fright_ms = ms;
	g->ghost_kill_index = 0;
	for (i = 0; i < PAC_GHOST_COUNT; i++) {
		ghost_t *gh = &g->ghosts[i];
		if (gh->state == PAC_GHOST_EATEN || gh->state == PAC_GHOST_REVIVING)
			continue;
		gh->scared = 1;
		if (gh->state != PAC_GHOST_NORMAL && gh->state != PAC_GHOST_LEAVING)
			continue;
		/* solo invierten los que estan fuera del pen */
		if (pac_maze_is_pen(pac_maze_col(gh->x), pac_maze_row(gh->y)))
			continue;
		gh->dir = pac_opposite(gh->dir);
		gh->facing = gh->dir;
	}
}

void pac_ai_update(pac_game_t *g, int dt_ms)
{
	int i;

	/* liberacion de fantasmas por contador de dots */
	for (i = 0; i < PAC_GHOST_COUNT; i++) {
		ghost_t *gh = &g->ghosts[i];
		if (gh->state == PAC_GHOST_HOME && g->ready_ms <= 0 &&
		    g->dots_eaten >= gh->exit_dots) {
			gh->state = PAC_GHOST_LEAVING;
			gh->state_ms = 0;
		}
	}

	/* si Pac-Man no come, los fantasmas salen igualmente (4 s, 3 s desde L5) */
	if (g->ready_ms <= 0) {
		int interval = (g->level < 5) ? 4000 : 3000;
		g->global_release_ms += dt_ms;
		if (g->global_release_ms >= interval) {
			for (i = 0; i < PAC_GHOST_COUNT; i++) {
				ghost_t *gh = &g->ghosts[i];
				if (gh->state == PAC_GHOST_HOME) {
					gh->state = PAC_GHOST_LEAVING;
					gh->state_ms = 0;
					g->global_release_ms = 0;
					break;
				}
			}
		}
	}

	/* temporizador de frightened */
	if (g->fright_ms > 0) {
		g->fright_ms -= dt_ms;
		if (g->fright_ms <= 0) {
			g->fright_ms = 0;
			for (i = 0; i < PAC_GHOST_COUNT; i++)
				g->ghosts[i].scared = 0;
		}
	}

	/* fases scatter/chase: el reloj se pausa durante el frightened */
	if (g->fright_ms <= 0 && g->ready_ms <= 0 && g->mode_timer_ms > 0) {
		g->mode_timer_ms -= dt_ms;
		if (g->mode_timer_ms <= 0) {
			g->mode_timer_ms = 0;
			mode_next(g);
		}
	}
}

/* ------------------------------------------------------------------ */
/* objetivos y decision                                                */
/* ------------------------------------------------------------------ */
static void scatter_corner(pac_ghost_id_t id, int *tc, int *tr)
{
	switch (id) {
	case PAC_GHOST_BLINKY: *tc = 25; *tr = -3; break;
	case PAC_GHOST_PINKY:  *tc = 2;  *tr = -3; break;
	case PAC_GHOST_INKY:   *tc = 27; *tr = 31; break;
	default:               *tc = 0;  *tr = 31; break;
	}
}

void pac_ai_ghost_target(const pac_game_t *g, const ghost_t *gh,
                         int *tc, int *tr)
{
	pac_ghost_id_t id = (pac_ghost_id_t)(gh - g->ghosts);
	int pc = pac_maze_col(g->pac.x);
	int pr = pac_maze_row(g->pac.y);
	pac_dir_t pd = (g->pac.dir != PAC_DIR_NONE) ? g->pac.dir : g->pac.facing;
	int elroy = pac_ai_elroy(g);

	*tc = pc;
	*tr = pr;

	/* en scatter cada uno va a su esquina; Cruise Elroy hace perseguir al rojo */
	if (g->mode == PAC_PHASE_SCATTER) {
		scatter_corner(id, tc, tr);
		if (id == PAC_GHOST_BLINKY && elroy > 0 &&
		    gh->state == PAC_GHOST_NORMAL) {
			*tc = pc;
			*tr = pr;
		}
		return;
	}

	switch (id) {
	case PAC_GHOST_BLINKY:
		*tc = pc;
		*tr = pr;
		break;
	case PAC_GHOST_PINKY:
		if (pd == PAC_DIR_UP) {
			/* bug original: mira 4 tiles arriba y 4 a la izquierda */
			*tc = pc - 4;
			*tr = pr - 4;
		} else {
			*tc = pc + 4 * pac_dir_dx(pd);
			*tr = pr + 4 * pac_dir_dy(pd);
		}
		break;
	case PAC_GHOST_INKY: {
		int px = pc + 2 * pac_dir_dx(pd);
		int py = pr + 2 * pac_dir_dy(pd);
		int bc = pac_maze_col(g->ghosts[PAC_GHOST_BLINKY].x);
		int br = pac_maze_row(g->ghosts[PAC_GHOST_BLINKY].y);
		if (pd == PAC_DIR_UP) {
			px = pc - 2;
			py = pr - 2;
		}
		*tc = 2 * px - bc;
		*tr = 2 * py - br;
		break;
	}
	default: {   /* Clyde: persigue si esta lejos (>8 tiles), si no a su esquina */
		int cx = pac_maze_col(gh->x);
		int cy = pac_maze_row(gh->y);
		int dx = cx - pc;
		int dy = cy - pr;
		if (dx * dx + dy * dy > 8 * 8) {
			*tc = pc;
			*tr = pr;
		} else {
			scatter_corner(PAC_GHOST_CLYDE, tc, tr);
		}
		break;
	}
	}
}

static int dir_valid_for_ghost(const pac_game_t *g, int col, int row, pac_dir_t d)
{
	return pac_maze_walkable_ghost(g, col + pac_dir_dx(d), row + pac_dir_dy(d));
}

/* zonas del arcade donde los fantasmas no pueden girar hacia arriba
 * (docs/PAKU_AUDIT.md 3.6; 0-based) salvo en frightened */
static int no_up_tile(int col, int row)
{
	return (col == 12 || col == 15) && (row == 11 || row == 23);
}

pac_dir_t pac_ai_ghost_decide(pac_game_t *g, ghost_t *gh)
{
	static const pac_dir_t order[4] = {
		PAC_DIR_UP, PAC_DIR_LEFT, PAC_DIR_DOWN, PAC_DIR_RIGHT
	};
	int col = pac_maze_col(gh->x);
	int row = pac_maze_row(gh->y);
	pac_dir_t rev = pac_opposite(gh->dir);
	int i;

	if (gh->state != PAC_GHOST_NORMAL)
		return gh->dir;

	if (gh->scared) {
		/* Paku-Paku: objetivo de tile pseudoaleatorio y luego minimiza
		 * distancia; en frightened se permite girar arriba en cualquier tile. */
		int tc = pac_random(g) % PAC_COLS;
		int tr = pac_random(g) % PAC_ROWS;
		int best = 0x7fffffff;
		pac_dir_t best_dir = PAC_DIR_NONE;
		for (i = 0; i < 4; i++) {
			int nx, ny, dx, dy, dist;
			if (order[i] == rev)
				continue;
			if (!dir_valid_for_ghost(g, col, row, order[i]))
				continue;
			nx = col + pac_dir_dx(order[i]);
			ny = row + pac_dir_dy(order[i]);
			dx = nx - tc;
			dy = ny - tr;
			dist = dx * dx + dy * dy;
			if (dist < best) {
				best = dist;
				best_dir = order[i];
			}
		}
		if (best_dir != PAC_DIR_NONE)
			return best_dir;
		if (dir_valid_for_ghost(g, col, row, rev))
			return rev;
		return gh->dir;
	}

	{
		int tc, tr;
		int best = 0x7fffffff;
		pac_dir_t best_dir = PAC_DIR_NONE;

		pac_ai_ghost_target(g, gh, &tc, &tr);
		for (i = 0; i < 4; i++) {
			int nx, ny, dx, dy, dist;
			if (order[i] == rev)
				continue;
			if (order[i] == PAC_DIR_UP && no_up_tile(col, row))
				continue;
			if (!dir_valid_for_ghost(g, col, row, order[i]))
				continue;
			nx = col + pac_dir_dx(order[i]);
			ny = row + pac_dir_dy(order[i]);
			dx = nx - tc;
			dy = ny - tr;
			dist = dx * dx + dy * dy;
			if (dist < best) {
				best = dist;
				best_dir = order[i];
			}
		}
		if (best_dir != PAC_DIR_NONE)
			return best_dir;
	}

	/* sin salida: invertir si es posible */
	if (pac_maze_walkable_ghost(g, col + pac_dir_dx(rev),
	                            row + pac_dir_dy(rev)))
		return rev;
	return gh->dir;
}
