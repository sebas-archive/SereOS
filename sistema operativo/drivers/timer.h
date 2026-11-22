/* drivers/timer.h - PIT 8253/8254 a 100 Hz (IRQ 0) */
#ifndef SEREOS_TIMER_H
#define SEREOS_TIMER_H
#include <stdint.h>

void     timer_init(uint32_t hz);
uint32_t timer_ticks(void);
uint32_t timer_hz(void);
uint32_t timer_uptime_ms(void);
uint32_t timer_uptime_sec(void);
void     timer_sleep_ms(uint32_t ms);   /* espera con hlt, sin bloquear IRQ */

#endif
