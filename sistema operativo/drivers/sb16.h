/* drivers/sb16.h - driver Sound Blaster 16 (DSP + DMA 8237, PCM 8 bits mono)
 *
 * Reproductor PCM NO BLOQUEANTE: sb16_play() programa el DSP y el DMA y
 * retorna de inmediato. El fin del bloque se detecta de dos formas:
 *   1. por la IRQ 5 del SB16 (fin de transferencia DMA; el handler solo lee
 *      el puerto de estado base+0x0E, que es el acknowledge 8-bit del DSP, y
 *      marca la bandera de fin);
 *   2. por tiempo (timer_ticks) como red de seguridad, por si la IRQ no
 *      llegara (por ejemplo si la VM tiene el SB16 en otra IRQ distinta).
 * Asi el sistema nunca se queda con el canal ocupado aunque la IRQ falle.
 *
 * El buffer debe estar por debajo de 16 MiB y no cruzar un limite de 64 KiB
 * (limitaciones del DMA 8237 de 8 bits); sb16_play() lo valida y devuelve 0
 * si el bloque no es utilizable. La capa audio/audio.c usa una bounce buffer
 * alineada a 64 KiB para cumplir siempre ese contrato.
 *
 * Hardware de referencia: SB16 a 0x220, IRQ 5, DMA 8-bit 1, DMA 16-bit 5
 * (valores por defecto de QEMU y del ajuste "SoundBlaster 16" de VirtualBox).
 */
#ifndef SEREOS_SB16_H
#define SEREOS_SB16_H
#include <stdint.h>

#define SB16_MAX_BUFFER 32768u   /* tamano maximo de bloque reproducible */

/* recursos por defecto del SB16 (QEMU `-device sb16` y VirtualBox SB16) */
#define SB16_IRQ    5
#define SB16_DMA    1            /* canal DMA 8 bits  */
#define SB16_DMA16  5            /* canal DMA 16 bits */

/* autodeteccion de 0x220 a 0x280 (paso 0x10) con reset del DSP. Devuelve 1
 * si hay SB16, 0 si no. Idempotente y tolerante a fallos: nunca cuelga ni
 * rompe el sistema (todos los sondeos tienen timeout). */
int      sb16_init(void);
int      sb16_present(void);

/* version del DSP (por ejemplo 0x0405 = 4.5) y puerto base detectado */
uint16_t sb16_version(void);
uint16_t sb16_base(void);

/* IRQ usada por el driver y numero de transferencias terminadas por IRQ
 * (diagnostico: si crece, la IRQ 5 esta realmente conectada). */
int      sb16_irq(void);
uint32_t sb16_irq_count(void);

/* reproduce un bloque PCM 8 bits sin signo mono. No bloquea.
 * rate: 4000..45000 Hz (se programa el divisor mas cercano del DSP).
 * Devuelve 1 si arranco, 0 si no hay SB16, ya habia algo sonando o el
 * buffer no cumple las restricciones del DMA. */
int      sb16_play(const uint8_t *data, uint32_t len, uint32_t rate);

/* 1 mientras el bloque programado sigue reproduciendose (por IRQ o tiempo) */
int      sb16_busy(void);

/* detiene el DMA y silencia el altavoz del SB16 */
void     sb16_stop(void);

/* frecuencia real que el DSP programo para la frecuencia pedida */
uint32_t sb16_actual_rate(uint32_t rate);

/* tasas de muestreo utiles para la capa de audio */
uint32_t sb16_sample_rate(void);

#endif /* SEREOS_SB16_H */
