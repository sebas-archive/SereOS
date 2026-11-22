/* assets/sprites_res.h - sprites definitivos derivados de Res
 *
 * 16x16 uint16_t RGB565, transparente = 0xF81F.
 * Contrato para game-dev (integra con PACMAN_USE_RES_ASSETS):
 *   - pacasset_fruit_sprite_res[5][256]        frutas CEREZA..UVAS (indices 0..4)
 *   - pacasset_ghost_frame_res[4][2][256]      colores 0 rojo/1 rosa/2 cian/3 naranja,
 *                                              frames 0/1 de falda, ojos neutros ya compuestos
 *   - pacasset_ghost_fright_frame_res[2][256]  asustado (cuerpo azul, ojos cazados)
 *   - pacasset_ghost_flash_frame_res[2][256]   parpadeo final (cuerpo blanco)
 *   - pacasset_ghost_eyes_frame_res[4][256]    solo ojos, mirando derecha/izquierda/arriba/abajo
 *   - pacasset_fruit_name_res[5]               CEREZA..UVAS (ASCII, sin acentos)
 * Pac-Man y vida: se mantienen los actuales (Res no aporta PNG).
 * Uso privado/academico; ver assets/LICENSE_RES.md.
 */
#ifndef PACMAN_SPRITES_RES_H
#define PACMAN_SPRITES_RES_H
#include <stdint.h>

#define PAC_RES_SPRITE_SIZE   16
#define PAC_RES_SPRITE_PIXELS (PAC_RES_SPRITE_SIZE * PAC_RES_SPRITE_SIZE)
#define PAC_RES_TRANSPARENT   0xF81Fu

#define PAC_RES_GHOST_COLORS  4
#define PAC_RES_GHOST_FRAMES  2
#define PAC_RES_GHOST_EYE_DIRS 4

#define PAC_RES_GHOST_BLINKY  0
#define PAC_RES_GHOST_PINKY   1
#define PAC_RES_GHOST_INKY    2
#define PAC_RES_GHOST_CLYDE   3

#define PAC_RES_EYE_RIGHT     0
#define PAC_RES_EYE_LEFT      1
#define PAC_RES_EYE_UP        2
#define PAC_RES_EYE_DOWN      3

extern const uint16_t pacasset_fruit_sprite_res[5][PAC_RES_SPRITE_PIXELS];
extern const uint16_t pacasset_ghost_frame_res[PAC_RES_GHOST_COLORS]
                                             [PAC_RES_GHOST_FRAMES]
                                             [PAC_RES_SPRITE_PIXELS];
extern const uint16_t pacasset_ghost_fright_frame_res[PAC_RES_GHOST_FRAMES]
                                                     [PAC_RES_SPRITE_PIXELS];
extern const uint16_t pacasset_ghost_flash_frame_res[PAC_RES_GHOST_FRAMES]
                                                    [PAC_RES_SPRITE_PIXELS];
extern const uint16_t pacasset_ghost_eyes_frame_res[PAC_RES_GHOST_EYE_DIRS]
                                                   [PAC_RES_SPRITE_PIXELS];
extern const char *const pacasset_fruit_name_res[5];

extern const uint8_t pacasset_res_sprite_size;
extern const uint16_t pacasset_res_sprite_pixels;

#endif /* PACMAN_SPRITES_RES_H */
