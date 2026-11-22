/* gui/app.h - descriptor de aplicacion del escritorio y registro de apps */
#ifndef SEREOS_APP_H
#define SEREOS_APP_H
#include "window.h"
#include "input.h"

struct window;

typedef struct app {
	const char *id;            /* identificador estable, p.ej. "terminal" */
	const char *name;          /* nombre visible */
	const char *icon;          /* id de icono dibujado por icons_draw() */
	int         default_width;
	int         default_height;

	void (*init)(void);                                  /* una vez al arrancar */
	void (*open)(struct window *w);                      /* al abrir ventana */
	void (*close)(struct window *w);                     /* al cerrar ventana */
	void (*draw)(struct window *w);                      /* contenido (clip ya fijado) */
	void (*event)(struct window *w, const event_t *ev);  /* eventos con foco */
	void (*update)(struct window *w, uint32_t dt_ms);    /* paso cooperativo */
} app_t;

void   app_register(app_t *app);
int    app_count(void);
app_t *app_get(int index);
app_t *app_find(const char *id);
const char *app_icon_id(app_t *app);

/* implementadas por las aplicaciones; apps_register() las registra */
app_t *app_terminal(void);
app_t *app_files(void);
app_t *app_sysmonitor(void);
app_t *app_about(void);
app_t *app_game(void);
void   apps_register(void);

#endif
