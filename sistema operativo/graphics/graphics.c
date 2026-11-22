/* graphics/graphics.c - motor grafico nativo de SereOS
 *
 * Primitivas 2D en software para el compositor de 1024x768.  Todas las
 * funciones:
 *   - trabajan sobre el backbuffer del framebuffer (doble buffer),
 *   - aplican clipping integrado contra la region fijada con gfx_set_clip(),
 *   - reciben colores 0x00RRGGBB y escriben pixeles en el formato real del
 *     hardware (la conversion se hace una vez por primitiva con
 *     fb_map_color() salvo en las mezclas alfa, que ya trabajan en formato
 *     canonico),
 *   - rellenan por filas completas (no pixel a pixel) y usan rep stosl/
 *     rep movsl en tramos grandes para reducir el coste en QEMU.
 *
 * El backbuffer contiene pixeles ya convertidos al formato del hardware.
 * Con el modo tipico BGRX de 8 bits por canal (1024x768x32) eso coincide
 * exactamente con 0x00RRGGBB, de modo que las rutas rapidas son identidad.
 *
 * Sin libc del host: solo <stdint.h>/<stddef.h>.
 */
#include <stdint.h>
#include <stddef.h>
#include "graphics.h"

#define GFX_MAX_RADIUS 4096

/* --- estado del motor --------------------------------------------------- */
static uint32_t *g_px;          /* backbuffer, stride = g_w */
static int g_w;                 /* ancho de pantalla en pixeles */
static int g_h;                 /* alto de pantalla en pixeles */
static int g_ready;             /* 1 tras gfx_init() con framebuffer valido */
static int g_fast;              /* 1 si las mascaras RGB son canonicas */
static uint8_t g_rp, g_rs;      /* mascara del rojo */
static uint8_t g_gp, g_gs;      /* mascara del verde */
static uint8_t g_bp, g_bs;      /* mascara del azul */
static int g_clip_x0, g_clip_y0;   /* clip [x0,x1) [y0,y1) */
static int g_clip_x1, g_clip_y1;

/* ======================================================================== */
/* utilidades matematicas y de color                                       */
/* ======================================================================== */

static uint32_t isqrt_u32(uint32_t v)
{
	uint32_t x, y;

	if (v < 2u) {
		return v;
	}
	x = v;
	y = (x + 1u) / 2u;
	while (y < x) {
		x = y;
		y = (x + v / x) / 2u;
	}
	return x;
}

/* division exacta por 255 para valores 0..65025 (sin idiv) */
static inline uint32_t div255(uint32_t v)
{
	return (v + 1u + (v >> 8)) >> 8;
}

static inline uint32_t channel_scale(uint32_t c, uint8_t size)
{
	if (size == 0u) {
		return 0u;
	}
	if (size >= 8u) {
		uint32_t shift = (uint32_t)(size - 8u);
		if (shift > 24u) {
			shift = 24u;
		}
		return c << shift;
	}
	return c >> (8u - size);
}

static inline uint32_t channel_expand(uint32_t v, uint8_t size)
{
	if (size == 0u) {
		return 0u;
	}
	if (size >= 8u) {
		if (size == 8u) {
			return v;
		}
		return v >> (uint32_t)(size - 8u);
	}
	if (size < 4u) {
		return v << (8u - size);
	}
	return (v << (8u - size)) | (v >> (2u * size - 8u));
}

/* pixel del backbuffer -> 0x00RRGGBB */
static inline uint32_t px_decode(uint32_t p)
{
	uint32_t r, g, b;

	if (g_fast) {
		return p & 0x00FFFFFFu;
	}
	r = (p >> g_rp) & ((1u << g_rs) - 1u);
	g = (p >> g_gp) & ((1u << g_gs) - 1u);
	b = (p >> g_bp) & ((1u << g_bs) - 1u);
	return (channel_expand(r, g_rs) << 16) |
	       (channel_expand(g, g_gs) << 8) |
	       channel_expand(b, g_bs);
}

/* 0x00RRGGBB -> pixel del backbuffer */
static inline uint32_t px_encode(uint32_t rgb)
{
	if (g_fast) {
		return rgb & 0x00FFFFFFu;
	}
	return (channel_scale((rgb >> 16) & 0xFFu, g_rs) << g_rp) |
	       (channel_scale((rgb >> 8) & 0xFFu, g_gs) << g_gp) |
	       (channel_scale(rgb & 0xFFu, g_bs) << g_bp);
}

/* mezcla alfa 0..255 de dos colores canonicos */
static inline uint32_t blend_rgb(uint32_t dst, uint32_t src, uint32_t a)
{
	uint32_t ia = 255u - a;
	uint32_t r = div255(((src >> 16) & 0xFFu) * a +
	                    ((dst >> 16) & 0xFFu) * ia);
	uint32_t g = div255(((src >> 8) & 0xFFu) * a +
	                    ((dst >> 8) & 0xFFu) * ia);
	uint32_t b = div255((src & 0xFFu) * a + (dst & 0xFFu) * ia);
	return (r << 16) | (g << 8) | b;
}

/* Mezcla sobre un pixel ya almacenado en el backbuffer. */
static inline uint32_t blend_mapped(uint32_t dst, uint32_t src, uint32_t a)
{
	return px_encode(blend_rgb(px_decode(dst), src, a));
}

/* ======================================================================== */
/* escritura de pixeles y tramos                                           */
/* ======================================================================== */

static inline uint32_t *row_ptr(int y)
{
	return g_px + (size_t)y * (size_t)g_w;
}

static inline int point_in_clip(int x, int y)
{
	return x >= g_clip_x0 && x < g_clip_x1 &&
	       y >= g_clip_y0 && y < g_clip_y1;
}

/* Rellena `count` pixeles consecutivos con un color ya convertido. */
static inline void span_fill(uint32_t *dst, int count, uint32_t mapped)
{
	if (count <= 0) {
		return;
	}
#if defined(__i386__)
	if (count >= 32) {
		__asm__ volatile ("rep stosl"
		                  : "+D"(dst), "+c"(count)
		                  : "a"(mapped)
		                  : "memory");
		return;
	}
#endif
	while (count-- > 0) {
		*dst++ = mapped;
	}
}

static inline void copy_words(uint32_t *dst, const uint32_t *src, int count)
{
	if (count <= 0) {
		return;
	}
#if defined(__i386__)
	if (count >= 16) {
		uint32_t *s = (uint32_t *)(uintptr_t)src;
		__asm__ volatile ("rep movsl"
		                  : "+D"(dst), "+S"(s), "+c"(count)
		                  :
		                  : "memory");
		return;
	}
#endif
	while (count-- > 0) {
		*dst++ = *src++;
	}
}

static inline void put_mapped(int x, int y, uint32_t mapped)
{
	g_px[(size_t)y * (size_t)g_w + (size_t)x] = mapped;
}

/* Mezcla alfa de `src` (0x00RRGGBB) sobre `count` pixeles. */
static void blend_span(uint32_t *dst, int count, uint32_t src, uint32_t a)
{
	if (count <= 0 || a == 0u) {
		return;
	}
	if (a >= 255u) {
		span_fill(dst, count, px_encode(src));
		return;
	}
	if (g_fast) {
		uint32_t sr = (src >> 16) & 0xFFu;
		uint32_t sg = (src >> 8) & 0xFFu;
		uint32_t sb = src & 0xFFu;
		uint32_t ia = 255u - a;
		while (count-- > 0) {
			uint32_t d = *dst & 0x00FFFFFFu;
			uint32_t r = div255(sr * a + ((d >> 16) & 0xFFu) * ia);
			uint32_t g = div255(sg * a + ((d >> 8) & 0xFFu) * ia);
			uint32_t b = div255(sb * a + (d & 0xFFu) * ia);
			*dst++ = (r << 16) | (g << 8) | b;
		}
		return;
	}
	while (count-- > 0) {
		*dst = blend_mapped(*dst, src, a);
		dst++;
	}
}

/* Mezcla alfa sobre un unico pixel (sin comprobar clip). */
static inline void put_alpha_px(int x, int y, uint32_t src, uint32_t a)
{
	uint32_t *p = row_ptr(y) + x;
	*p = blend_mapped(*p, src, a);
}

/* Recorta un rectangulo contra el clip.  Devuelve 0 si queda vacio. */
static int rect_clip(int *x, int *y, int *w, int *h)
{
	int x0 = *x;
	int y0 = *y;
	int x1 = x0 + *w;
	int y1 = y0 + *h;

	if (*w <= 0 || *h <= 0) {
		return 0;
	}
	if (x0 < g_clip_x0) {
		x0 = g_clip_x0;
	}
	if (y0 < g_clip_y0) {
		y0 = g_clip_y0;
	}
	if (x1 > g_clip_x1) {
		x1 = g_clip_x1;
	}
	if (y1 > g_clip_y1) {
		y1 = g_clip_y1;
	}
	if (x1 <= x0 || y1 <= y0) {
		return 0;
	}
	*x = x0;
	*y = y0;
	*w = x1 - x0;
	*h = y1 - y0;
	return 1;
}

/* ======================================================================== */
/* inicializacion y recorte                                                */
/* ======================================================================== */

void gfx_init(void)
{
	const fb_info_t *info;

	g_ready = 0;
	if (!fb_available() || !fb_has_backbuffer()) {
		return;
	}

	/* Continuidad: lo que ya este dibujado en la VRAM (splash de GRUB o
	 * fb_draw_test_pattern) pasa al backbuffer antes del primer frame. */
	fb_copy_direct_to_backbuffer();

	g_px = fb_backbuffer();
	if (g_px == 0) {
		return;
	}
	g_w = (int)fb_width();
	g_h = (int)fb_height();
	if (g_w <= 0 || g_h <= 0) {
		return;
	}

	info = fb_info();
	g_rp = info->red_pos;
	g_rs = info->red_size;
	g_gp = info->green_pos;
	g_gs = info->green_size;
	g_bp = info->blue_pos;
	g_bs = info->blue_size;
	g_fast = (g_rp == 16u && g_rs == 8u && g_gp == 8u && g_gs == 8u &&
	          g_bp == 0u && g_bs == 8u) ? 1 : 0;

	gfx_reset_clip();
	g_ready = 1;
	fb_mark_all_dirty();
}

int gfx_ready(void)
{
	return g_ready ? 1 : 0;
}

int gfx_width(void)
{
	return g_w;
}

int gfx_height(void)
{
	return g_h;
}

void gfx_set_clip(int x, int y, int w, int h)
{
	int x0 = x;
	int y0 = y;
	int x1 = x + w;
	int y1 = y + h;

	if (x0 < 0) {
		x0 = 0;
	}
	if (y0 < 0) {
		y0 = 0;
	}
	if (x1 > g_w) {
		x1 = g_w;
	}
	if (y1 > g_h) {
		y1 = g_h;
	}
	if (x1 < x0) {
		x1 = x0;
	}
	if (y1 < y0) {
		y1 = y0;
	}
	g_clip_x0 = x0;
	g_clip_y0 = y0;
	g_clip_x1 = x1;
	g_clip_y1 = y1;
}

void gfx_reset_clip(void)
{
	g_clip_x0 = 0;
	g_clip_y0 = 0;
	g_clip_x1 = g_w;
	g_clip_y1 = g_h;
}

void gfx_get_clip(int *x, int *y, int *w, int *h)
{
	if (x != 0) {
		*x = g_clip_x0;
	}
	if (y != 0) {
		*y = g_clip_y0;
	}
	if (w != 0) {
		*w = g_clip_x1 - g_clip_x0;
	}
	if (h != 0) {
		*h = g_clip_y1 - g_clip_y0;
	}
}

int gfx_in_clip(int x, int y)
{
	if (!g_ready) {
		return 0;
	}
	return point_in_clip(x, y) ? 1 : 0;
}

/* ======================================================================== */
/* primitivas basicas                                                      */
/* ======================================================================== */

void gfx_clear(uint32_t color)
{
	gfx_fill_rect(0, 0, g_w, g_h, color);
}

void gfx_put_pixel(int x, int y, uint32_t color)
{
	if (!g_ready || !point_in_clip(x, y)) {
		return;
	}
	put_mapped(x, y, fb_map_color(color));
}

uint32_t gfx_get_pixel(int x, int y)
{
	if (!g_ready || !point_in_clip(x, y)) {
		return 0u;
	}
	return fb_get_pixel(x, y);
}

/* Mezcla un unico pixel con cobertura alfa 0..255.  Lo usa el motor de texto
 * para glifos sueltos y los iconos para bordes suavizados. */
void gfx_blend_pixel(int x, int y, uint32_t color, uint8_t alpha)
{
	if (!g_ready || alpha == 0u || !point_in_clip(x, y)) {
		return;
	}
	if (alpha >= 255u) {
		put_mapped(x, y, fb_map_color(color));
		return;
	}
	put_alpha_px(x, y, color, alpha);
}

/*
 * Dibuja una mascara de cobertura alfa 8bpp (filas de w bytes, 0 =
 * transparente, 255 = opaco) tintada de `color`.  Es la primitiva del motor
 * tipografico: un unico recorrido por filas, sin decodificar color por pixel
 * en el formato habitual y respetando el clip del motor.
 */
void gfx_blit_alpha8(int x, int y, int w, int h, const uint8_t *mask,
                     uint32_t color)
{
	int x0, y0, x1, y1, yy;

	if (!g_ready || mask == 0 || w <= 0 || h <= 0) {
		return;
	}
	if (x + w <= g_clip_x0 || x >= g_clip_x1 ||
	    y + h <= g_clip_y0 || y >= g_clip_y1) {
		return;
	}
	x0 = (x < g_clip_x0) ? g_clip_x0 : x;
	x1 = (x + w > g_clip_x1) ? g_clip_x1 : x + w;
	y0 = (y < g_clip_y0) ? g_clip_y0 : y;
	y1 = (y + h > g_clip_y1) ? g_clip_y1 : y + h;
	if (x1 <= x0 || y1 <= y0) {
		return;
	}

	if (g_fast) {
		uint32_t sr = (color >> 16) & 0xFFu;
		uint32_t sg = (color >> 8) & 0xFFu;
		uint32_t sb = color & 0xFFu;
		for (yy = y0; yy < y1; yy++) {
			const uint8_t *src = mask +
			    (size_t)(yy - y) * (size_t)w + (size_t)(x0 - x);
			uint32_t *row = row_ptr(yy) + x0;
			int count = x1 - x0;
			while (count-- > 0) {
				uint32_t a = *src++;
				if (a != 0u) {
					if (a >= 255u) {
						*row = (sr << 16) | (sg << 8) | sb;
					} else {
						uint32_t d = *row & 0x00FFFFFFu;
						uint32_t ia = 255u - a;
						uint32_t r = div255(sr * a +
						    ((d >> 16) & 0xFFu) * ia);
						uint32_t g = div255(sg * a +
						    ((d >> 8) & 0xFFu) * ia);
						uint32_t b = div255(sb * a +
						    (d & 0xFFu) * ia);
						*row = (r << 16) | (g << 8) | b;
					}
				}
				row++;
			}
		}
		return;
	}

	for (yy = y0; yy < y1; yy++) {
		const uint8_t *src = mask +
		    (size_t)(yy - y) * (size_t)w + (size_t)(x0 - x);
		uint32_t *row = row_ptr(yy) + x0;
		int count = x1 - x0;
		while (count-- > 0) {
			uint32_t a = *src++;
			if (a != 0u) {
				row[0] = blend_mapped(row[0], color, a);
			}
			row++;
		}
	}
}

void gfx_fill_rect(int x, int y, int w, int h, uint32_t color)
{
	uint32_t mapped;
	int yy;

	if (!g_ready || w <= 0 || h <= 0) {
		return;
	}
	if (!rect_clip(&x, &y, &w, &h)) {
		return;
	}
	mapped = fb_map_color(color);
	for (yy = y; yy < y + h; yy++) {
		span_fill(row_ptr(yy) + x, w, mapped);
	}
}

void gfx_fill_rect_alpha(int x, int y, int w, int h, uint32_t color,
                         uint8_t alpha)
{
	int yy;

	if (!g_ready || w <= 0 || h <= 0 || alpha == 0u) {
		return;
	}
	if (alpha >= 255u) {
		gfx_fill_rect(x, y, w, h, color);
		return;
	}
	if (!rect_clip(&x, &y, &w, &h)) {
		return;
	}
	for (yy = y; yy < y + h; yy++) {
		blend_span(row_ptr(yy) + x, w, color, alpha);
	}
}

void gfx_draw_rect(int x, int y, int w, int h, uint32_t color)
{
	if (!g_ready || w <= 0 || h <= 0) {
		return;
	}
	if (w <= 2 || h <= 2) {
		gfx_fill_rect(x, y, w, h, color);
		return;
	}
	gfx_fill_rect(x, y, w, 1, color);
	gfx_fill_rect(x, y + h - 1, w, 1, color);
	gfx_fill_rect(x, y + 1, 1, h - 2, color);
	gfx_fill_rect(x + w - 1, y + 1, 1, h - 2, color);
}

/* Limita coordenadas de linea a un rango seguro (evita desbordes de int). */
static void clamp_line_coord(int *v)
{
	if (*v < -20000) {
		*v = -20000;
	} else if (*v > 20000) {
		*v = 20000;
	}
}

void gfx_draw_line(int x0, int y0, int x1, int y1, uint32_t color)
{
	uint32_t mapped;
	int dx, dy, sx, sy, err;

	if (!g_ready) {
		return;
	}
	clamp_line_coord(&x0);
	clamp_line_coord(&y0);
	clamp_line_coord(&x1);
	clamp_line_coord(&y1);
	/* rechazo rapido por caja envolvente */
	if ((x0 < g_clip_x0 && x1 < g_clip_x0) ||
	    (x0 >= g_clip_x1 && x1 >= g_clip_x1) ||
	    (y0 < g_clip_y0 && y1 < g_clip_y0) ||
	    (y0 >= g_clip_y1 && y1 >= g_clip_y1)) {
		return;
	}

	mapped = fb_map_color(color);
	dx = x1 - x0;
	if (dx < 0) {
		dx = -dx;
	}
	dy = y1 - y0;
	if (dy < 0) {
		dy = -dy;
	}
	sx = (x0 < x1) ? 1 : -1;
	sy = (y0 < y1) ? 1 : -1;
	err = dx - dy;

	for (;;) {
		if (point_in_clip(x0, y0)) {
			put_mapped(x0, y0, mapped);
		}
		if (x0 == x1 && y0 == y1) {
			break;
		}
		{
			int e2 = err * 2;
			if (e2 > -dy) {
				err -= dy;
				x0 += sx;
			}
			if (e2 < dx) {
				err += dx;
				y0 += sy;
			}
		}
	}
}

void gfx_draw_line_alpha(int x0, int y0, int x1, int y1, uint32_t color,
                         uint8_t alpha)
{
	int dx, dy, sx, sy, err;

	if (!g_ready || alpha == 0u) {
		return;
	}
	if (alpha >= 255u) {
		gfx_draw_line(x0, y0, x1, y1, color);
		return;
	}
	clamp_line_coord(&x0);
	clamp_line_coord(&y0);
	clamp_line_coord(&x1);
	clamp_line_coord(&y1);
	if ((x0 < g_clip_x0 && x1 < g_clip_x0) ||
	    (x0 >= g_clip_x1 && x1 >= g_clip_x1) ||
	    (y0 < g_clip_y0 && y1 < g_clip_y0) ||
	    (y0 >= g_clip_y1 && y1 >= g_clip_y1)) {
		return;
	}

	dx = x1 - x0;
	if (dx < 0) {
		dx = -dx;
	}
	dy = y1 - y0;
	if (dy < 0) {
		dy = -dy;
	}
	sx = (x0 < x1) ? 1 : -1;
	sy = (y0 < y1) ? 1 : -1;
	err = dx - dy;

	for (;;) {
		if (point_in_clip(x0, y0)) {
			put_alpha_px(x0, y0, color, alpha);
		}
		if (x0 == x1 && y0 == y1) {
			break;
		}
		{
			int e2 = err * 2;
			if (e2 > -dy) {
				err -= dy;
				x0 += sx;
			}
			if (e2 < dx) {
				err += dx;
				y0 += sy;
			}
		}
	}
}

void gfx_fill_circle(int cx, int cy, int r, uint32_t color)
{
	uint32_t mapped;
	uint32_t rr;
	int y0, y1, yy;

	if (!g_ready || r <= 0) {
		if (g_ready && r == 0) {
			gfx_put_pixel(cx, cy, color);
		}
		return;
	}
	if (r > GFX_MAX_RADIUS) {
		r = GFX_MAX_RADIUS;
	}
	if (cx + r < g_clip_x0 || cx - r >= g_clip_x1 ||
	    cy + r < g_clip_y0 || cy - r >= g_clip_y1) {
		return;
	}
	mapped = fb_map_color(color);
	rr = (uint32_t)(r * r);
	y0 = cy - r;
	if (y0 < g_clip_y0) {
		y0 = g_clip_y0;
	}
	y1 = cy + r;
	if (y1 > g_clip_y1 - 1) {
		y1 = g_clip_y1 - 1;
	}
	for (yy = y0; yy <= y1; yy++) {
		int dy = yy - cy;
		int rem = (int)rr - dy * dy;
		int half, xa, xb;
		if (rem < 0) {
			continue;
		}
		half = (int)isqrt_u32((uint32_t)rem);
		xa = cx - half;
		if (xa < g_clip_x0) {
			xa = g_clip_x0;
		}
		xb = cx + half;
		if (xb > g_clip_x1 - 1) {
			xb = g_clip_x1 - 1;
		}
		if (xb >= xa) {
			span_fill(row_ptr(yy) + xa, xb - xa + 1, mapped);
		}
	}
}

void gfx_draw_circle(int cx, int cy, int r, uint32_t color)
{
	uint32_t mapped;
	int x, y, err;

	if (!g_ready || r < 0) {
		return;
	}
	if (r > GFX_MAX_RADIUS) {
		r = GFX_MAX_RADIUS;
	}
	if (cx + r < g_clip_x0 || cx - r >= g_clip_x1 ||
	    cy + r < g_clip_y0 || cy - r >= g_clip_y1) {
		return;
	}
	mapped = fb_map_color(color);
	x = r;
	y = 0;
	err = 1 - r;
	while (x >= y) {
		if (point_in_clip(cx + x, cy + y)) {
			put_mapped(cx + x, cy + y, mapped);
		}
		if (point_in_clip(cx + y, cy + x)) {
			put_mapped(cx + y, cy + x, mapped);
		}
		if (point_in_clip(cx - y, cy + x)) {
			put_mapped(cx - y, cy + x, mapped);
		}
		if (point_in_clip(cx - x, cy + y)) {
			put_mapped(cx - x, cy + y, mapped);
		}
		if (point_in_clip(cx - x, cy - y)) {
			put_mapped(cx - x, cy - y, mapped);
		}
		if (point_in_clip(cx - y, cy - x)) {
			put_mapped(cx - y, cy - x, mapped);
		}
		if (point_in_clip(cx + y, cy - x)) {
			put_mapped(cx + y, cy - x, mapped);
		}
		if (point_in_clip(cx + x, cy - y)) {
			put_mapped(cx + x, cy - y, mapped);
		}
		y++;
		if (err < 0) {
			err += 2 * y + 1;
		} else {
			x--;
			err += 2 * (y - x) + 1;
		}
	}
}

/* ======================================================================== */
/* rectangulos redondeados                                                 */
/* ======================================================================== */

/* Desplazamiento horizontal del borde en la fila `ry` de un rectangulo alto
 * `h` con esquinas de radio `r`: 0 en el cuerpo y r-sqrt(r^2-dy^2) en los
 * arcos de las esquinas (arcos de circunferencia reales). */
static int round_inset(int ry, int h, int r)
{
	int dy;
	int rr;

	if (r <= 0) {
		return 0;
	}
	if (ry < r) {
		dy = r - ry;
	} else if (ry >= h - r) {
		dy = r - (h - 1 - ry);
	} else {
		return 0;
	}
	rr = r * r - dy * dy;
	if (rr < 0) {
		rr = 0;
	}
	return r - (int)isqrt_u32((uint32_t)rr);
}

static int clamp_radius(int w, int h, int radius)
{
	int r = radius;

	if (r < 0) {
		r = 0;
	}
	if (r > w / 2) {
		r = w / 2;
	}
	if (r > h / 2) {
		r = h / 2;
	}
	return r;
}

void gfx_fill_round_rect(int x, int y, int w, int h, int radius, uint32_t color)
{
	uint32_t mapped;
	int r, yy, y0, y1;

	if (!g_ready || w <= 0 || h <= 0) {
		return;
	}
	if (x + w <= g_clip_x0 || x >= g_clip_x1 ||
	    y + h <= g_clip_y0 || y >= g_clip_y1) {
		return;
	}
	r = clamp_radius(w, h, radius);
	mapped = fb_map_color(color);
	y0 = (y < g_clip_y0) ? g_clip_y0 : y;
	y1 = (y + h > g_clip_y1) ? g_clip_y1 : y + h;
	for (yy = y0; yy < y1; yy++) {
		int inset = round_inset(yy - y, h, r);
		int sx = x + inset;
		int ex = x + w - inset;
		if (sx < g_clip_x0) {
			sx = g_clip_x0;
		}
		if (ex > g_clip_x1) {
			ex = g_clip_x1;
		}
		if (ex > sx) {
			span_fill(row_ptr(yy) + sx, ex - sx, mapped);
		}
	}
}

void gfx_fill_round_rect_alpha(int x, int y, int w, int h, int radius,
                               uint32_t color, uint8_t alpha)
{
	int r, yy, y0, y1;

	if (!g_ready || w <= 0 || h <= 0 || alpha == 0u) {
		return;
	}
	if (alpha >= 255u) {
		gfx_fill_round_rect(x, y, w, h, radius, color);
		return;
	}
	if (x + w <= g_clip_x0 || x >= g_clip_x1 ||
	    y + h <= g_clip_y0 || y >= g_clip_y1) {
		return;
	}
	r = clamp_radius(w, h, radius);
	y0 = (y < g_clip_y0) ? g_clip_y0 : y;
	y1 = (y + h > g_clip_y1) ? g_clip_y1 : y + h;
	for (yy = y0; yy < y1; yy++) {
		int inset = round_inset(yy - y, h, r);
		int sx = x + inset;
		int ex = x + w - inset;
		if (sx < g_clip_x0) {
			sx = g_clip_x0;
		}
		if (ex > g_clip_x1) {
			ex = g_clip_x1;
		}
		if (ex > sx) {
			blend_span(row_ptr(yy) + sx, ex - sx, color, alpha);
		}
	}
}

/* Contorno de rectangulo redondeado, con alfa opcional (255 = opaco).
 * La usan gfx_draw_round_rect() y gfx_shadow(). */
static void round_rect_outline(int x, int y, int w, int h, int radius,
                               uint32_t color, uint32_t alpha)
{
	uint32_t mapped = 0u;
	int r, yy, y0, y1;

	if (w <= 0 || h <= 0) {
		return;
	}
	if (x + w <= g_clip_x0 || x >= g_clip_x1 ||
	    y + h <= g_clip_y0 || y >= g_clip_y1) {
		return;
	}
	r = clamp_radius(w, h, radius);
	if (alpha >= 255u) {
		mapped = fb_map_color(color);
	}
	y0 = (y < g_clip_y0) ? g_clip_y0 : y;
	y1 = (y + h > g_clip_y1) ? g_clip_y1 : y + h;
	for (yy = y0; yy < y1; yy++) {
		int inset = round_inset(yy - y, h, r);
		int lx = x + inset;
		int rx = x + w - 1 - inset;
		if (yy == y || yy == y + h - 1) {
			/* borde horizontal superior/inferior */
			int sx = (lx < g_clip_x0) ? g_clip_x0 : lx;
			int ex = rx + 1;
			if (ex > g_clip_x1) {
				ex = g_clip_x1;
			}
			if (ex > sx) {
				if (alpha >= 255u) {
					span_fill(row_ptr(yy) + sx, ex - sx, mapped);
				} else {
					blend_span(row_ptr(yy) + sx, ex - sx, color,
					           alpha);
				}
			}
		} else {
			/* bordes laterales (incluye los arcos) */
			if (alpha >= 255u) {
				if (point_in_clip(lx, yy)) {
					put_mapped(lx, yy, mapped);
				}
				if (rx != lx && point_in_clip(rx, yy)) {
					put_mapped(rx, yy, mapped);
				}
			} else {
				if (point_in_clip(lx, yy)) {
					put_alpha_px(lx, yy, color, alpha);
				}
				if (rx != lx && point_in_clip(rx, yy)) {
					put_alpha_px(rx, yy, color, alpha);
				}
			}
		}
	}
}

void gfx_draw_round_rect(int x, int y, int w, int h, int radius, uint32_t color)
{
	if (!g_ready || w <= 0 || h <= 0) {
		return;
	}
	round_rect_outline(x, y, w, h, radius, color, 255u);
}

/* ======================================================================== */
/* degradados, sombras y brillos                                           */
/* ======================================================================== */

void gfx_gradient_v(int x, int y, int w, int h, uint32_t top, uint32_t bottom)
{
	int yy, y0, y1;
	int origin_y = y;
	int total_h = h;

	if (!g_ready || w <= 0 || h <= 0) {
		return;
	}
	if (!rect_clip(&x, &y, &w, &h)) {
		return;
	}
	y0 = y;
	y1 = y + h;
	for (yy = y0; yy < y1; yy++) {
		uint32_t t = 0u;
		uint32_t r, g, b, c;
		if (total_h > 1) {
			int pos = yy - origin_y;      /* fila dentro del degradado */
			t = (uint32_t)((pos * 255) / (total_h - 1));
		}
		r = div255(((top >> 16) & 0xFFu) * (255u - t) +
		           ((bottom >> 16) & 0xFFu) * t);
		g = div255(((top >> 8) & 0xFFu) * (255u - t) +
		           ((bottom >> 8) & 0xFFu) * t);
		b = div255((top & 0xFFu) * (255u - t) + (bottom & 0xFFu) * t);
		c = (r << 16) | (g << 8) | b;
		span_fill(row_ptr(yy) + x, w, fb_map_color(c));
	}
}

void gfx_shadow(int x, int y, int w, int h, int radius, uint8_t strength)
{
	const int blur = 8;
	uint32_t layer_alpha;
	int i;

	if (!g_ready || w <= 0 || h <= 0 || strength == 0u) {
		return;
	}
	layer_alpha = (uint32_t)strength / (uint32_t)(blur + 1);
	if (layer_alpha == 0u) {
		layer_alpha = 1u;
	}
	/* Capas de contorno hacia fuera: el interior queda tapado por la
	 * ventana opaca, asi que solo hace falta dibujar el borde difuso. */
	for (i = blur - 1; i >= 0; i--) {
		round_rect_outline(x - i, y + 3 - i, w + 2 * i, h + 2 * i,
		                   radius + i, 0x00000000u, layer_alpha);
	}
}

void gfx_radial_glow(int cx, int cy, int radius, uint32_t color,
                     uint8_t strength)
{
	int y0, y1, yy;
	int r2;

	if (!g_ready || radius <= 0 || strength == 0u) {
		return;
	}
	if (radius > GFX_MAX_RADIUS) {
		radius = GFX_MAX_RADIUS;
	}
	if (cx + radius < g_clip_x0 || cx - radius >= g_clip_x1 ||
	    cy + radius < g_clip_y0 || cy - radius >= g_clip_y1) {
		return;
	}
	r2 = radius * radius;
	y0 = cy - radius;
	if (y0 < g_clip_y0) {
		y0 = g_clip_y0;
	}
	y1 = cy + radius;
	if (y1 > g_clip_y1 - 1) {
		y1 = g_clip_y1 - 1;
	}
	for (yy = y0; yy <= y1; yy++) {
		int dy = yy - cy;
		int rem = r2 - dy * dy;
		int half, xa, xb, xx;
		uint32_t *row;
		if (rem <= 0) {
			continue;
		}
		half = (int)isqrt_u32((uint32_t)rem);
		xa = cx - half;
		if (xa < g_clip_x0) {
			xa = g_clip_x0;
		}
		xb = cx + half;
		if (xb > g_clip_x1 - 1) {
			xb = g_clip_x1 - 1;
		}
		if (xb < xa) {
			continue;
		}
		row = row_ptr(yy);
		for (xx = xa; xx <= xb; xx++) {
			int dx = xx - cx;
			int d2 = dx * dx + dy * dy;
			uint32_t a = ((uint32_t)strength * (uint32_t)(r2 - d2)) /
			             (uint32_t)r2;
			if (a == 0u) {
				continue;
			}
			if (a > 255u) {
				a = 255u;
			}
			row[xx] = blend_mapped(row[xx], color, a);
		}
	}
}

/* ======================================================================== */
/* texto                                                                   */
/* ======================================================================== */

/* Dibuja un glifo ya resuelto con un color ya convertido. */
static void draw_glyph_mapped(int x, int y, const uint8_t *glyph,
                              uint32_t mapped, int scale)
{
	int py, y0, y1;
	int cw = FONT_GLYPH_W * scale;
	int ch = FONT_GLYPH_H * scale;

	if (x + cw <= g_clip_x0 || x >= g_clip_x1) {
		return;
	}
	y0 = (y < g_clip_y0) ? g_clip_y0 : y;
	y1 = (y + ch > g_clip_y1) ? g_clip_y1 : y + ch;
	for (py = y0; py < y1; py++) {
		int gy = (py - y) / scale;
		uint8_t bits = glyph[gy];
		uint32_t *row = row_ptr(py);
		int gx;
		if (bits == 0u) {
			continue;
		}
		for (gx = 0; gx < FONT_GLYPH_W; gx++) {
			int sx, sx0, sx1;
			if ((bits & (uint8_t)(0x80u >> gx)) == 0u) {
				continue;
			}
			sx = x + gx * scale;
			sx0 = (sx < g_clip_x0) ? g_clip_x0 : sx;
			sx1 = sx + scale;
			if (sx1 > g_clip_x1) {
				sx1 = g_clip_x1;
			}
			if (sx1 > sx0) {
				span_fill(row + sx0, sx1 - sx0, mapped);
			}
		}
	}
}

/* Variante alfa: color canonico, mezcla por pixel/tramo. */
static void draw_glyph_alpha(int x, int y, const uint8_t *glyph,
                             uint32_t color, uint32_t alpha, int scale)
{
	int py, y0, y1;
	int cw = FONT_GLYPH_W * scale;
	int ch = FONT_GLYPH_H * scale;

	if (x + cw <= g_clip_x0 || x >= g_clip_x1) {
		return;
	}
	y0 = (y < g_clip_y0) ? g_clip_y0 : y;
	y1 = (y + ch > g_clip_y1) ? g_clip_y1 : y + ch;
	for (py = y0; py < y1; py++) {
		int gy = (py - y) / scale;
		uint8_t bits = glyph[gy];
		uint32_t *row = row_ptr(py);
		int gx;
		if (bits == 0u) {
			continue;
		}
		for (gx = 0; gx < FONT_GLYPH_W; gx++) {
			int sx, sx0, sx1;
			if ((bits & (uint8_t)(0x80u >> gx)) == 0u) {
				continue;
			}
			sx = x + gx * scale;
			sx0 = (sx < g_clip_x0) ? g_clip_x0 : sx;
			sx1 = sx + scale;
			if (sx1 > g_clip_x1) {
				sx1 = g_clip_x1;
			}
			if (sx1 > sx0) {
				blend_span(row + sx0, sx1 - sx0, color, alpha);
			}
		}
	}
}

void gfx_draw_char(int x, int y, char c, uint32_t color, int scale)
{
	if (!g_ready) {
		return;
	}
	if (scale < 1) {
		scale = 1;
	}
	draw_glyph_mapped(x, y, font_glyph(c), fb_map_color(color), scale);
}

void gfx_draw_text(int x, int y, const char *s, uint32_t color, int scale)
{
	uint32_t mapped;
	int cw, ch, cx, cy;

	if (!g_ready || s == 0) {
		return;
	}
	if (scale < 1) {
		scale = 1;
	}
	cw = FONT_GLYPH_W * scale;
	ch = FONT_GLYPH_H * scale;
	mapped = fb_map_color(color);
	cx = x;
	cy = y;
	while (*s != '\0') {
		char c = *s;
		if (c == '\n') {
			cx = x;
			cy += ch;
			s++;
			continue;
		}
		if (c == '\r') {
			s++;
			continue;
		}
		if (c == '\t') {
			cx += cw * 4;
			s++;
			continue;
		}
		if (cy >= g_clip_y1) {
			break;
		}
		draw_glyph_mapped(cx, cy, font_glyph(c), mapped, scale);
		cx += cw;
		s++;
	}
}

void gfx_draw_text_alpha(int x, int y, const char *s, uint32_t color,
                         int scale, uint8_t alpha)
{
	int cw, ch, cx, cy;

	if (!g_ready || s == 0 || alpha == 0u) {
		return;
	}
	if (alpha >= 255u) {
		gfx_draw_text(x, y, s, color, scale);
		return;
	}
	if (scale < 1) {
		scale = 1;
	}
	cw = FONT_GLYPH_W * scale;
	ch = FONT_GLYPH_H * scale;
	cx = x;
	cy = y;
	while (*s != '\0') {
		char c = *s;
		if (c == '\n') {
			cx = x;
			cy += ch;
			s++;
			continue;
		}
		if (c == '\r') {
			s++;
			continue;
		}
		if (c == '\t') {
			cx += cw * 4;
			s++;
			continue;
		}
		if (cy >= g_clip_y1) {
			break;
		}
		draw_glyph_alpha(cx, cy, font_glyph(c), color, alpha, scale);
		cx += cw;
		s++;
	}
}

int gfx_text_width(const char *s, int scale)
{
	int width = 0;
	int i = 0;

	if (s == 0) {
		return 0;
	}
	if (scale < 1) {
		scale = 1;
	}
	while (s[i] != '\0' && s[i] != '\n') {
		width += (s[i] == '\t') ? (4 * FONT_GLYPH_W) : FONT_GLYPH_W;
		i++;
	}
	return width * scale;
}

int gfx_text_height(int scale)
{
	if (scale < 1) {
		scale = 1;
	}
	return FONT_GLYPH_H * scale;
}

/* ======================================================================== */
/* imagenes                                                                */
/* ======================================================================== */

void gfx_draw_bitmap8(int x, int y, const uint8_t *bits, int w, int h,
                      uint32_t color)
{
	uint32_t mapped;
	int stride, y0, y1, x0, x1, yy, xx;

	if (!g_ready || bits == 0 || w <= 0 || h <= 0) {
		return;
	}
	if (x + w <= g_clip_x0 || x >= g_clip_x1 ||
	    y + h <= g_clip_y0 || y >= g_clip_y1) {
		return;
	}
	mapped = fb_map_color(color);
	stride = (w + 7) >> 3;
	x0 = (x < g_clip_x0) ? g_clip_x0 : x;
	x1 = (x + w > g_clip_x1) ? g_clip_x1 : x + w;
	y0 = (y < g_clip_y0) ? g_clip_y0 : y;
	y1 = (y + h > g_clip_y1) ? g_clip_y1 : y + h;
	for (yy = y0; yy < y1; yy++) {
		const uint8_t *src = bits + (size_t)(yy - y) * (size_t)stride;
		uint32_t *row = row_ptr(yy);
		for (xx = x0; xx < x1; xx++) {
			int bx = xx - x;
			if ((src[bx >> 3] & (uint8_t)(0x80u >> (bx & 7))) != 0u) {
				row[xx] = mapped;
			}
		}
	}
}

/* RGB565 -> 0x00RRGGBB */
static inline uint32_t rgb565_to_rgb888(uint16_t p)
{
	uint32_t r = (uint32_t)(p >> 11) & 0x1Fu;
	uint32_t g = (uint32_t)(p >> 5) & 0x3Fu;
	uint32_t b = (uint32_t)p & 0x1Fu;

	r = (r << 3) | (r >> 2);
	g = (g << 2) | (g >> 4);
	b = (b << 3) | (b >> 2);
	return (r << 16) | (g << 8) | b;
}

void gfx_draw_sprite(int x, int y, const uint16_t *pixels, int w, int h)
{
	int y0, y1, x0, x1, yy, xx;

	if (!g_ready || pixels == 0 || w <= 0 || h <= 0) {
		return;
	}
	if (x + w <= g_clip_x0 || x >= g_clip_x1 ||
	    y + h <= g_clip_y0 || y >= g_clip_y1) {
		return;
	}
	x0 = (x < g_clip_x0) ? g_clip_x0 : x;
	x1 = (x + w > g_clip_x1) ? g_clip_x1 : x + w;
	y0 = (y < g_clip_y0) ? g_clip_y0 : y;
	y1 = (y + h > g_clip_y1) ? g_clip_y1 : y + h;

	for (yy = y0; yy < y1; yy++) {
		const uint16_t *src = pixels + (size_t)(yy - y) * (size_t)w;
		uint32_t *row = row_ptr(yy);
		if (g_fast) {
			for (xx = x0; xx < x1; xx++) {
				uint16_t p = src[xx - x];
				if (p != GFX_TRANSPARENT) {
					row[xx] = rgb565_to_rgb888(p);
				}
			}
		} else {
			for (xx = x0; xx < x1; xx++) {
				uint16_t p = src[xx - x];
				if (p != GFX_TRANSPARENT) {
					row[xx] = fb_map_color(rgb565_to_rgb888(p));
				}
			}
		}
	}
}

void gfx_draw_sprite_alpha(int x, int y, const uint16_t *pixels, int w, int h,
                           uint8_t alpha)
{
	int y0, y1, x0, x1, yy, xx;

	if (!g_ready || pixels == 0 || w <= 0 || h <= 0 || alpha == 0u) {
		return;
	}
	if (alpha >= 255u) {
		gfx_draw_sprite(x, y, pixels, w, h);
		return;
	}
	if (x + w <= g_clip_x0 || x >= g_clip_x1 ||
	    y + h <= g_clip_y0 || y >= g_clip_y1) {
		return;
	}
	x0 = (x < g_clip_x0) ? g_clip_x0 : x;
	x1 = (x + w > g_clip_x1) ? g_clip_x1 : x + w;
	y0 = (y < g_clip_y0) ? g_clip_y0 : y;
	y1 = (y + h > g_clip_y1) ? g_clip_y1 : y + h;

	for (yy = y0; yy < y1; yy++) {
		const uint16_t *src = pixels + (size_t)(yy - y) * (size_t)w;
		uint32_t *row = row_ptr(yy);
		for (xx = x0; xx < x1; xx++) {
			uint16_t p = src[xx - x];
			if (p != GFX_TRANSPARENT) {
				row[xx] = blend_mapped(row[xx],
				                       rgb565_to_rgb888(p), alpha);
			}
		}
	}
}

void gfx_blit_rgb(int x, int y, int w, int h, const uint32_t *pixels)
{
	int y0, y1, x0, x1, yy, xx;

	if (!g_ready || pixels == 0 || w <= 0 || h <= 0) {
		return;
	}
	if (x + w <= g_clip_x0 || x >= g_clip_x1 ||
	    y + h <= g_clip_y0 || y >= g_clip_y1) {
		return;
	}
	x0 = (x < g_clip_x0) ? g_clip_x0 : x;
	x1 = (x + w > g_clip_x1) ? g_clip_x1 : x + w;
	y0 = (y < g_clip_y0) ? g_clip_y0 : y;
	y1 = (y + h > g_clip_y1) ? g_clip_y1 : y + h;

	for (yy = y0; yy < y1; yy++) {
		const uint32_t *src = pixels + (size_t)(yy - y) * (size_t)w;
		uint32_t *row = row_ptr(yy) + x0;
		int count = x1 - x0;
		if (g_fast) {
			copy_words(row, src + (x0 - x), count);
		} else {
			for (xx = 0; xx < count; xx++) {
				row[xx] = fb_map_color(src[(x0 - x) + xx]);
			}
		}
	}
}

/* ======================================================================== */
/* composicion / presentacion                                              */
/* ======================================================================== */

void gfx_mark_dirty(int x, int y, int w, int h)
{
	fb_mark_dirty(x, y, w, h);
}

void gfx_mark_all_dirty(void)
{
	fb_mark_all_dirty();
}

void gfx_present(void)
{
	fb_present();
}

void gfx_present_dirty(void)
{
	fb_present_dirty();
}
