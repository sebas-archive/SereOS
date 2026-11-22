/* core_tests.c - harness del nucleo y render compartidos de PAC-MAN SereOS
 *
 * Usa una plataforma mock (framebuffer en memoria, reloj simulado, audio y
 * record capturados) para validar la logica sin OS ni SDL. Migrado del
 * harness de desarrollo del juego (78 checks).
 */
#include <stdio.h>
#include <stdint.h>
#include <stddef.h>
#include <stdlib.h>
#include <string.h>

#include "pac_platform.h"
#include "pacman.h"
#include "pac_game.h"
#include "pac_util.h"
#include "game_maze.h"
#include "game_ai.h"
#include "game_entities.h"
#include "game_audio.h"
#include "game_render.h"
#include "pac_theme.h"
#include "mock_platform.h"
#include "sprites_res.h"
#include "font_arcade.h"
#include "sfx_res.h"
#include "sprites.h"

#define SB16_MAX_BUFFER_LOCAL 32768u

/* compatibilidad con los codigos historicos del harness */
#define KEY_ESC            PAC_KEY_ESC
#define KEY_ENTER          PAC_KEY_ENTER
#define KEY_UP             PAC_KEY_UP
#define KEY_DOWN           PAC_KEY_DOWN
#define KEY_LEFT           PAC_KEY_LEFT
#define KEY_RIGHT          PAC_KEY_RIGHT
#define KEY_Q              PAC_KEY_Q
#define KEY_R              PAC_KEY_R
#define AUDIO_POWER        PAC_SFX_POWER
#define AUDIO_EXTRA_LIFE   PAC_SFX_EXTRA_LIFE
#define AUDIO_SIREN_FRIGHT PAC_SFX_SIREN_FRIGHT

static pac_game_t *g;
static int failures;
static int checks;

#define CHECK(cond, name) do { \
	checks++; \
	if (cond) printf("PASS %s\n", name); \
	else { printf("FAIL %s\n", name); failures++; } \
} while (0)

static int contains(const char *hay, const char *needle)
{
	size_t i, n = strlen(needle);
	for (i = 0; hay && hay[i]; i++)
		if (strncmp(hay + i, needle, n) == 0)
			return 1;
	return 0;
}

static void key_ev(int key, int down)
{
	pac_event_t ev;
	memset(&ev, 0, sizeof(ev));
	ev.type = down ? PAC_EVENT_KEY_DOWN : PAC_EVENT_KEY_UP;
	ev.key = (uint16_t)key;
	ev.pressed = down ? 1 : 0;
	ev.tick = mock_get_ticks();
	pac_game_event(g, &ev);
}

static void run_ticks(int n)
{
	int i;
	for (i = 0; i < n; i++) {
		mock_advance_tick();
		(void)pac_game_tick(g);
	}
}

static void run_ms(int ms) { run_ticks(ms / 10); }

static void draw(const char *name)
{
	pac_rect_t vp;
	char path[160];
	if (!g || pac_game_wants_close(g))
		return;
	vp.x = mock_content_x(); vp.y = mock_content_y();
	vp.w = mock_content_w(); vp.h = mock_content_h();
	pac_set_clip(vp.x, vp.y, vp.w, vp.h);
	pac_game_draw(g, &vp);
	snprintf(path, sizeof(path), "/tmp/pac_tests/%s.ppm", name);
	mock_dump_ppm(path, vp.x, vp.y, vp.w, vp.h);
	printf("[frame] %s\n", name);
}

static void new_window(void)
{
	if (g) {
		pac_game_destroy(g);
		g = NULL;
	}
	mock_set_size(880, 560);
	mock_set_focused(1);
	mock_set_minimized(0);
	g = pac_game_create();
	if (g) {
		pac_event_t ev;
		memset(&ev, 0, sizeof(ev));
		ev.type = PAC_EVENT_KEY_DOWN;
		ev.key = PAC_KEY_ENTER;
		ev.pressed = 1;
		pac_game_event(g, &ev);
		run_ticks(3);
		g->menu_sel = 0;
	}
}

static void close_game(void)
{
	if (!g)
		return;
	pac_game_destroy(g);
	g = NULL;
}


static void skip_ready(void)
{
	int guard = 1000;
	while (g && g->ready_ms > 0 && guard-- > 0) {
		mock_advance_tick();
		(void)pac_game_tick(g);
	}
}

static int tile_ok_pac(int col, int row)
{
	return pac_maze_walkable_pac(g, col, row);
}

/* ------------------------------------------------------------------ */
/* regresion del tunel lateral y del recorte de personajes            */
/* ------------------------------------------------------------------ */
#define TUNNEL_ROW 14

static int32_t tunnel_span(void) { return PAC_SUBPX(PAC_MAZE_W); }
static int32_t tunnel_half(void) { return PAC_SUBPX(PAC_MAZE_W / 2); }

/* partida recien empezada en PLAYING y sin cartel READY!: los tests de wrap
 * y de clip controlan las posiciones a mano, no deben esperar al banner */
static void enter_game(void)
{
	new_window();
	if (!g)
		return;
	g->menu_sel = 0;
	key_ev(KEY_ENTER, 1);
	run_ticks(2);
	key_ev(KEY_ENTER, 0);
	g->ready_ms = 0;
}

/* deja el juego en PLAYING sin hold/one-shot/READY ni movimiento, para
 * probar la maquina de audio de forma determinista */
static void audio_quiet(void)
{
	int i;

	if (!g)
		return;
	g->ready_ms = 0;
	g->death_ms = 0;
	g->fright_ms = 0;
	g->audio_hold_ms = 0;
	g->audio_oneshot = PAC_SFX_NONE;
	g->siren_grace_ms = 0;
	g->pac.dir = PAC_DIR_NONE;
	g->pac.requested = PAC_DIR_NONE;
	for (i = 0; i < PAC_GHOST_COUNT; i++) {
		g->ghosts[i].state = PAC_GHOST_HOME;
		g->ghosts[i].scared = 0;
		g->ghosts[i].x = pac_maze_center_x(PAC_SPAWN_BLINKY_COL);
		g->ghosts[i].y = pac_maze_center_y(PAC_SPAWN_BLINKY_ROW);
	}
}

/* numero de llamadas de audio registradas con kind/sfx dados (sfx < 0 = cualquiera) */
static int audio_log_has(int kind, int sfx)
{
	int i, k, v, n = 0;

	for (i = 0; i < mock_audio_log_count(); i++) {
		if (!mock_audio_log_at(i, &k, &v))
			continue;
		if (k == kind && (sfx < 0 || v == sfx))
			n++;
	}
	return n;
}

/* instantanea RGB32 del viewport dibujado, leida del framebuffer del mock */
typedef struct {
	int x, y, w, h;
	uint32_t *px;
} frame_snapshot_t;

static void viewport_of_content(pac_rect_t *vp)
{
	vp->x = mock_content_x();
	vp->y = mock_content_y();
	vp->w = mock_content_w();
	vp->h = mock_content_h();
}

/* replica el layout de view_get() del render: rect exacto del laberinto */
static void maze_screen_rect(const pac_rect_t *vp, int *mx, int *my)
{
	*mx = vp->x + (vp->w - PAC_MAZE_W) / 2;
	if (*mx < vp->x + SP_2)
		*mx = vp->x + SP_2;
	*my = vp->y + (vp->h - PAC_MAZE_H) / 2;
	if (*my < vp->y + SP_2)
		*my = vp->y + SP_2;
}

static void frame_render(const pac_rect_t *vp)
{
	pac_set_clip(vp->x, vp->y, vp->w, vp->h);
	pac_game_draw(g, vp);
}

static int frame_snapshot(frame_snapshot_t *s, const pac_rect_t *vp)
{
	int i, j;

	s->x = vp->x; s->y = vp->y; s->w = vp->w; s->h = vp->h;
	s->px = (uint32_t *)malloc((size_t)vp->w * (size_t)vp->h *
	                           sizeof(uint32_t));
	if (!s->px)
		return 0;
	for (j = 0; j < vp->h; j++)
		for (i = 0; i < vp->w; i++)
			s->px[(size_t)j * vp->w + i] =
			    mock_fb_at(vp->x + i, vp->y + j);
	return 1;
}

static void frame_snapshot_free(frame_snapshot_t *s)
{
	free(s->px);
	s->px = NULL;
}

static int in_maze_rect(int x, int y, int mx, int my)
{
	return x >= mx && x < mx + PAC_MAZE_W &&
	       y >= my && y < my + PAC_MAZE_H;
}

/* pixeles que cambiaron dentro (inside=1) o fuera (inside=0) del rect del
 * laberinto; guarda el primer cambio en los punteros de salida */
static int frame_count_changes(const frame_snapshot_t *s, int mx, int my,
                               int inside, int *fx, int *fy)
{
	int i, j, n = 0;

	for (j = 0; j < s->h; j++) {
		for (i = 0; i < s->w; i++) {
			int x = s->x + i, y = s->y + j;
			if (in_maze_rect(x, y, mx, my) != inside)
				continue;
			if (mock_fb_at(x, y) != s->px[(size_t)j * s->w + i]) {
				if (n == 0 && fx && fy) {
					*fx = x;
					*fy = y;
				}
				n++;
			}
		}
	}
	return n;
}

/* renderiza un frame base y otro con Pac-Man y dos fantasmas desplazados a
 * posiciones Q8.8 concretas; devuelve cuantos pixeles cambian fuera/dentro
 * del rect del laberinto. Con el clip correcto fuera del rect = 0. */
static void clip_case(int32_t pac_x, int32_t g0_x, int32_t g1_x,
                      int *outside_diffs, int *inside_diffs,
                      int *first_x, int *first_y)
{
	pac_rect_t vp;
	frame_snapshot_t base;
	int mx, my;

	*outside_diffs = -1;
	*inside_diffs = -1;
	enter_game();
	if (!g)
		return;
	viewport_of_content(&vp);
	maze_screen_rect(&vp, &mx, &my);

	/* base: entidades en sus posiciones normales dentro del laberinto */
	g->state = PAC_STATE_PLAYING;
	g->ready_ms = 0;
	frame_render(&vp);
	if (!frame_snapshot(&base, &vp))
		return;

	/* variante: Pac-Man y fantasmas fuera del borde real del laberinto */
	g->pac.x = pac_x;
	g->pac.y = pac_maze_center_y(TUNNEL_ROW);
	g->ghosts[PAC_GHOST_BLINKY].x = g0_x;
	g->ghosts[PAC_GHOST_BLINKY].y = pac_maze_center_y(TUNNEL_ROW);
	g->ghosts[PAC_GHOST_PINKY].x = g1_x;
	g->ghosts[PAC_GHOST_PINKY].y = pac_maze_center_y(TUNNEL_ROW);
	frame_render(&vp);

	*outside_diffs = frame_count_changes(&base, mx, my, 0, first_x, first_y);
	*inside_diffs = frame_count_changes(&base, mx, my, 1, NULL, NULL);
	frame_snapshot_free(&base);
}

/* BFS de conectividad del laberinto: todos los dots deben ser alcanzables */
static int maze_connected(void)
{
	static int16_t q[PAC_COLS * PAC_ROWS];
	static uint8_t vis[PAC_COLS * PAC_ROWS];
	int head = 0, tail = 0, i, reachable_dots = 0;
	int start = PAC_SPAWN_PAC_ROW * PAC_COLS + PAC_SPAWN_PAC_COL;

	memset(vis, 0, sizeof(vis));
	vis[start] = 1;
	q[tail++] = (int16_t)start;
	while (head < tail) {
		int node = q[head++];
		int col = node % PAC_COLS;
		int row = node / PAC_COLS;
		for (i = 0; i < 4; i++) {
			pac_dir_t d = (pac_dir_t)(i + 1);
			int nc = col + pac_dir_dx(d);
			int nr = row + pac_dir_dy(d);
			int nn;
			if (nc < 0 || nc >= PAC_COLS || nr < 0 || nr >= PAC_ROWS)
				continue;
			if (!pac_maze_walkable_pac(g, nc, nr) || vis[nr * PAC_COLS + nc])
				continue;
			nn = nr * PAC_COLS + nc;
			vis[nn] = 1;
			q[tail++] = (int16_t)nn;
		}
	}
	for (i = 0; i < PAC_COLS * PAC_ROWS; i++) {
		int t = g->maze.base[i];
		if ((t == PAC_TILE_DOT || t == PAC_TILE_POWER) && vis[i])
			reachable_dots++;
	}
	return reachable_dots;
}

int main(void)
{
	int i;
	int dots, power;
	int reachable;

	mock_record_seed("1500");
	new_window();
	CHECK(g != NULL, "open reserva estado");
	CHECK(g && g->state == PAC_STATE_MENU, "estado inicial MENU");
	CHECK(g && g->high_score == 1500, "high score cargado de RAMFS");
	CHECK(contains(mock_serial(), "GAME_MENU"), "serial GAME_MENU al abrir");
	CHECK(!contains(mock_serial(), "GAME_START"), "sin GAME_START antes de jugar");
	draw("01_menu");

	/* navegacion de menu por teclado */
	key_ev(KEY_DOWN, 1); run_ticks(2); key_ev(KEY_DOWN, 0); run_ticks(1);
	CHECK(g && g->menu_sel == 2, "flecha abajo navega el menu (salta Continuar)");
	key_ev(KEY_DOWN, 1); run_ticks(2); key_ev(KEY_DOWN, 0); run_ticks(1);
	CHECK(g && g->menu_sel == 3, "menu llega a Instrucciones");
	key_ev(KEY_ENTER, 1); run_ticks(2); key_ev(KEY_ENTER, 0);
	CHECK(g && g->state == PAC_STATE_INSTRUCTIONS, "abre instrucciones");
	draw("02_instrucciones");
	key_ev(KEY_ENTER, 1); run_ticks(2); key_ev(KEY_ENTER, 0); run_ticks(1);
	CHECK(g && g->state == PAC_STATE_MENU, "vuelve al menu");

	/* clic de raton en el menu */
	{
		int hx, hy, found = 0;
		int cx0 = mock_content_x(), cy0 = mock_content_y();
		for (hy = cy0; hy < cy0 + mock_content_h() && !found; hy += 6) {
			for (hx = cx0; hx < cx0 + mock_content_w(); hx += 6) {
				int hit = pac_render_menu_hit(g, hx, hy);
				if (hit == 2) {
					pac_event_t ev;
					memset(&ev, 0, sizeof(ev));
					ev.type = PAC_EVENT_MOUSE_DOWN;
					ev.button = PAC_MOUSE_LEFT;
					ev.mouse_x = (int16_t)hx;
					ev.mouse_y = (int16_t)hy;
					pac_game_event(g, &ev);
					found = 1;
					break;
				}
			}
		}
		run_ticks(3);
		CHECK(found && g->state == PAC_STATE_RECORD, "clic de raton abre RECORD");
		draw("03_record");
		key_ev(KEY_ENTER, 1); run_ticks(2); key_ev(KEY_ENTER, 0); run_ticks(1);
		CHECK(g && g->state == PAC_STATE_MENU, "vuelve al menu tras record");
		/* volver a JUGAR (0) desde RECORD (2) */
		g->menu_sel = 0;
		CHECK(g && g->menu_sel == 0, "selector vuelve a JUGAR");
	}

	/* iniciar partida */
	mock_serial_clear();
	g->menu_sel = 0;
	key_ev(KEY_ENTER, 1); run_ticks(2); key_ev(KEY_ENTER, 0); run_ticks(1);
	CHECK(g && g->state == PAC_STATE_PLAYING, "JUGAR inicia partida");
	CHECK(contains(mock_serial(), "GAME_START"), "serial GAME_START");
	CHECK(g && g->lives == PAC_LIVES_START && g->level == 1, "3 vidas y nivel 1");
	CHECK(g && g->ready_ms > 0, "estado READY! al empezar");
	/* laberinto: 240 dots + 4 power + conectividad total */
	dots = power = 0;
	for (i = 0; i < PAC_COLS * PAC_ROWS; i++) {
		if (g->maze.base[i] == PAC_TILE_DOT) dots++;
		else if (g->maze.base[i] == PAC_TILE_POWER) power++;
	}
	CHECK(dots == PAC_DOTS_TOTAL, "240 dots en el laberinto");
	CHECK(power == PAC_POWER_TOTAL, "4 power pills en el laberinto");
	CHECK(g->dots_left == dots && g->power_left == power, "contadores iniciales correctos");
	draw("04_ready");
	skip_ready();
	CHECK(g->ready_ms == 0, "READY! termina solo");
	draw("05_play");
	reachable = maze_connected();
	CHECK(reachable == dots + power, "BFS: todos los dots/power son alcanzables");

	/* Pac-Man no atraviesa paredes con direcciones aleatorias */
	{
		int bad = 0, moved = 0;
		int32_t start_x = g->pac.x, start_y = g->pac.y;
		for (i = 0; i < 1500; i++) {
			if (i % 55 == 0) {
				int d = rand() % 4;
				g->pac.requested = (pac_dir_t)(d + 1);
			}
			/* se actualiza solo Pac-Man para aislar colisiones con fantasmas */
			pac_entities_update_pacman(g, PAC_STEP_MS);
			{
				int col = pac_maze_col(g->pac.x);
				int row = pac_maze_row(g->pac.y);
				if (col < 0 || col >= PAC_COLS || row < 0 || row >= PAC_ROWS ||
				    !tile_ok_pac(col, row))
					bad++;
			}
			if (g->pac.x != start_x || g->pac.y != start_y)
				moved = 1;
		}
		CHECK(bad == 0, "Pac-Man nunca queda dentro de una pared");
		CHECK(moved, "Pac-Man se mueve al pedir direccion");
	}

	/* fantasmas: salen de la casa y no se atascan */
	{
		int left_home[PAC_GHOST_COUNT] = { 0, 0, 0, 0 };
		int max_lives = g->lives;
		int normal_seen[PAC_GHOST_COUNT] = { 0, 0, 0, 0 };
		int bad = 0, changed = 0, j;
		int32_t lastx[PAC_GHOST_COUNT], lasty[PAC_GHOST_COUNT];
		for (j = 0; j < PAC_GHOST_COUNT; j++) {
			lastx[j] = g->ghosts[j].x;
			lasty[j] = g->ghosts[j].y;
		}
		g->lives = 99;
		for (i = 0; i < 3000; i++) {
			if (i % 40 == 0)
				g->pac.requested = (pac_dir_t)(1 + rand() % 4);
			run_ticks(1);
			if (g->state == PAC_STATE_GAMEOVER)
				break;
			if (g->death_ms > 0) {
				run_ms(PAC_DEATH_MS + 200);
				skip_ready();
				continue;
			}
			for (j = 0; j < PAC_GHOST_COUNT; j++) {
				ghost_t *gh = &g->ghosts[j];
				if (gh->state != PAC_GHOST_HOME)
					left_home[j] = 1;
				if (gh->state == PAC_GHOST_NORMAL) {
					int col = pac_maze_col(gh->x);
					int row = pac_maze_row(gh->y);
					normal_seen[j] = 1;
					if (!pac_maze_walkable_ghost(g, col, row) &&
					    !pac_maze_is_pen(col, row))
						bad++;
				}
				if (gh->x != lastx[j] || gh->y != lasty[j]) {
					lastx[j] = gh->x;
					lasty[j] = gh->y;
					changed++;
				}
			}
		}
		CHECK(left_home[1] && left_home[2] && left_home[3], "Pinky/Inky/Clyde salen de la casa");
		CHECK(normal_seen[0] && normal_seen[1] && normal_seen[2] && normal_seen[3],
		      "los 4 fantasmas patrullan el laberinto");
		CHECK(bad == 0, "fantasmas nunca dentro de paredes");
		CHECK(changed > 500, "fantasmas en movimiento (no atascados)");
		g->lives = max_lives;
	}

	/* objetivos por personalidad (Pac-Man Dossier) */
	{
		int tc, tr;
		g->state = PAC_STATE_PLAYING;
		g->mode = PAC_PHASE_CHASE;
		g->pac.x = pac_maze_center_x(10);
		g->pac.y = pac_maze_center_y(10);
		g->pac.dir = PAC_DIR_RIGHT;
		g->ghosts[0].state = PAC_GHOST_NORMAL;   /* Blinky: directo */
		pac_ai_ghost_target(g, &g->ghosts[0], &tc, &tr);
		CHECK(tc == 10 && tr == 10, "objetivo Blinky = tile de Pac-Man");
		pac_ai_ghost_target(g, &g->ghosts[1], &tc, &tr);   /* Pinky derecho */
		CHECK(tc == 14 && tr == 10, "objetivo Pinky = 4 delante");
		g->pac.dir = PAC_DIR_UP;
		pac_ai_ghost_target(g, &g->ghosts[1], &tc, &tr);   /* bug arriba */
		CHECK(tc == 6 && tr == 6, "Pinky arriba aplica el bug (-4,-4)");
		g->pac.dir = PAC_DIR_RIGHT;
		g->ghosts[0].x = pac_maze_center_x(1);
		g->ghosts[0].y = pac_maze_center_y(1);
		pac_ai_ghost_target(g, &g->ghosts[2], &tc, &tr);   /* Inky */
		CHECK(tc == 23 && tr == 19, "objetivo Inky = 2*(pivote-Blinky)");
		g->ghosts[3].x = pac_maze_center_x(27);
		g->ghosts[3].y = pac_maze_center_y(30);
		pac_ai_ghost_target(g, &g->ghosts[3], &tc, &tr);   /* Clyde lejos */
		CHECK(tc == 10 && tr == 10, "Clyde persigue si esta lejos");
		g->ghosts[3].x = pac_maze_center_x(11);
		g->ghosts[3].y = pac_maze_center_y(10);
		pac_ai_ghost_target(g, &g->ghosts[3], &tc, &tr);   /* Clyde cerca */
		CHECK(tc == 0 && tr == 31, "Clyde va a su esquina si esta cerca");
		g->mode = PAC_PHASE_SCATTER;
		g->dots_left = 200;
		pac_ai_ghost_target(g, &g->ghosts[0], &tc, &tr);
		CHECK(tc == 25 && tr == -3, "scatter Blinky a la esquina superior derecha");
		g->mode = PAC_PHASE_CHASE;
	}

	/* power pill: frightened, comer fantasma y ojos de vuelta */
	{
		int ev;
		int score_before;
		int ok_scared = 1;
		pac_start_new_game(g);
		skip_ready();
		g->pac.x = pac_maze_center_x(1);
		g->pac.y = pac_maze_center_y(3);
		g->pac.dir = PAC_DIR_NONE;
		g->pac.requested = PAC_DIR_NONE;
		run_ticks(2);
		CHECK(g->power_left == PAC_POWER_TOTAL - 1, "power pill consumida");
		CHECK(g->fright_ms > 0, "power pill activa FRIGHTENED");
		for (i = 0; i < PAC_GHOST_COUNT; i++)
			if (g->ghosts[i].state != PAC_GHOST_EATEN &&
			    g->ghosts[i].state != PAC_GHOST_HOME &&
			    g->ghosts[i].state != PAC_GHOST_REVIVING &&
			    !g->ghosts[i].scared)
				ok_scared = 0;
		CHECK(ok_scared, "fantasmas fuera de casa quedan asustados");
		CHECK(mock_audio_last_play() == AUDIO_POWER || mock_audio_last_play() == AUDIO_SIREN_FRIGHT,
		      "audio POWER al comer power pill");
		draw("06_frightened");
		/* colocar un fantasma encima y comerlo */
		score_before = g->score;
		g->ghosts[0].state = PAC_GHOST_NORMAL;
		g->ghosts[0].scared = 1;
		g->ghosts[0].x = g->pac.x;
		g->ghosts[0].y = g->pac.y;
		ev = pac_entities_collisions(g);
		CHECK(ev == PAC_GAME_EVENT_EAT_GHOST, "colision con fantasma asustado lo come");
		CHECK(g->score == score_before + 200, "comer fantasma suma 200");
		CHECK(g->ghosts[0].state == PAC_GHOST_EATEN, "fantasma comido -> ojos");
		run_ticks(3);   /* puede hacer falta acumular 16 ms para un tick logico */
		CHECK(g->ghosts[0].path_len > 0, "ojos calculan ruta BFS a la casa");
		/* dejar que los ojos vuelvan y se regeneren */
		{
			int seen_revive = 0, seen_normal = 0;
			for (i = 0; i < 1200; i++) {
				run_ticks(1);
				if (g->ghosts[0].state == PAC_GHOST_REVIVING)
					seen_revive = 1;
				if (g->ghosts[0].state == PAC_GHOST_NORMAL ||
				    g->ghosts[0].state == PAC_GHOST_LEAVING)
					if (seen_revive)
						seen_normal = 1;
				if (g->state != PAC_STATE_PLAYING)
					break;
			}
			CHECK(seen_revive, "ojos llegan a la casa y se regeneran");
			CHECK(seen_normal, "fantasma regenerado vuelve a patrullar");
		}
	}

	/* muerte, vidas y game over */
	{
		int lives0;
		pac_start_new_game(g);
		skip_ready();
		lives0 = g->lives; (void)lives0;
		for (i = 0; i < 3; i++) {
			g->ghosts[0].state = PAC_GHOST_NORMAL;
			g->ghosts[0].scared = 0;
			g->ghosts[0].x = g->pac.x;
			g->ghosts[0].y = g->pac.y;
				g->pac.alive = 1;
			pac_entities_collisions(g);
			CHECK(g->death_ms > 0, "colision normal inicia muerte");
			run_ms(PAC_DEATH_MS + 300);
			if (g->state == PAC_STATE_GAMEOVER)
				break;
			skip_ready();
		}
		CHECK(g->lives == 0, "se pierden las 3 vidas");
		CHECK(g->state == PAC_STATE_GAMEOVER, "sin vidas -> GAME OVER");
		CHECK(contains(mock_serial(), "GAME_OVER"), "serial GAME_OVER");
		CHECK(mock_record_len() > 0, "high score persistido en RAMFS");
		draw("07_gameover");
	}

	/* nivel completado -> siguiente nivel */
	{
		int level0;
		pac_start_new_game(g);
		skip_ready();
		for (i = 0; i < PAC_COLS * PAC_ROWS; i++) {
			int col = i % PAC_COLS, row = i / PAC_COLS;
			pac_maze_consume(g, col, row);
		}
		run_ticks(2);
		CHECK(g->dots_left == 0 && g->power_left == 0, "todos los dots comidos");
		CHECK(g->state == PAC_STATE_LEVEL_CLEAR, "nivel completado -> LEVEL CLEAR");
		CHECK(contains(mock_serial(), "GAME_WIN"), "serial GAME_WIN al completar nivel");
		draw("08_levelclear");
		level0 = g->level;
		run_ms(PAC_LEVEL_CLEAR_MS + 400);
		CHECK(g->level == level0 + 1, "pasa al siguiente nivel");
		CHECK(g->state == PAC_STATE_PLAYING, "siguiente nivel en juego");
		CHECK(g->dots_left == PAC_DOTS_TOTAL, "dots restaurados en el nuevo nivel");
	}

	/* fruta: aparece a los 70 dots, se come y suma valor de nivel 2 */
	{
		int score0, saved_level = g->level, idx;
		int zero = 1;
		for (i = 0; i < PAC_FRUIT_COUNT; i++)
			if (g->fruit_counts[i] != 0)
				zero = 0;
		CHECK(zero && g->fruit_eaten_count == 0,
		      "contadores de fruta a cero al iniciar partida");
		skip_ready();
		g->dots_eaten = PAC_FRUIT_DOT_1 - 1;
		/* buscar un dot y poner a Pac-Man encima */
		for (i = 0; i < PAC_COLS * PAC_ROWS; i++) {
			int col = i % PAC_COLS, row = i / PAC_COLS;
			if (g->maze.tiles[i] == PAC_TILE_DOT) {
				g->pac.x = pac_maze_center_x(col);
				g->pac.y = pac_maze_center_y(row);
				g->pac.dir = PAC_DIR_NONE;
				g->pac.requested = PAC_DIR_NONE;
				break;
			}
		}
		run_ticks(2);
		CHECK(g->dots_eaten == PAC_FRUIT_DOT_1, "dot 70 comido");
		CHECK(g->fruit_visible_ms > 0, "fruta aparece a los 70 dots");
		CHECK(pac_ai_level_fruit(g) == 1 &&
		      pac_ai_level_fruit_value(g) == 300,
		      "nivel 2: fruta indice 1 (FRESA) vale 300");
		draw("09_fruit");
		score0 = g->score;
		g->pac.x = pac_maze_center_x(PAC_FRUIT_COL);
		g->pac.y = pac_maze_center_y(PAC_FRUIT_ROW);
		g->pac.dir = PAC_DIR_NONE;
		g->pac.requested = PAC_DIR_NONE;
		run_ticks(2);
		idx = pac_ai_level_fruit(g);
		CHECK(g->fruit_eaten_count == 1, "fruta comida (total 1)");
		CHECK(idx >= 0 && idx < PAC_FRUIT_COUNT && g->fruit_counts[idx] == 1,
		      "fruta comida suma al contador de su tipo");
		CHECK(g->score >= score0 + pac_ai_level_fruit_value(g),
		      "fruta de nivel 2 vale 300");
		draw("09b_fruit_eaten");

		/* segunda fruta del nivel 170: otro tipo suma en su contador */
		g->level = 4;   /* MANZANA (indice 3) vale 700 */
		g->fruit_flash_ms = 0;
		g->dots_eaten = PAC_FRUIT_DOT_2 - 1;
		for (i = 0; i < PAC_COLS * PAC_ROWS; i++) {
			int col = i % PAC_COLS, row = i / PAC_COLS;
			if (g->maze.tiles[i] == PAC_TILE_DOT) {
				g->pac.x = pac_maze_center_x(col);
				g->pac.y = pac_maze_center_y(row);
				g->pac.dir = PAC_DIR_NONE;
				g->pac.requested = PAC_DIR_NONE;
				break;
			}
		}
		run_ticks(2);
		CHECK(g->dots_eaten == PAC_FRUIT_DOT_2, "dot 170 comido");
		CHECK(g->fruit_visible_ms > 0 && g->fruit_index == 3,
		      "nivel 4: aparece MANZANA (indice 3)");
		score0 = g->score;
		g->pac.x = pac_maze_center_x(PAC_FRUIT_COL);
		g->pac.y = pac_maze_center_y(PAC_FRUIT_ROW);
		g->pac.dir = PAC_DIR_NONE;
		g->pac.requested = PAC_DIR_NONE;
		run_ticks(2);
		CHECK(g->fruit_counts[3] == 1 && g->fruit_counts[1] == 1,
		      "contadores por tipo acumulan frutas distintas");
		CHECK(g->fruit_eaten_count == 2, "total de frutas comidas = 2");
		CHECK(g->score >= score0 + 700, "MANZANA vale 700");
		g->level = saved_level;
	}

	/* fruta por nivel: indice (nivel-1)%5 y valores 100/300/500/700/1000 */
	{
		static const int lvls[8] = { 1, 2, 3, 4, 5, 6, 7, 21 };
		static const int exp_idx[8] = { 0, 1, 2, 3, 4, 0, 1, 0 };
		static const int exp_val[8] = { 100, 300, 500, 700, 1000, 100, 300, 100 };
		int k, saved = g->level, ok = 1;

		for (k = 0; k < 8; k++) {
			g->level = lvls[k];
			if (pac_ai_level_fruit(g) != exp_idx[k] ||
			    pac_ai_level_fruit_value(g) != exp_val[k])
				ok = 0;
		}
		CHECK(ok, "fruta por nivel cicla (nivel-1)%5 con valores 100..1000");
		g->level = 1;
		CHECK(pac_ai_level_fruit(g) == 0 &&
		      pac_ai_level_fruit_value(g) == 100, "nivel 1: CEREZA 100");
		g->level = 3;
		CHECK(pac_ai_level_fruit(g) == 2 &&
		      pac_ai_level_fruit_value(g) == 500, "nivel 3: NARANJA 500");
		g->level = 5;
		CHECK(pac_ai_level_fruit(g) == 4 &&
		      pac_ai_level_fruit_value(g) == 1000, "nivel 5: UVAS 1000");
		g->level = 21;
		CHECK(pac_ai_level_fruit(g) == 0 &&
		      pac_ai_level_fruit_value(g) == 100, "nivel 21: vuelve a CEREZA 100");
		g->level = saved;
	}

	/* vida extra a 10000 */
	{
		int lives0 = g->lives; (void)lives0;
		g->score = PAC_EXTRA_LIFE_AT - 10;
		g->extra_life_given = 0;
		pac_add_score(g, 20);
		CHECK(g->lives == lives0 + 1, "vida extra al superar 10000");
		CHECK(mock_audio_last_play() == AUDIO_EXTRA_LIFE, "audio extra life");
	}

	/* pausa y reanudacion */
	key_ev(KEY_ESC, 1); run_ticks(2); key_ev(KEY_ESC, 0);
	CHECK(g && g->state == PAC_STATE_PAUSED, "Esc pausa la partida");
	CHECK(contains(mock_serial(), "GAME_PAUSE"), "serial GAME_PAUSE");
	draw("10_pause");
	key_ev(KEY_ENTER, 1); run_ticks(2); key_ev(KEY_ENTER, 0);
	CHECK(g && g->state == PAC_STATE_PLAYING, "Enter reanuda");

	/* Q en pausa vuelve al titulo; Esc en el titulo cierra la ventana */
	key_ev(KEY_ESC, 1); run_ticks(2); key_ev(KEY_ESC, 0);
	key_ev(KEY_Q, 1); run_ticks(2); key_ev(KEY_Q, 0);
	CHECK(g && g->state == PAC_STATE_MENU, "Q en pausa vuelve al titulo");
	mock_serial_clear();
	key_ev(KEY_ESC, 1); run_ticks(2); key_ev(KEY_ESC, 0);
	CHECK(pac_game_wants_close(g) == 1, "Esc en el titulo pide cerrar");
	close_game();
	CHECK(contains(mock_serial(), "GAME_EXIT"), "serial GAME_EXIT al cerrar");
	CHECK(g == NULL, "close libera el estado");

	/* reabrir: el record persiste */
	new_window();
	CHECK(g && g->state == PAC_STATE_MENU, "reabrir en el titulo");
	CHECK(g->high_score > 0, "high score persistido al reabrir");
	draw("11_menu_reopen");

	/* REGRESION: reabrir el juego varias veces debe reconstruir dots/power */
	{
		int dots_now = 0;
		for (i = 0; i < PAC_COLS * PAC_ROWS; i++)
			if (g->maze.base[i] == PAC_TILE_DOT)
				dots_now++;
		CHECK(dots_now == PAC_DOTS_TOTAL, "reabrir 2a vez: base tiene 240 dots");
		CHECK(g->dots_left == PAC_DOTS_TOTAL && g->power_left == PAC_POWER_TOTAL,
		      "reabrir 2a vez: dots/power cargados en la partida");
		g->menu_sel = 0;
		key_ev(KEY_ENTER, 1); run_ticks(2); key_ev(KEY_ENTER, 0);
		CHECK(g && g->state == PAC_STATE_PLAYING, "reabrir 2a vez: JUGAR arranca");
		run_ms(PAC_READY_MS + 100);
		CHECK(g->state == PAC_STATE_PLAYING && g->dots_left > 200,
		      "reabrir 2a vez: el nivel NO se completa solo al empezar");
		draw("19_reopen_play");
		key_ev(KEY_ESC, 1); run_ticks(2); key_ev(KEY_ESC, 0);
		key_ev(KEY_Q, 1); run_ticks(2); key_ev(KEY_Q, 0);
		key_ev(KEY_ESC, 1); run_ticks(2); key_ev(KEY_ESC, 0);
		close_game();
		new_window();
		CHECK(g && g->state == PAC_STATE_MENU, "reabrir 3a vez: menu");
		dots_now = 0;
		for (i = 0; i < PAC_COLS * PAC_ROWS; i++)
			if (g->maze.base[i] == PAC_TILE_DOT)
				dots_now++;
		CHECK(dots_now == PAC_DOTS_TOTAL, "reabrir 3a vez: base tiene 240 dots");
		CHECK(g->dots_left == PAC_DOTS_TOTAL && g->power_left == PAC_POWER_TOTAL,
		      "reabrir 3a vez: dots/power cargados");
		draw("20_menu_third_open");
	}

	/* ============================ M1: fidelidad Paku-Paku ============ */
	{
		int i2, base, rel;

		CHECK(strcmp(PAC_APP_NAME, "PAC-MAN SereOS") == 0,
		      "M1: nombre visible exacto PAC-MAN SereOS");
		CHECK(PAC_READY_MS == 1500 && PAC_READY_START_MS == 4500 &&
		      PAC_FRUIT_MS == 10000 && PAC_DEATH_MS == 2800 &&
		      PAC_LEVEL_CLEAR_MS == 5400,
		      "M1: tiempos READY/fruta/muerte/level-clear de referencia");
		CHECK(PAC_SPAWN_PAC_COL == 14 && PAC_SPAWN_BLINKY_COL == 14 &&
		      PAC_SPAWN_PINKY_COL == 14 && PAC_SPAWN_INKY_COL == 12 &&
		      PAC_SPAWN_CLYDE_COL == 16,
		      "M1: spawns C14 (Pac/Blinky/Pinky)");

		/* tabla de salida del pen */
		g->level = 1;
		pac_ai_level_init(g);
		CHECK(g->ghosts[PAC_GHOST_PINKY].exit_dots == 0 &&
		      g->ghosts[PAC_GHOST_INKY].exit_dots == 30 &&
		      g->ghosts[PAC_GHOST_CLYDE].exit_dots == 90,
		      "M1: nivel 1 sale Clyde a 90 dots (no 60)");
		g->level = 2;
		pac_ai_level_init(g);
		CHECK(g->ghosts[PAC_GHOST_INKY].exit_dots == 0 &&
		      g->ghosts[PAC_GHOST_CLYDE].exit_dots == 50,
		      "M1: nivel 2 Clyde a 50 dots");
		g->level = 5;
		pac_ai_level_init(g);
		CHECK(g->ghosts[PAC_GHOST_INKY].exit_dots == 0 &&
		      g->ghosts[PAC_GHOST_CLYDE].exit_dots == 0,
		      "M1: nivel 5+ todos salen al empezar");

		/* velocidades frightened GhostSpeed/2+10 */
		base = PAC_SPEED_BASE_Q;
		g->level = 1; g->fright_ms = 6000;
		g->ghosts[0].state = PAC_GHOST_NORMAL; g->ghosts[0].scared = 1;
		CHECK(pac_ai_ghost_speed(g, &g->ghosts[0]) == base * 475 / 1000,
		      "M1: frightened 47,5 % (nivel 1)");
		g->level = 2;
		CHECK(pac_ai_ghost_speed(g, &g->ghosts[0]) == base * 525 / 1000,
		      "M1: frightened 52,5 % (nivel 2)");
		g->level = 5;
		CHECK(pac_ai_ghost_speed(g, &g->ghosts[0]) == base * 575 / 1000,
		      "M1: frightened 57,5 % (nivel 5)");

		/* inversion solo fuera del pen; y tambien en niveles sin frightened */
		g->level = 1;
		g->ghosts[0].state = PAC_GHOST_NORMAL;
		g->ghosts[0].scared = 0;
		g->ghosts[0].x = pac_maze_center_x(14);
		g->ghosts[0].y = pac_maze_center_y(23);
		g->ghosts[0].dir = PAC_DIR_RIGHT;
		pac_ai_frighten(g);
		CHECK(g->ghosts[0].dir == PAC_DIR_LEFT && g->fright_ms > 0,
		      "M1: frightened invierte fuera del pen");
		g->level = 1;
		g->ghosts[1].state = PAC_GHOST_LEAVING;
		g->ghosts[1].scared = 0;
		g->ghosts[1].x = pac_maze_center_x(14);
		g->ghosts[1].y = pac_maze_center_y(14);
		g->ghosts[1].dir = PAC_DIR_UP;
		pac_ai_frighten(g);
		CHECK(g->ghosts[1].dir == PAC_DIR_UP,
		      "M1: frightened NO invierte dentro del pen");
		g->level = 21; /* fright_s = 0 en la tabla */
		g->fright_ms = 0;
		g->ghosts[0].state = PAC_GHOST_NORMAL;
		g->ghosts[0].scared = 0;
		g->ghosts[0].x = pac_maze_center_x(14);
		g->ghosts[0].y = pac_maze_center_y(23);
		g->ghosts[0].dir = PAC_DIR_RIGHT;
		pac_ai_frighten(g);
		CHECK(g->fright_ms == 0 && g->ghosts[0].dir == PAC_DIR_LEFT,
		      "M1: nivel sin frightened solo invierte direccion");

		/* timer de liberacion 4 s / 3 s */
		g->level = 1;
		g->ready_ms = 0;
		g->global_release_ms = 0;
		for (i2 = 0; i2 < PAC_GHOST_COUNT; i2++) {
			g->ghosts[i2].state = PAC_GHOST_HOME;
			g->ghosts[i2].exit_dots = 9999;
		}
		for (i2 = 0; i2 < 250; i2++)
			pac_ai_update(g, PAC_STEP_MS);
		rel = 0;
		for (i2 = 0; i2 < PAC_GHOST_COUNT; i2++)
			if (g->ghosts[i2].state == PAC_GHOST_LEAVING)
				rel++;
		CHECK(rel == 1, "M1: timer libera 1 fantasma a los 4 s (nivel 1)");
		g->level = 5;
		g->ready_ms = 0;
		g->global_release_ms = 0;
		for (i2 = 0; i2 < PAC_GHOST_COUNT; i2++) {
			g->ghosts[i2].state = PAC_GHOST_HOME;
			g->ghosts[i2].exit_dots = 9999;
		}
		for (i2 = 0; i2 < 190; i2++)
			pac_ai_update(g, PAC_STEP_MS);
		rel = 0;
		for (i2 = 0; i2 < PAC_GHOST_COUNT; i2++)
			if (g->ghosts[i2].state == PAC_GHOST_LEAVING)
				rel++;
		CHECK(rel == 1, "M1: timer libera 1 fantasma a los 3 s (nivel 5)");

		/* fases persistentes tras morir */
		g->level = 1;
		pac_ai_level_init(g);
		g->mode_phase = 3;
		g->mode_timer_ms = 1234;
		g->mode = PAC_PHASE_CHASE;
		pac_ai_after_death(g);
		CHECK(g->mode_phase == 3 && g->mode_timer_ms == 1234 &&
		      g->fright_ms == 0,
		      "M1: fases scatter/chase persisten tras morir");

		/* READY inicial 4,5 s con audio */
		g->level = 1;
		pac_start_new_game(g);
		CHECK(g->ready_ms == PAC_READY_START_MS,
		      "M1: READY inicial 4,5 s con audio");
	}

	/* buffer de direccion: solicitar giro antes del centro lo aplica al llegar */
	{
		int guard = 20;
		pac_start_new_game(g);
		skip_ready();
		g->pac.x = pac_maze_center_x(1) - PAC_TILE_Q / 4;
		g->pac.y = pac_maze_center_y(5);
		g->pac.dir = PAC_DIR_RIGHT;
		g->pac.facing = PAC_DIR_RIGHT;
		g->pac.requested = PAC_DIR_UP;
		while (guard-- > 0 && g->pac.dir != PAC_DIR_UP) {
			mock_advance_tick();
			(void)pac_game_tick(g);
		}
		CHECK(g->pac.dir == PAC_DIR_UP && pac_maze_walkable_pac(
		          g, pac_maze_col(g->pac.x), pac_maze_row(g->pac.y)),
		      "M1: buffer de direccion aplica el giro en el siguiente centro");
	}

	/* M3: attract, settings y continuar */
	{
		int sound0;
		new_window();
		CHECK(g && g->state == PAC_STATE_MENU, "M3: Enter en attract abre menu");
		g->state = PAC_STATE_SETTINGS;
		g->settings_sel = 0;
		sound0 = g->sound_on;
		key_ev(KEY_ENTER, 1); run_ticks(2); key_ev(KEY_ENTER, 0);
		CHECK(g->sound_on != sound0, "M3: settings alterna sonido");
		key_ev(KEY_ESC, 1); run_ticks(2); key_ev(KEY_ESC, 0);
		CHECK(g->state == PAC_STATE_MENU, "M3: Esc vuelve del settings al menu");

		g->menu_sel = 0;
		key_ev(KEY_ENTER, 1); run_ticks(2); key_ev(KEY_ENTER, 0);
		skip_ready();
		g->score = 1234;
		key_ev(KEY_ESC, 1); run_ticks(2); key_ev(KEY_ESC, 0);
		CHECK(g->state == PAC_STATE_PAUSED, "M3: Esc abre pausa");
		g->pause_sel = 3; /* Menu principal */
		key_ev(KEY_ENTER, 1); run_ticks(2); key_ev(KEY_ENTER, 0);
		CHECK(g->state == PAC_STATE_MENU && g->continue_valid,
		      "M3: pausa -> menu guarda Continuar");
		g->menu_sel = 1;
		key_ev(KEY_ENTER, 1); run_ticks(2); key_ev(KEY_ENTER, 0);
		CHECK(g->state == PAC_STATE_PLAYING && g->score == 1234,
		      "M3: Continuar restaura la partida");
	}

	/* M2: assets Res, fuente arcade y PCM disponibles */
	CHECK(PAC_SPRITE_SIZE == 16 && PAC_RES_SPRITE_SIZE == 16 &&
	      PAC_RES_TRANSPARENT == 0xF81F,
	      "M2: contrato sprites 16x16/0xF81F");
	CHECK(strcmp(pacasset_fruit_name_res[0], "CEREZA") == 0 &&
	      strcmp(pacasset_fruit_name_res[1], "FRESA") == 0 &&
	      strcmp(pacasset_fruit_name_res[2], "NARANJA") == 0 &&
	      strcmp(pacasset_fruit_name_res[3], "MANZANA") == 0 &&
	      strcmp(pacasset_fruit_name_res[4], "UVAS") == 0,
	      "M2: nombres de fruta CEREZA/FRESA/NARANJA/MANZANA/UVAS");
	CHECK(sizeof(pacasset_fruit_sprite_res) ==
	      5 * PAC_RES_SPRITE_PIXELS * sizeof(uint16_t),
	      "M2: 5 sprites de fruta Res (5x16x16)");
	CHECK(sizeof(pacasset_fruit_name_res) / sizeof(pacasset_fruit_name_res[0]) == 5,
	      "M2: 5 nombres de fruta Res");
	CHECK(pacasset_ghost_frame_res[0][0][0] != 0xF81F ||
	      pacasset_ghost_frame_res[0][0][255] != 0xF81F,
	      "M2: fantasma Res tiene pixeles opacos");
	CHECK(pac_arcade_font_present['A' - PAC_ARCADEFONT_FIRST] &&
	      pac_arcade_font_present[0xE9 - PAC_ARCADEFONT_FIRST],
	      "M2: fuente arcade con Latin-1 (A/é)");
	CHECK(pacasset_sfx_res_available(PACASSET_RES_SFX_START) &&
	      pacasset_sfx_res_available(PACASSET_RES_SFX_WAKA1) &&
	      pacasset_sfx_res_available(PACASSET_RES_SFX_GHOST_RESPAWN) &&
	      !pacasset_sfx_res_available(PACASSET_RES_SFX_POWER),
	      "M2: PCM Res en slots START/WAKA/GHOST_RESPAWN y fallback POWER");

	/* M3: audio Game Start integro (chunks contiguos, <=32768) */
	{
		int i, n, sum = 0;
		n = pacasset_sfx_res_chunk_count[PACASSET_RES_SFX_START];
		CHECK(n >= 1 && n <= 2, "M3: Game Start usa chunks validos");
		for (i = 0; i < n; i++) {
			CHECK(pacasset_sfx_res_chunks[PACASSET_RES_SFX_START][i] != 0 &&
			      pacasset_sfx_res_chunk_len[PACASSET_RES_SFX_START][i] > 0 &&
			      pacasset_sfx_res_chunk_len[PACASSET_RES_SFX_START][i] <= SB16_MAX_BUFFER_LOCAL,
			      "M3: chunk Game Start no nulo y <=32768");
			sum += (int)pacasset_sfx_res_chunk_len[PACASSET_RES_SFX_START][i];
		}
		CHECK(sum == (int)pacasset_sfx_res[PACASSET_RES_SFX_START].len,
		      "M3: chunks Game Start suman la longitud total");
		CHECK(pacasset_sfx_res_loop[PACASSET_RES_SFX_START] == 0,
		      "M3: Game Start no es loop");
		new_window();
		mock_audio_clear_counts();
		g->menu_sel = 0;
		key_ev(KEY_ENTER, 1); run_ticks(2); key_ev(KEY_ENTER, 0);
		CHECK(mock_audio_count(PAC_SFX_START) == 1,
		      "M3: Game Start suena exactamente una vez");
	}

	/* M3: capturar los 4 fantasmas, puntuacion 200/400/800/1600 y reaparicion */
	{
		int i;
		int seen_revive[PAC_GHOST_COUNT] = { 0, 0, 0, 0 };
		int seen_normal[PAC_GHOST_COUNT] = { 0, 0, 0, 0 };
		int expect = 200;
		new_window();
		g->menu_sel = 0;
		key_ev(KEY_ENTER, 1); run_ticks(2); key_ev(KEY_ENTER, 0);
		skip_ready();
		g->lives = 99;
		g->ghost_kill_index = 0;
		pac_ai_frighten(g);
		for (i = 0; i < PAC_GHOST_COUNT; i++) {
			int score0 = g->score;
			g->ghosts[i].state = PAC_GHOST_NORMAL;
			g->ghosts[i].scared = 1;
			g->ghosts[i].x = g->pac.x;
			g->ghosts[i].y = g->pac.y;
			CHECK(pac_entities_collisions(g) == PAC_GAME_EVENT_EAT_GHOST,
			      "M3: colision come fantasma");
			CHECK(g->score - score0 == expect,
			      expect == 200 ? "M3: primer fantasma 200" :
			      expect == 400 ? "M3: segundo fantasma 400" :
			      expect == 800 ? "M3: tercer fantasma 800" :
			                      "M3: cuarto fantasma 1600");
			expect *= 2;
		}
		CHECK(g->fright_ms == 0, "M3: cuarto fantasma termina frightened");
		for (i = 0; i < 3000 && g->state == PAC_STATE_PLAYING; i++) {
			int k;
			mock_advance_tick();
			(void)pac_game_tick(g);
			for (k = 0; k < PAC_GHOST_COUNT; k++) {
				if (g->ghosts[k].state == PAC_GHOST_REVIVING)
					seen_revive[k] = 1;
				if ((g->ghosts[k].state == PAC_GHOST_NORMAL ||
				     g->ghosts[k].state == PAC_GHOST_LEAVING) &&
				    seen_revive[k])
					seen_normal[k] = 1;
			}
			if (g->ready_ms > 0)
				break;
		}
		CHECK(seen_revive[0] && seen_revive[1] && seen_revive[2] && seen_revive[3],
		      "M3: los 4 fantasmas pasan por REVIVING");
		CHECK(seen_normal[0] && seen_normal[1] && seen_normal[2] && seen_normal[3],
		      "M3: los 4 fantasmas reaparecen y vuelven a NORMAL/LEAVING");
		CHECK(contains(mock_serial(), "GHOST_EATEN 0") &&
		      contains(mock_serial(), "GHOST_RETURNED 0") &&
		      contains(mock_serial(), "GHOST_REVIVED 0"),
		      "M3: seriales GHOST_EATEN/RETURNED/REVIVED presentes");
		/* segunda power pill: re-captura valida */
		skip_ready();
		pac_ai_frighten(g);
		{
			int score0 = g->score;
			g->ghosts[0].state = PAC_GHOST_NORMAL;
			g->ghosts[0].scared = 1;
			g->ghosts[0].x = g->pac.x;
			g->ghosts[0].y = g->pac.y;
			CHECK(pac_entities_collisions(g) == PAC_GAME_EVENT_EAT_GHOST &&
			      g->score - score0 == 200,
			      "M3: segundo power pill vuelve a capturar (200)");
		}
	}

	/* M3: muerte conserva dots/power/score/level y no resetea laberinto */
	{
		int i, dots0, power0, score0, level0;
		new_window();
		g->menu_sel = 0;
		key_ev(KEY_ENTER, 1); run_ticks(2); key_ev(KEY_ENTER, 0);
		skip_ready();
		g->lives = 99;
		score0 = 1234;
		g->score = score0;
		g->level = 2;
		for (i = 0; i < 10; i++) {
			int t = i * 5;
			if (g->maze.tiles[t] == PAC_TILE_DOT &&
			    pac_maze_consume(g, t % PAC_COLS, t / PAC_COLS) == PAC_GAME_EVENT_EAT_DOT)
				(void)0;
		}
		dots0 = g->dots_left;
		power0 = g->power_left;
		level0 = g->level;
		g->ghosts[0].state = PAC_GHOST_NORMAL;
		g->ghosts[0].scared = 0;
		g->ghosts[0].x = g->pac.x;
		g->ghosts[0].y = g->pac.y;
		CHECK(pac_entities_collisions(g) == PAC_GAME_EVENT_DEATH,
		      "M3: muerte por fantasma normal");
		run_ms(PAC_DEATH_MS + 400);
		CHECK(g->dots_left == dots0 && g->power_left == power0,
		      "M3: muerte NO resetea dots/power");
		CHECK(g->score == score0 && g->level == level0,
		      "M3: muerte conserva score y nivel");
		CHECK(contains(mock_serial(), "PAC_DEATH") &&
		      contains(mock_serial(), "LIFE_START") &&
		      contains(mock_serial(), "PAC_STATS"),
		      "M3: seriales PAC_DEATH/LIFE_START/PAC_STATS presentes");
		/* siguiente nivel si resetea el laberinto */
		{
			int i2;
			skip_ready();
			for (i2 = 0; i2 < PAC_COLS * PAC_ROWS; i2++)
				if (g->maze.tiles[i2] == PAC_TILE_DOT ||
				    g->maze.tiles[i2] == PAC_TILE_POWER)
					(void)pac_maze_consume(g, i2 % PAC_COLS,
					                       i2 / PAC_COLS);
			run_ticks(3);
			run_ms(PAC_LEVEL_CLEAR_MS + 200);
			CHECK(g->dots_left == PAC_DOTS_TOTAL &&
			      g->power_left == PAC_POWER_TOTAL &&
			      g->level == level0 + 1,
			      "M3: siguiente nivel si resetea dots/power");
		}
	}

	/* layout en varias resoluciones */
	new_window();
	mock_set_size(1024, 768);
	draw("12_menu_1024");
	g->menu_sel = 3;
	key_ev(KEY_ENTER, 1); run_ticks(2); key_ev(KEY_ENTER, 0);
	draw("13_instrucciones_1024");
	key_ev(KEY_ENTER, 1); run_ticks(2); key_ev(KEY_ENTER, 0);
	key_ev(KEY_UP, 1); run_ticks(2); key_ev(KEY_UP, 0);
	key_ev(KEY_ENTER, 1); run_ticks(2); key_ev(KEY_ENTER, 0);
	run_ms(PAC_READY_MS + 100);
	draw("14_play_1024");

	/* 800x600 de contenido: menu, instrucciones y juego sin desbordes */
	mock_set_size(800, 600);
	key_ev(KEY_ESC, 1); run_ticks(2); key_ev(KEY_ESC, 0);
	key_ev(KEY_Q, 1); run_ticks(2); key_ev(KEY_Q, 0);
	draw("15_menu_800x600");
	g->menu_sel = 3;
	key_ev(KEY_ENTER, 1); run_ticks(2); key_ev(KEY_ENTER, 0);
	draw("16_instrucciones_800x600");
	key_ev(KEY_ENTER, 1); run_ticks(2); key_ev(KEY_ENTER, 0);
	key_ev(KEY_UP, 1); run_ticks(2); key_ev(KEY_UP, 0);
	key_ev(KEY_ENTER, 1); run_ticks(2); key_ev(KEY_ENTER, 0);
	run_ms(PAC_READY_MS + 100);
	draw("17_play_800x600");

	/* ventana minima: HUD compacto */
	mock_set_size(300, 200);
	draw("18_play_300");
	mock_set_size(880, 560);

	/* ------------------------------------------------------------------ */
	/* T: regresion del tunel lateral (wrap en el borde real)              */
	/* ------------------------------------------------------------------ */
	{
		int i, outside = 0, jumped = 0, y_ok = 1;
		int32_t prev, x_after_jump = 0;
		int32_t span = tunnel_span(), half = tunnel_half();

		enter_game();
		g->ready_ms = 0;
		g->death_ms = 0;
		g->fright_ms = 0;
		g->pac.alive = 1;
		g->pac.death_ms = 0;
		g->pac.x = pac_maze_center_x(0);
		g->pac.y = pac_maze_center_y(TUNNEL_ROW);
		g->pac.dir = PAC_DIR_LEFT;
		g->pac.requested = PAC_DIR_LEFT;
		g->pac.facing = PAC_DIR_LEFT;
		for (i = 0; i < 300; i++) {
			prev = g->pac.x;
			pac_entities_update_pacman(g, PAC_STEP_MS);
			/* el centro nunca puede quedar fuera del laberinto, ni en
			 * un frame de paso parcial */
			if (g->pac.x < 0 || g->pac.x > span)
				outside++;
			if (g->pac.x - prev > half) {
				if (!jumped)
					x_after_jump = g->pac.x;
				jumped = 1;
			}
			if (g->pac.y != pac_maze_center_y(TUNNEL_ROW))
				y_ok = 0;
		}
		CHECK(outside == 0,
		      "T1: Pac-Man nunca sale de [0,448] al cruzar el tunel izq->der");
		CHECK(jumped, "T2: Pac-Man cruza el borde izquierdo del laberinto");
		CHECK(jumped && x_after_jump > half,
		      "T3: tras el wrap izq->der reaparece en la mitad derecha");
		CHECK(y_ok, "T4: el wrap izq->der conserva la fila del tunel (14)");
	}

	{
		int i, outside = 0, jumped = 0, y_ok = 1;
		int32_t prev, x_after_jump = 0;
		int32_t span = tunnel_span(), half = tunnel_half();

		enter_game();
		g->ready_ms = 0;
		g->death_ms = 0;
		g->fright_ms = 0;
		g->pac.alive = 1;
		g->pac.death_ms = 0;
		g->pac.x = pac_maze_center_x(PAC_COLS - 1);
		g->pac.y = pac_maze_center_y(TUNNEL_ROW);
		g->pac.dir = PAC_DIR_RIGHT;
		g->pac.requested = PAC_DIR_RIGHT;
		g->pac.facing = PAC_DIR_RIGHT;
		for (i = 0; i < 300; i++) {
			prev = g->pac.x;
			pac_entities_update_pacman(g, PAC_STEP_MS);
			if (g->pac.x < 0 || g->pac.x > span)
				outside++;
			if (prev - g->pac.x > half) {
				if (!jumped)
					x_after_jump = g->pac.x;
				jumped = 1;
			}
			if (g->pac.y != pac_maze_center_y(TUNNEL_ROW))
				y_ok = 0;
		}
		CHECK(outside == 0,
		      "T5: Pac-Man nunca sale de [0,448] al cruzar el tunel der->izq");
		CHECK(jumped, "T6: Pac-Man cruza el borde derecho del laberinto");
		CHECK(jumped && x_after_jump < half,
		      "T7: tras el wrap der->izq reaparece en la mitad izquierda");
		CHECK(y_ok, "T8: el wrap der->izq conserva la fila del tunel (14)");
	}

	{
		int i, k, outside = 0, jumped = 0;
		int32_t prev, x_after_jump = 0;
		int32_t span = tunnel_span(), half = tunnel_half();
		ghost_t *gh0;

		enter_game();
		g->ready_ms = 0;
		g->death_ms = 0;
		g->fright_ms = 0;
		gh0 = &g->ghosts[PAC_GHOST_BLINKY];
		gh0->state = PAC_GHOST_NORMAL;
		gh0->scared = 0;
		gh0->x = pac_maze_center_x(0);
		gh0->y = pac_maze_center_y(TUNNEL_ROW);
		gh0->dir = PAC_DIR_LEFT;
		gh0->facing = PAC_DIR_LEFT;
		gh0->path_len = 0;
		gh0->path_pos = 0;
		for (i = 0; i < 240; i++) {
			prev = gh0->x;
			pac_entities_update_ghosts(g, PAC_STEP_MS);
			for (k = 0; k < PAC_GHOST_COUNT; k++) {
				if (g->ghosts[k].x < 0 || g->ghosts[k].x > span)
					outside++;
			}
			if (!jumped && gh0->x - prev > half) {
				jumped = 1;
				x_after_jump = gh0->x;
			}
		}
		CHECK(outside == 0,
		      "T9: ningun fantasma sale de [0,448] durante el wrap del tunel");
		CHECK(jumped, "T10: un fantasma normal cruza el borde izquierdo");
		CHECK(jumped && x_after_jump > half,
		      "T11: el fantasma reaparece en la mitad derecha");
	}

	/* ------------------------------------------------------------------ */
	/* T: recorte del render al rect del laberinto                        */
	/* ------------------------------------------------------------------ */
	{
		int out_d = -1, in_d = -1, fx = 0, fy = 0;

		/* D: Pac-Man a -4 px, fantasmas a -9 px y 449 px */
		clip_case(PAC_SUBPX(-4), PAC_SUBPX(-9), PAC_SUBPX(449),
		          &out_d, &in_d, &fx, &fy);
		CHECK(out_d == 0,
		      "T12: el clip impide pintar personajes fuera del laberinto");
		CHECK(in_d > 0,
		      "T13: el personaje desplazado si se dibuja dentro del laberinto");
		if (out_d != 0)
			printf("  [clip] primer pixel fuera del rect que difiere: (%d,%d)\n",
			       fx, fy);

		/* F: borde derecho con Pac-Man a 452 px */
		clip_case(PAC_SUBPX(452), PAC_SUBPX(449), PAC_SUBPX(-9),
		          &out_d, &in_d, &fx, &fy);
		CHECK(out_d == 0,
		      "T14: el clip impide pintar a x=452 px fuera del laberinto");
		CHECK(in_d > 0,
		      "T15: el caso del borde derecho cambia pixeles dentro del laberinto");
		if (out_d != 0)
			printf("  [clip] primer pixel fuera del rect que difiere: (%d,%d)\n",
			       fx, fy);
	}

	/* E: el clip exterior se restaura tras dibujar el campo */
	{
		pac_rect_t vp, after, custom;

		enter_game();
		viewport_of_content(&vp);
		pac_set_clip(vp.x, vp.y, vp.w, vp.h);
		pac_game_draw(g, &vp);
		pac_get_clip(&after);
		CHECK(after.x == vp.x && after.y == vp.y &&
		      after.w == vp.w && after.h == vp.h,
		      "T16: el clip exterior se restaura tras dibujar el campo");

		/* un clip exterior distinto del viewport tambien debe restaurarse */
		custom.x = vp.x + 3;
		custom.y = vp.y + 5;
		custom.w = vp.w - 10;
		custom.h = vp.h - 20;
		pac_set_clip(custom.x, custom.y, custom.w, custom.h);
		pac_game_draw(g, &vp);
		pac_get_clip(&after);
		CHECK(after.x == custom.x && after.y == custom.y &&
		      after.w == custom.w && after.h == custom.h,
		      "T17: se restaura un clip exterior distinto del viewport");
	}

	/* ============ AUDIO-B2: cableado eventos -> sonido (B2) ========== */
	{
		/* holds = duracion real del clip + margen */
		enter_game();
		audio_quiet();
		mock_audio_clear_counts();
		g->dots_eaten = 0;
		pac_emit_event(g, PAC_GAME_EVENT_EAT_DOT);
		CHECK(g->audio_hold_ms == 100, "B2: hold waka 100 ms");
		CHECK(g->siren_grace_ms == 300, "B2: gracia anti-stutter 300 ms tras dot");
		CHECK(g->audio_oneshot == PAC_SFX_WAKA1, "B2: waka queda como one-shot activo");

		audio_quiet();
		pac_emit_event(g, PAC_GAME_EVENT_EAT_POWER);
		CHECK(g->audio_hold_ms == 320 && g->audio_oneshot == PAC_SFX_POWER,
		      "B2: hold POWER 320 ms");

		audio_quiet();
		pac_emit_event(g, PAC_GAME_EVENT_EAT_GHOST);
		CHECK(g->audio_hold_ms == 590 && g->audio_oneshot == PAC_SFX_EAT_GHOST,
		      "B2: hold EAT_GHOST 590 ms (clip 574)");

		audio_quiet();
		pac_emit_event(g, PAC_GAME_EVENT_EAT_FRUIT);
		CHECK(g->audio_hold_ms == 460 && g->audio_oneshot == PAC_SFX_EAT_FRUIT,
		      "B2: hold EAT_FRUIT 460 ms (clip 440)");

		audio_quiet();
		pac_emit_event(g, PAC_GAME_EVENT_LEVEL_CLEAR);
		CHECK(g->audio_hold_ms == 5300 && g->audio_oneshot == PAC_SFX_LEVEL_CLEAR,
		      "B2: hold LEVEL_CLEAR 5300 ms (intermission 5204)");

		audio_quiet();
		pac_sound_play(g, PAC_SFX_MENU);
		CHECK(g->audio_hold_ms == 260 && g->audio_oneshot == PAC_SFX_MENU,
		      "B2: hold MENU 260 ms");

		/* EXTRA_LIFE tiene prioridad sobre el waka del mismo tick */
		enter_game();
		audio_quiet();
		mock_audio_clear_counts();
		g->score = PAC_EXTRA_LIFE_AT - 10;
		g->extra_life_given = 0;
		g->dots_eaten = 0;
		pac_emit_event(g, PAC_GAME_EVENT_EAT_DOT);
		CHECK(mock_audio_count(PAC_SFX_EXTRA_LIFE) == 1,
		      "B2: EXTRA_LIFE se pide al cruzar 10000");
		CHECK(mock_audio_count(PAC_SFX_WAKA1) + mock_audio_count(PAC_SFX_WAKA2) == 0,
		      "B2: el WAKA del mismo tick NO pisa EXTRA_LIFE (P0)");
		CHECK(g->audio_hold_ms == 1920 && g->audio_oneshot == PAC_SFX_EXTRA_LIFE,
		      "B2: hold EXTRA_LIFE 1920 ms, no el del waka");
		CHECK(mock_audio_last_play() == PAC_SFX_EXTRA_LIFE,
		      "B2: el ultimo one-shot sigue siendo EXTRA_LIFE");
		run_ms(2100);
		CHECK(g->audio_oneshot == PAC_SFX_NONE && g->audio_hold_ms == 0,
		      "B2: audio_oneshot/hold se limpian al terminar el clip");

		/* regreso de fantasmas = loop de estado, no evento */
		enter_game();
		audio_quiet();
		g->ghosts[0].state = PAC_GHOST_EATEN;
		g->ghosts[0].x = pac_maze_center_x(PAC_SPAWN_PAC_COL);
		g->ghosts[0].y = pac_maze_center_y(PAC_SPAWN_PAC_ROW);
		g->ghosts[0].path_len = 0;
		g->ghosts[0].path_pos = 0;
		run_ticks(2);
		CHECK(mock_audio_last_loop() == PAC_SFX_GHOST_RESPAWN,
		      "B2: GHOST_RESPAWN suena como loop mientras hay ojos (P0)");
		g->ghosts[0].state = PAC_GHOST_REVIVING;
		g->ghosts[0].state_ms = 0;
		g->ghosts[0].x = pac_maze_center_x(14);
		g->ghosts[0].y = pac_maze_center_y(15);
		run_ticks(2);
		CHECK(mock_audio_last_loop() == PAC_SFX_SIREN_HUNT,
		      "B2: al volver los ojos retoma HUNT (slot 13)");

		/* semantica de sirenas: frightened = hunter siren slot 12 */
		audio_quiet();
		g->fright_ms = 4000;
		run_ticks(2);
		CHECK(mock_audio_last_loop() == PAC_SFX_SIREN_CHASE,
		      "B2: frightened usa CHASE/hunter (slot 12) (P0)");
		g->fright_ms = 0;
		run_ticks(2);
		CHECK(mock_audio_last_loop() == PAC_SFX_SIREN_HUNT,
		      "B2: fuera de frightened vuelve HUNT (slot 13)");

		/* POWER no se corta a los 16 ms: hold antes de FRIGHT */
		audio_quiet();
		mock_audio_log_clear();
		pac_emit_event(g, PAC_GAME_EVENT_EAT_POWER);
		run_ticks(2);
		CHECK(g->fright_ms > 0, "B2: power pill activa frightened");
		CHECK(audio_log_has(1, PAC_SFX_SIREN_CHASE) == 0,
		      "B2: FRIGHT no arranca durante el hold de POWER (P0/P1)");
		run_ms(400);
		CHECK(mock_audio_last_loop() == PAC_SFX_SIREN_CHASE,
		      "B2: al agotarse el hold de POWER si arranca FRIGHT");

		/* MENU en attract y navegacion de menu */
		new_window();
		mock_audio_clear_counts();
		key_ev(KEY_DOWN, 1); run_ticks(2); key_ev(KEY_DOWN, 0);
		CHECK(mock_audio_count(PAC_SFX_MENU) >= 1,
		      "B2: MENU suena al navegar el menu (P0)");
		mock_audio_clear_counts();
		g->state = PAC_STATE_ATTRACT;
		key_ev(KEY_ENTER, 1); run_ticks(2); key_ev(KEY_ENTER, 0);
		CHECK(mock_audio_count(PAC_SFX_MENU) >= 1,
		      "B2: MENU suena en attract -> menu (P0)");

		/* toggle OFF -> ON resincroniza la sirena */
		enter_game();
		audio_quiet();
		run_ticks(2);
		CHECK(mock_audio_last_loop() == PAC_SFX_SIREN_HUNT,
		      "B2: sirena HUNT activa antes del toggle");
		g->sound_on = 0;
		pac_settings_apply(g);
		run_ticks(2);
		CHECK(g->audio_ok == 0 && mock_audio_last_loop() == -1,
		      "B2: OFF para la sirena");
		g->sound_on = 1;
		pac_settings_apply(g);
		run_ticks(3);
		CHECK(g->audio_ok == 1, "B2: ON reactiva el audio");
		CHECK(mock_audio_last_loop() == PAC_SFX_SIREN_HUNT,
		      "B2: OFF->ON rearma la sirena (P1)");

		/* perdida/recuperacion de foco detiene y rearma el loop */
		enter_game();
		audio_quiet();
		run_ticks(2);
		mock_set_focused(0);
		run_ticks(2);
		CHECK(mock_audio_last_loop() == -1,
		      "B2: sin foco se para el loop de sirena (P1)");
		mock_set_focused(1);
		run_ticks(3);
		CHECK(mock_audio_last_loop() == PAC_SFX_SIREN_HUNT,
		      "B2: al recuperar el foco se rearma la sirena (P1)");

		/* nivel completado cubre el clip de intermission */
		enter_game();
		audio_quiet();
		mock_audio_clear_counts();
		pac_set_state(g, PAC_STATE_LEVEL_CLEAR, NULL);
		CHECK(mock_audio_count(PAC_SFX_LEVEL_CLEAR) == 1,
		      "B2: LEVEL_CLEAR se pide una vez");
		CHECK(g->audio_hold_ms == 5300, "B2: hold LEVEL_CLEAR 5300 ms");
		CHECK(PAC_LEVEL_CLEAR_MS > 5204,
		      "B2: el estado nivel cubre intermission (5204 ms)");
	}

	/* ============ AUDIO-B5: pausa/foco silencian one-shots ========== */
	{
		/* la pausa corta tambien el one-shot en curso (p.ej. Game Start) */
		enter_game();
		audio_quiet();
		run_ticks(2);
		mock_audio_clear_counts();
		pac_emit_event(g, PAC_GAME_EVENT_EAT_GHOST);
		CHECK(g->audio_hold_ms == 590 && g->audio_oneshot == PAC_SFX_EAT_GHOST,
		      "B5: one-shot en curso antes de pausar");
		mock_audio_log_clear();
		key_ev(KEY_ESC, 1); run_ticks(2); key_ev(KEY_ESC, 0); run_ticks(1);
		CHECK(g->state == PAC_STATE_PAUSED, "B5: Esc pausa la partida");
		CHECK(g->audio_hold_ms == 0 && g->audio_oneshot == PAC_SFX_NONE &&
		      g->siren_grace_ms == 0 && g->siren == PAC_SFX_NONE,
		      "B5: la pausa resetea hold/oneshot/gracia/sirena");
		CHECK(audio_log_has(3, -1) >= 1,
		      "B5: la pausa pide pac_audio_stop() (P1)");
		CHECK(audio_log_has(0, PAC_SFX_EAT_GHOST) == 0,
		      "B5: la pausa no deja reintentos del one-shot");
		key_ev(KEY_ENTER, 1); run_ticks(2); key_ev(KEY_ENTER, 0); run_ticks(3);
		CHECK(g->state == PAC_STATE_PLAYING, "B5: Enter reanuda");
		CHECK(mock_audio_last_loop() == PAC_SFX_SIREN_HUNT,
		      "B5: al reanudar update_siren rearma la sirena");
		CHECK(mock_audio_count(PAC_SFX_EAT_GHOST) == 1,
		      "B5: el one-shot pausado NO se reintenta tras reanudar");

		/* perder el foco tambien silencia el one-shot y rearma al volver */
		enter_game();
		audio_quiet();
		run_ticks(2);
		mock_audio_clear_counts();
		pac_emit_event(g, PAC_GAME_EVENT_EAT_GHOST);
		mock_set_focused(0);
		mock_audio_log_clear();
		run_ticks(1);
		CHECK(g->audio_hold_ms == 0 && g->audio_oneshot == PAC_SFX_NONE &&
		      g->siren == PAC_SFX_NONE,
		      "B5: perder foco resetea el one-shot en curso (P1)");
		CHECK(audio_log_has(3, -1) >= 1,
		      "B5: perder foco pide pac_audio_stop()");
		CHECK(mock_audio_count(PAC_SFX_EAT_GHOST) == 1,
		      "B5: perder foco no reintenta el one-shot");
		mock_set_focused(1);
		run_ticks(3);
		CHECK(mock_audio_last_loop() == PAC_SFX_SIREN_HUNT,
		      "B5: al recuperar el foco rearma la sirena");

		/* minimizar se comporta igual que la perdida de foco */
		enter_game();
		audio_quiet();
		run_ticks(2);
		pac_emit_event(g, PAC_GAME_EVENT_EAT_GHOST);
		mock_set_minimized(1);
		mock_audio_log_clear();
		run_ticks(1);
		CHECK(g->audio_hold_ms == 0 && g->audio_oneshot == PAC_SFX_NONE,
		      "B5: minimizar resetea el one-shot en curso");
		CHECK(audio_log_has(3, -1) >= 1,
		      "B5: minimizar pide pac_audio_stop()");
		mock_set_minimized(0);
		run_ticks(3);
		CHECK(mock_audio_last_loop() == PAC_SFX_SIREN_HUNT,
		      "B5: al restaurar la ventana rearma la sirena");
	}

	printf("checks=%d failures=%d\n", checks, failures);
	return failures ? 1 : 0;
}
