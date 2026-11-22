/* gui/desktop.h - compositor del escritorio (barra, dock, ventanas, fondo) */
#ifndef SEREOS_DESKTOP_H
#define SEREOS_DESKTOP_H
#include "input.h"

void desktop_init(void);
void desktop_draw_all(void);            /* recompone todo el escritorio */
void desktop_tick(void);                /* procesa eventos, anima, marca frames */
void desktop_dispatch_event(const event_t *ev);
void desktop_open_app(const char *id);
void desktop_close_all(void);
void desktop_set_app_name(const char *name);

/* Navegacion adaptativa. El estado depende del WM global (¿hay alguna
 * ventana visible maximizada?), no de la ventana activa:
 *   - DESKTOP_BAR_DOCK:    dock flotante inferior + nombre de app centrado.
 *   - DESKTOP_BAR_TOPNAV:  el dock desaparece y los 5 accesos viven en el
 *                          centro de la barra superior; la ventana maximizada
 *                          llega hasta el borde inferior de la pantalla. */
typedef enum {
	DESKTOP_BAR_DOCK = 0,
	DESKTOP_BAR_TOPNAV = 1
} desktop_bar_state_t;

desktop_bar_state_t desktop_bar_state(void);
int desktop_topnav_active(void);
/* espacio vertical reservado en el borde inferior: 0 en modo topnav (sin
 * barra inferior) y DOCK_HEIGHT + DOCK_BOTTOM en modo dock. */
int desktop_bottom_inset(void);

#endif
