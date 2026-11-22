/* gui/gui.h - identidad visual de SereOS Desktop y bucle principal */
#ifndef SEREOS_GUI_H
#define SEREOS_GUI_H
#include <stdint.h>
#include "graphics.h"
#include "theme.h"
#include "text.h"

/* El tema completo vive en gui/theme.h (extern const theme_t theme).
 * gui_color_blend se declara alli. */

void gui_init(void);              /* subsistemas del escritorio */
void gui_run(void);               /* bucle principal (no retorna) */
int  gui_active(void);            /* 1 si el escritorio grafico esta activo */
void gui_request_redraw(void);    /* fuerza recompostura completa */
void gui_open_app(const char *app_id);
void gui_panic(const char *title, const char *detail);

#endif
