/* PAC-MAN SereOS - estado y API interna del nucleo compartido
 *
 * Este header es PRIVADO del componente (src/core): lo usan core y render.
 * Los backends solo ven include/pacman.h (estado opaco) e
 * include/pac_platform.h. No incluye cabeceras del sistema operativo ni SDL.
 *
 * Unidades: posiciones Q8.8 (256 subpixeles por pixel) y velocidades Q8.8
 * px/s. Laberinto de 28x31 tiles de 16x16 px (448x496 px).
 */
#ifndef PACMAN_GAME_H
#define PACMAN_GAME_H

#include <stdint.h>
#include "pac_platform.h"

/* identidad visible de la aplicacion (la usa el backend SereOS) */
#define PAC_APP_ID    "game"
#define PAC_APP_NAME  "PAC-MAN SereOS"
#define PAC_APP_ICON  "game"
#define PAC_WIN_W     880
#define PAC_WIN_H     560

/* laberinto */
#define PAC_TILE       16
#define PAC_COLS       28
#define PAC_ROWS       31
#define PAC_MAZE_W     (PAC_COLS * PAC_TILE)   /* 448 px */
#define PAC_MAZE_H     (PAC_ROWS * PAC_TILE)   /* 496 px */

/* punto fijo Q8.8 */
#define PAC_SUB        256
#define PAC_SUBPX(px)  ((int32_t)(px) * PAC_SUB)
#define PAC_PX(q)      ((int32_t)(q) >> 8)
#define PAC_TILE_Q     (PAC_TILE * PAC_SUB)    /* 4096 */

/* reloj de juego: fisica fija ~62.5 Hz y presentacion a 30 fps */
#define PAC_STEP_MS        16
#define PAC_RENDER_MS      33
#define PAC_MAX_CATCHUP    6
#define PAC_MAX_ELAPSED_MS 120

/* reglas de partida */
#define PAC_LIVES_START        3
#define PAC_DOTS_TOTAL         240
#define PAC_POWER_TOTAL        4
#define PAC_READY_MS           1500
#define PAC_READY_START_MS     4500
#define PAC_DEATH_MS           2800
/* intermission.wav dura 57377 muestras @11025 = 5204 ms; el estado debe
 * cubrir el clip completo con margen antes de pasar al siguiente nivel. */
#define PAC_LEVEL_CLEAR_MS     5400
#define PAC_FRUIT_MS           10000
#define PAC_EXTRA_LIFE_AT      10000
#define PAC_FRUIT_DOT_1        70
#define PAC_FRUIT_DOT_2        170
/* frutas reales disponibles: cereza, fresa, naranja, manzana y uvas */
#define PAC_FRUIT_COUNT        5

/* velocidad base del original en el mundo de 16 px:
 * DEFAULT_SPEED = 1.25 px/frame (8 px logicos) @60fps -> 9.375 tiles/s
 * -> 150 px/s. */
#define PAC_SPEED_BASE_Q  ((int32_t)150 * PAC_SUB)   /* 38400 Q8.8 px/s */

/* aparicion en tiles 0-based (referencia maze.txt) */
#define PAC_SPAWN_PAC_COL      14
#define PAC_SPAWN_PAC_ROW      23
#define PAC_SPAWN_BLINKY_COL   14
#define PAC_SPAWN_BLINKY_ROW   11
#define PAC_SPAWN_PINKY_COL    14
#define PAC_SPAWN_PINKY_ROW    14
#define PAC_SPAWN_INKY_COL     12
#define PAC_SPAWN_INKY_ROW     14
#define PAC_SPAWN_CLYDE_COL    16
#define PAC_SPAWN_CLYDE_ROW    14
#define PAC_FRUIT_COL          14
#define PAC_FRUIT_ROW          17

/* casa de fantasmas y puerta */
#define PAC_PEN_COL0     11
#define PAC_PEN_COL1     16
#define PAC_PEN_ROW0     13
#define PAC_PEN_ROW1     15
#define PAC_DOOR_ROW     12
#define PAC_DOOR_COL0    13
#define PAC_DOOR_COL1    14

/* clave de persistencia del record en pac_platform_storage_* */
#define PAC_RECORD_KEY   "record"

/* ------------------------------------------------------------------ */
/* tipos                                                               */
/* ------------------------------------------------------------------ */
typedef enum {
	PAC_DIR_NONE = 0,
	PAC_DIR_UP,
	PAC_DIR_RIGHT,
	PAC_DIR_DOWN,
	PAC_DIR_LEFT
} pac_dir_t;

typedef enum {
	PAC_TILE_VOID = 0,
	PAC_TILE_WALL,
	PAC_TILE_GATE,
	PAC_TILE_PEN,
	PAC_TILE_PATH,
	PAC_TILE_DOT,
	PAC_TILE_POWER,
	PAC_TILE_TUNNEL
} pac_tile_t;

typedef enum {
	PAC_STATE_ATTRACT = 0,
	PAC_STATE_MENU,
	PAC_STATE_INSTRUCTIONS,
	PAC_STATE_RECORD,
	PAC_STATE_SETTINGS,
	PAC_STATE_PLAYING,
	PAC_STATE_PAUSED,
	PAC_STATE_GAMEOVER,
	PAC_STATE_LEVEL_CLEAR
} pac_state_t;

/* opciones de menu (mismo orden que el render) */
#define PAC_MENU_ITEMS   6
#define PAC_PAUSE_ITEMS  5
#define PAC_OVER_ITEMS   3
#define PAC_SETTINGS_ITEMS 2

typedef enum {
	PAC_GHOST_BLINKY = 0,   /* rojo  */
	PAC_GHOST_PINKY,        /* rosa  */
	PAC_GHOST_INKY,         /* cian  */
	PAC_GHOST_CLYDE,        /* naranja */
	PAC_GHOST_COUNT
} pac_ghost_id_t;

typedef enum {
	PAC_GHOST_HOME = 0,
	PAC_GHOST_LEAVING,
	PAC_GHOST_NORMAL,
	PAC_GHOST_EATEN,
	PAC_GHOST_REVIVING
} pac_ghost_state_t;

typedef enum {
	PAC_PHASE_SCATTER = 0,
	PAC_PHASE_CHASE = 1
} pac_phase_t;

typedef enum {
	PAC_GAME_EVENT_NONE = 0,
	PAC_GAME_EVENT_EAT_DOT,
	PAC_GAME_EVENT_EAT_POWER,
	PAC_GAME_EVENT_EAT_GHOST,
	PAC_GAME_EVENT_EAT_FRUIT,
	PAC_GAME_EVENT_DEATH,
	PAC_GAME_EVENT_EXTRA_LIFE,
	PAC_GAME_EVENT_LEVEL_CLEAR,
	PAC_GAME_EVENT_GHOST_RESPAWN
} pac_game_event_t;

typedef struct {
	int32_t x, y;          /* centro del sprite en Q8.8 px */
	pac_dir_t dir;
	pac_dir_t requested;
	pac_dir_t facing;
	int alive;
	int mouth;
	int anim_ms;
	int death_ms;
	int moving;
} pacman_t;

typedef struct {
	int32_t x, y;
	pac_dir_t dir;
	pac_dir_t facing;
	pac_ghost_state_t state;
	int scared;
	int anim_ms;
	int state_ms;
	int bob_dir;
	int start_col, start_row;
	int exit_dots;
	int64_t path_len;
	int64_t path_pos;
	uint8_t path[PAC_COLS * PAC_ROWS + 4];
} ghost_t;

typedef struct {
	pac_dir_t held_dir;
	int confirm_pressed;
	int esc_pressed;
	int up_pressed;
	int down_pressed;
	int restart_pressed;
	int quit_pressed;
	int left_pressed;
	int right_pressed;
} pac_input_t;

typedef struct {
	uint8_t base[PAC_COLS * PAC_ROWS];
	uint8_t tiles[PAC_COLS * PAC_ROWS];
} pac_maze_t;

/* estado completo del juego (opaco fuera del componente) */
struct pac_game {
	int state;
	int state_prev;
	int menu_sel;
	int pause_sel;
	int over_sel;
	int settings_sel;
	int sound_on;
	int audio_hold_ms;
	int fullscreen;
	int classic;
	int continue_valid;
	struct pac_game *continue_snapshot;

	int score;
	int high_score;
	int lives;
	int level;
	int extra_life_given;

	int dots_left;
	int power_left;
	int dots_eaten;

	int fruit_visible_ms;
	int fruit_flash_ms;
	int fruit_value;
	int fruit_index;
	int fruit_eaten_count;             /* total de frutas comidas */
	uint8_t fruit_counts[PAC_FRUIT_COUNT]; /* por tipo 0..PAC_FRUIT_COUNT-1 */

	int digest_ms;
	int ready_ms;
	int level_clear_ms;
	int death_ms;
	int popup_ms;
	int popup_x, popup_y;
	int popup_value;

	int mode;
	int mode_timer_ms;
	int mode_phase;
	int mode_phase_count;
	int phase_is_chase[8];
	int32_t phase_ms[8];
	int fright_ms;
	int ghost_kill_index;
	int global_release_ms;
	int siren;
	int audio_ok;
	int audio_oneshot;       /* one-shot con hold en curso (prioridad) */
	int siren_grace_ms;      /* silencio de sirena tras comer dots (anti-stutter) */

	uint32_t anim_ms;
	uint32_t rng;
	uint32_t last_time_ms;
	uint32_t acc_ms;
	uint32_t last_draw_ms;
	int frame;

	int wants_close;
	pac_rect_t viewport;

	pacman_t pac;
	ghost_t ghosts[PAC_GHOST_COUNT];
	pac_maze_t maze;
	pac_input_t input;
};

/* alias corto usado por los modulos internos */
typedef struct pac_game pac_game_t;
typedef pac_game_t game_t;

/* ------------------------------------------------------------------ */
/* funciones internas (game.c)                                         */
/* ------------------------------------------------------------------ */
void pac_serial(const char *marker);
void serial_ghost_marker(const char *marker, int id);           /* -> pac_platform_log */
void pac_set_state(pac_game_t *g, pac_state_t state, const char *marker);
void pac_start_new_game(pac_game_t *g);
void pac_start_level(pac_game_t *g);
void pac_add_score(pac_game_t *g, int points);
void pac_check_extra_life(pac_game_t *g);
void pac_record_load(pac_game_t *g);
void pac_record_save(pac_game_t *g);
int  pac_menu_item_enabled(const pac_game_t *g, int item);
void pac_settings_load(pac_game_t *g);
void pac_settings_save(pac_game_t *g);
void pac_settings_apply(pac_game_t *g);
void pac_emit_event(pac_game_t *g, pac_game_event_t ev);
int  pac_random(pac_game_t *g);
void pac_after_pacman_death(pac_game_t *g);

/* utilidades de direccion */
static inline pac_dir_t pac_opposite(pac_dir_t d)
{
	switch (d) {
	case PAC_DIR_UP:    return PAC_DIR_DOWN;
	case PAC_DIR_DOWN:  return PAC_DIR_UP;
	case PAC_DIR_LEFT:  return PAC_DIR_RIGHT;
	case PAC_DIR_RIGHT: return PAC_DIR_LEFT;
	default:            return PAC_DIR_NONE;
	}
}

static inline int pac_dir_dx(pac_dir_t d)
{
	if (d == PAC_DIR_RIGHT) return 1;
	if (d == PAC_DIR_LEFT) return -1;
	return 0;
}

static inline int pac_dir_dy(pac_dir_t d)
{
	if (d == PAC_DIR_DOWN) return 1;
	if (d == PAC_DIR_UP) return -1;
	return 0;
}

#endif /* PACMAN_GAME_H */
