/* harness_slots_fix.c - captura PCM real del backend Linux CORREGIDO.
 * Incluye platform_linux.c sin modificarlo (misma TU) para dejar abierto
 * solo el dispositivo que se quiere capturar; las ramas internas de
 * decision son las del juego.
 *
 * Uso:
 *   SDL_AUDIODRIVER=disk SDL_DISKAUDIOFILE=/ruta/x.raw \
 *     ./harness_slots_fix <slot> <loop0|1> <captura_ms> <pcm|synth>
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <SDL2/SDL.h>

#include "pac_platform.h"
#include "platform_linux.h"
#include "sfx_res.h"

#include "/home/t1an/Descargas/sereos02/Pac-man SereOS/src/platform/linux/platform_linux.c"

static int voices_active(void)
{
	int i, n = 0;
	for (i = 0; i < PAC_PCM_VOICES; i++)
		if (g_pcm_voices[i].active)
			n++;
	return n;
}

int main(int argc, char **argv)
{
	int slot = argc > 1 ? atoi(argv[1]) : 2;
	int loop = argc > 2 ? atoi(argv[2]) : 0;
	int cap_ms = argc > 3 ? atoi(argv[3]) : 1000;
	const char *mode = argc > 4 ? argv[4] : "pcm";
	int combo_slot = argc > 5 ? atoi(argv[5]) : -1;
	int combo_ms = argc > 6 ? atoi(argv[6]) : 0;
	int combo_done = 0;
	Uint32 t0, last;
	Uint32 maxq = 0;

	if (SDL_Init(SDL_INIT_AUDIO) != 0) {
		fprintf(stderr, "SDL_Init: %s\n", SDL_GetError());
		return 1;
	}
	pac_audio_init();
	printf("mode=%s slot=%d loop=%d cap_ms=%d g_audio_on=%d g_pcm_on=%d "
	       "audio_dev=%u pcm_dev=%u stream=%d target=%u res_available=%d\n",
	       mode, slot, loop, cap_ms, g_audio_on, g_pcm_on,
	       (unsigned)g_audio_dev, (unsigned)g_pcm_dev,
	       g_pcm_stream ? 1 : 0, (unsigned)g_pcm_target_bytes,
	       pacasset_sfx_res_available(slot));
	fflush(stdout);

	if (strcmp(mode, "pcm") == 0) {
		if (g_audio_dev) {
			SDL_CloseAudioDevice(g_audio_dev);
			g_audio_dev = 0;
			g_audio_on = 0;
		}
	} else {
		if (g_pcm_dev) {
			SDL_CloseAudioDevice(g_pcm_dev);
			g_pcm_dev = 0;
			g_pcm_on = 0;
			g_pcm_loop = 0;
		}
	}
	printf("capturing_on=%s dev=%u available=%d\n", mode,
	       (unsigned)(strcmp(mode, "pcm") == 0 ? g_pcm_dev : g_audio_dev),
	       pac_audio_available());
	fflush(stdout);

	t0 = SDL_GetTicks();
	last = t0;
	if (loop)
		pac_audio_loop(slot);
	else
		pac_audio_play(slot);

	while ((int)(SDL_GetTicks() - t0) < cap_ms) {
		Uint32 now;
		if (combo_slot > 0 && !combo_done &&
		    (int)(SDL_GetTicks() - t0) >= combo_ms) {
			if (combo_slot >= 100) {
				printf("t=%4u COMBO pac_audio_loop(%d)\n",
				       (unsigned)(SDL_GetTicks() - t0),
				       combo_slot - 100);
				fflush(stdout);
				pac_audio_loop(combo_slot - 100);
			} else {
				printf("t=%4u COMBO pac_audio_play(%d)\n",
				       (unsigned)(SDL_GetTicks() - t0), combo_slot);
				fflush(stdout);
				pac_audio_play(combo_slot);
			}
			combo_done = 1;
		}
		pac_audio_update();
		if (g_pcm_dev) {
			Uint32 q = SDL_GetQueuedAudioSize(g_pcm_dev);
			if (q > maxq)
				maxq = q;
			now = SDL_GetTicks();
			if (now - last >= 100) {
				printf("t=%4u queued=%u qmax=%u loop=%d "
				       "voices=%d synth_loop=%d synth_os=%d\n",
				       (unsigned)(now - t0), (unsigned)q,
				       (unsigned)maxq, g_pcm_loop,
				       voices_active(), g_synth_loop,
				       g_synth_os);
				fflush(stdout);
				last = now;
			}
		}
		SDL_Delay(5);
	}
	printf("END t=%u queued=%u qmax=%u loop=%d voices=%d synth_loop=%d "
	       "synth_os=%d\n",
	       (unsigned)(SDL_GetTicks() - t0),
	       g_pcm_dev ? (unsigned)SDL_GetQueuedAudioSize(g_pcm_dev) : 0u,
	       (unsigned)maxq, g_pcm_loop, voices_active(), g_synth_loop,
	       g_synth_os);
	fflush(stdout);
	pac_audio_stop();
	printf("AFTER_STOP queued=%u\n",
	       g_pcm_dev ? (unsigned)SDL_GetQueuedAudioSize(g_pcm_dev) : 0u);
	if (g_pcm_dev)
		SDL_CloseAudioDevice(g_pcm_dev);
	if (g_audio_dev)
		SDL_CloseAudioDevice(g_audio_dev);
	SDL_Quit();
	return 0;
}
