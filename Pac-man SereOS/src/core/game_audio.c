/* PAC-MAN SereOS - eventos de audio del nucleo
 *
 * Traduce los efectos del juego a la API de plataforma pac_audio_*.
 * Si el backend no tiene audio (pac_audio_available()==0), el juego sigue
 * funcionando en silencio: ninguna llamada bloquea.
 *
 * Modelo:
 *   - g->audio_hold_ms: tiempo que el one-shot en curso debe sonar sin que la
 *     sirena lo pise. Se calcula con la duracion real del clip (assets/sfx_res)
 *     + 15-20 ms de margen.
 *   - g->audio_oneshot: efecto one-shot en curso; su prioridad impide que un
 *     evento de menor importancia (p.ej. el waka de un dot) lo corte.
 *   - g->siren: ultima sirena pedida al backend (idempotencia). Solo se
 *     actualiza cuando el audio esta disponible; si no, el siguiente
 *     update_siren la rearma.
 *   - g->siren_grace_ms: ventana de gracia tras comer un dot; sin mezclador
 *     evita que la sirena se reinicie en cada punto (stutter).
 */
#include <stdint.h>
#include "pac_platform.h"
#include "pac_game.h"
#include "game_audio.h"

static void sound_reset(pac_game_t *g)
{
	g->siren = PAC_SFX_NONE;
	g->audio_oneshot = PAC_SFX_NONE;
	g->audio_hold_ms = 0;
	g->siren_grace_ms = 0;
}

void pac_sound_init(pac_game_t *g)
{
	if (!g)
		return;
	pac_audio_init();
	g->audio_ok = pac_audio_available();
	sound_reset(g);
}

/* Duracion real del clip + margen (assets/sfx_res.c: muestras @11025 Hz).
 * START se mantiene alineado con PAC_READY_START_MS (4500 ms), no con el
 * clip (4234 ms). */
static int effect_hold_ms(int sfx)
{
	switch (sfx) {
	case PAC_SFX_START:        return 4500;  /* READY_START_MS (clip 4234) */
	case PAC_SFX_DEATH:        return 2000;  /* clip 1535; animacion 2800 */
	case PAC_SFX_GAME_OVER:    return 1200;  /* sintetizado 600 */
	case PAC_SFX_LEVEL_CLEAR:  return 5300;  /* intermission 5204 */
	case PAC_SFX_EXTRA_LIFE:   return 1920;  /* clip 1899 */
	case PAC_SFX_GHOST_RESPAWN:return 300;   /* clip 266 */
	case PAC_SFX_EAT_GHOST:    return 590;   /* clip 574 */
	case PAC_SFX_EAT_FRUIT:    return 460;   /* clip 440 */
	case PAC_SFX_POWER:        return 320;   /* sintetizado 160 + margen */
	case PAC_SFX_MENU:         return 260;   /* sintetizado 240 + margen */
	case PAC_SFX_WAKA1:
	case PAC_SFX_WAKA2:        return 100;   /* clip 84.5 */
	default:                   return 0;
	}
}

/* Prioridad de one-shots: un efecto en curso con hold solo se deja pisar por
 * otro de prioridad >=. Sin mezclador, esto evita que EXTRA_LIFE/DEATH/etc.
 * desaparezcan porque el mismo tick reproduce el sonido del propio evento. */
static int effect_priority(int sfx)
{
	switch (sfx) {
	case PAC_SFX_DEATH:        return 100;
	case PAC_SFX_GAME_OVER:    return 90;
	case PAC_SFX_EXTRA_LIFE:   return 80;
	case PAC_SFX_LEVEL_CLEAR:  return 75;
	case PAC_SFX_START:        return 70;
	case PAC_SFX_EAT_GHOST:    return 60;
	case PAC_SFX_EAT_FRUIT:    return 50;
	case PAC_SFX_POWER:        return 40;
	case PAC_SFX_GHOST_RESPAWN:return 35;
	case PAC_SFX_MENU:         return 20;
	case PAC_SFX_WAKA1:
	case PAC_SFX_WAKA2:        return 10;
	default:                   return 0;
	}
}

void pac_sound_play(pac_game_t *g, int sfx)
{
	int hold;

	if (!g || !g->audio_ok || sfx <= PAC_SFX_NONE || sfx >= PAC_SFX_COUNT)
		return;
	/* no pisar un one-shot en curso de mayor o igual prioridad */
	if (g->audio_oneshot > PAC_SFX_NONE && g->audio_hold_ms > 0 &&
	    effect_priority(sfx) < effect_priority(g->audio_oneshot))
		return;
	hold = effect_hold_ms(sfx);
	if (hold > 0) {
		/* modo estricto: el efecto para el loop y bloquea la sirena
		 * hasta que termine; luego update_siren la reanuda. */
		g->siren = PAC_SFX_NONE;
		pac_audio_stop_loop();
		g->audio_hold_ms = hold;
		g->audio_oneshot = sfx;
	}
	pac_audio_play(sfx);
}

void pac_sound_set_siren(pac_game_t *g, int sfx)
{
	if (!g)
		return;
	if (g->siren == sfx)
		return;
	if (!g->audio_ok) {
		/* sin audio no se cachea el estado: al reactivarlo update_siren
		 * debe poder rearmar la sirena. */
		if (sfx == PAC_SFX_NONE)
			g->siren = sfx;
		return;
	}
	g->siren = sfx;
	if (sfx == PAC_SFX_NONE)
		pac_audio_stop_loop();
	else
		pac_audio_loop(sfx);
}

void pac_sound_stop(pac_game_t *g)
{
	if (!g)
		return;
	sound_reset(g);
	if (!g->audio_ok)
		return;
	pac_audio_stop();
}

void pac_sound_update(pac_game_t *g)
{
	if (!g || !g->audio_ok)
		return;
	pac_audio_update();
}
