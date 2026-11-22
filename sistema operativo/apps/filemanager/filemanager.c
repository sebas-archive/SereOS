/* apps/filemanager/filemanager.c - explorador de archivos real del RAMFS
 *
 * Rediseno con el sistema de diseno de SereOS (theme.h/ui.h/text.h):
 * sidebar de 176 px, barra de ruta con chevrons, cabecera de columnas,
 * filas de 28 px, seleccion accent_soft, panel de vista previa y barra de
 * estado. Toda la navegacion y los datos siguen siendo reales (fs.h).
 */
#include <stdint.h>
#include "app.h"
#include "window.h"
#include "theme.h"
#include "ui.h"
#include "text.h"
#include "graphics.h"
#include "icons.h"
#include "fs.h"
#include "kmalloc.h"
#include "task.h"
#include "timer.h"
#include "input.h"
#include "string.h"
#include "filemanager.h"

#define FM_SIDEBAR_W      176   /* ancho fijo de la sidebar */
#define FM_SIDEBAR_ROW     30   /* filas de "Lugares" (dato del diseno) */
#define FM_SIDEBAR_ITEMS    3
#define FM_REFRESH_TICKS   50   /* refresco real periodico (0.5 s a 100 Hz) */
#define FM_DBLCLICK_TICKS  40   /* doble clic = 400 ms a 100 Hz */
#define FM_PREVIEW_H      (SP_10 + SP_10 + SP_8)  /* 112 px */

typedef struct {
	int cx, cy, cw, ch;
	int sidebar_w;
	int path_h;
	int refresh_x, refresh_y, refresh_size;
	int list_x, list_y, list_w, list_h, rows;
	int preview_y, preview_h;
	int status_y, status_h;
} fm_layout_t;

typedef struct {
	int         dir_id;                          /* nodo actual del RAMFS */
	fs_dirent_t entries[FS_MAX_NODES];           /* listado actual (real) */
	fs_dirent_t prev[FS_MAX_NODES];              /* listado anterior (cambios) */
	int         entry_count;
	int         prev_count;
	int         selected;                        /* indice seleccionado o -1 */
	int         hover;                           /* fila bajo el raton o -1 */
	int         sidebar_hover;                   /* item de sidebar o -1 */
	int         refresh_hover;                   /* boton refrescar bajo el raton */
	int         scroll;                          /* primera fila visible */
	int         rows;                            /* filas visibles (cache) */
	int         last_click_idx;
	uint32_t    last_click_tick;
	uint32_t    last_refresh_tick;
	int         last_nodes;
	uint32_t    last_used;
	char        preview[FS_DATA_MAX + 1];        /* contenido real del archivo */
	int         preview_len;
	int         preview_id;                      /* nodo previsualizado o -1 */
	int         task_id;
} files_state_t;

static const char *const fm_sidebar_path[FM_SIDEBAR_ITEMS] = { "/", "/home", "/docs" };
static const char *const fm_sidebar_label[FM_SIDEBAR_ITEMS] = { "Raiz", "/home", "/docs" };
static const char *const fm_sidebar_icon[FM_SIDEBAR_ITEMS] = { "storage", "home", "folder" };

static files_state_t *files_state(struct window *w) {
	return (files_state_t *)window_data(w);
}

/* ------------------------------------------------------------------ */
/* utilidades de texto (fuente proporcional + recorte por ancho)       */
/* ------------------------------------------------------------------ */
static void fm_draw_fit(text_style_t style, int x, int y, int maxw,
                        const char *s, uint32_t color) {
	char buf[FS_PATH_MAX + 8];
	int len, lo, hi;

	if (!s || maxw <= 0) return;
	if (text_width(style, s) <= maxw) {
		text_draw(style, x, y, s, color);
		return;
	}
	len = (int)strlen(s);
	if (len > FS_PATH_MAX) len = FS_PATH_MAX;
	lo = 0;
	hi = len;
	while (lo < hi) {
		int mid = (lo + hi + 1) / 2;
		int n = mid;
		if (n > len) n = len;
		memcpy(buf, s, (size_t)n);
		buf[n] = '\0';
		if (n + 3 <= (int)sizeof(buf) - 1) strcat(buf, "...");
		if (text_width(style, buf) <= maxw) lo = mid;
		else hi = mid - 1;
	}
	memcpy(buf, s, (size_t)lo);
	buf[lo] = '\0';
	if (lo + 3 <= (int)sizeof(buf) - 1) strcat(buf, "...");
	text_draw(style, x, y, buf, color);
}

static void fm_draw_fit_right(text_style_t style, int right_x, int y, int maxw,
                              const char *s, uint32_t color) {
	char buf[64];
	int len, lo, hi;

	if (!s || maxw <= 0) return;
	if (text_width(style, s) <= maxw) {
		text_draw_right(style, right_x, y, s, color);
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
	text_draw_right(style, right_x, y, buf, color);
}

/* ------------------------------------------------------------------ */
/* utilidades de ruta y listado                                        */
/* ------------------------------------------------------------------ */
static void fm_build_path(int id, char *out, int n) {
	char tmp[FS_PATH_MAX];
	int len = 0, cur = id, guard = 0;

	if (n <= 0) return;
	out[0] = '\0';
	if (id < 0) return;
	while (cur != FS_ROOT && cur >= 0 && guard++ < FS_MAX_NODES) {
		const char *name = fs_node_name(cur);
		int nl = name ? (int)strlen(name) : 0;
		if (len + nl + 1 >= (int)sizeof(tmp)) break;
		memmove(tmp + nl + 1, tmp, (size_t)len);
		tmp[0] = '/';
		if (name && nl > 0) memcpy(tmp + 1, name, (size_t)nl);
		len += nl + 1;
		cur = fs_parent(cur);
	}
	if (len == 0) tmp[len++] = '/';
	if (len >= n) len = n - 1;
	memcpy(out, tmp, (size_t)len);
	out[len] = '\0';
}

static int fm_entry_before(const fs_dirent_t *a, const fs_dirent_t *b) {
	if (a->is_dir != b->is_dir) return a->is_dir > b->is_dir;
	return strcasecmp(a->name, b->name) < 0;
}

static void fm_sort(fs_dirent_t *e, int n) {
	int i, j;
	for (i = 1; i < n; i++) {
		fs_dirent_t key = e[i];
		j = i - 1;
		while (j >= 0 && fm_entry_before(&key, &e[j])) {
			e[j + 1] = e[j];
			j--;
		}
		e[j + 1] = key;
	}
}

static int fm_find_id(const fs_dirent_t *e, int n, int id) {
	int i;
	for (i = 0; i < n; i++) if (e[i].id == id) return i;
	return -1;
}

static void fm_update_preview(files_state_t *st) {
	char path[FS_PATH_MAX];
	int n;

	st->preview_len = 0;
	st->preview[0] = '\0';
	st->preview_id = -1;
	if (st->selected < 0 || st->selected >= st->entry_count) return;
	if (st->entries[st->selected].is_dir) return;
	fm_build_path(st->entries[st->selected].id, path, (int)sizeof(path));
	n = fs_readfile(path, st->preview, FS_DATA_MAX);
	if (n < 0) n = 0;
	if (n > FS_DATA_MAX) n = FS_DATA_MAX;
	st->preview_len = n;
	st->preview[n] = '\0';
	st->preview_id = st->entries[st->selected].id;
}

/* Relee el directorio y detecta cambios reales (tambien los hechos por la
 * shell en paralelo). Devuelve 1 si algo cambio y hay que repintar. */
static int fm_load_dir(files_state_t *st, int dir_id, int keep_selection) {
	int n, i, sel_id = -1, changed = 0, nodes;
	uint32_t used;

	if (keep_selection && st->selected >= 0 && st->selected < st->entry_count)
		sel_id = st->entries[st->selected].id;

	n = fs_list(dir_id, st->entries, FS_MAX_NODES);
	if (n < 0) return 0;
	if (n > FS_MAX_NODES) n = FS_MAX_NODES;
	fm_sort(st->entries, n);

	if (n != st->prev_count ||
	    memcmp(st->entries, st->prev, (size_t)n * sizeof(fs_dirent_t)) != 0)
		changed = 1;
	memcpy(st->prev, st->entries, (size_t)n * sizeof(fs_dirent_t));
	st->prev_count = n;

	nodes = fs_node_count();
	used = fs_used_bytes();
	if (nodes != st->last_nodes || used != st->last_used) changed = 1;
	st->last_nodes = nodes;
	st->last_used = used;

	st->dir_id = dir_id;
	st->entry_count = n;
	if (sel_id >= 0) {
		i = fm_find_id(st->entries, n, sel_id);
		st->selected = (i >= 0) ? i : (n > 0 ? 0 : -1);
	} else {
		st->selected = (n > 0) ? 0 : -1;
	}
	st->hover = -1;
	st->sidebar_hover = -1;
	st->refresh_hover = 0;
	if (st->selected < 0) {
		st->scroll = 0;
	} else {
		if (st->selected < st->scroll) st->scroll = st->selected;
		if (st->scroll < 0) st->scroll = 0;
	}
	return changed;
}

static void fm_navigate(files_state_t *st, int dir_id) {
	if (dir_id < 0) return;
	if (dir_id != FS_ROOT && !fs_is_dir(dir_id)) return;
	st->scroll = 0;
	st->last_click_idx = -1;
	fm_load_dir(st, dir_id, 0);
	fm_update_preview(st);
}

static void fm_select_index(files_state_t *st, int idx) {
	int rows = st->rows > 0 ? st->rows : 8;
	int max_scroll;

	if (st->entry_count <= 0) { st->selected = -1; return; }
	if (idx < 0) idx = 0;
	if (idx >= st->entry_count) idx = st->entry_count - 1;
	if (idx != st->selected) {
		st->selected = idx;
		fm_update_preview(st);
	}
	if (st->selected < st->scroll) st->scroll = st->selected;
	if (st->selected >= st->scroll + rows) st->scroll = st->selected - rows + 1;
	max_scroll = st->entry_count - rows;
	if (max_scroll < 0) max_scroll = 0;
	if (st->scroll > max_scroll) st->scroll = max_scroll;
	if (st->scroll < 0) st->scroll = 0;
}

static void fm_activate(files_state_t *st) {
	if (st->selected < 0 || st->selected >= st->entry_count) return;
	if (st->entries[st->selected].is_dir)
		fm_navigate(st, st->entries[st->selected].id);
	else
		fm_update_preview(st);   /* Enter sobre archivo = previsualizar */
}

/* ------------------------------------------------------------------ */
/* geometria (misma para dibujo y para los hit tests)                  */
/* ------------------------------------------------------------------ */
static void fm_layout(struct window *w, fm_layout_t *out) {
	int colh = text_height(TEXT_CAPTION) + SP_3;
	int statush = text_height(TEXT_CAPTION) + SP_3;
	int pathh = CTRL_HEIGHT + SP_3;
	int sidebar = FM_SIDEBAR_W;
	int list_max, preview, list_h;

	out->cx = window_content_x(w);
	out->cy = window_content_y(w);
	out->cw = window_content_w(w);
	out->ch = window_content_h(w);
	if (out->cw < 640) sidebar = 148;      /* ventanas estrechas */
	out->sidebar_w = sidebar;
	out->path_h = pathh;
	out->refresh_size = CTRL_HEIGHT;
	out->refresh_x = out->cx + out->cw - SP_4 - CTRL_HEIGHT;
	out->refresh_y = out->cy + (pathh - CTRL_HEIGHT) / 2;
	out->list_x = out->cx + sidebar + 1;
	out->list_y = out->cy + pathh + colh;
	out->list_w = out->cw - sidebar - 1;
	out->status_y = out->cy + out->ch - statush;
	out->status_h = statush;

	list_max = out->status_y - out->list_y;
	/* con ventana maximizada el alto extra se reparte entre listado y preview */
	preview = FM_PREVIEW_H;
	if (out->ch >= 600) {
		preview = out->ch * 22 / 100;
		if (preview < FM_PREVIEW_H) preview = FM_PREVIEW_H;
		if (preview > 168) preview = 168;
	}
	if (preview > list_max - 3 * LIST_ROW_H) preview = list_max - 3 * LIST_ROW_H;
	if (preview < SP_10 + SP_8) preview = 0;
	list_h = list_max - preview;
	if (list_h < 0) list_h = 0;
	out->list_h = list_h;
	out->rows = list_h / LIST_ROW_H;
	if (out->rows < 1) out->rows = 1;
	out->preview_y = out->list_y + list_h;
	out->preview_h = preview;
}

static int fm_sidebar_top(const fm_layout_t *lay) {
	return lay->cy + SP_4 + text_height(TEXT_CAPTION) + SP_2;
}

static int fm_row_at(files_state_t *st, const fm_layout_t *lay,
                     int mx, int my, int *out_y) {
	int dy, idx;

	if (mx < lay->list_x || mx >= lay->list_x + lay->list_w) return -1;
	if (my < lay->list_y || my >= lay->list_y + lay->list_h) return -1;
	dy = my - lay->list_y;
	idx = st->scroll + dy / LIST_ROW_H;
	if (idx < 0 || idx >= st->entry_count) return -1;
	if (out_y) *out_y = lay->list_y + (dy / LIST_ROW_H) * LIST_ROW_H;
	return idx;
}

/* zona de 8 px del borde reservada por el WM para redimensionar */
#define FM_RESIZE_EDGE SP_2
static int fm_in_resize_edge(const fm_layout_t *lay, int mx, int my) {
	int lx = mx - lay->cx;
	int ly = my - lay->cy;

	if (lx < FM_RESIZE_EDGE || lx >= lay->cw - FM_RESIZE_EDGE) return 1;
	if (ly >= lay->ch - FM_RESIZE_EDGE) return 1;
	return 0;
}

static int fm_sidebar_at(const fm_layout_t *lay, int mx, int my) {
	int top = fm_sidebar_top(lay);
	int rel;

	if (mx < lay->cx || mx >= lay->cx + lay->sidebar_w) return -1;
	if (my < top) return -1;
	rel = (my - top) / FM_SIDEBAR_ROW;
	if (rel >= FM_SIDEBAR_ITEMS) return -1;
	return rel;
}

/* ------------------------------------------------------------------ */
/* dibujo                                                              */
/* ------------------------------------------------------------------ */
static void fm_draw_sidebar(files_state_t *st, const fm_layout_t *lay) {
	int i, top;

	ui_surface(lay->cx, lay->cy, lay->sidebar_w, lay->ch, 0, theme.surface_2, 0);
	ui_surface(lay->cx + lay->sidebar_w, lay->cy, 1, lay->ch, 0, theme.border, 0);
	text_draw(TEXT_CAPTION, lay->cx + SP_4, lay->cy + SP_4, "Lugares", theme.text_dim);

	top = fm_sidebar_top(lay);
	for (i = 0; i < FM_SIDEBAR_ITEMS; i++) {
		int iy = top + i * FM_SIDEBAR_ROW;
		int id = fs_lookup(fm_sidebar_path[i]);
		int active = (id >= 0 && id == st->dir_id);
		uint32_t col = active ? theme.text : theme.text_dim;
		int tx = lay->cx + SP_4 + 24;
		int ty = iy + (FM_SIDEBAR_ROW - text_height(TEXT_BODY)) / 2;

		if (active)
			gfx_fill_round_rect_alpha(lay->cx + SP_2, iy,
			                          lay->sidebar_w - 2 * SP_2,
			                          FM_SIDEBAR_ROW, RADIUS_SM,
			                          theme.accent, 56);
		else if (i == st->sidebar_hover)
			gfx_fill_round_rect_alpha(lay->cx + SP_2, iy,
			                          lay->sidebar_w - 2 * SP_2,
			                          FM_SIDEBAR_ROW, RADIUS_SM,
			                          theme.surface_3, 120);
		icons_draw_color(fm_sidebar_icon[i], lay->cx + SP_4 + 8,
		                 iy + FM_SIDEBAR_ROW / 2, 16,
		                 active ? theme.accent : theme.text_dim);
		text_draw(TEXT_BODY, tx, ty, fm_sidebar_label[i], col);
	}
}

static void fm_draw_breadcrumb(int x, int y, int maxw, const char *path) {
	const char *p = path;
	int cx = x;
	int chev_w = 12;

	if (!path || !path[0]) return;
	if (path[0] != '/') {
		text_draw(TEXT_SMALL, x, y, path, theme.text);
		return;
	}
	p = path + 1;
	if (!*p) {
		text_draw(TEXT_SMALL, x, y, "/", theme.text);
		return;
	}
	while (*p) {
		const char *s = p;
		int len = 0, w;
		char seg[FS_NAME_MAX + 1];

		while (p[len] && p[len] != '/') len++;
		if (len > FS_NAME_MAX) len = FS_NAME_MAX;
		memcpy(seg, s, (size_t)len);
		seg[len] = '\0';
		w = text_width(TEXT_SMALL, seg);

		if (cx + w > x + maxw) {   /* no cabe el resto: recorta */
			fm_draw_fit(TEXT_SMALL, cx, y, x + maxw - cx, seg, theme.text);
			return;
		}
		text_draw(TEXT_SMALL, cx, y, seg, theme.text);
		cx += w;
		p += len;
		if (*p == '/') p++;
		if (*p) {
			icons_draw_color("chevron_right", cx + SP_1 + chev_w / 2,
			                 y + text_height(TEXT_SMALL) / 2, chev_w,
			                 theme.text_faint);
			cx += chev_w + SP_2;
		}
	}
}

static void fm_draw_pathbar(files_state_t *st, const fm_layout_t *lay) {
	char path[FS_PATH_MAX];
	int px = lay->cx + lay->sidebar_w + SP_4;
	int icon_cx = px + 8;
	int text_x = px + 24;
	int text_y = lay->cy + (lay->path_h - text_height(TEXT_SMALL)) / 2;
	int maxw;

	ui_surface(lay->cx + lay->sidebar_w, lay->cy,
	           lay->cw - lay->sidebar_w, lay->path_h, 0, theme.surface_2, 0);
	fm_build_path(st->dir_id, path, (int)sizeof(path));
	icons_draw_color("storage", icon_cx, lay->cy + lay->path_h / 2, 16, theme.text_dim);
	maxw = lay->refresh_x - SP_4 - text_x;
	fm_draw_breadcrumb(text_x, text_y, maxw, path);

	/* boton de refresco (recarga real del listado) */
	if (st->refresh_hover)
		ui_surface(lay->refresh_x, lay->refresh_y, lay->refresh_size,
		           lay->refresh_size, CTRL_RADIUS, theme.surface_3, 0);
	icons_draw_color("refresh", lay->refresh_x + lay->refresh_size / 2,
	                 lay->refresh_y + lay->refresh_size / 2, 16,
	                 st->refresh_hover ? theme.text : theme.text_dim);
	ui_divider(lay->cx + lay->sidebar_w, lay->cy + lay->path_h - 1,
	           lay->cw - lay->sidebar_w);
}

static void fm_draw_colhead(const fm_layout_t *lay) {
	int y = lay->cy + lay->path_h;
	int type_right, size_right, name_x, label_y;

	name_x = lay->list_x + SP_4 + 24;
	type_right = lay->list_x + lay->list_w - SP_4 - 72;
	size_right = lay->list_x + lay->list_w - SP_4;
	label_y = y + (text_height(TEXT_CAPTION) + SP_3 - text_height(TEXT_CAPTION)) / 2;

	text_draw(TEXT_CAPTION, name_x, label_y, "Nombre", theme.text_dim);
	fm_draw_fit_right(TEXT_CAPTION, type_right, label_y, 90, "Tipo", theme.text_dim);
	fm_draw_fit_right(TEXT_CAPTION, size_right, label_y, 64, "Tamano", theme.text_dim);
	ui_divider(lay->cx + lay->sidebar_w, y + text_height(TEXT_CAPTION) + SP_3 - 1,
	           lay->cw - lay->sidebar_w);
}

static void fm_draw_list(files_state_t *st, const fm_layout_t *lay) {
	int i, max_scroll;
	int name_x = lay->list_x + SP_4 + 24;
	int type_right = lay->list_x + lay->list_w - SP_4 - 72;
	int size_right = lay->list_x + lay->list_w - SP_4;
	int name_maxw = type_right - SP_2 - name_x;

	st->rows = lay->rows > 0 ? lay->rows : 1;
	max_scroll = st->entry_count - st->rows;
	if (max_scroll < 0) max_scroll = 0;
	if (st->scroll > max_scroll) st->scroll = max_scroll;
	if (st->scroll < 0) st->scroll = 0;

	if (st->entry_count == 0) {
		int ly = lay->list_y + lay->list_h / 2 - text_height(TEXT_BODY);

		text_draw_center(TEXT_BODY, lay->list_x + lay->list_w / 2, ly,
		                 "Carpeta vacia", theme.text_dim);
		text_draw_center(TEXT_SMALL, lay->list_x + lay->list_w / 2,
		                 ly + text_height(TEXT_BODY) + SP_1,
		                 "Use la shell para crear contenido", theme.text_faint);
		return;
	}

	for (i = 0; i < st->rows; i++) {
		int idx = st->scroll + i;
		int ry;
		fs_dirent_t *e;
		int ty;
		char sizebuf[24];

		if (idx >= st->entry_count) break;
		ry = lay->list_y + i * LIST_ROW_H;
		e = &st->entries[idx];
		ty = ry + (LIST_ROW_H - text_height(TEXT_BODY)) / 2;

		if (idx == st->selected) {
			gfx_fill_rect_alpha(lay->list_x, ry, lay->list_w, LIST_ROW_H,
			                    theme.accent, 60);
			gfx_fill_rect(lay->list_x, ry, 2, LIST_ROW_H, theme.accent);
		} else if (idx == st->hover) {
			gfx_fill_rect_alpha(lay->list_x, ry, lay->list_w, LIST_ROW_H,
			                    theme.surface_3, 150);
		}

		icons_draw_color(e->is_dir ? "folder" : "file",
		                 lay->list_x + SP_4 + 8, ry + LIST_ROW_H / 2, 16,
		                 e->is_dir ? theme.cyan : theme.text_dim);
		fm_draw_fit(TEXT_BODY, name_x, ty, name_maxw, e->name, theme.text);
		fm_draw_fit_right(TEXT_SMALL, type_right, ty + SP_1, 90,
		                  e->is_dir ? "Carpeta" : "Archivo", theme.text_faint);
		if (!e->is_dir) {
			snprintf(sizebuf, sizeof(sizebuf), "%u B", (unsigned)e->size);
			fm_draw_fit_right(TEXT_SMALL, size_right, ty + SP_1, 64,
			                  sizebuf, theme.text_faint);
		}
	}

	if (st->entry_count > st->rows) {
		int track_h = st->rows * LIST_ROW_H;
		int thumb_h = track_h * st->rows / st->entry_count;
		int thumb_y = lay->list_y;
		int sx = lay->list_x + lay->list_w - 3;

		if (thumb_h < 18) thumb_h = 18;
		if (thumb_h > track_h) thumb_h = track_h;
		if (max_scroll > 0)
			thumb_y += (track_h - thumb_h) * st->scroll / max_scroll;
		ui_surface(sx, lay->list_y, 2, track_h, RADIUS_XS, theme.border, 0);
		gfx_fill_round_rect(sx, thumb_y, 2, thumb_h, 1, theme.text_faint);
	}
}

static void fm_draw_preview(files_state_t *st, const fm_layout_t *lay) {
	fs_dirent_t *sel = NULL;
	int px, py, pw, line_y, line_h, maxlines, char_w, cols, i, li;

	if (lay->preview_h <= 0) return;
	px = lay->list_x + SP_4;
	py = lay->preview_y;
	pw = lay->list_w - 2 * SP_4;

	ui_surface(lay->list_x, py, lay->list_w, lay->preview_h, 0, theme.surface_2, 0);
	ui_divider(lay->list_x, py, lay->list_w);

	if (st->selected >= 0 && st->selected < st->entry_count)
		sel = &st->entries[st->selected];

	if (!sel) {
		text_draw(TEXT_SMALL, px, py + SP_3, "Sin seleccion", theme.text_dim);
		return;
	}

	fm_draw_fit(TEXT_LABEL, px, py + SP_2,
	            lay->list_w - 2 * SP_4 - text_width(TEXT_CAPTION, "Archivo") - SP_4,
	            sel->name, theme.text);
	fm_draw_fit_right(TEXT_CAPTION, lay->list_x + lay->list_w - SP_4,
	                  py + SP_3 + SP_1, pw / 2,
	                  sel->is_dir ? "Carpeta" : "Archivo", theme.text_faint);

	line_y = py + SP_2 + text_height(TEXT_LABEL) + SP_2;
	line_h = text_height(TEXT_MONO_SMALL) + 2;
	maxlines = (py + lay->preview_h - SP_2 - line_y) / line_h;
	if (maxlines < 1) return;

	if (sel->is_dir) {
		text_draw(TEXT_SMALL, px, line_y, "Pulse Enter para abrir la carpeta",
		          theme.text_dim);
		return;
	}
	if (st->preview_id != sel->id) {
		text_draw(TEXT_SMALL, px, line_y, "(cargando...)", theme.text_dim);
		return;
	}
	if (st->preview_len == 0) {
		text_draw(TEXT_SMALL, px, line_y, "(archivo vacio)", theme.text_dim);
		return;
	}

	char_w = text_width(TEXT_MONO_SMALL, "M");
	if (char_w < 3) char_w = 6;
	cols = pw / char_w;
	if (cols < 8) cols = 8;

	i = 0;
	for (li = 0; li < maxlines && i < st->preview_len; li++) {
		char line[160];
		int n = 0, y = line_y + li * line_h;

		while (i < st->preview_len && st->preview[i] != '\n' && n < cols) {
			char c = st->preview[i++];
			if ((unsigned char)c < 32 || (unsigned char)c > 126) c = '.';
			line[n++] = c;
		}
		while (i < st->preview_len && st->preview[i] != '\n' && n < cols) i++;
		if (i < st->preview_len && st->preview[i] == '\n') i++;
		line[n] = '\0';
		text_draw(TEXT_MONO_SMALL, px, y, line, theme.text_dim);
	}
}

static void fm_draw_status(files_state_t *st, const fm_layout_t *lay) {
	static const char hint[] = "Enter abrir  |  Retroceso subir  |  r refrescar";
	char buf[128];
	int y;

	ui_surface(lay->cx, lay->status_y, lay->cw, lay->status_h, 0, theme.surface_2, 0);
	ui_divider(lay->cx, lay->status_y, lay->cw);
	y = lay->status_y + (lay->status_h - text_height(TEXT_CAPTION)) / 2;

	snprintf(buf, sizeof(buf), "%d nodos  |  %u B usados de %u KiB",
	         fs_node_count(), (unsigned)fs_used_bytes(),
	         (unsigned)(fs_capacity_bytes() / 1024u));
	text_draw(TEXT_CAPTION, lay->cx + SP_4, y, buf, theme.text_dim);
	if (text_width(TEXT_CAPTION, buf) + text_width(TEXT_CAPTION, hint) +
	    SP_4 * 2 + SP_4 <= lay->cw)
		text_draw_right(TEXT_CAPTION, lay->cx + lay->cw - SP_4, y, hint,
		                theme.text_faint);
	(void)st;
}

static void files_draw(struct window *w) {
	files_state_t *st = files_state(w);
	fm_layout_t lay;

	if (!st) return;
	fm_layout(w, &lay);
	ui_surface(lay.cx, lay.cy, lay.cw, lay.ch, 0, theme.surface, 0);
	if (lay.cw < 320 || lay.ch < 200) return;

	fm_draw_sidebar(st, &lay);
	fm_draw_pathbar(st, &lay);
	fm_draw_colhead(&lay);
	fm_draw_list(st, &lay);
	fm_draw_preview(st, &lay);
	fm_draw_status(st, &lay);
}

/* ------------------------------------------------------------------ */
/* ciclo de vida                                                       */
/* ------------------------------------------------------------------ */
static void files_step(void *arg) {
	struct window *w = (struct window *)arg;
	files_state_t *st = files_state(w);
	uint32_t now;

	if (!st) return;
	now = timer_ticks();
	if ((int32_t)(now - st->last_refresh_tick) >= FM_REFRESH_TICKS) {
		st->last_refresh_tick = now;
		if (fm_load_dir(st, st->dir_id, 1)) {
			fm_update_preview(st);
			window_invalidate(w);
		}
	}
}

static void files_open(struct window *w) {
	files_state_t *st;
	char cwd[FS_PATH_MAX];
	int id;

	st = (files_state_t *)kzalloc(sizeof(files_state_t));
	if (!st) return;
	st->task_id = -1;
	st->selected = -1;
	st->hover = -1;
	st->sidebar_hover = -1;
	st->refresh_hover = 0;
	st->preview_id = -1;
	st->last_click_idx = -1;
	st->last_click_tick = 0;
	st->last_refresh_tick = timer_ticks();
	st->last_nodes = -1;
	st->rows = 8;

	id = fs_cwd();
	if (id < 0) {
		fs_getcwd(cwd, (uint32_t)sizeof(cwd));
		id = fs_lookup(cwd);
	}
	if (id < 0) id = FS_ROOT;
	st->dir_id = id;
	window_set_data(w, st);

	fm_load_dir(st, st->dir_id, 0);
	fm_update_preview(st);

	st->task_id = task_create("files", files_step, w);
	window_invalidate(w);
}

static void files_close(struct window *w) {
	files_state_t *st = files_state(w);
	if (!st) return;
	if (st->task_id >= 0) task_kill(st->task_id);
	window_set_data(w, 0);
	kfree(st);
}

static void files_event(struct window *w, const event_t *ev) {
	files_state_t *st = files_state(w);
	fm_layout_t lay;
	int mx, my, idx;

	if (!st || !ev) return;
	fm_layout(w, &lay);
	mx = (int)ev->mouse_x;
	my = (int)ev->mouse_y;

	switch (ev->type) {
	case EVENT_KEY_DOWN: {
		int rows = st->rows > 0 ? st->rows : 8;

		switch (ev->key) {
		case KEY_UP:       fm_select_index(st, st->selected - 1); break;
		case KEY_DOWN:     fm_select_index(st, st->selected + 1); break;
		case KEY_PAGEUP:   fm_select_index(st, st->selected - rows); break;
		case KEY_PAGEDOWN: fm_select_index(st, st->selected + rows); break;
		case KEY_HOME:     fm_select_index(st, 0); break;
		case KEY_END:      fm_select_index(st, st->entry_count - 1); break;
		case KEY_ENTER:
			fm_activate(st);
			break;
		case KEY_BACKSPACE: {
			int parent = fs_parent(st->dir_id);
			if (parent >= 0) fm_navigate(st, parent);
			break;
		}
		case KEY_R:
			fm_load_dir(st, st->dir_id, 1);
			fm_update_preview(st);
			break;
		default:
			break;
		}
		window_invalidate(w);
		break;
	}
	case EVENT_MOUSE_MOVE: {
		int sh = fm_sidebar_at(&lay, mx, my);
		int rh = (mx >= lay.refresh_x && mx < lay.refresh_x + lay.refresh_size &&
		          my >= lay.refresh_y && my < lay.refresh_y + lay.refresh_size);

		idx = fm_row_at(st, &lay, mx, my, 0);
		if (idx != st->hover || sh != st->sidebar_hover || rh != st->refresh_hover) {
			st->hover = idx;
			st->sidebar_hover = sh;
			st->refresh_hover = rh;
			window_invalidate(w);
		}
		break;
	}
	case EVENT_MOUSE_WHEEL: {
		int max_scroll = lay.rows > 0 ? st->entry_count - lay.rows : 0;
		if (max_scroll < 0) max_scroll = 0;
		st->scroll -= ev->wheel;
		if (st->scroll > max_scroll) st->scroll = max_scroll;
		if (st->scroll < 0) st->scroll = 0;
		window_invalidate(w);
		break;
	}
	case EVENT_MOUSE_DOWN: {
		if (!ev->pressed || ev->button != MOUSE_BTN_LEFT) break;
		/* los 8 px del borde son del WM (resize); no los tratamos aqui */
		if (fm_in_resize_edge(&lay, mx, my)) break;
		/* sidebar */
		{
			int si = fm_sidebar_at(&lay, mx, my);

			if (si >= 0) {
				int id = fs_lookup(fm_sidebar_path[si]);
				if (id >= 0) fm_navigate(st, id);
				window_invalidate(w);
				break;
			}
		}
		/* boton de refresco */
		if (mx >= lay.refresh_x && mx < lay.refresh_x + lay.refresh_size &&
		    my >= lay.refresh_y && my < lay.refresh_y + lay.refresh_size) {
			fm_load_dir(st, st->dir_id, 1);
			fm_update_preview(st);
			window_invalidate(w);
			break;
		}
		/* listado: seleccion + doble clic */
		idx = fm_row_at(st, &lay, mx, my, 0);
		if (idx >= 0) {
			if (idx == st->last_click_idx &&
			    (uint32_t)(ev->tick - st->last_click_tick) <= FM_DBLCLICK_TICKS) {
				fm_select_index(st, idx);
				fm_activate(st);
				st->last_click_idx = -1;
			} else {
				fm_select_index(st, idx);
				st->last_click_idx = idx;
				st->last_click_tick = ev->tick;
			}
			window_invalidate(w);
		}
		break;
	}
	default:
		break;
	}
}

static app_t files_app = {
	.id = "files",
	.name = "Archivos",
	.icon = "files",
	.default_width = 900,
	.default_height = 560,
	.init = 0,
	.open = files_open,
	.close = files_close,
	.draw = files_draw,
	.event = files_event,
	.update = 0,
};

app_t *app_files(void) {
	return &files_app;
}
