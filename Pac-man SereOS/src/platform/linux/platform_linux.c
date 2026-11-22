/* PAC-MAN SereOS - backend Linux (SDL2 + framebuffer software 32bpp)
 *
 * Implementa include/pac_platform.h sin que el core/render conozcan SDL.
 * Ventana logica de 1024x768 con escalado entero (SDL_RenderSetIntegerScale);
 * el juego se dibuja en un framebuffer software ARGB8888 y se sube a una
 * textura SDL cada frame. Audio sintetizado (onda cuadrada) sin recursos
 * externos; si SDL no puede abrir audio el juego funciona en silencio.
 */
#include <stdint.h>
#include <stddef.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <errno.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <SDL2/SDL.h>

#include "pac_platform.h"
#include "platform_linux.h"
#include "sfx_res.h"

#define PAC_LINUX_W 1024
#define PAC_LINUX_H 768
#define PAC_SDL_RENDERER_FLAGS (SDL_RENDERER_ACCELERATED | SDL_RENDERER_PRESENTVSYNC)

static uint32_t g_fb[PAC_LINUX_W * PAC_LINUX_H];
static int g_w = PAC_LINUX_W;
static int g_h = PAC_LINUX_H;
static int g_clip_x, g_clip_y, g_clip_w, g_clip_h;
static int g_quit;
static int g_smoke_frames;
static char g_screenshot[512];
static char g_scene[32];
static int g_screenshot_taken;

static SDL_Window *g_win;
static SDL_Renderer *g_ren;
static SDL_Texture *g_tex;

/* audio */
#define PAC_AUDIO_RATE 22050
#define PAC_PCM_RATE PACASSET_RES_SFX_RATE   /* 11025 Hz del PCM de sfx_res */
#define PAC_PCM_VOICES 6                     /* voces one-shot simultaneas */
#define PAC_PCM_MIX_CHUNK 256                /* muestras mezcladas por bloque */
#define PAC_PCM_TARGET 512                   /* bytes objetivo en la cola PCM */
#define PAC_SYNTH_AMP 10000                  /* amplitud de la onda cuadrada */
#define PAC_SYNTH_FADE 44                    /* ~2 ms a 22050 Hz (anti-click) */

static SDL_AudioDeviceID g_audio_dev;   /* sintesis: S16 mono 22050 callback */
static SDL_AudioDeviceID g_pcm_dev;     /* PCM de sfx_res: u8 mono 11025 cola */
static int g_audio_on;
static int g_pcm_on;
static int g_sdl_audio;                 /* subsistema SDL de audio inicializado */
static int g_audio_attempted;           /* ya se intento abrir el audio */

/* sintesis: bucle de sirena (independiente del one-shot) */
static int g_synth_loop;
static int g_synth_loop_freq;
static uint32_t g_synth_loop_freq2;
static uint32_t g_synth_loop_phase;
static uint32_t g_synth_loop_samples;
/* sintesis: efecto one-shot */
static int g_synth_os;
static int g_synth_os_freq;
static uint32_t g_synth_os_start_ms;
static uint32_t g_synth_os_duration_ms;
static uint32_t g_synth_os_phase;
static uint32_t g_synth_os_samples;

/* mezclador PCM: bucle de sirena + voces one-shot (sin borrar la cola) */
typedef struct {
	int active;
	int slot;
	int chunk;
	uint32_t off;
	uint32_t remaining;
} pac_pcm_voice_t;

static pac_pcm_voice_t g_pcm_voices[PAC_PCM_VOICES];
static int g_pcm_loop;
static int g_pcm_loop_slot;
static int g_pcm_loop_chunk;
static uint32_t g_pcm_loop_off;
static uint8_t g_pcm_mix[PAC_PCM_MIX_CHUNK];
static uint8_t g_pcm_out[8192];          /* conversion opcional de formato/rate */
static SDL_AudioStream *g_pcm_stream;    /* solo si el device no da u8/11025 exacto */
static uint32_t g_pcm_target_bytes = PAC_PCM_TARGET;

/* frecuencias/durations por efecto (Hz, ms; 0 = loop hasta stop) */
static const int g_sfx_freq[PAC_SFX_COUNT] = {
	0, 660, 880, 880, 660, 1200, 1568, 1760, 220, 1568, 1760, 165,
	880, 660, 440, 1200
};
static const int g_sfx_ms[PAC_SFX_COUNT] = {
	0, 240, 450, 70, 70, 160, 180, 160, 700, 600, 450, 600, 0, 0, 0, 500
};

/* ------------------------------------------------------------------ */
/* helpers de framebuffer                                              */
/* ------------------------------------------------------------------ */
static void put_px(int x, int y, uint32_t color)
{
	if (x < g_clip_x || y < g_clip_y ||
	    x >= g_clip_x + g_clip_w || y >= g_clip_y + g_clip_h)
		return;
	if (x < 0 || y < 0 || x >= g_w || y >= g_h)
		return;
	g_fb[y * g_w + x] = color;
}

static void mix_px(int x, int y, uint32_t color, uint8_t alpha)
{
	uint32_t bg;
	uint32_t a, ia;
	uint32_t r, g, b;

	if (x < g_clip_x || y < g_clip_y ||
	    x >= g_clip_x + g_clip_w || y >= g_clip_y + g_clip_h)
		return;
	if (x < 0 || y < 0 || x >= g_w || y >= g_h)
		return;
	if (alpha == 0)
		return;
	if (alpha == 255) {
		g_fb[y * g_w + x] = color;
		return;
	}
	a = alpha;
	ia = 255u - a;
	bg = g_fb[y * g_w + x];
	r = (((color >> 16) & 0xFFu) * a + ((bg >> 16) & 0xFFu) * ia) / 255u;
	g = (((color >> 8) & 0xFFu) * a + ((bg >> 8) & 0xFFu) * ia) / 255u;
	b = ((color & 0xFFu) * a + (bg & 0xFFu) * ia) / 255u;
	g_fb[y * g_w + x] = (r << 16) | (g << 8) | b;
}

static uint32_t rgb565_to_888(uint16_t v)
{
	uint32_t r = (v >> 11) & 0x1F;
	uint32_t g = (v >> 5) & 0x3F;
	uint32_t b = v & 0x1F;
	return ((r * 255 / 31) << 16) | ((g * 255 / 63) << 8) | (b * 255 / 31);
}

static int in_round_rect(int px, int py, int x, int y, int w, int h, int r)
{
	int cx, cy, dx, dy;
	if (px < x || py < y || px >= x + w || py >= y + h)
		return 0;
	if (r <= 0)
		return 1;
	if (px >= x + r && px < x + w - r)
		return 1;
	if (py >= y + r && py < y + h - r)
		return 1;
	cx = (px < x + r) ? x + r : x + w - r - 1;
	cy = (py < y + r) ? y + r : y + h - r - 1;
	dx = px - cx;
	dy = py - cy;
	return (dx * dx + dy * dy <= r * r);
}

/* ------------------------------------------------------------------ */
/* argumentos                                                          */
/* ------------------------------------------------------------------ */
void pac_linux_parse_args(int argc, char **argv)
{
	int i;
	g_smoke_frames = 0;
	g_screenshot[0] = 0;
	g_scene[0] = 0;
	for (i = 1; i < argc; i++) {
		if (strcmp(argv[i], "--smoke") == 0 && i + 1 < argc) {
			g_smoke_frames = atoi(argv[++i]);
			if (g_smoke_frames < 1)
				g_smoke_frames = 1;
		} else if (strcmp(argv[i], "--screenshot") == 0 && i + 1 < argc) {
			snprintf(g_screenshot, sizeof(g_screenshot), "%s", argv[++i]);
		} else if (strcmp(argv[i], "--scene") == 0 && i + 1 < argc) {
			snprintf(g_scene, sizeof(g_scene), "%s", argv[++i]);
		} else if (strcmp(argv[i], "--help") == 0 || strcmp(argv[i], "-h") == 0) {
			printf("PAC-MAN SereOS (Linux/SDL2)\n"
			       "  --smoke N        ejecuta N frames sin intervencion\n"
			       "  --screenshot R   guarda una captura PPM del ultimo frame\n"
			       "  --scene S        QA: attract|menu|settings|play|pause|gameover|victory|frightened|gamestart|ghostcapture|death\n"
			       "  --help           esta ayuda\n"
			       "Controles: flechas/WASD mover, Enter confirmar, Esc pausa/atras,\n"
			       "           R reiniciar, Q volver al titulo (en pausa).\n");
			g_quit = 1;
		} else {
			fprintf(stderr, "opcion no reconocida: %s (usa --help)\n", argv[i]);
		}
	}
}

int pac_linux_should_quit(void) { return g_quit; }
int pac_linux_smoke_frames(void) { return g_smoke_frames; }
const char *pac_linux_screenshot_path(void) { return g_screenshot; }
const char *pac_linux_scene(void) { return g_scene; }

/* ------------------------------------------------------------------ */
/* storage (record persistente en el directorio de usuario)            */
/* ------------------------------------------------------------------ */
static void mkdir_parents(const char *path)
{
	char tmp[512];
	size_t i, n;

	n = strlen(path);
	if (n >= sizeof(tmp))
		return;
	memcpy(tmp, path, n + 1);
	for (i = 1; i < n; i++) {
		if (tmp[i] == '/') {
			tmp[i] = 0;
			if (tmp[0])
				(void)mkdir(tmp, 0755);
			tmp[i] = '/';
		}
	}
}

static int storage_path(const char *key, char *out, size_t out_len)
{
	const char *xdg = getenv("XDG_DATA_HOME");
	const char *home = getenv("HOME");
	const char *name = (key && key[0]) ? key : "record";

	if (xdg && xdg[0]) {
		snprintf(out, out_len, "%s/pacman-sereos/%s.txt", xdg, name);
	} else if (home && home[0]) {
		snprintf(out, out_len, "%s/.local/share/pacman-sereos/%s.txt", home, name);
	} else {
		snprintf(out, out_len, "./pacman-sereos-%s.txt", name);
	}
	return 0;
}

int pac_storage_read(const char *key, void *buf, int max_len)
{
	char path[512];
	FILE *f;
	int n;

	if (max_len <= 0)
		return -1;
	if (storage_path(key, path, sizeof(path)) != 0)
		return -1;
	f = fopen(path, "rb");
	if (!f)
		return -1;
	n = (int)fread(buf, 1, (size_t)max_len, f);
	fclose(f);
	return n > 0 ? n : -1;
}

int pac_storage_write(const char *key, const void *buf, int len)
{
	char path[512];
	FILE *f;
	int n;

	if (len <= 0)
		return 0;
	if (storage_path(key, path, sizeof(path)) != 0)
		return -1;
	mkdir_parents(path);
	f = fopen(path, "wb");
	if (!f)
		return -1;
	n = (int)fwrite(buf, 1, (size_t)len, f);
	fclose(f);
	return n;
}

/* ------------------------------------------------------------------ */
/* audio sintetizado                                                   */
/* ------------------------------------------------------------------ */
/* ---- mezclador PCM de sfx_res (u8 mono 11025) ---------------------- */
static void pcm_queue_bytes(const uint8_t *buf, int len)
{
	if (!g_pcm_dev || !g_pcm_on || len <= 0)
		return;
	if (g_pcm_stream) {
		int got;
		if (SDL_AudioStreamPut(g_pcm_stream, buf, len) != 0)
			return;
		while ((got = SDL_AudioStreamGet(g_pcm_stream, g_pcm_out,
		                                 (int)sizeof(g_pcm_out))) > 0)
			(void)SDL_QueueAudio(g_pcm_dev, g_pcm_out, (Uint32)got);
	} else {
		(void)SDL_QueueAudio(g_pcm_dev, buf, (Uint32)len);
	}
}

static int pcm_has_voices(void)
{
	int i;
	for (i = 0; i < PAC_PCM_VOICES; i++)
		if (g_pcm_voices[i].active)
			return 1;
	return 0;
}

static int pcm_loop_next(uint8_t *out)
{
	const uint8_t *data;
	uint32_t len;

	if (!g_pcm_loop)
		return 0;
	data = pacasset_sfx_res_chunks[g_pcm_loop_slot][g_pcm_loop_chunk];
	len = pacasset_sfx_res_chunk_len[g_pcm_loop_slot][g_pcm_loop_chunk];
	if (!data || len == 0u) {
		g_pcm_loop = 0;
		return 0;
	}
	*out = data[g_pcm_loop_off++];
	if (g_pcm_loop_off >= len) {
		g_pcm_loop_chunk++;
		g_pcm_loop_off = 0;
		if (g_pcm_loop_chunk >=
		    (int)pacasset_sfx_res_chunk_count[g_pcm_loop_slot])
			g_pcm_loop_chunk = 0;
	}
	return 1;
}

static int pcm_voice_next(pac_pcm_voice_t *v, uint8_t *out)
{
	const uint8_t *data;
	uint32_t len;

	if (!v->active)
		return 0;
	data = pacasset_sfx_res_chunks[v->slot][v->chunk];
	len = pacasset_sfx_res_chunk_len[v->slot][v->chunk];
	if (!data || len == 0u) {
		v->active = 0;
		return 0;
	}
	*out = data[v->off++];
	if (v->remaining > 0)
		v->remaining--;
	if (v->off >= len) {
		v->chunk++;
		v->off = 0;
		if (v->chunk >= (int)pacasset_sfx_res_chunk_count[v->slot])
			v->active = 0;
	}
	return 1;
}

/* Arranca una voz one-shot. No borra la cola: los efectos se mezclan
 * (p.ej. waka sobre la sirena). Si las 6 voces estan ocupadas se roba la
 * que menos muestras le quedan (la menos audible); la prioridad real la
 * decide el core. */
static void pcm_voice_start(int slot)
{
	pac_pcm_voice_t *v = NULL;
	uint32_t min_rem = 0xFFFFFFFFu;
	int i, steal = -1;

	for (i = 0; i < PAC_PCM_VOICES; i++) {
		if (!g_pcm_voices[i].active) {
			v = &g_pcm_voices[i];
			break;
		}
		if (g_pcm_voices[i].remaining < min_rem) {
			min_rem = g_pcm_voices[i].remaining;
			steal = i;
		}
	}
	if (!v)
		v = &g_pcm_voices[steal];
	v->active = 1;
	v->slot = slot;
	v->chunk = 0;
	v->off = 0;
	v->remaining = pacasset_sfx_res[slot].len;
}

static void pcm_loop_start(int slot)
{
	g_pcm_loop = 1;
	g_pcm_loop_slot = slot;
	g_pcm_loop_chunk = 0;
	g_pcm_loop_off = 0;
}

/* Detiene el bucle PCM. Si no hay one-shots en curso limpia la cola para
 * que el corte sea inmediato; si los hay, los deja terminar. */
static void pcm_loop_stop(void)
{
	g_pcm_loop = 0;
	if (!pcm_has_voices()) {
		if (g_pcm_dev)
			SDL_ClearQueuedAudio(g_pcm_dev);
		if (g_pcm_stream)
			SDL_AudioStreamClear(g_pcm_stream);
	}
}

static void pcm_stop(void)
{
	int i;

	g_pcm_loop = 0;
	for (i = 0; i < PAC_PCM_VOICES; i++)
		g_pcm_voices[i].active = 0;
	if (g_pcm_dev)
		SDL_ClearQueuedAudio(g_pcm_dev);
	if (g_pcm_stream)
		SDL_AudioStreamClear(g_pcm_stream);
}

/* Rellena la cola del dispositivo PCM con bloques mezclados. La cola se
 * mantiene acotada (<= objetivo + bloque) y sin huecos: se rellena cuando
 * baja del objetivo en cada pac_audio_update() y al arrancar un sonido. */
static void mixer_feed(void)
{
	int guard = 0;

	if (!g_pcm_dev || !g_pcm_on)
		return;
	while (SDL_GetQueuedAudioSize(g_pcm_dev) < g_pcm_target_bytes &&
	       guard++ < 32) {
		int i, v, any = 0, sources = g_pcm_loop ? 1 : 0;

		for (v = 0; v < PAC_PCM_VOICES; v++)
			if (g_pcm_voices[v].active)
				sources++;
		if (sources < 1)
			sources = 1;
		for (i = 0; i < PAC_PCM_MIX_CHUNK; i++) {
			int sum = 0;
			uint8_t b;
			int acc;

			if (pcm_loop_next(&b)) {
				sum += (int)b - 128;
				any = 1;
			}
			for (v = 0; v < PAC_PCM_VOICES; v++) {
				if (pcm_voice_next(&g_pcm_voices[v], &b)) {
					sum += (int)b - 128;
					any = 1;
				}
			}
			/* reparto de ganancia 1/fuentes: con 1 fuente el nivel
			 * es identico al clip original; con varias no satura
			 * el u8 (evita clipping al mezclar). */
			acc = 128 + sum / sources;
			if (acc < 0)
				acc = 0;
			if (acc > 255)
				acc = 255;
			g_pcm_mix[i] = (uint8_t)acc;
		}
		if (!any)
			break;              /* silencio: el device ya emite ceros */
		pcm_queue_bytes(g_pcm_mix, PAC_PCM_MIX_CHUNK);
	}
}

/* ---- sintesis (S16 mono 22050, callback con mezcla bucle+one-shot) -- */
static uint32_t synth_phase_inc(int freq)
{
	/* salida = rate * inc / 65536  =>  inc = freq * 65536 / rate */
	if (freq <= 0)
		return 0;
	return (uint32_t)(((uint64_t)(uint32_t)freq << 16) / PAC_AUDIO_RATE);
}

static void synth_loop_start(int sfx)
{
	g_synth_loop = 1;
	g_synth_loop_freq = g_sfx_freq[sfx] ? g_sfx_freq[sfx] : 440;
	g_synth_loop_freq2 = (uint32_t)(g_synth_loop_freq +
	                               (sfx == PAC_SFX_SIREN_FRIGHT ? 220 : 120));
	g_synth_loop_phase = 0;
	g_synth_loop_samples = 0;
}

static void synth_loop_stop(void)
{
	g_synth_loop = 0;
}

static void synth_play_one_shot(int sfx)
{
	g_synth_os = 1;
	g_synth_os_freq = g_sfx_freq[sfx] ? g_sfx_freq[sfx] : 440;
	g_synth_os_duration_ms = (uint32_t)g_sfx_ms[sfx];
	g_synth_os_start_ms = SDL_GetTicks();
	g_synth_os_phase = 0;
	g_synth_os_samples = 0;
}

static void synth_stop_all(void)
{
	g_synth_loop = 0;
	g_synth_os = 0;
}

static int16_t synth_square(uint32_t *phase, uint32_t inc)
{
	*phase += inc;
	return ((*phase & 0x8000u) != 0) ? PAC_SYNTH_AMP : -PAC_SYNTH_AMP;
}

/* Envolvente corta para que el one-shot sintetizado no chasquee al
 * empezar/terminar (misma amplitud, sin tocar el tono). */
static int synth_fade_gain(uint32_t sample, uint32_t total)
{
	if (sample < PAC_SYNTH_FADE)
		return (int)(sample * 256u / PAC_SYNTH_FADE);
	if (total > 0u && sample + PAC_SYNTH_FADE >= total) {
		uint32_t left = total - sample;
		if (left > PAC_SYNTH_FADE)
			left = PAC_SYNTH_FADE;
		return (int)(left * 256u / PAC_SYNTH_FADE);
	}
	return 256;
}

static void audio_callback(void *userdata, Uint8 *stream, int len)
{
	int16_t *out = (int16_t *)stream;
	int samples = len / (int)sizeof(int16_t);
	uint32_t os_total = 0;
	int i;

	(void)userdata;
	if (g_synth_os && g_synth_os_duration_ms)
		os_total = (uint32_t)(((uint64_t)g_synth_os_duration_ms *
		                       PAC_AUDIO_RATE) / 1000u);
	for (i = 0; i < samples; i++) {
		int acc = 0;

		if (g_synth_loop) {
			int freq = g_synth_loop_freq;
			if (g_synth_loop_freq2 &&
			    ((g_synth_loop_samples >> 12) & 1) != 0)
				freq = (int)g_synth_loop_freq2;
			acc += synth_square(&g_synth_loop_phase,
			                    synth_phase_inc(freq));
			g_synth_loop_samples++;
		}
		if (g_synth_os) {
			acc += synth_square(&g_synth_os_phase,
			                    synth_phase_inc(g_synth_os_freq)) *
			       synth_fade_gain(g_synth_os_samples, os_total) / 256;
			g_synth_os_samples++;
		}
		if (acc > 32767)
			acc = 32767;
		if (acc < -32768)
			acc = -32768;
		out[i] = (int16_t)acc;
	}
}

void pac_audio_init(void)
{
	SDL_AudioSpec want, have;

	if (g_audio_dev != 0 || g_pcm_dev != 0 || g_audio_attempted)
		return;
	g_audio_attempted = 1;
	if (!g_sdl_audio) {
		if ((SDL_WasInit(SDL_INIT_AUDIO) & SDL_INIT_AUDIO) == 0) {
			if (SDL_InitSubSystem(SDL_INIT_AUDIO) != 0) {
				fprintf(stderr, "audio no disponible: %s\n",
				        SDL_GetError());
				return;
			}
		}
		g_sdl_audio = 1;
	}

	/* dispositivo de sintesis: S16 mono 22050 con callback */
	memset(&want, 0, sizeof(want));
	want.freq = PAC_AUDIO_RATE;
	want.format = AUDIO_S16SYS;
	want.channels = 1;
	want.samples = 512;
	want.callback = audio_callback;
	g_audio_dev = SDL_OpenAudioDevice(NULL, 0, &want, &have, 0);
	if (g_audio_dev != 0) {
		SDL_PauseAudioDevice(g_audio_dev, 0);
		g_audio_on = 1;
	}

	/* dispositivo PCM (WAV de sfx_res): intento exacto u8/mono/11025 */
	memset(&want, 0, sizeof(want));
	want.freq = PAC_PCM_RATE;
	want.format = AUDIO_U8;
	want.channels = 1;
	want.samples = 1024;
	g_pcm_dev = SDL_OpenAudioDevice(NULL, 0, &want, &have, 0);
	if (g_pcm_dev != 0 && have.format == AUDIO_U8 && have.channels == 1 &&
	    have.freq == PAC_PCM_RATE) {
		g_pcm_on = 1;
	} else if (g_pcm_dev != 0) {
		SDL_CloseAudioDevice(g_pcm_dev);
		g_pcm_dev = 0;
	}
	/* fallback: el host no concede u8/mono/11025 exacto -> convertir en
	 * un SDL_AudioStream en vez de perder los 10 WAV (antes se cerraba
	 * el dispositivo y todo caia al beep sintetizado). */
	if (!g_pcm_on && g_sdl_audio) {
		memset(&want, 0, sizeof(want));
		want.freq = PAC_PCM_RATE;
		want.format = AUDIO_U8;
		want.channels = 1;
		want.samples = 1024;
		g_pcm_dev = SDL_OpenAudioDevice(NULL, 0, &want, &have,
		        SDL_AUDIO_ALLOW_FREQUENCY_CHANGE |
		        SDL_AUDIO_ALLOW_FORMAT_CHANGE |
		        SDL_AUDIO_ALLOW_CHANNELS_CHANGE);
		if (g_pcm_dev != 0) {
			g_pcm_stream = SDL_NewAudioStream(
			        AUDIO_U8, 1, PAC_PCM_RATE,
			        have.format, have.channels, have.freq);
			if (g_pcm_stream) {
				uint32_t bps = (uint32_t)SDL_AUDIO_BITSIZE(
				        have.format) / 8u;
				if (bps == 0u)
					bps = 1u;
				g_pcm_target_bytes = PAC_PCM_TARGET;
				if (have.freq != PAC_PCM_RATE)
					g_pcm_target_bytes = (uint32_t)(
					        (uint64_t)PAC_PCM_TARGET *
					        (uint32_t)have.freq / PAC_PCM_RATE);
				g_pcm_target_bytes *=
				        (uint32_t)have.channels * bps;
				g_pcm_on = 1;
			} else {
				SDL_CloseAudioDevice(g_pcm_dev);
				g_pcm_dev = 0;
			}
		}
	}
	if (g_pcm_on)
		SDL_PauseAudioDevice(g_pcm_dev, 0);
	if (!g_audio_on && !g_pcm_on)
		fprintf(stderr, "audio: sin dispositivos; el juego seguira en "
		        "silencio\n");
}

int pac_audio_available(void) { return (g_audio_on || g_pcm_on) ? 1 : 0; }

void pac_audio_play(int sfx)
{
	if (sfx <= PAC_SFX_NONE || sfx >= PAC_SFX_COUNT)
		return;
	if (g_pcm_on && pacasset_sfx_res_available(sfx)) {
		/* WAV: se mezcla sobre el bucle (waka sobre sirena, etc.) */
		pcm_voice_start(sfx);
		mixer_feed();
		return;
	}
	/* rama sintetizada: parar el bucle PCM para no solapar ambos sonidos */
	pcm_loop_stop();
	synth_play_one_shot(sfx);
}

void pac_audio_loop(int sfx)
{
	if (sfx <= PAC_SFX_NONE || sfx >= PAC_SFX_COUNT) {
		pac_audio_stop_loop();
		return;
	}
	if (g_pcm_on && pacasset_sfx_res_available(sfx)) {
		pcm_loop_start(sfx);
		synth_loop_stop();
		mixer_feed();
		return;
	}
	/* sin WAV (p.ej. FRIGHT): parar el bucle PCM antes de sintetizar */
	pcm_loop_stop();
	synth_loop_start(sfx);
}

void pac_audio_stop_loop(void)
{
	pcm_loop_stop();
	synth_loop_stop();
}

void pac_audio_stop(void)
{
	pcm_stop();
	synth_stop_all();
}

void pac_audio_update(void)
{
	mixer_feed();
	if (g_synth_os && g_synth_os_duration_ms &&
	    SDL_GetTicks() - g_synth_os_start_ms >= g_synth_os_duration_ms)
		g_synth_os = 0;
}

/* ------------------------------------------------------------------ */
/* init / shutdown / ventana                                           */
/* ------------------------------------------------------------------ */
int pac_platform_init(void)
{
	Uint32 flags;

	if (SDL_Init(SDL_INIT_VIDEO | SDL_INIT_EVENTS) != 0) {
		fprintf(stderr, "SDL_Init: %s\n", SDL_GetError());
		return 0;
	}
	/* el audio es opcional: si el subsistema falla (sin servidor de
	 * sonido, driver roto...) el juego debe arrancar en silencio, no
	 * abortar. Antes SDL_Init(VIDEO|AUDIO|EVENTS) devolvia 0 y el juego
	 * terminaba con exit 1. */
	if (SDL_InitSubSystem(SDL_INIT_AUDIO) != 0) {
		fprintf(stderr, "audio no disponible; el juego seguira en "
		        "silencio: %s\n", SDL_GetError());
		g_sdl_audio = 0;
	} else {
		g_sdl_audio = 1;
	}
	flags = SDL_WINDOW_RESIZABLE;
	if (g_smoke_frames > 0 || getenv("SDL_VIDEODRIVER"))
		flags |= SDL_WINDOW_HIDDEN;
	g_win = SDL_CreateWindow("PAC-MAN SereOS",
	                         SDL_WINDOWPOS_CENTERED, SDL_WINDOWPOS_CENTERED,
	                         PAC_LINUX_W, PAC_LINUX_H, SDL_WINDOW_SHOWN | flags);
	if (!g_win) {
		fprintf(stderr, "SDL_CreateWindow: %s\n", SDL_GetError());
		return 0;
	}
	g_ren = SDL_CreateRenderer(g_win, -1, PAC_SDL_RENDERER_FLAGS);
	if (!g_ren)
		g_ren = SDL_CreateRenderer(g_win, -1, SDL_RENDERER_SOFTWARE);
	if (!g_ren) {
		fprintf(stderr, "SDL_CreateRenderer: %s\n", SDL_GetError());
		return 0;
	}
	SDL_RenderSetLogicalSize(g_ren, PAC_LINUX_W, PAC_LINUX_H);
	SDL_RenderSetIntegerScale(g_ren, SDL_TRUE);
	g_tex = SDL_CreateTexture(g_ren, SDL_PIXELFORMAT_ARGB8888,
	                          SDL_TEXTUREACCESS_STREAMING,
	                          PAC_LINUX_W, PAC_LINUX_H);
	if (!g_tex) {
		fprintf(stderr, "SDL_CreateTexture: %s\n", SDL_GetError());
		return 0;
	}
	SDL_SetHint(SDL_HINT_RENDER_SCALE_QUALITY, "nearest");

	/* fondo inicial y clip completo */
	g_w = PAC_LINUX_W;
	g_h = PAC_LINUX_H;
	memset(g_fb, 0, sizeof(g_fb));
	g_clip_x = 0;
	g_clip_y = 0;
	g_clip_w = g_w;
	g_clip_h = g_h;

	pac_audio_init();
	pac_linux_text_init();
	g_quit = 0;
	g_screenshot_taken = 0;
	return 1;
}

void pac_platform_shutdown(void)
{
	if (g_audio_dev != 0) {
		SDL_CloseAudioDevice(g_audio_dev);
		g_audio_dev = 0;
		g_audio_on = 0;
	}
	if (g_pcm_dev != 0) {
		SDL_CloseAudioDevice(g_pcm_dev);
		g_pcm_dev = 0;
		g_pcm_on = 0;
		g_pcm_loop = 0;
		{
			int i;
			for (i = 0; i < PAC_PCM_VOICES; i++)
				g_pcm_voices[i].active = 0;
		}
	}
	if (g_pcm_stream) {
		SDL_FreeAudioStream(g_pcm_stream);
		g_pcm_stream = NULL;
	}
	if (g_tex) {
		SDL_DestroyTexture(g_tex);
		g_tex = NULL;
	}
	if (g_ren) {
		SDL_DestroyRenderer(g_ren);
		g_ren = NULL;
	}
	if (g_win) {
		SDL_DestroyWindow(g_win);
		g_win = NULL;
	}
	SDL_Quit();
}

int pac_platform_width(void) { return g_w; }
int pac_platform_height(void) { return g_h; }

void pac_platform_content_rect(pac_rect_t *out)
{
	if (!out)
		return;
	out->x = 0;
	out->y = 0;
	out->w = g_w;
	out->h = g_h;
}

int pac_platform_focused(void)
{
	const char *drv = getenv("SDL_VIDEODRIVER");
	if (g_smoke_frames > 0)
		return 1;
	if (drv && strcmp(drv, "dummy") == 0)
		return 1;
	return SDL_GetKeyboardFocus() == g_win ? 1 : 0;
}

int pac_platform_minimized(void)
{
	if (!g_win)
		return 1;
	return (SDL_GetWindowFlags(g_win) & SDL_WINDOW_MINIMIZED) ? 1 : 0;
}

void pac_platform_request_close(void) { g_quit = 1; }

int pac_platform_set_fullscreen(int enabled)
{
	if (!g_win)
		return 0;
	SDL_SetWindowFullscreen(g_win, enabled ? SDL_WINDOW_FULLSCREEN_DESKTOP : 0);
	return 1;
}

int pac_platform_get_fullscreen(void)
{
	if (!g_win)
		return 0;
	return (SDL_GetWindowFlags(g_win) & SDL_WINDOW_FULLSCREEN_DESKTOP) ? 1 : 0;
}

void pac_platform_log(const char *marker)
{
	if (!marker)
		return;
	fprintf(stderr, "%s\n", marker);
	fflush(stderr);
}

uint32_t pac_time_ms(void) { return SDL_GetTicks(); }

void *pac_alloc(size_t size) { return malloc(size); }
void pac_free(void *ptr) { free(ptr); }

/* ------------------------------------------------------------------ */
/* render (framebuffer software)                                       */
/* ------------------------------------------------------------------ */
void pac_set_clip(int x, int y, int w, int h)
{
	g_clip_x = x;
	g_clip_y = y;
	g_clip_w = w;
	g_clip_h = h;
}

void pac_reset_clip(void)
{
	g_clip_x = 0;
	g_clip_y = 0;
	g_clip_w = g_w;
	g_clip_h = g_h;
}

void pac_get_clip(pac_rect_t *out)
{
	if (!out)
		return;
	out->x = g_clip_x;
	out->y = g_clip_y;
	out->w = g_clip_w;
	out->h = g_clip_h;
}

void pac_fill_rect(int x, int y, int w, int h, uint32_t color)
{
	int i, j;
	for (j = 0; j < h; j++)
		for (i = 0; i < w; i++)
			put_px(x + i, y + j, color);
}

void pac_fill_rect_alpha(int x, int y, int w, int h, uint32_t color, uint8_t alpha)
{
	int i, j;
	for (j = 0; j < h; j++)
		for (i = 0; i < w; i++)
			mix_px(x + i, y + j, color, alpha);
}

void pac_draw_rect(int x, int y, int w, int h, uint32_t color)
{
	pac_fill_rect(x, y, w, 1, color);
	pac_fill_rect(x, y + h - 1, w, 1, color);
	pac_fill_rect(x, y, 1, h, color);
	pac_fill_rect(x + w - 1, y, 1, h, color);
}

void pac_fill_round_rect(int x, int y, int w, int h, int radius, uint32_t color)
{
	int i, j, r = radius;
	if (w <= 0 || h <= 0)
		return;
	if (r > w / 2) r = w / 2;
	if (r > h / 2) r = h / 2;
	for (j = 0; j < h; j++)
		for (i = 0; i < w; i++)
			if (in_round_rect(x + i, y + j, x, y, w, h, r))
				put_px(x + i, y + j, color);
}

void pac_fill_round_rect_alpha(int x, int y, int w, int h, int radius,
                               uint32_t color, uint8_t alpha)
{
	int i, j, r = radius;
	if (w <= 0 || h <= 0)
		return;
	if (r > w / 2) r = w / 2;
	if (r > h / 2) r = h / 2;
	for (j = 0; j < h; j++)
		for (i = 0; i < w; i++)
			if (in_round_rect(x + i, y + j, x, y, w, h, r))
				mix_px(x + i, y + j, color, alpha);
}

void pac_draw_round_rect(int x, int y, int w, int h, int radius, uint32_t color)
{
	int i, j, r = radius;
	if (w <= 0 || h <= 0)
		return;
	if (r > w / 2) r = w / 2;
	if (r > h / 2) r = h / 2;
	for (j = 0; j < h; j++)
		for (i = 0; i < w; i++) {
			int px = x + i, py = y + j;
			if (!in_round_rect(px, py, x, y, w, h, r))
				continue;
			if (!in_round_rect(px - 1, py, x, y, w, h, r) ||
			    !in_round_rect(px + 1, py, x, y, w, h, r) ||
			    !in_round_rect(px, py - 1, x, y, w, h, r) ||
			    !in_round_rect(px, py + 1, x, y, w, h, r))
				put_px(px, py, color);
		}
}

void pac_blit_rgb(int x, int y, int w, int h, const uint32_t *pixels)
{
	int i, j;
	if (!pixels)
		return;
	for (j = 0; j < h; j++)
		for (i = 0; i < w; i++)
			put_px(x + i, y + j, pixels[j * w + i]);
}

void pac_sprite(int x, int y, const uint16_t *pixels, int w, int h)
{
	int i, j;
	if (!pixels)
		return;
	for (j = 0; j < h; j++)
		for (i = 0; i < w; i++) {
			uint16_t v = pixels[j * w + i];
			if (v == 0xF81F)
				continue;
			put_px(x + i, y + j, rgb565_to_888(v));
		}
}

void pac_sprite_alpha(int x, int y, const uint16_t *pixels, int w, int h,
                      uint8_t alpha)
{
	int i, j;
	if (!pixels)
		return;
	for (j = 0; j < h; j++)
		for (i = 0; i < w; i++) {
			uint16_t v = pixels[j * w + i];
			if (v == 0xF81F)
				continue;
			mix_px(x + i, y + j, rgb565_to_888(v), alpha);
		}
}

void pac_mark_dirty(int x, int y, int w, int h)
{
	(void)x; (void)y; (void)w; (void)h;
}

void pac_present(void)
{
	if (!g_ren || !g_tex)
		return;
	SDL_UpdateTexture(g_tex, NULL, g_fb, g_w * (int)sizeof(uint32_t));
	SDL_RenderClear(g_ren);
	SDL_RenderCopy(g_ren, g_tex, NULL, NULL);
	SDL_RenderPresent(g_ren);
}

/* ------------------------------------------------------------------ */
/* input (estado fisico de teclas / raton)                             */
/* ------------------------------------------------------------------ */
static SDL_Scancode scancode_for(pac_key_t key)
{
	switch (key) {
	case PAC_KEY_ESC: return SDL_SCANCODE_ESCAPE;
	case PAC_KEY_ENTER: return SDL_SCANCODE_RETURN;
	case PAC_KEY_SPACE: return SDL_SCANCODE_SPACE;
	case PAC_KEY_UP: return SDL_SCANCODE_UP;
	case PAC_KEY_DOWN: return SDL_SCANCODE_DOWN;
	case PAC_KEY_LEFT: return SDL_SCANCODE_LEFT;
	case PAC_KEY_RIGHT: return SDL_SCANCODE_RIGHT;
	default: break;
	}
	if (key >= PAC_KEY_A && key <= PAC_KEY_Z)
		return (SDL_Scancode)(SDL_SCANCODE_A + (key - PAC_KEY_A));
	if (key >= PAC_KEY_0 && key <= PAC_KEY_9)
		return (SDL_Scancode)(SDL_SCANCODE_0 + (key - PAC_KEY_0));
	return SDL_SCANCODE_UNKNOWN;
}

int pac_input_key_down(pac_key_t key)
{
	const Uint8 *state;
	SDL_Scancode sc;

	if (!g_win)
		return 0;
	state = SDL_GetKeyboardState(NULL);
	sc = scancode_for(key);
	if (sc == SDL_SCANCODE_UNKNOWN)
		return 0;
	return state[sc] ? 1 : 0;
}

int pac_mouse_x(void)
{
	int x = 0, y = 0;
	SDL_GetMouseState(&x, &y);
	pac_linux_window_to_canvas(x, y, &x, &y);
	return x;
}

int pac_mouse_y(void)
{
	int x = 0, y = 0;
	SDL_GetMouseState(&x, &y);
	pac_linux_window_to_canvas(x, y, &x, &y);
	return y;
}

void pac_blit_alpha8(int x, int y, int w, int h, const uint8_t *mask,
                     uint32_t color)
{
	pac_linux_blit_alpha8(x, y, w, h, mask, color);
}

/* primitivas para el motor tipografico */
void pac_linux_blit_alpha8(int x, int y, int w, int h,
                           const uint8_t *mask, uint32_t color)
{
	int i, j;
	if (!mask)
		return;
	for (j = 0; j < h; j++)
		for (i = 0; i < w; i++) {
			uint8_t m = mask[j * w + i];
			if (m)
				mix_px(x + i, y + j, color, m);
		}
}

void pac_linux_blend_pixel(int x, int y, uint32_t color, uint8_t alpha)
{
	mix_px(x, y, color, alpha);
}

/* ------------------------------------------------------------------ */
/* captura PPM                                                         */
/* ------------------------------------------------------------------ */
int pac_linux_save_ppm(const char *path)
{
	FILE *f;
	int i, j;

	if (!path || !path[0])
		return -1;
	f = fopen(path, "wb");
	if (!f) {
		fprintf(stderr, "no se pudo crear %s: %s\n", path, strerror(errno));
		return -1;
	}
	fprintf(f, "P6\n%d %d\n255\n", g_w, g_h);
	for (j = 0; j < g_h; j++)
		for (i = 0; i < g_w; i++) {
			uint32_t c = g_fb[j * g_w + i];
			fputc((int)((c >> 16) & 0xFFu), f);
			fputc((int)((c >> 8) & 0xFFu), f);
			fputc((int)(c & 0xFFu), f);
		}
	fclose(f);
	g_screenshot_taken = 1;
	return 0;
}

void pac_linux_window_to_canvas(int wx, int wy, int *cx, int *cy)
{
	float lx = 0.0f, ly = 0.0f;
	if (!g_ren) {
		if (cx) *cx = wx;
		if (cy) *cy = wy;
		return;
	}
	SDL_RenderWindowToLogical(g_ren, wx, wy, &lx, &ly);
	if (cx) *cx = (int)(lx + 0.5f);
	if (cy) *cy = (int)(ly + 0.5f);
}

void pac_linux_mark_screenshot_done(void) { g_screenshot_taken = 1; }
int pac_linux_screenshot_done(void) { return g_screenshot_taken; }
