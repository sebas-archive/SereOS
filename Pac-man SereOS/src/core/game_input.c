/* PAC-MAN SereOS - mapeo de eventos de plataforma a la logica del juego
 *
 * Flechas o WASD mueven a Pac-Man; Enter confirma; Esc pausa/atras; R
 * reinicia; Q vuelve al titulo desde pausa. Los flancos se consumen en cada
 * tick y las teclas mantenidas se leen con pac_input_key_down().
 */
#include <stdint.h>
#include <string.h>
#include "pac_platform.h"
#include "pac_game.h"
#include "game_input.h"
#include "game_render.h"

void pac_input_init(pac_game_t *g)
{
	if (!g)
		return;
	memset(&g->input, 0, sizeof(g->input));
	g->input.held_dir = PAC_DIR_NONE;
}

void pac_input_event(pac_game_t *g, const pac_event_t *ev)
{
	if (!g || !ev)
		return;

	switch (ev->type) {
	case PAC_EVENT_KEY_DOWN:
		switch (ev->key) {
		case PAC_KEY_ESC:
			g->input.esc_pressed = 1;
			break;
		case PAC_KEY_ENTER:
			g->input.confirm_pressed = 1;
			break;
		case PAC_KEY_UP:
		case PAC_KEY_W:
			g->input.up_pressed = 1;
			g->pac.requested = PAC_DIR_UP;
			break;
		case PAC_KEY_DOWN:
		case PAC_KEY_S:
			g->input.down_pressed = 1;
			g->pac.requested = PAC_DIR_DOWN;
			break;
		case PAC_KEY_LEFT:
		case PAC_KEY_A:
		case PAC_KEY_Z:
			g->input.left_pressed = 1;
			g->pac.requested = PAC_DIR_LEFT;
			break;
		case PAC_KEY_RIGHT:
		case PAC_KEY_D:
		case PAC_KEY_X:
			g->input.right_pressed = 1;
			g->pac.requested = PAC_DIR_RIGHT;
			break;
		case PAC_KEY_R:
			g->input.restart_pressed = 1;
			break;
		case PAC_KEY_Q:
			g->input.quit_pressed = 1;
			break;
		case PAC_KEY_F11:
			g->fullscreen = !g->fullscreen;
			pac_settings_apply(g);
			pac_settings_save(g);
			break;
		default:
			break;
		}
		break;
	case PAC_EVENT_MOUSE_DOWN:
		if (ev->button == PAC_MOUSE_LEFT && g->state == PAC_STATE_MENU) {
			int hit = pac_render_menu_hit(g, ev->mouse_x, ev->mouse_y);
			if (hit >= 0) {
				g->menu_sel = hit;
				g->input.confirm_pressed = 1;
			}
		}
		break;
	case PAC_EVENT_QUIT:
		g->wants_close = 1;
		break;
	default:
		break;
	}
}

static int key_or(int a, int b)
{
	return a || b;
}

void pac_input_begin_frame(pac_game_t *g, int focused)
{
	pac_dir_t held = PAC_DIR_NONE;

	if (!g)
		return;

	if (!focused) {
		g->input.held_dir = PAC_DIR_NONE;
		return;
	}

	if (key_or(pac_input_key_down(PAC_KEY_UP), pac_input_key_down(PAC_KEY_W)))
		held = PAC_DIR_UP;
	else if (key_or(pac_input_key_down(PAC_KEY_DOWN),
	                pac_input_key_down(PAC_KEY_S)))
		held = PAC_DIR_DOWN;
	else if (key_or(pac_input_key_down(PAC_KEY_LEFT),
	                pac_input_key_down(PAC_KEY_A)))
		held = PAC_DIR_LEFT;
	else if (key_or(pac_input_key_down(PAC_KEY_RIGHT),
	                pac_input_key_down(PAC_KEY_D)))
		held = PAC_DIR_RIGHT;

	g->input.held_dir = held;
	/* respaldo si se perdio el evento de pulsacion */
	if (held != PAC_DIR_NONE && g->pac.requested == PAC_DIR_NONE)
		g->pac.requested = held;
}

void pac_input_consume(pac_game_t *g)
{
	if (!g)
		return;
	g->input.confirm_pressed = 0;
	g->input.esc_pressed = 0;
	g->input.up_pressed = 0;
	g->input.down_pressed = 0;
	g->input.restart_pressed = 0;
	g->input.quit_pressed = 0;
	g->input.left_pressed = 0;
	g->input.right_pressed = 0;
}
