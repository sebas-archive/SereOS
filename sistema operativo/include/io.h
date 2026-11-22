/* include/io.h - acceso a puertos de E/S del x86 */
#ifndef SEREOS_IO_H
#define SEREOS_IO_H
#include <stdint.h>

static inline void outb(uint16_t port, uint8_t val) {
	__asm__ volatile ("outb %0, %1" : : "a"(val), "Nd"(port));
}
static inline uint8_t inb(uint16_t port) {
	uint8_t r;
	__asm__ volatile ("inb %1, %0" : "=a"(r) : "Nd"(port));
	return r;
}
static inline void outw(uint16_t port, uint16_t val) {
	__asm__ volatile ("outw %0, %1" : : "a"(val), "Nd"(port));
}
static inline uint16_t inw(uint16_t port) {
	uint16_t r;
	__asm__ volatile ("inw %1, %0" : "=a"(r) : "Nd"(port));
	return r;
}
static inline void io_wait(void) { outb(0x80, 0); }
static inline void cli(void) { __asm__ volatile ("cli"); }
static inline void sti(void) { __asm__ volatile ("sti"); }
static inline void hlt(void) { __asm__ volatile ("hlt"); }
static inline void irq_save_disable(void) { __asm__ volatile ("cli"); }
#endif
