/* drivers/serial.h - puerto serie COM1 para diagnostico y pruebas */
#ifndef SEREOS_SERIAL_H
#define SEREOS_SERIAL_H
#include <stdint.h>

void serial_init(void);
void serial_putc(char c);
void serial_write(const char *s);
void serial_printf(const char *fmt, ...);
int  serial_ready(void);

#endif
