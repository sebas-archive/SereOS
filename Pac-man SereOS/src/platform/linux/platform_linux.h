/* PAC-MAN SereOS - interfaz interna del backend Linux (no publica) */
#ifndef PACMAN_PLATFORM_LINUX_H
#define PACMAN_PLATFORM_LINUX_H

#include <stdint.h>
#include "pac_platform.h"

/* argumentos de linea de comandos (los llama main antes de pac_platform_init) */
void pac_linux_parse_args(int argc, char **argv);
int  pac_linux_should_quit(void);
int  pac_linux_smoke_frames(void);
const char *pac_linux_screenshot_path(void);
const char *pac_linux_scene(void);

/* guarda el framebuffer actual como PPM P6; 0 = ok */
int  pac_linux_save_ppm(const char *path);
void pac_linux_window_to_canvas(int wx, int wy, int *cx, int *cy);

/* inicializacion del motor tipografico (atrios de assets/fonts) */
void pac_linux_text_init(void);

/* primitivas internas que usa el motor tipografico */
void pac_linux_blit_alpha8(int x, int y, int w, int h,
                           const uint8_t *mask, uint32_t color);
void pac_linux_blend_pixel(int x, int y, uint32_t color, uint8_t alpha);

#endif /* PACMAN_PLATFORM_LINUX_H */
