/* PAC-MAN SereOS - puente de audio del nucleo (sin backend) */
#ifndef PACMAN_GAME_AUDIO_H
#define PACMAN_GAME_AUDIO_H

#include "pac_game.h"

void pac_sound_init(pac_game_t *g);
void pac_sound_play(pac_game_t *g, int sfx);       /* pac_audio_sfx_t */
void pac_sound_set_siren(pac_game_t *g, int sfx);  /* bucle de sirena */
void pac_sound_stop(pac_game_t *g);
void pac_sound_update(pac_game_t *g);

#endif /* PACMAN_GAME_AUDIO_H */
