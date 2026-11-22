/* kernel/idt.c - Tabla de Descriptores de Interrupcion, excepciones y PIC 8259 */
#include "interrupts.h"
#include "panic.h"
#include "io.h"

struct idt_entry { uint16_t base_low, sel; uint8_t zero, flags; uint16_t base_high; } __attribute__((packed));
struct idt_ptr { uint16_t limit; uint32_t base; } __attribute__((packed));
static struct idt_entry idt[256];
static struct idt_ptr ip;
static irq_handler_t irq_handlers[16];
static volatile uint32_t irq_counts[16];
extern void idt_flush(uint32_t);

#define DECL(n) extern void isr##n(void);
DECL(0) DECL(1) DECL(2) DECL(3) DECL(4) DECL(5) DECL(6) DECL(7) DECL(8) DECL(9) DECL(10) DECL(11)
DECL(12) DECL(13) DECL(14) DECL(15) DECL(16) DECL(17) DECL(18) DECL(19) DECL(20) DECL(21) DECL(22)
DECL(23) DECL(24) DECL(25) DECL(26) DECL(27) DECL(28) DECL(29) DECL(30) DECL(31)
#define DIRQ(n) extern void irq##n(void);
DIRQ(0) DIRQ(1) DIRQ(2) DIRQ(3) DIRQ(4) DIRQ(5) DIRQ(6) DIRQ(7) DIRQ(8) DIRQ(9) DIRQ(10) DIRQ(11)
DIRQ(12) DIRQ(13) DIRQ(14) DIRQ(15)

static void (*const isrs[32])(void) = { isr0, isr1, isr2, isr3, isr4, isr5, isr6, isr7, isr8, isr9,
	isr10, isr11, isr12, isr13, isr14, isr15, isr16, isr17, isr18, isr19, isr20, isr21, isr22, isr23,
	isr24, isr25, isr26, isr27, isr28, isr29, isr30, isr31 };
static void (*const irqs[16])(void) = { irq0, irq1, irq2, irq3, irq4, irq5, irq6, irq7, irq8, irq9,
	irq10, irq11, irq12, irq13, irq14, irq15 };

static void idt_set(int n, uint32_t base) {
	idt[n].base_low = base & 0xFFFF;
	idt[n].base_high = (base >> 16) & 0xFFFF;
	idt[n].sel = 0x08;
	idt[n].zero = 0;
	idt[n].flags = 0x8E;        /* presente, anillo 0, interrupt gate de 32 bits */
}

/* reubica las IRQ del PIC 8259 a los vectores 32-47 para no chocar con las excepciones */
static void pic_remap(void) {
	outb(0x20, 0x11); io_wait(); outb(0xA0, 0x11); io_wait();
	outb(0x21, 0x20); io_wait(); outb(0xA1, 0x28); io_wait();
	outb(0x21, 0x04); io_wait(); outb(0xA1, 0x02); io_wait();
	outb(0x21, 0x01); io_wait(); outb(0xA1, 0x01); io_wait();
	outb(0x21, 0x00); outb(0xA1, 0x00);
}

void idt_init(void) {
	ip.limit = sizeof(idt) - 1;
	ip.base = (uint32_t)&idt;
	for (int i = 0; i < 32; i++) idt_set(i, (uint32_t)isrs[i]);
	pic_remap();
	for (int i = 0; i < 16; i++) idt_set(32 + i, (uint32_t)irqs[i]);
	idt_flush((uint32_t)&ip);
}

void irq_install(int irq, irq_handler_t h) { irq_handlers[irq % 16] = h; }
uint32_t irq_count(int irq) { return irq_counts[irq % 16]; }

void interrupt_handler(struct regs *r) {
	if (r->int_no < 32) panic_exception(r);       /* pantalla de excepcion (no retorna) */
	int irq = r->int_no - 32;
	irq_counts[irq]++;
	if (irq_handlers[irq]) irq_handlers[irq](r);
	if (irq >= 8) outb(0xA0, 0x20);               /* fin de interrupcion (EOI) al PIC esclavo */
	outb(0x20, 0x20);                             /* EOI al PIC maestro */
}
