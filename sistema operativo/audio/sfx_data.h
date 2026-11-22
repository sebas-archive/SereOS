/* audio/sfx_data.h - SFX ORIGINALES sintetizados para SereOS.
 *
 * GENERADO por tools/gen_audio.py - NO editar a mano.
 * PCM 8 bits sin signo (128 = silencio), mono, 11025 Hz.
 * Todos los sonidos fueron sintetizados desde cero para este proyecto
 * (square/triangle/sine + barridos, vibrato, ruido determinista y
 * envolventes). No se redistribuye ningun WAV de terceros.
 *
 * Clip                   muestras       ms  tipo
 * AUDIO_MENU                 2646    240.0  one-shot
 * AUDIO_START                9922    900.0  one-shot
 * AUDIO_WAKA1                1213    110.0  one-shot
 * AUDIO_WAKA2                1213    110.0  one-shot
 * AUDIO_POWER                5292    480.0  one-shot
 * AUDIO_EAT_GHOST            3308    300.0  one-shot
 * AUDIO_EAT_FRUIT            3749    340.0  one-shot
 * AUDIO_DEATH               14774   1340.0  one-shot
 * AUDIO_EXTRA_LIFE           7497    680.0  one-shot
 * AUDIO_LEVEL_CLEAR         13671   1240.0  one-shot
 * AUDIO_GAME_OVER           16978   1540.0  one-shot
 * AUDIO_SIREN_CHASE         11025   1000.0  loop
 * AUDIO_SIREN_HUNT          11025   1000.0  loop
 * AUDIO_SIREN_FRIGHT         8820    800.0  loop
 *
 * Total: 111133 bytes de PCM (10.1 s).
 */
#ifndef SEREOS_SFX_DATA_H
#define SEREOS_SFX_DATA_H
#include <stdint.h>
#include "audio.h"

#define SFX_DATA_RATE 11025
#define SFX_DATA_BYTES 111133

typedef struct {
	const uint8_t *data;   /* muestras PCM 8 bits sin signo */
	uint32_t       length; /* numero de muestras */
	uint16_t       rate;   /* frecuencia de muestreo en Hz */
	uint8_t        loopable;
} sfx_clip_t;

extern const sfx_clip_t sfx_clips[AUDIO_COUNT];

#endif /* SEREOS_SFX_DATA_H */
