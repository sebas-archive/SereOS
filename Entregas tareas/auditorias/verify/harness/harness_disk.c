/* harness_disk.c - single-device capture of the real Linux platform using
 * SDL's "disk" audio driver (one device -> one file, no host mixer).
 *
 * It includes src/platform/linux/platform_linux.c UNCHANGED (same TU) only to
 * be able to close the device that is not being captured; the audio decision
 * code is the real one.  This is the ISO-free, host-independent counterpart
 * of capture_linux.sh (which captures at system level through a null sink).
 *
 * Usage:
 *   SDL_AUDIODRIVER=disk SDL_DISKAUDIOFILE=/path/x.raw \
 *     ./harness_disk <slot> <play|loop> <ms> [mix]
 * "mix" mode: plays slots 6,7,9,3,4,6 at 0/60/160/260/320/380 ms to test the
 * 6-voice PCM mixer, then runs 1500 ms so every tail is captured.
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <SDL2/SDL.h>

#include "pac_platform.h"
#include "sfx_res.h"

/* statics of the backend, same translation unit */
#include "/home/t1an/Descargas/sereos02/Pac-man SereOS/src/platform/linux/platform_linux.c"

int main(int argc, char **argv)
{
	char mode[16];
	int slot = argc > 1 ? atoi(argv[1]) : 2;
	const char *m = argc > 2 ? argv[2] : "play";
	int ms = argc > 3 ? atoi(argv[3]) : 1000;
	int i;
	Uint32 t0, last;

	if (argc > 4 && strcmp(argv[4], "mix") == 0)
		snprintf(mode, sizeof mode, "%s", "mix6");
	else if (argc > 4 && strcmp(argv[4], "mix2") == 0)
		snprintf(mode, sizeof mode, "%s", "mix2");
	else
		snprintf(mode, sizeof mode, "%s", "single");

	if (SDL_Init(SDL_INIT_AUDIO) != 0) {
		fprintf(stderr, "SDL_Init: %s\n", SDL_GetError());
		return 1;
	}
	pac_audio_init();
	printf("mode=%s slot=%d play=%s ms=%d g_audio_on=%d g_pcm_on=%d\n",
	       mode, slot, m, ms, g_audio_on, g_pcm_on);
	fflush(stdout);

	/* capture only the PCM device (synthesis would write into the same file) */
	if (g_audio_dev) {
		SDL_CloseAudioDevice(g_audio_dev);
		g_audio_dev = 0;
		g_audio_on = 0;
	}
	printf("pcm_dev=%u available=%d\n", (unsigned)g_pcm_dev,
	       pac_audio_available());
	fflush(stdout);

	t0 = SDL_GetTicks();
	last = t0;
	if (strcmp(mode, "mix2") == 0) {
		/* two distinct timbres at the same instant: both must be audible
		 * in the overlap spectrum if the mixer is real */
		pac_audio_play(3);   /* WAKA1 */
		pac_audio_play(8);   /* DEATH */
		printf("mix2: played slot 3 + slot 8 at t=0\n");
		fflush(stdout);
		while ((int)(SDL_GetTicks() - t0) < ms) {
			pac_audio_update();
			SDL_Delay(2);
		}
	} else if (strcmp(mode, "mix6") == 0) {
		static const struct { int at_ms; int slot; } seq[] = {
			{0, 6}, {55, 7}, {110, 9}, {220, 3}, {270, 4}, {300, 6}
		};
		int n = (int)(sizeof(seq) / sizeof(seq[0]));
		int si = 0;
		while ((int)(SDL_GetTicks() - t0) < ms) {
			Uint32 now = SDL_GetTicks();
			while (si < n && (int)(now - t0) >= seq[si].at_ms) {
				pac_audio_play(seq[si].slot);
				printf("t=%u play slot %d\n",
				       (unsigned)(now - t0), seq[si].slot);
				fflush(stdout);
				si++;
			}
			pac_audio_update();
			SDL_Delay(2);
		}
	} else {
		if (strcmp(m, "loop") == 0)
			pac_audio_loop(slot);
		else
			pac_audio_play(slot);
		while ((int)(SDL_GetTicks() - t0) < ms) {
			pac_audio_update();
			SDL_Delay(2);
		}
	}
	printf("END t=%u\n", (unsigned)(SDL_GetTicks() - t0));
	fflush(stdout);
	if (g_pcm_dev)
		SDL_CloseAudioDevice(g_pcm_dev);
	SDL_Quit();
	return 0;
}
