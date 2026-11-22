/* gui/icons.h - iconografia vectorial de SereOS
 *
 * Los iconos se dibujan con trazos geometricos de 1.5-2 px (estilo lineal,
 * sin efectos 3D, sin emojis). Cualquier tamano se compone a partir de un
 * atlas de cobertura alfa generado en tools/gen_ui_icons.py, por lo que
 * mantienen calidad al escalar.
 */
#ifndef SEREOS_ICONS_H
#define SEREOS_ICONS_H
#include <stdint.h>

/* El logotipo oficial vive en su propio componente (gui/logo.h).  Se incluye
 * aqui para mantener la compatibilidad de icons_draw_logo()/icons_logo_width()
 * con el codigo existente. */
#include "logo.h"

/* ids:
 *   sereos, files, folder, file, terminal, monitor, settings, about,
 *   game, power, network, memory, storage, search, close, minimize,
 *   maximize, restore, chevron_left, chevron_right, play, pause,
 *   refresh, info, check, warning, error, disk, home, arrows
 */
void icons_init(void);

/* icono centrado en (x,y) con tamano size, color explicito */
void icons_draw_color(const char *id, int x, int y, int size, uint32_t color);

/* icono con tinte del tema y resalte opcional (para listas/menus) */
void icons_draw(const char *id, int x, int y, int size, int hovered);

/* icono en tile redondeado (dock, launcher) */
void icons_draw_tile(const char *id, int cx, int cy, int tile_size,
                     uint32_t tint, int hovered);

/* icono_info (accesos de "Acerca de"): "i" dentro de un circulo de trazo
 * lineal en el tono azul/celeste de la marca (theme.cyan). Es la UNICA
 * implementacion del icono de informacion y se usa SOLO en los accesos:
 * fila "Acerca de" del menu, tile del dock y su equivalente en la topnav.
 * NO es el logotipo: para la marca y el contenido use el recurso separado
 * logo_sereos (logo_draw_about / logo_draw_topbar / logo_draw_brand). */
void icons_draw_info_badge(int cx, int cy, int size);

/* El logotipo oficial (logo_draw*, icons_draw_logo, icons_logo_width) esta
 * declarado en gui/logo.h, incluido arriba. */

#endif
