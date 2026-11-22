/* apps/sysmonitor/sysmonitor.c - monitor del sistema de SereOS Desktop
 *
 * Rediseno con el sistema de diseno (theme.h/ui.h/text.h): cabecera con hora
 * y uptime, rejilla 2x2 de tarjetas, tarjeta de tareas cooperativas y tarjeta
 * de estado del kernel. Todos los valores son reales; si un subsistema no esta
 * disponible se muestra "no disponible" (nunca datos inventados).
 */
#include <stdint.h>
#include "app.h"
#include "window.h"
#include "theme.h"
#include "ui.h"
#include "text.h"
#include "graphics.h"
#include "page.h"
#include "kmalloc.h"
#include "timer.h"
#include "rtc.h"
#include "task.h"
#include "scheduler.h"
#include "input.h"
#include "fs.h"
#include "log.h"
#include "audio.h"
#include "string.h"
#include "sysmonitor.h"

#define SM_REFRESH_TICKS 50   /* 0.5 s a 100 Hz */

typedef struct {
	int      task_id;
	uint32_t last_refresh;
} sysmon_state_t;

/* ------------------------------------------------------------------ */
/* utilidades                                                          */
/* ------------------------------------------------------------------ */
static int sm_pct(uint32_t used, uint32_t total) {
	uint32_t u = used, t = total;

	if (t == 0) return 0;
	while (t > 0xFFFFu) { u >>= 8; t >>= 8; }
	if (t == 0) return 0;
	u = u * 100u / t;
	return (int)(u > 100u ? 100u : u);
}

static uint32_t sm_bar_color(int pct) {
	if (pct >= 85) return theme.red;
	if (pct >= 65) return theme.amber;
	return theme.accent;
}

static void sm_draw_fit(text_style_t style, int x, int y, int maxw,
                        const char *s, uint32_t color) {
	char buf[96];
	int len, lo, hi;

	if (!s || maxw <= 0) return;
	if (text_width(style, s) <= maxw) {
		text_draw(style, x, y, s, color);
		return;
	}
	len = (int)strlen(s);
	if (len > (int)sizeof(buf) - 4) len = (int)sizeof(buf) - 4;
	lo = 0;
	hi = len;
	while (lo < hi) {
		int mid = (lo + hi + 1) / 2;
		memcpy(buf, s, (size_t)mid);
		buf[mid] = '\0';
		strcat(buf, "...");
		if (text_width(style, buf) <= maxw) lo = mid;
		else hi = mid - 1;
	}
	memcpy(buf, s, (size_t)lo);
	buf[lo] = '\0';
	strcat(buf, "...");
	text_draw(style, x, y, buf, color);
}

static void sm_card_frame(int x, int y, int w, int h, const char *title) {
	ui_card(x, y, w, h);
	text_draw(TEXT_LABEL, x + SP_4, y + SP_3, title, theme.text_dim);
}

/* ------------------------------------------------------------------ */
/* tarjetas de la rejilla 2x2                                          */
/* ------------------------------------------------------------------ */
static void sm_draw_ram(int x, int y, int w, int h) {
	uint32_t total = page_total_bytes();
	uint32_t used = page_used_bytes();
	uint32_t freeb = (total > used) ? total - used : 0;
	int title_h = text_height(TEXT_LABEL);
	int head_h = text_height(TEXT_HEADLINE);
	int small_h = text_height(TEXT_SMALL);
	int content_h = head_h + SP_1 + small_h + SP_3 + BAR_HEIGHT;
	int area_y = y + SP_3 + title_h;
	int vy = area_y + (h - SP_3 - title_h - content_h) / 2;
	int by;
	char value[48], sub[80];
	if (vy < area_y + SP_1) vy = area_y + SP_1;
	by = vy + head_h + SP_1 + small_h + SP_3;
	if (by + BAR_HEIGHT > y + h - SP_2) by = y + h - SP_2 - BAR_HEIGHT;

	sm_card_frame(x, y, w, h, "Memoria RAM");
	if (total == 0) {
		text_draw(TEXT_HEADLINE, x + SP_4, vy, "no disponible", theme.text_dim);
		return;
	}
	snprintf(value, sizeof(value), "%u MB usados",
	         (unsigned)(used / (1024u * 1024u)));
	snprintf(sub, sizeof(sub), "Total %u MB  |  Libre %u MB",
	         (unsigned)(total / (1024u * 1024u)),
	         (unsigned)(freeb / (1024u * 1024u)));
	text_draw(TEXT_HEADLINE, x + SP_4, vy, value, theme.text);
	sm_draw_fit(TEXT_SMALL, x + SP_4, vy + head_h + SP_1,
	            w - 2 * SP_4, sub, theme.text_dim);
	if (by > vy)
		ui_progress_bar(x + SP_4, by, w - 2 * SP_4, BAR_HEIGHT,
		                sm_pct(used, total), sm_bar_color(sm_pct(used, total)));
}

static void sm_draw_heap(int x, int y, int w, int h) {
	uint32_t total = heap_total();
	uint32_t used = heap_used();
	uint32_t largest = heap_largest_free();
	int title_h = text_height(TEXT_LABEL);
	int head_h = text_height(TEXT_HEADLINE);
	int small_h = text_height(TEXT_SMALL);
	int content_h = head_h + SP_1 + small_h + SP_3 + BAR_HEIGHT;
	int area_y = y + SP_3 + title_h;
	int vy = area_y + (h - SP_3 - title_h - content_h) / 2;
	int by;
	char value[48], sub[80];
	if (vy < area_y + SP_1) vy = area_y + SP_1;
	by = vy + head_h + SP_1 + small_h + SP_3;
	if (by + BAR_HEIGHT > y + h - SP_2) by = y + h - SP_2 - BAR_HEIGHT;

	sm_card_frame(x, y, w, h, "Heap del kernel");
	if (total == 0) {
		text_draw(TEXT_HEADLINE, x + SP_4, vy, "no disponible", theme.text_dim);
		return;
	}
	snprintf(value, sizeof(value), "%u KB en uso",
	         (unsigned)(used / 1024u));
	snprintf(sub, sizeof(sub), "Arena %u KB  |  Mayor bloque %u KB",
	         (unsigned)(total / 1024u), (unsigned)(largest / 1024u));
	text_draw(TEXT_HEADLINE, x + SP_4, vy, value, theme.text);
	sm_draw_fit(TEXT_SMALL, x + SP_4, vy + head_h + SP_1,
	            w - 2 * SP_4, sub, theme.text_dim);
	if (by > vy)
		ui_progress_bar(x + SP_4, by, w - 2 * SP_4, BAR_HEIGHT,
		                sm_pct(used, total), sm_bar_color(sm_pct(used, total)));
}

static void sm_draw_uptime(int x, int y, int w, int h) {
	uint32_t sec = timer_uptime_ms() / 1000u;
	int title_h = text_height(TEXT_LABEL);
	int head_h = text_height(TEXT_HEADLINE);
	int small_h = text_height(TEXT_SMALL);
	int area_y = y + SP_3 + title_h;
	int vy = area_y + (h - SP_3 - title_h - head_h - SP_1 - small_h) / 2;
	int sub_y;
	char value[32], sub[80];

	if (vy < area_y + SP_1) vy = area_y + SP_1;
	sub_y = vy + head_h + SP_1;
	sm_card_frame(x, y, w, h, "Tiempo encendido");
	snprintf(value, sizeof(value), "%02u:%02u:%02u",
	         (unsigned)(sec / 3600u), (unsigned)((sec / 60u) % 60u),
	         (unsigned)(sec % 60u));
	snprintf(sub, sizeof(sub), "PIT %u Hz  |  %u ticks",
	         (unsigned)timer_hz(), (unsigned)timer_ticks());
	text_draw(TEXT_HEADLINE, x + SP_4, vy, value, theme.text);
	sm_draw_fit(TEXT_SMALL, x + SP_4, sub_y, w - 2 * SP_4, sub, theme.text_dim);
}

static void sm_draw_screen(int x, int y, int w, int h) {
	const fb_info_t *fi = fb_info();
	int title_h = text_height(TEXT_LABEL);
	int head_h = text_height(TEXT_HEADLINE);
	int small_h = text_height(TEXT_SMALL);
	int area_y = y + SP_3 + title_h;
	int vy = area_y + (h - SP_3 - title_h - head_h - SP_1 - small_h) / 2;
	int sub_y;
	char value[64], sub[80];

	if (vy < area_y + SP_1) vy = area_y + SP_1;
	sub_y = vy + head_h + SP_1;
	sm_card_frame(x, y, w, h, "Pantalla");
	if (!fb_available() || !fi) {
		text_draw(TEXT_HEADLINE, x + SP_4, vy, "no disponible", theme.text_dim);
		return;
	}
	snprintf(value, sizeof(value), "%ux%u @ %u bpp",
	         (unsigned)fi->width, (unsigned)fi->height, (unsigned)fi->bpp);
	snprintf(sub, sizeof(sub), "Pitch %u B  |  Backbuffer %s",
	         (unsigned)fi->pitch, fb_has_backbuffer() ? "activo" : "no disp.");
	sm_draw_fit(TEXT_HEADLINE, x + SP_4, vy, w - 2 * SP_4, value, theme.text);
	sm_draw_fit(TEXT_SMALL, x + SP_4, sub_y, w - 2 * SP_4, sub, theme.text_dim);
}

/* ------------------------------------------------------------------ */
/* tarjeta de tareas                                                   */
/* ------------------------------------------------------------------ */
static const char *sm_task_state(int state) {
	switch (state) {
	case TASK_READY:    return "lista";
	case TASK_SLEEPING: return "dormida";
	case TASK_DEAD:     return "terminada";
	default:            return "libre";
	}
}

static uint32_t sm_task_state_color(int state) {
	switch (state) {
	case TASK_READY:    return theme.green;
	case TASK_SLEEPING: return theme.amber;
	default:            return theme.text_faint;
	}
}

static void sm_draw_tasks(int x, int y, int w, int h) {
	task_t *list[TASK_MAX];
	int n = 0, i, slots, row_h, max_rows, shown, active;
	int row_y;
	char header[64];

	ui_card(x, y, w, h);
	active = task_active_count();
	slots = task_total_slots();
	text_draw(TEXT_LABEL, x + SP_4, y + SP_3, "Tareas cooperativas", theme.text_dim);
	snprintf(header, sizeof(header), "%d activas / %d slots", active, slots);
	text_draw_right(TEXT_CAPTION, x + w - SP_4, y + SP_3 + SP_1, header,
	                theme.text_faint);

	for (i = 1; i <= slots && i <= TASK_MAX; i++) {
		task_t *t = task_get(i);
		if (!t) continue;
		if (n < TASK_MAX) list[n++] = t;
	}

	row_h = text_height(TEXT_SMALL) + SP_1;
	row_y = y + SP_3 + text_height(TEXT_LABEL) + SP_2;
	max_rows = (y + h - SP_2 - row_y) / row_h;
	if (max_rows < 1) return;
	if (n == 0) {
		text_draw(TEXT_SMALL, x + SP_4, row_y, "Sin tareas cooperativas",
		          theme.text_dim);
		return;
	}
	shown = (n < max_rows) ? n : max_rows;
	for (i = 0; i < shown; i++) {
		int ry = row_y + i * row_h;
		int ty = ry + (row_h - text_height(TEXT_SMALL)) / 2;
		int name_x = x + SP_4 + 14;
		int name_w = w * 45 / 100;
		int state_x = name_x + name_w;
		char runs[24];

		ui_status_dot(x + SP_4, ty + (text_height(TEXT_SMALL) - STATUS_DOT) / 2,
		              STATUS_DOT, sm_task_state_color(list[i]->state));
		sm_draw_fit(TEXT_BODY, name_x,
		            ry + (row_h - text_height(TEXT_BODY)) / 2,
		            name_w - SP_2, list[i]->name, theme.text);
		sm_draw_fit(TEXT_SMALL, state_x, ty, w / 4,
		            sm_task_state(list[i]->state), theme.text_dim);
		snprintf(runs, sizeof(runs), "%u runs", (unsigned)list[i]->runs);
		text_draw_right(TEXT_MONO_SMALL, x + w - SP_4, ty, runs, theme.text_faint);
	}
	if (n > shown) {
		char more[32];
		snprintf(more, sizeof(more), "+%d mas", n - shown);
		text_draw_right(TEXT_CAPTION, x + w - SP_4, y + h - SP_2 - text_height(TEXT_CAPTION),
		                more, theme.text_faint);
	}
}

/* ------------------------------------------------------------------ */
/* tarjeta de estado del kernel                                        */
/* ------------------------------------------------------------------ */
static void sm_draw_kernel(int x, int y, int w, int h) {
	char v1[24], v2[24], v3[24], v4[24], v5[24], v6[24], v7[24];
	char v8[24], v9[24];
	int row_h, max_rows, i;
	struct sm_kv { const char *label; const char *value; uint32_t color; } kv[9];

	ui_card(x, y, w, h);
	text_draw(TEXT_LABEL, x + SP_4, y + SP_3, "Estado del kernel", theme.text_dim);

	snprintf(v1, sizeof(v1), "%s", paging_enabled() ? "activa" : "inactiva");
	snprintf(v2, sizeof(v2), "%s", mouse_present() ? "presente" : "no presente");
	snprintf(v3, sizeof(v3), "%d nodos", fs_node_count());
	snprintf(v4, sizeof(v4), "%d", klog_errors());
	snprintf(v5, sizeof(v5), "%u pasos", (unsigned)scheduler_steps());
	snprintf(v6, sizeof(v6), "%u", (unsigned)scheduler_activations());
	snprintf(v7, sizeof(v7), "#%d", scheduler_current_id());
	if (fb_available())
		snprintf(v8, sizeof(v8), "%ux%u", (unsigned)fb_width(), (unsigned)fb_height());
	else
		snprintf(v8, sizeof(v8), "no disponible");
	if (audio_available())
		snprintf(v9, sizeof(v9), "%s", audio_backend());
	else
		snprintf(v9, sizeof(v9), "no disponible");

	kv[0].label = "Paginacion";  kv[0].value = v1;
	kv[0].color = paging_enabled() ? theme.green : theme.red;
	kv[1].label = "Raton PS/2";  kv[1].value = v2;
	kv[1].color = mouse_present() ? theme.green : theme.amber;
	kv[2].label = "RAMFS";       kv[2].value = v3; kv[2].color = theme.text;
	kv[3].label = "Errores klog"; kv[3].value = v4;
	kv[3].color = klog_errors() == 0 ? theme.green : theme.amber;
	kv[4].label = "Scheduler";   kv[4].value = v5; kv[4].color = theme.text;
	kv[5].label = "Activaciones"; kv[5].value = v6; kv[5].color = theme.text;
	kv[6].label = "Tarea actual"; kv[6].value = v7; kv[6].color = theme.text;
	kv[7].label = "Pantalla"; kv[7].value = v8;
	kv[7].color = fb_available() ? theme.green : theme.amber;
	kv[8].label = "Audio"; kv[8].value = v9;
	kv[8].color = audio_available() ? theme.green : theme.amber;

	row_h = text_height(TEXT_SMALL) + SP_1;
	max_rows = (y + h - SP_2 - (y + SP_3 + text_height(TEXT_LABEL) + SP_2)) / row_h;
	for (i = 0; i < 9 && i < max_rows; i++) {
		int ry = y + SP_3 + text_height(TEXT_LABEL) + SP_2 + i * row_h;

		ui_kv_row_colored(x + SP_4, ry + (row_h - text_height(TEXT_SMALL)) / 2,
		                  w - 2 * SP_4, kv[i].label, kv[i].value, kv[i].color);
	}
}

/* ------------------------------------------------------------------ */
/* dibujo completo                                                     */
/* ------------------------------------------------------------------ */
static void sm_draw(struct window *w) {
	sysmon_state_t *st = (sysmon_state_t *)window_data(w);
	int cx, cy, cw, ch, pad, gap, header_h, grid_top, y;
	int card_w, card_h, bottom_y, bottom_h, avail;
	char timebuf[16], upbuf[32];

	if (!st) return;
	cx = window_content_x(w);
	cy = window_content_y(w);
	cw = window_content_w(w);
	ch = window_content_h(w);
	if (cw < 480 || ch < 300) return;

	pad = SP_4;
	gap = SP_3;
	ui_surface(cx, cy, cw, ch, 0, theme.surface, 0);

	header_h = text_height(TEXT_TITLE) + SP_3 * 2;
	y = cy + pad;
	text_draw(TEXT_TITLE, cx + pad, y + (header_h - text_height(TEXT_TITLE)) / 2,
	          "Monitor del sistema", theme.text);
	if (rtc_available()) {
		rtc_time_string(timebuf, (uint32_t)sizeof(timebuf));
		text_draw_right(TEXT_LABEL, cx + cw - pad, y, timebuf, theme.text);
	} else {
		text_draw_right(TEXT_LABEL, cx + cw - pad, y, "--:--:--", theme.text_dim);
	}
	{
		uint32_t sec = timer_uptime_ms() / 1000u;
		snprintf(upbuf, sizeof(upbuf), "uptime %02u:%02u:%02u",
		         (unsigned)(sec / 3600u), (unsigned)((sec / 60u) % 60u),
		         (unsigned)(sec % 60u));
		text_draw_right(TEXT_SMALL, cx + cw - pad,
		                y + text_height(TEXT_LABEL) + SP_1, upbuf, theme.text_dim);
	}
	ui_divider(cx + pad, y + header_h, cw - 2 * pad);

	grid_top = y + header_h + SP_1 + gap;
	avail = (cy + ch - pad) - grid_top;
	card_w = (cw - 2 * pad - gap) / 2;
	card_h = (avail - gap * 3) * 31 / 100;
	if (card_h < 96) card_h = 96;
	if (card_h > 190) card_h = 190;
	bottom_y = grid_top + 2 * card_h + gap;
	bottom_h = cy + ch - pad - bottom_y;
	if (bottom_h < SP_12) bottom_h = 0;

	sm_draw_ram(cx + pad, grid_top, card_w, card_h);
	sm_draw_heap(cx + pad + card_w + gap, grid_top, card_w, card_h);
	sm_draw_uptime(cx + pad, grid_top + card_h + gap, card_w, card_h);
	sm_draw_screen(cx + pad + card_w + gap, grid_top + card_h + gap, card_w, card_h);

	if (bottom_h > 0) {
		sm_draw_tasks(cx + pad, bottom_y, card_w, bottom_h);
		sm_draw_kernel(cx + pad + card_w + gap, bottom_y, card_w, bottom_h);
	}
}

/* ------------------------------------------------------------------ */
/* ciclo de vida                                                       */
/* ------------------------------------------------------------------ */
static void sm_step(void *arg) {
	struct window *w = (struct window *)arg;
	sysmon_state_t *st = (sysmon_state_t *)window_data(w);
	uint32_t now;

	if (!st) return;
	now = timer_ticks();
	if ((int32_t)(now - st->last_refresh) >= SM_REFRESH_TICKS) {
		st->last_refresh = now;
		window_invalidate(w);
	}
}

static void sm_open(struct window *w) {
	sysmon_state_t *st;
	static int audio_started = 0;

	if (!audio_started) {
		audio_init();          /* idempotente: backend real para la tarjeta */
		audio_started = 1;
	}
	st = (sysmon_state_t *)kzalloc(sizeof(sysmon_state_t));
	if (!st) return;
	st->task_id = -1;
	st->last_refresh = timer_ticks();
	window_set_data(w, st);
	st->task_id = task_create("monitor", sm_step, w);
	window_invalidate(w);
}

static void sm_close(struct window *w) {
	sysmon_state_t *st = (sysmon_state_t *)window_data(w);
	if (!st) return;
	if (st->task_id >= 0) task_kill(st->task_id);
	window_set_data(w, 0);
	kfree(st);
}

static void sm_event(struct window *w, const event_t *ev) {
	(void)w;
	(void)ev;
}

static app_t sysmonitor_app = {
	.id = "monitor",
	.name = "Monitor",
	.icon = "monitor",
	.default_width = 860,
	.default_height = 560,
	.init = 0,
	.open = sm_open,
	.close = sm_close,
	.draw = sm_draw,
	.event = sm_event,
	.update = 0,
};

app_t *app_sysmonitor(void) {
	return &sysmonitor_app;
}
