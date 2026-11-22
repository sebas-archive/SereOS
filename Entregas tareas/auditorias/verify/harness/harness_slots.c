/* harness_slots.c - captura PCM real de la plataforma Linux SIN MODIFICAR
 * fuentes del proyecto.
 *
 * Incluye src/platform/linux/platform_linux.c tal cual (misma unidad de
 * traduccion) para poder elegir el dispositivo que escribe en el fichero
 * del driver "disk" de SDL (los dos dispositivos abiertos por el juego
 * escribirian en el mismo fichero y se corromperian entre si).
 *
 * Uso:
 *   SDL_AUDIODRIVER=disk SDL_DISKAUDIOFILE=/ruta/x.raw \
 *     ./harness_slots <slot> <loop0|1> <captura_ms> <pcm|synth>
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <SDL2/SDL.h>

#include "pac_platform.h"
#include "platform_linux.h"
#include "sfx_res.h"

/* definiciones estaticas del backend, en la misma TU */
#include "/home/t1an/Descargas/sereos02/Pac-man SereOS/src/platform/linux/platform_linux.c"

int main(int argc, char **argv)
{
	int slot = argc > 1 ? atoi(argv[1]) : 2;
	int loop = argc > 2 ? atoi(argv[2]) : 0;
	int cap_ms = argc > 3 ? atoi(argv[3]) : 1000;
	const char *mode = argc > 4 ? argv[4] : "pcm";
	Uint32 t0, last;

	if (SDL_Init(SDL_INIT_AUDIO) != 0) {
		fprintf(stderr, "SDL_Init: %s\n", SDL_GetError());
		return 1;
	}
	pac_audio_init();
	printf("mode=%s slot=%d loop=%d cap_ms=%d g_audio_on=%d g_pcm_on=%d "
	       "audio_dev=%u pcm_dev=%u\n",
	       mode, slot, loop, cap_ms, g_audio_on, g_pcm_on,
	       (unsigned)g_audio_dev, (unsigned)g_pcm_dev);
	fflush(stdout);

	if (strcmp(mode, "pcm") == 0) {
		/* dejar solo el dispositivo PCM: la sintesis escribiria ceros
		 * en el mismo fichero y lo sobreescribiria */
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
			g_pcm_active = 0;
		}
	}
	printf("capturing_on=%s dev=%u available=%d res_available=%d\n",
	       mode, (unsigned)(strcmp(mode, "pcm") == 0 ? g_pcm_dev : g_audio_dev),
	       pac_audio_available(), pacasset_sfx_res_available(slot));
	fflush(stdout);

	t0 = SDL_GetTicks();
	last = t0;
	if (loop)
		pac_audio_loop(slot);
	else
		pac_audio_play(slot);

	while ((int)(SDL_GetTicks() - t0) < cap_ms) {
		Uint32 now;
		pac_audio_update();
		if (g_pcm_dev) {
			Uint32 q = SDL_GetQueuedAudioSize(g_pcm_dev);
			now = SDL_GetTicks();
			if (now - last >= 100) {
				printf("t=%4u queued=%u active=%d loop=%d playing=%d\n",
				       (unsigned)(now - t0), (unsigned)q,
				       g_pcm_active, g_pcm_loop, g_audio_playing);
				fflush(stdout);
				last = now;
			}
		}
		SDL_Delay(5);
	}
	printf("END t=%u queued=%u pcm_active=%d audio_playing=%d\n",
	       (unsigned)(SDL_GetTicks() - t0),
	       g_pcm_dev ? (unsigned)SDL_GetQueuedAudioSize(g_pcm_dev) : 0u,
	       g_pcm_active, g_audio_playing);
	fflush(stdout);
	if (g_pcm_dev)
		SDL_CloseAudioDevice(g_pcm_dev);
	if (g_audio_dev)
		SDL_CloseAudioDevice(g_audio_dev);
	SDL_Quit();
	return 0;
}
