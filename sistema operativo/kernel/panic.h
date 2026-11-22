/* kernel/panic.h - pantalla de excepciones y parada segura */
#ifndef SEREOS_PANIC_H
#define SEREOS_PANIC_H
#include <stdint.h>
#include "interrupts.h"

void panic_exception(struct regs *r);
void panic(const char *msg);

#endif
