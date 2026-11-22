/* PAC-MAN SereOS - teclado del nucleo compartido */
#ifndef PACMAN_GAME_INPUT_H
#define PACMAN_GAME_INPUT_H

#include "pac_game.h"

void pac_input_init(pac_game_t *g);
/* traduce un evento de plataforma (pac_event_t) a la logica del juego */
void pac_input_event(pac_game_t *g, const pac_event_t *ev);
/* lee teclas mantenidas de la plataforma (solo si la ventana tiene foco) */
void pac_input_begin_frame(pac_game_t *g, int focused);
/* limpia los flancos una vez procesados por el tick */
void pac_input_consume(pac_game_t *g);

#endif /* PACMAN_GAME_INPUT_H */
