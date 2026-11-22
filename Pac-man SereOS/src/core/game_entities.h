/* apps/game/game_entities.h - Pac-Man y los cuatro fantasmas */
#ifndef SEREOS_GAME_ENTITIES_H
#define SEREOS_GAME_ENTITIES_H

#include "pac_game.h"

/* posiciones y estados iniciales de un nivel nuevo */
void pac_entities_init_level(pac_game_t *g);

/* recoloca a todos tras una muerte (conservando dots y puntuacion) */
void pac_entities_reset_positions(pac_game_t *g);

/* avanza a Pac-Man con su velocidad actual (movimiento en cuadricula) */
void pac_entities_update_pacman(pac_game_t *g, int dt_ms);

/* avanza a los cuatro fantasmas (IA en las intersecciones, casa, ojos) */
void pac_entities_update_ghosts(pac_game_t *g, int dt_ms);

/* colisiones Pac-Man/fantasmas; devuelve PAC_GAME_EVENT_EAT_GHOST o PAC_GAME_EVENT_DEATH */
int pac_entities_collisions(pac_game_t *g);

#endif /* SEREOS_GAME_ENTITIES_H */
