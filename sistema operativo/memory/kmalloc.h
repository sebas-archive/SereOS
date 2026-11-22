/* memory/kmalloc.h - heap del kernel (first-fit con lista de bloques libres) */
#ifndef SEREOS_KMALLOC_H
#define SEREOS_KMALLOC_H
#include <stddef.h>
#include <stdint.h>

#define HEAP_ARENA_SIZE (8 * 1024 * 1024)

void     heap_init(void);
void    *kmalloc(size_t size);
void    *kzalloc(size_t size);
void     kfree(void *ptr);
void    *krealloc(void *ptr, size_t size);

uint32_t heap_total(void);
uint32_t heap_used(void);
uint32_t heap_free(void);
uint32_t heap_largest_free(void);
uint32_t heap_alloc_count(void);

#endif
