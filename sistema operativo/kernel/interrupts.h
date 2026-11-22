/* kernel/interrupts.h - GDT, IDT, excepciones y PIC 8259 */
#ifndef SEREOS_INTERRUPTS_H
#define SEREOS_INTERRUPTS_H
#include <stdint.h>

struct regs {
	uint32_t ds;
	uint32_t edi, esi, ebp, esp, ebx, edx, ecx, eax;
	uint32_t int_no, err_code;
	uint32_t eip, cs, eflags;
};

typedef void (*irq_handler_t)(struct regs *);

void gdt_init(void);
void idt_init(void);
void irq_install(int irq, irq_handler_t h);
void interrupt_handler(struct regs *r);
uint32_t irq_count(int irq);

#endif
