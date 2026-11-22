/* apps/game/game_entities.c - movimiento en cuadricula, casa y colisiones
 *
 * Las posiciones son el centro de cada entidad en Q8.8 px. Pac-Man y los
 * fantasmas solo toman decisiones cuando su centro coincide exactamente con
 * el centro de un tile; entre centros avanzan en linea recta. El tunel de la
 * fila 14 hace wrap horizontal en el borde real del laberinto: el centro que
 * cruza el extremo izquierdo (x < 0) reaparece en el extremo derecho y el que
 * cruza el extremo derecho (x > PAC_MAZE_W) reaparece en el izquierdo, siempre
 * dentro del mismo frame. Sin FPU: todas las operaciones son enteras.
 */
#include <stdint.h>
#include "string.h"
#include "pac_game.h"
#include "game_maze.h"
#include "game_ai.h"
#include "game_entities.h"

#define HALF_TILE_Q  PAC_SUBPX(PAC_TILE / 2)

/* distancia desde un centro de tile hasta el siguiente en sentido positivo */
static int32_t center_phase(int32_t pos)
{
	int32_t d = (pos - HALF_TILE_Q) % PAC_TILE_Q;
	if (d < 0)
		d += PAC_TILE_Q;
	return d;
}

static int at_tile_center(int32_t x, int32_t y)
{
	return center_phase(x) == 0 && center_phase(y) == 0;
}

static void wrap_axis_x(int32_t *x)
{
	/* plegado del tunel en el borde real del laberinto: el centro que cruza
	 * 0 pasa al extremo opuesto y el que cruza PAC_MAZE_W vuelve al inicio.
	 * while para tolerar sobrepasos de varios tiles en un mismo frame. */
	int32_t span = PAC_SUBPX(PAC_MAZE_W);

	while (*x < 0)
		*x += span;
	while (*x > span)
		*x -= span;
}

/* mueve una coordenada hacia un objetivo sin pasarse */
static void move_toward(int32_t *v, int32_t target, int32_t dist)
{
	if (*v < target) {
		*v += dist;
		if (*v > target)
			*v = target;
	} else if (*v > target) {
		*v -= dist;
		if (*v < target)
			*v = target;
	}
}

static int32_t dir_distance(int32_t pos, pac_dir_t dir)
{
	int32_t phase = center_phase(pos);
	int sign = (dir == PAC_DIR_RIGHT || dir == PAC_DIR_DOWN) ? 1 : -1;
	if (phase == 0)
		return PAC_TILE_Q;
	return (sign > 0) ? (PAC_TILE_Q - phase) : phase;
}

/* ------------------------------------------------------------------ */
/* inicializacion                                                      */
/* ------------------------------------------------------------------ */
static void ghost_setup(ghost_t *gh, int id, int col, int row,
                        pac_dir_t dir, pac_ghost_state_t state)
{
	memset(gh, 0, sizeof(*gh));
	gh->x = pac_maze_center_x(col);
	gh->y = pac_maze_center_y(row);
	gh->dir = dir;
	gh->facing = dir;
	gh->state = state;
	gh->start_col = col;
	gh->start_row = row;
	gh->anim_ms = id * 70;
	gh->bob_dir = (id & 1) ? -1 : 1;
	gh->path_len = 0;
	gh->path_pos = 0;
}

void pac_entities_init_level(pac_game_t *g)
{
	pacman_t *p = &g->pac;

	memset(p, 0, sizeof(*p));
	p->x = pac_maze_center_x(PAC_SPAWN_PAC_COL);
	p->y = pac_maze_center_y(PAC_SPAWN_PAC_ROW);
	p->dir = PAC_DIR_LEFT;
	p->requested = PAC_DIR_LEFT;
	p->facing = PAC_DIR_LEFT;
	p->alive = 1;
	p->mouth = 0;
	p->death_ms = 0;

	ghost_setup(&g->ghosts[PAC_GHOST_BLINKY], PAC_GHOST_BLINKY,
	            PAC_SPAWN_BLINKY_COL, PAC_SPAWN_BLINKY_ROW,
	            PAC_DIR_LEFT, PAC_GHOST_NORMAL);
	ghost_setup(&g->ghosts[PAC_GHOST_PINKY], PAC_GHOST_PINKY,
	            PAC_SPAWN_PINKY_COL, PAC_SPAWN_PINKY_ROW,
	            PAC_DIR_UP, PAC_GHOST_HOME);
	ghost_setup(&g->ghosts[PAC_GHOST_INKY], PAC_GHOST_INKY,
	            PAC_SPAWN_INKY_COL, PAC_SPAWN_INKY_ROW,
	            PAC_DIR_UP, PAC_GHOST_HOME);
	ghost_setup(&g->ghosts[PAC_GHOST_CLYDE], PAC_GHOST_CLYDE,
	            PAC_SPAWN_CLYDE_COL, PAC_SPAWN_CLYDE_ROW,
	            PAC_DIR_UP, PAC_GHOST_HOME);

	g->ghosts[PAC_GHOST_PINKY].state_ms = 0;
}

void pac_entities_reset_positions(pac_game_t *g)
{
	pacman_t *p = &g->pac;
	int i;

	p->x = pac_maze_center_x(PAC_SPAWN_PAC_COL);
	p->y = pac_maze_center_y(PAC_SPAWN_PAC_ROW);
	p->dir = PAC_DIR_LEFT;
	p->requested = PAC_DIR_LEFT;
	p->facing = PAC_DIR_LEFT;
	p->alive = 1;
	p->death_ms = 0;
	p->mouth = 0;
	p->moving = 0;

	for (i = 0; i < PAC_GHOST_COUNT; i++) {
		ghost_t *gh = &g->ghosts[i];
		int col = gh->start_col;
		int row = gh->start_row;
		gh->x = pac_maze_center_x(col);
		gh->y = pac_maze_center_y(row);
		gh->dir = (i == PAC_GHOST_BLINKY) ? PAC_DIR_LEFT : PAC_DIR_UP;
		gh->facing = gh->dir;
		gh->state = (i == PAC_GHOST_BLINKY) ? PAC_GHOST_NORMAL : PAC_GHOST_HOME;
		gh->scared = 0;
		gh->path_len = 0;
		gh->path_pos = 0;
		gh->state_ms = 0;
		gh->bob_dir = (i & 1) ? -1 : 1;
	}
}

/* ------------------------------------------------------------------ */
/* Pac-Man                                                             */
/* ------------------------------------------------------------------ */
static void pacman_apply_request(game_t *g, pacman_t *p, int col, int row)
{
	pac_dir_t want = p->requested;

	if (want != PAC_DIR_NONE && want != p->dir) {
		if (pac_maze_walkable_pac(g, col + pac_dir_dx(want),
		                          row + pac_dir_dy(want))) {
			p->dir = want;
			p->facing = want;
		}
	}
	if (p->dir != PAC_DIR_NONE &&
	    !pac_maze_walkable_pac(g, col + pac_dir_dx(p->dir),
	                           row + pac_dir_dy(p->dir))) {
		p->dir = PAC_DIR_NONE;
	}
}

void pac_entities_update_pacman(pac_game_t *g, int dt_ms)
{
	pacman_t *p = &g->pac;
	int32_t dist;
	int moved = 0;

	if (!p->alive || p->death_ms > 0 || g->ready_ms > 0)
		return;

	/* giro instantaneo si piden la direccion contraria */
	if (p->requested != PAC_DIR_NONE && p->dir != PAC_DIR_NONE &&
	    p->requested == pac_opposite(p->dir)) {
		p->dir = p->requested;
		p->facing = p->dir;
	}

	dist = pac_ai_pacman_speed(g) * dt_ms / 1000;

	while (dist > 0) {
		int col, row;
		int32_t step, *pos;
		int sign;

		col = pac_maze_col(p->x);
		row = pac_maze_row(p->y);

		if (p->dir == PAC_DIR_NONE) {
			if (at_tile_center(p->x, p->y))
				pacman_apply_request(g, p, col, row);
			if (p->dir == PAC_DIR_NONE)
				break;
		}

		/* en el centro de un tile se decide la direccion */
		if (at_tile_center(p->x, p->y)) {
			pacman_apply_request(g, p, col, row);
			if (p->dir == PAC_DIR_NONE)
				break;
			step = PAC_TILE_Q;
		} else {
			step = dir_distance((p->dir == PAC_DIR_LEFT || p->dir == PAC_DIR_RIGHT)
			                        ? p->x : p->y,
			                    p->dir);
		}

		sign = (p->dir == PAC_DIR_RIGHT || p->dir == PAC_DIR_DOWN) ? 1 : -1;
		pos = (p->dir == PAC_DIR_LEFT || p->dir == PAC_DIR_RIGHT) ? &p->x : &p->y;

		if (dist < step) {
			*pos += sign * dist;
			dist = 0;
			moved = 1;
			/* plegado inmediato si el centro cruzo el borde del laberinto */
			if (p->dir == PAC_DIR_LEFT || p->dir == PAC_DIR_RIGHT)
				wrap_axis_x(&p->x);
		} else {
			*pos += sign * step;
			dist -= step;
			moved = 1;
			/* plegado del tunel al alcanzar un centro de tile */
			if (p->dir == PAC_DIR_LEFT || p->dir == PAC_DIR_RIGHT)
				wrap_axis_x(&p->x);
		}
		if (p->dir == PAC_DIR_LEFT || p->dir == PAC_DIR_RIGHT)
			p->facing = p->dir;
		else
			p->facing = p->dir;
	}

	p->moving = moved;
	if (moved) {
		p->anim_ms += dt_ms;
		p->mouth = (p->anim_ms / 39) % 3;
	} else {
		p->mouth = 1;
	}

	/* comer dots, power pills y fruta */
	if (p->alive) {
		int col = pac_maze_col(p->x);
		int row = pac_maze_row(p->y);
		int ev = pac_maze_consume(g, col, row);
		if (ev != PAC_GAME_EVENT_NONE)
			pac_emit_event(g, (pac_game_event_t)ev);
	}
	if (p->alive && g->fruit_visible_ms > 0 &&
	    pac_maze_col(p->x) == PAC_FRUIT_COL &&
	    pac_maze_row(p->y) == PAC_FRUIT_ROW) {
		g->fruit_visible_ms = 0;
		g->fruit_flash_ms = 1200;
		g->fruit_eaten_count++;
		if (g->fruit_index >= 0 && g->fruit_index < PAC_FRUIT_COUNT)
			g->fruit_counts[g->fruit_index]++;
		pac_add_score(g, g->fruit_value);
		g->popup_ms = 1000;
		g->popup_value = g->fruit_value;
		g->popup_x = pac_maze_center_x(PAC_FRUIT_COL);
		g->popup_y = pac_maze_center_y(PAC_FRUIT_ROW) - PAC_SUBPX(12);
		pac_emit_event(g, PAC_GAME_EVENT_EAT_FRUIT);
	}
}

/* ------------------------------------------------------------------ */
/* Fantasmas: movimiento normal por el laberinto                       */
/* ------------------------------------------------------------------ */
static void ghost_move_normal(game_t *g, ghost_t *gh, int dt_ms)
{
	int32_t dist = pac_ai_ghost_speed(g, gh) * dt_ms / 1000;

	while (dist > 0) {
		int32_t step, *pos;
		int sign;

		if (at_tile_center(gh->x, gh->y)) {
			gh->dir = pac_ai_ghost_decide(g, gh);
			if (gh->dir == PAC_DIR_NONE)
				break;
			step = PAC_TILE_Q;
		} else {
			step = dir_distance((gh->dir == PAC_DIR_LEFT || gh->dir == PAC_DIR_RIGHT)
			                        ? gh->x : gh->y,
			                    gh->dir);
		}

		sign = (gh->dir == PAC_DIR_RIGHT || gh->dir == PAC_DIR_DOWN) ? 1 : -1;
		pos = (gh->dir == PAC_DIR_LEFT || gh->dir == PAC_DIR_RIGHT) ? &gh->x : &gh->y;

		if (dist < step) {
			*pos += sign * dist;
			dist = 0;
			/* plegado inmediato si el centro cruzo el borde del laberinto */
			if (gh->dir == PAC_DIR_LEFT || gh->dir == PAC_DIR_RIGHT)
				wrap_axis_x(&gh->x);
		} else {
			*pos += sign * step;
			dist -= step;
			/* plegado del tunel al alcanzar un centro de tile */
			if (gh->dir == PAC_DIR_LEFT || gh->dir == PAC_DIR_RIGHT)
				wrap_axis_x(&gh->x);
		}
		gh->facing = gh->dir;
	}
}

/* rebote dentro de la casa mientras espera salir */
static void ghost_home_bob(game_t *g, ghost_t *gh, int dt_ms)
{
	int32_t dist = pac_ai_ghost_speed(g, gh) * dt_ms / 1000;
	int32_t base = pac_maze_center_y(gh->start_row);
	int32_t target = base + gh->bob_dir * PAC_SUBPX(6);

	move_toward(&gh->y, target, dist);
	if (gh->y == target)
		gh->bob_dir = -gh->bob_dir;
	gh->dir = (gh->bob_dir > 0) ? PAC_DIR_DOWN : PAC_DIR_UP;
	gh->facing = gh->dir;
}

/* salida de la casa: alinear con la puerta y subir al pasillo */
static void ghost_leave_pen(game_t *g, ghost_t *gh, int dt_ms)
{
	int32_t speed = pac_ai_ghost_speed(g, gh) * dt_ms / 1000;
	int32_t door_col = (gh->x <= pac_maze_center_x(PAC_DOOR_COL0)) ? PAC_DOOR_COL0
	                                                               : PAC_DOOR_COL1;
	int32_t target_x = pac_maze_center_x(door_col);
	int32_t target_y = pac_maze_center_y(11);

	if (gh->x != target_x) {
		move_toward(&gh->x, target_x, speed);
		gh->facing = (gh->x < target_x) ? PAC_DIR_RIGHT : PAC_DIR_LEFT;
		gh->dir = gh->facing;
		gh->state_ms = 0;
		return;
	}
	if (gh->y != target_y) {
		move_toward(&gh->y, target_y, speed);
		gh->facing = PAC_DIR_UP;
		gh->dir = PAC_DIR_UP;
		return;
	}
	/* ya esta en el pasillo superior */
	gh->state = PAC_GHOST_NORMAL;
	gh->dir = PAC_DIR_LEFT;
	gh->facing = gh->dir;
	gh->state_ms = 0;
}

/* ojos volviendo a la casa: siguen la ruta BFS calculada */
static void ghost_eyes_return(game_t *g, ghost_t *gh, int dt_ms)
{
	int32_t dist = pac_ai_ghost_speed(g, gh) * dt_ms / 1000;
	int home_col = 14;

	if ((gh - g->ghosts) == PAC_GHOST_INKY)
		home_col = 12;
	else if ((gh - g->ghosts) == PAC_GHOST_CLYDE)
		home_col = 16;

	while (dist > 0) {
		int32_t phase, step, *pos;
		int sign;

		if (at_tile_center(gh->x, gh->y)) {
			int col = pac_maze_col(gh->x);
			int row = pac_maze_row(gh->y);
			if (gh->path_len == 0) {
				gh->path_len = pac_maze_bfs(col, row, home_col, 15,
				                            gh->path, (int)sizeof(gh->path));
				gh->path_pos = 0;
				if (gh->path_len == 0) {
					/* sin ruta (posicion rara): regenerar en casa.
					 * El sonido de respawn lo gobierna update_siren
					 * mientras el fantasma siga en PAC_GHOST_EATEN. */
					gh->x = pac_maze_center_x(home_col);
					gh->y = pac_maze_center_y(15);
					gh->state = PAC_GHOST_REVIVING;
					gh->state_ms = 700;
					return;
				}
			}
			if (gh->path_pos >= gh->path_len) {
				/* ha llegado a su hueco: se regenera; update_siren
				 * retomara el ambiente al no quedar ojos en EATEN. */
				gh->state = PAC_GHOST_REVIVING;
				gh->state_ms = 700;
				serial_ghost_marker("GHOST_RETURNED", (int)(gh - g->ghosts));
				gh->x = pac_maze_center_x(home_col);
				gh->y = pac_maze_center_y(15);
				gh->dir = PAC_DIR_UP;
				gh->facing = PAC_DIR_UP;
				gh->path_len = 0;
				gh->path_pos = 0;
				return;
			}
			gh->dir = (pac_dir_t)gh->path[gh->path_pos++];
			gh->facing = gh->dir;
		}
		if (gh->dir == PAC_DIR_NONE) {
			/* sin direccion no se puede avanzar: vuelve al centro */
			break;
		}

		phase = dir_distance((gh->dir == PAC_DIR_LEFT || gh->dir == PAC_DIR_RIGHT)
		                         ? gh->x : gh->y, gh->dir);
		sign = (gh->dir == PAC_DIR_RIGHT || gh->dir == PAC_DIR_DOWN) ? 1 : -1;
		pos = (gh->dir == PAC_DIR_LEFT || gh->dir == PAC_DIR_RIGHT)
		          ? &gh->x : &gh->y;
		step = phase;

		if (dist < step) {
			*pos += sign * dist;
			dist = 0;
			/* plegado inmediato si el centro cruzo el borde del laberinto */
			if (gh->dir == PAC_DIR_LEFT || gh->dir == PAC_DIR_RIGHT)
				wrap_axis_x(&gh->x);
		} else {
			*pos += sign * step;
			dist -= step;
			/* plegado del tunel al alcanzar un centro de tile */
			if (gh->dir == PAC_DIR_LEFT || gh->dir == PAC_DIR_RIGHT)
				wrap_axis_x(&gh->x);
		}
	}
}

void pac_entities_update_ghosts(pac_game_t *g, int dt_ms)
{
	int i;

	if (g->ready_ms > 0 || g->death_ms > 0)
		return;

	for (i = 0; i < PAC_GHOST_COUNT; i++) {
		ghost_t *gh = &g->ghosts[i];

		gh->anim_ms += dt_ms;

		switch (gh->state) {
		case PAC_GHOST_HOME:
			ghost_home_bob(g, gh, dt_ms);
			break;
		case PAC_GHOST_LEAVING:
			ghost_leave_pen(g, gh, dt_ms);
			break;
		case PAC_GHOST_EATEN:
			ghost_eyes_return(g, gh, dt_ms);
			break;
		case PAC_GHOST_REVIVING:
			if (gh->state_ms > 0)
				gh->state_ms -= dt_ms;
			if (gh->state_ms <= 0) {
				gh->state = PAC_GHOST_LEAVING;
				gh->dir = PAC_DIR_UP;
				gh->facing = PAC_DIR_UP;
				serial_ghost_marker("GHOST_REVIVED", (int)(gh - g->ghosts));
			}
			break;
		case PAC_GHOST_NORMAL:
		default:
			ghost_move_normal(g, gh, dt_ms);
			break;
		}
	}
}

/* ------------------------------------------------------------------ */
/* colisiones                                                          */
/* ------------------------------------------------------------------ */
static void ghost_eat(game_t *g, ghost_t *gh)
{
	int value = 200 << (g->ghost_kill_index > 3 ? 3 : g->ghost_kill_index);

	if (g->ghost_kill_index < 4)
		g->ghost_kill_index++;
	if (g->ghost_kill_index >= 4) {
		/* al comerse el cuarto fantasma termina el frightened */
		int i;
		g->fright_ms = 0;
		for (i = 0; i < PAC_GHOST_COUNT; i++)
			g->ghosts[i].scared = 0;
	}

	gh->state = PAC_GHOST_EATEN;
	serial_ghost_marker("GHOST_EATEN", (int)(gh - g->ghosts));
	gh->scared = 0;
	gh->path_len = 0;
	gh->path_pos = 0;
	gh->dir = PAC_DIR_NONE;
	/* el fantasma puede ser comido entre tiles por la tolerancia de
	 * colision; se centra en su tile para que el BFS de ojos siempre
	 * arranque desde un centro valido (antes se quedaba sin direccion). */
	gh->x = pac_maze_center_x(pac_maze_col(gh->x));
	gh->y = pac_maze_center_y(pac_maze_row(gh->y));

	pac_add_score(g, value);
	g->popup_ms = 900;
	g->popup_value = value;
	g->popup_x = gh->x;
	g->popup_y = gh->y - PAC_SUBPX(10);
	pac_emit_event(g, PAC_GAME_EVENT_EAT_GHOST);
}

int pac_entities_collisions(pac_game_t *g)
{
	pacman_t *p = &g->pac;
	int i;

	if (!p->alive || g->ready_ms > 0 || g->death_ms > 0)
		return PAC_GAME_EVENT_NONE;

	for (i = 0; i < PAC_GHOST_COUNT; i++) {
		ghost_t *gh = &g->ghosts[i];
		int32_t dx, dy;

		if (gh->state == PAC_GHOST_EATEN || gh->state == PAC_GHOST_REVIVING)
			continue;
		dx = PAC_PX(gh->x) - PAC_PX(p->x);
		dy = PAC_PX(gh->y) - PAC_PX(p->y);
		/* mismo tile o 4 px de tolerancia (2 px del original a 8 px/tile) */
		if (pac_maze_col(gh->x) != pac_maze_col(p->x) ||
		    pac_maze_row(gh->y) != pac_maze_row(p->y)) {
			if (dx > 4 || dx < -4 || dy > 4 || dy < -4)
				continue;
		}

		if (gh->scared && gh->state != PAC_GHOST_HOME) {
			ghost_eat(g, gh);
			return PAC_GAME_EVENT_EAT_GHOST;
		}
		if (gh->state == PAC_GHOST_NORMAL || gh->state == PAC_GHOST_LEAVING) {
			p->alive = 0;
			p->death_ms = PAC_DEATH_MS;
			p->mouth = 2;
			pac_serial("PAC_DEATH");
			pac_emit_event(g, PAC_GAME_EVENT_DEATH);
			return PAC_GAME_EVENT_DEATH;
		}
	}
	return PAC_GAME_EVENT_NONE;
}
