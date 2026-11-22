/* gui/desktop.c - compositor del escritorio SereOS (rediseno visual 1.1)
 *
 * Lenguaje visual: minimalista, mucho espacio negativo y jerarquia clara.
 *   - Fondo: color plano theme.bg con un par de formas abstractas muy
 *     sutiles (arcos/elipses y una franja diagonal con alfa 5-12). Sin
 *     cuadricula ni estrellas. Se cachea en un buffer estatico del tamano
 *     maximo del framebuffer (1280x1024) y solo se repinta si cambia.
 *   - Barra superior 30 px: fondo bg translucido + borde 1 px; logo,
 *     wordmark, boton de menu, app activa centrada y a la derecha memoria
 *     real (mini barra + MB), uptime, fecha y hora RTC.
 *   - Menu desplegable sobrio: panel surface_2 RADIUS_MD, items de 30 px con
 *     icono de 16 px, hover accent_soft y separador.
 *   - Dock 58 px centrado: superficie translucida RADIUS_LG, tiles de 44 px
 *     con iconos de 40 px, hover en surface_3, indicador de app abierta y
 *     tooltip.
 *   - Ventanas: sombra sutil de dos capas, marco RADIUS_MD, borde 1 px
 *     (border_strong si esta activa), titulo de 34 px sobre surface_2,
 *     semaforos de 11 px y contenido sobre surface.
 *
 * La composicion conserva el modelo anterior: recompostura completa en
 * cambios estructurales y repintado por regiones para frames invalidados,
 * reloj, hover y arrastre; se presenta solo lo sucio (gfx_present_dirty).
 */
#include <stdint.h>
#include "desktop.h"
#include "gui.h"
#include "theme.h"
#include "ui.h"
#include "window.h"
#include "app.h"
#include "icons.h"
#include "logo.h"
#include "graphics.h"
#include "text.h"
#include "framebuffer.h"
#include "input.h"
#include "timer.h"
#include "rtc.h"
#include "page.h"
#include "serial.h"
#include "string.h"
#include "io.h"
#include "sereos_version.h"

/* Contrato de apagado del kernel: void sereos_shutdown(void) */
#include "shutdown.h"

/* ------------------------------------------------------------------ */
/* metricas del escritorio (a partir de los tokens de theme.h)        */
/* ------------------------------------------------------------------ */
#define TOPBAR_BTN_SIZE   20
#define MENU_ITEM_H       30
#define MENU_W            224
#define MENU_PAD_Y        6
#define MENU_SEP_GAP      8
#define MENU_HINT_H       20
#define MENU_HEADER_H     46
#define MENU_H            (MENU_HEADER_H + MENU_PAD_Y * 2 + MENU_ITEMS * MENU_ITEM_H + \
                           MENU_SEP_GAP + MENU_HINT_H)
#define MENU_ITEMS        7          /* 5 apps + Reiniciar + Apagar */
#define DOCK_TILE         44
#define DOCK_ICONS        5
#define MENU_APP_ICON     18          /* insignia "i" de la fila "Acerca de" */
#define DOCK_W            (DOCK_PAD * 2 + DOCK_ICONS * DOCK_TILE + \
                           (DOCK_ICONS - 1) * DOCK_ICON_GAP)
#define WIN_MARGIN        24          /* margen de recomposicion para sombras */

/* los botones del marco (metricas, dibujo y hit tests) viven en window.c;
 * aqui solo se consume window_button_center()/window_button_radius(). */

/* definidas en gui.c (misma unidad de composicion) */
extern int gui_full_redraw_pending;

/* auxiliares internas de window.c, no forman parte de window.h congelado */
void window_process_pending(void);
int  window_is_pending_close(struct window *w);

/* ------------------------------------------------------------------ */
/* estado interno                                                     */
/* ------------------------------------------------------------------ */
static uint32_t wallpaper_cache[FB_MAX_PIXELS];
static int      wallpaper_valid;
static int      wallpaper_w;
static int      wallpaper_h;

static int dirty_topbar;
static int dirty_dock;
static int dirty_menu;

static desktop_bar_state_t last_bar_state;

/* navegacion adaptativa: dock <-> accesos en la top bar.
 * nav_anim: 0 = dock visible, 1000 = navegacion superior visible. */
#define NAV_ANIM_SWITCH       500
#define NAV_ANIM_STEP_PER_MS  7      /* ~145 ms de transicion completa */
static int nav_anim;
static uint32_t anim_last_tick;
static int nav_x0;                   /* borde izquierdo de los accesos en la topbar */
static int nav_drawn;                /* los accesos se han dibujado en este frame */

static int menu_open;
static int menu_hover;
static int menu_btn_hover;

static struct window *drag_window;
static int drag_dx, drag_dy;
static int drag_start_x, drag_start_y;
static int drag_moved;
static int drag_prev_x, drag_prev_y, drag_prev_w, drag_prev_h;

static struct window *resize_window;
static int resize_zone_bits;
static int resize_start_x, resize_start_y;
static int resize_orig_x, resize_orig_y, resize_orig_w, resize_orig_h;
static int resize_prev_x, resize_prev_y, resize_prev_w, resize_prev_h;

static struct window *dbl_window;
static uint32_t dbl_tick;
static int dbl_x, dbl_y;

static int dock_hover_index;

static struct window *tl_hover_window;
static int            tl_hover_button;

static char app_name_override[32];
static int  app_name_set;

static uint32_t last_uptime_sec;
static uint32_t last_tick_ref;

static const char *const dock_ids[DOCK_ICONS] = {
	"files", "terminal", "monitor", "game", "about"
};
static const char *const dock_names[DOCK_ICONS] = {
	"Archivos", "Terminal", "Monitor", "PAC-MAN SereOS", "Acerca de"
};

static const char *const menu_labels[MENU_ITEMS] = {
	"Acerca de", "Archivos", "Terminal", "Monitor", "PAC-MAN SereOS",
	"Reiniciar", "Apagar"
};
static const char *const menu_icons[MENU_ITEMS] = {
	"about", "files", "terminal", "monitor", "game", "refresh", "power"
};
static const char *const menu_apps[MENU_ITEMS] = {
	"about", "files", "terminal", "monitor", "game", 0, 0
};

/* ------------------------------------------------------------------ */
/* utilidades                                                        */
/* ------------------------------------------------------------------ */

static int point_in(int px, int py, int x, int y, int w, int h) {
	return px >= x && py >= y && px < x + w && py < y + h;
}

static int imin(int a, int b) { return a < b ? a : b; }
static int imax(int a, int b) { return a > b ? a : b; }
static int iabs(int v) { return v < 0 ? -v : v; }

/* zonas de redimensionado (bordes de 8 px de ventanas normales) */
#define RZ_LEFT    1
#define RZ_RIGHT   2
#define RZ_BOTTOM  4

static int resize_zone_at(struct window *w, int x, int y) {
	int wx, wy, ww, hh;
	int left, right, bottom;

	if (!w || !window_visible(w) || window_maximized(w))
		return 0;
	wx = window_x(w);
	wy = window_y(w);
	ww = window_width(w);
	hh = window_height(w);
	/* la barra de titulo se reserva para arrastre y doble clic */
	if (y < wy + WIN_TITLEBAR_H)
		return 0;
	left = (x >= wx) && (x < wx + 8);
	right = (x >= wx + ww - 8) && (x < wx + ww);
	bottom = (y >= wy + hh - 8) && (y < wy + hh);
	if (left && bottom)
		return RZ_LEFT | RZ_BOTTOM;
	if (right && bottom)
		return RZ_RIGHT | RZ_BOTTOM;
	if (bottom)
		return RZ_BOTTOM;
	if (right)
		return RZ_RIGHT;
	if (left)
		return RZ_LEFT;
	return 0;
}

static uint32_t *backbuffer(void) {
	return fb_has_backbuffer() ? fb_backbuffer() : 0;
}

/* --- navegacion adaptativa: helpers de animacion y layout --- */

static int nav_visible(void) {
	return nav_anim >= NAV_ANIM_SWITCH;
}

/* desplazamiento vertical del dock durante la transicion (0 = visible) */
static int dock_slide(void) {
	int span = DOCK_HEIGHT + DOCK_BOTTOM + 2;

	if (nav_anim <= 0)
		return 0;
	if (nav_anim >= NAV_ANIM_SWITCH)
		return span;
	return (span * nav_anim) / NAV_ANIM_SWITCH;
}

static int topbar_nav_total(void) {
	return DOCK_ICONS * TOPBAR_NAV_TILE + (DOCK_ICONS - 1) * TOPBAR_NAV_GAP;
}

static int topbar_nav_cx(int index) {
	return nav_x0 + index * (TOPBAR_NAV_TILE + TOPBAR_NAV_GAP) +
	       TOPBAR_NAV_TILE / 2;
}

/* indice de acceso de la topbar bajo (x,y), solo si la nav esta visible */
static int topbar_nav_index_at(int x, int y) {
	int i;

	if (!nav_visible() || !nav_drawn)
		return -1;
	if (y < 0 || y >= TOPBAR_H)
		return -1;
	for (i = 0; i < DOCK_ICONS; i++) {
		int cx = topbar_nav_cx(i);

		if (x >= cx - TOPBAR_NAV_TILE / 2 && x < cx + TOPBAR_NAV_TILE / 2)
			return i;
	}
	return -1;
}

/* ------------------------------------------------------------------ */
/* navegacion adaptativa: estado global del WM                        */
/* ------------------------------------------------------------------ */

desktop_bar_state_t desktop_bar_state(void) {
	int i;

	for (i = 0; i < window_count(); i++) {
		struct window *w = window_get(i);

		if (w && window_visible(w) && window_maximized(w))
			return DESKTOP_BAR_TOPNAV;
	}
	return DESKTOP_BAR_DOCK;
}

int desktop_topnav_active(void) {
	return desktop_bar_state() == DESKTOP_BAR_TOPNAV;
}

/* espacio vertical reservado en el borde inferior: sin barra en topnav */
int desktop_bottom_inset(void) {
	if (desktop_topnav_active())
		return 0;
	return DOCK_HEIGHT + DOCK_BOTTOM;
}

/* ------------------------------------------------------------------ */
/* fondo de escritorio                                                */
/* ------------------------------------------------------------------ */

static void wallpaper_paint(int w, int h) {
	int i;
	uint32_t arc_a;
	uint32_t arc_c;

	gfx_reset_clip();

	/* degradado vertical leve, con algo mas de azul hacia el fondo */
	gfx_gradient_v(0, 0, w, h, 0x0A0C11, 0x0F1420);

	/* halo radial suave arriba-derecha + respiracion cian abajo-izquierda */
	gfx_radial_glow(w * 76 / 100, h * 14 / 100, h * 62 / 100, theme.accent, 24);
	gfx_radial_glow(w * 18 / 100, h * 90 / 100, h * 42 / 100, theme.cyan, 14);

	/* cuerpo tenue del halo para que la composicion no quede plana */
	gfx_fill_circle(w * 82 / 100, h * 20 / 100, h * 30 / 100,
	                gui_color_blend(theme.accent, 0x0C1018, 9));

	/* arcos geometricos finos que barren desde abajo-izquierda */
	arc_a = gui_color_blend(theme.accent, 0x0C1018, 52);
	arc_c = gui_color_blend(theme.cyan, 0x0C1018, 36);
	gfx_draw_circle(w * 2 / 100, h + h * 52 / 100, h * 82 / 100, arc_a);
	gfx_draw_circle(w * 2 / 100, h + h * 52 / 100, h * 70 / 100, arc_c);
	gfx_draw_circle(w * 8 / 100, h + h * 34 / 100, h * 52 / 100, arc_a);

	/* vineta perimetrica discreta (4 bordes) */
	for (i = 0; i < 96 && i < h; i++) {
		uint8_t a = (uint8_t)(28 - (28 * i) / 96);

		gfx_fill_rect_alpha(0, i, w, 1, theme.black, a);
	}
	for (i = 0; i < 120 && i < h; i++) {
		uint8_t a = (uint8_t)(34 - (34 * i) / 120);

		gfx_fill_rect_alpha(0, h - 1 - i, w, 1, theme.black, a);
	}
	for (i = 0; i < 120 && i < w; i++) {
		uint8_t a = (uint8_t)(26 - (26 * i) / 120);

		gfx_fill_rect_alpha(i, 0, 1, h, theme.black, a);
		gfx_fill_rect_alpha(w - 1 - i, 0, 1, h, theme.black, a);
	}
}

static void wallpaper_cache_store(int w, int h) {
	uint32_t *bb = backbuffer();
	uint32_t stride;
	int row;

	wallpaper_valid = 0;
	if (!bb || w <= 0 || h <= 0 || w > FB_MAX_WIDTH || h > FB_MAX_HEIGHT)
		return;
	stride = fb_width();
	if (stride < (uint32_t)w)
		stride = (uint32_t)w;
	for (row = 0; row < h; row++)
		memcpy(&wallpaper_cache[row * w], &bb[(uint32_t)row * stride],
		       (size_t)w * 4);
	wallpaper_w = w;
	wallpaper_h = h;
	wallpaper_valid = 1;
}

static void wallpaper_ensure(void) {
	int w = gfx_width();
	int h = gfx_height();

	if (w <= 0 || h <= 0)
		return;
	if (w > FB_MAX_WIDTH)
		w = FB_MAX_WIDTH;
	if (h > FB_MAX_HEIGHT)
		h = FB_MAX_HEIGHT;
	if (wallpaper_valid && wallpaper_w == w && wallpaper_h == h)
		return;
	wallpaper_paint(w, h);
	wallpaper_cache_store(w, h);
}

static void wallpaper_region(int x, int y, int w, int h) {
	int sw = gfx_width();
	int sh = gfx_height();
	uint32_t *bb;
	uint32_t stride;
	int row;

	if (x < 0) { w += x; x = 0; }
	if (y < 0) { h += y; y = 0; }
	if (x + w > sw) w = sw - x;
	if (y + h > sh) h = sh - y;
	if (w <= 0 || h <= 0)
		return;

	gfx_reset_clip();
	wallpaper_ensure();
	bb = backbuffer();
	if (wallpaper_valid && bb) {
		stride = fb_width();
		if (stride < (uint32_t)wallpaper_w)
			stride = (uint32_t)wallpaper_w;
		for (row = 0; row < h; row++)
			memcpy(&bb[(uint32_t)(y + row) * stride + (uint32_t)x],
			       &wallpaper_cache[(y + row) * wallpaper_w + x],
			       (size_t)w * 4);
	} else {
		wallpaper_paint(sw, sh);
	}
}

/* ------------------------------------------------------------------ */
/* barra superior                                                     */
/* ------------------------------------------------------------------ */

/* ancho real del glifo ribbon de la marca de la top bar (sin contenedor) */
static int topbar_logo_w(void) {
	int w = logo_icon_width(TOPBAR_LOGO, LOGO_GLYPH_RIBBON);

	if (w <= 0)
		w = TOPBAR_LOGO;
	return w;
}

static int topbar_word_x(void) {
	/* la marca de la top bar es el glifo suelto del PNG: su ancho real
	 * (~9 px para altura 10) + gap SP_2 marcan el inicio del wordmark */
	return TOPBAR_PAD_X + topbar_logo_w() + SP_2;
}

static int topbar_menu_btn_x(void) {
	return topbar_word_x() + text_width(TEXT_LABEL, SEREOS_NAME) + SP_3;
}

static int topbar_menu_btn_y(void) {
	return (TOPBAR_H - TOPBAR_BTN_SIZE) / 2;
}

static struct window *app_window(const char *id);
static void draw_tooltip(const char *text, int cx, int bottom_y);
static const uint32_t dock_tints[DOCK_ICONS];

static const char *active_app_name(void) {
	struct window *aw = window_active_window();

	if (aw && window_visible(aw)) {
		app_t *a = window_app(aw);

		if (a && a->name && a->name[0])
			return a->name;
		if (window_title(aw)[0])
			return window_title(aw);
	}
	if (app_name_set)
		return app_name_override;
	return "Escritorio";
}

static void draw_topbar(void) {
	int sw = gfx_width();
	int wy = (TOPBAR_H - text_height(TEXT_LABEL)) / 2;
	int cy = (TOPBAR_H - text_height(TEXT_SMALL)) / 2;
	int bx = topbar_menu_btn_x();
	int by = topbar_menu_btn_y();
	int rx;
	int pct = 0;
	int show_date;
	int show_up;
	char clockbuf[16], datebuf[16], upbuf[24], membuf[24];
	const char *clock_s, *date_s;
	uint32_t total, used, up_sec;
	const char *name;
	int name_w;
	int i;

	if (sw <= 0)
		return;
	show_date = sw >= 900;
	show_up = sw >= 820;

	/* superficie translucida y borde inferior de 1 px */
	gfx_fill_rect_alpha(0, 0, sw, TOPBAR_H, theme.bg, 210);
	gfx_fill_rect(0, TOPBAR_H - 1, sw, 1, theme.border);

	/* izquierda: marca de la TOP BAR = SOLO el glifo ribbon del PNG
	 * (S blanca sobre transparente: sin circulo ni fondo azul), de la
	 * misma altura visual que el wordmark y centrada en su MISMA caja de
	 * linea (equivalente a flex align-items:center, gap SP_2). */
	logo_draw_topbar(TOPBAR_PAD_X + topbar_logo_w() / 2,
	                 wy + text_height(TEXT_LABEL) / 2, TOPBAR_LOGO);
	text_draw(TEXT_LABEL, topbar_word_x(), wy, SEREOS_NAME, theme.text);

	if (menu_btn_hover || menu_open)
		gfx_fill_round_rect(bx, by, TOPBAR_BTN_SIZE, TOPBAR_BTN_SIZE, RADIUS_XS,
		                    menu_open ? theme.surface_3 : theme.surface_2);
	icons_draw_color("menu", bx + TOPBAR_BTN_SIZE / 2, by + TOPBAR_BTN_SIZE / 2, 16,
	                 (menu_btn_hover || menu_open) ? theme.text : theme.text_dim);

	/* derecha: grupos [hora] | [fecha] | [uptime] | [memoria] */
	if (rtc_available()) {
		rtc_time_string(clockbuf, sizeof(clockbuf));
		rtc_date_string(datebuf, sizeof(datebuf));
		clock_s = clockbuf;
		date_s = datebuf;
	} else {
		clock_s = "--:--:--";
		date_s = "--/--/----";
	}
	total = page_total_bytes();
	used = page_used_bytes();
	if (total > 0) {
		uint32_t uk = used >> 10;
		uint32_t tk = total >> 10;

		pct = (tk > 0) ? (int)((uk * 100u) / tk) : 0;
		if (pct > 100)
			pct = 100;
		snprintf(membuf, sizeof(membuf), "%u MB", (unsigned)(used >> 20));
	} else {
		snprintf(membuf, sizeof(membuf), "n/d");
	}
	up_sec = timer_uptime_sec();
	snprintf(upbuf, sizeof(upbuf), "UP %02u:%02u:%02u",
	         (unsigned)(up_sec / 3600u), (unsigned)((up_sec / 60u) % 60u),
	         (unsigned)(up_sec % 60u));

	rx = sw - TOPBAR_PAD_X;
	for (i = 0; i < 4; i++) {
		/* 0 = hora, 1 = fecha, 2 = uptime, 3 = memoria */
		int gw;
		int gx;
		int draw_group = 1;

		if (i == 1 && !show_date)
			draw_group = 0;
		if (i == 2 && !show_up)
			draw_group = 0;
		if (!draw_group)
			continue;

		if (i == 0) {
			gw = text_width(TEXT_LABEL, clock_s);
		} else if (i == 1) {
			gw = text_width(TEXT_CAPTION, date_s);
		} else if (i == 2) {
			gw = text_width(TEXT_CAPTION, upbuf);
		} else {
			gw = 48 + SP_2 + text_width(TEXT_CAPTION, membuf);
		}
		gx = rx - gw;
		if (gx < bx + TOPBAR_BTN_SIZE + SP_8) {
			/* sin sitio: se omite el grupo */
			continue;
		}

		if (i == 0) {
			text_draw(TEXT_LABEL, gx, wy, clock_s, theme.text);
		} else if (i == 1) {
			text_draw(TEXT_CAPTION, gx,
			          (TOPBAR_H - text_height(TEXT_CAPTION)) / 2,
			          date_s, theme.text_faint);
		} else if (i == 2) {
			text_draw(TEXT_CAPTION, gx,
			          (TOPBAR_H - text_height(TEXT_CAPTION)) / 2,
			          upbuf, theme.text_dim);
		} else {
			int bar_y = (TOPBAR_H - BAR_HEIGHT) / 2;

			gfx_fill_round_rect(gx, bar_y, 48, BAR_HEIGHT, BAR_RADIUS,
			                    theme.surface_3);
			if (pct > 0)
				gfx_fill_round_rect(gx, bar_y, (48 * pct) / 100, BAR_HEIGHT,
				                    BAR_RADIUS, theme.accent);
			text_draw(TEXT_CAPTION, gx + 48 + SP_2,
			          (TOPBAR_H - text_height(TEXT_CAPTION)) / 2,
			          membuf, theme.text_dim);
		}
		rx = gx;

		/* separador vertical de 1 px entre grupos visibles */
		if (i != 3) {
			int next = i + 1;

			if (next == 1 && !show_date)
				next = 2;
			if (next == 2 && !show_up)
				next = 3;
			if (next <= 3) {
				rx -= SP_3;
				if (rx > bx + TOPBAR_BTN_SIZE + SP_4)
					gfx_fill_rect_alpha(rx, (TOPBAR_H - 14) / 2, 1, 14,
					                    theme.border, 40);
				rx -= SP_3;
			}
		}
	}

	/* centro: accesos de navegacion (topnav) o nombre de app (dock) */
	{
		int left = topbar_menu_btn_x() + TOPBAR_BTN_SIZE + SP_3;
		int right = rx - SP_3;
		int total = topbar_nav_total();
		int x0 = -1;

		if (nav_visible()) {
			/* prioridad: centro geometrico de la pantalla */
			int preferred = sw / 2 - total / 2;

			if (preferred >= left + SP_3 && preferred + total <= right - SP_3)
				x0 = preferred;
			else if (right - left > total + SP_3 * 2)
				x0 = (left + right - total) / 2;
		}

		if (x0 >= 0) {
			struct window *focused = window_active_window();
			app_t *focused_app = (focused && window_visible(focused))
			                         ? window_app(focused) : 0;

			nav_drawn = 1;
			nav_x0 = x0;
			for (i = 0; i < DOCK_ICONS; i++) {
				int cx = topbar_nav_cx(i);
				app_t *a = app_find(dock_ids[i]);
				struct window *w = app_window(dock_ids[i]);
				int open = (w != 0);
				int active = (a && focused_app == a);
				int hovered = (dock_hover_index == i);
				uint32_t tint;

				if (active)
					gfx_fill_round_rect(cx - TOPBAR_NAV_TILE / 2, 1,
					                    TOPBAR_NAV_TILE, TOPBAR_NAV_TILE,
					                    RADIUS_XS, theme.accent_soft);
				else if (hovered)
					gfx_fill_round_rect(cx - TOPBAR_NAV_TILE / 2, 1,
					                    TOPBAR_NAV_TILE, TOPBAR_NAV_TILE,
					                    RADIUS_XS, theme.surface_3);
				tint = active ? theme.text
				              : (open ? dock_tints[i] : theme.text_faint);
				if (i == DOCK_ICONS - 1)
					icons_draw_info_badge(cx, TOPBAR_NAV_TILE / 2 + 1,
					                      TOPBAR_NAV_ICON);
				else
					icons_draw_color(dock_ids[i], cx,
					                 TOPBAR_NAV_TILE / 2 + 1,
					                 TOPBAR_NAV_ICON, tint);
				if (open)
					gfx_fill_rect(cx - 1, TOPBAR_H - 6, 3, 3, theme.accent);
				if (active)
					gfx_fill_rect(cx - TOPBAR_NAV_TILE / 2, TOPBAR_H - 2,
					              TOPBAR_NAV_TILE, 2, theme.accent);
				if (hovered)
					draw_tooltip(dock_names[i], cx, TOPBAR_H + 30);
			}
		} else {
			nav_drawn = 0;
			if (!nav_visible()) {
				name = active_app_name();
				name_w = text_width(TEXT_SMALL, name);
				if (right - left > name_w + SP_6)
					text_draw_center(TEXT_SMALL, (left + right) / 2, cy, name,
					                 theme.text_dim);
			}
		}
	}
}

/* ------------------------------------------------------------------ */
/* menu desplegable                                                   */
/* ------------------------------------------------------------------ */

#define MENU_X (topbar_menu_btn_x() - 2)
#define MENU_Y (TOPBAR_H + SP_1)

static void menu_item_rect(int index, int *x, int *y, int *w, int *h) {
	int base = MENU_Y + MENU_HEADER_H + MENU_PAD_Y;

	*x = MENU_X + 4;
	*w = MENU_W - 8;
	*h = MENU_ITEM_H;
	if (index < 5) {
		/* apps: Acerca de, Archivos, Terminal, Monitor, PAC-MAN */
		*y = base + index * MENU_ITEM_H;
	} else {
		/* grupo de sistema, tras el separador: Reiniciar, Apagar */
		*y = base + index * MENU_ITEM_H + MENU_SEP_GAP;
	}
}

static int menu_item_at(int x, int y) {
	int i;

	if (!menu_open)
		return -1;
	if (!point_in(x, y, MENU_X, MENU_Y, MENU_W, MENU_H))
		return -1;
	for (i = 0; i < MENU_ITEMS; i++) {
		int ix, iy, iw, ih;

		menu_item_rect(i, &ix, &iy, &iw, &ih);
		if (point_in(x, y, ix, iy, iw, ih))
			return i;
	}
	return -1;
}

static void menu_activate(int item) {
	if (item < 0 || item >= MENU_ITEMS)
		return;
	if (item == MENU_ITEMS - 2) {
		/* Reiniciar: contrato del kernel (kernel/shutdown.h); muestra la
		 * pantalla "Reiniciando..." y reinicia el equipo */
		sereos_restart();
		for (;;)
			hlt();
	}
	if (item == MENU_ITEMS - 1) {
		/* Apagar: contrato del kernel (kernel/shutdown.h) */
		serial_write("SEREOS_SHUTDOWN\n");
		sereos_shutdown();
		for (;;)
			hlt();
	}
	gui_open_app(menu_apps[item]);
}

static void draw_menu(void) {
	int i;

	if (!menu_open)
		return;

	gfx_shadow(MENU_X, MENU_Y + 2, MENU_W, MENU_H, RADIUS_MD, 80);
	gfx_fill_round_rect(MENU_X, MENU_Y, MENU_W, MENU_H, RADIUS_MD, theme.surface_2);
	gfx_draw_round_rect(MENU_X, MENU_Y, MENU_W, MENU_H, RADIUS_MD, theme.border);

	/* cabecera: logotipo OFICIAL (circular) + wordmark + version discreta.
	 * El glifo ribbon del asset nuevo es exclusivo de la top bar. */
	{
		int ly = MENU_Y + MENU_HEADER_H / 2;
		int lh = MENU_LOGO;      /* contenedor cuadrado */
		int lx = MENU_X + SP_3 + lh / 2;

		logo_draw_brand(lx, ly, lh);
		text_draw(TEXT_LABEL, MENU_X + SP_3 + lh + SP_2,
		          ly - text_height(TEXT_LABEL) / 2, SEREOS_NAME, theme.text);
		text_draw_right(TEXT_CAPTION, MENU_X + MENU_W - SP_3,
		                ly - text_height(TEXT_CAPTION) / 2,
		                "v" SEREOS_VERSION, theme.text_faint);
		gfx_fill_rect(MENU_X + SP_3, MENU_Y + MENU_HEADER_H - 1,
		              MENU_W - SP_3 * 2, 1, theme.border);
	}

	for (i = 0; i < MENU_ITEMS; i++) {
		int ix, iy, iw, ih;
		int hovered = (menu_hover == i);
		uint32_t color;

		menu_item_rect(i, &ix, &iy, &iw, &ih);
		if (i == 5) {
			/* separador antes del grupo de sistema (Reiniciar/Apagar) */
			ui_divider_alpha(MENU_X + SP_3, iy - MENU_SEP_GAP / 2,
			                 MENU_W - SP_3 * 2, 170);
		}
		if (hovered)
			gfx_fill_round_rect(ix, iy, iw, ih, RADIUS_SM, theme.accent_soft);
		color = (i >= 5) ? theme.text_dim : theme.text;
		if (i == 0) {
			/* About: insignia "i" en circulo (misma que ventana y dock) */
			icons_draw_info_badge(ix + SP_3 + 8, iy + ih / 2, MENU_APP_ICON);
		} else {
			icons_draw_color(menu_icons[i], ix + SP_3 + 8, iy + ih / 2, 16,
			                 hovered ? theme.text : color);
		}
		text_draw(TEXT_BODY, ix + SP_3 + 16 + SP_2,
		          iy + (ih - text_height(TEXT_BODY)) / 2, menu_labels[i], color);
	}

	/* pista de atajo Alt+W (debajo del ultimo item del menu) */
	{
		int hx = MENU_X + SP_3;
		int hy = MENU_Y + MENU_HEADER_H + MENU_PAD_Y +
		         MENU_ITEMS * MENU_ITEM_H + MENU_SEP_GAP +
		         (MENU_HINT_H - text_height(TEXT_CAPTION)) / 2;

		text_draw(TEXT_CAPTION, hx, hy, "Alt+W  Cerrar ventana", theme.text_faint);
	}
}

/* ------------------------------------------------------------------ */
/* dock inferior                                                      */
/* ------------------------------------------------------------------ */

static void dock_rect(int *x, int *y, int *w, int *h) {
	int sw = gfx_width();
	int sh = gfx_height();

	*w = DOCK_W;
	*h = DOCK_HEIGHT;
	*x = (sw - DOCK_W) / 2;
	*y = sh - DOCK_BOTTOM - DOCK_HEIGHT;
}

/* indice de icono del dock bajo (x,y); el dock solo es interactivo
 * mientras es visible durante la transicion */
static int dock_index_at(int x, int y) {
	int dx, dy, dw, dh, rel;

	if (nav_anim >= NAV_ANIM_SWITCH)
		return -1;
	dock_rect(&dx, &dy, &dw, &dh);
	dy += dock_slide();
	if (y < dy - 32 || y > dy + dh)
		return -1;
	if (x < dx || x >= dx + dw)
		return -1;
	rel = x - dx - DOCK_PAD;
	if (rel < 0)
		return -1;
	rel /= (DOCK_TILE + DOCK_ICON_GAP);
	if (rel < 0 || rel >= DOCK_ICONS)
		return -1;
	return rel;
}

static struct window *app_window(const char *id) {
	app_t *a = app_find(id);
	int i;

	if (!a)
		return 0;
	for (i = 0; i < window_count(); i++) {
		struct window *w = window_get(i);

		if (window_app(w) == a && !window_is_pending_close(w))
			return w;
	}
	return 0;
}

/* click en la barra: abre, restaura, enfoca o minimiza segun el estado */
static void bar_activate_app(int index) {
	const char *id;
	app_t *a;
	struct window *w;

	if (index < 0 || index >= DOCK_ICONS)
		return;
	id = dock_ids[index];
	a = app_find(id);
	if (!a)
		return;
	w = app_window(id);
	if (!w) {
		gui_open_app(id);
		return;
	}
	if (window_minimized(w))
		window_restore(w);
	else if (window_active(w) && window_visible(w))
		window_minimize(w);
	else
		window_focus(w);
}

static void draw_tooltip(const char *text, int cx, int bottom_y) {
	int tw = text_width(TEXT_CAPTION, text);
	int pw = tw + SP_3 * 2;
	int px = cx - pw / 2;
	int py = bottom_y - 26;

	if (px < SP_1)
		px = SP_1;
	if (px + pw > gfx_width() - SP_1)
		px = gfx_width() - SP_1 - pw;
	gfx_shadow(px, py + 1, pw, 20, RADIUS_SM, 70);
	gfx_fill_round_rect(px, py, pw, 20, RADIUS_SM, theme.surface_2);
	gfx_draw_round_rect(px, py, pw, 20, RADIUS_SM, theme.border);
	text_draw_center(TEXT_CAPTION, cx, py + (20 - text_height(TEXT_CAPTION)) / 2,
	                 text, theme.text);
}

static const uint32_t dock_tints[DOCK_ICONS] = {
	0x7EA7FF,   /* files   - azul suave */
	0xB8C2D6,   /* terminal- grafito claro */
	0x56C596,   /* monitor - verde */
	0xE3B25A,   /* game    - ambar */
	0xC3CAD8    /* about   - gris calido */
};

static void draw_dock(void) {
	int dx, dy, dw, dh, i;

	dock_rect(&dx, &dy, &dw, &dh);
	gfx_shadow(dx, dy + 2, dw, dh, DOCK_RADIUS, 60);
	gfx_fill_round_rect_alpha(dx, dy, dw, dh, DOCK_RADIUS, theme.surface, 220);
	gfx_draw_round_rect(dx, dy, dw, dh, DOCK_RADIUS, theme.border);

	for (i = 0; i < DOCK_ICONS; i++) {
		int cx = dx + DOCK_PAD + i * (DOCK_TILE + DOCK_ICON_GAP) + DOCK_TILE / 2;
		int icy = dy + 26;
		int hovered = (dock_hover_index == i);

		/* un solo panel: el hover es un redondeo suave sin borde */
		if (hovered)
			gfx_fill_round_rect(cx - DOCK_TILE / 2, icy - DOCK_TILE / 2,
			                    DOCK_TILE, DOCK_TILE, RADIUS_SM,
			                    theme.surface_3);
		if (i == DOCK_ICONS - 1) {
			/* About: insignia "i" en circulo azul/celeste (no el logo S) */
			icons_draw_info_badge(cx, icy, DOCK_ICON);
		} else {
			icons_draw_color(dock_ids[i], cx, icy, DOCK_ICON,
			                 hovered ? theme.text : dock_tints[i]);
		}
		if (app_window(dock_ids[i]))
			gfx_fill_rect(cx - 1, dy + dh - 8, 3, 3, theme.accent);
		if (hovered)
			draw_tooltip(dock_names[i], cx, dy - 6);
	}
}

/* barra inferior: solo el dock flotante; en modo navegacion superior no se
 * dibuja absolutamente nada abajo (la ventana llega hasta el borde) */
static void draw_bottom_bar(void) {
	if (nav_anim < NAV_ANIM_SWITCH)
		draw_dock();
}

/* ------------------------------------------------------------------ */
/* ventanas: marco y composicion                                      */
/* ------------------------------------------------------------------ */

#define CORNER_BLOCK 16
static uint32_t corner_bg[4][CORNER_BLOCK * CORNER_BLOCK];

/* guarda/restaura bloques de pixeles del backbuffer (esquinas redondeadas) */
static void block_save(int x, int y, int w, int h, uint32_t *dst) {
	uint32_t *bb = backbuffer();
	uint32_t stride = fb_width();
	int sw = gfx_width();
	int sh = gfx_height();
	int i, j;

	if (bb && stride >= (uint32_t)sw) {
		for (j = 0; j < h; j++) {
			for (i = 0; i < w; i++) {
				int gx = x + i, gy = y + j;

				if (gx >= 0 && gy >= 0 && gx < sw && gy < sh)
					dst[j * w + i] = bb[(uint32_t)gy * stride + (uint32_t)gx];
				else
					dst[j * w + i] = 0;
			}
		}
		return;
	}
	for (j = 0; j < h; j++)
		for (i = 0; i < w; i++)
			dst[j * w + i] = gfx_get_pixel(x + i, y + j);
}


/* test de pertenencia a un rectangulo redondeado (mismo criterio que
 * gfx_fill_round_rect). Se usa para decidir que pixeles de las esquinas
 * pertenecen a la ventana y cuales al fondo que hay detras. */
static int inside_round_window(int px, int py, int x, int y, int w, int h, int r)
{
	int cx, cy, dx, dy;

	if (px < x || py < y || px >= x + w || py >= y + h)
		return 0;
	if (r < 0) r = 0;
	if (r > w / 2) r = w / 2;
	if (r > h / 2) r = h / 2;
	if (r == 0)
		return 1;
	cx = px;
	cy = py;
	if (cx < x + r) cx = x + r;
	else if (cx > x + w - 1 - r) cx = x + w - 1 - r;
	if (cy < y + r) cy = y + r;
	else if (cy > y + h - 1 - r) cy = y + h - 1 - r;
	dx = px - cx;
	dy = py - cy;
	return (dx * dx + dy * dy) <= r * r;
}

/* guarda el fondo (wallpaper/ventanas inferiores/sombra) bajo las cuatro
 * esquinas ANTES de pintar la ventana */
static void save_window_corners(int x, int y, int w, int h)
{
	block_save(x, y, CORNER_BLOCK, CORNER_BLOCK, corner_bg[0]);
	block_save(x + w - CORNER_BLOCK, y, CORNER_BLOCK, CORNER_BLOCK, corner_bg[1]);
	block_save(x, y + h - CORNER_BLOCK, CORNER_BLOCK, CORNER_BLOCK, corner_bg[2]);
	block_save(x + w - CORNER_BLOCK, y + h - CORNER_BLOCK,
	           CORNER_BLOCK, CORNER_BLOCK, corner_bg[3]);
}

/* tras dibujar el contenido de la app, restaura SOLO los pixeles de las
 * esquinas que quedan fuera del contorno redondeado. Asi el contenido de la
 * aplicacion llega hasta el borde redondeado sin dejar parches cuadrados y el
 * fondo/sombra exterior se conserva intacto. */
static void restore_window_corners_masked(int x, int y, int w, int h)
{
	const int bx[4] = { x, x + w - CORNER_BLOCK, x, x + w - CORNER_BLOCK };
	const int by[4] = { y, y, y + h - CORNER_BLOCK, y + h - CORNER_BLOCK };
	uint32_t *bb = backbuffer();
	uint32_t stride = fb_width();
	int sw = gfx_width();
	int sh = gfx_height();
	int c, i, j;

	for (c = 0; c < 4; c++) {
		for (j = 0; j < CORNER_BLOCK; j++) {
			for (i = 0; i < CORNER_BLOCK; i++) {
				int gx = bx[c] + i;
				int gy = by[c] + j;

				if (inside_round_window(gx, gy, x, y, w, h, WIN_RADIUS))
					continue;
				if (gx < 0 || gy < 0 || gx >= sw || gy >= sh)
					continue;
				if (bb && stride >= (uint32_t)sw)
					bb[(uint32_t)gy * stride + (uint32_t)gx] =
					    corner_bg[c][j * CORNER_BLOCK + i];
				else
					gfx_put_pixel(gx, gy, corner_bg[c][j * CORNER_BLOCK + i]);
			}
		}
	}
}

/* Botones compartidos por TODAS las ventanas (frame unico de desktop.c).
 * Orden izquierda->derecha: minimizar (ambar), maximizar/restaurar (verde),
 * cerrar (rojo). Los glifos oscuros son SIEMPRE visibles y ganan contraste
 * en hover. Las metricas (centro/radio) vienen de window.c. */
static void draw_traffic_lights(struct window *w) {
	int active = window_active(w);
	int hovered_btn = (tl_hover_window == w) ? tl_hover_button : -1;
	int radius = window_button_radius();
	uint32_t base[WINDOW_BUTTON_COUNT];
	int i;

	base[WINDOW_BUTTON_MINIMIZE] = theme.amber;
	base[WINDOW_BUTTON_MAXIMIZE] = theme.green;
	base[WINDOW_BUTTON_CLOSE] = theme.red;

	for (i = 0; i < WINDOW_BUTTON_COUNT; i++) {
		int cx, cy;
		uint32_t color, glyph;
		int hovered;

		if (!window_button_center(w, i, &cx, &cy))
			continue;
		color = active ? base[i]
		               : gui_color_blend(base[i], theme.surface_2, 165);
		hovered = (hovered_btn == i);
		if (hovered)
			color = gui_color_blend(color, theme.white, active ? 38 : 20);
		gfx_fill_circle(cx, cy, radius, color);

		/* glifo oscuro legible sobre el circulo; hover = mas contraste */
		glyph = gui_color_blend(color, theme.black, hovered ? 215 : 165);

		if (i == WINDOW_BUTTON_MINIMIZE) {
			gfx_draw_line(cx - 2, cy, cx + 2, cy, glyph);
		} else if (i == WINDOW_BUTTON_MAXIMIZE) {
			if (window_maximized(w)) {
				/* restaurar: dos cuadrados superpuestos */
				gfx_draw_rect(cx - 1, cy - 3, 4, 4, glyph);
				gfx_draw_rect(cx - 3, cy - 1, 4, 4, glyph);
			} else {
				gfx_draw_rect(cx - 2, cy - 2, 5, 5, glyph);
			}
		} else {
			gfx_draw_line(cx - 2, cy - 2, cx + 2, cy + 2, glyph);
			gfx_draw_line(cx - 2, cy + 2, cx + 2, cy - 2, glyph);
		}
	}
}

static void draw_window_title(struct window *w, int x, int y, int ww, int active) {
	const char *title = window_title(w);
	int tw = text_width(TEXT_LABEL, title);
	int inset = window_title_side_inset();
	int left = x + inset;
	int right = x + ww - inset;
	int avail = right - left;
	int ty = y + (WIN_TITLEBAR_H - text_height(TEXT_LABEL)) / 2;
	int tx;

	if (avail <= 40)
		return;
	/* centrado GEOMETRICO en la ventana (x + ww/2) con recorte simetrico
	 * que reserva la zona de botones; no se desplaza al maximizar */
	tx = x + ww / 2 - tw / 2;
	if (tx + tw > right)
		tx = right - tw;
	if (tx < left)
		tx = left;
	text_draw_clipped(TEXT_LABEL, tx, ty, title,
	                  active ? theme.text : theme.text_faint,
	                  left, y, avail, WIN_TITLEBAR_H);
}

static void draw_window_content(struct window *w, int x, int y, int ww, int hh) {
	int clip[4];
	int cw, ch, cx, cy;
	app_t *a;

	(void)x; (void)y; (void)ww; (void)hh;
	cw = window_content_w(w);
	ch = window_content_h(w);
	cx = window_content_x(w);
	cy = window_content_y(w);
	if (cw <= 0 || ch <= 0)
		return;
	gfx_get_clip(&clip[0], &clip[1], &clip[2], &clip[3]);
	{
		int l = imax(clip[0], cx);
		int t = imax(clip[1], cy);
		int r = imin(clip[0] + clip[2], cx + cw);
		int b = imin(clip[1] + clip[3], cy + ch);

		if (r > l && b > t) {
			gfx_set_clip(l, t, r - l, b - t);
			a = window_app(w);
			if (a && a->draw)
				a->draw(w);
			gfx_set_clip(clip[0], clip[1], clip[2], clip[3]);
		}
	}
}

static void draw_window(struct window *w, int with_shadow) {
	int x, y, ww, hh, active;
	uint32_t title_bg;

	if (!window_visible(w))
		return;
	x = window_x(w);
	y = window_y(w);
	ww = window_width(w);
	hh = window_height(w);
	if (ww <= 0 || hh <= 0)
		return;
	active = window_active(w);
	title_bg = active ? theme.surface_2 : theme.surface;

	if (window_maximized(w)) {
		/* full-bleed: sin sombra, radios ni borde exterior; la ventana
		 * cubre exactamente el area entre la barra superior y la barra
		 * de tareas (ninguna franja de wallpaper alrededor) */
		gfx_fill_rect(x, y, ww, hh, theme.surface);
		gfx_fill_rect(x, y, ww, WIN_TITLEBAR_H, title_bg);
		gfx_fill_rect(x, y + WIN_TITLEBAR_H - 1, ww, 1, theme.border);
		gfx_fill_rect(x, y + WIN_TITLEBAR_H, ww, hh - WIN_TITLEBAR_H,
		              theme.surface);
		draw_traffic_lights(w);
		draw_window_title(w, x, y, ww, active);
		draw_window_content(w, x, y, ww, hh);
		return;
	}

	/* ventana normal: tarjeta flotante con sombra sutil y esquinas */
	if (with_shadow) {
		gfx_shadow(x, y + 3, ww, hh, WIN_RADIUS, 70);
		gfx_shadow(x, y + 8, ww, hh, WIN_RADIUS, WIN_SHADOW_ALPHA);
	}
	/* fondo real bajo las esquinas (wallpaper/ventanas inferiores/sombra) */
	save_window_corners(x, y, ww, hh);
	gfx_fill_round_rect(x, y, ww, hh, WIN_RADIUS, theme.surface);
	gfx_fill_round_rect(x, y, ww, WIN_TITLEBAR_H + WIN_RADIUS, WIN_RADIUS,
	                    title_bg);
	gfx_fill_rect(x, y + WIN_RADIUS, ww, WIN_TITLEBAR_H - WIN_RADIUS,
	              title_bg);
	gfx_fill_rect(x + WIN_BORDER, y + WIN_TITLEBAR_H - 1,
	              ww - WIN_BORDER * 2, 1, theme.border);
	gfx_fill_rect(x + WIN_BORDER, y + WIN_TITLEBAR_H, ww - WIN_BORDER * 2,
	              hh - WIN_TITLEBAR_H - WIN_BORDER, theme.surface);
	gfx_draw_round_rect(x, y, ww, hh, WIN_RADIUS,
	                    active ? theme.border_strong : theme.border);

	draw_traffic_lights(w);
	draw_window_title(w, x, y, ww, active);
	draw_window_content(w, x, y, ww, hh);
	/* recorta el contenido a la forma redondeada y redibuja el contorno */
	restore_window_corners_masked(x, y, ww, hh);
	gfx_draw_round_rect(x, y, ww, hh, WIN_RADIUS,
	                    active ? theme.border_strong : theme.border);
}

/* ------------------------------------------------------------------ */
/* composicion                                                        */
/* ------------------------------------------------------------------ */

static void compose_full(void) {
	int sw = gfx_width();
	int sh = gfx_height();
	int i;

	gfx_reset_clip();
	wallpaper_region(0, 0, sw, sh);
	for (i = 0; i < window_count(); i++) {
		struct window *w = window_get(i);

		if (window_visible(w)) {
			draw_window(w, 1);
			window_clear_frame(w);
		}
	}
	draw_bottom_bar();
	draw_topbar();
	if (menu_open)
		draw_menu();
	gfx_reset_clip();
	gfx_mark_all_dirty();
	dirty_topbar = 0;
	dirty_dock = 0;
	dirty_menu = 0;
}

static int rect_intersects(int ax, int ay, int aw, int ah,
                           int bx, int by, int bw, int bh) {
	return !(ax >= bx + bw || bx >= ax + aw || ay >= by + bh || by >= ay + ah);
}

static void compose_region(int x, int y, int w, int h) {
	int i, dx, dy, dw, dh;
	int sw = gfx_width();

	if (w <= 0 || h <= 0)
		return;
	wallpaper_region(x, y, w, h);
	gfx_set_clip(x, y, w, h);
	for (i = 0; i < window_count(); i++) {
		struct window *w2 = window_get(i);

		if (!window_visible(w2))
			continue;
		if (!rect_intersects(x, y, w, h, window_x(w2) - WIN_MARGIN,
		                     window_y(w2) - WIN_MARGIN,
		                     window_width(w2) + WIN_MARGIN * 2,
		                     window_height(w2) + WIN_MARGIN * 2))
			continue;
		draw_window(w2, 1);
	}
	if (nav_anim < NAV_ANIM_SWITCH) {
		dock_rect(&dx, &dy, &dw, &dh);
		dy += dock_slide();
		if (rect_intersects(x, y, w, h, dx - 24, dy - 36, dw + 48, dh + 46))
			draw_dock();
	}
	if (rect_intersects(x, y, w, h, 0, 0, sw, TOPBAR_H + 44))
		draw_topbar();
	if (menu_open && rect_intersects(x, y, w, h, MENU_X, MENU_Y, MENU_W, MENU_H))
		draw_menu();
	gfx_reset_clip();
	gfx_mark_dirty(x, y, w, h);
}

static void compose_window_region(struct window *w) {
	if (window_maximized(w)) {
		/* full-bleed: no hay sombra que cubra, se repinta el rect exacto */
		compose_region(window_x(w), window_y(w),
		               window_width(w), window_height(w));
		return;
	}
	compose_region(window_x(w) - WIN_MARGIN, window_y(w) - WIN_MARGIN,
	               window_width(w) + WIN_MARGIN * 2,
	               window_height(w) + WIN_MARGIN * 2);
}

/* ------------------------------------------------------------------ */
/* animaciones y hover                                                */
/* ------------------------------------------------------------------ */

static void update_hovers(void) {
	int mx = input_mouse_x();
	int my = input_mouse_y();
	int idx, hot;

	/* reloj / uptime: refresco una vez por segundo */
	{
		uint32_t up = timer_uptime_sec();

		if (up != last_uptime_sec) {
			last_uptime_sec = up;
			dirty_topbar = 1;
		}
	}

	/* boton de menu */
	hot = point_in(mx, my, topbar_menu_btn_x(), topbar_menu_btn_y(),
	               TOPBAR_BTN_SIZE, TOPBAR_BTN_SIZE);
	if (hot != menu_btn_hover) {
		menu_btn_hover = hot;
		dirty_topbar = 1;
	}

	/* hover de los accesos (topbar) o del dock, segun el modo actual */
	idx = nav_visible() ? topbar_nav_index_at(mx, my) : dock_index_at(mx, my);
	if (idx != dock_hover_index) {
		dock_hover_index = idx;
		if (nav_visible())
			dirty_topbar = 1;
		else
			dirty_dock = 1;
	}

	/* hover del menu desplegable */
	if (menu_open) {
		int item = menu_item_at(mx, my);

		if (item != menu_hover) {
			menu_hover = item;
			dirty_menu = 1;
		}
	} else {
		menu_hover = -1;
	}

	/* hover de los semaforos de la ventana bajo el cursor */
	{
		struct window *hw = window_at(mx, my);
		int hb = -1;

		if (hw && window_visible(hw) && my >= window_y(hw) &&
		    my < window_y(hw) + WIN_TITLEBAR_H) {
			if (window_hit_minimize(hw, mx, my))
				hb = WINDOW_BUTTON_MINIMIZE;
			else if (window_hit_maximize(hw, mx, my))
				hb = WINDOW_BUTTON_MAXIMIZE;
			else if (window_hit_close(hw, mx, my))
				hb = WINDOW_BUTTON_CLOSE;
		}
		if (hw != tl_hover_window || hb != tl_hover_button) {
			if (tl_hover_window)
				window_invalidate(tl_hover_window);
			if (hw)
				window_invalidate(hw);
			tl_hover_window = hw;
			tl_hover_button = hb;
		}
	}
}

/* ------------------------------------------------------------------ */
/* entrada                                                            */
/* ------------------------------------------------------------------ */

static int window_exists(struct window *w) {
	int i;

	for (i = 0; i < window_count(); i++) {
		if (window_get(i) == w)
			return 1;
	}
	return 0;
}

/* arrastre por barra de titulo; solo empieza a mover tras superar el umbral
 * de 4 px, para que un doble clic no desplace la ventana */
static void drag_update(int mx, int my) {
	int ox, oy, nx, ny, ww, hh;

	if (!drag_window)
		return;
	if (!drag_moved) {
		if (iabs(mx - drag_start_x) < 4 && iabs(my - drag_start_y) < 4)
			return;
		drag_moved = 1;
	}
	ox = drag_prev_x;
	oy = drag_prev_y;
	ww = drag_prev_w;
	hh = drag_prev_h;
	window_move(drag_window, mx - drag_dx, my - drag_dy);
	nx = window_x(drag_window);
	ny = window_y(drag_window);
	if (nx == ox && ny == oy)
		return;
	compose_region(ox - WIN_MARGIN, oy - WIN_MARGIN,
	               ww + WIN_MARGIN * 2, hh + WIN_MARGIN * 2);
	compose_region(nx - WIN_MARGIN, ny - WIN_MARGIN,
	               ww + WIN_MARGIN * 2, hh + WIN_MARGIN * 2);
	drag_prev_x = nx;
	drag_prev_y = ny;
	drag_prev_w = window_width(drag_window);
	drag_prev_h = window_height(drag_window);
}

static void start_resize(struct window *w, int zone, int mx, int my) {
	resize_window = w;
	resize_zone_bits = zone;
	resize_start_x = mx;
	resize_start_y = my;
	resize_orig_x = window_x(w);
	resize_orig_y = window_y(w);
	resize_orig_w = window_width(w);
	resize_orig_h = window_height(w);
	resize_prev_x = resize_orig_x;
	resize_prev_y = resize_orig_y;
	resize_prev_w = resize_orig_w;
	resize_prev_h = resize_orig_h;
}

/* aplica el redimensionado activo con ventana_set_geometry y repinta solo
 * las dos regiones afectadas */
static void resize_update(int mx, int my) {
	int nx, ny, nw, nh, dx, dy;

	if (!resize_window)
		return;
	dx = mx - resize_start_x;
	dy = my - resize_start_y;
	nx = resize_orig_x;
	ny = resize_orig_y;
	nw = resize_orig_w;
	nh = resize_orig_h;
	if (resize_zone_bits & RZ_LEFT) {
		nw -= dx;
		nx += dx;
	}
	if (resize_zone_bits & RZ_RIGHT)
		nw += dx;
	if (resize_zone_bits & RZ_BOTTOM)
		nh += dy;
	window_set_geometry(resize_window, nx, ny, nw, nh);
	nx = window_x(resize_window);
	ny = window_y(resize_window);
	nw = window_width(resize_window);
	nh = window_height(resize_window);
	if (nx == resize_prev_x && ny == resize_prev_y &&
	    nw == resize_prev_w && nh == resize_prev_h)
		return;
	compose_region(resize_prev_x - WIN_MARGIN, resize_prev_y - WIN_MARGIN,
	               resize_prev_w + WIN_MARGIN * 2,
	               resize_prev_h + WIN_MARGIN * 2);
	compose_region(nx - WIN_MARGIN, ny - WIN_MARGIN,
	               nw + WIN_MARGIN * 2, nh + WIN_MARGIN * 2);
	resize_prev_x = nx;
	resize_prev_y = ny;
	resize_prev_w = nw;
	resize_prev_h = nh;
}

/* clic simple/doble en la barra de titulo (doble <= 350 ms -> maximizar) */
static void handle_title_click(struct window *w, int x, int y) {
	uint32_t now = timer_ticks();
	int is_double;

	is_double = (dbl_window == w && (now - dbl_tick) <= 35 &&
	             iabs(x - dbl_x) <= 4 && iabs(y - dbl_y) <= 4);
	if (is_double) {
		dbl_window = 0;
		window_toggle_maximize(w);
		return;
	}
	dbl_window = w;
	dbl_tick = now;
	dbl_x = x;
	dbl_y = y;
}

static void route_mouse_to_window(const event_t *ev) {
	struct window *w = window_at(ev->mouse_x, ev->mouse_y);

	if (!w || window_is_pending_close(w))
		return;
	if (window_app(w) && window_app(w)->event)
		window_app(w)->event(w, ev);
}

void desktop_dispatch_event(const event_t *ev) {
	if (!ev)
		return;

	switch (ev->type) {
	case EVENT_MOUSE_MOVE:
		if (resize_window)
			resize_update(ev->mouse_x, ev->mouse_y);
		else if (drag_window)
			drag_update(ev->mouse_x, ev->mouse_y);
		else
			route_mouse_to_window(ev);
		break;

	case EVENT_MOUSE_DOWN:
		/* el menu abierto captura el clic */
		if (menu_open) {
			int item = menu_item_at(ev->mouse_x, ev->mouse_y);

			menu_open = 0;
			menu_hover = -1;
			gui_request_redraw();
			if (item >= 0)
				menu_activate(item);
			break;
		}
		/* boton de menu */
		if (point_in(ev->mouse_x, ev->mouse_y, topbar_menu_btn_x(),
		             topbar_menu_btn_y(), TOPBAR_BTN_SIZE, TOPBAR_BTN_SIZE)) {
			menu_open = 1;
			menu_hover = -1;
			gui_request_redraw();
			break;
		}
		/* accesos de la top bar (modo navegacion superior) */
		{
			int ni = topbar_nav_index_at(ev->mouse_x, ev->mouse_y);

			if (ni >= 0) {
				bar_activate_app(ni);
				break;
			}
		}
		/* dock flotante (solo si esta visible) */
		{
			int di = dock_index_at(ev->mouse_x, ev->mouse_y);

			if (di >= 0) {
				bar_activate_app(di);
				break;
			}
		}
		/* ventana bajo el cursor */
		{
			struct window *w = window_at(ev->mouse_x, ev->mouse_y);

			if (!w || window_is_pending_close(w))
				break;
			window_focus(w);
			if (window_hit_close(w, ev->mouse_x, ev->mouse_y)) {
				window_close(w);
				break;
			}
			if (window_hit_minimize(w, ev->mouse_x, ev->mouse_y)) {
				window_minimize(w);
				break;
			}
			if (window_hit_maximize(w, ev->mouse_x, ev->mouse_y)) {
				window_toggle_maximize(w);
				break;
			}
			/* redimensionado por bordes/esquinas (solo normales) */
			{
				int zone = resize_zone_at(w, ev->mouse_x, ev->mouse_y);

				if (zone) {
					start_resize(w, zone, ev->mouse_x, ev->mouse_y);
					break;
				}
			}
			if (window_hit_title_drag(w, ev->mouse_x, ev->mouse_y)) {
				drag_window = w;
				drag_dx = ev->mouse_x - window_x(w);
				drag_dy = ev->mouse_y - window_y(w);
				drag_start_x = ev->mouse_x;
				drag_start_y = ev->mouse_y;
				drag_moved = 0;
				drag_prev_x = window_x(w);
				drag_prev_y = window_y(w);
				drag_prev_w = window_width(w);
				drag_prev_h = window_height(w);
			} else if (window_app(w) && window_app(w)->event) {
				window_app(w)->event(w, ev);
			}
		}
		break;

	case EVENT_MOUSE_UP:
		if (resize_window) {
			resize_window = 0;
			break;
		}
		if (drag_window) {
			struct window *dw = drag_window;

			drag_window = 0;
			if (!drag_moved)
				handle_title_click(dw, ev->mouse_x, ev->mouse_y);
			else
				dbl_window = 0;
			break;
		}
		route_mouse_to_window(ev);
		break;

	case EVENT_MOUSE_WHEEL:
		route_mouse_to_window(ev);
		break;

	case EVENT_KEY_DOWN:
	case EVENT_KEY_UP:
		if (menu_open && ev->type == EVENT_KEY_DOWN && ev->key == KEY_ESC) {
			menu_open = 0;
			menu_hover = -1;
			gui_request_redraw();
			break;
		}
		{
			struct window *w = window_active_window();

			if (w && window_visible(w) && !window_is_pending_close(w) &&
			    window_app(w) && window_app(w)->event)
				window_app(w)->event(w, ev);
		}
		break;

	default:
		break;
	}
}

/* ------------------------------------------------------------------ */
/* ciclo de frame                                                     */
/* ------------------------------------------------------------------ */

void desktop_tick(void) {
	uint32_t now = timer_ticks();
	int i;

	/* 1. aplicar cierres / focos diferidos antes de componer */
	window_process_pending();
	if (drag_window && !window_exists(drag_window))
		drag_window = 0;
	if (resize_window && !window_exists(resize_window))
		resize_window = 0;
	if (dbl_window && !window_exists(dbl_window))
		dbl_window = 0;

	/* 2. cambio dock <-> navegacion superior: reclampar y recomponer todo */
	{
		desktop_bar_state_t st = desktop_bar_state();

		if (st != last_bar_state) {
			last_bar_state = st;
			dock_hover_index = -1;
			anim_last_tick = timer_ticks();
			window_clamp_all();
			gui_request_redraw();
		}
	}

	/* 3. transicion discreta (~145 ms): el dock baja y solo entonces aparece
	 * la nav en la topbar; al reves al restaurar. Sin iconos duplicados. */
	{
		int target = (last_bar_state == DESKTOP_BAR_TOPNAV) ? 1000 : 0;

		if (nav_anim != target) {
			uint32_t nt = timer_ticks();
			uint32_t dt = nt - anim_last_tick;
			uint32_t hz = timer_hz();
			int old = nav_anim;

			anim_last_tick = nt;
			if (hz == 0)
				hz = 100;
			if (dt > 0) {
				int step = (int)(dt * (1000u * NAV_ANIM_STEP_PER_MS) / hz);

				if (nav_anim < target) {
					nav_anim += step;
					if (nav_anim > target)
						nav_anim = target;
				} else {
					nav_anim -= step;
					if (nav_anim < target)
						nav_anim = target;
				}
				if (old < NAV_ANIM_SWITCH || nav_anim < NAV_ANIM_SWITCH)
					dirty_dock = 1;
				if ((old < NAV_ANIM_SWITCH) != (nav_anim < NAV_ANIM_SWITCH))
					dirty_topbar = 1;
			}
		}
	}

	/* 4. hover y reloj */
	last_tick_ref = now;
	update_hovers();

	/* 5. recompostura completa si hay cambio estructural pendiente */
	if (gui_full_redraw_pending) {
		gui_full_redraw_pending = 0;
		compose_full();
		return;
	}

	/* 6. repintado parcial: ventanas invalidadas, topbar, barra y menu */
	for (i = 0; i < window_count(); i++) {
		struct window *w = window_get(i);

		if (window_visible(w) && window_needs_frame(w)) {
			window_clear_frame(w);
			compose_window_region(w);
		}
	}
	if (dirty_topbar) {
		dirty_topbar = 0;
		/* la superficie de la top bar es translucida: hay que recomponer
		 * la franja (wallpaper + ventanas + barra), no repintarla encima;
		 * de lo contrario quedan fantasmas de los accesos de navegacion
		 * al pasar de ventana maximizada a normal. */
		compose_region(0, 0, gfx_width(), TOPBAR_H + 44);
	}
	if (dirty_dock) {
		int strip = DOCK_HEIGHT + DOCK_BOTTOM + 40;

		dirty_dock = 0;
		compose_region(0, gfx_height() - strip, gfx_width(), strip);
	}
	if (dirty_menu) {
		dirty_menu = 0;
		draw_menu();
		gfx_mark_dirty(MENU_X - SP_4, MENU_Y - SP_4, MENU_W + SP_8,
		               MENU_H + SP_8);
	}
}

/* 1 si queda trabajo de dibujo pendiente para este frame */
int desktop_work_pending(void) {
	int i;

	if (gui_full_redraw_pending || dirty_topbar || dirty_dock || dirty_menu)
		return 1;
	for (i = 0; i < window_count(); i++) {
		struct window *w = window_get(i);

		if (window_visible(w) && window_needs_frame(w))
			return 1;
	}
	return 0;
}

/* ------------------------------------------------------------------ */
/* API publica (desktop.h)                                            */
/* ------------------------------------------------------------------ */

void desktop_init(void) {
	wallpaper_valid = 0;
	wallpaper_w = 0;
	wallpaper_h = 0;
	dirty_topbar = 0;
	dirty_dock = 0;
	dirty_menu = 0;
	menu_open = 0;
	menu_hover = -1;
	menu_btn_hover = 0;
	drag_window = 0;
	drag_moved = 0;
	dbl_window = 0;
	resize_window = 0;
	dock_hover_index = -1;
	last_bar_state = DESKTOP_BAR_DOCK;
	nav_anim = 0;
	anim_last_tick = timer_ticks();
	nav_x0 = gfx_width() / 2 - topbar_nav_total() / 2;
	nav_drawn = 0;
	tl_hover_window = 0;
	tl_hover_button = -1;
	app_name_set = 0;
	app_name_override[0] = 0;
	last_uptime_sec = 0xFFFFFFFFu;
	last_tick_ref = timer_ticks();

	/* prepara y cachea el fondo de escritorio (no dibuja el resto) */
	wallpaper_ensure();
	gui_request_redraw();
	serial_write("DESKTOP_INIT\n");
}

/* recompone todo el escritorio (lo usa splash para la transicion final) */
void desktop_draw_all(void) {
	compose_full();
}

void desktop_open_app(const char *id) {
	gui_open_app(id);
}

void desktop_close_all(void) {
	while (window_count() > 0) {
		struct window *w = window_get(window_count() - 1);

		if (!w)
			break;
		window_close(w);
		window_process_pending();
	}
	drag_window = 0;
	gui_request_redraw();
}

void desktop_set_app_name(const char *name) {
	if (!name) {
		app_name_set = 0;
		app_name_override[0] = 0;
	} else {
		strncpy(app_name_override, name, sizeof(app_name_override) - 1);
		app_name_override[sizeof(app_name_override) - 1] = 0;
		app_name_set = app_name_override[0] != 0;
	}
	dirty_topbar = 1;
}
