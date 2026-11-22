/* apps/apps.c - registro de las aplicaciones del escritorio SereOS
 *
 * El orden de registro es el orden del dock y de las teclas F1..F5:
 *   F1 Archivos, F2 Terminal, F3 Monitor, F4 Juegos, F5 Acerca de.
 * Las aplicaciones se implementan en sus propios modulos; aqui solo se
 * registran sus descriptores en el registro del compositor (gui/app.c).
 */
#include "app.h"

void apps_register(void) {
	/* idempotente: kernel_main o gui_init pueden intentar registrarlas */
	static int registered = 0;
	if (registered) return;
	registered = 1;
	app_register(app_files());
	app_register(app_terminal());
	app_register(app_sysmonitor());
	app_register(app_game());
	app_register(app_about());
}
