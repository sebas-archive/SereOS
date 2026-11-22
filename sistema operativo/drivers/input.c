/* drivers/input.c - sistema centralizado de entrada de SereOS
 *
 * Cola circular de eventos alimentada desde las ISR del teclado (IRQ 1) y
 * del raton (IRQ 12). El escritorio, el juego y la shell de respaldo la
 * consumen con input_poll() sin bloquearse entre si ni perder eventos.
 *
 * Concurrencia: el productor (ISR) escribe SOLO q_head y los consumidores
 * mueven SOLO q_tail. El consumidor deshabilita interrupciones el tiempo
 * minimo necesario para leer/copiar el evento y avanzar q_tail; nunca se
 * mantiene cli() durante trabajo largo. Este archivo no hace E/S ni esperas.
 */
#include <stdint.h>
#include "input.h"
#include "timer.h"

/* ------------------------------------------------------------------ */
/* estado interno                                                      */
/* ------------------------------------------------------------------ */

static event_t queue[INPUT_QUEUE_SIZE];
static volatile uint32_t q_head = 0;     /* indice de escritura (ISR)   */
static volatile uint32_t q_tail = 0;     /* indice de lectura (hilos)   */
static volatile uint32_t q_dropped = 0;  /* eventos perdidos por cola llena */

/* estado fisico de teclas para input_key_down() y los modificadores */
static volatile uint8_t key_state[KEY_COUNT];

/* cursor absoluto del raton, botones y limites de pantalla */
static volatile int32_t mouse_pos_x = 512;
static volatile int32_t mouse_pos_y = 384;
static volatile uint8_t mouse_buttons = 0;
static volatile int32_t mouse_bound_w = 1024;
static volatile int32_t mouse_bound_h = 768;

/* ------------------------------------------------------------------ */
/* utilidades de sincronizacion (cli/restauracion de EFLAGS)           */
/* ------------------------------------------------------------------ */

/* Guarda EFLAGS y deshabilita interrupciones. Devuelve las banderas
 * previas para restaurarlas exactamente con irq_restore(). */
static inline uint32_t irq_save_flags(void) {
	uint32_t flags;
	__asm__ volatile ("pushfl\n\tpopl %0\n\tcli" : "=r"(flags) : : "memory");
	return flags;
}

static inline void irq_restore_flags(uint32_t flags) {
	__asm__ volatile ("pushl %0\n\tpopfl" : : "r"(flags) : "memory", "cc");
}

/* ------------------------------------------------------------------ */
/* inicializacion                                                      */
/* ------------------------------------------------------------------ */

void input_init(void) {
	uint32_t flags = irq_save_flags();
	q_head = 0;
	q_tail = 0;
	q_dropped = 0;
	for (uint32_t i = 0; i < (uint32_t)KEY_COUNT; i++) key_state[i] = 0;
	mouse_buttons = 0;
	mouse_pos_x = mouse_bound_w / 2;
	mouse_pos_y = mouse_bound_h / 2;
	irq_restore_flags(flags);
}

/* ------------------------------------------------------------------ */
/* cola de eventos                                                     */
/* ------------------------------------------------------------------ */

void input_push_event(const event_t *ev) {
	if (!ev) return;
	uint32_t flags = irq_save_flags();
	uint32_t next = (q_head + 1u) % INPUT_QUEUE_SIZE;
	if (next == q_tail) {
		/* cola llena: se descarta el evento mas nuevo y se cuenta */
		q_dropped++;
		irq_restore_flags(flags);
		return;
	}
	queue[q_head] = *ev;
	queue[q_head].tick = timer_ticks();
	q_head = next;
	irq_restore_flags(flags);
}

int input_poll(event_t *out) {
	if (!out) return 0;
	uint32_t flags = irq_save_flags();
	if (q_tail == q_head) {
		irq_restore_flags(flags);
		return 0;
	}
	*out = queue[q_tail];
	q_tail = (q_tail + 1u) % INPUT_QUEUE_SIZE;
	irq_restore_flags(flags);
	return 1;
}

int input_has_event(void) {
	return q_head != q_tail;
}

void input_flush(void) {
	uint32_t flags = irq_save_flags();
	q_tail = q_head;
	irq_restore_flags(flags);
}

/* ------------------------------------------------------------------ */
/* productores: teclado                                                */
/* ------------------------------------------------------------------ */

void input_push_key(uint16_t key, int pressed, char ch) {
	if (key < (uint16_t)KEY_COUNT) key_state[key] = pressed ? 1u : 0u;

	event_t ev = { 0 };
	ev.type = (uint8_t)(pressed ? EVENT_KEY_DOWN : EVENT_KEY_UP);
	ev.pressed = pressed ? 1u : 0u;
	ev.key = key;
	ev.ch = ch;
	input_push_event(&ev);
}

int input_key_down(uint16_t key) {
	if (key >= (uint16_t)KEY_COUNT) return 0;
	return key_state[key] != 0;
}

int input_shift_down(void) {
	return (key_state[KEY_LEFTSHIFT] != 0) || (key_state[KEY_RIGHTSHIFT] != 0);
}

int input_ctrl_down(void) {
	return (key_state[KEY_LEFTCTRL] != 0) || (key_state[KEY_RIGHTCTRL] != 0);
}

int input_alt_down(void) {
	return (key_state[KEY_LEFTALT] != 0) || (key_state[KEY_RIGHTALT] != 0);
}

/* ------------------------------------------------------------------ */
/* productores: raton                                                  */
/* ------------------------------------------------------------------ */

void input_set_mouse_bounds(int width, int height) {
	if (width < 1) width = 1;
	if (height < 1) height = 1;

	uint32_t flags = irq_save_flags();
	mouse_bound_w = width;
	mouse_bound_h = height;
	if (mouse_pos_x < 0) mouse_pos_x = 0;
	if (mouse_pos_y < 0) mouse_pos_y = 0;
	if (mouse_pos_x > width - 1) mouse_pos_x = width - 1;
	if (mouse_pos_y > height - 1) mouse_pos_y = height - 1;
	irq_restore_flags(flags);
}

int input_mouse_x(void) { return (int)mouse_pos_x; }
int input_mouse_y(void) { return (int)mouse_pos_y; }
int input_mouse_buttons(void) { return (int)mouse_buttons; }

/* Empuja un evento de raton ya decodificado por el driver PS/2.
 *   - x, y: posicion absoluta que tendra el cursor (se limita a bounds).
 *   - button: mascara MOUSE_BTN_* (0 si no aplica).
 *   - wheel: delta de rueda (positivo = hacia arriba).
 *   - pressed: 1 pulsacion / 0 liberacion (solo si button != 0).
 *   - is_wheel: 1 para generar EVENT_MOUSE_WHEEL.
 * Con button == 0 e is_wheel == 0 se genera un EVENT_MOUSE_MOVE. */
void input_push_mouse(int x, int y, int button, int wheel, int pressed, int is_wheel) {
	/* limites de pantalla, siempre con clamp */
	if (x < 0) x = 0;
	if (y < 0) y = 0;
	if (x > mouse_bound_w - 1) x = mouse_bound_w - 1;
	if (y > mouse_bound_h - 1) y = mouse_bound_h - 1;

	event_t ev = { 0 };

	uint32_t flags = irq_save_flags();
	mouse_pos_x = x;
	mouse_pos_y = y;

	if (is_wheel) {
		ev.type = EVENT_MOUSE_WHEEL;
		ev.wheel = (int8_t)wheel;
	} else if (button) {
		if (pressed) {
			mouse_buttons = (uint8_t)(mouse_buttons | (uint8_t)button);
			ev.type = EVENT_MOUSE_DOWN;
			ev.pressed = 1;
		} else {
			mouse_buttons = (uint8_t)(mouse_buttons & (uint8_t)~button);
			ev.type = EVENT_MOUSE_UP;
			ev.pressed = 0;
		}
		ev.button = (uint8_t)button;
	} else {
		ev.type = EVENT_MOUSE_MOVE;
	}

	ev.mouse_x = (int16_t)x;
	ev.mouse_y = (int16_t)y;
	ev.button = ev.button ? ev.button : (uint8_t)(mouse_buttons & 0x07);
	irq_restore_flags(flags);

	input_push_event(&ev);
}
