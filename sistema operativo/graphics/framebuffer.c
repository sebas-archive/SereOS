/* graphics/framebuffer.c - framebuffer lineal entregado por GRUB (Multiboot 1)
 *
 * SereOS usa el modo grafico lineal que GRUB negocia a partir de la peticion
 * de video de boot/boot.s (1024x768x32) y que queda descrito en la estructura
 * multiboot_info.  Este archivo:
 *
 *   - parsea y valida esa estructura (por direccion, sin copiarla),
 *   - expone un backbuffer estatico uint32_t[FB_MAX_PIXELS],
 *   - permite dibujar directamente sobre la VRAM antes de inicializar el
 *     motor grafico (patron de prueba / diagnostico temprano),
 *   - convierte colores 0x00RRGGBB a la mascara real del hardware,
 *   - copia a la VRAM solo las regiones sucias (hasta 32 rectangulos).
 *
 * Formato interno del backbuffer: cada uint32_t contiene el pixel YA
 * convertido al formato del hardware (el mismo valor que se escribe en VRAM).
 * En el modo tipico 1024x768x32 BGRX de GRUB eso coincide con 0x00RRGGBB,
 * por lo que "presentar" es una copia directa de palabras de 32 bits.  Para
 * 24bpp los 24 bits bajos contienen el pixel convertido.
 *
 * Nada de libc del host: solo <stdint.h>/<stddef.h> y bucles propios.
 */
#include <stdint.h>
#include <stddef.h>
#include "framebuffer.h"

/* --- offsets de multiboot_info (Multiboot 1, especificacion) ------------ */
#define MB_INFO_FLAGS        0u     /* bit 12 = informacion de framebuffer */
#define MB_FLAG_FRAMEBUFFER  0x00001000u
#define MB_FB_ADDR_OFFSET    88u    /* u64: direccion fisica del framebuffer */
#define MB_FB_PITCH_OFFSET   96u    /* u32: bytes por linea */
#define MB_FB_WIDTH_OFFSET   100u   /* u32: ancho en pixeles */
#define MB_FB_HEIGHT_OFFSET  104u   /* u32: alto en pixeles */
#define MB_FB_BPP_OFFSET     108u   /* u8 : bits por pixel */
#define MB_FB_TYPE_OFFSET    109u   /* u8 : 1 = RGB */
#define MB_FB_RED_POS        110u   /* u8 : posicion del rojo */
#define MB_FB_RED_SIZE       111u   /* u8 : bits de rojo */
#define MB_FB_GREEN_POS      112u
#define MB_FB_GREEN_SIZE     113u
#define MB_FB_BLUE_POS       114u
#define MB_FB_BLUE_SIZE      115u

/* Vista empaquetada de la parte final de multiboot_info.  El resto de la
 * estructura (flags .. vbe_interface_len) ocupa los primeros 88 bytes. */
typedef struct {
	uint32_t flags;
	uint8_t  reserved[84];        /* offsets 4..87 */
	uint64_t framebuffer_addr;    /* offset 88 */
	uint32_t framebuffer_pitch;   /* offset 96 */
	uint32_t framebuffer_width;   /* offset 100 */
	uint32_t framebuffer_height;  /* offset 104 */
	uint8_t  framebuffer_bpp;     /* offset 108 */
	uint8_t  framebuffer_type;    /* offset 109 */
	uint8_t  red_pos, red_size;   /* offset 110, 111 */
	uint8_t  green_pos, green_size;
	uint8_t  blue_pos, blue_size; /* offset 114, 115 */
} mb_info_t;

/* Comprobacion en tiempo de compilacion: la vista anterior debe coincidir con
 * los offsets que fija la especificacion Multiboot 1. */
typedef char fb_multiboot_layout_check[
    (offsetof(mb_info_t, framebuffer_addr) == MB_FB_ADDR_OFFSET &&
     offsetof(mb_info_t, framebuffer_pitch) == MB_FB_PITCH_OFFSET &&
     offsetof(mb_info_t, framebuffer_width) == MB_FB_WIDTH_OFFSET &&
     offsetof(mb_info_t, framebuffer_height) == MB_FB_HEIGHT_OFFSET &&
     offsetof(mb_info_t, framebuffer_bpp) == MB_FB_BPP_OFFSET &&
     offsetof(mb_info_t, framebuffer_type) == MB_FB_TYPE_OFFSET &&
     offsetof(mb_info_t, red_pos) == MB_FB_RED_POS &&
     offsetof(mb_info_t, green_pos) == MB_FB_GREEN_POS &&
     offsetof(mb_info_t, blue_pos) == MB_FB_BLUE_POS) ? 1 : -1];

#define FB_DIRTY_MAX 32

typedef struct {
	int x0, y0, x1, y1;           /* limites exclusivos al estilo [x0,x1) */
} fb_rect_t;

/* --- estado interno ----------------------------------------------------- */
static fb_info_t g_info;
static uint32_t g_backbuffer[FB_MAX_PIXELS] __attribute__((aligned(16)));
static int g_backbuffer_ok;              /* 1 si el modo cabe en el backbuffer */
static volatile uint8_t *g_vram;        /* VRAM mapeada identidad */
static int g_fast_layout;               /* mascaras RGB canonicas (BGRX/RGB) */
static fb_rect_t g_dirty[FB_DIRTY_MAX];
static int g_dirty_count;

/* ======================================================================== */
/* utilidades de memoria (sin libc del host)                                */
/* ======================================================================== */

static void zero_words(uint32_t *dst, uint32_t n)
{
	while (n-- > 0u) {
		*dst++ = 0u;
	}
}

/* Convierte un canal de 8 bits al tamano de mascara real (1..8 bits). */
static uint32_t scale_channel(uint32_t c, uint8_t size)
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

/* Exponente inverso: valor de mascara -> canal de 8 bits. */
static uint32_t expand_channel(uint32_t v, uint8_t size)
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

/* ======================================================================== */
/* inicializacion                                                          */
/* ======================================================================== */

/*
 * Valida el modo de video y publica g_info.  Devuelve 1 si hay framebuffer
 * utilizable; 0 si SereOS debe caer al modo VGA de texto.
 */
int fb_init(uint32_t boot_info_addr)
{
	const mb_info_t *mbi;
	uint64_t addr64;
	uint32_t width, height, pitch;
	uint32_t bytes_pp, min_pitch, bytes;
	uint8_t bpp, type;
	uint8_t rp, rs, gp, gs, bp, bs;

	g_info.available = 0;
	g_backbuffer_ok = 0;
	g_fast_layout = 0;
	g_vram = 0;
	g_dirty_count = 0;

	if (boot_info_addr == 0u) {
		return 0;
	}
	mbi = (const mb_info_t *)(uintptr_t)boot_info_addr;

	/* El bootloader solo garantiza estos campos si activo el bit 12. */
	if ((mbi->flags & MB_FLAG_FRAMEBUFFER) == 0u) {
		return 0;
	}

	addr64 = mbi->framebuffer_addr;
	if ((addr64 >> 32) != 0u) {
		return 0;                       /* i686: fuera del espacio fisico */
	}
	if ((uint32_t)addr64 == 0u) {
		return 0;                       /* sin direccion valida */
	}

	type = mbi->framebuffer_type;
	bpp = mbi->framebuffer_bpp;
	width = mbi->framebuffer_width;
	height = mbi->framebuffer_height;
	pitch = mbi->framebuffer_pitch;

	if (type != 1u) {
		return 0;                       /* solo RGB lineal (no indexado) */
	}
	if (bpp != 32u && bpp != 24u) {
		return 0;                       /* 16bpp: sin soporte -> VGA texto */
	}
	if (width == 0u || height == 0u) {
		return 0;
	}
	if (width > FB_MAX_WIDTH || height > FB_MAX_HEIGHT) {
		return 0;                       /* no cabe en el backbuffer estatico */
	}

	bytes_pp = (uint32_t)bpp / 8u;
	min_pitch = width * bytes_pp;
	if (pitch < min_pitch) {
		return 0;                       /* lineas mas cortas que el ancho */
	}
	if (pitch > 16384u) {
		return 0;                       /* pitch absurdo: bootloader raro */
	}

	/* Mascaras de color: si el bootloader no las rellena, se asume el orden
	 * BGRX/RGB tipico de GRUB (rojo 16, verde 8, azul 0, 8 bits). */
	rp = mbi->red_pos;
	rs = mbi->red_size;
	gp = mbi->green_pos;
	gs = mbi->green_size;
	bp = mbi->blue_pos;
	bs = mbi->blue_size;
	if (rs == 0u || rs > 8u || gs == 0u || gs > 8u || bs == 0u || bs > 8u ||
	    (uint32_t)rp + rs > (uint32_t)bpp ||
	    (uint32_t)gp + gs > (uint32_t)bpp ||
	    (uint32_t)bp + bs > (uint32_t)bpp) {
		rp = 16u;
		rs = 8u;
		gp = 8u;
		gs = 8u;
		bp = 0u;
		bs = 8u;
	}

	bytes = pitch * height;
	if (bytes == 0u || bytes > (32u * 1024u * 1024u)) {
		return 0;
	}

	g_info.available = 1;
	g_info.width = width;
	g_info.height = height;
	g_info.pitch = pitch;
	g_info.bpp = bpp;
	g_info.physical = (uint32_t)addr64;
	g_info.red_pos = rp;
	g_info.red_size = rs;
	g_info.green_pos = gp;
	g_info.green_size = gs;
	g_info.blue_pos = bp;
	g_info.blue_size = bs;
	g_info.type = type;
	g_info.bytes = bytes;

	g_vram = (volatile uint8_t *)(uintptr_t)g_info.physical;

	g_fast_layout = (rp == 16u && rs == 8u && gp == 8u && gs == 8u &&
	                 bp == 0u && bs == 8u) ? 1 : 0;

	g_backbuffer_ok = 1;
	zero_words(g_backbuffer, (uint32_t)FB_MAX_PIXELS);

	return 1;
}

/* ======================================================================== */
/* consultas de estado                                                     */
/* ======================================================================== */

int fb_available(void)
{
	return g_info.available ? 1 : 0;
}

const fb_info_t *fb_info(void)
{
	return &g_info;
}

uint32_t fb_width(void)
{
	return g_info.available ? g_info.width : 0u;
}

uint32_t fb_height(void)
{
	return g_info.available ? g_info.height : 0u;
}

uint32_t fb_pitch(void)
{
	return g_info.available ? g_info.pitch : 0u;
}

uint32_t fb_bpp(void)
{
	return g_info.available ? (uint32_t)g_info.bpp : 0u;
}

uint32_t fb_size_bytes(void)
{
	return g_info.available ? g_info.bytes : 0u;
}

uint32_t *fb_backbuffer(void)
{
	return g_backbuffer_ok ? g_backbuffer : 0;
}

int fb_has_backbuffer(void)
{
	return (g_info.available && g_backbuffer_ok) ? 1 : 0;
}

/* ======================================================================== */
/* conversion de color                                                     */
/* ======================================================================== */

/* 0x00RRGGBB -> valor que espera el hardware (mascaras reales). */
uint32_t fb_map_color(uint32_t rgb)
{
	uint32_t r, g, b;

	if (!g_info.available) {
		return rgb & 0x00FFFFFFu;
	}
	if (g_fast_layout) {
		return rgb & 0x00FFFFFFu;       /* identidad en BGRX/RGB de 8 bits */
	}
	r = (rgb >> 16) & 0xFFu;
	g = (rgb >> 8) & 0xFFu;
	b = rgb & 0xFFu;
	return (scale_channel(r, g_info.red_size) << g_info.red_pos) |
	       (scale_channel(g, g_info.green_size) << g_info.green_pos) |
	       (scale_channel(b, g_info.blue_size) << g_info.blue_pos);
}

/* Valor de la mascara real -> 0x00RRGGBB (solo lo usa fb_get_pixel). */
static uint32_t fb_unmap_color(uint32_t pixel)
{
	uint32_t r, g, b;

	if (!g_info.available) {
		return pixel & 0x00FFFFFFu;
	}
	if (g_fast_layout) {
		return pixel & 0x00FFFFFFu;
	}
	r = (pixel >> g_info.red_pos) & ((1u << g_info.red_size) - 1u);
	g = (pixel >> g_info.green_pos) & ((1u << g_info.green_size) - 1u);
	b = (pixel >> g_info.blue_pos) & ((1u << g_info.blue_size) - 1u);
	return (expand_channel(r, g_info.red_size) << 16) |
	       (expand_channel(g, g_info.green_size) << 8) |
	       expand_channel(b, g_info.blue_size);
}

uint32_t fb_rgb(uint8_t r, uint8_t g, uint8_t b)
{
	return ((uint32_t)r << 16) | ((uint32_t)g << 8) | (uint32_t)b;
}

/* ======================================================================== */
/* dibujo directo sobre la VRAM (sin backbuffer)                           */
/* ======================================================================== */

/* Escribe un pixel ya convertido en (x,y).  Supone coordenadas validas. */
static void direct_write_mapped(int x, int y, uint32_t mapped)
{
	size_t offset = (size_t)y * g_info.pitch;

	if (g_info.bpp == 32u) {
		volatile uint32_t *row =
		    (volatile uint32_t *)(uintptr_t)(g_vram + offset);
		row[x] = mapped;
	} else {
		volatile uint8_t *p = g_vram + offset + (size_t)x * 3u;
		p[0] = (uint8_t)(mapped & 0xFFu);
		p[1] = (uint8_t)((mapped >> 8) & 0xFFu);
		p[2] = (uint8_t)((mapped >> 16) & 0xFFu);
	}
}

/* Rellena una linea de x0 a x1-1 con un color ya convertido. */
static void direct_fill_row(int y, int x0, int x1, uint32_t mapped)
{
	size_t offset = (size_t)y * g_info.pitch;
	int n = x1 - x0;

	if (n <= 0) {
		return;
	}
	if (g_info.bpp == 32u) {
		volatile uint32_t *row =
		    (volatile uint32_t *)(uintptr_t)(g_vram + offset) + x0;
		while (n-- > 0) {
			*row++ = mapped;
		}
	} else {
		volatile uint8_t *p = g_vram + offset + (size_t)x0 * 3u;
		while (n-- > 0) {
			p[0] = (uint8_t)(mapped & 0xFFu);
			p[1] = (uint8_t)((mapped >> 8) & 0xFFu);
			p[2] = (uint8_t)((mapped >> 16) & 0xFFu);
			p += 3;
		}
	}
}

/* Rellena un rectangulo directo con un color ya convertido. */
static void direct_fill_rect(int x, int y, int w, int h, uint32_t mapped)
{
	int yy;

	if (w <= 0 || h <= 0) {
		return;
	}
	if (x < 0) {
		w += x;
		x = 0;
	}
	if (y < 0) {
		h += y;
		y = 0;
	}
	if (x + w > (int)g_info.width) {
		w = (int)g_info.width - x;
	}
	if (y + h > (int)g_info.height) {
		h = (int)g_info.height - y;
	}
	if (w <= 0 || h <= 0) {
		return;
	}
	for (yy = y; yy < y + h; yy++) {
		direct_fill_row(yy, x, x + w, mapped);
	}
}

void fb_put_pixel_direct(int x, int y, uint32_t rgb)
{
	if (!g_info.available) {
		return;
	}
	if (x < 0 || y < 0 ||
	    (uint32_t)x >= g_info.width || (uint32_t)y >= g_info.height) {
		return;
	}
	direct_write_mapped(x, y, fb_map_color(rgb));
}

void fb_fill_direct(uint32_t rgb)
{
	uint32_t mapped;
	uint32_t yy;
	uint32_t n = g_info.width;

	if (!g_info.available) {
		return;
	}
	mapped = fb_map_color(rgb);
	for (yy = 0; yy < g_info.height; yy++) {
		direct_fill_row((int)yy, 0, (int)n, mapped);
	}
}

/*
 * Patron de prueba de video: degradado, barras de color, rejilla, borde,
 * cruz central y rampa de grises.  Sirve para comprobar a simple vista que
 * las mascaras RGB se interpretan bien y que el pitch es correcto (una
 * rejilla torcida o colores cruzados delatan un error de formato).
 */
void fb_draw_test_pattern(void)
{
	static const uint32_t bars[8] = {
		0x00FF0000u, 0x0000FF00u, 0x000000FFu, 0x0000FFFFu,
		0x00FF00FFu, 0x00FFFF00u, 0x00FFFFFFu, 0x00808080u
	};
	int w, h, i, y;

	if (!g_info.available) {
		return;
	}
	w = (int)g_info.width;
	h = (int)g_info.height;

	/* Fondo: degradado vertical azul noche -> casi negro. */
	for (y = 0; y < h; y++) {
		uint32_t t = (h > 1) ? (uint32_t)((y * 255) / (h - 1)) : 0u;
		uint32_t r = 10u + ((3u - 10u) * t) / 255u;
		uint32_t g = 18u + ((6u - 18u) * t) / 255u;
		uint32_t b = 46u + ((16u - 46u) * t) / 255u;
		direct_fill_row(y, 0, w, fb_map_color(fb_rgb((uint8_t)r,
		                                             (uint8_t)g,
		                                             (uint8_t)b)));
	}

	/* Barras de color en la franja central. */
	for (i = 0; i < 8; i++) {
		int x0 = (i * w) / 8;
		int x1 = ((i + 1) * w) / 8;
		direct_fill_rect(x0, h / 3, x1 - x0, h / 6,
		                 fb_map_color(bars[i]));
	}

	/* Rejilla tenue cada 64 pixeles. */
	for (i = 0; i < w; i += 64) {
		direct_fill_rect(i, 0, 1, h, fb_map_color(0x00223045u));
	}
	for (i = 0; i < h; i += 64) {
		direct_fill_rect(0, i, w, 1, fb_map_color(0x00223045u));
	}

	/* Cruz central. */
	direct_fill_rect(w / 2 - 1, 0, 2, h, fb_map_color(0x00FFFFFFu));
	direct_fill_rect(0, h / 2 - 1, w, 2, fb_map_color(0x00FFFFFFu));

	/* Borde de 3 pixeles y esquinas de referencia. */
	direct_fill_rect(0, 0, w, 3, fb_map_color(0x00E8EEF8u));
	direct_fill_rect(0, h - 3, w, 3, fb_map_color(0x00E8EEF8u));
	direct_fill_rect(0, 0, 3, h, fb_map_color(0x00E8EEF8u));
	direct_fill_rect(w - 3, 0, 3, h, fb_map_color(0x00E8EEF8u));

	/* Rampa de grises (32 pasos) en la banda inferior. */
	for (i = 0; i < 32; i++) {
		int x0 = (i * w) / 32;
		int x1 = ((i + 1) * w) / 32;
		uint32_t v = (uint32_t)(i * 255 / 31);
		direct_fill_rect(x0, h - h / 8, x1 - x0, h / 8,
		                 fb_map_color(fb_rgb((uint8_t)v, (uint8_t)v,
		                                      (uint8_t)v)));
	}
}

/* ======================================================================== */
/* backbuffer                                                              */
/* ======================================================================== */

void fb_put_pixel(int x, int y, uint32_t rgb)
{
	if (!g_backbuffer_ok) {
		return;
	}
	if (x < 0 || y < 0 ||
	    (uint32_t)x >= g_info.width || (uint32_t)y >= g_info.height) {
		return;
	}
	g_backbuffer[(size_t)y * g_info.width + (uint32_t)x] = fb_map_color(rgb);
}

uint32_t fb_get_pixel(int x, int y)
{
	if (!g_backbuffer_ok) {
		return 0u;
	}
	if (x < 0 || y < 0 ||
	    (uint32_t)x >= g_info.width || (uint32_t)y >= g_info.height) {
		return 0u;
	}
	return fb_unmap_color(g_backbuffer[(size_t)y * g_info.width + (uint32_t)x]);
}

/* Copia el contenido actual de la VRAM al backbuffer (continuidad del splash
 * de GRUB y de cualquier dibujo directo previo). */
void fb_copy_direct_to_backbuffer(void)
{
	uint32_t x, y;

	if (!g_backbuffer_ok) {
		return;
	}
	for (y = 0u; y < g_info.height; y++) {
		uint32_t *dst = g_backbuffer + (size_t)y * g_info.width;
		if (g_info.bpp == 32u) {
			volatile uint32_t *src =
			    (volatile uint32_t *)(uintptr_t)
			    (g_vram + (size_t)y * g_info.pitch);
			for (x = 0u; x < g_info.width; x++) {
				dst[x] = src[x];
			}
		} else {
			volatile uint8_t *src =
			    g_vram + (size_t)y * g_info.pitch;
			for (x = 0u; x < g_info.width; x++) {
				uint32_t p0 = src[(size_t)x * 3u + 0u];
				uint32_t p1 = src[(size_t)x * 3u + 1u];
				uint32_t p2 = src[(size_t)x * 3u + 2u];
				dst[x] = p0 | (p1 << 8) | (p2 << 16);
			}
		}
	}
	fb_mark_all_dirty();
}

/* ======================================================================== */
/* regiones sucias                                                         */
/* ======================================================================== */

/* Recorta un rectangulo a la pantalla.  Devuelve 0 si queda vacio. */
static int clip_dirty_rect(int x, int y, int w, int h, fb_rect_t *out)
{
	int x0 = x;
	int y0 = y;
	int x1 = x + w;
	int y1 = y + h;

	if (w <= 0 || h <= 0) {
		return 0;
	}
	if (x0 < 0) {
		x0 = 0;
	}
	if (y0 < 0) {
		y0 = 0;
	}
	if (x1 > (int)g_info.width) {
		x1 = (int)g_info.width;
	}
	if (y1 > (int)g_info.height) {
		y1 = (int)g_info.height;
	}
	if (x1 <= x0 || y1 <= y0) {
		return 0;
	}
	out->x0 = x0;
	out->y0 = y0;
	out->x1 = x1;
	out->y1 = y1;
	return 1;
}

void fb_mark_dirty(int x, int y, int w, int h)
{
	fb_rect_t n;
	int i;

	if (!g_info.available) {
		return;
	}
	if (!clip_dirty_rect(x, y, w, h, &n)) {
		return;
	}

	/* Fusiona con todos los rectangulos que solapen; la union puede pasar a
	 * solapar otros, por eso se reinicia el recorrido tras cada fusion. */
	i = 0;
	while (i < g_dirty_count) {
		fb_rect_t *d = &g_dirty[i];
		if (n.x0 < d->x1 && d->x0 < n.x1 && n.y0 < d->y1 && d->y0 < n.y1) {
			if (d->x0 < n.x0) {
				n.x0 = d->x0;
			}
			if (d->y0 < n.y0) {
				n.y0 = d->y0;
			}
			if (d->x1 > n.x1) {
				n.x1 = d->x1;
			}
			if (d->y1 > n.y1) {
				n.y1 = d->y1;
			}
			g_dirty_count--;
			g_dirty[i] = g_dirty[g_dirty_count];
			i = 0;
			continue;
		}
		i++;
	}

	if (g_dirty_count < FB_DIRTY_MAX) {
		g_dirty[g_dirty_count++] = n;
	} else {
		/* Sin hueco libre: se pierde precision y se presenta el area de
		 * todos los rectangulos como una sola region. */
		fb_rect_t all = n;
		for (i = 0; i < g_dirty_count; i++) {
			if (g_dirty[i].x0 < all.x0) {
				all.x0 = g_dirty[i].x0;
			}
			if (g_dirty[i].y0 < all.y0) {
				all.y0 = g_dirty[i].y0;
			}
			if (g_dirty[i].x1 > all.x1) {
				all.x1 = g_dirty[i].x1;
			}
			if (g_dirty[i].y1 > all.y1) {
				all.y1 = g_dirty[i].y1;
			}
		}
		g_dirty[0] = all;
		g_dirty_count = 1;
	}
}

void fb_mark_all_dirty(void)
{
	if (!g_info.available) {
		return;
	}
	g_dirty[0].x0 = 0;
	g_dirty[0].y0 = 0;
	g_dirty[0].x1 = (int)g_info.width;
	g_dirty[0].y1 = (int)g_info.height;
	g_dirty_count = 1;
}

/* ======================================================================== */
/* presentacion a VRAM                                                     */
/* ======================================================================== */

/* Copia `count` palabras del backbuffer a una fila de la VRAM. */
static void present_words(volatile uint8_t *vram_row, const uint32_t *src,
                          int count)
{
#if defined(__i386__)
	if (count >= 16) {
		/* rep movsl es notablemente mas rapido que un bucle en QEMU. */
		uint32_t *dst = (uint32_t *)(uintptr_t)vram_row;
		uint32_t *s = (uint32_t *)(uintptr_t)src;
		__asm__ volatile ("rep movsl"
		                  : "+D"(dst), "+S"(s), "+c"(count)
		                  :
		                  : "memory");
		return;
	}
#endif
	{
		volatile uint32_t *dst = (volatile uint32_t *)(uintptr_t)vram_row;
		while (count-- > 0) {
			*dst++ = *src++;
		}
	}
}

/* Copia una fila de la region [x0,x1) de la fila y del backbuffer a la VRAM. */
static void present_row(int y, int x0, int x1)
{
	int n = x1 - x0;
	const uint32_t *src;
	size_t offset;

	if (n <= 0) {
		return;
	}
	src = g_backbuffer + (size_t)y * g_info.width + (uint32_t)x0;
	offset = (size_t)y * g_info.pitch;

	if (g_info.bpp == 32u) {
		present_words(g_vram + offset + (size_t)x0 * 4u, src, n);
	} else {
		volatile uint8_t *dst = g_vram + offset + (size_t)x0 * 3u;
		while (n-- > 0) {
			uint32_t p = *src++;
			dst[0] = (uint8_t)(p & 0xFFu);
			dst[1] = (uint8_t)((p >> 8) & 0xFFu);
			dst[2] = (uint8_t)((p >> 16) & 0xFFu);
			dst += 3;
		}
	}
}

/* Copia a VRAM el rectangulo ya recortado. */
static void present_rect(const fb_rect_t *r)
{
	int y;

	for (y = r->y0; y < r->y1; y++) {
		present_row(y, r->x0, r->x1);
	}
}

void fb_present(void)
{
	fb_rect_t full;

	if (!g_backbuffer_ok) {
		return;
	}
	full.x0 = 0;
	full.y0 = 0;
	full.x1 = (int)g_info.width;
	full.y1 = (int)g_info.height;
	present_rect(&full);
	g_dirty_count = 0;
}

void fb_present_dirty(void)
{
	int i;

	if (!g_backbuffer_ok) {
		return;
	}
	for (i = 0; i < g_dirty_count; i++) {
		present_rect(&g_dirty[i]);
	}
	g_dirty_count = 0;
}
