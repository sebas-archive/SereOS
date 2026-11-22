/* graphics/graphics.h - motor grafico nativo de SereOS
 *
 * Todas las coordenadas son absolutas de pantalla salvo que se indique lo
 * contrario. El recorte (clipping) esta integrado en cada primitiva.
 * Los colores son 0x00RRGGBB independientes del formato real del framebuffer.
 * La transparencia del compositor se simula con mezcla alfa de colores.
 */
#ifndef SEREOS_GRAPHICS_H
#define SEREOS_GRAPHICS_H
#include <stdint.h>
#include "framebuffer.h"
#include "font.h"

#define GFX_TRANSPARENT 0xF81Fu   /* clave de transparencia en sprites RGB565 */

void     gfx_init(void);
int      gfx_ready(void);
int      gfx_width(void);
int      gfx_height(void);

/* recorte */
void gfx_set_clip(int x, int y, int w, int h);
void gfx_reset_clip(void);
void gfx_get_clip(int *x, int *y, int *w, int *h);
int  gfx_in_clip(int x, int y);

/* primitivas basicas */
void     gfx_clear(uint32_t color);
void     gfx_put_pixel(int x, int y, uint32_t color);
uint32_t gfx_get_pixel(int x, int y);
void     gfx_fill_rect(int x, int y, int w, int h, uint32_t color);
void     gfx_fill_rect_alpha(int x, int y, int w, int h, uint32_t color, uint8_t alpha);
void     gfx_draw_rect(int x, int y, int w, int h, uint32_t color);
void     gfx_draw_line(int x0, int y0, int x1, int y1, uint32_t color);
void     gfx_draw_line_alpha(int x0, int y0, int x1, int y1, uint32_t color, uint8_t alpha);
void     gfx_fill_circle(int cx, int cy, int r, uint32_t color);
void     gfx_draw_circle(int cx, int cy, int r, uint32_t color);
void     gfx_fill_round_rect(int x, int y, int w, int h, int radius, uint32_t color);
void     gfx_fill_round_rect_alpha(int x, int y, int w, int h, int radius,
                                   uint32_t color, uint8_t alpha);
void     gfx_draw_round_rect(int x, int y, int w, int h, int radius, uint32_t color);
void     gfx_gradient_v(int x, int y, int w, int h, uint32_t top, uint32_t bottom);
void     gfx_shadow(int x, int y, int w, int h, int radius, uint8_t strength);
void     gfx_radial_glow(int cx, int cy, int radius, uint32_t color, uint8_t strength);

/* texto */
void gfx_draw_char(int x, int y, char c, uint32_t color, int scale);
void gfx_draw_text(int x, int y, const char *s, uint32_t color, int scale);
void gfx_draw_text_alpha(int x, int y, const char *s, uint32_t color, int scale, uint8_t alpha);
int  gfx_text_width(const char *s, int scale);
int  gfx_text_height(int scale);

/* imagenes */
void gfx_draw_bitmap8(int x, int y, const uint8_t *bits, int w, int h, uint32_t color);
void gfx_draw_sprite(int x, int y, const uint16_t *pixels, int w, int h);
void gfx_draw_sprite_alpha(int x, int y, const uint16_t *pixels, int w, int h, uint8_t alpha);
void gfx_blit_rgb(int x, int y, int w, int h, const uint32_t *pixels);
/* mezcla un pixel con cobertura alfa (0..255) sobre el backbuffer; respeta el clip */
void gfx_blend_pixel(int x, int y, uint32_t color, uint8_t alpha);
/* dibuja una mascara de cobertura alfa 8bpp (filas de w bytes) tintada de color */
void gfx_blit_alpha8(int x, int y, int w, int h, const uint8_t *mask, uint32_t color);

/* composicion / presentacion */
void gfx_mark_dirty(int x, int y, int w, int h);
void gfx_mark_all_dirty(void);
void gfx_present(void);
void gfx_present_dirty(void);

#endif
