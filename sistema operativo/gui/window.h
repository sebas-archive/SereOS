/* gui/window.h - gestor de ventanas del compositor
 *
 * El escritorio dibuja el marco (barra de titulo, semaforos, sombra, bordes).
 * La aplicacion dibuja solo el area de contenido: el escritorio fija el clip
 * y llama a app->draw(w). Las coordenadas de dibujo de la app son absolutas
 * de pantalla; use window_content_x/y/w/h() como origen.
 */
#ifndef SEREOS_WINDOW_H
#define SEREOS_WINDOW_H
#include <stdint.h>
#include "app.h"

struct app;

#define WINDOW_MAX 8

typedef enum {
	WIN_STATE_NORMAL = 0,
	WIN_STATE_MINIMIZED,
	WIN_STATE_MAXIMIZED
} window_state_t;

/* crea ventana y llama a app->open(). Devuelve 0 si no hay espacio. */
struct window *window_create(struct app *app, const char *title,
                             int x, int y, int w, int h);
void window_close(struct window *w);       /* cierra y libera estado */
void window_focus(struct window *w);
void window_move(struct window *w, int x, int y);
/* redimensionado interactivo (solo ventanas normales): aplica clamp a la
 * pantalla/area util y a los minimos WIN_MIN_W/H. */
void window_set_geometry(struct window *win, int x, int y, int width, int height);
void window_minimize(struct window *w);
void window_restore(struct window *w);
void window_toggle_maximize(struct window *w);
void window_set_title(struct window *w, const char *title);
void window_invalidate(struct window *w);
void window_invalidate_all(void);

/* geometria */
int window_x(struct window *w);
int window_y(struct window *w);
int window_width(struct window *w);
int window_height(struct window *w);
int window_content_x(struct window *w);
int window_content_y(struct window *w);
int window_content_w(struct window *w);
int window_content_h(struct window *w);
int window_titlebar_height(void);
int window_visible(struct window *w);
int window_minimized(struct window *w);
int window_maximized(struct window *w);
int window_active(struct window *w);
int window_min_width(void);
int window_min_height(void);

/* estado de la aplicacion dentro de la ventana */
struct app *window_app(struct window *w);
void       *window_data(struct window *w);
void        window_set_data(struct window *w, void *data);
const char *window_title(struct window *w);

/* consulta para el compositor y la entrada */
struct window *window_active_window(void);
struct window *window_at(int x, int y);        /* ventana superior en ese punto */
int            window_count(void);
struct window *window_get(int index);
int            window_needs_frame(struct window *w);
void           window_clamp_all(void);
void           window_clear_frame(struct window *w);
/* ------------------------------------------------------------------ */
/* botones del marco (UNICA fuente de metricas)                       */
/* ------------------------------------------------------------------ */
/* Los tres botones se dibujan a la DERECHA de la barra de titulo, en
 * orden izquierda->derecha: 0 = minimizar, 1 = maximizar/restaurar,
 * 2 = cerrar. Su color lo decide el compositor (ambar/verde/rojo) y el
 * glifo depende del estado (maximizar vs restaurar). */
#define WINDOW_BUTTON_COUNT 3
#define WINDOW_BUTTON_MINIMIZE 0
#define WINDOW_BUTTON_MAXIMIZE 1
#define WINDOW_BUTTON_CLOSE    2

/* centro (coordenadas de pantalla) del boton `index` en la barra de titulo */
int window_button_center(struct window *w, int index, int *x, int *y);
/* radio de los circulos de los botones (misma metrica para dibujo y hit) */
int window_button_radius(void);
/* ancho reservado a cada lado del titulo para que este quede centrado */
int window_title_side_inset(void);
/* 1 si (x,y) esta en la barra de titulo y NO sobre ningun boton: zona de
 * arrastre / doble clic a maximizar */
int window_hit_title_drag(struct window *w, int x, int y);

/* hit tests de los botones (misma metrica que window_button_center) */
int window_hit_close(struct window *w, int x, int y);
int window_hit_minimize(struct window *w, int x, int y);
int window_hit_maximize(struct window *w, int x, int y);

#endif
