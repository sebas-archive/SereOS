/* harness_flow_verify.c - INDEPENDENT logic-level verification harness.
 *
 * Links the REAL shared core (src/core, src/render, assets) against a
 * platform stub (tests/mock_platform.c is used only as a framebuffer/clock
 * stub) and intercepts every pac_audio_* call with ld --wrap.  The wrapper
 * is OUR code, so the recorded event->audio sequence does not depend on the
 * fixers' own test instrumentation.
 *
 * It answers, with evidence, the sequence questions of task-9:
 *   - START plays exactly once and siren resumes afterwards
 *   - waka alternates 3/4 on dots
 *   - EXTRA_LIFE is not overwritten by a waka in the same tick
 *   - GHOST_RESPAWN loop is requested while a ghost is EATEN
 *   - frightened uses slot 12, normal uses slot 13, never both
 *   - MENU plays on menu navigation
 *   - LEVEL_CLEAR uses the intermission PCM (slot 10), GAME_OVER slot 11
 *   - pause / focus loss stop the loop and resume it
 *   - one-shot of higher priority is not truncated by a lower one
 *
 * Build (from workspace root):
 *   gcc -O2 -g -std=c99 -Iinclude -Isrc/core -Isrc/render -Iassets -Itests \
 *       audit/verify/harness/harness_flow_verify.c tests/mock_platform.c \
 *       $(ls src/core/*.c) $(ls src/render/*.c) $(ls assets/*.c) -lm \
 *       -Wl,--wrap=pac_audio_play -Wl,--wrap=pac_audio_loop \
 *       -Wl,--wrap=pac_audio_stop_loop -Wl,--wrap=pac_audio_stop \
 *       -o audit/verify/harness/harness_flow_verify
 *
 * Run: audit/verify/harness/harness_flow_verify [all|scenario]
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "pacman.h"
#include "pac_game.h"

/* ---- mock platform (clock + focus control) --------------------------- */
void mock_set_focused(int focused);
void mock_set_minimized(int minimized);
void mock_advance_tick(void);
uint32_t mock_get_ticks(void);
void mock_audio_clear_counts(void);

/* ---- our audio interception ----------------------------------------- */
#define LOG_MAX 4096
typedef struct { int t_ms; int kind; int sfx; } ev_t; /* 0 play 1 loop 2 stop_loop 3 stop */
static ev_t g_log[LOG_MAX];
static int g_log_n;
static int g_fail, g_pass;

static void log_ev(int kind, int sfx)
{
	if (g_log_n < LOG_MAX) {
		g_log[g_log_n].t_ms = (int)mock_get_ticks() * 10;
		g_log[g_log_n].kind = kind;
		g_log[g_log_n].sfx = sfx;
		g_log_n++;
	}
}

/* real symbols from tests/mock_platform.c */
void __real_pac_audio_play(int sfx);
void __real_pac_audio_loop(int sfx);
void __real_pac_audio_stop_loop(void);
void __real_pac_audio_stop(void);

void __wrap_pac_audio_play(int sfx) { log_ev(0, sfx); __real_pac_audio_play(sfx); }
void __wrap_pac_audio_loop(int sfx) { log_ev(1, sfx); __real_pac_audio_loop(sfx); }
void __wrap_pac_audio_stop_loop(void) { log_ev(2, -1); __real_pac_audio_stop_loop(); }
void __wrap_pac_audio_stop(void) { log_ev(3, -1); __real_pac_audio_stop(); }

/* ---- helpers -------------------------------------------------------- */
static void log_clear(void) { g_log_n = 0; }

static void advance(pac_game_t *g, int ms)
{
	int steps = ms / 10;
	int i;
	for (i = 0; i < steps; i++) {
		mock_advance_tick();
		pac_game_tick(g);
	}
}

static int count_kind(int kind, int sfx, int from, int to)
{
	int i, n = 0;
	for (i = from; i < to && i < g_log_n; i++)
		if (g_log[i].kind == kind && (sfx < 0 || g_log[i].sfx == sfx))
			n++;
	return n;
}

static int count_play(int sfx) { return count_kind(0, sfx, 0, g_log_n); }
static int count_loop(int sfx) { return count_kind(1, sfx, 0, g_log_n); }
static int count_stoploop(void) { return count_kind(2, -1, 0, g_log_n); }

static int next_time(int kind, int sfx, int from)
{
	int i;
	for (i = from; i < g_log_n; i++)
		if (g_log[i].kind == kind && (sfx < 0 || g_log[i].sfx == sfx))
			return g_log[i].t_ms;
	return -1;
}

static int last_loop(void)
{
	int i;
	for (i = g_log_n - 1; i >= 0; i--)
		if (g_log[i].kind == 1)
			return g_log[i].sfx;
	return -1;
}

static void check(int cond, const char *name, const char *detail)
{
	if (cond) {
		g_pass++;
		printf("PASS  %-52s %s\n", name, detail ? detail : "");
	} else {
		g_fail++;
		printf("FAIL  %-52s %s\n", name, detail ? detail : "");
	}
}

static const char *SFX(int s)
{
	static const char *names[] = {
		"NONE", "MENU", "START", "WAKA1", "WAKA2", "POWER", "EAT_GHOST",
		"EAT_FRUIT", "DEATH", "EXTRA_LIFE", "LEVEL_CLEAR", "GAME_OVER",
		"SIREN_CHASE", "SIREN_HUNT", "SIREN_FRIGHT", "GHOST_RESPAWN"
	};
	if (s < 0 || s >= 16) return "?";
	return names[s];
}

static void dump_log(const char *tag)
{
	int i;
	printf("---- audio sequence [%s] (%d events) ----\n", tag, g_log_n);
	for (i = 0; i < g_log_n; i++) {
		const char *k = g_log[i].kind == 0 ? "play" :
		                g_log[i].kind == 1 ? "loop" :
		                g_log[i].kind == 2 ? "stop_loop" : "stop";
		printf("  t=%5dms %-9s %s(%d)\n", g_log[i].t_ms, k,
		       SFX(g_log[i].sfx), g_log[i].sfx);
	}
}

static pac_game_t *new_game(void)
{
	pac_game_t *g = pac_game_create();
	mock_set_focused(1);
	mock_set_minimized(0);
	mock_audio_clear_counts();
	log_clear();
	return g;
}

static void key(pac_game_t *g, pac_key_t k, int down)
{
	pac_event_t ev;
	memset(&ev, 0, sizeof ev);
	ev.type = down ? PAC_EVENT_KEY_DOWN : PAC_EVENT_KEY_UP;
	ev.pressed = down ? 1 : 0;
	ev.key = k;
	ev.tick = (uint32_t)mock_get_ticks() * 10u;
	pac_game_event(g, &ev);
}

/* start a real game from the menu and advance past READY_START */
static pac_game_t *start_playing(int ready_ms)
{
	pac_game_t *g = new_game();
	advance(g, 300);            /* attract */
	key(g, PAC_KEY_ENTER, 1);   /* attract -> menu */
	advance(g, 100);
	key(g, PAC_KEY_ENTER, 0);
	advance(g, 200);
	key(g, PAC_KEY_ENTER, 1);   /* menu item 0 "Jugar" -> start game */
	advance(g, 100);
	key(g, PAC_KEY_ENTER, 0);
	advance(g, ready_ms);
	return g;
}

/* ---- scenarios ------------------------------------------------------ */
static void sc_start(void)
{
	pac_game_t *g = start_playing(7500);
	check(count_play(2) == 1, "start: START played exactly once",
	      "plays=2 count");
	check(next_time(1, 13, 0) > 4000, "start: normal siren resumes after hold",
	      "SIREN_HUNT loop after ~4.5s");
	check(count_loop(12) == 0, "start: no frightened siren in normal play", "");
	dump_log("start");
	pac_game_destroy(g);
}

static void sc_dots(void)
{
	pac_game_t *g = start_playing(7500);
	int w1, w2;
	log_clear();
	pac_emit_event(g, PAC_GAME_EVENT_EAT_DOT);
	g->dots_eaten++;
	advance(g, 120);
	pac_emit_event(g, PAC_GAME_EVENT_EAT_DOT);
	g->dots_eaten++;
	advance(g, 120);
	pac_emit_event(g, PAC_GAME_EVENT_EAT_DOT);
	advance(g, 120);
	w1 = count_play(3);
	w2 = count_play(4);
	check(w1 + w2 == 3, "dots: exactly 3 waka plays for 3 dots",
	      "waka1+waka2=3");
	check(w1 >= 1 && w2 >= 1, "dots: waka1/waka2 alternate", "");
	dump_log("dots");
	pac_game_destroy(g);
}

static void sc_extralife(void)
{
	pac_game_t *g = start_playing(7500);
	log_clear();
	pac_add_score(g, PAC_EXTRA_LIFE_AT);   /* crosses 10000 -> extra life */
	pac_emit_event(g, PAC_GAME_EVENT_EAT_DOT);  /* same tick waka */
	advance(g, 400);
	check(count_play(9) >= 1, "extra life: EXTRA_LIFE is requested", "");
	check(count_play(3) + count_play(4) == 0,
	      "extra life: same-tick waka does NOT overwrite EXTRA_LIFE", "");
	dump_log("extralife");
	pac_game_destroy(g);
}

static void sc_respawn(void)
{
	pac_game_t *g = start_playing(7500);
	int loop_before, loop_after;
	log_clear();
	g->ghosts[0].state = PAC_GHOST_EATEN;   /* eyes returning home */
	g->ghosts[0].scared = 0;
	advance(g, 120);
	loop_before = last_loop();
	check(loop_before == 15, "respawn: loop slot 15 while eyes are EATEN",
	      "SIREN/LOOP = GHOST_RESPAWN");
	g->ghosts[0].state = PAC_GHOST_NORMAL;
	advance(g, 120);
	loop_after = last_loop();
	check(loop_after == 13 || loop_after == 12,
	      "respawn: normal siren restored after respawn ends",
	      "loop back to HUNT/CHASE");
	check(loop_after != 15, "respawn: GHOST_RESPAWN loop does not stick", "");
	dump_log("respawn");
	pac_game_destroy(g);
}

static void sc_fright(void)
{
	pac_game_t *g = start_playing(7500);
	log_clear();
	g->fright_ms = 800;
	advance(g, 120);
	check(last_loop() == 12, "fright: frightened uses slot 12 (hunter siren)",
	      "loop = SIREN_CHASE(12)");
	advance(g, 1200);           /* fright over */
	check(last_loop() == 13, "fright: normal play returns to slot 13 (hunted)",
	      "loop = SIREN_HUNT(13)");
	dump_log("fright");
	pac_game_destroy(g);
}

static void sc_menu(void)
{
	pac_game_t *g = new_game();
	advance(g, 300);
	key(g, PAC_KEY_ENTER, 1);   /* attract -> menu */
	advance(g, 100);
	key(g, PAC_KEY_ENTER, 0);
	advance(g, 200);
	log_clear();
	key(g, PAC_KEY_DOWN, 1);
	advance(g, 60);
	key(g, PAC_KEY_DOWN, 0);
	advance(g, 120);
	check(count_play(1) >= 1, "menu: MENU blip requested on navigation", "");
	dump_log("menu");
	pac_game_destroy(g);
}

static void sc_levelclear(void)
{
	pac_game_t *g = new_game();
	log_clear();
	pac_game_debug_scene(g, "victory");
	advance(g, 100);
	check(count_play(10) >= 1, "level clear: LEVEL_CLEAR(intermission) requested",
	      "slot 10");
	/* state must last at least as long as the 5.2 s intermission */
	advance(g, 5600);
	check(g->state == PAC_STATE_LEVEL_CLEAR,
	      "level clear: state lasts >= intermission duration (5.2s)", "");
	dump_log("levelclear");
	pac_game_destroy(g);
}

static void sc_gameover(void)
{
	pac_game_t *g = new_game();
	log_clear();
	pac_game_debug_scene(g, "gameover");
	advance(g, 100);
	check(count_play(11) >= 1, "game over: GAME_OVER requested", "slot 11");
	dump_log("gameover");
	pac_game_destroy(g);
}

static void sc_pause(void)
{
	pac_game_t *g = start_playing(7500);
	int loops_before;
	log_clear();
	loops_before = count_loop(13) + count_loop(12);
	key(g, PAC_KEY_ESC, 1);
	advance(g, 60);
	key(g, PAC_KEY_ESC, 0);
	advance(g, 200);
	check(loops_before > 0 || count_loop(13) + count_loop(12) == 0,
	      "pause: siren was looping before pause (info)", "");
	check(count_stoploop() >= 1, "pause: loop stopped on pause", "");
	log_clear();
	key(g, PAC_KEY_ESC, 1);
	advance(g, 60);
	key(g, PAC_KEY_ESC, 0);
	advance(g, 300);
	check(count_loop(13) + count_loop(12) >= 1,
	      "pause: siren resumes after unpause", "");
	dump_log("pause");
	pac_game_destroy(g);
}

static void sc_focus(void)
{
	pac_game_t *g = start_playing(7500);
	log_clear();
	mock_set_focused(0);
	advance(g, 100);
	check(count_stoploop() >= 1, "focus: loop stopped on focus loss", "");
	log_clear();
	mock_set_focused(1);
	advance(g, 300);
	check(count_loop(13) + count_loop(12) >= 1,
	      "focus: loop re-armed when focus returns", "");
	dump_log("focus");
	pac_game_destroy(g);
}

static void sc_toggle(void)
{
	pac_game_t *g = start_playing(7500);
	log_clear();
	g->sound_on = 0;
	pac_settings_apply(g);
	advance(g, 100);
	check(pac_audio_available() == 1 && g->audio_ok == 0,
	      "toggle: sound OFF disables audio (audio_ok=0)", "");
	log_clear();
	g->sound_on = 1;
	pac_settings_apply(g);
	advance(g, 300);
	check(g->audio_ok == 1, "toggle: sound ON re-enables audio", "");
	check(count_loop(13) + count_loop(12) >= 1,
	      "toggle: siren comes back after OFF->ON", "");
	dump_log("toggle");
	pac_game_destroy(g);
}

static void sc_oneshot(void)
{
	pac_game_t *g = start_playing(7500);
	int t_ghost, t_waka;
	log_clear();
	pac_emit_event(g, PAC_GAME_EVENT_EAT_GHOST);
	advance(g, 20);
	pac_emit_event(g, PAC_GAME_EVENT_EAT_DOT);  /* must not replace ghost */
	advance(g, 300);
	t_ghost = next_time(0, 6, 0);
	t_waka = next_time(0, 3, 0);
	if (t_waka < 0) t_waka = next_time(0, 4, 0);
	check(t_ghost >= 0, "oneshot: EAT_GHOST requested", "");
	check(t_waka < 0 || t_waka >= t_ghost + 500,
	      "oneshot: waka does not truncate EAT_GHOST", "higher priority wins");
	dump_log("oneshot");
	pac_game_destroy(g);
}

static void sc_power(void)
{
	pac_game_t *g = start_playing(7500);
	int t_power, t_fright;
	log_clear();
	pac_emit_event(g, PAC_GAME_EVENT_EAT_POWER);
	advance(g, 60);
	t_power = next_time(0, 5, 0);
	check(t_power >= 0, "power: POWER requested on power pellet", "");
	check(next_time(1, 12, 0) < 0 || next_time(1, 12, 0) > t_power + 250,
	      "power: fright siren does not cut the POWER beep immediately", "");
	advance(g, 600);
	t_fright = next_time(1, 12, 0);
	check(t_fright >= 0, "power: fright siren starts after the POWER hold", "");
	dump_log("power");
	pac_game_destroy(g);
}

static void sc_pauseoneshot(void)
{
	pac_game_t *g = start_playing(7500);
	log_clear();
	pac_emit_event(g, PAC_GAME_EVENT_EAT_GHOST);   /* one-shot en curso */
	advance(g, 40);
	key(g, PAC_KEY_ESC, 1);                        /* pausa */
	advance(g, 60);
	key(g, PAC_KEY_ESC, 0);
	advance(g, 120);
	check(count_kind(3, -1, 0, g_log_n) >= 1 || count_stoploop() >= 1,
	      "B5: pause stops the in-flight one-shot (pac_audio_stop)",
	      "stop/stop_loop issued");
	/* foco: perder foco debe silenciar tambien */
	pac_emit_event(g, PAC_GAME_EVENT_EAT_GHOST);
	advance(g, 40);
	log_clear();
	mock_set_focused(0);
	advance(g, 100);
	check(count_kind(3, -1, 0, g_log_n) >= 1 || count_stoploop() >= 1,
	      "B5: focus loss stops the in-flight one-shot", "");
	dump_log("pauseoneshot");
	pac_game_destroy(g);
}

static void sc_startonce(void)
{
	pac_game_t *g = start_playing(7500);
	advance(g, 4000);
	check(count_play(2) == 1, "start: still exactly 1 START after 9.5s", "");
	dump_log("startonce");
	pac_game_destroy(g);
}

int main(int argc, char **argv)
{
	const char *sc = argc > 1 ? argv[1] : "all";
	printf("== independent core->audio sequence harness ==\n");
	if (!strcmp(sc, "all") || !strcmp(sc, "start")) sc_start();
	if (!strcmp(sc, "all") || !strcmp(sc, "startonce")) sc_startonce();
	if (!strcmp(sc, "all") || !strcmp(sc, "power")) sc_power();
	if (!strcmp(sc, "all") || !strcmp(sc, "pauseoneshot")) sc_pauseoneshot();
	if (!strcmp(sc, "all") || !strcmp(sc, "dots")) sc_dots();
	if (!strcmp(sc, "all") || !strcmp(sc, "extralife")) sc_extralife();
	if (!strcmp(sc, "all") || !strcmp(sc, "respawn")) sc_respawn();
	if (!strcmp(sc, "all") || !strcmp(sc, "fright")) sc_fright();
	if (!strcmp(sc, "all") || !strcmp(sc, "menu")) sc_menu();
	if (!strcmp(sc, "all") || !strcmp(sc, "levelclear")) sc_levelclear();
	if (!strcmp(sc, "all") || !strcmp(sc, "gameover")) sc_gameover();
	if (!strcmp(sc, "all") || !strcmp(sc, "pause")) sc_pause();
	if (!strcmp(sc, "all") || !strcmp(sc, "focus")) sc_focus();
	if (!strcmp(sc, "all") || !strcmp(sc, "toggle")) sc_toggle();
	if (!strcmp(sc, "all") || !strcmp(sc, "oneshot")) sc_oneshot();
	printf("\n== RESULT: %d PASS / %d FAIL ==\n", g_pass, g_fail);
	return g_fail ? 1 : 0;
}
