/* drivers/serial.c - puerto serie COM1 (16550 UART) para diagnostico
 *
 * Configuracion: 115200 baudios, 8 bits de datos, sin paridad, 1 bit de
 * parada (8N1), FIFO habilitada. Se usa para los marcadores de QA y para
 * replicar el log del kernel (kprintf -> serial + VGA).
 *
 * El puerto se valida con una lectura del registro LSR: un bus sin UART
 * devuelve 0xFF. Si no hay puerto, serial_ready() es 0 y todas las salidas
 * se descartan en silencio (el sistema nunca debe caerse por el serie).
 */
#include "serial.h"
#include "io.h"
#include "string.h"

#define COM1_BASE   0x3F8
#define REG_DATA    (COM1_BASE + 0)
#define REG_IER     (COM1_BASE + 1)
#define REG_FIFO    (COM1_BASE + 2)
#define REG_LCR     (COM1_BASE + 3)
#define REG_MCR     (COM1_BASE + 4)
#define REG_LSR     (COM1_BASE + 5)
#define LSR_THR_EMPTY 0x20
#define LSR_TEMT      0x40

static int ready;

void serial_init(void) {
	int i;

	/* si el puerto no existe, el bus flota a 0xFF */
	ready = 0;
	outb(REG_IER, 0x00);          /* sin interrupciones del UART */
	outb(REG_LCR, 0x80);          /* DLAB = 1 para fijar el divisor */
	outb(REG_DATA, 0x01);         /* divisor 1 => 115200 baudios */
	outb(REG_IER, 0x00);
	outb(REG_LCR, 0x03);          /* 8N1, DLAB = 0 */
	outb(REG_FIFO, 0xC7);         /* habilitar y limpiar FIFOs, umbral 14 */
	outb(REG_MCR, 0x0B);          /* DTR + RTS + OUT2 */

	if (inb(REG_LSR) == 0xFF) return;   /* no hay UART en 0x3F8 */

	/* vaciar lo que haya pendiente de entrada (teclas de GRUB, etc.) */
	for (i = 0; i < 16 && (inb(REG_LSR) & 0x01); i++) (void)inb(REG_DATA);

	ready = 1;
}

int serial_ready(void) { return ready; }

void serial_putc(char c) {
	uint32_t guard;

	if (!ready) return;
	if (c == '\n') {              /* consola serie: CR antes de LF */
		guard = 100000u;
		while (!(inb(REG_LSR) & LSR_THR_EMPTY) && --guard) {}
		outb(REG_DATA, '\r');
	}
	guard = 100000u;
	while (!(inb(REG_LSR) & LSR_THR_EMPTY) && --guard) {}
	outb(REG_DATA, (uint8_t)c);
}

void serial_write(const char *s) {
	if (!ready || !s) return;
	while (*s) serial_putc(*s++);
}

void serial_printf(const char *fmt, ...) {
	char buf[256];
	va_list ap;
	int n;

	if (!ready || !fmt) return;
	va_start(ap, fmt);
	n = vsnprintf(buf, sizeof(buf), fmt, ap);
	va_end(ap);
	if (n < 0) return;
	if ((size_t)n >= sizeof(buf)) n = (int)sizeof(buf) - 1;
	serial_write(buf);
}
