/* drivers/mouse.c - raton PS/2 (controlador 8042, IRQ 12)
 *
 * Inicializacion real del dispositivo auxiliar:
 *   0xA8  habilita el puerto auxiliar
 *   0x20/0x60 lee y reescribe el byte de configuracion con IRQ12 y reloj
 *   0xF6  valores por defecto
 *   magia de Intellimouse (muestreo 200/100/80 + 0xF2) para detectar rueda
 *   0xF3/0xF4 fija el muestreo y habilita el envio de datos
 *
 * La ISR solo decodifica paquetes de 3 bytes (o 4 con rueda), se resincroniza
 * con el bit 3 del primer byte y empuja eventos a input.c. Si no hay raton,
 * mouse_init() termina sin romper nada y mouse_present() devuelve 0.
 */
#include <stdint.h>
#include "input.h"
#include "interrupts.h"
#include "io.h"

#define PS2_DATA    0x60
#define PS2_STATUS  0x64
#define PS2_CMD     0x64

#define PS2_STATUS_OUT_FULL 0x01   /* hay dato en el buffer de salida */
#define PS2_STATUS_IN_FULL  0x02   /* buffer de entrada lleno        */
#define PS2_STATUS_AUX      0x20   /* el dato viene del puerto aux   */

#define PS2_ACK  0xFA
#define PS2_RESEND 0xFE

#define MOUSE_MAX_TIMEOUT 100000

/* estado del dispositivo */
static volatile int mouse_ready = 0;     /* dispositivo detectado y activo */
static int mouse_wheel = 0;              /* 0 = sin rueda, 3 = IMPS/2, 4 = IMEX */
static uint8_t packet_size = 3;
static uint8_t packet[4];
static int packet_index = 0;
static uint8_t prev_buttons = 0;

/* ------------------------------------------------------------------ */
/* acceso de bajo nivel al controlador 8042                            */
/* ------------------------------------------------------------------ */

static int ps2_wait_write(void) {
	for (int i = 0; i < MOUSE_MAX_TIMEOUT; i++)
		if (!(inb(PS2_STATUS) & PS2_STATUS_IN_FULL)) return 1;
	return 0;
}

static int ps2_wait_read(void) {
	for (int i = 0; i < MOUSE_MAX_TIMEOUT; i++)
		if (inb(PS2_STATUS) & PS2_STATUS_OUT_FULL) return 1;
	return 0;
}

static int ps2_cmd(uint8_t cmd) {
	if (!ps2_wait_write()) return 0;
	outb(PS2_CMD, cmd);
	return 1;
}

/* envia un byte al dispositivo auxiliar (comando 0xD4) */
static int mouse_write(uint8_t data) {
	if (!ps2_cmd(0xD4)) return 0;
	if (!ps2_wait_write()) return 0;
	outb(PS2_DATA, data);
	return 1;
}

/* lee un byte cualquiera del buffer de salida (respuesta del controlador) */
static int ps2_read_byte(uint8_t *out) {
	if (!ps2_wait_read()) return 0;
	*out = inb(PS2_DATA);
	return 1;
}

/* lee un byte que provenga del dispositivo auxiliar (ACK o dato del raton);
 * los bytes del teclado que aparezcan por el camino se descartan. */
static int aux_read(uint8_t *out) {
	for (int i = 0; i < MOUSE_MAX_TIMEOUT; i++) {
		uint8_t status = inb(PS2_STATUS);
		if (status & PS2_STATUS_OUT_FULL) {
			uint8_t data = inb(PS2_DATA);
			if (status & PS2_STATUS_AUX) {
				*out = data;
				return 1;
			}
		}
	}
	return 0;
}

/* espera el ACK de un comando (tolera algun byte de datos previo) */
static int mouse_expect_ack(void) {
	for (int i = 0; i < 4; i++) {
		uint8_t b = 0;
		if (!aux_read(&b)) return 0;
		if (b == PS2_ACK) return 1;
		if (b == PS2_RESEND) return 0;
	}
	return 0;
}

/* envia un comando al raton y verifica su ACK */
static int mouse_cmd(uint8_t cmd) {
	if (!mouse_write(cmd)) return 0;
	return mouse_expect_ack();
}

/* descarta bytes pendientes del buffer de salida */
static void ps2_drain(void) {
	for (int i = 0; i < 64; i++) {
		if (!(inb(PS2_STATUS) & PS2_STATUS_OUT_FULL)) break;
		(void)inb(PS2_DATA);
	}
}

/* ------------------------------------------------------------------ */
/* decodificacion de paquetes en la ISR                                */
/* ------------------------------------------------------------------ */

static void mouse_callback(struct regs *r) {
	(void)r;

	uint8_t status = inb(PS2_STATUS);
	if (!(status & PS2_STATUS_OUT_FULL)) return;
	if (!(status & PS2_STATUS_AUX)) return;   /* dato del teclado: no tocar */

	uint8_t b = inb(PS2_DATA);
	if (!mouse_ready) return;   /* byte drenado y descartado */

	/* el primer byte de un paquete siempre tiene el bit 3 a 1; si no,
	 * estamos desalineados: se descarta hasta encontrar el inicio. */
	if (packet_index == 0 && !(b & 0x08)) return;

	packet[packet_index++] = b;
	if (packet_index < (int)packet_size) return;
	packet_index = 0;

	uint8_t flags = packet[0];

	/* bits 6/7: desbordamiento de X/Y; el movimiento no es fiable */
	if (flags & 0xC0) return;

	int dx = packet[1];
	int dy = packet[2];
	if (flags & 0x10) dx -= 256;   /* bit de signo de X */
	if (flags & 0x20) dy -= 256;   /* bit de signo de Y */

	int dz = 0;
	if (mouse_wheel == 3) {
		/* IMPS/2: el 4o byte es un entero con signo; en el protocolo PS/2
		 * el valor negativo corresponde a girar la rueda hacia arriba.
		 * Se invierte para que EVENT_MOUSE_WHEEL sea positivo = arriba. */
		dz = -(int)(int8_t)packet[3];
	} else if (mouse_wheel == 4) {
		/* IMEX: el bit 6 indica rueda horizontal; si no, la vertical va
		 * en los 4 bits bajos con signo. */
		if (!(packet[3] & 0x40)) {
			int v = packet[3] & 0x0F;
			if (v & 0x08) v -= 16;
			dz = -v;
		}
	}

	/* PS/2 usa Y creciente hacia arriba; la pantalla crece hacia abajo */
	int nx = input_mouse_x() + dx;
	int ny = input_mouse_y() - dy;

	if (dx != 0 || dy != 0)
		input_push_mouse(nx, ny, 0, 0, 0, 0);

	uint8_t buttons = (uint8_t)(flags & 0x07);   /* izquierdo, derecho, central */
	uint8_t changed = (uint8_t)(buttons ^ prev_buttons);

	if (changed & 0x01)
		input_push_mouse(nx, ny, MOUSE_BTN_LEFT, 0, (buttons & 0x01) ? 1 : 0, 0);
	if (changed & 0x02)
		input_push_mouse(nx, ny, MOUSE_BTN_RIGHT, 0, (buttons & 0x02) ? 1 : 0, 0);
	if (changed & 0x04)
		input_push_mouse(nx, ny, MOUSE_BTN_MIDDLE, 0, (buttons & 0x04) ? 1 : 0, 0);
	prev_buttons = buttons;

	if (dz != 0)
		input_push_mouse(nx, ny, 0, dz, 0, 1);
}

/* ------------------------------------------------------------------ */
/* inicializacion                                                      */
/* ------------------------------------------------------------------ */

/* Intenta activar el modo Intellimouse para tener rueda (4o byte). */
static void mouse_detect_wheel(void) {
	mouse_wheel = 0;
	packet_size = 3;

	/* secuencia magica de muestreo 200, 100, 80 */
	if (!mouse_cmd(0xF3)) return;
	if (!mouse_cmd(200)) return;
	if (!mouse_cmd(0xF3)) return;
	if (!mouse_cmd(100)) return;
	if (!mouse_cmd(0xF3)) return;
	if (!mouse_cmd(80)) return;

	/* pedir el id del dispositivo */
	uint8_t id = 0;
	if (!mouse_write(0xF2)) return;
	if (!mouse_expect_ack()) return;
	if (!aux_read(&id)) return;

	if (id == 0x03) {          /* Intellimouse (IMPS/2)  */
		mouse_wheel = 3;
		packet_size = 4;
	} else if (id == 0x04) {   /* Intellimouse Explorer (IMEX) */
		mouse_wheel = 4;
		packet_size = 4;
	} else {
		mouse_wheel = 0;       /* raton estandar de 3 bytes */
		packet_size = 3;
	}

	/* restaurar un muestreo razonable para el escritorio */
	if (mouse_cmd(0xF3)) (void)mouse_cmd(100);
}

void mouse_init(void) {
	mouse_ready = 0;
	mouse_wheel = 0;
	packet_size = 3;
	packet_index = 0;
	prev_buttons = 0;

	/* el manejador se instala siempre para poder drenar el puerto si algo
	 * llega; con mouse_ready == 0 simplemente descarta los bytes. */
	irq_install(12, mouse_callback);

	/* 1) habilitar el puerto auxiliar del 8042 */
	if (!ps2_cmd(0xA8)) return;

	/* 2) leer el byte de configuracion, habilitar IRQ12 y el reloj aux */
	uint8_t config = 0;
	if (!ps2_cmd(0x20)) return;
	if (!ps2_read_byte(&config)) return;
	config |= 0x02;      /* IRQ 12 habilitada            */
	config &= (uint8_t)~0x20; /* bit 5 = 1 deshabilita reloj aux */
	if (!ps2_cmd(0x60)) return;
	if (!ps2_wait_write()) return;
	outb(PS2_DATA, config);

	ps2_drain();

	/* 3) deshabilitar reporte por si el BIOS lo dejo activo y resetear */
	(void)mouse_cmd(0xF5);
	ps2_drain();
	if (!mouse_cmd(0xF6)) return;

	/* 4) intentar habilitar la rueda */
	mouse_detect_wheel();

	/* 5) habilitar el envio de datos */
	if (!mouse_cmd(0xF4)) return;

	mouse_ready = 1;
	ps2_drain();
}

int mouse_present(void) {
	return mouse_ready;
}
