/* PAC-MAN SereOS - texto arcade (Press Start K) sobre el atlas del componente */
#ifndef PACMAN_ARCADE_TEXT_H
#define PACMAN_ARCADE_TEXT_H

#include <stdint.h>

int  pac_arcade_text_width(const char *text, int scale);
void pac_arcade_text_draw(int x, int y, const char *text, uint32_t color,
                          int scale);
void pac_arcade_text_draw_center(int cx, int y, const char *text,
                                 uint32_t color, int scale);
void pac_arcade_text_draw_right(int rx, int y, const char *text,
                                uint32_t color, int scale);
/* 1 si todos los codepoints estan cubiertos por el atlas */
int  pac_arcade_text_covers(const char *text);

#endif
