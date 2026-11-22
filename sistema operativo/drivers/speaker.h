/* drivers/speaker.h - altavoz del PC (PIT canal 2). Sonido no bloqueante. */
#ifndef SEREOS_SPEAKER_H
#define SEREOS_SPEAKER_H
#include <stdint.h>

void speaker_init(void);
void speaker_tone(uint32_t hz);   /* empieza a sonar (0 = silencio) */
void speaker_off(void);
void speaker_beep(uint32_t hz, uint32_t ms);  /* beep bloqueante corto */

#endif
