/* gui/app.c - registro de aplicaciones del escritorio SereOS
 *
 * El registro lo llena apps_register() (llamado desde kernel_main ANTES de
 * gui_init). El compositor, la barra superior y el dock localizan las apps
 * por identificador estable ("files", "terminal", "monitor", "game",
 * "about") y crean sus ventanas con window_create().
 */
#include "app.h"
#include "string.h"

#define APP_MAX 16

static app_t *apps[APP_MAX];
static int app_total;

void app_register(app_t *app) {
	int i;

	if (!app || !app->id || !app->id[0])
		return;
	/* evitar registros duplicados si alguien llama dos veces */
	for (i = 0; i < app_total; i++) {
		if (apps[i] && strcmp(apps[i]->id, app->id) == 0)
			return;
	}
	if (app_total >= APP_MAX)
		return;
	apps[app_total++] = app;
}

int app_count(void) {
	return app_total;
}

app_t *app_get(int index) {
	if (index < 0 || index >= app_total)
		return 0;
	return apps[index];
}

app_t *app_find(const char *id) {
	int i;

	if (!id)
		return 0;
	for (i = 0; i < app_total; i++) {
		if (apps[i] && apps[i]->id && strcmp(apps[i]->id, id) == 0)
			return apps[i];
	}
	return 0;
}

const char *app_icon_id(app_t *app) {
	if (!app)
		return "file";
	if (app->icon && app->icon[0])
		return app->icon;
	return app->id ? app->id : "file";
}
