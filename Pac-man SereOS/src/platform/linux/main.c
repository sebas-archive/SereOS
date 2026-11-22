/* PAC-MAN SereOS - bucle principal del backend Linux (SDL2)
 *
 * Traduce eventos SDL a pac_event_t, avanza el nucleo compartido y presenta
 * el framebuffer software. Soporta modo smoke sin ventana para CI:
 *   SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy ./pacman-sereos --smoke 120 \
 *       --screenshot /tmp/pac.ppm
 */
#include <stdio.h>
#include <string.h>
#include <SDL2/SDL.h>

#include "pacman.h"
#include "pac_platform.h"
#include "platform_linux.h"

static int map_key(SDL_Keycode k)
{
	switch (k) {
	case SDLK_ESCAPE: return PAC_KEY_ESC;
	case SDLK_RETURN: case SDLK_KP_ENTER: return PAC_KEY_ENTER;
	case SDLK_SPACE: return PAC_KEY_SPACE;
	case SDLK_UP: return PAC_KEY_UP;
	case SDLK_DOWN: return PAC_KEY_DOWN;
	case SDLK_LEFT: return PAC_KEY_LEFT;
	case SDLK_RIGHT: return PAC_KEY_RIGHT;
	case SDLK_a: return PAC_KEY_A;
	case SDLK_b: return PAC_KEY_B;
	case SDLK_c: return PAC_KEY_C;
	case SDLK_d: return PAC_KEY_D;
	case SDLK_e: return PAC_KEY_E;
	case SDLK_f: return PAC_KEY_F;
	case SDLK_g: return PAC_KEY_G;
	case SDLK_h: return PAC_KEY_H;
	case SDLK_i: return PAC_KEY_I;
	case SDLK_j: return PAC_KEY_J;
	case SDLK_k: return PAC_KEY_K;
	case SDLK_l: return PAC_KEY_L;
	case SDLK_m: return PAC_KEY_M;
	case SDLK_n: return PAC_KEY_N;
	case SDLK_o: return PAC_KEY_O;
	case SDLK_p: return PAC_KEY_P;
	case SDLK_q: return PAC_KEY_Q;
	case SDLK_r: return PAC_KEY_R;
	case SDLK_s: return PAC_KEY_S;
	case SDLK_t: return PAC_KEY_T;
	case SDLK_u: return PAC_KEY_U;
	case SDLK_v: return PAC_KEY_V;
	case SDLK_w: return PAC_KEY_W;
	case SDLK_x: return PAC_KEY_X;
	case SDLK_y: return PAC_KEY_Y;
	case SDLK_z: return PAC_KEY_Z;
	case SDLK_0: return PAC_KEY_0;
	case SDLK_1: return PAC_KEY_1;
	case SDLK_2: return PAC_KEY_2;
	case SDLK_3: return PAC_KEY_3;
	case SDLK_4: return PAC_KEY_4;
	case SDLK_5: return PAC_KEY_5;
	case SDLK_6: return PAC_KEY_6;
	case SDLK_7: return PAC_KEY_7;
	case SDLK_8: return PAC_KEY_8;
	case SDLK_9: return PAC_KEY_9;
	case SDLK_F11: return PAC_KEY_F11;
	default: return PAC_KEY_NONE;
	}
}

static void push_key(pac_game_t *g, const SDL_KeyboardEvent *ke, int down)
{
	pac_event_t ev;
	memset(&ev, 0, sizeof(ev));
	ev.type = down ? PAC_EVENT_KEY_DOWN : PAC_EVENT_KEY_UP;
	ev.key = (uint16_t)map_key(ke->keysym.sym);
	ev.pressed = down ? 1 : 0;
	ev.ch = 0;
	ev.tick = pac_time_ms();
	if (ev.key != PAC_KEY_NONE)
		pac_game_event(g, &ev);
}

static void push_mouse(pac_game_t *g, Uint32 type, int wx, int wy,
                       Uint8 button, int pressed, int wheel)
{
	pac_event_t ev;
	int cx = wx, cy = wy;

	pac_linux_window_to_canvas(wx, wy, &cx, &cy);
	memset(&ev, 0, sizeof(ev));
	ev.type = (uint8_t)type;
	ev.pressed = (uint8_t)(pressed ? 1 : 0);
	ev.mouse_x = (int16_t)cx;
	ev.mouse_y = (int16_t)cy;
	ev.button = button;
	ev.wheel = (int8_t)wheel;
	ev.tick = pac_time_ms();
	pac_game_event(g, &ev);
}

static void pump_events(pac_game_t *g)
{
	SDL_Event e;
	while (SDL_PollEvent(&e)) {
		switch (e.type) {
		case SDL_QUIT:
			pac_platform_request_close();
			break;
		case SDL_KEYDOWN:
			if (!e.key.repeat)
				push_key(g, &e.key, 1);

			break;
		case SDL_KEYUP:
			push_key(g, &e.key, 0);
			break;
		case SDL_MOUSEMOTION:
			push_mouse(g, PAC_EVENT_MOUSE_MOVE, e.motion.x, e.motion.y, 0, 0, 0);
			break;
		case SDL_MOUSEBUTTONDOWN:
			push_mouse(g, PAC_EVENT_MOUSE_DOWN, e.button.x, e.button.y,
			           e.button.button == SDL_BUTTON_LEFT ? PAC_MOUSE_LEFT :
			           (e.button.button == SDL_BUTTON_RIGHT ? PAC_MOUSE_RIGHT :
			            PAC_MOUSE_MIDDLE), 1, 0);
			break;
		case SDL_MOUSEBUTTONUP:
			push_mouse(g, PAC_EVENT_MOUSE_UP, e.button.x, e.button.y,
			           e.button.button == SDL_BUTTON_LEFT ? PAC_MOUSE_LEFT :
			           (e.button.button == SDL_BUTTON_RIGHT ? PAC_MOUSE_RIGHT :
			            PAC_MOUSE_MIDDLE), 0, 0);
			break;
		case SDL_MOUSEWHEEL:
			{
				int mx = 0, my = 0;
				pac_event_t ev;
				SDL_GetMouseState(&mx, &my);
				pac_linux_window_to_canvas(mx, my, &mx, &my);
				memset(&ev, 0, sizeof(ev));
				ev.type = PAC_EVENT_MOUSE_WHEEL;
				ev.mouse_x = (int16_t)mx;
				ev.mouse_y = (int16_t)my;
				ev.wheel = (int8_t)e.wheel.y;
				ev.tick = pac_time_ms();
				pac_game_event(g, &ev);
			}
			break;
		default:
			break;
		}
	}
}

int main(int argc, char **argv)
{
	pac_game_t *g;
	int frames = 0;
	int smoke;
	const char *shot;
	uint32_t last_loop;

	pac_linux_parse_args(argc, argv);
	if (pac_linux_should_quit())
		return 0;

	if (!pac_platform_init())
		return 1;
	g = pac_game_create();
	if (g && pac_linux_scene()[0])
		pac_game_debug_scene(g, pac_linux_scene());
	if (!g) {
		pac_platform_shutdown();
		return 1;
	}

	smoke = pac_linux_smoke_frames();
	shot = pac_linux_screenshot_path();
	last_loop = pac_time_ms();

	/* Primera pintura incondicional: el nucleo solo redibuja si la ventana
	 * tiene el foco, pero en Wayland una ventana sin buffer no se mapea ni
	 * recibe foco: lanzada desde un proceso sin token de activacion se
	 * quedaria invisible y congelada para siempre. */
	{
		pac_rect_t vp0;
		pac_platform_content_rect(&vp0);
		pac_game_draw(g, &vp0);
		pac_present();
	}

	while (!pac_game_wants_close(g) && !pac_linux_should_quit()) {
		pac_rect_t vp;

		pump_events(g);
		if (pac_linux_should_quit())
			break;

		if (pac_game_tick(g)) {
			pac_platform_content_rect(&vp);
			pac_game_draw(g, &vp);
			pac_present();
			frames++;
			if (smoke > 0 && frames >= smoke)
				break;
		}
		pac_audio_update();

		/* limite de frame (~60 Hz) para no quemar CPU */
		{
			uint32_t now = pac_time_ms();
			uint32_t spent = now - last_loop;
			if (spent < 16)
				SDL_Delay(16 - spent);
			last_loop = pac_time_ms();
		}
	}
	/* solicitud de cierre del juego (Esc) -> cerrar la plataforma */
	if (pac_game_wants_close(g))
		pac_platform_request_close();

	if (shot && shot[0] && frames > 0)
		(void)pac_linux_save_ppm(shot);

	pac_game_destroy(g);
	pac_platform_shutdown();
	return 0;
}
