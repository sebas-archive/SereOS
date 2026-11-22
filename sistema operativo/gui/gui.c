/* gui/gui.c - identidad visual de SereOS Desktop y bucle principal
 *
 * La paleta vive en gui/theme.c (const theme_t theme) y el kit de
 * componentes en gui/ui.c. Aqui estan el arranque de los subsistemas
 * visuales, el bucle de eventos/frames, los atajos globales F1..F7 y
 * Alt/Ctrl+W, la apertura diferida de aplicaciones y la pantalla de error
 * critico (gui_panic), dibujada solo con primitivas estaticas para que
 * funcione desde una ISR de excepcion.
 */
#include <stdint.h>
#include "gui.h"
#include "theme.h"
#include "ui.h"
#include "window.h"
#include "app.h"
#include "desktop.h"
#include "cursor.h"
#include "icons.h"
#include "logo.h"
#include "graphics.h"
#include "text.h"
#include "input.h"
#include "timer.h"
#include "scheduler.h"
#include "serial.h"
#include "string.h"
#include "io.h"
#include "sereos_version.h"

/* ------------------------------------------------------------------ */
/* estado compartido con desktop.c                                   */
/* ------------------------------------------------------------------ */
/* bandera de recompostura completa; la consume desktop_tick() */
int gui_full_redraw_pending;

/* auxiliares internas de desktop.c / window.c (no estan en los headers
 * congelados porque solo las usa el propio compositor) */
int  desktop_work_pending(void);
void window_process_pending(void);
void window_work_area(int *x, int *y, int *w, int *h);

static int gui_active_flag;

/* peticiones de apertura diferidas (se aplican fuera del despacho de
 * eventos para no crear ventanas a mitad de una iteracion) */
#define GUI_PENDING_APPS 4
#define GUI_APP_ID_MAX   24
static char gui_pending_apps[GUI_PENDING_APPS][GUI_APP_ID_MAX];
static int  gui_pending_count;

/* ------------------------------------------------------------------ */
/* utilidades                                                         */
/* ------------------------------------------------------------------ */

void gui_request_redraw(void) {
	gui_full_redraw_pending = 1;
}

static int clamp_int(int v, int lo, int hi) {
	if (v < lo)
		return lo;
	if (v > hi)
		return hi;
	return v;
}

/* ------------------------------------------------------------------ */
/* apertura de aplicaciones (diferida)                                */
/* ------------------------------------------------------------------ */

void gui_open_app(const char *app_id) {
	size_t n;

	if (!app_id || !app_id[0])
		return;
	if (!app_find(app_id)) {
		serial_printf("APP_MISSING:%s\n", app_id);
		return;
	}
	if (gui_pending_count >= GUI_PENDING_APPS)
		return;
	n = strlen(app_id);
	if (n >= GUI_APP_ID_MAX)
		n = GUI_APP_ID_MAX - 1;
	memcpy(gui_pending_apps[gui_pending_count], app_id, n);
	gui_pending_apps[gui_pending_count][n] = 0;
	gui_pending_count++;
}

static void open_app_now(const char *id) {
	app_t *a = app_find(id);
	int i, ww, hh, x, y, wx, wy, warea, harea;
	static int cascade;
	struct window *w;

	if (!a)
		return;
	/* si la app ya tiene ventana: restaurar (si esta minimizada) o enfocar */
	for (i = 0; i < window_count(); i++) {
		struct window *win = window_get(i);

		if (window_app(win) == a) {
			if (window_minimized(win))
				window_restore(win);
			else
				window_focus(win);
			return;
		}
	}
	/* ventana nueva centrada y limitada al area de trabajo (sin tapar el
	 * dock ni la barra superior) */
	window_work_area(&wx, &wy, &warea, &harea);
	ww = (a->default_width > 0) ? a->default_width : 720;
	hh = (a->default_height > 0) ? a->default_height : 480;
	ww = clamp_int(ww, window_min_width(), warea);
	hh = clamp_int(hh, window_min_height(), harea);
	x = wx + (warea - ww) / 2 + (cascade % 4) * SP_6 - (SP_6 + SP_2);
	y = wy + (harea - hh) / 2 + (cascade % 4) * SP_5 - SP_6;
	x = clamp_int(x, wx, wx + warea - ww);
	y = clamp_int(y, wy, wy + harea - hh);
	cascade++;
	w = window_create(a, a->name ? a->name : id, x, y, ww, hh);
	if (!w) {
		serial_printf("APP_FAIL:%s\n", id);
		return;
	}
}

static void gui_process_pending_apps(void) {
	int i;

	if (gui_pending_count == 0)
		return;
	for (i = 0; i < gui_pending_count; i++)
		open_app_now(gui_pending_apps[i]);
	gui_pending_count = 0;
}

/* ------------------------------------------------------------------ */
/* atajos globales                                                    */
/* ------------------------------------------------------------------ */

static void focus_next_window(void) {
	int n = window_count();
	struct window *cur = window_active_window();
	int start = -1;
	int i;

	if (n < 1)
		return;
	for (i = 0; i < n; i++) {
		if (window_get(i) == cur) {
			start = i;
			break;
		}
	}
	for (i = 1; i <= n; i++) {
		int idx = (start < 0) ? (n - i) : ((start - i + 2 * n) % n);
		struct window *w = window_get(idx);

		if (w && window_visible(w)) {
			window_focus(w);
			return;
		}
	}
}

/* modificadores rastreados por si el driver aun no expone su estado */
static int key_alt_down;
static int key_ctrl_down;

static int handle_global_key(const event_t *ev) {
	if (ev->type == EVENT_KEY_UP) {
		if (ev->key == KEY_LEFTALT || ev->key == KEY_RIGHTALT)
			key_alt_down = 0;
		if (ev->key == KEY_LEFTCTRL || ev->key == KEY_RIGHTCTRL)
			key_ctrl_down = 0;
		return 0;
	}
	if (ev->type != EVENT_KEY_DOWN)
		return 0;
	switch (ev->key) {
	case KEY_LEFTALT:
	case KEY_RIGHTALT:
		key_alt_down = 1;
		return 0;
	case KEY_LEFTCTRL:
	case KEY_RIGHTCTRL:
		key_ctrl_down = 1;
		return 0;
	case KEY_F1:
		gui_open_app("files");
		return 1;
	case KEY_F2:
		gui_open_app("terminal");
		return 1;
	case KEY_F3:
		gui_open_app("monitor");
		return 1;
	case KEY_F4:
		gui_open_app("game");
		return 1;
	case KEY_F5:
		gui_open_app("about");
		return 1;
	case KEY_F6:
		focus_next_window();
		return 1;
	case KEY_F7: {
		struct window *w = window_active_window();

		if (w)
			window_minimize(w);
		return 1;
	}
	case KEY_W:
		/* Alt+W / Ctrl+W: cierre diferido de la ventana activa (QA) */
		if (key_alt_down || key_ctrl_down ||
		    input_alt_down() || input_ctrl_down()) {
			struct window *w = window_active_window();

			if (w)
				window_close(w);
			return 1;
		}
		return 0;
	default:
		return 0;
	}
}

/* ------------------------------------------------------------------ */
/* arranque                                                           */
/* ------------------------------------------------------------------ */

void gui_init(void) {
	gui_active_flag = 1;
	gui_full_redraw_pending = 0;
	gui_pending_count = 0;

	/* subsistemas visuales: tipografia, iconografia y kit de componentes */
	text_init();
	icons_init();
	ui_init();

	/* el registro de apps ya lo hizo apps_register() desde kernel_main */
	desktop_init();
	cursor_init();
	input_flush();

	serial_write("DESKTOP_READY\n");
}

int gui_active(void) {
	return gui_active_flag;
}

/* ------------------------------------------------------------------ */
/* bucle principal                                                    */
/* ------------------------------------------------------------------ */

void gui_run(void) {
	serial_write("GUI_LOOP\n");

	for (;;) {
		event_t ev;

		/* 1. devolver el fondo que ocupaba el cursor */
		cursor_restore();

		/* 2. drenar la cola de entrada (un unico consumidor) */
		while (input_poll(&ev)) {
			/* atajos globales F1..F7 y Alt/Ctrl+W antes de despachar */
			if ((ev.type == EVENT_KEY_DOWN || ev.type == EVENT_KEY_UP) &&
			    handle_global_key(&ev))
				continue;
			desktop_dispatch_event(&ev);
		}

		/* 3. aperturas diferidas (crean ventanas fuera del despacho) */
		gui_process_pending_apps();
		window_clamp_all();

		/* 4. un paso de las tareas cooperativas de las apps */
		scheduler_tick();

		/* 5. hover, reloj y repintado de regiones invalidadas */
		desktop_tick();

		/* 6. cursor compuesto sobre el backbuffer y presentacion sucia */
		cursor_draw(input_mouse_x(), input_mouse_y());
		gfx_present_dirty();

		/* 7. dormir solo cuando no queda trabajo pendiente */
		if (!input_has_event() && gui_pending_count == 0 &&
		    !gui_full_redraw_pending && !desktop_work_pending())
			hlt();
	}
}

/* ------------------------------------------------------------------ */
/* pantalla de error critico (segura desde ISR)                       */
/* ------------------------------------------------------------------ */

/* envuelve texto en varias lineas dentro de maxw; devuelve la y final */
static int panic_wrap(text_style_t style, int x, int y, int maxw,
                      const char *s, uint32_t color) {
	char line[256];
	int len = 0;
	int line_h = text_height(style);

	line[0] = 0;
	if (!s)
		return y;
	while (*s) {
		const char *ws;
		int wl;
		char cand[256];
		int cl;

		if (*s == '\n') {
			if (len > 0) {
				text_draw(style, x, y, line, color);
				y += line_h;
			}
			len = 0;
			line[0] = 0;
			s++;
			continue;
		}
		if (*s == ' ') {
			s++;
			continue;
		}
		ws = s;
		while (*s && *s != ' ' && *s != '\n')
			s++;
		wl = (int)(s - ws);
		if (wl > 240)
			wl = 240;
		cl = len;
		memcpy(cand, line, (size_t)len);
		if (len)
			cand[cl++] = ' ';
		memcpy(cand + cl, ws, (size_t)wl);
		cl += wl;
		cand[cl] = 0;

		if (len > 0 && text_width(style, cand) > maxw) {
			text_draw(style, x, y, line, color);
			y += line_h;
			len = wl;
			memcpy(line, ws, (size_t)wl);
			line[len] = 0;
		} else {
			len = cl;
			memcpy(line, cand, (size_t)cl + 1);
		}
	}
	if (len > 0) {
		text_draw(style, x, y, line, color);
		y += line_h;
	}
	return y;
}

void gui_panic(const char *title, const char *detail) {
	int sw, sh, x, w, y, footer_y;

	cli();
	sw = gfx_width();
	sh = gfx_height();
	if (sw <= 0 || sh <= 0)
		return;

	gfx_reset_clip();
	gfx_fill_rect(0, 0, sw, sh, theme.bg);

	/* barra superior pequena: solo marca (logotipo oficial) */
	gfx_fill_rect(0, 0, sw, 40, theme.bg);
	gfx_fill_rect(0, 39, sw, 1, theme.border);
	{
		/* la pantalla de panico usa el glifo OFICIAL de marca (no ribbon) */
		logo_draw_brand(20 + PANIC_LOGO / 2, 20, PANIC_LOGO);
		text_draw(TEXT_LABEL, 20 + PANIC_LOGO + SP_2,
		          (40 - text_height(TEXT_LABEL)) / 2, SEREOS_NAME,
		          theme.text_dim);
	}

	/* columna de contenido centrada, ancho maximo 760 px */
	w = sw - SP_8 * 2;
	if (w > 760)
		w = 760;
	if (w < 200)
		w = sw - SP_4 * 2;
	x = (sw - w) / 2;
	if (x < SP_2)
		x = SP_2;
	y = 40 + SP_8 + SP_2;

	/* jerarquia: punto de estado + error, descripcion y titulo */
	gfx_fill_circle(x + SP_1, y + text_height(TEXT_HEADLINE) / 2, 4, theme.red);
	text_draw(TEXT_HEADLINE, x + SP_3 + SP_1, y, "Error crítico", theme.red);
	y += text_height(TEXT_HEADLINE) + SP_3;
	y = panic_wrap(TEXT_BODY, x, y, w,
	               "Se produjo una excepción del procesador y el sistema se "
	               "detuvo de forma segura.", theme.text_dim);
	y += SP_2;
	if (title)
		y = panic_wrap(TEXT_TITLE, x, y, w, title, theme.text);
	y += SP_4;
	gfx_fill_rect(x, y, w, 1, theme.border);
	y += SP_4;

	/* bloque tecnico: filas etiqueta/valor (sin panel ni borde) */
	if (detail && detail[0]) {
		const char *p = detail;
		int first = 1;
		int row_h = text_height(TEXT_MONO) + SP_2;
		int col = 160;
		int clip_bottom = sh - 64;

		if (clip_bottom < y + row_h)
			clip_bottom = y + row_h;
		gfx_set_clip(x, y, w, clip_bottom - y);
		while (*p) {
			char label[64];
			char value[96];
			int ll, vl;
			const char *eq, *v, *ve, *e;

			while (*p == ' ' || *p == '\r')
				p++;
			if (*p == '\n') {
				p++;
				continue;
			}
			eq = p;
			while (*eq && *eq != '=' && *eq != '\n')
				eq++;
			if (*eq != '=') {
				/* linea sin '=': se muestra entera como valor */
				e = p;
				while (*e && *e != '\n')
					e++;
				vl = (int)(e - p);
				while (vl > 0 && (p[vl - 1] == ' ' || p[vl - 1] == '\r'))
					vl--;
				if (vl > (int)sizeof(value) - 1)
					vl = (int)sizeof(value) - 1;
				memcpy(value, p, (size_t)vl);
				value[vl] = 0;
				if (!first)
					gfx_fill_rect_alpha(x, y, w, 1, theme.border, 26);
				text_draw(TEXT_MONO, x, y, value, theme.text_dim);
				y += row_h;
				first = 0;
				p = (*e == '\n') ? e + 1 : e;
				continue;
			}
			/* etiqueta */
			ll = (int)(eq - p);
			while (ll > 0 && (p[ll - 1] == ' ' || p[ll - 1] == '\r'))
				ll--;
			if (ll > (int)sizeof(label) - 1)
				ll = (int)sizeof(label) - 1;
			memcpy(label, p, (size_t)ll);
			label[ll] = 0;
			/* valor: hasta una rafaga de 3 espacios o fin de linea */
			v = eq + 1;
			while (*v == ' ')
				v++;
			ve = v;
			while (*ve && *ve != '\n') {
				if (ve[0] == ' ' && ve[1] == ' ' && ve[2] == ' ')
					break;
				ve++;
			}
			vl = (int)(ve - v);
			while (vl > 0 && (v[vl - 1] == ' ' || v[vl - 1] == '\r'))
				vl--;
			if (vl > (int)sizeof(value) - 1)
				vl = (int)sizeof(value) - 1;
			memcpy(value, v, (size_t)vl);
			value[vl] = 0;

			if (!first)
				gfx_fill_rect_alpha(x, y, w, 1, theme.border, 26);
			text_draw(TEXT_CAPTION, x,
			          y + (text_height(TEXT_MONO) - text_height(TEXT_CAPTION)) / 2,
			          label, theme.text_dim);
			text_draw(TEXT_MONO, x + col, y, value, theme.text);
			y += row_h;
			first = 0;
			p = (*ve == '\n') ? ve + 1 : ve;
		}
		gfx_reset_clip();
	}

	/* pie */
	footer_y = sh - SP_6 * 2 - text_height(TEXT_SMALL);
	if (footer_y < SP_10)
		footer_y = SP_10;
	if (footer_y > y + SP_3)
		gfx_fill_rect_alpha(x, footer_y - SP_3, w, 1, theme.border, 50);
	text_draw(TEXT_SMALL, x, footer_y, "Reinicia la máquina para continuar.",
	          theme.text_faint);

	gfx_reset_clip();
	gfx_mark_all_dirty();
	gfx_present();
}
