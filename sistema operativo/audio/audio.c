/* audio/audio.c - capa de audio de SereOS (independiente del juego)
 *
 * Backends:
 *   1. "sb16":  Sound Blaster 16 con PCM 8 bits mono por DMA (drivers/sb16.c).
 *      Deteccion con reset del DSP de 0x220 a 0x280 (paso 0x10); fin de
 *      bloque por IRQ 5 (con red de seguridad por tiempo).
 *   2. "pcspk": altavoz del PC (drivers/speaker.c) como fallback real cuando
 *      no hay SB16; reproduce tonos cortos y sirenas alternando frecuencias.
 *
 * audio_detail() describe el dispositivo detectado y es el contrato que usa
 * la UI (Acerca de). audio_test_tone() es el tono de diagnostico de la shell.
 *
 * Diseno NO BLOQUEANTE: audio_play()/audio_loop() solo encolan o disparan el
 * hardware; audio_update() avanza la maquina de estados desde el paso
 * cooperativo del juego (o desde cualquier bucle principal). Nunca se duerme
 * ni se espera al hardware; la finalizacion del DMA se detecta por tiempo en
 * drivers/sb16.c y las sirenas se rearman solas.
 *
 * Cola de one-shots: 4 peticiones. Si el canal esta ocupado y la cola llena,
 * la peticion se descarta y se incrementa audio_underruns() (peticiones
 * perdidas por saturacion; no es un error de hardware).
 *
 * Los SFX son originales y estan en audio/sfx_data.c (generados por
 * tools/gen_audio.py). El buffer PCM que se entrega al DMA es una bounce
 * buffer estatica alineada a 64 KiB y de 32 KiB, que cumple las restricciones
 * del 8237 (por debajo de 16 MiB y sin cruzar paginas de 64 KiB).
 */
#include "audio.h"
#include "sfx_data.h"
#include "sb16.h"
#include "speaker.h"
#include "timer.h"
#include "string.h"

#define AUDIO_QUEUE_MAX   4
#define AUDIO_DMA_SIZE    SB16_MAX_BUFFER

typedef enum {
	BACKEND_NONE = 0,
	BACKEND_SB16,
	BACKEND_PCSPK
} audio_backend_kind_t;

/* bounce buffer del DMA: 64 KiB de alineacion => nunca cruza pagina de DMA */
static uint8_t audio_dma[AUDIO_DMA_SIZE] __attribute__((aligned(65536)));

static int                    audio_ready;
static audio_backend_kind_t   backend;
static uint32_t               play_counter;
static uint32_t               lost_requests;

static uint8_t                queue[AUDIO_QUEUE_MAX];
static int                    queue_head;
static int                    queue_count;

static audio_sfx_t            loop_sfx;
static int                    loop_playing;   /* el clip en curso es el bucle */
static int                    loop_phase;     /* fase de sirena en pcspk */
static uint32_t               loop_next_tick;

static int                    pcspk_active;
static int                    pcspk_is_loop;
static uint32_t               pcspk_off_tick;

/* ======================================================================== */
/* utilidades                                                               */
/* ======================================================================== */
static const char *const sfx_names[AUDIO_COUNT] = {
	"none", "menu", "start", "waka1", "waka2", "power", "eat_ghost",
	"eat_fruit", "death", "extra_life", "level_clear", "game_over",
	"siren_chase", "siren_hunt", "siren_fright"
};

static uint32_t ms_to_ticks(uint32_t ms) {
	uint32_t hz = timer_hz();
	uint32_t ticks;
	if (hz == 0) hz = 100u;
	if (ms == 0) return 0;
	ticks = (ms * hz + 999u) / 1000u;
	return ticks ? ticks : 1u;
}

static const sfx_clip_t *clip_of(audio_sfx_t id) {
	const sfx_clip_t *c;
	if ((int)id <= (int)AUDIO_NONE || (int)id >= (int)AUDIO_COUNT) return 0;
	c = &sfx_clips[id];
	if (!c->data || c->length == 0) return 0;
	return c;
}

static int queue_push(audio_sfx_t id) {
	if (queue_count >= AUDIO_QUEUE_MAX) return 0;
	queue[(queue_head + queue_count) % AUDIO_QUEUE_MAX] = (uint8_t)id;
	queue_count++;
	return 1;
}

static audio_sfx_t queue_pop(void) {
	audio_sfx_t id;
	if (queue_count <= 0) return AUDIO_NONE;
	id = (audio_sfx_t)queue[queue_head];
	queue_head = (queue_head + 1) % AUDIO_QUEUE_MAX;
	queue_count--;
	return id;
}

/* copia el clip a la bounce buffer y arranca el DMA; 1 si sono */
static int sb16_start_clip(const sfx_clip_t *c, int is_loop) {
	uint32_t len;

	if (!c) return 0;
	len = c->length;
	if (len > AUDIO_DMA_SIZE) { lost_requests++; return 0; }
	memcpy(audio_dma, c->data, len);
	if (!sb16_play(audio_dma, len, c->rate)) {
		lost_requests++;
		loop_playing = 0;
		return 0;
	}
	loop_playing = is_loop ? 1 : 0;
	return 1;
}

/* ======================================================================== */
/* fallback: altavoz del PC                                                 */
/* ======================================================================== */
static void pcspk_map(audio_sfx_t id, uint32_t *hz, uint32_t *ms) {
	switch (id) {
	case AUDIO_MENU:       *hz = 700;  *ms = 110; break;
	case AUDIO_START:      *hz = 950;  *ms = 220; break;
	case AUDIO_WAKA1:      *hz = 520;  *ms = 70;  break;
	case AUDIO_WAKA2:      *hz = 390;  *ms = 70;  break;
	case AUDIO_POWER:      *hz = 880;  *ms = 180; break;
	case AUDIO_EAT_GHOST:  *hz = 660;  *ms = 140; break;
	case AUDIO_EAT_FRUIT:  *hz = 1000; *ms = 150; break;
	case AUDIO_DEATH:      *hz = 180;  *ms = 420; break;
	case AUDIO_EXTRA_LIFE: *hz = 1250; *ms = 260; break;
	case AUDIO_LEVEL_CLEAR: *hz = 1000; *ms = 350; break;
	case AUDIO_GAME_OVER:  *hz = 140;  *ms = 520; break;
	default:               *hz = 440;  *ms = 120; break;
	}
}

static void pcspk_oneshot(audio_sfx_t id) {
	uint32_t hz, ms;
	pcspk_map(id, &hz, &ms);
	speaker_tone(hz);
	pcspk_active = 1;
	pcspk_is_loop = 0;
	pcspk_off_tick = timer_ticks() + ms_to_ticks(ms);
}

/* apaga el one-shot del altavoz del PC cuando vence. Se llama desde
 * audio_update() para TODOS los backends: en BACKEND_SB16 tambien puede
 * haberse disparado un pcspk_oneshot() como fallback puntual de sb16_play()
 * (audio_play()), y antes ese tono no se apagaba nunca (se quedaba sonando
 * hasta audio_stop()). */
static void pcspk_release_expired(void) {
	uint32_t now;
	if (!pcspk_active || pcspk_is_loop) return;
	now = timer_ticks();
	if ((int32_t)(now - pcspk_off_tick) >= 0) {
		speaker_off();
		pcspk_active = 0;
	}
}

/* patron de sirena del altavoz del PC: frecuencia e intervalo por fase */
static void pcspk_siren(audio_sfx_t id, int phase, uint32_t *hz, uint32_t *ms) {
	switch (id) {
	case AUDIO_SIREN_CHASE:
		*hz = phase ? 247u : 196u;  *ms = 250; break;
	case AUDIO_SIREN_HUNT:
		*hz = phase ? 370u : 294u;  *ms = 125; break;
	case AUDIO_SIREN_FRIGHT:
		*hz = phase ? 165u : 131u;  *ms = 180; break;
	default:
		*hz = 220u; *ms = 250; break;
	}
}

/* ======================================================================== */
/* API publica                                                              */
/* ======================================================================== */
void audio_init(void) {
	if (audio_ready) return;
	audio_ready = 1;
	backend = BACKEND_NONE;
	play_counter = 0;
	lost_requests = 0;
	queue_head = 0;
	queue_count = 0;
	loop_sfx = AUDIO_NONE;
	loop_playing = 0;
	loop_phase = 0;
	loop_next_tick = 0;
	pcspk_active = 0;
	pcspk_is_loop = 0;
	pcspk_off_tick = 0;

	speaker_off();

	if (sb16_init()) {
		backend = BACKEND_SB16;
	} else {
		/* el altavoz del PC es el fallback universal */
		backend = BACKEND_PCSPK;
	}
}

int audio_available(void) { return audio_ready && backend != BACKEND_NONE; }

const char *audio_backend(void) {
	if (!audio_ready) return "ninguno";
	switch (backend) {
	case BACKEND_SB16:  return "sb16";
	case BACKEND_PCSPK: return "pcspk";
	default:            return "ninguno";
	}
}

const char *audio_sfx_name(audio_sfx_t id) {
	if ((int)id < 0 || (int)id >= (int)AUDIO_COUNT) return "none";
	return sfx_names[id];
}

const char *audio_detail(void) {
	static char detail[64];

	if (!audio_ready) audio_init();

	switch (backend) {
	case BACKEND_SB16:
		/* cadena compacta: la fila "Audio" de Acerca de es estrecha y debe
		 * caber completa; el detalle de DSP se muestra en `audio` y en el
		 * log de arranque (ver sb16_version()); se mantiene el formato
		 * documentado en el contrato. */
		snprintf(detail, sizeof(detail),
		         "SB16 0x%03x IRQ%u DMA%u",
		         (unsigned)sb16_base(), (unsigned)sb16_irq(),
		         (unsigned)SB16_DMA);
		return detail;
	case BACKEND_PCSPK:
		return "solo PC speaker";
	default:
		return "no disponible";
	}
}

void audio_play(audio_sfx_t id) {
	const sfx_clip_t *c;

	if (!audio_ready) audio_init();
	c = clip_of(id);
	if (!c) return;                 /* AUDIO_NONE o id invalido: se ignora */
	play_counter++;

	if (backend == BACKEND_SB16) {
		if (sb16_busy()) {
			if (!queue_push(id)) lost_requests++;
			return;
		}
		if (!sb16_start_clip(c, 0)) pcspk_oneshot(id);   /* fallback puntual */
	} else if (backend == BACKEND_PCSPK) {
		pcspk_oneshot(id);
	}
}

void audio_loop(audio_sfx_t id) {
	const sfx_clip_t *c;

	if (!audio_ready) audio_init();
	c = clip_of(id);
	if (!c) { audio_stop_loop(); return; }

	loop_sfx = id;
	loop_phase = 0;

	if (backend == BACKEND_SB16) {
		if (loop_playing && sb16_busy()) {
			/* cambio de sirena en caliente: cortar el clip anterior */
			sb16_stop();
			loop_playing = 0;
		} else if (sb16_busy()) {
			loop_playing = 0;   /* hay un one-shot: el bucle espera */
			return;
		}
		if (!sb16_start_clip(c, 1)) lost_requests++;
	} else if (backend == BACKEND_PCSPK) {
		loop_next_tick = timer_ticks();
	}
}

void audio_stop_loop(void) {
	int had_loop = (loop_sfx != AUDIO_NONE) || loop_playing;
	loop_sfx = AUDIO_NONE;
	loop_phase = 0;
	loop_next_tick = 0;
	if (backend == BACKEND_SB16) {
		/* si el canal esta ocupado por el bucle (aunque loop_playing se
		 * hubiera desincronizado) se para el DMA para no dejarlo
		 * rearmandose desde audio_update() */
		if (had_loop) { sb16_stop(); loop_playing = 0; }
	} else if (backend == BACKEND_PCSPK) {
		if (pcspk_active && pcspk_is_loop) {
			speaker_off();
			pcspk_active = 0;
			pcspk_is_loop = 0;
		}
	}
}

void audio_stop(void) {
	queue_count = 0;
	queue_head = 0;
	loop_sfx = AUDIO_NONE;
	loop_playing = 0;
	loop_phase = 0;
	loop_next_tick = 0;
	if (backend == BACKEND_SB16) sb16_stop();
	speaker_off();
	pcspk_active = 0;
	pcspk_is_loop = 0;
	pcspk_off_tick = 0;
}

void audio_update(void) {
	if (!audio_ready) return;

	/* un fallback puntual al altavoz del PC debe apagarse aunque el
	 * backend activo sea el SB16 (ver pcspk_release_expired) */
	pcspk_release_expired();

	if (backend == BACKEND_SB16) {
		if (sb16_busy()) return;   /* todavia suena algo */

		if (queue_count > 0) {
			audio_sfx_t id = queue_pop();
			const sfx_clip_t *c = clip_of(id);
			if (c && !sb16_start_clip(c, 0)) pcspk_oneshot(id);
			return;
		}
		if (loop_sfx != AUDIO_NONE) {
			const sfx_clip_t *c = clip_of(loop_sfx);
			if (c && !sb16_start_clip(c, 1)) lost_requests++;
			return;
		}
		loop_playing = 0;
		return;
	}

	if (backend == BACKEND_PCSPK) {
		uint32_t now = timer_ticks();

		/* el one-shot vencido ya se apago en pcspk_release_expired() */
		/* rearmar la sirena en el altavoz del PC */
		if (loop_sfx != AUDIO_NONE) {
			if (pcspk_active && !pcspk_is_loop) return;   /* respeta one-shot */
			if (!pcspk_active || (int32_t)(now - loop_next_tick) >= 0) {
				uint32_t hz, ms;
				pcspk_siren(loop_sfx, loop_phase, &hz, &ms);
				loop_phase ^= 1;
				speaker_tone(hz);
				pcspk_active = 1;
				pcspk_is_loop = 1;
				loop_next_tick = now + ms_to_ticks(ms);
			}
		}
	}
}

int audio_busy(void) {
	if (!audio_ready) return 0;
	if (backend == BACKEND_SB16)
		return sb16_busy() || queue_count > 0 || loop_sfx != AUDIO_NONE;
	if (backend == BACKEND_PCSPK)
		return pcspk_active || loop_sfx != AUDIO_NONE;
	return 0;
}

uint32_t audio_play_count(void) { return play_counter; }
uint32_t audio_underruns(void) { return lost_requests; }

uint32_t audio_sample_rate(void) {
	/* el altavoz del PC no reproduce PCM: 0 es honesto */
	return backend == BACKEND_SB16 ? SFX_DATA_RATE : 0u;
}

uint8_t *audio_dma_bounce(uint32_t *capacity) {
	if (capacity) *capacity = AUDIO_DMA_SIZE;
	if (!audio_ready) return 0;
	return audio_dma;
}

/* Tonos de diagnostico para la shell (beep / audiotest). Sintetiza una onda
 * cuadrada de 8 bits sin signo (128 = silencio) en la bounce buffer y la
 * reproduce con el backend activo. Bloquea como maximo `ms` milisegundos
 * usando timer_sleep_ms() (hlt), por lo que no consume CPU del anfitrion. */
int audio_test_tone(uint32_t hz, uint32_t ms) {
	uint8_t *buf;
	uint32_t cap = 0, n, i, rate;

	if (!audio_ready) audio_init();
	if (hz == 0) hz = 440;
	if (ms == 0) ms = 200;

	if (backend == BACKEND_SB16) {
		buf = audio_dma_bounce(&cap);
		if (!buf || cap == 0) return 0;

		rate = SFX_DATA_RATE;
		n = (rate * ms) / 1000u;
		if (n < 128u) n = 128u;
		if (n > cap) n = cap;

		/* oscilador DDS: la fase de 16.16 bits evita el error de tono que
		 * produce dividir rate/hz con enteros en las notas agudas */
		{
			uint32_t phase = 0;
			uint32_t inc = (hz << 16) / rate;
			if (inc == 0) inc = 1;
			for (i = 0; i < n; i++) {
				phase += inc;
				buf[i] = (uint8_t)((phase & 0x8000u) ? 219u : 37u);
			}
		}

		if (sb16_busy()) sb16_stop();   /* diagnostico: corta lo que hubiera */
		if (!sb16_play(buf, n, rate)) return 0;

		/* fin real por IRQ5 (dma_done) o, si no llegara, por tiempo */
		while (sb16_busy()) timer_sleep_ms(2);
		sb16_stop();
		return 1;
	}

	if (backend == BACKEND_PCSPK) {
		speaker_tone(hz);
		timer_sleep_ms(ms);
		speaker_off();
		return 1;
	}

	return 0;
}
