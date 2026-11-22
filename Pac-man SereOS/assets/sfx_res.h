/* assets/sfx_res.h - SFX PCM definitivos derivados de Res (PAC-MAN SereOS)
 *
 * PCM 8 bits SIN SIGNO, mono, 11025 Hz (compatible con el SB16 de SereOS
 * y con SDL Linux). Generado desde los 11 WAV de Res (incluye intermission).
 * Recurso de uso privado/academico; ver assets/LICENSE_RES.md.
 *
 * Slots: identicos a `pac_audio_sfx_t` (pac_platform.h) con la adicion de
 * PAC_SFX_GHOST_RESPAWN al final, es decir:
 *   0 NONE | 1 MENU | 2 START | 3 WAKA1 | 4 WAKA2 | 5 POWER |
 *   6 EAT_GHOST | 7 EAT_FRUIT | 8 DEATH | 9 EXTRA_LIFE | 10 LEVEL_CLEAR |
 *   11 GAME_OVER | 12 SIREN_CHASE | 13 SIREN_HUNT | 14 SIREN_FRIGHT |
 *   15 GHOST_RESPAWN
 * Slots con WAV: 2,3,4,6,7,8,9,10,12,13,15. Sin WAV (data=0): 1,5,11,14.
 *   START=game start, WAKA1/2=waka1/2, EAT_GHOST=eat ghost,
 *   EAT_FRUIT=eat fruit, EXTRA_LIFE=extra life, DEATH=pacman death,
 *   LEVEL_CLEAR=intermission (one-shot, 2 trozos),
 *   GHOST_RESPAWN=ghost respawn (periodo de bucle; flag loop=0 por defecto:
 *   el bucle se pide con pac_audio_loop),
 *   SIREN_HUNT=hunted siren (loop), SIREN_CHASE=hunter siren (loop).
 *
 * Clips largos (START y LEVEL_CLEAR) se entregan troceados en bloques <=32768
 * (limite SB16):
 *   pacasset_sfx_res_chunk_count[slot]     numero de trozos (1 o 2)
 *   pacasset_sfx_res_chunks[slot][i]       puntero al trozo i
 *   pacasset_sfx_res_chunk_len[slot][i]    muestras del trozo i
 * `pacasset_sfx_res[slot].data` apunta al primer trozo y `.len` es el total.
 * Para reproducir en SB16: enviar trozos de uno en uno respetando el limite
 * de bloque; en Linux se puede reproducir el total de una vez.
 *
 * Sirenas: `pacasset_siren_hunt_res[4]` / `pacasset_siren_chase_res[4]` con
 * pitch +0/+10/+20/+30% ya remuestreado (mismo rate 11025); el slot 13/12
 * del array principal apunta a la variante +0%.
 */
#ifndef PACMAN_SFX_RES_H
#define PACMAN_SFX_RES_H
#include <stdint.h>

#define PACASSET_RES_SFX_RATE          11025
#define PACASSET_RES_SFX_SLOTS         16
#define PACASSET_RES_SFX_MAX_CHUNKS    2
#define PACASSET_RES_SIREN_VARIANTS    4

#define PACASSET_RES_SFX_NONE          0
#define PACASSET_RES_SFX_MENU          1
#define PACASSET_RES_SFX_START         2
#define PACASSET_RES_SFX_WAKA1         3
#define PACASSET_RES_SFX_WAKA2         4
#define PACASSET_RES_SFX_POWER         5
#define PACASSET_RES_SFX_EAT_GHOST     6
#define PACASSET_RES_SFX_EAT_FRUIT     7
#define PACASSET_RES_SFX_DEATH         8
#define PACASSET_RES_SFX_EXTRA_LIFE    9
#define PACASSET_RES_SFX_LEVEL_CLEAR   10
#define PACASSET_RES_SFX_GAME_OVER     11
#define PACASSET_RES_SFX_SIREN_CHASE   12
#define PACASSET_RES_SFX_SIREN_HUNT    13
#define PACASSET_RES_SFX_SIREN_FRIGHT  14
#define PACASSET_RES_SFX_GHOST_RESPAWN 15

typedef struct {
	const uint8_t *data;   /* muestras PCM u8 (primer trozo si chunks>1) */
	uint32_t       len;    /* muestras totales (todos los trozos) */
} pac_res_sfx_t;

extern const pac_res_sfx_t pacasset_sfx_res[PACASSET_RES_SFX_SLOTS];
extern const uint8_t pacasset_sfx_res_loop[PACASSET_RES_SFX_SLOTS];
extern const uint8_t pacasset_sfx_res_chunk_count[PACASSET_RES_SFX_SLOTS];
extern const uint8_t *const pacasset_sfx_res_chunks
        [PACASSET_RES_SFX_SLOTS][PACASSET_RES_SFX_MAX_CHUNKS];
extern const uint32_t pacasset_sfx_res_chunk_len
        [PACASSET_RES_SFX_SLOTS][PACASSET_RES_SFX_MAX_CHUNKS];
extern const uint16_t pacasset_sfx_res_rate;
extern const uint32_t pacasset_sfx_res_total_bytes;

/* 4 variantes de frecuencia (pitch +0/10/20/30%) de cada sirena */
extern const pac_res_sfx_t pacasset_siren_hunt_res[PACASSET_RES_SIREN_VARIANTS];
extern const pac_res_sfx_t pacasset_siren_chase_res[PACASSET_RES_SIREN_VARIANTS];
extern const uint8_t pacasset_siren_variant_pct[PACASSET_RES_SIREN_VARIANTS];

static inline int pacasset_sfx_res_available(int slot)
{
	return (slot >= 0 && slot < PACASSET_RES_SFX_SLOTS &&
	        pacasset_sfx_res[slot].data != 0 && pacasset_sfx_res[slot].len != 0u);
}

#endif /* PACMAN_SFX_RES_H */
