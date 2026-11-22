/* drivers/input.h - sistema centralizado de eventos de entrada
 *
 * Los drivers (IRQ 1 teclado, IRQ 12 raton) empujan eventos a una cola
 * circular. El escritorio y el juego la consumen con input_poll() sin
 * bloquearse entre si. El estado fisico de las teclas/raton tambien se
 * mantiene para la fisica del juego.
 */
#ifndef SEREOS_INPUT_H
#define SEREOS_INPUT_H
#include <stdint.h>

/* ---- codigos de tecla fisicos (independientes de la distribucion) ---- */
typedef enum {
	KEY_NONE = 0,
	KEY_ESC, KEY_ENTER, KEY_SPACE, KEY_BACKSPACE, KEY_TAB,
	KEY_LEFTSHIFT, KEY_RIGHTSHIFT, KEY_LEFTCTRL, KEY_RIGHTCTRL, KEY_LEFTALT, KEY_RIGHTALT,
	KEY_UP, KEY_DOWN, KEY_LEFT, KEY_RIGHT,
	KEY_INSERT, KEY_DELETE, KEY_HOME, KEY_END, KEY_PAGEUP, KEY_PAGEDOWN,
	KEY_F1, KEY_F2, KEY_F3, KEY_F4, KEY_F5, KEY_F6,
	KEY_F7, KEY_F8, KEY_F9, KEY_F10, KEY_F11, KEY_F12,
	KEY_A, KEY_B, KEY_C, KEY_D, KEY_E, KEY_F, KEY_G, KEY_H, KEY_I, KEY_J,
	KEY_K, KEY_L, KEY_M, KEY_N, KEY_O, KEY_P, KEY_Q, KEY_R, KEY_S, KEY_T,
	KEY_U, KEY_V, KEY_W, KEY_X, KEY_Y, KEY_Z,
	KEY_0, KEY_1, KEY_2, KEY_3, KEY_4, KEY_5, KEY_6, KEY_7, KEY_8, KEY_9,
	KEY_MINUS, KEY_EQUAL, KEY_LEFTBRACE, KEY_RIGHTBRACE,
	KEY_SEMICOLON, KEY_APOSTROPHE, KEY_GRAVE, KEY_BACKSLASH,
	KEY_COMMA, KEY_DOT, KEY_SLASH, KEY_CAPSLOCK,
	KEY_COUNT
} keycode_t;

/* ---- tipos de evento ---- */
typedef enum {
	EVENT_NONE = 0,
	EVENT_KEY_DOWN,
	EVENT_KEY_UP,
	EVENT_MOUSE_MOVE,
	EVENT_MOUSE_DOWN,
	EVENT_MOUSE_UP,
	EVENT_MOUSE_WHEEL,
	EVENT_TICK,        /* se emite desde el bucle principal, no desde la ISR */
	EVENT_QUIT
} event_type_t;

#define MOUSE_BTN_LEFT   1
#define MOUSE_BTN_RIGHT  2
#define MOUSE_BTN_MIDDLE 4

typedef struct {
	uint8_t  type;      /* event_type_t */
	uint8_t  pressed;   /* 1 = pulsado, 0 = soltado */
	uint16_t key;       /* keycode_t */
	char     ch;        /* caracter ASCII traducido (0 si no aplica) */
	int16_t  mouse_x;   /* posicion absoluta del cursor (eventos de raton) */
	int16_t  mouse_y;
	uint8_t  button;    /* MOUSE_BTN_* */
	int8_t   wheel;
	uint32_t tick;      /* timer_ticks() en el momento del evento */
} event_t;

#define INPUT_QUEUE_SIZE 512

/* inicializa la cola; llamar antes de timer/keyboard/mouse */
void input_init(void);
/* consume un evento; devuelve 1 si habia uno, 0 si la cola esta vacia */
int  input_poll(event_t *out);
int  input_has_event(void);
void input_flush(void);

/* los drivers llaman a estas funciones desde la ISR (sin bloqueo) */
void input_push_event(const event_t *ev);
void input_push_key(uint16_t key, int pressed, char ch);
void input_push_mouse(int x, int y, int button, int wheel, int pressed, int is_wheel);

/* estado fisico (para fisica del juego y modificadores) */
int  input_key_down(uint16_t key);
int  input_shift_down(void);
int  input_ctrl_down(void);
int  input_alt_down(void);

/* cursor absoluto */
int  input_mouse_x(void);
int  input_mouse_y(void);
int  input_mouse_buttons(void);
void input_set_mouse_bounds(int width, int height);

/* drivers */
void keyboard_init(void);
char keyboard_getchar(void);      /* compatibilidad con la shell de texto */
int  keyboard_available(void);
void mouse_init(void);
int  mouse_present(void);

#endif
