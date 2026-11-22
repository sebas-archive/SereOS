/* gui/window.c - gestor de ventanas del compositor SereOS
 *
 * Modelo: pool de ventanas en orden z (de abajo a arriba), puntero a la
 * ventana enfocada y geometria con clamp al area util de la pantalla.
 *
 * Cierre, foco y restauracion son DIFERIDOS: las funciones publicas solo
 * marcan la intencion (pending) y window_process_pending() la aplica al
 * final del frame. Asi una aplicacion puede cerrar o enfocar ventanas desde
 * su propio callback app->event sin liberar memoria que el compositor aun
 * esta recorriendo.
 *
 * El marco (sombra, barra de titulo, semaforos) lo dibuja desktop.c; aqui
 * solo se mantiene el estado. Las apps dibujan en coordenadas absolutas de
 * pantalla y usan window_content_x/y/w/h como origen del area de contenido.
 */
#include "window.h"
#include "gui.h"
#include "theme.h"
#include "desktop.h"
#include "graphics.h"
#include "serial.h"
#include "string.h"

#define WINDOW_TITLE_MAX 48

/* Geometria de los botones del marco (UNICA fuente; desktop.c la consume a
 * traves de window_button_center()). Los botones van a la DERECHA, en orden
 * izquierda->derecha: minimizar (0), maximizar/restaurar (1), cerrar (2).
 * TRAFFIC_EDGE_X es la distancia del centro del boton exterior al borde. */
#define TRAFFIC_EDGE_X   14
#define TRAFFIC_STEP     18
#define TRAFFIC_R        5
#define TRAFFIC_HIT_R    9

struct window {
	int      used;
	int      pending_close;   /* cierre solicitado, aun no aplicado */
	int      pending_focus;   /* foco solicitado, aun no aplicado */
	int      closing;         /* proteccion contra reentrada de app->close */
	app_t   *app;
	char     title[WINDOW_TITLE_MAX];
	int      x, y, w, h;
	int      saved_x, saved_y, saved_w, saved_h;  /* rect previo a maximizar */
	int      state;           /* window_state_t */
	int      was_maximized;   /* se minimizo estando maximizada */
	int      needs_frame;     /* el contenido debe recomponerse */
	void    *data;            /* estado privado de la aplicacion */
};

static struct window  window_pool[WINDOW_MAX];
static struct window *window_order[WINDOW_MAX];  /* de abajo (0) a arriba */
static int            window_total;
static struct window *window_focused;
static struct window *window_pending_focus;

/* ------------------------------------------------------------------ */
/* utilidades internas                                                */
/* ------------------------------------------------------------------ */

static int screen_w(void) {
	int w = gfx_width();

	return (w > 0) ? w : 1024;
}

static int screen_h(void) {
	int h = gfx_height();

	return (h > 0) ? h : 768;
}

static int order_index(struct window *w) {
	int i;

	for (i = 0; i < window_total; i++) {
		if (window_order[i] == w)
			return i;
	}
	return -1;
}

static void order_remove(struct window *w) {
	int i = order_index(w);
	int k;

	if (i < 0)
		return;
	for (k = i; k + 1 < window_total; k++)
		window_order[k] = window_order[k + 1];
	window_total--;
	window_order[window_total] = 0;
}

static void order_raise(struct window *w) {
	int i;

	if (!w || !w->used)
		return;
	i = order_index(w);
	if (i < 0)
		return;
	for (; i + 1 < window_total; i++)
		window_order[i] = window_order[i + 1];
	window_order[window_total - 1] = w;
}

/* area de trabajo comun: margen lateral, bajo la barra superior y sobre la
 * barra inferior (dock flotante o barra de tareas extendida). El inset lo
 * decide el compositor con desktop_bottom_inset(), de modo que una ventana
 * maximizada ocupa exactamente entre ambas barras sin quedar debajo. */
void window_work_area(int *x, int *y, int *w, int *h) {
	int sw = screen_w();
	int sh = screen_h();
	int inset = desktop_bottom_inset();
	int wx = SP_3;
	int wy = TOPBAR_H + SP_2;
	int ww = sw - SP_3 * 2;
	int wh = sh - TOPBAR_H - SP_2 - inset;

	if (ww < WIN_MIN_W) {
		wx = 0;
		ww = sw;
	}
	if (wh < WIN_MIN_H)
		wh = sh - wy;
	if (wh < 1)
		wh = 1;
	*x = wx;
	*y = wy;
	*w = ww;
	*h = wh;
}

/* mantiene la ventana dentro del area de trabajo */
static void clamp_geometry(struct window *w) {
	int wx, wy, ww, wh;

	window_work_area(&wx, &wy, &ww, &wh);
	if (w->w > ww)
		w->w = ww;
	if (w->h > wh)
		w->h = wh;
	if (w->w < WIN_MIN_W && ww >= WIN_MIN_W)
		w->w = WIN_MIN_W;
	if (w->h < WIN_MIN_H && wh >= WIN_MIN_H)
		w->h = WIN_MIN_H;
	if (w->x < wx)
		w->x = wx;
	if (w->x + w->w > wx + ww)
		w->x = wx + ww - w->w;
	if (w->x < wx)
		w->x = wx;
	if (w->y < wy)
		w->y = wy;
	if (w->y + w->h > wy + wh)
		w->y = wy + wh - w->h;
	if (w->y < wy)
		w->y = wy;
}

/* rectangulo maximizado exacto: full-bleed desde la barra superior hasta el
 * borde inferior de la pantalla (sin dock ni barra de tareas), sin margenes,
 * redondeos ni sombras. */
static void maximized_rect(int *x, int *y, int *w, int *h) {
	int sw = screen_w();
	int sh = screen_h();
	int hh = sh - TOPBAR_H;

	*x = 0;
	*y = TOPBAR_H;
	*w = sw;
	if (hh < WIN_MIN_H)
		hh = sh - TOPBAR_H;
	if (hh < 1)
		hh = 1;
	*h = hh;
}

/* recupera el rect guardado antes de maximizar y solo lo ajusta si ya no
 * cabe en el area actual (p. ej. cambio de resolucion) */
static void apply_saved_rect(struct window *w) {
	int wx, wy, ww, wh;

	w->x = w->saved_x;
	w->y = w->saved_y;
	w->w = w->saved_w;
	w->h = w->saved_h;
	window_work_area(&wx, &wy, &ww, &wh);
	if (w->w > ww)
		w->w = ww;
	if (w->h > wh)
		w->h = wh;
	if (w->w < WIN_MIN_W && ww >= WIN_MIN_W)
		w->w = WIN_MIN_W;
	if (w->h < WIN_MIN_H && wh >= WIN_MIN_H)
		w->h = WIN_MIN_H;
	if (w->x < wx)
		w->x = wx;
	if (w->x + w->w > wx + ww)
		w->x = wx + ww - w->w;
	if (w->y < wy)
		w->y = wy;
	if (w->y + w->h > wy + wh)
		w->y = wy + wh - w->h;
	if (w->y < wy)
		w->y = wy;
}

/* la ventana superior visible (excluye las que se estan cerrando) */
static struct window *top_visible_window(void) {
	int i;

	for (i = window_total - 1; i >= 0; i--) {
		struct window *w = window_order[i];

		if (w && w->used && !w->pending_close && !w->closing &&
		    w->state != WIN_STATE_MINIMIZED)
			return w;
	}
	return 0;
}

/* ------------------------------------------------------------------ */
/* ciclo de vida                                                     */
/* ------------------------------------------------------------------ */

struct window *window_create(struct app *app, const char *title,
                             int x, int y, int w, int h) {
	struct window *win = 0;
	int i;

	if (!app)
		return 0;
	for (i = 0; i < WINDOW_MAX; i++) {
		if (!window_pool[i].used) {
			win = &window_pool[i];
			break;
		}
	}
	if (!win || window_total >= WINDOW_MAX)
		return 0;

	memset(win, 0, sizeof(*win));
	win->used = 1;
	win->app = app;
	win->state = WIN_STATE_NORMAL;
	win->needs_frame = 1;
	win->data = 0;
	win->x = x;
	win->y = y;
	win->w = (w < WIN_MIN_W) ? WIN_MIN_W : w;
	win->h = (h < WIN_MIN_H) ? WIN_MIN_H : h;
	win->saved_x = win->x;
	win->saved_y = win->y;
	win->saved_w = win->w;
	win->saved_h = win->h;
	if (title && title[0]) {
		strncpy(win->title, title, WINDOW_TITLE_MAX - 1);
		win->title[WINDOW_TITLE_MAX - 1] = 0;
	} else {
		strncpy(win->title, (app->name ? app->name : "Aplicacion"),
		        WINDOW_TITLE_MAX - 1);
		win->title[WINDOW_TITLE_MAX - 1] = 0;
	}
	clamp_geometry(win);

	window_order[window_total++] = win;
	window_focused = win;
	window_pending_focus = 0;

	/* la aplicacion reserva su estado privado y registra sus tareas */
	if (app->open)
		app->open(win);

	serial_printf("APP_OPEN:%s\n", app->id ? app->id : "?");
	gui_request_redraw();
	return win;
}

/* aplica cierres y focos pendientes (llamado por el compositor al final
 * del frame, nunca desde dentro de un callback de aplicacion) */
void window_process_pending(void) {
	int changed = 0;
	int i;

	/* 1. cierres diferidos */
	i = 0;
	while (i < window_total) {
		struct window *w = window_order[i];

		if (!w || !w->pending_close) {
			i++;
			continue;
		}
		if (w->closing) {
			i++;
			continue;
		}
		w->closing = 1;
		if (w->app && w->app->close)
			w->app->close(w);
		if (w->app && w->app->id)
			serial_printf("APP_CLOSE:%s\n", w->app->id);
		else
			serial_write("APP_CLOSE:?\n");
		w->used = 0;
		w->pending_close = 0;
		w->pending_focus = 0;
		w->closing = 0;
		w->data = 0;
		w->app = 0;
		order_remove(w);
		if (window_focused == w)
			window_focused = 0;
		if (window_pending_focus == w)
			window_pending_focus = 0;
		changed = 1;
	}

	/* 2. foco diferido */
	if (window_pending_focus) {
		struct window *w = window_pending_focus;

		window_pending_focus = 0;
		w->pending_focus = 0;
		if (w->used && !w->pending_close && !w->closing) {
			if (w->state == WIN_STATE_MINIMIZED) {
				if (w->was_maximized) {
					w->state = WIN_STATE_MAXIMIZED;
					maximized_rect(&w->x, &w->y, &w->w, &w->h);
					w->was_maximized = 0;
				} else {
					w->state = WIN_STATE_NORMAL;
				}
			}
			order_raise(w);
			if (window_focused != w) {
				window_focused = w;
				changed = 1;
			}
			w->needs_frame = 1;
		}
	}

	/* 3. si no queda ventana enfocada, se enfoca la superior visible */
	if (!window_focused) {
		struct window *w = top_visible_window();

		if (w) {
			window_focused = w;
			w->needs_frame = 1;
			changed = 1;
		}
	}

	if (changed) {
		window_clamp_all();
		gui_request_redraw();
	}
}

void window_close(struct window *w) {
	if (!w || !w->used || w->closing)
		return;
	w->pending_close = 1;
	if (window_focused == w)
		window_focused = 0;
	if (window_pending_focus == w)
		window_pending_focus = 0;
}

void window_focus(struct window *w) {
	if (!w || !w->used || w->closing || w->pending_close)
		return;
	if (window_focused == w && order_index(w) == window_total - 1) {
		w->needs_frame = 1;
		return;
	}
	w->pending_focus = 1;
	window_pending_focus = w;
}

void window_move(struct window *w, int x, int y) {
	if (!w || !w->used || w->state != WIN_STATE_NORMAL)
		return;
	w->x = x;
	w->y = y;
	clamp_geometry(w);
}

/* redimensionado interactivo de ventanas normales con clamp al work area */
void window_set_geometry(struct window *w, int x, int y, int ww, int hh) {
	int wx, wy, ww_area, hh_area;

	if (!w || !w->used || w->state != WIN_STATE_NORMAL)
		return;
	window_work_area(&wx, &wy, &ww_area, &hh_area);
	if (ww < WIN_MIN_W)
		ww = WIN_MIN_W;
	if (hh < WIN_MIN_H)
		hh = WIN_MIN_H;
	if (ww > ww_area)
		ww = ww_area;
	if (hh > hh_area)
		hh = hh_area;
	if (x < wx)
		x = wx;
	if (x + ww > wx + ww_area)
		x = wx + ww_area - ww;
	if (y < wy)
		y = wy;
	if (y + hh > wy + hh_area)
		y = wy + hh_area - hh;
	if (x != w->x || y != w->y || ww != w->w || hh != w->h) {
		w->x = x;
		w->y = y;
		w->w = ww;
		w->h = hh;
		w->needs_frame = 1;
	}
}

void window_minimize(struct window *w) {
	if (!w || !w->used || w->state == WIN_STATE_MINIMIZED)
		return;
	w->was_maximized = (w->state == WIN_STATE_MAXIMIZED) ? 1 : 0;
	w->state = WIN_STATE_MINIMIZED;
	w->needs_frame = 0;
	if (window_focused == w)
		window_focused = 0;
	if (window_pending_focus == w)
		window_pending_focus = 0;
	window_clamp_all();
	gui_request_redraw();
}

void window_restore(struct window *w) {
	if (!w || !w->used)
		return;
	if (w->state == WIN_STATE_MINIMIZED) {
		if (w->was_maximized) {
			w->state = WIN_STATE_MAXIMIZED;
			maximized_rect(&w->x, &w->y, &w->w, &w->h);
			w->was_maximized = 0;
		} else {
			w->state = WIN_STATE_NORMAL;
		}
	}
	w->needs_frame = 1;
	window_clamp_all();
	gui_request_redraw();
	window_focus(w);
}

void window_toggle_maximize(struct window *w) {
	if (!w || !w->used || w->state == WIN_STATE_MINIMIZED)
		return;

	if (w->state == WIN_STATE_MAXIMIZED) {
		w->state = WIN_STATE_NORMAL;
		w->was_maximized = 0;
		apply_saved_rect(w);
	} else {
		w->saved_x = w->x;
		w->saved_y = w->y;
		w->saved_w = w->w;
		w->saved_h = w->h;
		w->state = WIN_STATE_MAXIMIZED;
		w->was_maximized = 0;
		maximized_rect(&w->x, &w->y, &w->w, &w->h);
	}
	w->needs_frame = 1;
	window_clamp_all();
	gui_request_redraw();
	window_focus(w);
}

void window_set_title(struct window *w, const char *title) {
	if (!w || !w->used || !title)
		return;
	strncpy(w->title, title, WINDOW_TITLE_MAX - 1);
	w->title[WINDOW_TITLE_MAX - 1] = 0;
	w->needs_frame = 1;
}

void window_invalidate(struct window *w) {
	if (w && w->used)
		w->needs_frame = 1;
}

void window_invalidate_all(void) {
	int i;

	for (i = 0; i < window_total; i++) {
		if (window_order[i] && window_order[i]->used)
			window_order[i]->needs_frame = 1;
	}
}

/* ------------------------------------------------------------------ */
/* geometria                                                          */
/* ------------------------------------------------------------------ */

int window_x(struct window *w) { return w ? w->x : 0; }
int window_y(struct window *w) { return w ? w->y : 0; }
int window_width(struct window *w) { return w ? w->w : 0; }
int window_height(struct window *w) { return w ? w->h : 0; }

int window_content_x(struct window *w) {
	if (!w)
		return 0;
	if (w->state == WIN_STATE_MAXIMIZED)
		return w->x;
	return w->x + WIN_BORDER;
}

int window_content_y(struct window *w) { return w ? w->y + WIN_TITLEBAR_H : 0; }

int window_content_w(struct window *w) {
	int cw;

	if (!w)
		return 0;
	cw = w->w - ((w->state == WIN_STATE_MAXIMIZED) ? 0 : WIN_BORDER * 2);
	return (cw > 0) ? cw : 0;
}

int window_content_h(struct window *w) {
	int ch;

	if (!w)
		return 0;
	ch = w->h - WIN_TITLEBAR_H -
	     ((w->state == WIN_STATE_MAXIMIZED) ? 0 : WIN_BORDER);
	return (ch > 0) ? ch : 0;
}

int window_titlebar_height(void) { return WIN_TITLEBAR_H; }
int window_min_width(void) { return WIN_MIN_W; }
int window_min_height(void) { return WIN_MIN_H; }

int window_visible(struct window *w) {
	return w && w->used && !w->pending_close && !w->closing &&
	       w->state != WIN_STATE_MINIMIZED;
}

int window_minimized(struct window *w) {
	return w && w->state == WIN_STATE_MINIMIZED;
}

int window_active(struct window *w) {
	return w && w->used && w == window_focused;
}

int window_maximized(struct window *w) {
	return w && w->used && w->state == WIN_STATE_MAXIMIZED;
}

/* recoloca/clampa todas las ventanas al area de trabajo actual. Las
 * maximizadas ocupan el rect full-bleed exacto (depende del estado del WM:
 * dock o navegacion superior) y el resto se mantiene dentro de sus limites. */
void window_clamp_all(void) {
	int wx, wy, ww, wh;
	int i;

	window_work_area(&wx, &wy, &ww, &wh);
	for (i = 0; i < window_total; i++) {
		struct window *w = window_order[i];
		int ox, oy, ow, oh;

		if (!w || !w->used)
			continue;
		if (w->state == WIN_STATE_MINIMIZED)
			continue;
		ox = w->x;
		oy = w->y;
		ow = w->w;
		oh = w->h;
		if (w->state == WIN_STATE_MAXIMIZED) {
			maximized_rect(&w->x, &w->y, &w->w, &w->h);
		} else {
			clamp_geometry(w);
		}
		if (w->x != ox || w->y != oy || w->w != ow || w->h != oh)
			w->needs_frame = 1;
	}
}

/* ------------------------------------------------------------------ */
/* estado de la aplicacion                                            */
/* ------------------------------------------------------------------ */

struct app *window_app(struct window *w) { return w ? w->app : 0; }
void       *window_data(struct window *w) { return w ? w->data : 0; }

void window_set_data(struct window *w, void *data) {
	if (w)
		w->data = data;
}

const char *window_title(struct window *w) {
	return (w && w->title[0]) ? w->title : "";
}

/* ------------------------------------------------------------------ */
/* consulta para el compositor y la entrada                           */
/* ------------------------------------------------------------------ */

struct window *window_active_window(void) {
	return window_focused;
}

struct window *window_at(int x, int y) {
	int i;

	for (i = window_total - 1; i >= 0; i--) {
		struct window *w = window_order[i];

		if (!window_visible(w))
			continue;
		if (x >= w->x && x < w->x + w->w && y >= w->y && y < w->y + w->h)
			return w;
	}
	return 0;
}

int window_count(void) {
	return window_total;
}

/* indice 0 = ventana inferior, window_count()-1 = ventana superior */
struct window *window_get(int index) {
	if (index < 0 || index >= window_total)
		return 0;
	return window_order[index];
}

int window_needs_frame(struct window *w) {
	return w && w->used && w->needs_frame;
}

void window_clear_frame(struct window *w) {
	if (w)
		w->needs_frame = 0;
}

/* ------------------------------------------------------------------ */
/* botones del marco (semaforos a la derecha)                         */
/* ------------------------------------------------------------------ */

int window_button_radius(void) {
	return TRAFFIC_R;
}

/* ancho que ocupa el grupo de botones a cada lado; el titulo se centra
 * geometricamente en la ventana reservando este inset simetrico */
int window_title_side_inset(void) {
	return TRAFFIC_EDGE_X + (WINDOW_BUTTON_COUNT - 1) * TRAFFIC_STEP +
	       TRAFFIC_R + 8;
}

int window_button_center(struct window *w, int index, int *x, int *y) {
	if (!w || index < 0 || index >= WINDOW_BUTTON_COUNT)
		return 0;
	/* 0 = el mas a la izquierda del grupo, 2 = el mas a la derecha */
	if (x)
		*x = w->x + w->w - TRAFFIC_EDGE_X -
		     (WINDOW_BUTTON_COUNT - 1 - index) * TRAFFIC_STEP;
	if (y)
		*y = w->y + WIN_TITLEBAR_H / 2;
	return 1;
}

static int hit_button(struct window *w, int x, int y, int index) {
	int cx, cy, dx, dy;

	if (!window_visible(w))
		return 0;
	if (!window_button_center(w, index, &cx, &cy))
		return 0;
	dx = x - cx;
	dy = y - cy;
	return (dx * dx + dy * dy) <= (TRAFFIC_HIT_R * TRAFFIC_HIT_R);
}

int window_hit_close(struct window *w, int x, int y) {
	return hit_button(w, x, y, WINDOW_BUTTON_CLOSE);
}

int window_hit_minimize(struct window *w, int x, int y) {
	return hit_button(w, x, y, WINDOW_BUTTON_MINIMIZE);
}

int window_hit_maximize(struct window *w, int x, int y) {
	return hit_button(w, x, y, WINDOW_BUTTON_MAXIMIZE);
}

/* zona de arrastre/doble clic: la barra de titulo salvo el grupo de botones */
int window_hit_title_drag(struct window *w, int x, int y) {
	int i;

	if (!window_visible(w))
		return 0;
	if (x < w->x || x >= w->x + w->w)
		return 0;
	if (y < w->y || y >= w->y + WIN_TITLEBAR_H)
		return 0;
	for (i = 0; i < WINDOW_BUTTON_COUNT; i++) {
		if (hit_button(w, x, y, i))
			return 0;
	}
	return 1;
}

/* consulta auxiliar usada por desktop.c (no forma parte del contrato
 * congelado de window.h): evita despachar eventos a ventanas que se estan
 * cerrando en este frame. */
int window_is_pending_close(struct window *w) {
	return w && (w->pending_close || w->closing);
}
