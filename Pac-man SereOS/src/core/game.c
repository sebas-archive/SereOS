/* PAC-MAN SereOS - nucleo compartido: maquina de estados del juego
 *
 * Logica comun a los backends SereOS y Linux: estados (menu, instrucciones,
 * record, juego, pausa, game over, nivel completado), puntuacion, vidas,
 * niveles, frutas, record persistente y marcadores de QA. No incluye
 * cabeceras del sistema operativo ni SDL: todo pasa por pac_platform.h.
 */
#include <stdint.h>
#include <stddef.h>
#include <string.h>
#include "pacman.h"
#include "pac_platform.h"
#include "pac_game.h"
#include "pac_util.h"
#include "game_maze.h"
#include "game_ai.h"
#include "game_entities.h"
#include "game_input.h"
#include "game_audio.h"
#include "game_render.h"

#define PAC_SETTINGS_SOUND_KEY "sound"
#define PAC_SETTINGS_FULL_KEY  "fullscreen"
#define PAC_SETTINGS_CLASSIC_KEY "classic"

/* ------------------------------------------------------------------ */
/* utilidades                                                          */
/* ------------------------------------------------------------------ */
void pac_serial(const char *marker)
{
	if (!marker)
		return;
	pac_platform_log(marker);
}

static int serial_append(char *buf, int n, const char *text)
{
	while (text && *text && n < 120)
		buf[n++] = *text++;
	return n;
}

static int serial_append_int(char *buf, int n, int value)
{
	char tmp[12];
	int len = pac_itoa(value, tmp);
	int i;
	for (i = 0; i < len && n < 120; i++)
		buf[n++] = tmp[i];
	return n;
}

void serial_ghost_marker(const char *marker, int id)
{
	char buf[96];
	int n = 0;
	n = serial_append(buf, n, marker);
	n = serial_append(buf, n, " ");
	n = serial_append_int(buf, n, id);
	buf[n] = 0;
	pac_platform_log(buf);
}

static void serial_marker_int(const char *marker, int value)
{
	char buf[128];
	int n = 0;
	n = serial_append(buf, n, marker);
	n = serial_append(buf, n, " ");
	n = serial_append_int(buf, n, value);
	buf[n] = 0;
	pac_platform_log(buf);
}

static void serial_stats(pac_game_t *g)
{
	char buf[160];
	int n = 0;
	if (!g)
		return;
	n = serial_append(buf, n, "PAC_STATS dots=");
	n = serial_append_int(buf, n, g->dots_left);
	n = serial_append(buf, n, " power=");
	n = serial_append_int(buf, n, g->power_left);
	n = serial_append(buf, n, " score=");
	n = serial_append_int(buf, n, g->score);
	n = serial_append(buf, n, " level=");
	n = serial_append_int(buf, n, g->level);
	n = serial_append(buf, n, " lives=");
	n = serial_append_int(buf, n, g->lives);
	buf[n] = 0;
	pac_platform_log(buf);
}

int pac_random(pac_game_t *g)
{
	g->rng = g->rng * 1103515245u + 12345u;
	return (int)((g->rng >> 16) & 0x7FFFu);
}

void pac_add_score(pac_game_t *g, int points)
{
	if (!g)
		return;
	g->score += points;
	if (g->score < 0)
		g->score = 0;
	if (g->score > g->high_score)
		g->high_score = g->score;
	pac_check_extra_life(g);
}

void pac_check_extra_life(pac_game_t *g)
{
	if (!g || g->extra_life_given)
		return;
	if (g->score >= PAC_EXTRA_LIFE_AT) {
		g->extra_life_given = 1;
		g->lives++;
		if (g->lives > 9)
			g->lives = 9;
		pac_sound_play(g, PAC_SFX_EXTRA_LIFE);
	}
}

void pac_record_load(pac_game_t *g)
{
	char buf[24];
	int n;

	if (!g)
		return;
	g->high_score = 0;
	memset(buf, 0, sizeof(buf));
	n = pac_storage_read(PAC_RECORD_KEY, buf, (int)(sizeof(buf) - 1));
	if (n <= 0)
		return;
	if (n < (int)sizeof(buf))
		buf[n] = 0;
	else
		buf[sizeof(buf) - 1] = 0;
	g->high_score = pac_atoi(buf);
	if (g->high_score < 0)
		g->high_score = 0;
}

/* ------------------------------------------------------------------ */
/* settings persistentes y continuar partida                           */
/* ------------------------------------------------------------------ */
static int read_setting(const char *key, int def)
{
	char buf[12];
	int n = pac_storage_read(key, buf, (int)sizeof(buf) - 1);
	if (n <= 0)
		return def;
	buf[n] = 0;
	return pac_atoi(buf) ? 1 : 0;
}

static void write_setting(const char *key, int value)
{
	char buf[2];
	buf[0] = value ? '1' : '0';
	buf[1] = 0;
	(void)pac_storage_write(key, buf, 1);
}

void pac_settings_load(pac_game_t *g)
{
	if (!g)
		return;
	g->sound_on = read_setting(PAC_SETTINGS_SOUND_KEY, 1);
	g->fullscreen = read_setting(PAC_SETTINGS_FULL_KEY, 0);
	g->classic = read_setting(PAC_SETTINGS_CLASSIC_KEY, 1);
}

void pac_settings_save(pac_game_t *g)
{
	if (!g)
		return;
	write_setting(PAC_SETTINGS_SOUND_KEY, g->sound_on);
	write_setting(PAC_SETTINGS_FULL_KEY, g->fullscreen);
	write_setting(PAC_SETTINGS_CLASSIC_KEY, g->classic);
}

void pac_settings_apply(pac_game_t *g)
{
	if (!g)
		return;
	if (!g->sound_on) {
		/* para loop/one-shot y limpia el estado antes de silenciar */
		pac_sound_stop(g);
		g->audio_ok = 0;
	} else {
		g->audio_ok = pac_audio_available();
		/* al reactivar, reset para que update_siren rearme la sirena */
		pac_sound_stop(g);
	}
	(void)pac_platform_set_fullscreen(g->fullscreen);
}

static void save_continue(pac_game_t *g)
{
	pac_game_t *snap;
	void *old;

	if (!g)
		return;
	old = g->continue_snapshot;
	snap = (pac_game_t *)pac_alloc(sizeof(*snap));
	if (!snap)
		return;
	memcpy(snap, g, sizeof(*snap));
	snap->continue_snapshot = NULL;
	snap->wants_close = 0;
	if (old)
		pac_free(old);
	g->continue_snapshot = snap;
	g->continue_valid = 1;
}

static void clear_continue(pac_game_t *g)
{
	if (!g)
		return;
	if (g->continue_snapshot)
		pac_free(g->continue_snapshot);
	g->continue_snapshot = NULL;
	g->continue_valid = 0;
}

static void restore_continue(pac_game_t *g)
{
	pac_game_t *snap;
	pac_game_t tmp;

	if (!g || !g->continue_valid || !g->continue_snapshot)
		return;
	snap = g->continue_snapshot;
	tmp = *snap;
	tmp.continue_snapshot = snap;
	tmp.wants_close = 0;
	*g = tmp;
	/* el audio del snapshot puede estar obsoleto (menu sin loop): resync */
	pac_sound_stop(g);
	g->state = PAC_STATE_PLAYING;
	g->state_prev = PAC_STATE_PLAYING;
	g->ready_ms = PAC_READY_MS;
	g->pause_sel = 0;
}

int pac_menu_item_enabled(const pac_game_t *g, int item)
{
	if (!g)
		return 0;
	if (item == 1)
		return g->continue_valid ? 1 : 0;
	return 1;
}

void pac_record_save(pac_game_t *g)
{
	char buf[24];
	int n;

	if (!g)
		return;
	if (g->high_score <= 0 && g->score <= 0)
		return;
	if (g->score > g->high_score)
		g->high_score = g->score;
	n = pac_itoa(g->high_score, buf);
	if (n > 0)
		(void)pac_storage_write(PAC_RECORD_KEY, buf, n);
}

/* ------------------------------------------------------------------ */
/* eventos de juego (puntos, sonido y estados)                         */
/* ------------------------------------------------------------------ */
void pac_emit_event(pac_game_t *g, pac_game_event_t ev)
{
	if (!g)
		return;
	switch (ev) {
	case PAC_GAME_EVENT_EAT_DOT:
		g->digest_ms = PAC_STEP_MS;
		pac_add_score(g, 10);
		pac_sound_play(g, (g->dots_eaten & 1) ? PAC_SFX_WAKA2 : PAC_SFX_WAKA1);
		/* sin mezclador: evita que la sirena se reinicie en cada punto */
		g->siren_grace_ms = 300;
		g->global_release_ms = 0;
		break;
	case PAC_GAME_EVENT_EAT_POWER:
		g->digest_ms = PAC_STEP_MS * 3;
		pac_add_score(g, 50);
		pac_sound_play(g, PAC_SFX_POWER);
		pac_ai_frighten(g);
		g->global_release_ms = 0;
		break;
	case PAC_GAME_EVENT_EAT_GHOST:
		pac_sound_play(g, PAC_SFX_EAT_GHOST);
		break;
	case PAC_GAME_EVENT_EAT_FRUIT:
		pac_sound_play(g, PAC_SFX_EAT_FRUIT);
		break;
	case PAC_GAME_EVENT_DEATH:
		pac_sound_play(g, PAC_SFX_DEATH);
		g->death_ms = PAC_DEATH_MS;
		g->siren_grace_ms = 0;
		break;
	case PAC_GAME_EVENT_EXTRA_LIFE:
		pac_sound_play(g, PAC_SFX_EXTRA_LIFE);
		break;
	case PAC_GAME_EVENT_LEVEL_CLEAR:
		pac_sound_play(g, PAC_SFX_LEVEL_CLEAR);
		break;
	default:
		break;
	}
}

/* ------------------------------------------------------------------ */
/* estados y arranque                                                  */
/* ------------------------------------------------------------------ */
void pac_set_state(pac_game_t *g, pac_state_t state, const char *marker)
{
	if (!g)
		return;
	g->state_prev = g->state;
	g->state = (int)state;
	if (marker)
		pac_serial(marker);

	switch (state) {
	case PAC_STATE_PAUSED:
		/* la pausa silencia TODO (sirena y one-shots en curso); al
		 * reanudar update_siren rearmara la sirena, no el one-shot. */
		pac_sound_stop(g);
		break;
	case PAC_STATE_GAMEOVER:
		pac_sound_set_siren(g, PAC_SFX_NONE);
		pac_sound_play(g, PAC_SFX_GAME_OVER);
		pac_record_save(g);
		break;
	case PAC_STATE_LEVEL_CLEAR:
		pac_sound_set_siren(g, PAC_SFX_NONE);
		pac_sound_play(g, PAC_SFX_LEVEL_CLEAR);
		pac_record_save(g);
		break;
	case PAC_STATE_MENU:
		pac_sound_set_siren(g, PAC_SFX_NONE);
		break;
	default:
		break;
	}

}

void pac_start_level(pac_game_t *g)
{
	if (!g)
		return;
	pac_maze_reset(g);
	pac_entities_init_level(g);
	pac_ai_level_init(g);
	serial_marker_int("LEVEL_START", g->level);
	serial_stats(g);

	g->ready_ms = PAC_READY_MS;
	g->death_ms = 0;
	g->level_clear_ms = 0;
	g->fruit_visible_ms = 0;
	g->fruit_flash_ms = 0;
	g->fruit_index = pac_ai_level_fruit(g);
	g->fruit_value = pac_ai_level_fruit_value(g);
	g->popup_ms = 0;
	g->global_release_ms = 0;
	g->siren_grace_ms = 0;

	pac_sound_set_siren(g, PAC_SFX_NONE);
}

void pac_start_new_game(pac_game_t *g)
{
	if (!g)
		return;
	/* corta el audio de la partida anterior (loop y one-shot en curso) */
	pac_sound_stop(g);
	g->score = 0;
	g->lives = PAC_LIVES_START;
	g->level = 1;
	g->extra_life_given = 0;
	g->fruit_eaten_count = 0;
	memset(g->fruit_counts, 0, sizeof(g->fruit_counts));
	pac_start_level(g);
	g->ready_ms = g->audio_ok ? PAC_READY_START_MS : PAC_READY_MS;
	g->state = PAC_STATE_PLAYING;
	g->state_prev = PAC_STATE_PLAYING;
	pac_serial("GAME_START");
	pac_sound_set_siren(g, PAC_SFX_NONE);
	pac_sound_play(g, PAC_SFX_START);
	/* el Game Start no se interrumpe con sirena: hold alineado con READY */
	g->audio_hold_ms = 4500;
	g->siren_grace_ms = 0;
}

void pac_after_pacman_death(pac_game_t *g)
{
	if (!g)
		return;
	g->lives--;
	if (g->lives <= 0) {
		g->lives = 0;
		pac_set_state(g, PAC_STATE_GAMEOVER, "GAME_OVER");
		return;
	}
	pac_entities_reset_positions(g);
	pac_ai_after_death(g);
	serial_marker_int("LIFE_START", g->lives);
	serial_stats(g);
	/* contadores relativos tras morir: 7 / 17 / 32 dots (Dossier p.20) */
	g->ghosts[PAC_GHOST_PINKY].exit_dots = g->dots_eaten + 7;
	g->ghosts[PAC_GHOST_INKY].exit_dots = g->dots_eaten + 17;
	g->ghosts[PAC_GHOST_CLYDE].exit_dots = g->dots_eaten + 32;
	g->ready_ms = PAC_READY_MS;
	g->death_ms = 0;
	g->fright_ms = 0;
	g->fruit_visible_ms = 0;
	g->global_release_ms = 0;
	g->siren_grace_ms = 0;
	{
		int i;
		for (i = 0; i < PAC_GHOST_COUNT; i++)
			g->ghosts[i].scared = 0;
	}

}

/* Sirena segun el estado del juego (audio/audio.h de SereOS) */
static void update_siren(pac_game_t *g)
{
	int i;
	int eyes_returning = 0;

	if (!g || g->state != PAC_STATE_PLAYING || g->ready_ms > 0 ||
	    g->death_ms > 0 || g->audio_hold_ms > 0 || g->siren_grace_ms > 0) {
		pac_sound_set_siren(g, PAC_SFX_NONE);
		return;
	}
	/* ojos de fantasma comidos volviendo a la casa: en Paku-Paku el
	 * "GhostRespawn" es un LOOP que se mantiene hasta que los ojos llegan
	 * y vuelve el ambiente (modSoundFX.bas:120-132). */
	for (i = 0; i < PAC_GHOST_COUNT; i++) {
		if (g->ghosts[i].state == PAC_GHOST_EATEN) {
			eyes_returning = 1;
			break;
		}
	}
	if (eyes_returning) {
		pac_sound_set_siren(g, PAC_SFX_GHOST_RESPAWN);
		return;
	}
	if (g->fright_ms > 0) {
		/* hunter siren = ambiente del power pill (slot 12, WAV 133 ms) */
		pac_sound_set_siren(g, PAC_SFX_SIREN_CHASE);
		return;
	}
	/* hunted siren = ambiente normal (slot 13, WAV 400 ms) */
	pac_sound_set_siren(g, PAC_SFX_SIREN_HUNT);
}

/* ------------------------------------------------------------------ */
/* logica por estado                                                   */
/* ------------------------------------------------------------------ */
static void tick_attract(pac_game_t *g)
{
	if (g->input.confirm_pressed) {
		pac_sound_play(g, PAC_SFX_MENU);
		g->menu_sel = 0;
		pac_set_state(g, PAC_STATE_MENU, "GAME_MENU");
		return;
	}
	if (g->input.esc_pressed || g->input.quit_pressed)
		g->wants_close = 1;
}

static void tick_menu(pac_game_t *g)
{
	int guard = PAC_MENU_ITEMS;

	{
		int dir = 0;
		if (g->input.up_pressed) dir = -1;
		else if (g->input.down_pressed) dir = 1;
		if (dir != 0) {
			do {
				g->menu_sel = (g->menu_sel + dir + PAC_MENU_ITEMS) %
				              PAC_MENU_ITEMS;
			} while (!pac_menu_item_enabled(g, g->menu_sel) && guard-- > 0);
			pac_sound_play(g, PAC_SFX_MENU);
		}
	}
	if (!g->input.confirm_pressed) {
		if (g->input.esc_pressed)
			g->wants_close = 1;
		return;
	}
	pac_sound_play(g, PAC_SFX_MENU);
	switch (g->menu_sel) {
	case 0:
		clear_continue(g);
		pac_start_new_game(g);
		break;
	case 1:
		restore_continue(g);
		break;
	case 2:
		pac_set_state(g, PAC_STATE_RECORD, NULL);
		break;
	case 3:
		pac_set_state(g, PAC_STATE_INSTRUCTIONS, NULL);
		break;
	case 4:
		g->settings_sel = 0;
		pac_set_state(g, PAC_STATE_SETTINGS, NULL);
		break;
	default:
		g->wants_close = 1;
		break;
	}
}

static void tick_settings(pac_game_t *g)
{
	int v;
	if (g->input.up_pressed)
		g->settings_sel = (g->settings_sel + PAC_SETTINGS_ITEMS - 1) %
		                  PAC_SETTINGS_ITEMS;
	if (g->input.down_pressed)
		g->settings_sel = (g->settings_sel + 1) % PAC_SETTINGS_ITEMS;
	if (g->input.esc_pressed) {
		pac_set_state(g, (g->state_prev == PAC_STATE_PAUSED) ?
		              PAC_STATE_PAUSED : PAC_STATE_MENU, NULL);
		return;
	}
	if (!(g->input.confirm_pressed || g->input.left_pressed ||
	      g->input.right_pressed))
		return;
	switch (g->settings_sel) {
	case 0: g->sound_on = !g->sound_on; v = g->sound_on; break;
	case 1: g->fullscreen = !g->fullscreen; v = g->fullscreen; break;
	default: g->classic = !g->classic; v = g->classic; break;
	}
	pac_settings_apply(g);
	pac_settings_save(g);
	(void)v;
}

static void tick_paused(pac_game_t *g)
{
	if (g->input.up_pressed) {
		g->pause_sel = (g->pause_sel + PAC_PAUSE_ITEMS - 1) % PAC_PAUSE_ITEMS;
		pac_sound_play(g, PAC_SFX_MENU);
	}
	if (g->input.down_pressed) {
		g->pause_sel = (g->pause_sel + 1) % PAC_PAUSE_ITEMS;
		pac_sound_play(g, PAC_SFX_MENU);
	}
	if (g->input.restart_pressed) {
		clear_continue(g);
		pac_start_new_game(g);
		return;
	}
	if (g->input.quit_pressed) {
		save_continue(g);
		pac_set_state(g, PAC_STATE_MENU, NULL);
		return;
	}
	if (!g->input.confirm_pressed && !g->input.esc_pressed)
		return;
	if (g->input.esc_pressed) {
		pac_sound_stop(g);
		g->state = PAC_STATE_PLAYING;
		return;
	}
	switch (g->pause_sel) {
	case 0:
		pac_sound_stop(g);
		g->state = PAC_STATE_PLAYING;
		break;
	case 1:
		clear_continue(g);
		pac_start_new_game(g);
		break;
	case 2:
		g->settings_sel = 0;
		pac_set_state(g, PAC_STATE_SETTINGS, NULL);
		break;
	case 3:
		save_continue(g);
		pac_set_state(g, PAC_STATE_MENU, NULL);
		break;
	default:
		g->wants_close = 1;
		break;
	}
}

static void tick_gameover(pac_game_t *g)
{
	if (g->input.up_pressed)
		g->over_sel = (g->over_sel + PAC_OVER_ITEMS - 1) % PAC_OVER_ITEMS;
	if (g->input.down_pressed)
		g->over_sel = (g->over_sel + 1) % PAC_OVER_ITEMS;
	if (g->input.esc_pressed) {
		pac_set_state(g, PAC_STATE_MENU, NULL);
		return;
	}
	if (!g->input.confirm_pressed && !g->input.quit_pressed)
		return;
	if (g->input.quit_pressed) {
		pac_set_state(g, PAC_STATE_MENU, NULL);
		return;
	}
	switch (g->over_sel) {
	case 0:
		clear_continue(g);
		pac_start_new_game(g);
		break;
	case 1:
		pac_set_state(g, PAC_STATE_MENU, NULL);
		break;
	default:
		g->wants_close = 1;
		break;
	}
}

static void spawn_fruit_if_needed(pac_game_t *g)
{
	if (g->fruit_visible_ms > 0 || g->fruit_flash_ms > 0)
		return;
	if (g->dots_eaten == PAC_FRUIT_DOT_1 || g->dots_eaten == PAC_FRUIT_DOT_2) {
		g->fruit_visible_ms = PAC_FRUIT_MS;
		g->fruit_index = pac_ai_level_fruit(g);
		g->fruit_value = pac_ai_level_fruit_value(g);
		/* la aparicion es silenciosa; el sonido va al comerla (EAT_FRUIT) */
	}
}

static void tick_playing(pac_game_t *g, int dt_ms)
{
	if (g->input.esc_pressed) {
		pac_set_state(g, PAC_STATE_PAUSED, "GAME_PAUSE");
		return;
	}
	if (g->input.restart_pressed) {
		pac_start_new_game(g);
		return;
	}

	/* animacion de muerte: congela el mundo */
	if (g->death_ms > 0) {
		g->death_ms -= dt_ms;
		g->pac.death_ms = g->death_ms > 0 ? g->death_ms : 0;
		if (g->death_ms <= 0) {
			g->death_ms = 0;
			g->pac.death_ms = 0;
			pac_after_pacman_death(g);
		}
		return;
	}

	/* READY!: cuenta atras sin mover a nadie */
	if (g->ready_ms > 0) {
		g->ready_ms -= dt_ms;
		if (g->ready_ms < 0)
			g->ready_ms = 0;
		return;
	}

	if (g->fruit_visible_ms > 0) {
		g->fruit_visible_ms -= dt_ms;
		if (g->fruit_visible_ms < 0)
			g->fruit_visible_ms = 0;
	}
	if (g->fruit_flash_ms > 0) {
		g->fruit_flash_ms -= dt_ms;
		if (g->fruit_flash_ms < 0)
			g->fruit_flash_ms = 0;
	}
	if (g->popup_ms > 0) {
		g->popup_ms -= dt_ms;
		if (g->popup_ms < 0)
			g->popup_ms = 0;
	}

	if (g->digest_ms > 0)
		g->digest_ms -= dt_ms;
	pac_ai_update(g, dt_ms);
	if (g->digest_ms <= 0)
		pac_entities_update_pacman(g, dt_ms);
	pac_entities_update_ghosts(g, dt_ms);

	if (pac_entities_collisions(g) == PAC_GAME_EVENT_DEATH)
		return;

	spawn_fruit_if_needed(g);

	/* nivel completado: todos los dots y power pills comidos */
	if (g->dots_left <= 0 && g->power_left <= 0) {
		g->level_clear_ms = PAC_LEVEL_CLEAR_MS;
		pac_set_state(g, PAC_STATE_LEVEL_CLEAR, "GAME_WIN");
	}
}

static void tick_level_clear(pac_game_t *g, int dt_ms)
{
	if (g->level_clear_ms > 0) {
		g->level_clear_ms -= dt_ms;
		if (g->level_clear_ms > 0)
			return;
	}
	g->level++;
	if (g->level > 255)
		g->level = 255;
	pac_start_level(g);
	g->state = PAC_STATE_PLAYING;
	g->state_prev = PAC_STATE_PLAYING;
}

static void game_tick(pac_game_t *g, int dt_ms)
{
	g->anim_ms += (uint32_t)dt_ms;
	if (g->audio_hold_ms > 0) {
		g->audio_hold_ms -= dt_ms;
		if (g->audio_hold_ms <= 0) {
			g->audio_hold_ms = 0;
			g->audio_oneshot = PAC_SFX_NONE;
		}
	}
	if (g->siren_grace_ms > 0) {
		g->siren_grace_ms -= dt_ms;
		if (g->siren_grace_ms < 0)
			g->siren_grace_ms = 0;
	}
	g->frame++;
	pac_sound_update(g);

	switch (g->state) {
	case PAC_STATE_ATTRACT:
		tick_attract(g);
		break;
	case PAC_STATE_MENU:
		tick_menu(g);
		break;
	case PAC_STATE_SETTINGS:
		tick_settings(g);
		break;
	case PAC_STATE_INSTRUCTIONS:
		if (g->input.confirm_pressed || g->input.esc_pressed)
			pac_set_state(g, PAC_STATE_MENU, NULL);
		break;
	case PAC_STATE_RECORD:
		if (g->input.confirm_pressed || g->input.esc_pressed)
			pac_set_state(g, PAC_STATE_MENU, NULL);
		break;
	case PAC_STATE_PLAYING:
		tick_playing(g, dt_ms);
		break;
	case PAC_STATE_PAUSED:
		tick_paused(g);
		break;
	case PAC_STATE_GAMEOVER:
		tick_gameover(g);
		break;
	case PAC_STATE_LEVEL_CLEAR:
		tick_level_clear(g, dt_ms);
		break;
	default:
		break;
	}

	update_siren(g);
	pac_input_consume(g);
}


/* ------------------------------------------------------------------ */
/* API publica para los backends (include/pacman.h)                    */
/* ------------------------------------------------------------------ */
pac_game_t *pac_game_create(void)
{
	pac_game_t *g = (pac_game_t *)pac_alloc(sizeof(pac_game_t));

	if (!g) {
		pac_platform_log("GAME_OOM");
		return NULL;
	}
	memset(g, 0, sizeof(*g));
	g->state = PAC_STATE_ATTRACT;
	g->state_prev = PAC_STATE_ATTRACT;
	g->menu_sel = 0;
	g->pause_sel = 0;
	g->over_sel = 0;
	g->settings_sel = 0;
	g->lives = PAC_LIVES_START;
	g->level = 1;
	g->rng = 0x5041434Du;   /* "PAC M" */
	g->last_time_ms = pac_time_ms();
	g->last_draw_ms = 0;
	g->acc_ms = 0;
	g->anim_ms = 0;
	g->frame = 0;
	g->wants_close = 0;
	pac_platform_content_rect(&g->viewport);

	pac_input_init(g);
	pac_record_load(g);
	pac_settings_load(g);
	pac_sound_init(g);
	pac_settings_apply(g);
	pac_maze_init(g);
	pac_entities_init_level(g);
	pac_ai_level_init(g);
	g->ready_ms = 0;

	pac_serial("GAME_MENU");
	return g;
}

void pac_game_destroy(pac_game_t *g)
{
	if (!g)
		return;
	pac_sound_stop(g);
	pac_record_save(g);
	pac_settings_save(g);
	clear_continue(g);
	pac_platform_log("GAME_EXIT");
	pac_free(g);
}

void pac_game_event(pac_game_t *g, const pac_event_t *ev)
{
	if (!g || !ev)
		return;
	pac_input_event(g, ev);
}

int pac_game_tick(pac_game_t *g)
{
	uint32_t now, elapsed;
	int steps = 0;
	int redraw = 0;

	if (!g)
		return 0;

	now = pac_time_ms();
	elapsed = now - g->last_time_ms;
	g->last_time_ms = now;
	if (elapsed > PAC_MAX_ELAPSED_MS)
		elapsed = PAC_MAX_ELAPSED_MS;

	if (pac_platform_minimized()) {
		g->acc_ms = 0;
		/* no dejar sirena ni one-shots sonando con la ventana minimizada */
		if (g->siren != PAC_SFX_NONE || g->audio_hold_ms > 0 ||
		    g->audio_oneshot != PAC_SFX_NONE || g->siren_grace_ms > 0)
			pac_sound_stop(g);
		return 0;
	}
	/* si la ventana pierde el foco se congela (evita muertes injustas) */
	if (!pac_platform_focused()) {
		g->acc_ms = 0;
		g->last_draw_ms = now;
		if (g->siren != PAC_SFX_NONE || g->audio_hold_ms > 0 ||
		    g->audio_oneshot != PAC_SFX_NONE || g->siren_grace_ms > 0)
			pac_sound_stop(g);
		return 0;
	}

	pac_input_begin_frame(g, 1);

	g->acc_ms += elapsed;
	while (g->acc_ms >= PAC_STEP_MS && steps < PAC_MAX_CATCHUP) {
		game_tick(g, PAC_STEP_MS);
		g->acc_ms -= PAC_STEP_MS;
		steps++;
	}
	if (g->acc_ms > PAC_STEP_MS * 4)
		g->acc_ms = 0;

	/* presentacion a 30 fps: el backend redibuja si devolvemos 1 */
	if (now - g->last_draw_ms >= PAC_RENDER_MS) {
		redraw = 1;
		g->last_draw_ms = now;
	}
	return redraw;
}

void pac_game_draw(pac_game_t *g, const pac_rect_t *viewport)
{
	if (!g)
		return;
	if (viewport)
		g->viewport = *viewport;
	else
		pac_platform_content_rect(&g->viewport);
	pac_render_draw(g);
}

int pac_game_wants_close(const pac_game_t *g)
{
	return g ? g->wants_close : 1;
}

const pac_rect_t *pac_game_viewport(const pac_game_t *g)
{
	static const pac_rect_t empty = { 0, 0, 0, 0 };
	return g ? &g->viewport : &empty;
}

void pac_game_debug_scene(pac_game_t *g, const char *scene)
{
	if (!g || !scene)
		return;
	if (strcmp(scene, "attract") == 0) {
		g->state = PAC_STATE_ATTRACT;
	} else if (strcmp(scene, "menu") == 0) {
		g->state = PAC_STATE_MENU;
	} else if (strcmp(scene, "settings") == 0) {
		g->state = PAC_STATE_SETTINGS;
		g->settings_sel = 0;
	} else if (strcmp(scene, "gamestart") == 0) {
		pac_start_new_game(g);   /* conserva READY 4,5 s: Start limpio */
	} else if (strcmp(scene, "ghostcapture") == 0) {
		/* QA: fuerza una captura real (ojos/retorno) */
		pac_start_new_game(g);
		g->ready_ms = 0;
		pac_ai_frighten(g);
		g->ghosts[0].state = PAC_GHOST_NORMAL;
		g->ghosts[0].scared = 1;
		g->ghosts[0].x = g->pac.x;
		g->ghosts[0].y = g->pac.y;
		(void)pac_entities_collisions(g);
	} else if (strcmp(scene, "death") == 0) {
		/* QA: come dots/power antes de forzar la muerte para evidenciar
		 * que el laberinto NO se reinicia. */
		int i;
		pac_start_new_game(g);
		g->ready_ms = 0;
		for (i = 0; i < PAC_COLS * PAC_ROWS; i++) {
			if (g->maze.tiles[i] == PAC_TILE_DOT) {
				(void)pac_maze_consume(g, i % PAC_COLS, i / PAC_COLS);
				g->score += 10;
				if (g->score > g->high_score)
					g->high_score = g->score;
				if (g->dots_eaten >= 10)
					break;
			}
		}
		serial_stats(g);
		g->ghosts[0].state = PAC_GHOST_NORMAL;
		g->ghosts[0].scared = 0;
		g->ghosts[0].x = g->pac.x;
		g->ghosts[0].y = g->pac.y;
		(void)pac_entities_collisions(g);
	} else if (strcmp(scene, "play") == 0) {
		pac_start_new_game(g);
		g->ready_ms = 0;
	} else if (strcmp(scene, "pause") == 0) {
		pac_start_new_game(g);
		g->ready_ms = 0;
		pac_set_state(g, PAC_STATE_PAUSED, "GAME_PAUSE");
	} else if (strcmp(scene, "gameover") == 0) {
		pac_start_new_game(g);
		g->ready_ms = 0;
		g->lives = 0;
		g->score = 1500;          /* QA: permite verificar el record persistente */
		g->high_score = 1500;
		pac_set_state(g, PAC_STATE_GAMEOVER, "GAME_OVER");
	} else if (strcmp(scene, "victory") == 0) {
		pac_start_new_game(g);
		g->ready_ms = 0;
		g->dots_left = 0;
		g->power_left = 0;
		pac_set_state(g, PAC_STATE_LEVEL_CLEAR, "GAME_WIN");
		g->level_clear_ms = 100000;   /* QA: mantener la pantalla de nivel */
	} else if (strcmp(scene, "frightened") == 0) {
		pac_start_new_game(g);
		g->ready_ms = 0;
		pac_ai_frighten(g);
	}
}
