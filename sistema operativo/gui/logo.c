/* gui/logo.c - componente reutilizable del logotipo OFICIAL de SereOS
 *
 * Compone el glifo oficial (S blanca extraida de assets/logo/
 * official_logo.png -> mascaras alfa 8bpp en gui/logo_data.c) sobre un
 * contenedor de marca: circulo, squircle (superelipse n=4), cuadrado
 * redondeado o el sprite oficial completo (compatibilidad).
 *
 * ANTIALIASING: los contenedores y el anillo del splash se rasterizan con
 * cobertura 4x4 muestras (16 sub-muestras por pixel) SOLO en los pixeles de
 * borde; el interior se rellena por filas con gfx_fill_rect.  La cobertura se
 * mezcla con gfx_blend_pixel() y alfa = (cov*255+8)/16, sin coma flotante.
 * La caja del contenedor sigue siendo EXACTAMENTE size x size y la cobertura
 * no se sale de ella; todo es determinista y respeta el clip del motor.
 *
 * Igual que antes: sin malloc, sin estado y sin primitivas bloqueantes, de
 * modo que la funcion es segura en el bucle de dibujo e incluso en la
 * pantalla de panico (ISR con interrupciones desactivadas).
 *
 * El glifo se dibuja SIEMPRE centrado en (cx,cy), con su proporcion oficial
 * (354/376) y sin recortes: la mascara se elige por altura de la tabla
 * generada y se compone tal cual con gfx_blit_alpha8(), nunca se escala en
 * tiempo de ejecucion.
 */
#include <stdint.h>

#include "logo.h"
#include "logo_data.h"
#include "logo_ribbon_data.h"
#include "graphics.h"
#include "theme.h"

/* separacion entre el borde del contenedor y el anillo exterior (1 px) */
#ifndef LOGO_RING_GAP
#define LOGO_RING_GAP 4
#endif

/* cota defensiva: evita desbordar las cuentas con tamanos absurdos */
#define LOGO_MAX_SIZE 4096

/* ------------------------------------------------------------------ */
/* utilidades matematicas enteras                                      */
/* ------------------------------------------------------------------ */
static uint32_t isqrt_u32(uint32_t v)
{
	uint32_t x, y;

	if (v < 2u)
		return v;
	x = v;
	y = (x + 1u) / 2u;
	while (y < x) {
		x = y;
		y = (x + v / x) / 2u;
	}
	return x;
}

static uint64_t pow4_u64(uint64_t x)
{
	uint64_t x2 = x * x;
	return x2 * x2;
}

static int64_t pow4_i64(int64_t x)
{
	int64_t x2 = x * x;
	return x2 * x2;
}

/* raiz cuarta entera por busqueda binaria (tamanos de hasta 65535 px) */
static uint32_t iroot4_u64(uint64_t v)
{
	uint32_t lo = 0u, hi = 65535u;

	while (lo < hi) {
		uint32_t mid = lo + (hi - lo + 1u) / 2u;
		if (pow4_u64((uint64_t)mid) <= v)
			lo = mid;
		else
			hi = mid - 1u;
	}
	return lo;
}

/* ------------------------------------------------------------------ */
/* geometria exacta por filas (misma que la version sin AA)            */
/* ------------------------------------------------------------------ */
/* primer pixel (indice local u) cuyo centro cae dentro de la forma en la
 * fila v; devuelve -1 si la fila no toca la forma */
static int span_lo(int shape, int size, int radius, int v)
{
	int dy, k;

	if (shape == LOGO_SHAPE_ROUNDED) {
		if (radius <= 0)
			return 0;
		if (v < radius)
			dy = 2 * radius - 2 * v - 1;
		else if (v >= size - radius)
			dy = 2 * radius - 2 * (size - 1 - v) - 1;
		else
			return 0;
		k = (int)isqrt_u32((uint32_t)(4 * radius * radius - dy * dy));
		return (2 * radius - 1 - k + 1) / 2;   /* ceil((2r-1-k)/2) */
	}

	dy = 2 * v + 1 - size;
	if (shape == LOGO_SHAPE_SQUIRCLE) {
		uint64_t s4 = pow4_u64((uint64_t)size);
		uint64_t dv = (dy < 0) ? (uint64_t)(-dy) : (uint64_t)dy;
		uint32_t k4 = iroot4_u64(s4 - pow4_u64(dv));

		return (size - (int)k4) / 2;
	}

	k = (int)isqrt_u32((uint32_t)(size * size - dy * dy));
	return (size - k) / 2;
}

/* ------------------------------------------------------------------ */
/* cobertura 4x4 (16 sub-muestras por pixel)                           */
/* ------------------------------------------------------------------ */
/* una sub-muestra esta dentro de la forma? (x8,y8 en octavos, relativos al
 * borde superior izquierdo del contenedor, 0..8*size) */
static int sample_inside(int shape, int size, int radius, int x8, int y8)
{
	int64_t dx, dy;

	if (shape == LOGO_SHAPE_ROUNDED) {
		int64_t s8 = 8 * (int64_t)size;
		int64_t r8 = 8 * (int64_t)radius;
		int64_t lx = (x8 < s8 - x8) ? x8 : s8 - x8;
		int64_t ly = (y8 < s8 - y8) ? y8 : s8 - y8;
		int64_t ax, ay;

		if (lx >= r8 || ly >= r8)
			return 1;
		ax = r8 - lx;
		ay = r8 - ly;
		return ax * ax + ay * ay <= r8 * r8;
	}

	dx = (int64_t)x8 - 4 * (int64_t)size;
	dy = (int64_t)y8 - 4 * (int64_t)size;
	if (shape == LOGO_SHAPE_SQUIRCLE)
		return pow4_i64(dx) + pow4_i64(dy) <=
		       pow4_i64(4 * (int64_t)size);

	return dx * dx + dy * dy <= 16 * (int64_t)size * size;
}

static int sample_coverage(int shape, int size, int radius, int u, int v)
{
	int cov = 0, j, k;

	for (j = 0; j < 4; j++) {
		int y8 = 8 * v + 2 * j + 1;

		for (k = 0; k < 4; k++) {
			int x8 = 8 * u + 2 * k + 1;

			cov += sample_inside(shape, size, radius, x8, y8);
		}
	}
	return cov;
}

static void blend_cov(int x, int y, int cov, uint32_t color)
{
	uint32_t a;

	if (cov <= 0)
		return;
	a = ((uint32_t)cov * 255u + 8u) / 16u;
	gfx_blend_pixel(x, y, color, (uint8_t)a);
}

/* la forma es simetrica respecto del eje vertical: el pixel espejo comparte
 * cobertura.  El pixel central (tamano impar) se pinta una sola vez. */
static void blend_cov_mirror(int x0, int y, int size, int u, int cov,
                             uint32_t color)
{
	blend_cov(x0 + u, y, cov, color);
	if (u != size - 1 - u)
		blend_cov(x0 + size - 1 - u, y, cov, color);
}

/* contenedor con AA: interior por filas (gfx_fill_rect) y borde con cobertura */
static void fill_shape_aa(int cx, int cy, int size, int shape, int radius,
                          uint32_t color)
{
	int x0 = cx - size / 2;
	int y0 = cy - size / 2;
	int half = (size + 1) / 2;
	int v;

	if (shape == LOGO_SHAPE_ROUNDED) {
		if (radius < 0)
			radius = 0;
		if (radius > size / 2)
			radius = size / 2;
	}

	for (v = 0; v < size; v++) {
		int lo = span_lo(shape, size, radius, v);
		int full = -1;
		int u;

		if (lo < 0 || lo >= half)
			continue;

		/* borde izquierdo por fuera del tramo de centros interiores
		 * (filas polares: aqui pueden aparecer varias muestras) */
		for (u = lo - 1; u >= 0; u--) {
			int cov = sample_coverage(shape, size, radius, u, v);

			if (cov == 0)
				break;
			blend_cov_mirror(x0, y0 + v, size, u, cov, color);
		}

		/* hasta el primer pixel totalmente cubierto */
		for (u = lo; u < half; u++) {
			int cov = sample_coverage(shape, size, radius, u, v);

			if (cov >= 16) {
				full = u;
				break;
			}
			blend_cov_mirror(x0, y0 + v, size, u, cov, color);
		}
		if (full < 0)
			continue;   /* fila polar: todo su contenido es borde */

		gfx_fill_rect(x0 + full, y0 + v, size - 2 * full, 1, color);
	}
}

/* anillo exterior AA de 1 px: banda radial [R-0.5, R+0.5] muestreada 4x4.
 * Se muestrea alrededor del centro del pixel-bbox (cx+0.5, cy+0.5) para que
 * el bbox quede EXACTAMENTE en 2*R+1 px, igual que logo_extent(). */
static void draw_ring_aa(int cx, int cy, int size, uint8_t ring_alpha)
{
	int r = size / 2 + LOGO_RING_GAP;
	int64_t r_in = 8 * (int64_t)r - 4;
	int64_t r_out = 8 * (int64_t)r + 4;
	int64_t r_in2 = r_in * r_in;
	int64_t r_out2 = r_out * r_out;
	int d2_low = (r - 1) * (r - 1);
	int d2_high = (r + 2) * (r + 2);
	int du, dv;

	if (ring_alpha == 0 || r <= 0)
		return;

	for (dv = -r; dv <= r; dv++) {
		for (du = -r; du <= r; du++) {
			int d2c = du * du + dv * dv;
			int cov = 0, j, k;

			if (d2c < d2_low || d2c > d2_high)
				continue;
			for (j = 0; j < 4; j++) {
				int64_t y8 = 8 * (int64_t)dv + 2 * j - 3;

				for (k = 0; k < 4; k++) {
					int64_t x8 = 8 * (int64_t)du + 2 * k - 3;
					int64_t d2 = x8 * x8 + y8 * y8;

					if (d2 >= r_in2 && d2 <= r_out2)
						cov++;
				}
			}
			if (cov > 0) {
				uint32_t a = ((uint32_t)cov * ring_alpha + 8u) / 16u;

				gfx_blend_pixel(cx + du, cy + dv, theme.accent,
				                (uint8_t)a);
			}
		}
	}
}

/* ------------------------------------------------------------------ */
/* glifo oficial                                                       */
/* ------------------------------------------------------------------ */
static int ribbon_height_for(int size)
{
	int gh = (size * LOGO_GLYPH_RATIO_PCT + 50) / 100;

	if (gh < LOGO_RIBBON_MIN_HEIGHT)
		gh = LOGO_RIBBON_MIN_HEIGHT;
	if (gh > LOGO_RIBBON_MAX_HEIGHT)
		gh = LOGO_RIBBON_MAX_HEIGHT;
	return gh;
}

/* altura ribbon exacta si existe; si no, la mas cercana (empate -> la menor) */
static int ribbon_index(int gh)
{
	int i, best = -1;
	int best_d = 0x7FFFFFFF;

	for (i = 0; i < (int)LOGO_RIBBON_COUNT; i++) {
		int d = (int)logo_ribbon_heights[i] - gh;

		if (d < 0)
			d = -d;
		if (d < best_d) {
			best_d = d;
			best = i;
		}
	}
	return best;
}

static int glyph_height_for(int size)
{
	int gh = (size * LOGO_GLYPH_RATIO_PCT + 50) / 100;

	if (gh < LOGO_GLYPH_MIN_HEIGHT)
		gh = LOGO_GLYPH_MIN_HEIGHT;
	if (gh > LOGO_GLYPH_MAX_HEIGHT)
		gh = LOGO_GLYPH_MAX_HEIGHT;
	return gh;
}

/* altura exacta si existe; si no, la mas cercana (empate -> la menor) */
static int glyph_index(int gh)
{
	int i, best = -1;
	int best_d = 0x7FFFFFFF;

	for (i = 0; i < (int)LOGO_GLYPH_COUNT; i++) {
		int d = (int)logo_glyph_heights[i] - gh;

		if (d < 0)
			d = -d;
		if (d < best_d) {
			best_d = d;
			best = i;
		}
	}
	return best;
}

/* dibuja el glifo elegido, centrado por su bbox y sin escalar en runtime */
static void draw_glyph(int cx, int cy, int size, logo_glyph_t glyph)
{
	if (glyph == LOGO_GLYPH_RIBBON) {
		const logo_ribbon_glyph_t *g;
		int idx = ribbon_index(ribbon_height_for(size));

		if (idx < 0)
			return;
		g = &logo_ribbon_glyphs[idx];
		if (!g->mask || g->w == 0 || g->h == 0)
			return;
		gfx_blit_alpha8(cx - (int)g->w / 2, cy - (int)g->h / 2,
		                (int)g->w, (int)g->h, g->mask, LOGO_BRAND_WHITE);
		return;
	}

	{
		const logo_official_glyph_t *g;
		int idx = glyph_index(glyph_height_for(size));

		if (idx < 0)
			return;
		g = &logo_glyphs[idx];
		if (!g->mask || g->w == 0 || g->h == 0)
			return;
		gfx_blit_alpha8(cx - (int)g->w / 2, cy - (int)g->h / 2,
		                (int)g->w, (int)g->h, g->mask, LOGO_BRAND_WHITE);
	}
}

/* ------------------------------------------------------------------ */
/* glifo suelto (sin contenedor): icono PNG de la top bar              */
/* ------------------------------------------------------------------ */
/* indice de la mascara de altura exacta o la mas cercana (empate: menor) */
static int icon_index(logo_glyph_t glyph, int height)
{
	const uint16_t *heights;
	int count, i, best = -1;
	int best_d = 0x7FFFFFFF;

	if (height <= 0)
		return -1;
	if (glyph == LOGO_GLYPH_RIBBON) {
		heights = logo_ribbon_heights;
		count = (int)LOGO_RIBBON_COUNT;
	} else {
		heights = logo_glyph_heights;
		count = (int)LOGO_GLYPH_COUNT;
	}
	for (i = 0; i < count; i++) {
		int d = (int)heights[i] - height;

		if (d < 0)
			d = -d;
		if (d < best_d) {
			best_d = d;
			best = i;
		}
	}
	return best;
}

void logo_draw_icon(int cx, int cy, int height, logo_glyph_t glyph)
{
	int idx = icon_index(glyph, height);

	if (idx < 0)
		return;

	if (glyph == LOGO_GLYPH_RIBBON) {
		const logo_ribbon_glyph_t *g = &logo_ribbon_glyphs[idx];

		if (!g->mask || g->w == 0 || g->h == 0)
			return;
		gfx_blit_alpha8(cx - (int)g->w / 2, cy - (int)g->h / 2,
		                (int)g->w, (int)g->h, g->mask, LOGO_BRAND_WHITE);
		return;
	}

	{
		const logo_official_glyph_t *g = &logo_glyphs[idx];

		if (!g->mask || g->w == 0 || g->h == 0)
			return;
		gfx_blit_alpha8(cx - (int)g->w / 2, cy - (int)g->h / 2,
		                (int)g->w, (int)g->h, g->mask, LOGO_BRAND_WHITE);
	}
}

int logo_icon_width(int height, logo_glyph_t glyph)
{
	int idx = icon_index(glyph, height);

	if (idx < 0)
		return 0;
	if (glyph == LOGO_GLYPH_RIBBON)
		return (int)logo_ribbon_glyphs[idx].w;
	return (int)logo_glyphs[idx].w;
}

/* ------------------------------------------------------------------ */
/* sprite oficial completo (LOGO_SHAPE_PLAIN, compatibilidad)          */
/* ------------------------------------------------------------------ */
/* altura exacta si existe; si no, la inmediatamente mayor; si no, la mayor */
static int logo_index(int size)
{
	int i;

	if (size <= 0)
		return -1;
	for (i = 0; i < (int)LOGO_SIZE_COUNT; i++)
		if ((int)logo_heights[i] == size)
			return i;
	for (i = 0; i < (int)LOGO_SIZE_COUNT; i++)
		if ((int)logo_heights[i] > size)
			return i;
	return (int)LOGO_SIZE_COUNT - 1;
}

static void draw_plain(int cx, int cy, int size)
{
	const logo_bitmap_t *bm;
	int idx = logo_index(size);

	if (idx < 0)
		return;
	bm = &logo_bitmaps[idx];
	if (!bm->px || bm->w == 0 || bm->h == 0)
		return;
	gfx_draw_sprite(cx - (int)bm->w / 2, cy - (int)bm->h / 2,
	                bm->px, (int)bm->w, (int)bm->h);
}

/* ------------------------------------------------------------------ */
/* API publica                                                         */
/* ------------------------------------------------------------------ */
static void logo_draw_impl(int cx, int cy, int size, logo_shape_t shape,
                           int radius_pct, uint8_t ring_alpha,
                           logo_glyph_t glyph)
{
	int radius = 0;

	if (size <= 0)
		return;
	if (size > LOGO_MAX_SIZE)
		size = LOGO_MAX_SIZE;

	if (shape == LOGO_SHAPE_PLAIN) {
		draw_plain(cx, cy, size);
		return;
	}

	if (shape == LOGO_SHAPE_ROUNDED) {
		int pct = (radius_pct > 0) ? radius_pct : 22;

		radius = (size * pct + 50) / 100;
	}

	fill_shape_aa(cx, cy, size, (int)shape, radius, LOGO_BRAND_BLUE);

	if (ring_alpha > 0)
		draw_ring_aa(cx, cy, size, ring_alpha);

	draw_glyph(cx, cy, size, glyph);
}

void logo_draw(int cx, int cy, int size, logo_shape_t shape, int radius_pct,
               uint8_t ring_alpha)
{
	logo_draw_impl(cx, cy, size, shape, radius_pct, ring_alpha,
	               LOGO_GLYPH_OFFICIAL);
}

void logo_draw_glyph(int cx, int cy, int size, logo_shape_t shape,
                     int radius_pct, uint8_t ring_alpha, logo_glyph_t glyph)
{
	logo_draw_impl(cx, cy, size, shape, radius_pct, ring_alpha, glyph);
}

void logo_draw_topbar(int cx, int cy, int size)
{
	/* unica ubicacion con el asset ribbon: SOLO el glifo del PNG, sin
	 * contenedor, sin anillo y sin fondo azul. `size` es la ALTURA del
	 * glifo (peticion del usuario), no el lado de un contenedor. */
	logo_draw_icon(cx, cy, size, LOGO_GLYPH_RIBBON);
}

void logo_draw_brand(int cx, int cy, int size)
{
	/* marca oficial en circulo (menu y pantalla de panico) */
	logo_draw_impl(cx, cy, size, LOGO_SHAPE_CIRCLE, 0, 0,
	               LOGO_GLYPH_OFFICIAL);
}

void logo_draw_splash(int cx, int cy, int size)
{
	/* circulo con anillo exterior AA de 1 px, discreto pero continuo:
	 * mezcla accent sobre el fondo con opacidad global 110/255 */
	logo_draw_impl(cx, cy, size, LOGO_SHAPE_CIRCLE, 0, 110,
	               LOGO_GLYPH_OFFICIAL);
}

void logo_draw_about(int cx, int cy, int size)
{
	logo_draw_impl(cx, cy, size, LOGO_SHAPE_ROUNDED, 22, 0,
	               LOGO_GLYPH_OFFICIAL);
}

void logo_draw_app_icon(int cx, int cy, int size)
{
	logo_draw_impl(cx, cy, size, LOGO_SHAPE_SQUIRCLE, 0, 0,
	               LOGO_GLYPH_OFFICIAL);
}

int logo_extent(int size, uint8_t ring_alpha)
{
	int r;

	if (size <= 0)
		return 0;
	if (ring_alpha == 0)
		return size;
	r = size / 2 + LOGO_RING_GAP;
	return 2 * r + 1;   /* diametro del anillo exterior (bbox exacta) */
}

/* ------------------------------------------------------------------ */
/* compatibilidad con la API anterior                                  */
/* ------------------------------------------------------------------ */
void icons_draw_logo(int x, int y, int size)
{
	logo_draw(x, y, size, LOGO_SHAPE_PLAIN, 0, 0);
}

int icons_logo_width(int size)
{
	int idx = logo_index(size);

	if (idx < 0)
		return 0;
	return (int)logo_bitmaps[idx].w;
}
