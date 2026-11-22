/* drivers/keyboard.c - teclado PS/2 (IRQ 1, scancode set 1, distribucion US)
 *
 * La ISR solo decodifica scancodes, mantiene el estado de los modificadores
 * y empuja eventos a la cola central de input.c. No imprime nada ni hace
 * logica pesada: el trabajo de verdad lo hacen el escritorio y el juego.
 *
 * Se conserva ademas un pequeno buffer de caracteres ASCII para que la
 * consola VGA de respaldo (shell_run_text) pueda leer con keyboard_getchar().
 */
#include <stdint.h>
#include "input.h"
#include "interrupts.h"
#include "io.h"

/* ------------------------------------------------------------------ */
/* tablas de traduccion scancode set 1 -> keycode_t + ASCII (US)       */
/* ------------------------------------------------------------------ */

typedef struct {
	uint8_t key;   /* keycode_t; 0 = tecla no soportada (KEY_NONE) */
	char    lo;    /* caracter sin Shift (0 si no aplica)           */
	char    hi;    /* caracter con Shift                            */
} keymap_entry_t;

/* scancodes normales (make) 0x00..0x7F */
static const keymap_entry_t keymap[128] = {
	[0x01] = { KEY_ESC,        27,   27   },
	[0x02] = { KEY_1,         '1',  '!'   },
	[0x03] = { KEY_2,         '2',  '@'   },
	[0x04] = { KEY_3,         '3',  '#'   },
	[0x05] = { KEY_4,         '4',  '$'   },
	[0x06] = { KEY_5,         '5',  '%'   },
	[0x07] = { KEY_6,         '6',  '^'   },
	[0x08] = { KEY_7,         '7',  '&'   },
	[0x09] = { KEY_8,         '8',  '*'   },
	[0x0A] = { KEY_9,         '9',  '('   },
	[0x0B] = { KEY_0,         '0',  ')'   },
	[0x0C] = { KEY_MINUS,     '-',  '_'   },
	[0x0D] = { KEY_EQUAL,     '=',  '+'   },
	[0x0E] = { KEY_BACKSPACE, '\b', '\b'  },
	[0x0F] = { KEY_TAB,       '\t', '\t'  },
	[0x10] = { KEY_Q,         'q',  'Q'   },
	[0x11] = { KEY_W,         'w',  'W'   },
	[0x12] = { KEY_E,         'e',  'E'   },
	[0x13] = { KEY_R,         'r',  'R'   },
	[0x14] = { KEY_T,         't',  'T'   },
	[0x15] = { KEY_Y,         'y',  'Y'   },
	[0x16] = { KEY_U,         'u',  'U'   },
	[0x17] = { KEY_I,         'i',  'I'   },
	[0x18] = { KEY_O,         'o',  'O'   },
	[0x19] = { KEY_P,         'p',  'P'   },
	[0x1A] = { KEY_LEFTBRACE, '[',  '{'   },
	[0x1B] = { KEY_RIGHTBRACE,']',  '}'   },
	[0x1C] = { KEY_ENTER,     '\n', '\n'  },
	[0x1D] = { KEY_LEFTCTRL,  0,    0     },
	[0x1E] = { KEY_A,         'a',  'A'   },
	[0x1F] = { KEY_S,         's',  'S'   },
	[0x20] = { KEY_D,         'd',  'D'   },
	[0x21] = { KEY_F,         'f',  'F'   },
	[0x22] = { KEY_G,         'g',  'G'   },
	[0x23] = { KEY_H,         'h',  'H'   },
	[0x24] = { KEY_J,         'j',  'J'   },
	[0x25] = { KEY_K,         'k',  'K'   },
	[0x26] = { KEY_L,         'l',  'L'   },
	[0x27] = { KEY_SEMICOLON, ';',  ':'   },
	[0x28] = { KEY_APOSTROPHE,'\'', '"'   },
	[0x29] = { KEY_GRAVE,     '`',  '~'   },
	[0x2A] = { KEY_LEFTSHIFT, 0,    0     },
	[0x2B] = { KEY_BACKSLASH, '\\', '|'   },
	[0x2C] = { KEY_Z,         'z',  'Z'   },
	[0x2D] = { KEY_X,         'x',  'X'   },
	[0x2E] = { KEY_C,         'c',  'C'   },
	[0x2F] = { KEY_V,         'v',  'V'   },
	[0x30] = { KEY_B,         'b',  'B'   },
	[0x31] = { KEY_N,         'n',  'N'   },
	[0x32] = { KEY_M,         'm',  'M'   },
	[0x33] = { KEY_COMMA,     ',',  '<'   },
	[0x34] = { KEY_DOT,       '.',  '>'   },
	[0x35] = { KEY_SLASH,     '/',  '?'   },
	[0x36] = { KEY_RIGHTSHIFT,0,    0     },
	[0x38] = { KEY_LEFTALT,   0,    0     },
	[0x39] = { KEY_SPACE,     ' ',  ' '   },
	[0x3A] = { KEY_CAPSLOCK,  0,    0     },
	[0x3B] = { KEY_F1,        0,    0     },
	[0x3C] = { KEY_F2,        0,    0     },
	[0x3D] = { KEY_F3,        0,    0     },
	[0x3E] = { KEY_F4,        0,    0     },
	[0x3F] = { KEY_F5,        0,    0     },
	[0x40] = { KEY_F6,        0,    0     },
	[0x41] = { KEY_F7,        0,    0     },
	[0x42] = { KEY_F8,        0,    0     },
	[0x43] = { KEY_F9,        0,    0     },
	[0x44] = { KEY_F10,       0,    0     },
	[0x57] = { KEY_F11,       0,    0     },
	[0x58] = { KEY_F12,       0,    0     },
};

/* scancodes prefijados por E0 (teclas extendidas). La mayoria no produce
 * caracter ASCII; los keycode_t permiten al juego/escritorio usarlas. */
static const keymap_entry_t keymap_e0[128] = {
	[0x1C] = { KEY_ENTER,      '\n', '\n' },
	[0x1D] = { KEY_RIGHTCTRL,  0,    0    },
	[0x35] = { KEY_SLASH,      '/',  '/'  },
	[0x38] = { KEY_RIGHTALT,   0,    0    },
	[0x47] = { KEY_HOME,       0,    0    },
	[0x48] = { KEY_UP,         0,    0    },
	[0x49] = { KEY_PAGEUP,     0,    0    },
	[0x4B] = { KEY_LEFT,       0,    0    },
	[0x4D] = { KEY_RIGHT,      0,    0    },
	[0x4F] = { KEY_END,        0,    0    },
	[0x50] = { KEY_DOWN,       0,    0    },
	[0x51] = { KEY_PAGEDOWN,   0,    0    },
	[0x52] = { KEY_INSERT,     0,    0    },
	[0x53] = { KEY_DELETE,     0,    0    },
};

/* ------------------------------------------------------------------ */
/* estado del teclado                                                  */
/* ------------------------------------------------------------------ */

static volatile uint8_t shift_left = 0, shift_right = 0;
static volatile uint8_t ctrl_left = 0, ctrl_right = 0;
static volatile uint8_t alt_left = 0, alt_right = 0;
static volatile uint8_t caps_lock = 0;
static volatile uint8_t caps_down = 0;  /* evita realternar con la repeticion */
static volatile uint8_t extended = 0;   /* el siguiente scancode viene tras E0 */
static volatile uint8_t pause_skip = 0; /* bytes restantes de la secuencia E1 (Pause) */
static volatile int kb_present = 0;     /* teclado PS/2 detectado por la sonda */

/* buffer ASCII para la consola de texto de respaldo */
#define KB_BUFFER 128
static volatile char kb_buffer[KB_BUFFER];
static volatile uint32_t kb_head = 0, kb_tail = 0;

static void kb_push_char(char c) {
	uint32_t next = (kb_head + 1u) % KB_BUFFER;
	if (next != kb_tail) {
		kb_buffer[kb_head] = c;
		kb_head = next;
	}
}

/* Decodifica una tecla (make o break) ya traducida a keycode/ASCII. */
static void keyboard_handle_key(const keymap_entry_t *entry, int pressed) {
	uint8_t key = entry->key;
	char ch = 0;

	if (key == KEY_NONE) return;

	if (pressed) {
		/* modificadores: el estado se actualiza antes que el resto */
		switch (key) {
		case KEY_LEFTSHIFT:  shift_left = 1; break;
		case KEY_RIGHTSHIFT: shift_right = 1; break;
		case KEY_LEFTCTRL:   ctrl_left = 1; break;
		case KEY_RIGHTCTRL:  ctrl_right = 1; break;
		case KEY_LEFTALT:    alt_left = 1; break;
		case KEY_RIGHTALT:   alt_right = 1; break;
		case KEY_CAPSLOCK:
			/* la repeticion automatica (typematic) no debe realternar */
			if (!caps_down) caps_lock = (uint8_t)!caps_lock;
			caps_down = 1;
			break;
		default: {
			int shifted = (shift_left || shift_right);
			char base = shifted ? entry->hi : entry->lo;
			/* Caps Lock solo afecta a letras y se combina con Shift:
			 * caps + shift produce minusculas (igual que un teclado real). */
			if (caps_lock && base >= 'a' && base <= 'z') base = (char)(base - 32);
			else if (caps_lock && base >= 'A' && base <= 'Z') base = (char)(base + 32);
			ch = base;
			break;
		}
		}
	} else {
		switch (key) {
		case KEY_LEFTSHIFT:  shift_left = 0; break;
		case KEY_RIGHTSHIFT: shift_right = 0; break;
		case KEY_LEFTCTRL:   ctrl_left = 0; break;
		case KEY_RIGHTCTRL:  ctrl_right = 0; break;
		case KEY_LEFTALT:    alt_left = 0; break;
		case KEY_RIGHTALT:   alt_right = 0; break;
		case KEY_CAPSLOCK:   caps_down = 0; break;
		default: break;
		}
	}

	/* evento central: keycode + ASCII traducido */
	input_push_key(key, pressed, ch);

	/* buffer de caracteres para la shell de texto (solo pulsaciones utiles) */
	if (pressed && ch != 0) {
		if ((ch >= 32 && ch < 127) || ch == '\n' || ch == '\b' || ch == '\t')
			kb_push_char(ch);
	}
}

/* ------------------------------------------------------------------ */
/* ISR del teclado                                                     */
/* ------------------------------------------------------------------ */

static void keyboard_callback(struct regs *r) {
	(void)r;

	/* el puerto 0x60 es compartido con el raton: solo consumir si el dato
	 * esta disponible y corresponde al teclado (bit 5 del estado = aux). */
	uint8_t status = inb(0x64);
	if (!(status & 0x01)) return;
	if (status & 0x20) return;

	uint8_t sc = inb(0x60);

	/* secuencia E1 1D 45 E1 9D C5 = Pause/Break: se ignora por completo */
	if (pause_skip) { pause_skip--; return; }
	if (sc == 0xE1) { pause_skip = 5; return; }

	/* prefijo de tecla extendida */
	if (sc == 0xE0) { extended = 1; return; }

	int released = (sc & 0x80) != 0;
	uint8_t code = (uint8_t)(sc & 0x7F);
	const keymap_entry_t *entry;

	if (extended) {
		extended = 0;
		entry = &keymap_e0[code];
	} else {
		entry = &keymap[code];
	}

	keyboard_handle_key(entry, !released);
}

/* ------------------------------------------------------------------ */
/* API publica                                                         */
/* ------------------------------------------------------------------ */

#define KB_PS2_DATA   0x60
#define KB_PS2_STATUS 0x64
#define KB_TIMEOUT    100000

static int kb_wait_write(void) {
	for (int i = 0; i < KB_TIMEOUT; i++)
		if (!(inb(KB_PS2_STATUS) & 0x02)) return 1;
	return 0;
}

static int kb_wait_read(void) {
	for (int i = 0; i < KB_TIMEOUT; i++)
		if (inb(KB_PS2_STATUS) & 0x01) return 1;
	return 0;
}

/* Sonda real del teclado: comando 0xEE (echo). Devuelve 1 si el controlador
 * responde con 0xEE. QEMU y el hardware PS/2 estandar lo implementan. */
static int kb_probe_present(void) {
	/* descarta bytes pendientes de un posible BIOS/arranque previo */
	for (int i = 0; i < 32; i++) {
		if (!(inb(KB_PS2_STATUS) & 0x01)) break;
		(void)inb(KB_PS2_DATA);
	}
	if (!kb_wait_write()) return 0;
	outb(KB_PS2_DATA, 0xEE);
	if (!kb_wait_read()) return 0;
	return inb(KB_PS2_DATA) == 0xEE;
}

static int kb_read_byte(uint8_t *out) {
	if (!kb_wait_read()) return 0;
	*out = inb(KB_PS2_DATA);
	return 1;
}

static int kb_write_byte(uint8_t data) {
	if (!kb_wait_write()) return 0;
	outb(KB_PS2_DATA, data);
	return 1;
}

/* Deja garantizado el scancode set 1:
 *  - si el controlador tiene activada la traduccion (bit 6 del byte de
 *    configuracion), el teclado puede seguir en set 2 y el 8042 lo traduce;
 *  - si la traduccion esta desactivada, se pide al teclado el set 1 con
 *    0xF0 0x01. Todo el intercambio es por sondeo (aun sin interrupciones). */
static void kb_configure_scancode_set(void) {
	uint8_t config = 0, ack = 0, set = 0;

	if (!kb_wait_write()) return;
	outb(KB_PS2_STATUS, 0x20);            /* leer byte de configuracion */
	if (!kb_read_byte(&config)) return;
	if (config & 0x40) return;            /* el 8042 traduce set2 -> set1 */

	/* traduccion desactivada: leer el set actual (0xF0 0x00) */
	if (!kb_write_byte(0xF0)) return;
	if (!kb_read_byte(&ack) || ack != 0xFA) return;
	if (!kb_write_byte(0x00)) return;
	if (!kb_read_byte(&ack) || ack != 0xFA) return;
	if (!kb_read_byte(&set)) return;
	if (set == 1) return;

	/* seleccionar el scancode set 1 (0xF0 0x01) */
	if (!kb_write_byte(0xF0)) return;
	if (!kb_read_byte(&ack) || ack != 0xFA) return;
	if (!kb_write_byte(0x01)) return;
	(void)kb_read_byte(&ack);
}

void keyboard_init(void) {
	extended = 0;
	pause_skip = 0;
	shift_left = shift_right = 0;
	ctrl_left = ctrl_right = 0;
	alt_left = alt_right = 0;
	caps_lock = 0;
	caps_down = 0;
	kb_head = kb_tail = 0;
	kb_present = kb_probe_present();
	kb_configure_scancode_set();
	irq_install(1, keyboard_callback);
}

/* Espera (con hlt) hasta que haya un caracter ASCII disponible. Solo la usa
 * la consola VGA de respaldo; el escritorio consume eventos con input_poll(). */
char keyboard_getchar(void) {
	while (kb_head == kb_tail) hlt();
	char c = kb_buffer[kb_tail];
	kb_tail = (kb_tail + 1u) % KB_BUFFER;
	return c;
}

/* 1 si hay un teclado PS/2 detectado (lo consulta la app "Acerca de"). */
int keyboard_available(void) {
	return kb_present;
}
