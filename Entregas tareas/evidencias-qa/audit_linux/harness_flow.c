/* harness_flow.c - traza de la cadena game.c -> game_audio.c -> pac_audio_*
 * -> SDL, SIN MODIFICAR las fuentes del proyecto.
 *
 * Se enlaza contra los .o ya compilados por `make linux` usando ld --wrap
 * para interceptar (solo en el arnes) las funciones de audio y las llamadas
 * SDL realmente ejecutadas por el backend.
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <SDL2/SDL.h>

#include "pac_platform.h"
#include "pacman.h"
#include "pac_game.h"
#include "game_audio.h"

Uint32 __real_SDL_GetTicks(void);
int __real_SDL_OpenAudioDevice(const char *, int, const SDL_AudioSpec *,
                               SDL_AudioSpec *, int);
int __real_SDL_QueueAudio(SDL_AudioDeviceID, const void *, Uint32);
void __real_SDL_ClearQueuedAudio(SDL_AudioDeviceID);
Uint32 __real_SDL_GetQueuedAudioSize(SDL_AudioDeviceID);
void __real_SDL_CloseAudioDevice(SDL_AudioDeviceID);
void __real_pac_audio_play(int);
void __real_pac_audio_loop(int);
void __real_pac_audio_stop_loop(void);
void __real_pac_audio_stop(void);
void __real_pac_sound_play(pac_game_t *, int);
void __real_pac_sound_set_siren(pac_game_t *, int);
void __real_pac_sound_stop(pac_game_t *);

static SDL_AudioDeviceID g_pcm_id, g_synth_id;
static int g_start_plays, g_play_calls[64], g_loop_calls[64];
static FILE *g_log;

#define LOG(...) do { fprintf(g_log, __VA_ARGS__); fputc('\n', g_log); fflush(g_log); } while (0)
#define T (unsigned)__real_SDL_GetTicks()

static const char *state_name(int s)
{
	switch (s) {
	case PAC_STATE_ATTRACT: return "ATTRACT";
	case PAC_STATE_MENU: return "MENU";
	case PAC_STATE_SETTINGS: return "SETTINGS";
	case PAC_STATE_INSTRUCTIONS: return "INSTRUCTIONS";
	case PAC_STATE_RECORD: return "RECORD";
	case PAC_STATE_PLAYING: return "PLAYING";
	case PAC_STATE_PAUSED: return "PAUSED";
	case PAC_STATE_GAMEOVER: return "GAMEOVER";
	case PAC_STATE_LEVEL_CLEAR: return "LEVEL_CLEAR";
	default: return "?";
	}
}

Uint32 __wrap_SDL_GetTicks(void)
{
	return __real_SDL_GetTicks();
}

Uint32 __wrap_SDL_GetQueuedAudioSize(SDL_AudioDeviceID dev)
{
	return __real_SDL_GetQueuedAudioSize(dev);
}

int __wrap_SDL_OpenAudioDevice(const char *name, int capture,
                               const SDL_AudioSpec *want, SDL_AudioSpec *have,
                               int changes)
{
	int id = __real_SDL_OpenAudioDevice(name, capture, want, have, changes);
	LOG("[%6u] SDL_OpenAudioDevice id=%d want{freq=%d fmt=0x%x ch=%d samples=%d}"
	    " -> have{freq=%d fmt=0x%x ch=%d}", T, id,
	    want ? want->freq : -1, want ? (unsigned)want->format : 0,
	    want ? want->channels : -1, want ? want->samples : 0,
	    have ? have->freq : -1, have ? (unsigned)have->format : 0,
	    have ? have->channels : -1);
	if (have && have->format == AUDIO_U8 && have->channels == 1 &&
	    have->freq == 11025)
		g_pcm_id = (SDL_AudioDeviceID)id;
	else
		g_synth_id = (SDL_AudioDeviceID)id;
	return id;
}

int __wrap_SDL_QueueAudio(SDL_AudioDeviceID dev, const void *data, Uint32 len)
{
	Uint32 before = __real_SDL_GetQueuedAudioSize(dev);
	LOG("[%6u]   SDL_QueueAudio dev=%u len=%u queued_before=%u queued_after=%u%s",
	    T, (unsigned)dev, len, before, before + len,
	    (dev == g_pcm_id) ? "  <== PCM" : "  <== SYNTH");
	return __real_SDL_QueueAudio(dev, data, len);
}

void __wrap_SDL_ClearQueuedAudio(SDL_AudioDeviceID dev)
{
	LOG("[%6u]   SDL_ClearQueuedAudio dev=%u queued_before=%u%s", T,
	    (unsigned)dev, __real_SDL_GetQueuedAudioSize(dev),
	    (dev == g_pcm_id) ? "  <== PCM" : "  <== SYNTH");
	__real_SDL_ClearQueuedAudio(dev);
}

void __wrap_SDL_CloseAudioDevice(SDL_AudioDeviceID dev)
{
	LOG("[%6u]   SDL_CloseAudioDevice dev=%u", T, (unsigned)dev);
	__real_SDL_CloseAudioDevice(dev);
}

void __wrap_pac_audio_play(int sfx)
{
	g_play_calls[sfx & 63]++;
	if (sfx == 2) g_start_plays++;
	LOG("[%6u] pac_audio_play(%d)  pcm_queued=%u", T, sfx,
	    g_pcm_id ? __real_SDL_GetQueuedAudioSize(g_pcm_id) : 0u);
	__real_pac_audio_play(sfx);
}

void __wrap_pac_audio_loop(int sfx)
{
	g_loop_calls[sfx & 63]++;
	LOG("[%6u] pac_audio_loop(%d)  pcm_queued=%u", T, sfx,
	    g_pcm_id ? __real_SDL_GetQueuedAudioSize(g_pcm_id) : 0u);
	__real_pac_audio_loop(sfx);
}

void __wrap_pac_audio_stop_loop(void)
{
	LOG("[%6u] pac_audio_stop_loop()  pcm_queued=%u", T,
	    g_pcm_id ? __real_SDL_GetQueuedAudioSize(g_pcm_id) : 0u);
	__real_pac_audio_stop_loop();
}

void __wrap_pac_audio_stop(void)
{
	LOG("[%6u] pac_audio_stop()", T);
	__real_pac_audio_stop();
}

void __wrap_pac_sound_play(pac_game_t *g, int sfx)
{
	LOG("[%6u] SOURCE pac_sound_play(slot=%d) state=%s hold=%d siren=%d"
	    " audio_ok=%d", T, sfx, g ? state_name(g->state) : "?", 
	    g ? g->audio_hold_ms : -1, g ? g->siren : -1,
	    g ? g->audio_ok : -1);
	__real_pac_sound_play(g, sfx);
	if (g)
		LOG("[%6u]   => hold=%d siren=%d", T, g->audio_hold_ms, g->siren);
}

void __wrap_pac_sound_set_siren(pac_game_t *g, int sfx)
{
	int old = g ? g->siren : -1;
	__real_pac_sound_set_siren(g, sfx);
	if (g && old != sfx)
		LOG("[%6u] SOURCE pac_sound_set_siren(%d->%d) state=%s hold=%d"
		    " fright=%d", T, old, sfx, state_name(g->state),
		    g->audio_hold_ms, g->fright_ms);
}

void __wrap_pac_sound_stop(pac_game_t *g)
{
	LOG("[%6u] SOURCE pac_sound_stop() state=%s", T,
	    g ? state_name(g->state) : "?");
	__real_pac_sound_stop(g);
}

static void sample(const pac_game_t *g, const char *tag)
{
	LOG("[%6u] STATE %-12s state=%s siren=%d hold=%d ready=%d death=%d"
	    " fright=%d dots_left=%d pcm_queued=%u", T, tag,
	    g ? state_name(g->state) : "?", g ? g->siren : -1,
	    g ? g->audio_hold_ms : -1, g ? g->ready_ms : -1,
	    g ? g->death_ms : -1, g ? g->fright_ms : -1,
	    g ? g->dots_left : -1,
	    g_pcm_id ? __real_SDL_GetQueuedAudioSize(g_pcm_id) : 0u);
}

static void step(pac_game_t *g, int ms)
{
	Uint32 t0 = __real_SDL_GetTicks();
	while ((int)(__real_SDL_GetTicks() - t0) < ms) {
		SDL_Delay(2);
		(void)pac_game_tick(g);
	}
}

static void send_key(pac_game_t *g, pac_key_t key, int pressed)
{
	pac_event_t ev;
	memset(&ev, 0, sizeof(ev));
	ev.type = pressed ? PAC_EVENT_KEY_DOWN : PAC_EVENT_KEY_UP;
	ev.key = (uint16_t)key;
	ev.pressed = (uint8_t)(pressed ? 1 : 0);
	ev.tick = __real_SDL_GetTicks();
	pac_game_event(g, &ev);
}

static void tap_key(pac_game_t *g, pac_key_t key)
{
	send_key(g, key, 1);
	step(g, 40);           /* un game_tick consume el flanco */
	send_key(g, key, 0);
	step(g, 40);
}

int main(int argc, char **argv)
{
	const char *sc = argc > 1 ? argv[1] : "start";
	pac_game_t *g;

	g_log = stdout;
	if (SDL_Init(0) != 0) {
		fprintf(stderr, "SDL_Init: %s\n", SDL_GetError());
		return 1;
	}
	if (!pac_platform_init()) {
		fprintf(stderr, "pac_platform_init fallo\n");
		return 1;
	}
	g = pac_game_create();
	if (!g)
		return 1;
	LOG("[%6u] ===== escenario %s =====", T, sc);
	sample(g, "inicio");

	if (strcmp(sc, "start") == 0) {
		tap_key(g, PAC_KEY_ENTER);          /* attract -> menu */
		sample(g, "tras-menu");
		tap_key(g, PAC_KEY_ENTER);          /* menu -> nueva partida */
		sample(g, "tras-start");
		for (int i = 0; i < 12; i++) {
			step(g, 500);
			sample(g, "t+");
		}
		LOG("[%6u] SUMMARY start_plays=%d loop_hunt=%d loop_chase=%d "
		    "loop_fright=%d", T, g_start_plays,
		    g_loop_calls[13], g_loop_calls[12], g_loop_calls[14]);
	} else if (strcmp(sc, "siren") == 0) {
		/* forzar PLAYING sin READY ni hold */
		g->state = PAC_STATE_PLAYING;
		g->ready_ms = 0;
		g->audio_hold_ms = 0;
		g->dots_left = 200;
		g->power_left = 4;
		step(g, 300);
		sample(g, "hunt");
		g->dots_left = 10;                 /* <=50 -> chase */
		step(g, 300);
		sample(g, "chase");
		g->fright_ms = 5000;               /* -> fright (SIN WAV) */
		step(g, 300);
		sample(g, "fright");
		g->fright_ms = 0;                  /* vuelve a chase */
		step(g, 300);
		sample(g, "chase2");
		g->fright_ms = 1;
		g->power_left = 4;
		(void)pac_emit_event(g, PAC_GAME_EVENT_EAT_POWER);
		step(g, 100);
		sample(g, "power");
		g->fright_ms = 0;
		step(g, 400);
		sample(g, "post-power");
		pac_set_state(g, PAC_STATE_PAUSED, "GAME_PAUSE");
		step(g, 200);
		sample(g, "paused");
		pac_set_state(g, PAC_STATE_PLAYING, NULL);
		step(g, 300);
		sample(g, "resume");
		LOG("[%6u] SUMMARY loops hunt=%d chase=%d fright=%d", T,
		    g_loop_calls[13], g_loop_calls[12], g_loop_calls[14]);
	} else if (strcmp(sc, "oneshot") == 0) {
		g->state = PAC_STATE_PLAYING;
		g->ready_ms = 0;
		g->audio_hold_ms = 0;
		step(g, 100);
		(void)pac_emit_event(g, PAC_GAME_EVENT_EAT_GHOST);
		step(g, 30);
		(void)pac_emit_event(g, PAC_GAME_EVENT_EAT_FRUIT);
		step(g, 30);
		(void)pac_emit_event(g, PAC_GAME_EVENT_EAT_GHOST);
		step(g, 30);
		(void)pac_emit_event(g, PAC_GAME_EVENT_EAT_GHOST);
		LOG("[%6u] SUMMARY plays: ghost=%d fruit=%d", T,
		    g_play_calls[6], g_play_calls[7]);
	} else if (strcmp(sc, "death") == 0) {
		g->state = PAC_STATE_PLAYING;
		g->ready_ms = 0;
		g->audio_hold_ms = 0;
		step(g, 200);
		(void)pac_emit_event(g, PAC_GAME_EVENT_DEATH);
		step(g, 300);
		sample(g, "muerte");
		step(g, 2000);
		sample(g, "tras-muerte");
		g->lives = 0;
		pac_set_state(g, PAC_STATE_GAMEOVER, "GAME_OVER");
		step(g, 300);
		sample(g, "gameover");
		LOG("[%6u] SUMMARY death=%d gameover=%d", T,
		    g_play_calls[8], g_play_calls[11]);
	} else if (strcmp(sc, "holdcut") == 0) {
		g->state = PAC_STATE_PLAYING;
		g->ready_ms = 0;
		g->audio_hold_ms = 0;
		g->dots_left = 200;
		g->power_left = 4;
		step(g, 300);                       /* sirena activa */
		sample(g, "sirena");
		LOG("-- EAT_GHOST (WAV 574 ms, hold 300 ms) --");
		(void)pac_emit_event(g, PAC_GAME_EVENT_EAT_GHOST);
		step(g, 700);
		sample(g, "ghost");
		LOG("-- EXTRA_LIFE (WAV 1899 ms, hold 900 ms) --");
		(void)pac_emit_event(g, PAC_GAME_EVENT_EXTRA_LIFE);
		step(g, 1200);
		sample(g, "extralife");
		LOG("-- EAT_FRUIT (WAV 440 ms, hold 250 ms) --");
		(void)pac_emit_event(g, PAC_GAME_EVENT_EAT_FRUIT);
		step(g, 600);
		sample(g, "fruit");
	} else if (strcmp(sc, "pausecycle") == 0) {
		tap_key(g, PAC_KEY_ENTER);
		tap_key(g, PAC_KEY_ENTER);
		sample(g, "start");
		for (int i = 0; i < 3; i++) {
			tap_key(g, PAC_KEY_ESC);       /* pausa */
			sample(g, "pausa");
			step(g, 200);
			tap_key(g, PAC_KEY_ESC);       /* reanuda */
			sample(g, "reanuda");
			step(g, 200);
		}
		LOG("[%6u] SUMMARY start_plays=%d (esperado 1)", T, g_start_plays);
	} else if (strcmp(sc, "respawn") == 0) {
		g->state = PAC_STATE_PLAYING;
		g->ready_ms = 0;
		g->audio_hold_ms = 0;
		step(g, 100);
		LOG("-- emit PAC_GAME_EVENT_GHOST_RESPAWN --");
		(void)pac_emit_event(g, PAC_GAME_EVENT_GHOST_RESPAWN);
		step(g, 300);
		sample(g, "respawn");
		LOG("-- emit PAC_GAME_EVENT_EXTRA_LIFE (control) --");
		(void)pac_emit_event(g, PAC_GAME_EVENT_EXTRA_LIFE);
		step(g, 100);
		LOG("[%6u] SUMMARY ghost_respawn_slot15_plays=%d extra_life=%d", T,
		    g_play_calls[15], g_play_calls[9]);
	} else {
		LOG("escenario desconocido: %s", sc);
	}
	pac_game_destroy(g);
	pac_platform_shutdown();
	return 0;
}
