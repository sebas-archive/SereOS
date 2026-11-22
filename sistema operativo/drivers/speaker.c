/* drivers/speaker.c - altavoz del PC a traves del PIT (canal 2)
 *
 * Hardware: el altavoz se conecta a la salida del canal 2 del PIT 8253/8254 y
 * a la compuerta de habilitacion del puerto 0x61:
 *   - bit 0 de 0x61 = compuerta (GATE) del canal 2 del PIT
 *   - bit 1 de 0x61 = habilitacion del altavoz (SPEAKER DATA)
 * El canal 0 del PIT (IRQ 0, 100 Hz) es independiente: se programa por 0x40
 * con la palabra de control 0x36 (canal 0), mientras que este driver usa
 * 0x42 con 0xB6 (canal 2). Ambos comparten la direccion 0x43 pero los bits
 * 6-7 seleccionan el canal, por lo que reprogramar el canal 2 NO altera los
 * 100 Hz del temporizador (comprobado con `ticks` en la shell).
 *
 * speaker_tone() programa el divisor del canal 2 (puertos 0x43/0x42), en
 * modo 3 (onda cuadrada) y deja el tono sonando sin bloquear: el juego puede
 * seguir animando mientras suena. speaker_off() corta la salida.
 * speaker_beep() es la unica operacion bloqueante y solo se usa para avisos
 * cortos (arranque, errores, comando de la shell).
 *
 * Importante para VMs: el altavoz del PC solo se oye si el hipervisor lo
 * emula y lo enruta a un backend de audio:
 *   - QEMU: -machine pcspk-audiodev=<audiodev> (si no, no hay sonido);
 *   - VirtualBox: la emulacion del PC speaker esta deshabilitada por defecto
 *     en muchas versiones y en cualquier caso no usa el controlador de audio
 *     de la VM -> practicamente inaudible;
 *   - VMware: no emula el altavoz del PC.
 * Por eso el SB16 es el backend preferente y este driver es solo el fallback.
 */
#include "speaker.h"
#include "timer.h"
#include "io.h"

#define PIT_FREQ_HZ 1193182u   /* reloj base del PIT */
#define PIT_CH2     0x42
#define PIT_CMD     0x43
#define SPEAKER_CTL 0x61

static int interrupts_enabled(void) {
	uint32_t flags;
	__asm__ volatile ("pushf; pop %0" : "=r"(flags));
	return (flags & 0x200u) ? 1 : 0;
}

/* deja el canal 2 en modo 3 (onda cuadrada) con un divisor conocido y la
 * compuerta apagada: estado inicial determinista del hardware */
void speaker_init(void) {
	speaker_off();
	outb(PIT_CMD, 0xB6);      /* canal 2, modo 3, lobyte/hibyte, binario */
	outb(PIT_CH2, 0x00);
	outb(PIT_CH2, 0x00);      /* divisor 65536: 18 Hz, inaudible con puerta off */
}

void speaker_tone(uint32_t hz) {
	uint32_t divisor;
	uint8_t ctl;

	if (hz == 0) { speaker_off(); return; }

	/* limites fisicos del PIT: divisor 1..65535 */
	if (hz > 20000u) hz = 20000u;
	if (hz < 19u) hz = 19u;
	divisor = PIT_FREQ_HZ / hz;
	if (divisor < 1u) divisor = 1u;
	if (divisor > 65535u) divisor = 65535u;

	/* cerrar la compuerta antes de reprogramar el divisor evita un clic y
	 * un tono espurio con el divisor anterior */
	ctl = inb(SPEAKER_CTL);
	outb(SPEAKER_CTL, (uint8_t)(ctl & 0xFC));

	outb(PIT_CMD, 0xB6);      /* canal 2, modo 3, binario (NO toca el canal 0) */
	outb(PIT_CH2, (uint8_t)(divisor & 0xFF));
	outb(PIT_CH2, (uint8_t)((divisor >> 8) & 0xFF));

	outb(SPEAKER_CTL, (uint8_t)((ctl & 0xFC) | 0x03));  /* compuerta + datos */
}

void speaker_off(void) {
	uint8_t ctl = inb(SPEAKER_CTL);
	outb(SPEAKER_CTL, (uint8_t)(ctl & 0xFC));
}

void speaker_beep(uint32_t hz, uint32_t ms) {
	if (hz == 0 || ms == 0) return;
	speaker_tone(hz);

	/* espera real: con PIT e interrupciones activas se duerme con hlt.
	 * En el arranque temprano (sin PIT) se usa una espera por sondeo del
	 * reloj del PIT; nunca se cuelga el sistema. */
	if (timer_hz() > 0 && interrupts_enabled()) {
		timer_sleep_ms(ms);
	} else {
		volatile uint32_t spins = ms * 3000u;
		while (spins--) __asm__ volatile ("pause");
	}
	speaker_off();
}
