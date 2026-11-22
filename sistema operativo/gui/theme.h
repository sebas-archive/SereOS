/* gui/theme.h - sistema de diseno de SereOS (tokens visuales unicos)
 *
 * Toda la interfaz comparte esta escala: colores, espaciado (multiplos de 4),
 * radios, metricas de ventana, tipografia (graphics/text.h) e iconografia.
 * Ninguna aplicacion debe inventar colores o margenes fuera de estos tokens.
 */
#ifndef SEREOS_THEME_H
#define SEREOS_THEME_H
#include <stdint.h>
#include "text.h"

/* ------------------------------------------------------------------ */
/* paleta                                                              */
/* ------------------------------------------------------------------ */
typedef struct {
	/* fondos y superficies */
	uint32_t bg;             /* fondo del escritorio: carbon azulado */
	uint32_t bg_elevated;    /* fondo de paneles flotantes */
	uint32_t surface;        /* superficie principal de ventana */
	uint32_t surface_2;      /* barras, sidebar, tarjetas */
	uint32_t surface_3;      /* hover / seleccion suave */
	uint32_t border;         /* borde de 1 px */
	uint32_t border_strong;  /* borde enfocado */
	uint32_t shadow;         /* color de sombra */

	/* texto */
	uint32_t text;           /* texto principal, blanco calido */
	uint32_t text_dim;       /* texto secundario */
	uint32_t text_faint;     /* metadatos */

	/* acentos y estados */
	uint32_t accent;         /* azul electrico moderado */
	uint32_t accent_soft;    /* relleno de seleccion */
	uint32_t cyan;           /* acento secundario */
	uint32_t green;          /* correcto */
	uint32_t amber;          /* advertencia */
	uint32_t red;            /* error */
	uint32_t white;
	uint32_t black;

	/* compatibilidad con codigo anterior (se eliminara gradualmente) */
	uint32_t bg_deep, bg_mid, bg_glow;
	uint32_t surface_hi, surface_low;
	uint32_t border_hi;
	uint32_t accent2;
	uint32_t yellow;
	uint32_t window_bg, titlebar, titlebar_inactive;
	uint32_t dock_bg, topbar_bg, menu_bg;
} theme_t;

extern const theme_t theme;

/* mezcla alfa 0..255 */
uint32_t gui_color_blend(uint32_t fg, uint32_t bg, uint8_t alpha);

/* ------------------------------------------------------------------ */
/* escala de espaciado (multiplos de 4 px)                             */
/* ------------------------------------------------------------------ */
#define SP_0   0
#define SP_1   4
#define SP_2   8
#define SP_3   12
#define SP_4   16
#define SP_5   20
#define SP_6   24
#define SP_8   32
#define SP_10  40
#define SP_12  48

/* radios */
#define RADIUS_XS     4
#define RADIUS_SM     6
#define RADIUS_MD     10
#define RADIUS_LG     14
#define RADIUS_XL     18

/* ------------------------------------------------------------------ */
/* metricas de escritorio                                              */
/* ------------------------------------------------------------------ */
#define TOPBAR_H          30
#define TOPBAR_PAD_X      12
/* ALTURA del glifo PNG de la marca en la barra superior (no es lado de
 * contenedor: el glifo ribbon se dibuja suelto, sin fondo). Se fija a la
 * altura visual de las mayusculas del wordmark (TEXT_LABEL 12 px). */
#define TOPBAR_LOGO       10

/* ------------------------------------------------------------------ */
/* logotipo oficial (ver gui/logo.h y docs/LOGO.md)                    */
/* ------------------------------------------------------------------ */
/* Todos los tokens son el LADO del contenedor cuadrado del logotipo.
 * Las formas (circulo, squircle, cuadrado redondeado) las resuelve el
 * componente; aqui solo se fija el tamano en cada ubicacion. */
#define LOGO_RING_GAP     4    /* separacion del anillo exterior del splash */
#define MENU_LOGO         24   /* cabecera del menu desplegable (circulo) */
#define ABOUT_LOGO        60   /* Acerca de (cuadrado redondeado 22%) */
#define SPLASH_LOGO       88   /* splash en resoluciones altas (76-96) */
#define SPLASH_LOGO_SMALL 76   /* splash en resoluciones bajas (<600 px) */
#define APP_LOGO          40   /* icono de app/acceso directo (= DOCK_ICON) */
#define PANIC_LOGO        18   /* cabecera de la pantalla de panico */

/* navegacion adaptativa: accesos en la top bar cuando hay una ventana
 * maximizada (el dock inferior desaparece) */
#define TOPBAR_NAV_ICON   18
#define TOPBAR_NAV_TILE   24
#define TOPBAR_NAV_GAP    2

#define DOCK_HEIGHT       58
#define DOCK_RADIUS       16
#define DOCK_ICON         40
#define DOCK_ICON_GAP     6
#define DOCK_PAD          8
#define DOCK_BOTTOM       8
#define DOCK_INDICATOR    3

/* ventanas */
#define WIN_RADIUS        10
#define WIN_TITLEBAR_H    34
#define WIN_BORDER        1
#define WIN_MIN_W         300
#define WIN_MIN_H         180
#define WIN_SHADOW_ALPHA  90

/* controles */
#define CTRL_HEIGHT       28
#define CTRL_RADIUS       6
#define CARD_RADIUS       8
#define BAR_HEIGHT        6
#define BAR_RADIUS        3
#define LIST_ROW_H        28
#define STATUS_DOT        6

/* ------------------------------------------------------------------ */
/* tipografia (ver graphics/text.h)                                    */
/* ------------------------------------------------------------------ */
#define FONT_UI_TITLE      TEXT_TITLE
#define FONT_UI_BODY       TEXT_BODY
#define FONT_UI_SMALL      TEXT_SMALL
#define FONT_UI_CAPTION    TEXT_CAPTION
#define FONT_UI_LABEL      TEXT_LABEL
#define FONT_MONO_BODY     TEXT_MONO

/* colores semanticos de estado para indicadores y componentes */
#define COLOR_OK      (theme.green)
#define COLOR_WARN    (theme.amber)
#define COLOR_ERROR   (theme.red)
#define COLOR_INFO    (theme.accent)

#endif
