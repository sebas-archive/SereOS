/* audio/audio.h - capa de audio nativa de SereOS (independiente del juego)
 *
 * Implementacion: Sound Blaster 16 (DSP + DMA 8237, PCM 8 bits mono) cuando
 * esta presente, con fallback al altavoz del PC. Los efectos son sintetizados
 * originalmente para SereOS (no se redistribuyen WAV de terceros).
 * Todo el API es NO BLOQUEANTE: audio_update() avanza la maquina de estados
 * de sonido desde el paso cooperativo del juego.
 */
#ifndef SEREOS_AUDIO_H
#define SEREOS_AUDIO_H
#include <stdint.h>

typedef enum {
	AUDIO_NONE = 0,
	AUDIO_MENU,
	AUDIO_START,
	AUDIO_WAKA1,
	AUDIO_WAKA2,
	AUDIO_POWER,
	AUDIO_EAT_GHOST,
	AUDIO_EAT_FRUIT,
	AUDIO_DEATH,
	AUDIO_EXTRA_LIFE,
	AUDIO_LEVEL_CLEAR,
	AUDIO_GAME_OVER,
	AUDIO_SIREN_CHASE,
	AUDIO_SIREN_HUNT,
	AUDIO_SIREN_FRIGHT,
	AUDIO_COUNT
} audio_sfx_t;

/* inicializa el dispositivo (SB16 / altavoz). Idempotente y tolerante a fallos. */
void audio_init(void);
int  audio_available(void);
const char *audio_backend(void);   /* "sb16", "pcspk" o "ninguno" */
const char *audio_sfx_name(audio_sfx_t id);

/* Descripcion legible del dispositivo REALMENTE detectado (contrato con la
 * UI, p.ej. la fila "Audio" de Acerca de):
 *   "SB16 0x220 IRQ5 DMA1"   (base, IRQ y DMA reales; el DSP se informa en
 *                             el log de arranque y con el comando `audio`)
 *   "solo PC speaker"
 *   "no disponible"
 * Devuelve una cadena estatica (no liberar). Llama a audio_init() si aun no
 * se ha inicializado, de modo que se puede usar en cualquier momento. */
const char *audio_detail(void);

/* Tono de diagnostico BLOQUEANTE (comandos `beep`/`audiotest` de la shell):
 * sintetiza una onda cuadrada de hz durante ms y la reproduce por el backend
 * activo (PCM por DMA en el SB16, PIT canal 2 en el altavoz del PC).
 * Devuelve 1 si sono, 0 si no hay backend disponible. NO usar desde el juego. */
int audio_test_tone(uint32_t hz, uint32_t ms);

/* reproduce un efecto una vez (no bloquea; si hay uno sonando, se encola o descarta) */
void audio_play(audio_sfx_t id);
/* bucle continuo (sirenas); AUDIO_NONE lo detiene */
void audio_loop(audio_sfx_t id);
void audio_stop_loop(void);
void audio_stop(void);

/* debe llamarse periodicamente (p.ej. cada frame del juego) para encadenar
 * bucles y liberar el canal cuando termina un efecto */
void audio_update(void);

int      audio_busy(void);
uint32_t audio_play_count(void);
uint32_t audio_underruns(void);
uint32_t audio_sample_rate(void);

/* Buffer PCM "bounce" interno del kernel: 32 KiB alineados a 64 KiB y por
 * debajo de 16 MiB (contrato del DMA 8237 de 8 bits, ver drivers/sb16.c).
 * Lo usa la capa de audio y tambien la plataforma nativa del juego para
 * entregar chunks de assets al SB16 sin duplicar memoria ni romper el
 * contrato (los assets en .rodata no estan alineados y pueden cruzar 64 KiB).
 * Devuelve NULL si el audio no esta inicializado. `capacity` recibe el
 * tamano maximo admitido por bloque. */
uint8_t *audio_dma_bounce(uint32_t *capacity);

#endif
