/* gui/cursor.h - cursor del raton compuesto sobre el backbuffer */
#ifndef SEREOS_CURSOR_H
#define SEREOS_CURSOR_H
#include <stdint.h>

void cursor_init(void);
void cursor_restore(void);       /* restaura el fondo guardado bajo el cursor */
void cursor_draw(int x, int y);  /* guarda fondo y dibuja la flecha */
int  cursor_width(void);
int  cursor_height(void);

#endif
