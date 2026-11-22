/* PAC-MAN SereOS - render compartido (mismo codigo en SereOS y Linux) */
#ifndef PACMAN_RENDER_H
#define PACMAN_RENDER_H

#include "pac_game.h"

/* redibuja todo el contenido de la ventana en el viewport actual */
void pac_render_draw(pac_game_t *g);

/* opcion del menu bajo una coordenada absoluta de ventana; -1 si ninguna */
int pac_render_menu_hit(pac_game_t *g, int sx, int sy);

#endif /* PACMAN_RENDER_H */
