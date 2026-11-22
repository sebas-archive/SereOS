/* stubs.c - dependencias del kernel real necesarias para probar shutdown.c
 * aislado en QEMU. Solo para la prueba; no forma parte del arbol SereOS. */
#include <stdint.h>
#include <stdarg.h>
#include "theme.h"

static inline void outb_(uint16_t p, uint8_t v) { __asm__ volatile("outb %0,%1"::"a"(v),"Nd"(p)); }
static inline uint8_t inb_(uint16_t p) { uint8_t v; __asm__ volatile("inb %1,%0":"=a"(v):"Nd"(p)); return v; }

void shutdown_test_serial_init(void) {
    outb_(0x3F9, 0x00);
    outb_(0x3FB, 0x80);
    outb_(0x3F8, 0x01);
    outb_(0x3F9, 0x00);
    outb_(0x3FB, 0x03);
    outb_(0x3FA, 0xC7);
    outb_(0x3FC, 0x0B);
}

static void com1_putc(char c) {
    int guard = 100000;
    while (!(inb_(0x3FD) & 0x20) && --guard) { }
    outb_(0x3F8, (uint8_t)c);
}
void serial_write(const char *s) { while (*s) com1_putc(*s++); }
void serial_init(void) { shutdown_test_serial_init(); }
int  serial_ready(void) { return 1; }
void serial_putc(char c) { com1_putc(c); }

static void put_uint(unsigned v, unsigned base, int width, int zero, char *out, int *n) {
    char tmp[16]; int i = 0;
    do { unsigned d = v % base; tmp[i++] = (char)(d < 10 ? '0' + d : 'a' + d - 10); v /= base; } while (v);
    while (width > i) { tmp[i++] = zero ? '0' : ' '; }
    while (i > 0) out[(*n)++] = tmp[--i];
}
void serial_printf(const char *fmt, ...) {
    char buf[256]; int n = 0; va_list ap;
    va_start(ap, fmt);
    while (*fmt && n < 250) {
        if (*fmt != '%') { buf[n++] = *fmt++; continue; }
        fmt++;
        int zero = 0, width = 0;
        if (*fmt == '0') { zero = 1; fmt++; }
        while (*fmt >= '0' && *fmt <= '9') { width = width * 10 + (*fmt - '0'); fmt++; }
        if (*fmt == 'x') { put_uint(va_arg(ap, unsigned), 16, width, zero, buf, &n); fmt++; }
        else if (*fmt == 'u') { put_uint(va_arg(ap, unsigned), 10, width, zero, buf, &n); fmt++; }
        else if (*fmt == 'd') { int v = va_arg(ap, int); if (v < 0) { buf[n++] = '-'; v = -v; } put_uint((unsigned)v, 10, width, zero, buf, &n); fmt++; }
        else if (*fmt == 's') { const char *s = va_arg(ap, const char *); while (s && *s && n < 250) buf[n++] = *s++; fmt++; }
        else if (*fmt == '%') { buf[n++] = '%'; fmt++; }
        else { buf[n++] = *fmt++; }
    }
    buf[n] = 0;
    va_end(ap);
    serial_write(buf);
}

/* --- dependencias del kernel que shutdown.c invoca --- */
void audio_stop(void) { serial_write("STUB:audio_stop\n"); }

struct window { int dummy; };
int window_count(void) { return 0; }
struct window *window_get(int index) { (void)index; return 0; }
void window_close(struct window *w) { (void)w; }
void window_process_pending(void) { }

int fb_available(void) { return 0; }
int fb_has_backbuffer(void) { return 0; }
int gfx_width(void) { return 0; }
int gfx_height(void) { return 0; }
void gfx_reset_clip(void) {}
void gfx_clear(uint32_t color) { (void)color; }
int  gfx_text_width(const char *s, int scale) { (void)s; (void)scale; return 0; }
void gfx_draw_text(int x, int y, const char *s, uint32_t c, int scale) { (void)x;(void)y;(void)s;(void)c;(void)scale; }
void gfx_mark_all_dirty(void) {}
void gfx_present(void) {}
void terminal_write(const char *s) { serial_write("[VGA] "); serial_write(s); }
void timer_sleep_ms(uint32_t ms) { (void)ms; }
uint32_t timer_hz(void) { return 0; }

/* libc minima que usa shutdown.c */
#include <stddef.h>
size_t strlen(const char *s) { size_t n = 0; while (s && s[n]) n++; return n; }
void *memcpy(void *d, const void *src, size_t n) {
    unsigned char *dd = d; const unsigned char *ss = src;
    while (n--) *dd++ = *ss++;
    return d;
}

/* tema del sistema (subset con los colores que usa shutdown.c) */
const theme_t theme = {
    .bg = 0x0B0D12u,
    .text = 0xF2F4F8u,
    .text_dim = 0xA8B0C0u,
    .black = 0x000000u,
};
void logo_draw_about(int cx, int cy, int size) { (void)cx; (void)cy; (void)size; }
void text_draw_center(text_style_t style, int cx, int y, const char *text, uint32_t color) {
    (void)cx; (void)y; (void)color;
    serial_printf("STUB:text_center style=%d text=%s\n", style, text ? text : "(null)");
}
int text_height(text_style_t style) { return style == TEXT_DISPLAY ? 34 : 15; }
void gfx_fill_rect_alpha(int x, int y, int w, int h, uint32_t c, uint8_t a) {
    (void)x;(void)y;(void)w;(void)h;(void)c;(void)a;
}

/* entradas de las pruebas */
void sereos_shutdown(void);
void sereos_restart(void);
void shutdown_test_entry(void) {
    serial_init();
    serial_write("SHUTDOWN_TEST_START\n");
    sereos_shutdown();
    serial_write("SHUTDOWN_TEST_SURVIVED\n");
    for (;;) __asm__ volatile("cli; hlt");
}
void restart_test_entry(void) {
    serial_init();
    serial_write("RESTART_TEST_START\n");
    sereos_restart();
    serial_write("RESTART_TEST_SURVIVED\n");
    for (;;) __asm__ volatile("cli; hlt");
}
