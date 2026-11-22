/* Mock de plataforma para el harness de core (sin OS ni SDL) */
#ifndef PACMAN_MOCK_PLATFORM_H
#define PACMAN_MOCK_PLATFORM_H

#include <stdint.h>
#include "pac_platform.h"

void mock_set_size(int w, int h);
int  mock_content_x(void);
int  mock_content_y(void);
int  mock_content_w(void);
int  mock_content_h(void);
void mock_set_focused(int focused);
void mock_set_minimized(int minimized);

void mock_advance_tick(void);
uint32_t mock_get_ticks(void);
void mock_dump_ppm(const char *path, int x, int y, int w, int h);

/* lectura cruda del framebuffer 1024x768 (0 si la coordenada queda fuera).
 * El clip de pac_set_clip() no borra ni altera el contenido: solo limita
 * las primitivas que escriben, asi que leer directo permite comprobar que
 * un personaje NO pinto fuera de su area. */
uint32_t mock_fb_at(int x, int y);

void mock_serial_clear(void);
const char *mock_serial(void);

void mock_record_seed(const char *txt);
const char *mock_record(void);
int   mock_record_len(void);

int mock_audio_last_play(void);
int mock_audio_last_loop(void);
int mock_audio_play_count(void);
int mock_audio_count(int sfx);
void mock_audio_clear_counts(void);

/* secuencia de llamadas de audio: kind 0=play 1=loop 2=stop_loop 3=stop.
 * Permite comprobar orden/prioridad (p.ej. EXTRA_LIFE no pisado por WAKA). */
void mock_audio_log_clear(void);
int  mock_audio_log_count(void);
int  mock_audio_log_at(int i, int *kind, int *sfx);

#endif /* PACMAN_MOCK_PLATFORM_H */
