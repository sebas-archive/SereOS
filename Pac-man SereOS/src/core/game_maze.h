/* apps/game/game_maze.h - laberinto 28x31 de PAC-MAN SereOS
 *
 * Portado de la referencia de Paku-Paku (docs/reference/maze.c, maze.txt):
 * 240 dots + 4 power pills, casa de fantasmas en cols 11..16 filas 13..15,
 * puerta en fila 12 cols 13..14, tuneles en la fila 14 con wrap horizontal.
 * Coordenadas de tile 0-based; centros de tile en punto fijo Q8.8.
 */
#ifndef SEREOS_GAME_MAZE_H
#define SEREOS_GAME_MAZE_H

#include <stdint.h>
#include "pac_game.h"

/* construye la tabla base, el fondo pre-renderizado y carga los dots */
void pac_maze_init(pac_game_t *g);

/* rellena la rejilla actual con los dots/power del nivel */
void pac_maze_reset(pac_game_t *g);

/* tipo de tile actual (pac_tile_t); fuera del laberinto devuelve VOID */
int pac_maze_tile(const pac_game_t *g, int col, int row);

/* transitable para Pac-Man (y para fantasmas normales fuera de la casa) */
int pac_maze_walkable_pac(const pac_game_t *g, int col, int row);
int pac_maze_walkable_ghost(const pac_game_t *g, int col, int row);
/* transitable para los ojos (incluye casa y puerta) */
int pac_maze_walkable_eyes(const pac_game_t *g, int col, int row);

int pac_maze_is_pen(int col, int row);
int pac_maze_is_gate(int col, int row);
int pac_maze_is_tunnel(const pac_game_t *g, int col, int row);

/* centros de tile en Q8.8 y conversion inversa */
int32_t pac_maze_center_x(int col);
int32_t pac_maze_center_y(int row);
static inline int pac_maze_col(int32_t x) { return (int)(PAC_PX(x) / PAC_TILE); }
static inline int pac_maze_row(int32_t y) { return (int)(PAC_PX(y) / PAC_TILE); }

/* consume el dot/power de la celda; devuelve PAC_GAME_EVENT_EAT_DOT/POWER o NONE */
int pac_maze_consume(pac_game_t *g, int col, int row);

/* fondo estatico 448x496 en 0x00RRGGBB (se pinta una vez) */
const uint32_t *pac_maze_background(void);

/* ruta BFS (direcciones) entre dos tiles para los ojos de los fantasmas */
int pac_maze_bfs(int start_col, int start_row, int goal_col, int goal_row,
                 uint8_t *dirs, int max_dirs);

int pac_maze_dot_total(void);
int pac_maze_power_total(void);

/* tablas del mapa de referencia (para render/HUD) */
const char *const *pac_maze_ascii(void);

#endif /* SEREOS_GAME_MAZE_H */
