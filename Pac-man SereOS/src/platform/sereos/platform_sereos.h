/* PAC-MAN SereOS - interfaz interna del adaptador nativo (no publica) */
#ifndef PACMAN_PLATFORM_SEREOS_H
#define PACMAN_PLATFORM_SEREOS_H

#include "pac_platform.h"

struct window;

/* el adaptador necesita la ventana activa para foco/clip/invalidacion */
void pac_sereos_bind_window(struct window *w);
struct window *pac_sereos_window(void);

/* traduccion de codigos de tecla del OS a pac_key_t */
pac_key_t pac_sereos_map_keycode(int keycode);

#endif /* PACMAN_PLATFORM_SEREOS_H */
