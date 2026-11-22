/* PAC-MAN SereOS - API publica del nucleo compartido
 *
 * Los backends (SereOS y Linux) solo necesitan este header y
 * pac_platform.h. La implementacion del nucleo es opaca: el estado del juego
 * se reserva/libera con pac_game_create/pac_game_destroy y se avanza con
 * pac_game_tick. El render es compartido (src/render) y se invoca desde el
 * backend con el rectangulo de contenido de la ventana.
 *
 * Flujo de un backend:
 *
 *   if (!pac_platform_init()) return 1;
 *   pac_game_t *g = pac_game_create();
 *   while (!pac_game_wants_close(g)) {
 *       pac_event_t ev;
 *       while (pac_platform_poll? / el backend encola eventos)
 *           pac_game_event(g, &ev);
 *       if (pac_game_tick(g)) {            // 1 = hay que redibujar
 *           pac_game_draw(g, &viewport);
 *           pac_platform_present();
 *       }
 *       pac_audio_update();
 *       el backend duerme lo que reste de frame
 *   }
 *   pac_game_destroy(g);
 *   pac_platform_shutdown();
 *
 * En SereOS el bucle lo aporta el escritorio: la tarea cooperativa llama a
 * pac_game_tick y, si devuelve 1, invalida/redibuja la ventana; los eventos
 * llegan via app_t->event al backend y se traducen a pac_event_t.
 */
#ifndef PACMAN_H
#define PACMAN_H

#include <stdint.h>
#include "pac_platform.h"

#ifdef __cplusplus
extern "C" {
#endif

/* estado opaco del juego (nucleo + render) */
typedef struct pac_game pac_game_t;

/* Reserva el estado, carga el record y deja el juego en el menu principal.
 * Devuelve NULL si no hay memoria. Emite GAME_MENU por pac_platform_log(). */
pac_game_t *pac_game_create(void);

/* Detiene audio, guarda el record si mejora y libera el estado. */
void pac_game_destroy(pac_game_t *g);

/* Entrega un evento de la plataforma (solo cuando la ventana tiene foco). */
void pac_game_event(pac_game_t *g, const pac_event_t *ev);

/* Avanza el juego usando pac_time_ms() (reloj fijo interno + limite de
 * redibujado a 30 fps). Devuelve 1 si el backend debe redibujar. */
int  pac_game_tick(pac_game_t *g);

/* Redibuja todo el contenido en `viewport` (coordenadas de pantalla). */
void pac_game_draw(pac_game_t *g, const pac_rect_t *viewport);

/* 1 si el juego pidio cerrarse (Esc en menu/game over o Q en pausa, segun
 * el estado). En SereOS el adaptador debe llamar a window_close() de forma
 * diferida, nunca liberar el estado a mano. */
int  pac_game_wants_close(const pac_game_t *g);

/* Ultimo viewport usado (util para hit-testing de raton sin redibujar). */
const pac_rect_t *pac_game_viewport(const pac_game_t *g);

/* SOLO QA/capturas: fuerza un estado concreto sin jugar la partida.
 * Escenas: "menu", "play", "pause", "gameover", "victory", "frightened".
 * En builds normales el juego nunca la llama. */
void pac_game_debug_scene(pac_game_t *g, const char *scene);

#ifdef __cplusplus
}
#endif

#endif /* PACMAN_H */
