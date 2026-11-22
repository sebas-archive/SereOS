/* drivers/timer.c - temporizador PIT 8253/8254 en el IRQ 0 (100 Hz por defecto)
 *
 * La ISR solo incrementa el contador de ticks: no toca la consola ni el
 * terminal_status (la barra de estado del escritorio la dibuja la GUI).
 * timer_sleep_ms() espera activamente con hlt(), de modo que el procesador
 * queda en bajo consumo y las interrupciones siguen atendiendo teclado/raton.
 */
#include <stdint.h>
#include "timer.h"
#include "interrupts.h"
#include "io.h"

#define PIT_BASE_HZ 1193182u   /* frecuencia real del oscilador del PIT */

static volatile uint32_t ticks = 0;
static uint32_t freq = 100;    /* Hz configurados */

static void timer_callback(struct regs *r) {
	(void)r;
	ticks++;
}

void timer_init(uint32_t hz) {
	if (hz == 0 || hz > PIT_BASE_HZ) hz = 100;

	uint32_t divisor = PIT_BASE_HZ / hz;
	if (divisor == 0) divisor = 1;
	if (divisor > 65535u) divisor = 65535u;

	freq = hz;
	ticks = 0;

	outb(0x43, 0x36);                              /* canal 0, modo 3, lobyte/hibyte */
	outb(0x40, (uint8_t)(divisor & 0xFF));
	outb(0x40, (uint8_t)((divisor >> 8) & 0xFF));

	irq_install(0, timer_callback);
}

uint32_t timer_ticks(void) {
	return ticks;
}

uint32_t timer_hz(void) {
	return freq;
}

uint32_t timer_uptime_ms(void) {
	uint32_t t = ticks;
	uint32_t f = freq ? freq : 1;
	/* division primero para no desbordar t * 1000 en 32 bits */
	return (t / f) * 1000u + ((t % f) * 1000u) / f;
}

uint32_t timer_uptime_sec(void) {
	uint32_t f = freq ? freq : 1;
	return ticks / f;
}

void timer_sleep_ms(uint32_t ms) {
	if (ms == 0) return;
	uint32_t f = freq ? freq : 1;

	/* ticks a esperar, calculado sin desbordar con ms grandes */
	uint32_t wait = (ms / 1000u) * f + (((ms % 1000u) * f + 999u) / 1000u);
	if (wait == 0) wait = 1;

	uint32_t start = ticks;
	/* hlt hasta que el PIT haya avanzado los ticks necesarios */
	while ((uint32_t)(ticks - start) < wait)
		hlt();
}
