/* apps/game/assets/assets.h - sprites originales de PAC-MAN SereOS
 *
 * Todos los sprites son uint16_t RGB565, 16x16, con 0xF81F como color
 * transparente (GFX_TRANSPARENT del motor grafico). Arte original creado
 * para SereOS: NO se redistribuyen sprites de Pac-Man/Namco ni de Paku-Paku.
 * Los recursos de Paku-Paku se usaron solo como referencia de estilo.
 *
 * Direcciones: 0 = derecha, 1 = izquierda, 2 = arriba, 3 = abajo.
 * Bocas de Pacman: 0 = cerrada, 1 = semiabierta, 2 = abierta.
 * Fantasmas: colores 0 = rojo, 1 = rosa, 2 = cian, 3 = naranja.
 */
#ifndef PACMAN_SPRITES_H
#define PACMAN_SPRITES_H
#include <stdint.h>

/* Por defecto se usan los sprites definitivos derivados de Res (privado).
 * Compilar con -DPACMAN_USE_RES_ASSETS=0 para el arte original de respaldo.
 * Pac-Man, vida y llave decorativa no se sustituyen: Res no aporta PNG para
 * ellos (la llave es solo el icono del indicador de NIVEL, no una fruta). */
#ifndef PACMAN_USE_RES_ASSETS
#define PACMAN_USE_RES_ASSETS 1
#endif

#define PAC_SPRITE_SIZE 16
#define PAC_SPRITE_PIXELS (PAC_SPRITE_SIZE * PAC_SPRITE_SIZE)

extern const uint16_t pacasset_pacman_frame[4][3][PAC_SPRITE_PIXELS];
extern const uint16_t pacasset_life_sprite[PAC_SPRITE_PIXELS];
/* llave dorada decorativa del indicador de NIVEL (no es fruta) */
extern const uint16_t pacasset_key_sprite[PAC_SPRITE_PIXELS];

#if PACMAN_USE_RES_ASSETS && !defined(PACMAN_SPRITES_IMPL)
#include "sprites_res.h"
#define pacasset_ghost_frame          pacasset_ghost_frame_res
#define pacasset_ghost_fright_frame   pacasset_ghost_fright_frame_res
#define pacasset_ghost_flash_frame    pacasset_ghost_flash_frame_res
#define pacasset_ghost_eyes_frame     pacasset_ghost_eyes_frame_res
#define pacasset_fruit_sprite         pacasset_fruit_sprite_res
#define pacasset_fruit_name           pacasset_fruit_name_res
#else
extern const uint16_t pacasset_ghost_frame[4][2][PAC_SPRITE_PIXELS];
extern const uint16_t pacasset_ghost_fright_frame[2][PAC_SPRITE_PIXELS];
extern const uint16_t pacasset_ghost_flash_frame[2][PAC_SPRITE_PIXELS];
extern const uint16_t pacasset_ghost_eyes_frame[4][PAC_SPRITE_PIXELS];
extern const uint16_t pacasset_fruit_sprite[5][PAC_SPRITE_PIXELS];
extern const char *const pacasset_fruit_name[5];
#endif

#endif
