#ifndef TERMINAL_H
#define TERMINAL_H
#include <stdint.h>
#include <stddef.h>
enum vga_color {
	VGA_BLACK = 0, VGA_BLUE = 1, VGA_GREEN = 2, VGA_CYAN = 3,
	VGA_RED = 4, VGA_MAGENTA = 5, VGA_BROWN = 6, VGA_LIGHT_GREY = 7,
	VGA_DARK_GREY = 8, VGA_LIGHT_BLUE = 9, VGA_LIGHT_GREEN = 10,
	VGA_LIGHT_CYAN = 11, VGA_LIGHT_RED = 12, VGA_LIGHT_MAGENTA = 13,
	VGA_YELLOW = 14, VGA_WHITE = 15,
};
void terminal_init(void);
void terminal_clear(void);
void terminal_putchar(char c);
void terminal_write(const char *s);
void terminal_write_color(const char *s, enum vga_color fg);
void terminal_write_uint(uint32_t v);
void terminal_write_hex(uint32_t v);
void terminal_ok(const char *msg);
void terminal_status(const char *left, uint32_t seconds);
void terminal_panic_screen(void);
size_t kstrlen(const char *s);
int kstrcmp(const char *a, const char *b);
#endif
