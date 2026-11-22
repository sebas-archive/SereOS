/* gui/logo.h - componente reutilizable de la marca de SereOS
 *
 * Dos fuentes de glifo, ambas proporcionadas por el propietario y extraidas a
 * mascaras alfa 8bpp (no se redibuja ni se usa tipografia):
 *   - OFICIAL: assets/logo/official_logo.png (S blanca sobre azul) -> splash,
 *     Acerca de, panico, menu y dock (gui/logo_data.c).
 *   - RIBBON : assets/logo/ribbon_s_logo.png (S blanca ribbon, PNG con
 *     transparencia) -> SOLO la top bar, dibujado como icono suelto sin
 *     contenedor ni fondo (gui/logo_ribbon_data.c).
 * Para las ubicaciones con marca azul, el componente compone el glifo sobre un
 * contenedor de marca (circulo, squircle, cuadrado redondeado o sprite
 * completo) y lo centra por su bbox; logo_draw_icon() dibuja solo el glifo.
 *
 * Coordenadas: (cx,cy) es el CENTRO del contenedor cuadrado de lado `size`.
 * Los tamanos son libres (no hay tokens): el glifo mide
 * round(size*LOGO_GLYPH_RATIO_PCT/100) de alto y conserva la proporcion de su
 * fuente, de modo que siempre queda centrado y sin recortes.
 *
 * La API es 100% estatica (sin heap, sin bloqueos): puede usarse desde el
 * bucle de dibujo e incluso desde la pantalla de panico.
 */
#ifndef SEREOS_LOGO_H
#define SEREOS_LOGO_H
#include <stdint.h>

/* marca para gui/logo_data.h: en esa cabecera el struct del glifo oficial se
 * llama logo_official_glyph_t para no chocar con este enum. */
#define SEREOS_LOGO_GLYPH_T_DEFINED 1

/* formas del contenedor; el valor 0 se reserva para el sprite completo y
 * mantiene la compatibilidad con icons_draw_logo() */
typedef enum {
	LOGO_SHAPE_PLAIN = 0,
	LOGO_SHAPE_CIRCLE,
	LOGO_SHAPE_SQUIRCLE,
	LOGO_SHAPE_ROUNDED
} logo_shape_t;

/* fuente del glifo S:
 *   LOGO_GLYPH_OFFICIAL : marca oficial (splash, Acerca de, panico, menu, dock)
 *   LOGO_GLYPH_RIBBON   : asset "Minimalist White Ribbon S Logo" (solo top bar)
 * Ambas se centran por su bbox y se extraen de los PNG oficiales; ninguna se
 * redibuja ni se deforma. */
typedef enum {
	LOGO_GLYPH_OFFICIAL = 0,
	LOGO_GLYPH_RIBBON
} logo_glyph_t;

/* colores de marca (muestreados del PNG oficial) */
#define LOGO_BRAND_BLUE  0x004EFDu
#define LOGO_BRAND_WHITE 0xFFFFFFu

/* proporcion del glifo oficial (ancho/alto = 354/376 = 0,9415; caja de
 * cobertura alfa 366x386) y fraccion de altura del contenedor que ocupa la S
 * (56 %, comun a las dos fuentes) */
#define LOGO_GLYPH_ASPECT_NUM 354
#define LOGO_GLYPH_ASPECT_DEN 376
#define LOGO_GLYPH_RATIO_PCT  56

/* proporcion del glifo ribbon (caja real del asset: 834x944 = 0,8835) */
#define LOGO_RIBBON_ASPECT_NUM 834
#define LOGO_RIBBON_ASPECT_DEN 944

/* Dibuja el logotipo centrado en (cx,cy).
 *   shape      : LOGO_SHAPE_* (PLAIN = sprite oficial completo)
 *   radius_pct : solo ROUNDED; radio = round(size*radius_pct/100); si es <=0
 *                se usa el 22 % por defecto.
 *   ring_alpha : 0 = sin anillo; >0 dibuja un anillo exterior de 1 px con
 *                radio size/2+LOGO_RING_GAP mezclado sobre theme.bg (lo usa
 *                el splash). En PLAIN se ignora.
 * Usa siempre el glifo OFICIAL. */
void logo_draw(int cx, int cy, int size, logo_shape_t shape, int radius_pct,
               uint8_t ring_alpha);

/* Variante generica: contenedor + glifo elegido (OFICIAL o RIBBON). */
void logo_draw_glyph(int cx, int cy, int size, logo_shape_t shape,
                     int radius_pct, uint8_t ring_alpha, logo_glyph_t glyph);

/* Dibuja SOLO el glifo (sin contenedor, sin anillo y sin fondo): mascara alfa
 * blanca centrada en (cx,cy), con altura exacta `height` (se elige la mascara
 * exacta o la mas cercana de la tabla; NUNCA se escala en runtime). La mascara
 * ya trae su propio antialiasing. Es lo que usa la top bar con el PNG ribbon. */
void logo_draw_icon(int cx, int cy, int height, logo_glyph_t glyph);

/* Ancho real del glifo para esa altura (0 si height <= 0). Para RIBBON,
 * round(height*834/944); para OFICIAL, la proporcion de su tabla. */
int  logo_icon_width(int height, logo_glyph_t glyph);

/* atajos semanticos de la interfaz */
/* top bar: SOLO el glifo RIBBON del PNG, sin fondo azul. `size` es la ALTURA
 * del glifo (no el lado de un contenedor). */
void logo_draw_topbar(int cx, int cy, int size);
void logo_draw_brand(int cx, int cy, int size);     /* CIRCLE + glifo OFICIAL */
void logo_draw_splash(int cx, int cy, int size);    /* CIRCLE + anillo, OFICIAL */
void logo_draw_about(int cx, int cy, int size);     /* ROUNDED 22 %, OFICIAL */
void logo_draw_app_icon(int cx, int cy, int size);  /* SQUIRCLE, OFICIAL */

/* lado total ocupado (contenedor + anillo exterior si ring_alpha > 0) */
int  logo_extent(int size, uint8_t ring_alpha);

/* compatibilidad con la API anterior: sprite oficial completo (PLAIN).
 * (x,y) sigue siendo el centro; la altura es `size` y el ancho se deriva de
 * la proporcion original (nunca se deforma). */
void icons_draw_logo(int x, int y, int size);
int  icons_logo_width(int size);

#endif /* SEREOS_LOGO_H */
