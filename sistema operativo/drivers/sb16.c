/* drivers/sb16.c - Sound Blaster 16: DSP + DMA 8237 canal 1 (8 bits mono)
 *
 * Cadena de reproduccion:
 *   1. reset del DSP (escribir 1 y luego 0 en base+6, esperar 0xAA en base+0xA)
 *   2. leer version con 0xE1
 *   3. mixer: volumen maestro y de voz al maximo (registros de ATENUACION:
 *      0x00 = 0 dB = volumen maximo, 0xFF = -62 dB = silencio). Tambien se
 *      programan los registros 0x30..0x33, que son los que aplican QEMU,
 *      VirtualBox y las SB16 reales para el volumen maestro y de la voz.
 *   4. activar altavoz con 0xD1
 *   5. programar la frecuencia de salida: 0x41 + frecuencia de 16 bits
 *      (byte alto y luego bajo) en SB16; 0x40 + constante de tiempo en SB Pro
 *   6. programar el 8237: enmascarar canal 1, flip-flop, modo single-cycle
 *      incrementando en memoria (0x49: single, incremento, READ = memoria ->
 *      dispositivo; 0x45 seria WRITE = dispositivo -> memoria y dejaria el
 *      buffer sin tocar / con basura en hardware real), direccion, pagina y
 *      contador
 *   7. DSP 0x14 (salida 8-bit single-cycle DMA) + longitud-1
 *
 * Fin de transferencia: la IRQ 5 la genera el propio SB16 al terminar el
 * bloque. El handler (irq_install(5, ...)) solo lee base+0x0E, que es el
 * acknowledge de la IRQ de 8 bits del DSP, marca la bandera de fin y cuenta
 * la interrupcion; el EOI al PIC lo hace interrupt_handler() en kernel/idt.c.
 * Como red de seguridad sb16_busy() tambien libera el canal por tiempo
 * (duracion del bloque + margen), de modo que una IRQ mal configurada nunca
 * bloquea el audio para siempre.
 *
 * Restricciones del DMA de 8 bits: el buffer fisico (identidad en SereOS)
 * debe estar por debajo de 16 MiB y no puede cruzar un limite de 64 KiB.
 * La capa audio/audio.c usa una bounce buffer de 64 KiB alineada y de 32 KiB
 * para cumplir siempre ese contrato. La plataforma nativa del juego
 * (Pac-man SereOS/src/platform/sereos/platform_sereos.c) hace lo mismo con su
 * propia bounce buffer `pcm_bounce` antes de llamar a sb16_play(): los chunks
 * de assets viven en .rodata sin alineacion y algunos cruzaban los 64 KiB.
 */
#include "sb16.h"
#include "timer.h"
#include "io.h"
#include "interrupts.h"

/* Bases de E/S que se sondean (SB16 tipico 0x220; el rango 0x220..0x280 con
 * paso 0x10 cubre las direcciones que permiten los jumpers/PnP de la tarjeta
 * y las que emulan QEMU/VirtualBox/DOSBox). */
#define SB16_BASE_FIRST 0x220
#define SB16_BASE_LAST  0x280
#define SB16_BASE_STEP  0x10

#define DSP_RESET        0x06   /* base + 6  : reset; lectura 0xFF          */
#define DSP_READ_DATA    0x0A   /* base + 10 : datos de lectura            */
#define DSP_WRITE_PORT   0x0C   /* base + 12 : escritura cmd/datos; lectura
                                 *             estado de escritura (bit 7
                                 *             = 1 ocupado)                */
#define DSP_READ_STATUS  0x0E   /* base + 14 : estado de lectura (bit 7 =
                                 *             hay dato); leer ack IRQ 8-bit */
#define MIXER_INDEX      0x04   /* base + 4  */
#define MIXER_DATA       0x05   /* base + 5  */

#define DSP_CMD_SET_RATE     0x41  /* tasa de salida 8-bit */
#define DSP_CMD_SPEAKER_ON   0xD1
#define DSP_CMD_SPEAKER_OFF  0xD3
#define DSP_CMD_HALT_DMA     0xD0
#define DSP_CMD_PLAY_8BIT_DMA 0x14 /* single-cycle 8-bit output */
#define DSP_CMD_GET_VERSION  0xE1

/* Modo del 8237 para reproducir por el canal 1:
 *   0x49 = 0100 1001b -> single (bits 7-6 = 01), incremento (bit 5 = 0),
 *   READ = memoria -> dispositivo (bits 3-2 = 10) y canal 1 (bits 1-0 = 01).
 *   El modo WRITE (0x45) es el de captura (dispositivo -> memoria). */
#define DMA_MODE_SINGLE_READ_CH1 0x49

/* marginal de seguridad del fin por tiempo cuando la IRQ no llega (ms) */
#define SB16_TIME_SLACK_MS 100u

static uint16_t base_port;
static uint16_t dsp_version;
static uint8_t  dsp_major;
static uint32_t last_rate;
static int      present;
static int      playing;
static volatile int      dma_done;      /* lo pone a 1 el handler de IRQ5 */
static volatile uint32_t irq_completions;
static uint32_t start_tick;
static uint32_t duration_ticks;
static uint32_t total_plays;

static uint32_t dsp_read_status(void) { return inb((uint16_t)(base_port + DSP_READ_STATUS)); }

/* espera a que el DSP pueda aceptar un comando (base+0x0C, bit 7 = ocupado).
 * 0 = timeout. */
static int dsp_write(uint8_t value) {
	uint32_t guard = 200000u;
	while ((inb((uint16_t)(base_port + DSP_WRITE_PORT)) & 0x80) && guard--) { }
	if (guard == 0) return 0;
	outb((uint16_t)(base_port + DSP_WRITE_PORT), value);
	return 1;
}

/* espera a que el DSP tenga un byte de lectura (base+0x0E, bit 7). */
static int dsp_read(uint8_t *out) {
	uint32_t guard = 200000u;
	while (!(dsp_read_status() & 0x80) && guard--) { }
	if (guard == 0 || !out) return 0;
	*out = inb((uint16_t)(base_port + DSP_READ_DATA));
	return 1;
}

/* acknowledge de la IRQ de 8 bits del SB16: leer el puerto de estado.
 * (Es tambien el ack de fin de DMA; no hace falta leer base+0x0A.) */
static void dsp_ack_irq(void) {
	if (!base_port) return;
	(void)inb((uint16_t)(base_port + DSP_READ_STATUS));
}

static void mixer_write(uint8_t reg, uint8_t value) {
	outb((uint16_t)(base_port + MIXER_INDEX), reg);
	io_wait();
	outb((uint16_t)(base_port + MIXER_DATA), value);
	io_wait();
}

/* volumen al maximo: los registros del mixer son atenuacion (0x00 = 0 dB,
 * 0xFF = -62 dB / silencio). Se programan las dos vistas del SB16:
 *   0x04/0x22  voz/maestro (formato SB16)
 *   0x30..0x33 maestro L/R y voz L/R (formato SB Pro que aplican las VM) */
static void mixer_max_volume(void) {
	mixer_write(0x22, 0x00);   /* master volume            */
	mixer_write(0x04, 0x00);   /* voice volume             */
	mixer_write(0x30, 0x00);   /* master left              */
	mixer_write(0x31, 0x00);   /* master right             */
	mixer_write(0x32, 0x00);   /* voice/pcm out left       */
	mixer_write(0x33, 0x00);   /* voice/pcm out right      */
}

/* reset del DSP en el puerto base actual; 1 si responde 0xAA */
static int dsp_reset(void) {
	uint8_t ack = 0;
	uint32_t guard;

	outb((uint16_t)(base_port + DSP_RESET), 0x01);
	for (guard = 0; guard < 200; guard++) io_wait();   /* >= 3 us */
	outb((uint16_t)(base_port + DSP_RESET), 0x00);

	/* el DSP tarda ~100 us en responder; se sondea el puerto de estado */
	guard = 200000u;
	while (!(dsp_read_status() & 0x80) && guard--) { }
	if (guard == 0) return 0;
	ack = inb((uint16_t)(base_port + DSP_READ_DATA));
	return ack == 0xAA;
}

/* programa una frecuencia de salida 8-bit. En un SB16 (DSP >= 4) el comando
 * 0x41 lleva la frecuencia en 16 bits (hi, lo); en un SB Pro (DSP 3) se usa
 * el comando 0x40 con la constante de tiempo. */
static uint32_t set_sample_rate(uint32_t rate) {
	if (rate < 5000u) rate = 5000u;
	if (rate > 45000u) rate = 45000u;

	if (dsp_major >= 4) {
		/* el DSP espera primero el byte alto y despues el bajo */
		if (!dsp_write(DSP_CMD_SET_RATE)) return 0;
		if (!dsp_write((uint8_t)((rate >> 8) & 0xFF))) return 0;
		if (!dsp_write((uint8_t)(rate & 0xFF))) return 0;
		return rate;
	}

	{
		uint32_t tc = 256u - (1000000u / rate);
		if (tc > 255u) tc = 255u;
		if (!dsp_write(0x40)) return 0;   /* SB Pro: constante de tiempo */
		if (!dsp_write((uint8_t)tc)) return 0;
		return 1000000u / (256u - tc);
	}
}

static void dma_mask_channel1(int masked) {
	outb(0x0A, masked ? 0x05 : 0x01);   /* bit 1 del registro de mascara */
}

/* enmascarar el canal mientras no hay transferencia: evita DREQs fantasma */
static void dma_idle(void) {
	dma_mask_channel1(1);
}

/* programa el 8237 para leer len bytes desde data (memoria -> DSP) */
static int dma_program(const uint8_t *data, uint32_t len) {
	uint32_t addr = (uint32_t)(uintptr_t)data;
	uint32_t count = len - 1u;

	if (addr + len > 0x01000000u) return 0;              /* DMA de 8 bits: < 16 MiB */
	if (((addr & 0xFFFFu) + len) > 0x10000u) return 0;   /* no puede cruzar 64 KiB */

	dma_mask_channel1(1);      /* enmascarar canal 1 durante la programacion */
	outb(0x0C, 0x00);          /* limpiar flip-flop de direccion/contador */
	outb(0x0B, DMA_MODE_SINGLE_READ_CH1);
	outb(0x02, (uint8_t)(addr & 0xFF));          /* direccion bajo */
	outb(0x02, (uint8_t)((addr >> 8) & 0xFF));   /* direccion alto */
	outb(0x83, (uint8_t)((addr >> 16) & 0xFF));  /* pagina del canal 1 */
	outb(0x03, (uint8_t)(count & 0xFF));         /* contador bajo */
	outb(0x03, (uint8_t)((count >> 8) & 0xFF));  /* contador alto */
	dma_mask_channel1(0);      /* desenmascarar: el DSP empieza al pedir DREQ */
	return 1;
}

/* handler de la IRQ 5: solo acknowledge del DSP + bandera de fin. El EOI al
 * PIC lo envia interrupt_handler() (kernel/idt.c) al volver. */
static void sb16_irq_handler(struct regs *r) {
	(void)r;
	dsp_ack_irq();
	dma_done = 1;
	irq_completions++;
}

/* El PIC remapeado deja las 16 IRQ desenmascaradas (mascara 0x00), pero se
 * deja explicito el desenmascarado de la IRQ del SB16 por si en el futuro se
 * enmascara alguna. IRQ < 8 -> PIC maestro (puerto 0x21). */
static void pic_unmask_irq(int irq) {
	uint8_t mask;
	if (irq < 0 || irq > 15) return;
	if (irq < 8) {
		mask = inb(0x21);
		outb(0x21, (uint8_t)(mask & ~(1u << irq)));
	} else {
		mask = inb(0xA1);
		outb(0xA1, (uint8_t)(mask & ~(1u << (irq - 8))));
	}
}

static int probe_base(uint16_t base) {
	uint8_t major = 0, minor = 0;

	base_port = base;
	if (!dsp_reset()) return 0;

	if (!dsp_write(DSP_CMD_GET_VERSION)) return 0;
	if (!dsp_read(&major) || !dsp_read(&minor)) return 0;
	if (major == 0 || major == 0xFF) return 0;

	dsp_version = (uint16_t)(((uint16_t)major << 8) | minor);
	dsp_major = major;
	return 1;
}

int sb16_init(void) {
	uint16_t base;

	if (present) return 1;
	present = 0;
	playing = 0;
	total_plays = 0;
	dsp_version = 0;
	dsp_major = 0;
	last_rate = 0;
	base_port = 0;
	dma_done = 0;
	irq_completions = 0;

	for (base = SB16_BASE_FIRST; base <= SB16_BASE_LAST; base = (uint16_t)(base + SB16_BASE_STEP)) {
		if (!probe_base(base)) continue;

		mixer_max_volume();

		/* altavoz apagado y DMA enmascarado hasta el primer play */
		dsp_write(DSP_CMD_SPEAKER_OFF);
		dsp_write(DSP_CMD_HALT_DMA);
		dma_idle();

		/* IRQ 5: handler en la IDT + PIC desenmascarado. La IRQ solo se usa
		 * para saber cuando termina el bloque; el audio no depende de ella. */
		present = 1;
		irq_install(SB16_IRQ, sb16_irq_handler);
		pic_unmask_irq(SB16_IRQ);
		return 1;
	}

	base_port = 0;
	dsp_major = 0;
	return 0;
}

int sb16_present(void) { return present; }

uint16_t sb16_version(void) { return dsp_version; }

uint16_t sb16_base(void) { return base_port; }

int sb16_irq(void) { return SB16_IRQ; }

uint32_t sb16_irq_count(void) { return irq_completions; }

uint32_t sb16_actual_rate(uint32_t rate) {
	if (rate < 5000u) rate = 5000u;
	if (rate > 45000u) rate = 45000u;
	if (dsp_major >= 4) return rate;
	{
		uint32_t tc = 256u - (1000000u / rate);
		if (tc > 255u) tc = 255u;
		return 1000000u / (256u - tc);
	}
}

uint32_t sb16_sample_rate(void) { return last_rate; }

int sb16_play(const uint8_t *data, uint32_t len, uint32_t rate) {
	uint32_t actual, ms, hz, ticks, slack;

	if (!present || !data || len == 0 || len > SB16_MAX_BUFFER) return 0;
	if (sb16_busy()) return 0;
	if (!dma_program(data, len)) return 0;

	actual = set_sample_rate(rate);
	if (actual == 0) {
		dma_idle();
		return 0;
	}
	last_rate = actual;

	if (!dsp_write(DSP_CMD_SPEAKER_ON)) {
		dma_idle();
		return 0;
	}
	dma_done = 0;
	if (!dsp_write(DSP_CMD_PLAY_8BIT_DMA)) {
		dsp_write(DSP_CMD_SPEAKER_OFF);
		dma_idle();
		return 0;
	}
	if (!dsp_write((uint8_t)((len - 1u) & 0xFF)) ||
	    !dsp_write((uint8_t)(((len - 1u) >> 8) & 0xFF))) {
		dsp_write(DSP_CMD_SPEAKER_OFF);
		dma_idle();
		return 0;
	}

	/* duracion real segun la frecuencia que el DSP acepto; el margen extra
	 * es solo la red de seguridad si la IRQ 5 no llegara */
	ms = (len * 1000u) / actual;   /* len <= 32 KiB: no desborda 32 bits */
	hz = timer_hz();
	if (hz == 0) hz = 100u;
	ticks = (ms * hz + 999u) / 1000u;
	slack = (SB16_TIME_SLACK_MS * hz + 999u) / 1000u;
	if (ticks == 0) ticks = 1;

	start_tick = timer_ticks();
	duration_ticks = ticks + slack;
	playing = 1;
	total_plays++;
	return 1;
}

int sb16_busy(void) {
	uint32_t hz;

	if (!playing) return 0;
	if (dma_done) {
		/* el SB16 ya genero la IRQ de fin de bloque */
		playing = 0;
		dma_done = 0;
		dma_idle();
		return 0;
	}
	hz = timer_hz();
	if (hz == 0) {
		/* sin PIT no hay forma de medir la duracion: se libera el canal */
		playing = 0;
		dsp_ack_irq();
		dma_idle();
		return 0;
	}
	if ((uint32_t)(timer_ticks() - start_tick) >= duration_ticks) {
		playing = 0;
		/* el single-cycle ya termino o la IRQ no llego: se libera igual */
		dsp_ack_irq();
		dma_idle();
		return 0;
	}
	return 1;
}

void sb16_stop(void) {
	if (!present) return;
	dma_idle();
	dsp_write(DSP_CMD_HALT_DMA);       /* 0xD0: detener DMA de 8 bits */
	dsp_write(DSP_CMD_SPEAKER_OFF);    /* 0xD3: silenciar altavoz */
	dsp_ack_irq();
	playing = 0;
	dma_done = 0;
	duration_ticks = 0;
}
