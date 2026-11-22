/* graphics/framebuffer.h - framebuffer lineal entregado por GRUB (Multiboot 1) */
#ifndef SEREOS_FRAMEBUFFER_H
#define SEREOS_FRAMEBUFFER_H
#include <stdint.h>

#define FB_MAX_WIDTH   1280
#define FB_MAX_HEIGHT  1024
#define FB_MAX_PIXELS  (FB_MAX_WIDTH * FB_MAX_HEIGHT)

typedef struct {
	int      available;
	uint32_t width, height;
	uint32_t pitch;          /* bytes por fila */
	uint8_t  bpp;            /* bits por pixel (esperado 32) */
	uint32_t physical;       /* direccion fisica del framebuffer */
	uint8_t  red_pos, red_size;
	uint8_t  green_pos, green_size;
	uint8_t  blue_pos, blue_size;
	uint8_t  type;           /* 0 = indexed, 1 = RGB, 2 = EGA */
	uint32_t bytes;
} fb_info_t;

/* boot_info = direccion de la estructura multiboot_info que dejo GRUB */
int               fb_init(uint32_t boot_info_addr);
int               fb_available(void);
const fb_info_t  *fb_info(void);
uint32_t          fb_width(void);
uint32_t          fb_height(void);
uint32_t          fb_pitch(void);
uint32_t          fb_bpp(void);
uint32_t          fb_size_bytes(void);

/* dibujo directo sobre el framebuffer (sin backbuffer, para el arranque) */
void     fb_put_pixel_direct(int x, int y, uint32_t rgb);
void     fb_fill_direct(uint32_t rgb);
void     fb_draw_test_pattern(void);

/* backbuffer (doble buffer) */
uint32_t *fb_backbuffer(void);
int       fb_has_backbuffer(void);
void      fb_put_pixel(int x, int y, uint32_t rgb);
uint32_t  fb_get_pixel(int x, int y);
void      fb_copy_direct_to_backbuffer(void);

/* conversion de color 0x00RRGGBB al formato del framebuffer */
uint32_t  fb_map_color(uint32_t rgb);
uint32_t  fb_rgb(uint8_t r, uint8_t g, uint8_t b);

/* regiones sucias: solo se copian a VRAM las zonas modificadas */
void      fb_mark_dirty(int x, int y, int w, int h);
void      fb_mark_all_dirty(void);
void      fb_present(void);          /* copia todo el backbuffer */
void      fb_present_dirty(void);    /* copia solo las regiones sucias */

#endif
