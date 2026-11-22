/* apps/game/game_ai.h - IA de fantasmas y tabla de niveles
 *
 * Valores portados de Paku-Paku (cMazeLevel.cls / docs/reference/levels.csv):
 * velocidades por nivel, tiempos de scatter/chase, frightened y Cruise Elroy.
 */
#ifndef SEREOS_GAME_AI_H
#define SEREOS_GAME_AI_H

#include "pac_game.h"

/* prepara fase scatter/chase, velocidades y contadores de salida del nivel */
void pac_ai_level_init(pac_game_t *g);
void pac_ai_after_death(pac_game_t *g);

/* temporizadores: fases, frightened, liberacion de fantasmas de la casa */
void pac_ai_update(pac_game_t *g, int dt_ms);

/* power pill: invierte y asusta a los fantasmas que patrullan */
void pac_ai_frighten(pac_game_t *g);
void pac_ai_reverse_all(pac_game_t *g);

/* decision de direccion en el centro de un tile (fantasma normal) */
pac_dir_t pac_ai_ghost_decide(pac_game_t *g, ghost_t *gh);

/* tile objetivo segun personalidad y modo */
void pac_ai_ghost_target(const pac_game_t *g, const ghost_t *gh, int *tc, int *tr);

/* velocidades actuales en Q8.8 px/s */
int32_t pac_ai_pacman_speed(const pac_game_t *g);
int32_t pac_ai_ghost_speed(const pac_game_t *g, const ghost_t *gh);

/* datos de nivel para HUD/render */
int pac_ai_level_fruit(const pac_game_t *g);
int pac_ai_level_fruit_value(const pac_game_t *g);
int pac_ai_level_fright_ms(const pac_game_t *g);
int pac_ai_elroy(const pac_game_t *g);            /* 0, 1 o 2 */
int pac_ai_pacman_hunter(const pac_game_t *g);    /* 1 si el power esta activo */

#endif /* SEREOS_GAME_AI_H */
