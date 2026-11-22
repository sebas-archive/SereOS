/* filesystem/fs.c - RAMFS de SereOS: arbol real de nodos en memoria
 *
 * Cada nodo es un directorio o un archivo con su nombre, padre, tamano y un
 * buffer de datos de FS_DATA_MAX bytes. Los identificadores son indices en
 * una tabla estatica (FS_MAX_NODES) y el nodo 0 es siempre la raiz "/".
 *
 * Caracteristicas:
 *  - Rutas absolutas ("/home/record.txt") y relativas al cwd ("docs", "..").
 *  - "." y ".." resueltos de verdad; nunca se sale de la raiz.
 *  - Descriptores con offset para lecturas/escrituras secuenciales.
 *  - fs_list() entrega el contenido de un directorio al explorador/shell.
 *  - Semilla real creada en fs_init(): /, /home, /docs, /readme.txt y
 *    /home/record.txt con contenido util (no hay datos inventados en runtime).
 *
 * Los datos viven en .bss (no depende del heap) porque fs_init() se llama
 * antes de que las apps empiecen a reservar memoria.
 */
#include "fs.h"
#include "string.h"

#define FS_MAX_FDS 16

typedef struct {
	int      id;
	char     name[FS_NAME_MAX];
	int      parent;     /* -1 para la raiz */
	int      is_dir;
	uint32_t size;       /* bytes validos en data */
	uint8_t  data[FS_DATA_MAX];
} fs_node_internal_t;

typedef struct {
	int      used;
	int      node;
	uint32_t offset;
} fs_fd_t;

static fs_node_internal_t nodes[FS_MAX_NODES];
static fs_fd_t fds[FS_MAX_FDS];
static int cwd;

/* ======================================================================== */
/* utilidades internas                                                      */
/* ======================================================================== */
static fs_node_internal_t *node(int id) {
	if (id < 0 || id >= FS_MAX_NODES) return 0;
	if (!nodes[id].id) return 0;      /* id == 0 significa "ranura libre" */
	return &nodes[id];
}

static int find_child(int parent, const char *name) {
	int i;
	if (!node(parent) || !nodes[parent].is_dir) return -1;
	for (i = 1; i < FS_MAX_NODES; i++) {
		if (!nodes[i].id) continue;
		if (nodes[i].parent != parent) continue;
		if (strcmp(nodes[i].name, name) == 0) return i;
	}
	return -1;
}

static int alloc_node(const char *name, int parent, int is_dir) {
	int i;
	for (i = 1; i < FS_MAX_NODES; i++) {
		if (nodes[i].id) continue;
		nodes[i].id = i + 1;            /* 0 reservado para "libre" */
		memset(nodes[i].name, 0, FS_NAME_MAX);
		strncpy(nodes[i].name, name, FS_NAME_MAX - 1);
		nodes[i].name[FS_NAME_MAX - 1] = 0;
		nodes[i].parent = parent;
		nodes[i].is_dir = is_dir;
		nodes[i].size = 0;
		memset(nodes[i].data, 0, FS_DATA_MAX);
		return i;
	}
	return -1;
}

static void release_node(int id) {
	int i;
	if (!node(id) || id == FS_ROOT) return;
	nodes[id].id = 0;
	nodes[id].name[0] = 0;
	nodes[id].parent = -1;
	nodes[id].is_dir = 0;
	nodes[id].size = 0;
	/* cerrar descriptores que apuntaban al nodo borrado */
	for (i = 0; i < FS_MAX_FDS; i++)
		if (fds[i].used && fds[i].node == id) fds[i].used = 0;
}

/* resuelve una ruta completa. Devuelve id de nodo o -1. */
static int resolve(const char *path) {
	int cur;
	const char *p;

	if (!path) return -1;
	if (!path[0]) return cwd;
	cur = (path[0] == '/') ? FS_ROOT : cwd;
	p = path;

	while (*p) {
		char comp[FS_NAME_MAX];
		size_t len = 0;

		while (*p == '/') p++;
		if (!*p) break;
		while (p[len] && p[len] != '/') len++;
		if (len == 0 || len >= FS_NAME_MAX) return -1;
		memcpy(comp, p, len);
		comp[len] = 0;
		p += len;

		if (strcmp(comp, ".") == 0) continue;
		if (strcmp(comp, "..") == 0) {
			if (nodes[cur].parent >= 0) cur = nodes[cur].parent;
			continue;
		}
		if (!node(cur) || !nodes[cur].is_dir) return -1;
		cur = find_child(cur, comp);
		if (cur < 0) return -1;
	}
	return cur;
}

/* resuelve el directorio padre y el nombre final de una ruta.
 * Devuelve id del padre y copia el nombre en leaf; -1 si no es valida. */
static int resolve_parent(const char *path, char *leaf, size_t leaf_n) {
	char buf[FS_PATH_MAX];
	size_t plen;
	char *slash;
	const char *name;
	int parent;

	if (!path || !path[0] || leaf_n == 0) return -1;
	plen = strlen(path);
	if (plen >= FS_PATH_MAX) return -1;
	strcpy(buf, path);

	/* quitar barras finales, salvo que la ruta sea "/" */
	while (plen > 1 && buf[plen - 1] == '/') buf[--plen] = 0;
	slash = strrchr(buf, '/');
	if (!slash) {
		name = buf;
		parent = cwd;
	} else if (slash == buf) {
		name = slash + 1;
		parent = FS_ROOT;
	} else {
		*slash = 0;
		name = slash + 1;
		parent = resolve(buf);
	}

	if (parent < 0 || !node(parent) || !nodes[parent].is_dir) return -1;
	if (!name[0] || strlen(name) >= FS_NAME_MAX) return -1;
	if (strcmp(name, ".") == 0 || strcmp(name, "..") == 0) return -1;
	strncpy(leaf, name, leaf_n - 1);
	leaf[leaf_n - 1] = 0;
	return parent;
}

/* crea un archivo o directorio en la ruta indicada; devuelve id o -1 */
static int create_entry(const char *path, int is_dir) {
	char leaf[FS_NAME_MAX];
	int parent;

	parent = resolve_parent(path, leaf, sizeof(leaf));
	if (parent < 0) return -1;
	if (find_child(parent, leaf) >= 0) return -1;      /* ya existe */
	return alloc_node(leaf, parent, is_dir);
}

/* ======================================================================== */
/* inicializacion y semilla                                                 */
/* ======================================================================== */
static void seed_file(const char *path, const char *content) {
	int id = create_entry(path, 0);
	if (id < 0) return;
	nodes[id].size = (uint32_t)strlen(content);
	if (nodes[id].size > FS_DATA_MAX) nodes[id].size = FS_DATA_MAX;
	memcpy(nodes[id].data, content, nodes[id].size);
}

void fs_init(void) {
	memset(nodes, 0, sizeof(nodes));
	memset(fds, 0, sizeof(fds));
	cwd = FS_ROOT;

	/* raiz "/" */
	nodes[FS_ROOT].id = FS_ROOT + 1;    /* marca "en uso"; root se maneja aparte */
	nodes[FS_ROOT].name[0] = '/';
	nodes[FS_ROOT].name[1] = 0;
	nodes[FS_ROOT].parent = -1;
	nodes[FS_ROOT].is_dir = 1;
	nodes[FS_ROOT].size = 0;

	/* arbol inicial real */
	create_entry("/home", 1);
	create_entry("/docs", 1);
	seed_file("/readme.txt",
		"Bienvenido a SereOS 1.0 \"Desktop\".\n"
		"\n"
		"SereOS es un sistema operativo propio para i686 escrito desde cero\n"
		"en C y NASM, sin libc del host. Arranca con GRUB 2 (Multiboot 1) y\n"
		"su kernel monolitico incluye:\n"
		"  - paginacion por identidad con paginas PSE de 4 MiB\n"
		"  - allocator de marcos fisicos y heap first-fit\n"
		"  - planificador cooperativo round-robin\n"
		"  - RAMFS con arbol de nodos real y este explorador\n"
		"  - escritorio grafico nativo con ventanas, dock y aplicaciones\n"
		"  - terminal compartida entre la shell VGA y la app Terminal\n"
		"\n"
		"Proyecto final de Sistemas Operativos - UMB 2026\n"
		"SereOS es un sistema original, no una aplicacion ni una simulacion.\n");
	seed_file("/home/record.txt", "0");

}

/* ======================================================================== */
/* operaciones de rutas                                                     */
/* ======================================================================== */
int fs_create(const char *path) { return create_entry(path, 0); }
int fs_mkdir(const char *path)  { return create_entry(path, 1); }

int fs_delete(const char *path) {
	int id = resolve(path);
	if (id <= FS_ROOT) return -1;
	if (nodes[id].is_dir) {
		int i;
		for (i = 1; i < FS_MAX_NODES; i++)
			if (nodes[i].id && nodes[i].parent == id) return -1;   /* no vacio */
	}
	if (cwd == id) cwd = nodes[id].parent >= 0 ? nodes[id].parent : FS_ROOT;
	release_node(id);
	return 0;
}

int fs_exists(const char *path) { return resolve(path) >= 0 ? 1 : 0; }
int fs_lookup(const char *path) { return resolve(path); }

int fs_chdir(const char *path) {
	int id = resolve(path);
	if (id < 0 || !nodes[id].is_dir) return -1;
	cwd = id;
	return 0;
}

void fs_getcwd(char *buf, uint32_t n) {
	int stack[FS_MAX_NODES];
	int depth = 0, id = cwd;
	uint32_t pos = 0;

	if (!buf || n == 0) return;
	buf[0] = 0;
	if (n == 1) return;
	if (!node(cwd) || cwd == FS_ROOT) {
		strncpy(buf, "/", n - 1);
		buf[n - 1] = 0;
		return;
	}

	/* apilar los nodos desde el cwd hasta (sin incluir) la raiz */
	while (id > FS_ROOT && depth < FS_MAX_NODES) {
		stack[depth++] = id;
		id = nodes[id].parent;
		if (id < 0) break;
	}
	for (int k = depth - 1; k >= 0; k--) {
		const char *name = nodes[stack[k]].name;
		size_t len = strlen(name);
		if (pos + len + 2 > n) break;      /* no cabe: se trunca */
		buf[pos++] = '/';
		memcpy(buf + pos, name, len);
		pos += (uint32_t)len;
	}
	buf[pos] = 0;
}

/* ======================================================================== */
/* descriptores                                                             */
/* ======================================================================== */
int fs_open(const char *path) {
	int id = resolve(path);
	int i;

	if (id < 0 || !node(id) || nodes[id].is_dir) return -1;
	for (i = 0; i < FS_MAX_FDS; i++) {
		if (fds[i].used) continue;
		fds[i].used = 1;
		fds[i].node = id;
		fds[i].offset = 0;
		return i;
	}
	return -1;   /* tabla de descriptores llena */
}

int fs_close(int fd) {
	if (fd < 0 || fd >= FS_MAX_FDS || !fds[fd].used) return -1;
	fds[fd].used = 0;
	fds[fd].node = -1;
	fds[fd].offset = 0;
	return 0;
}

int fs_read(int fd, void *buf, uint32_t n) {
	fs_node_internal_t *nd;
	uint32_t avail, cnt;

	if (fd < 0 || fd >= FS_MAX_FDS || !fds[fd].used || !buf) return -1;
	nd = node(fds[fd].node);
	if (!nd) return -1;
	if (fds[fd].offset >= nd->size) return 0;
	avail = nd->size - fds[fd].offset;
	cnt = (n < avail) ? n : avail;
	memcpy(buf, nd->data + fds[fd].offset, cnt);
	fds[fd].offset += cnt;
	return (int)cnt;
}

int fs_write(int fd, const void *buf, uint32_t n) {
	fs_node_internal_t *nd;
	uint32_t space, cnt;

	if (fd < 0 || fd >= FS_MAX_FDS || !fds[fd].used || !buf) return -1;
	nd = node(fds[fd].node);
	if (!nd || nd->is_dir) return -1;
	if (fds[fd].offset >= FS_DATA_MAX) return 0;
	space = FS_DATA_MAX - fds[fd].offset;
	cnt = (n < space) ? n : space;
	/* si se escribe mas alla del final, rellenar el hueco con ceros */
	if (fds[fd].offset > nd->size)
		memset(nd->data + nd->size, 0, fds[fd].offset - nd->size);
	memcpy(nd->data + fds[fd].offset, buf, cnt);
	fds[fd].offset += cnt;
	if (fds[fd].offset > nd->size) nd->size = fds[fd].offset;
	return (int)cnt;
}

/* ======================================================================== */
/* listado                                                                  */
/* ======================================================================== */
int fs_list(int dir_id, fs_dirent_t *out, int max) {
	int i, count = 0;
	if (dir_id < 0) dir_id = cwd;
	if (!node(dir_id) || !nodes[dir_id].is_dir) return -1;
	if (!out || max <= 0) return 0;

	for (i = 1; i < FS_MAX_NODES && count < max; i++) {
		if (!nodes[i].id || nodes[i].parent != dir_id) continue;
		out[count].id = i;
		memset(out[count].name, 0, FS_NAME_MAX);
		strncpy(out[count].name, nodes[i].name, FS_NAME_MAX - 1);
		out[count].is_dir = (uint8_t)(nodes[i].is_dir ? 1 : 0);
		out[count].size = nodes[i].size;
		count++;
	}
	return count;
}

/* ======================================================================== */
/* utilidades                                                               */
/* ======================================================================== */
int fs_readfile(const char *path, void *buf, uint32_t n) {
	int id = resolve(path);
	uint32_t cnt;

	if (id < 0 || !node(id) || nodes[id].is_dir || !buf) return -1;
	cnt = (n < nodes[id].size) ? n : nodes[id].size;
	if (cnt) memcpy(buf, nodes[id].data, cnt);
	if (cnt < n) ((char *)buf)[cnt] = 0;   /* terminador si hay espacio */
	return (int)cnt;
}

int fs_writefile(const char *path, const void *buf, uint32_t n) {
	int id = resolve(path);
	uint32_t cnt;

	if (id < 0) {
		id = fs_create(path);              /* crear si no existe */
		if (id < 0) return -1;
	} else if (nodes[id].is_dir) {
		return -1;
	}
	if (!buf) return -1;
	cnt = (n < FS_DATA_MAX) ? n : FS_DATA_MAX;
	if (cnt) memcpy(nodes[id].data, buf, cnt);
	nodes[id].size = cnt;
	return (int)cnt;
}

int fs_is_dir(int id) {
	fs_node_internal_t *nd = node(id);
	return nd ? nd->is_dir : 0;
}

uint32_t fs_node_size(int id) {
	fs_node_internal_t *nd = node(id);
	return nd ? nd->size : 0;
}

const char *fs_node_name(int id) {
	fs_node_internal_t *nd = node(id);
	return nd ? nd->name : "";
}

int fs_parent(int id) {
	fs_node_internal_t *nd = node(id);
	return nd ? nd->parent : -1;
}

int fs_node_count(void) {
	int i, n = 0;
	for (i = 0; i < FS_MAX_NODES; i++)
		if (nodes[i].id) n++;
	return n;
}

uint32_t fs_used_bytes(void) {
	int i;
	uint32_t total = 0;
	for (i = 0; i < FS_MAX_NODES; i++)
		if (nodes[i].id && !nodes[i].is_dir) total += nodes[i].size;
	return total;
}

uint32_t fs_capacity_bytes(void) { return (uint32_t)FS_MAX_NODES * FS_DATA_MAX; }

int fs_cwd(void) { return cwd; }
