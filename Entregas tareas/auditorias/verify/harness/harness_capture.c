/* harness_capture.c - independent per-slot audio capture for the Linux/SDL2
 * platform of PAC-MAN SereOS.
 *
 * Uses ONLY the public platform API (include/pac_platform.h), so it keeps
 * working across internal refactors of platform_linux.c.  Audio is captured
 * at system level (PipeWire/PulseAudio null sink + parec), which is stronger
 * evidence than SDL's "disk" driver: it is the same PCM the desktop hears.
 *
 * Usage:
 *   SDL_VIDEODRIVER=dummy ./harness_capture <slot> <mode:play|loop> <ms>
 * Optional env:
 *   HARNESS_ONESHOT_GAP_MS  if >0, after the initial trigger, every gap_ms a
 *                           second pac_audio_play(<slot2>) is issued (slot2 via
 *                           argv[4]) to test one-shot precedence/truncation.
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <SDL2/SDL.h>

#include "pac_platform.h"

int main(int argc, char **argv)
{
	int slot = argc > 1 ? atoi(argv[1]) : 2;
	const char *mode = argc > 2 ? argv[2] : "play";
	int ms = argc > 3 ? atoi(argv[3]) : 1000;
	int slot2 = argc > 4 ? atoi(argv[4]) : -1;
	Uint32 t0, last;
	int i;

	if (!pac_platform_init()) {
		fprintf(stderr, "pac_platform_init FAILED\n");
		return 1;
	}
	printf("available=%d slot=%d mode=%s ms=%d\n", pac_audio_available(),
	       slot, mode, ms);
	fflush(stdout);

	t0 = SDL_GetTicks();
	last = t0;
	if (strcmp(mode, "loop") == 0)
		pac_audio_loop(slot);
	else
		pac_audio_play(slot);

	while ((int)(SDL_GetTicks() - t0) < ms) {
		Uint32 now;
		pac_audio_update();
		now = SDL_GetTicks();
		if (now - last >= 100) {
			printf("t=%4u avail=%d\n", (unsigned)(now - t0),
			       pac_audio_available());
			fflush(stdout);
			last = now;
		}
		SDL_Delay(5);
	}
	/* optional: trigger a second one-shot at the very end to test overlap */
	if (slot2 >= 0) {
		pac_audio_play(slot2);
		for (i = 0; i < 40; i++) {   /* ~200 ms tail */
			pac_audio_update();
			SDL_Delay(5);
		}
	}
	printf("END t=%u\n", (unsigned)(SDL_GetTicks() - t0));
	fflush(stdout);
	pac_platform_shutdown();
	return 0;
}
