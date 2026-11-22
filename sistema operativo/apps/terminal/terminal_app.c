/* apps/terminal/terminal_app.c - terminal grafica de SereOS Desktop
 *
 * Rediseno con el sistema de diseno de SereOS (gui/theme.h + gui/ui.h +
 * graphics/text.h). Terminal oscura uniforme, tipografia monoespaciada,
 * prompt con acento, cursor de bloque y scrollbar fina. La interpretacion de
 * comandos sigue delegada en la shell compartida (shell/shell.h).
 *
 * Buffer: 320 lineas x 100 columnas con un color shell_color_t por caracter.
 * Scroll con PgUp/PgDn y rueda; auto-scroll al fondo.
 */
#include <stdint.h>
#include "app.h"
#include "window.h"
#include "theme.h"
#include "ui.h"
#include "text.h"
#include "graphics.h"
#include "shell.h"
#include "kmalloc.h"
#include "task.h"
#include "timer.h"
#include "serial.h"
#include "string.h"
#include "terminal_app.h"

#define TERM_LINES    320            /* lineas de scrollback */
#define TERM_COLS     100            /* columnas por linea */
#define TERM_BLINK_TICKS 60          /* parpadeo lento del cursor (0.6 s a 100 Hz) */
#define TERM_CURSOR_W 7
#define TERM_CURSOR_H 15

typedef struct {
	shell_t       sh;                            /* shell compartida */
	char          text[TERM_LINES][TERM_COLS];   /* caracteres del scrollback */
	uint8_t       color[TERM_LINES][TERM_COLS];  /* shell_color_t por caracter */
	uint8_t       wrap[TERM_LINES];              /* 1 = continuacion por auto-wrap */
	int           line_count;                    /* lineas realmente usadas */
	int           row, col;                      /* cursor logico */
	int           scroll;                        /* lineas desplazadas del fondo */
	int           visible_rows;                  /* filas visibles (cache draw) */
	int           task_id;                       /* tarea cooperativa */
	shell_color_t cur_color;                     /* color de salida actual */
	int           dirty;                         /* hay salida nueva sin pintar */
	int           blink_on;                      /* cursor visible (parpadeo) */
} terminal_state_t;

static terminal_state_t *term_state(struct window *w) {
	return (terminal_state_t *)window_data(w);
}

/* ------------------------------------------------------------------ */
/* colores de la shell -> sistema de diseno                            */
/* ------------------------------------------------------------------ */
static uint32_t term_color(shell_color_t c) {
	switch (c) {
	case SH_COLOR_OK:     return theme.green;
	case SH_COLOR_ERR:    return theme.red;
	case SH_COLOR_INFO:   return theme.cyan;
	case SH_COLOR_WARN:   return theme.amber;
	case SH_COLOR_ACCENT: return theme.accent;
	case SH_COLOR_DIM:    return theme.text_dim;
	case SH_COLOR_DEFAULT:
	default:              return theme.text;
	}
}

/* ------------------------------------------------------------------ */
/* buffer de scrollback                                                */
/* ------------------------------------------------------------------ */
static void term_line_clear(terminal_state_t *st, int line) {
	if (line < 0 || line >= TERM_LINES) return;
	memset(st->text[line], ' ', TERM_COLS);
	memset(st->color[line], (int)SH_COLOR_DEFAULT, TERM_COLS);
	st->wrap[line] = 0;
}

static void term_reset(terminal_state_t *st) {
	int i;
	for (i = 0; i < TERM_LINES; i++) term_line_clear(st, i);
	st->line_count = 1;
	st->row = 0;
	st->col = 0;
	st->scroll = 0;
	st->dirty = 1;
}

/* continuation = 1 cuando la nueva linea es el resultado de un auto-wrap. */
static void term_newline(terminal_state_t *st, int continuation) {
	st->col = 0;
	if (st->row + 1 < TERM_LINES) {
		st->row++;
		if (st->row >= st->line_count) st->line_count = st->row + 1;
		term_line_clear(st, st->row);
	} else {
		/* scrollback lleno: se descarta la linea mas antigua */
		memmove(st->text[0], st->text[1], (TERM_LINES - 1) * TERM_COLS);
		memmove(st->color[0], st->color[1], (TERM_LINES - 1) * TERM_COLS);
		memmove(&st->wrap[0], &st->wrap[1], TERM_LINES - 1);
		term_line_clear(st, TERM_LINES - 1);
		st->row = TERM_LINES - 1;
	}
	st->wrap[st->row] = (uint8_t)(continuation ? 1 : 0);
	if (st->scroll > 0) st->scroll++;
	st->dirty = 1;
}

static void term_putc(terminal_state_t *st, char c) {
	if (c == '\n') { term_newline(st, 0); return; }

	if (c == '\r') {
		st->col = 0;
		st->dirty = 1;
		return;
	}
	if (c == '\b') {
		if (st->col > 0) {
			st->col--;
		} else if (st->row > 0 && st->wrap[st->row]) {
			st->row--;
			st->col = TERM_COLS - 1;
		} else {
			st->dirty = 1;
			return;
		}
		st->text[st->row][st->col] = ' ';
		st->color[st->row][st->col] = (uint8_t)st->cur_color;
		st->dirty = 1;
		return;
	}
	if (c == '\t') {
		int next = (st->col / 8 + 1) * 8;
		if (next > TERM_COLS) next = TERM_COLS;
		while (st->col < next) {
			st->text[st->row][st->col] = ' ';
			st->color[st->row][st->col] = (uint8_t)st->cur_color;
			st->col++;
		}
		if (st->col >= TERM_COLS) term_newline(st, 1);
		st->dirty = 1;
		return;
	}
	if (c == '\f') {                     /* comando "clear" */
		term_reset(st);
		return;
	}
	if ((unsigned char)c < 32 || (unsigned char)c > 126) return;

	st->text[st->row][st->col] = c;
	st->color[st->row][st->col] = (uint8_t)st->cur_color;
	st->col++;
	if (st->col >= TERM_COLS) term_newline(st, 1);
	st->dirty = 1;
}

static void term_puts(terminal_state_t *st, const char *s) {
	while (*s) term_putc(st, *s++);
}

static void term_puts_colored(terminal_state_t *st, const char *s, shell_color_t c) {
	shell_color_t prev = st->cur_color;
	st->cur_color = c;
	term_puts(st, s);
	st->cur_color = prev;
}

/* adaptador de salida que entrega la shell compartida */
static void term_out_write(void *ctx, const char *text) {
	terminal_state_t *st = (terminal_state_t *)ctx;

	if (!st || !text) return;
	/* prompt "sereos> ": nombre en acento y ">" en color secundario */
	if (st->cur_color == SH_COLOR_ACCENT && strcmp(text, "sereos> ") == 0) {
		term_puts_colored(st, "sereos", SH_COLOR_ACCENT);
		term_puts_colored(st, ">", SH_COLOR_DIM);
		term_puts_colored(st, " ", SH_COLOR_DEFAULT);
		return;
	}
	term_puts(st, text);
}

static void term_out_set_color(void *ctx, shell_color_t color) {
	terminal_state_t *st = (terminal_state_t *)ctx;
	if (st) st->cur_color = color;
}

/* ------------------------------------------------------------------ */
/* scroll                                                              */
/* ------------------------------------------------------------------ */
static int term_max_scroll(terminal_state_t *st, int visible_rows) {
	int max = st->line_count - visible_rows;
	if (max < 0) max = 0;
	if (st->scroll < 0) st->scroll = 0;
	if (st->scroll > max) st->scroll = max;
	return max;
}

static void term_scroll_by(terminal_state_t *st, int delta) {
	int max = st->line_count - (st->visible_rows > 0 ? st->visible_rows : 1);
	if (max < 0) max = 0;
	st->scroll += delta;
	if (st->scroll < 0) st->scroll = 0;
	if (st->scroll > max) st->scroll = max;
}

/* ------------------------------------------------------------------ */
/* dibujo                                                              */
/* ------------------------------------------------------------------ */
static void term_draw_scrollbar(int x, int y, int h, int visible,
                                int max_scroll, int scroll) {
	int thumb_h, thumb_y, denom;

	if (h <= 0) return;
	ui_surface(x, y, 2, h, RADIUS_XS, theme.border, 0);
	thumb_h = h * visible / (visible + max_scroll);
	if (thumb_h < 18) thumb_h = 18;
	if (thumb_h > h) thumb_h = h;
	thumb_y = y;
	denom = max_scroll;
	if (denom > 0) thumb_y = y + (h - thumb_h) * (max_scroll - scroll) / denom;
	gfx_fill_round_rect(x, thumb_y, 2, thumb_h, 1,
	                    scroll > 0 ? theme.accent : theme.text_faint);
}

static void term_draw(struct window *w) {
	terminal_state_t *st = term_state(w);
	int cx, cy, cw, ch, pad, cell_w, cell_h, area_x, area_y, area_w, area_h;
	int rows, cols, max_scroll, first, r, c, sb_x;

	if (!st) return;
	cx = window_content_x(w);
	cy = window_content_y(w);
	cw = window_content_w(w);
	ch = window_content_h(w);
	if (cw < 120 || ch < 80) return;

	ui_surface(cx, cy, cw, ch, 0, theme.bg, 0);
	pad = SP_3;
	cell_w = text_width(TEXT_MONO, "M");
	cell_h = text_height(TEXT_MONO);
	if (cell_w < 4) cell_w = 7;
	if (cell_h < 8) cell_h = 15;

	area_x = cx + pad;
	area_y = cy + pad;
	area_w = cw - 2 * pad - (SP_2 + 2);   /* deja sitio a la scrollbar */
	area_h = ch - 2 * pad;
	rows = area_h / cell_h;
	cols = area_w / cell_w;
	if (rows < 1) rows = 1;
	if (rows > TERM_LINES) rows = TERM_LINES;
	if (cols < 1) cols = 1;
	if (cols > TERM_COLS) cols = TERM_COLS;
	st->visible_rows = rows;

	max_scroll = term_max_scroll(st, rows);
	first = st->line_count - rows - st->scroll;
	if (first < 0) first = 0;

	for (r = 0; r < rows; r++) {
		int line = first + r;
		int y;

		if (line < 0 || line >= st->line_count) continue;
		y = area_y + r * cell_h;
		c = 0;
		while (c < cols) {
			char run[TERM_COLS + 1];
			uint8_t col8 = st->color[line][c];
			int start = c, n = 0, has_text = 0;

			while (c < cols && st->color[line][c] == col8) {
				char chr = st->text[line][c];
				run[n++] = chr;
				if (chr != ' ') has_text = 1;
				c++;
			}
			if (has_text) {
				run[n] = '\0';
				text_draw(TEXT_MONO, area_x + start * cell_w, y, run,
				          term_color((shell_color_t)col8));
			}
		}
	}

	/* cursor de bloque (solo al fondo y con la ventana activa) */
	if (st->blink_on && st->scroll == 0 && window_active(w)) {
		int vr = st->row - first;
		int vc = st->col;

		if (vc >= cols) vc = cols - 1;
		if (vc < 0) vc = 0;
		if (vr >= 0 && vr < rows) {
			int bx = area_x + vc * cell_w;
			int by = area_y + vr * cell_h + (cell_h - TERM_CURSOR_H) / 2;
			char chr = st->text[st->row][st->col];

			gfx_fill_rect_alpha(bx, by, TERM_CURSOR_W, TERM_CURSOR_H,
			                    theme.accent, 160);
			if (chr > 32 && chr < 127) {
				char one[2];
				one[0] = chr;
				one[1] = '\0';
				text_draw(TEXT_MONO, bx, area_y + vr * cell_h, one, theme.bg);
			}
		}
	}

	/* scrollbar fina a la derecha */
	sb_x = cx + cw - pad - 1;
	if (st->line_count > rows)
		term_draw_scrollbar(sb_x, cy + pad, ch - 2 * pad, rows,
		                    max_scroll, st->scroll);

	st->dirty = 0;
}

/* ------------------------------------------------------------------ */
/* ciclo de vida y eventos                                             */
/* ------------------------------------------------------------------ */
static void term_step(void *arg) {
	struct window *w = (struct window *)arg;
	terminal_state_t *st = term_state(w);
	uint32_t now;
	int blink;

	if (!st) return;
	now = timer_ticks();
	blink = ((now / TERM_BLINK_TICKS) & 1u) == 0u;
	if (blink != st->blink_on && window_active(w)) {
		st->blink_on = blink;
		window_invalidate(w);
	}
	if (st->dirty) window_invalidate(w);
}

static void term_open(struct window *w) {
	terminal_state_t *st;
	shell_out_t out;

	st = (terminal_state_t *)kzalloc(sizeof(terminal_state_t));
	if (!st) return;
	st->cur_color = SH_COLOR_DEFAULT;
	st->visible_rows = 20;
	st->task_id = -1;
	st->blink_on = 1;
	term_reset(st);
	window_set_data(w, st);

	out.ctx = st;
	out.write = term_out_write;
	out.set_color = term_out_set_color;
	shell_attach(&st->sh, out);

	/* banner compacto (3 lineas) con atajos y ayuda basica */
	term_puts(st, "SereOS 1.0 Desktop - Terminal\n");
	term_puts_colored(st,
	                  "F1 Archivos | F2 Terminal | F3 Monitor | F4 Juego | F5 Acerca\n",
	                  SH_COLOR_DIM);
	term_puts_colored(st,
	                  "help para comandos | UP/DOWN historial | PgUp/PgDn o rueda: scroll\n",
	                  SH_COLOR_DIM);
	shell_prompt(&st->sh);
	st->dirty = 1;

	serial_write("TERM_READY\n");
	st->task_id = task_create("terminal", term_step, w);
	window_invalidate(w);
}

static void term_close(struct window *w) {
	terminal_state_t *st = term_state(w);
	if (!st) return;
	if (st->task_id >= 0) task_kill(st->task_id);
	window_set_data(w, 0);
	kfree(st);
}

static void term_event(struct window *w, const event_t *ev) {
	terminal_state_t *st = term_state(w);
	if (!st || !ev) return;

	switch (ev->type) {
	case EVENT_KEY_DOWN: {
		int rows = (st->visible_rows > 3) ? st->visible_rows - 2 : 3;

		switch (ev->key) {
		case KEY_PAGEUP:
			term_scroll_by(st, rows);
			break;
		case KEY_PAGEDOWN:
			term_scroll_by(st, -rows);
			break;
		case KEY_END:
			if (input_ctrl_down()) {
				st->scroll = 0;
				break;
			}
			shell_feed_key(&st->sh, ev->key, ev->ch);
			break;
		default:
			st->scroll = 0;
			st->blink_on = 1;
			if (ev->ch >= 32 && ev->ch <= 126)
				shell_feed(&st->sh, ev->ch);
			else
				shell_feed_key(&st->sh, ev->key, ev->ch);
			break;
		}
		window_invalidate(w);
		break;
	}
	case EVENT_KEY_UP:
		break;
	case EVENT_MOUSE_WHEEL:
		if (ev->wheel > 0) term_scroll_by(st, 3);
		else if (ev->wheel < 0) term_scroll_by(st, -3);
		window_invalidate(w);
		break;
	default:
		break;
	}
}

static app_t terminal_app = {
	.id = "terminal",
	.name = "Terminal",
	.icon = "terminal",
	.default_width = 720,
	.default_height = 470,
	.init = 0,
	.open = term_open,
	.close = term_close,
	.draw = term_draw,
	.event = term_event,
	.update = 0,        /* refresco por tarea cooperativa */
};

app_t *app_terminal(void) {
	return &terminal_app;
}
