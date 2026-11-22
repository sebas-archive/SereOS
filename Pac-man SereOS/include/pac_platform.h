/* PAC-MAN SereOS - contrato de plataforma (pac_platform)
 *
 * Unica frontera entre el nucleo/render compartidos y cada backend. El core
 * NUNCA incluye headers de SereOS (gui/, graphics/, drivers/...) ni SDL:
 * solo este header y la libreria estandar de C. Cada backend implementa
 * todas las funciones de este contrato.
 *
 * Convenciones:
 *   - Colores de la API: 0x00RRGGBB (independientes del framebuffer real).
 *   - Sprites: uint16_t RGB565 con clave de transparencia 0xF81F.
 *   - Texto: estilos tipograficos del sistema (Inter/JetBrains Mono).
 *     y es la parte superior de la caja de linea (igual que graphics/text.h).
 *   - Las funciones son no bloqueantes salvo que se indique lo contrario.
 */
#ifndef PACMAN_PLATFORM_H
#define PACMAN_PLATFORM_H

#include <stdint.h>
#include <stddef.h>

#define PAC_PLATFORM_ABI 1

/* ------------------------------------------------------------------ */
/* tipos basicos                                                       */
/* ------------------------------------------------------------------ */
typedef struct {
	int x, y, w, h;
} pac_rect_t;

/* teclas logicas: backend traduce su teclado fisico a este enum */
typedef enum {
	PAC_KEY_NONE = 0,
	PAC_KEY_ESC,
	PAC_KEY_ENTER,
	PAC_KEY_SPACE,
	PAC_KEY_UP,
	PAC_KEY_DOWN,
	PAC_KEY_LEFT,
	PAC_KEY_RIGHT,
	PAC_KEY_A, PAC_KEY_B, PAC_KEY_C, PAC_KEY_D, PAC_KEY_E, PAC_KEY_F,
	PAC_KEY_G, PAC_KEY_H, PAC_KEY_I, PAC_KEY_J, PAC_KEY_K, PAC_KEY_L,
	PAC_KEY_M, PAC_KEY_N, PAC_KEY_O, PAC_KEY_P, PAC_KEY_Q, PAC_KEY_R,
	PAC_KEY_S, PAC_KEY_T, PAC_KEY_U, PAC_KEY_V, PAC_KEY_W, PAC_KEY_X,
	PAC_KEY_Y, PAC_KEY_Z,
	PAC_KEY_0, PAC_KEY_1, PAC_KEY_2, PAC_KEY_3, PAC_KEY_4,
	PAC_KEY_5, PAC_KEY_6, PAC_KEY_7, PAC_KEY_8, PAC_KEY_9, PAC_KEY_F11,
	PAC_KEY_COUNT
} pac_key_t;

typedef enum {
	PAC_EVENT_NONE = 0,
	PAC_EVENT_KEY_DOWN,
	PAC_EVENT_KEY_UP,
	PAC_EVENT_MOUSE_MOVE,
	PAC_EVENT_MOUSE_DOWN,
	PAC_EVENT_MOUSE_UP,
	PAC_EVENT_MOUSE_WHEEL,
	PAC_EVENT_QUIT
} pac_event_type_t;

#define PAC_MOUSE_LEFT   1
#define PAC_MOUSE_RIGHT  2
#define PAC_MOUSE_MIDDLE 4

typedef struct {
	uint8_t  type;      /* pac_event_type_t */
	uint8_t  pressed;   /* 1 pulsado / 0 soltado (teclas y botones) */
	uint16_t key;       /* pac_key_t */
	char     ch;        /* caracter ASCII/Latin-1 si aplica */
	int16_t  mouse_x;   /* posicion absoluta del cursor */
	int16_t  mouse_y;
	uint8_t  button;    /* PAC_MOUSE_* */
	int8_t   wheel;
	uint32_t tick;      /* pac_time_ms() del evento */
} pac_event_t;

/* estilos tipograficos (mismos tamanos que el sistema SereOS) */
typedef enum {
	PAC_TEXT_CAPTION = 0,   /* UI  10 px regular */
	PAC_TEXT_SMALL,         /* UI  11 px regular */
	PAC_TEXT_BODY,          /* UI  13 px regular */
	PAC_TEXT_LABEL,         /* UI  12 px semibold */
	PAC_TEXT_TITLE,         /* UI  16 px semibold */
	PAC_TEXT_HEADLINE,      /* UI  20 px semibold */
	PAC_TEXT_DISPLAY,       /* UI  30 px semibold */
	PAC_TEXT_MONO,          /* mono 13 px */
	PAC_TEXT_MONO_SMALL,    /* mono 11 px */
	PAC_TEXT_STYLE_COUNT
} pac_text_style_t;

/* efectos de audio (mismo orden/identidad que audio/audio.h de SereOS) */
typedef enum {
	PAC_SFX_NONE = 0,
	PAC_SFX_MENU,
	PAC_SFX_START,
	PAC_SFX_WAKA1,
	PAC_SFX_WAKA2,
	PAC_SFX_POWER,
	PAC_SFX_EAT_GHOST,
	PAC_SFX_EAT_FRUIT,
	PAC_SFX_DEATH,
	PAC_SFX_EXTRA_LIFE,
	PAC_SFX_LEVEL_CLEAR,
	PAC_SFX_GAME_OVER,
	PAC_SFX_SIREN_CHASE,
	PAC_SFX_SIREN_HUNT,
	PAC_SFX_SIREN_FRIGHT,
	PAC_SFX_GHOST_RESPAWN,   /* extension del componente: respawn de ojos */
	PAC_SFX_COUNT
} pac_audio_sfx_t;

/* ------------------------------------------------------------------ */
/* ciclo de vida, ventana, tiempo, log y cierre                        */
/* ------------------------------------------------------------------ */
/* Inicializa el backend (framebuffer, ventana, input, audio...).
 * Devuelve 1 si puede ejecutarse el juego, 0 si el backend no esta listo. */
int  pac_platform_init(void);

/* Libera todos los recursos del backend. Idempotente. */
void pac_platform_shutdown(void);

/* Tamano logico del lienzo de render (p.ej. 1024x768 en Linux, area de
 * contenido de la ventana en SereOS). */
int  pac_platform_width(void);
int  pac_platform_height(void);

/* Rectangulo de contenido donde dibujar (coordenadas de pantalla). En
 * Linux suele ser (0,0,width,height); en SereOS es el area interior de la
 * ventana del compositor. */
void pac_platform_content_rect(pac_rect_t *out);

/* 1 si la ventana tiene el foco; el core congela la partida si no. */
int  pac_platform_focused(void);
/* 1 si la ventana esta minimizada. */
int  pac_platform_minimized(void);

/* Pide al anfitrion cerrar la ventana/aplicacion (cierre diferido). */
void pac_platform_request_close(void);

/* Pantalla completa / maximizado. Devuelve 1 si se aplico. */
int  pac_platform_set_fullscreen(int enabled);
int  pac_platform_get_fullscreen(void);

/* Escribe un marcador de QA (GAME_MENU, GAME_START, ...). En SereOS va a
 * COM1; en Linux a stderr (si PACMAN_LOG=1 o siempre, a decision del
 * backend). No usar para depuracion ruidosa. */
void pac_platform_log(const char *marker);

/* Tiempo monotono en milisegundos desde que arranco la plataforma. */
uint32_t pac_time_ms(void);

/* Memoria del juego (SereOS: kmalloc/kfree; Linux: malloc/free). */
void *pac_alloc(size_t size);
void  pac_free(void *ptr);

/* Persistencia de clave/valor en texto (record). Devuelve bytes leidos o
 * <0 si no existe (SereOS: RAMFS; Linux: fichero de usuario). */
int  pac_storage_read(const char *key, void *buf, int max_len);
int  pac_storage_write(const char *key, const void *buf, int len);

/* ------------------------------------------------------------------ */
/* render                                                              */
/* ------------------------------------------------------------------ */
void pac_set_clip(int x, int y, int w, int h);
void pac_reset_clip(void);
void pac_get_clip(pac_rect_t *out);

void pac_fill_rect(int x, int y, int w, int h, uint32_t color);
void pac_fill_rect_alpha(int x, int y, int w, int h, uint32_t color, uint8_t alpha);
void pac_draw_rect(int x, int y, int w, int h, uint32_t color);
void pac_fill_round_rect(int x, int y, int w, int h, int radius, uint32_t color);
void pac_fill_round_rect_alpha(int x, int y, int w, int h, int radius,
                               uint32_t color, uint8_t alpha);
void pac_draw_round_rect(int x, int y, int w, int h, int radius, uint32_t color);

/* Copia un buffer 0x00RRGGBB (p.ej. fondo pre-renderizado del laberinto). */
void pac_blit_rgb(int x, int y, int w, int h, const uint32_t *pixels);

/* Cobertura alfa 8bpp (fuente arcade, mascaras). */
void pac_blit_alpha8(int x, int y, int w, int h, const uint8_t *mask,
                     uint32_t color);

/* Sprites RGB565 con transparencia 0xF81F. */
void pac_sprite(int x, int y, const uint16_t *pixels, int w, int h);
void pac_sprite_alpha(int x, int y, const uint16_t *pixels, int w, int h,
                      uint8_t alpha);

/* Marca la region modificada. SereOS invalida la ventana; Linux puede
 * ignorarlo (presenta el lienzo software completo). */
void pac_mark_dirty(int x, int y, int w, int h);

/* Vuelca el lienzo software a la pantalla. SereOS no hace nada (lo hace el
 * compositor); Linux hace SDL_RenderPresent. */
void pac_present(void);

/* ------------------------------------------------------------------ */
/* texto                                                               */
/* ------------------------------------------------------------------ */
int  pac_text_width(pac_text_style_t style, const char *text);
int  pac_text_height(pac_text_style_t style);
int  pac_text_ascent(pac_text_style_t style);
int  pac_text_line_gap(pac_text_style_t style);

void pac_text_draw(pac_text_style_t style, int x, int y,
                   const char *text, uint32_t color);
void pac_text_draw_alpha(pac_text_style_t style, int x, int y,
                         const char *text, uint32_t color, uint8_t alpha);
void pac_text_draw_center(pac_text_style_t style, int cx, int y,
                          const char *text, uint32_t color);
void pac_text_draw_right(pac_text_style_t style, int right_x, int y,
                         const char *text, uint32_t color);

/* ------------------------------------------------------------------ */
/* audio                                                               */
/* ------------------------------------------------------------------ */
void pac_audio_init(void);
int  pac_audio_available(void);
void pac_audio_play(int sfx);        /* pac_audio_sfx_t, una vez */
void pac_audio_loop(int sfx);        /* sirenas; PAC_SFX_NONE lo detiene */
void pac_audio_stop_loop(void);
void pac_audio_stop(void);           /* detiene todo */
void pac_audio_update(void);         /* avanza la maquina de sonido */

/* ------------------------------------------------------------------ */
/* input                                                               */
/* ------------------------------------------------------------------ */
/* Estado fisico de una tecla mantenida (para la fisica/menus). */
int  pac_input_key_down(pac_key_t key);

/* Estado del raton (posicion absoluta en coordenadas de ventana). */
int  pac_mouse_x(void);
int  pac_mouse_y(void);

#endif /* PACMAN_PLATFORM_H */
