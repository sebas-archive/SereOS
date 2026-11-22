/* shell/shell.h - interprete de comandos reutilizable (VGA y terminal grafica)
 *
 * La shell no escribe directamente en ningun dispositivo: emite texto por
 * un callback. Asi la terminal de texto (fallback VGA) y la terminal grafica
 * del escritorio comparten exactamente los mismos comandos.
 */
#ifndef SEREOS_SHELL_H
#define SEREOS_SHELL_H
#include <stdint.h>

#define SHELL_LINE_MAX  120
#define SHELL_HISTORY   16

typedef enum {
	SH_COLOR_DEFAULT = 0,
	SH_COLOR_OK,
	SH_COLOR_ERR,
	SH_COLOR_INFO,
	SH_COLOR_WARN,
	SH_COLOR_ACCENT,
	SH_COLOR_DIM
} shell_color_t;

typedef struct {
	void *ctx;
	void (*write)(void *ctx, const char *text);
	void (*set_color)(void *ctx, shell_color_t color);
} shell_out_t;

typedef struct {
	shell_out_t out;
	char        line[SHELL_LINE_MAX + 1];
	int         len, cursor;
	char        history[SHELL_HISTORY][SHELL_LINE_MAX + 1];
	int         hist_count;
	int         hist_pos;      /* -1 = linea actual */
	char        saved[SHELL_LINE_MAX + 1];
} shell_t;

void shell_attach(shell_t *sh, shell_out_t out);
void shell_banner(shell_t *sh);
void shell_prompt(shell_t *sh);
void shell_feed(shell_t *sh, char ch);                    /* edicion y ejecucion */
void shell_feed_key(shell_t *sh, uint16_t key, char ch);  /* flechas/historial/enter */
void shell_exec_line(shell_t *sh, const char *line);
uint32_t shell_uptime_sec(void);
void shell_run_text(void);   /* bucle de la consola VGA de respaldo */

#endif
