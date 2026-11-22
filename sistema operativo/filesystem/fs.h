/* filesystem/fs.h - sistema de archivos en RAM (RAMFS) de SereOS
 *
 * Arbol real de nodos con directorios y archivos, sin simulacion.
 * El explorador y la shell usan exactamente este subsistema.
 */
#ifndef SEREOS_FS_H
#define SEREOS_FS_H
#include <stdint.h>

#define FS_ROOT            0
#define FS_MAX_NODES       64
#define FS_NAME_MAX        28
#define FS_DATA_MAX        1024
#define FS_PATH_MAX        128

typedef struct {
	int      id;
	char     name[FS_NAME_MAX];
	uint8_t  is_dir;
	uint32_t size;
} fs_dirent_t;

void     fs_init(void);

/* operaciones sobre rutas (absolutas o relativas al cwd) */
int      fs_create(const char *path);
int      fs_mkdir(const char *path);
int      fs_delete(const char *path);
int      fs_exists(const char *path);
int      fs_lookup(const char *path);
int      fs_chdir(const char *path);
void     fs_getcwd(char *buf, uint32_t n);

/* descriptores */
int      fs_open(const char *path);
int      fs_close(int fd);
int      fs_read(int fd, void *buf, uint32_t n);
int      fs_write(int fd, const void *buf, uint32_t n);

/* listado de directorios */
int      fs_list(int dir_id, fs_dirent_t *out, int max);

/* utilidades */
int      fs_readfile(const char *path, void *buf, uint32_t n);
int      fs_writefile(const char *path, const void *buf, uint32_t n);
int      fs_is_dir(int id);
uint32_t fs_node_size(int id);
const char *fs_node_name(int id);
int      fs_parent(int id);
int      fs_node_count(void);
uint32_t fs_used_bytes(void);
uint32_t fs_capacity_bytes(void);
int      fs_cwd(void);

#endif
