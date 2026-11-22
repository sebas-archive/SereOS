/* PAC-MAN SereOS - adaptador app_t para el escritorio de SereOS
 *
 * Exporta la unica funcion publica que el OS necesita: app_t *app_game(void).
 * El nucleo y el render son compartidos con el backend Linux; este fichero
 * solo conecta la ventana/tarea/eventos del escritorio con pac_game_*.
 */
#include <stdint.h>
#include <string.h>

#include "app.h"
#include "window.h"
#include "input.h"
#include "task.h"
#include "timer.h"
#include "serial.h"
#include "kmalloc.h"

#include "pacman.h"
#include "pac_platform.h"
#include "pac_game.h"
#include "platform_sereos.h"

typedef struct {
	pac_game_t *game;
	int task_id;
} sereos_app_state_t;

/* ------------------------------------------------------------------ */
/* tarea cooperativa                                                   */
/* ------------------------------------------------------------------ */
static void game_step(void *arg)
{
	struct window *w = (struct window *)arg;
	sereos_app_state_t *st;

	if (!w)
		return;
	st = (sereos_app_state_t *)window_data(w);
	if (!st || !st->game)
		return;

	if (pac_game_tick(st->game))
		window_invalidate(w);
	if (pac_game_wants_close(st->game))
		window_close(w);
}

static void game_open(struct window *w)
{
	sereos_app_state_t *st;
	pac_game_t *g;

	if (!w)
		return;
	pac_sereos_bind_window(w);

	g = pac_game_create();
	if (!g)
		return;

	st = (sereos_app_state_t *)kmalloc((uint32_t)sizeof(*st));
	if (!st) {
		pac_game_destroy(g);
		return;
	}
	st->game = g;
	st->task_id = 0;

	window_set_data(w, st);
	window_set_title(w, PAC_APP_NAME);
	window_invalidate(w);

	st->task_id = task_create("game", game_step, w);
	if (st->task_id < 0)
		st->task_id = 0;
}

static void game_close(struct window *w)
{
	sereos_app_state_t *st;

	if (!w)
		return;
	st = (sereos_app_state_t *)window_data(w);
	if (!st)
		return;

	if (st->task_id > 0)
		task_kill(st->task_id);
	if (st->game)
		pac_game_destroy(st->game);
	window_set_data(w, NULL);
	kfree(st);
}

static void game_draw(struct window *w)
{
	sereos_app_state_t *st;
	pac_rect_t vp;

	if (!w)
		return;
	st = (sereos_app_state_t *)window_data(w);
	if (!st || !st->game)
		return;

	vp.x = window_content_x(w);
	vp.y = window_content_y(w);
	vp.w = window_content_w(w);
	vp.h = window_content_h(w);
	pac_game_draw(st->game, &vp);
}

static void game_event(struct window *w, const event_t *ev)
{
	sereos_app_state_t *st;
	pac_event_t pe;

	if (!w || !ev)
		return;
	st = (sereos_app_state_t *)window_data(w);
	if (!st || !st->game)
		return;

	memset(&pe, 0, sizeof(pe));
	pe.tick = (uint32_t)timer_ticks();
	pe.ch = ev->ch;
	pe.button = ev->button;
	pe.wheel = ev->wheel;
	pe.mouse_x = ev->mouse_x;
	pe.mouse_y = ev->mouse_y;
	pe.pressed = ev->pressed;
	pe.key = (uint16_t)pac_sereos_map_keycode(ev->key);

	switch (ev->type) {
	case EVENT_KEY_DOWN: pe.type = PAC_EVENT_KEY_DOWN; break;
	case EVENT_KEY_UP: pe.type = PAC_EVENT_KEY_UP; break;
	case EVENT_MOUSE_DOWN: pe.type = PAC_EVENT_MOUSE_DOWN; break;
	case EVENT_MOUSE_UP: pe.type = PAC_EVENT_MOUSE_UP; break;
	case EVENT_MOUSE_MOVE: pe.type = PAC_EVENT_MOUSE_MOVE; break;
	case EVENT_MOUSE_WHEEL: pe.type = PAC_EVENT_MOUSE_WHEEL; break;
	default: return;
	}
	pac_game_event(st->game, &pe);
}

/* ------------------------------------------------------------------ */
/* descriptor app_t                                                    */
/* ------------------------------------------------------------------ */
static app_t pacman_app = {
	PAC_APP_ID,
	PAC_APP_NAME,
	PAC_APP_ICON,
	PAC_WIN_W,
	PAC_WIN_H,
	NULL,          /* init */
	game_open,
	game_close,
	game_draw,
	game_event,
	NULL           /* update: avanza la tarea cooperativa */
};

app_t *app_game(void)
{
	return &pacman_app;
}
