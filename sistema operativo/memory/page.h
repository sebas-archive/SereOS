/* memory/page.h - allocator de marcos fisicos de 4 KiB y paginacion (PSE) */
#ifndef SEREOS_PAGE_H
#define SEREOS_PAGE_H
#include <stdint.h>
#include <stddef.h>

#define PAGE_SIZE 4096

void     page_init(uint32_t mem_upper_kib);
void    *page_alloc(void);                 /* marco de 4 KiB fisico = virtual */
void     page_free(void *p);
uint32_t page_frame_size(void);
uint32_t page_total_frames(void);
uint32_t page_free_frames(void);
uint32_t page_used_frames(void);
uint32_t page_total_bytes(void);
uint32_t page_used_bytes(void);

/* paginacion: identidad con paginas de 4 MiB (PSE) para el kernel y el
 * framebuffer. Debe llamarse despues de page_init() y fb_init(). */
void     paging_init(void);
int      paging_enabled(void);
uint32_t paging_directory_phys(void);

extern uint8_t kernel_start[];
extern uint8_t kernel_end[];

#endif
