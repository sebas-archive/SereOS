/* drivers/terminal.c - consola de texto VGA 80x25 de SereOS (respaldo/diagnostico)
 *
 * Fila 0: barra de estado (nombre y version del sistema + uptime).
 * Filas 1 a 24: terminal con scroll, backspace, tabulador y cursor hardware.
 *
 * Esta consola se usa cuando el framebuffer grafico no esta disponible y
 * tambien como canal de diagnostico (kprintf/panic). No depende de libc.
 */
#include "terminal.h"
#include "io.h"
#include "sereos_version.h"

#define VGA_WIDTH  80
#define VGA_HEIGHT 25
#define FIRST_ROW  1
#define VGA_TAB    8

static volatile uint16_t *const VGA = (uint16_t *)0xB8000;
static size_t row = FIRST_ROW, col = 0;
static uint8_t color = VGA_LIGHT_GREY | VGA_BLACK << 4;

static inline uint16_t entry(char c, uint8_t clr) {
	return (uint16_t)(unsigned char)c | (uint16_t)clr << 8;
}

/* ------------------------------------------------------------------ */
/* utilidades sin libc (las usa el kernel y la shell)                  */
/* ------------------------------------------------------------------ */

size_t kstrlen(const char *s) {
	size_t n = 0;
	while (s[n]) n++;
	return n;
}

int kstrcmp(const char *a, const char *b) {
	while (*a && *a == *b) { a++; b++; }
	return (unsigned char)*a - (unsigned char)*b;
}

/* mueve el cursor parpadeante del hardware (registros 0x0E y 0x0F del CRTC) */
static void update_cursor(void) {
	uint16_t pos = (uint16_t)(row * VGA_WIDTH + col);
	outb(0x3D4, 0x0F); outb(0x3D5, (uint8_t)(pos & 0xFF));
	outb(0x3D4, 0x0E); outb(0x3D5, (uint8_t)(pos >> 8));
}

/* ------------------------------------------------------------------ */
/* pantalla                                                            */
/* ------------------------------------------------------------------ */

void terminal_clear(void) {
	color = VGA_LIGHT_GREY | VGA_BLACK << 4;
	for (size_t y = FIRST_ROW; y < VGA_HEIGHT; y++)
		for (size_t x = 0; x < VGA_WIDTH; x++)
			VGA[y * VGA_WIDTH + x] = entry(' ', color);
	row = FIRST_ROW;
	col = 0;
	update_cursor();
}

void terminal_init(void) {
	color = VGA_LIGHT_GREY | VGA_BLACK << 4;
	for (size_t i = 0; i < VGA_WIDTH * VGA_HEIGHT; i++)
		VGA[i] = entry(' ', color);
	terminal_status(" " SEREOS_NAME " " SEREOS_VERSION "  |  consola VGA de respaldo  |  help", 0);
	row = FIRST_ROW;
	col = 0;
	update_cursor();
}

static void scroll(void) {
	for (size_t y = FIRST_ROW + 1; y < VGA_HEIGHT; y++)
		for (size_t x = 0; x < VGA_WIDTH; x++)
			VGA[(y - 1) * VGA_WIDTH + x] = VGA[y * VGA_WIDTH + x];
	for (size_t x = 0; x < VGA_WIDTH; x++)
		VGA[(VGA_HEIGHT - 1) * VGA_WIDTH + x] = entry(' ', color);
	row = VGA_HEIGHT - 1;
}

static void newline(void) {
	col = 0;
	if (++row >= VGA_HEIGHT) scroll();
}

void terminal_putchar(char c) {
	if (c == '\n') {
		newline();
	} else if (c == '\r') {
		col = 0;
	} else if (c == '\b') {
		/* retroceso: borra el caracter anterior, cruzando de fila */
		if (col > 0) {
			col--;
			VGA[row * VGA_WIDTH + col] = entry(' ', color);
		} else if (row > FIRST_ROW) {
			row--;
			col = VGA_WIDTH - 1;
			VGA[row * VGA_WIDTH + col] = entry(' ', color);
		}
	} else if (c == '\t') {
		size_t next = (col + VGA_TAB) & ~(size_t)(VGA_TAB - 1);
		if (next >= VGA_WIDTH) newline();
		else {
			while (col < next) {
				VGA[row * VGA_WIDTH + col] = entry(' ', color);
				col++;
			}
		}
	} else if (c == '\f') {
		terminal_clear();
	} else {
		VGA[row * VGA_WIDTH + col] = entry(c, color);
		if (++col == VGA_WIDTH) newline();
	}
	update_cursor();
}

void terminal_write(const char *s) {
	while (*s) terminal_putchar(*s++);
}

void terminal_write_color(const char *s, enum vga_color fg) {
	uint8_t old = color;
	color = (uint8_t)(fg | (VGA_BLACK << 4));
	terminal_write(s);
	color = old;
}

void terminal_write_uint(uint32_t v) {
	char buf[11];
	int i = 10;
	buf[i] = 0;
	if (v == 0) buf[--i] = '0';
	while (v) {
		buf[--i] = (char)('0' + (v % 10));
		v /= 10;
	}
	terminal_write(&buf[i]);
}

void terminal_write_hex(uint32_t v) {
	static const char hexdigits[] = "0123456789ABCDEF";
	char buf[11] = "0x00000000";
	for (int i = 9; i >= 2; i--) {
		buf[i] = hexdigits[v & 0xF];
		v >>= 4;
	}
	terminal_write(buf);
}

void terminal_ok(const char *msg) {
	terminal_write("[");
	terminal_write_color(" OK ", VGA_LIGHT_GREEN);
	terminal_write("] ");
	terminal_write(msg);
	terminal_write("\n");
}

/* barra de estado de la fila 0 (la llaman el arranque y la shell de texto) */
void terminal_status(const char *left, uint32_t seconds) {
	uint8_t c = (uint8_t)(VGA_WHITE | (VGA_BLUE << 4));
	size_t x = 0;

	if (left) {
		for (; left[x] && x < VGA_WIDTH; x++)
			VGA[x] = entry(left[x], c);
	}

	char t[] = "uptime 00:00:00 ";
	uint32_t h = seconds / 3600, m = (seconds / 60) % 60, sec = seconds % 60;
	t[7]  = (char)('0' + (h / 10) % 10);
	t[8]  = (char)('0' + h % 10);
	t[10] = (char)('0' + m / 10);
	t[11] = (char)('0' + m % 10);
	t[13] = (char)('0' + sec / 10);
	t[14] = (char)('0' + sec % 10);

	size_t suffix = sizeof(t) - 1;
	size_t start = (suffix < VGA_WIDTH) ? VGA_WIDTH - suffix : 0;
	for (; x < start; x++)
		VGA[x] = entry(' ', c);
	for (size_t i = 0; i < suffix && start + i < VGA_WIDTH; i++)
		VGA[start + i] = entry(t[i], c);
}

/* pantalla roja para errores fatales (excepciones del procesador) */
void terminal_panic_screen(void) {
	color = (uint8_t)(VGA_WHITE | (VGA_RED << 4));
	for (size_t i = VGA_WIDTH; i < VGA_WIDTH * VGA_HEIGHT; i++)
		VGA[i] = entry(' ', color);
	row = FIRST_ROW + 1;
	col = 0;
	update_cursor();
}
