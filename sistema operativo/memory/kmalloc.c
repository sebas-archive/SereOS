/* memory/kmalloc.c - heap del kernel: first-fit sobre un arena estatico
 *
 * Estrategia:
 *  - Un arena estatico de HEAP_ARENA_SIZE bytes (.bss, cero gracias a GRUB)
 *    se divide en bloques enlazados doblemente.
 *  - Cada bloque lleva cabecera de 24 bytes (multiplo de 8) con tamano total
 *    del bloque, bandera de libre, magic y punteros next/prev.
 *  - kmalloc recorre la lista desde el principio (first-fit) y divide el
 *    bloque si el sobrante alcanza para otro bloque util (cabecera + 8).
 *  - kfree marca el bloque libre y fusiona con el vecino siguiente y el
 *    anterior para evitar fragmentacion externa.
 *  - El payload queda alineado a 8 bytes (sizeof(block_t) = 24).
 *
 * No se usa la libc del host: solo libc/string.h propia.
 * El heap solo se toca desde contexto cooperativo (bucle del escritorio y
 * pasos de tarea); no hay asignaciones desde ISRs, asi que no requiere
 * bloqueos explicitos.
 */
#include "kmalloc.h"
#include "string.h"

#define BLOCK_MAGIC 0x53484541u   /* "SHEA" */
#define ALIGN8(x)   (((x) + 7u) & ~7u)
#define MIN_PAYLOAD 8u
#define HEADER_SIZE ((uint32_t)sizeof(block_t))
#define MIN_BLOCK   (HEADER_SIZE + MIN_PAYLOAD)

typedef struct block {
	uint32_t      size;     /* tamano total del bloque: cabecera + payload */
	uint32_t      free;     /* 1 = libre, 0 = en uso */
	uint32_t      magic;    /* BLOCK_MAGIC */
	uint32_t      pad;      /* relleno para que la cabecera mida 24 bytes */
	struct block *next;
	struct block *prev;
} block_t;

static uint8_t  heap_arena[HEAP_ARENA_SIZE] __attribute__((aligned(16)));
static block_t *heap_head;
static int      heap_ready;
static uint32_t allocated_payload;  /* bytes de payload vivos */
static uint32_t allocated_blocks;   /* bloques vivos (heap_alloc_count) */

/* division de un bloque libre b en dos: b conserva `want` bytes y el resto
 * se convierte en un bloque libre encadenado justo despues. */
static void split_block(block_t *b, uint32_t want) {
	block_t *rest;

	if (b->size < want + MIN_BLOCK) return;
	rest = (block_t *)((uint8_t *)b + want);
	rest->size = b->size - want;
	rest->free = 1;
	rest->magic = BLOCK_MAGIC;
	rest->pad = 0;
	rest->next = b->next;
	rest->prev = b;
	if (b->next) b->next->prev = rest;
	b->next = rest;
	b->size = want;
}

/* fusiona b con su vecino siguiente si ambos estan libres y son contiguos */
static void merge_next(block_t *b) {
	block_t *n = b->next;
	if (!n || !n->free || !b->free) return;
	if ((uint8_t *)b + b->size != (uint8_t *)n) return;
	b->size += n->size;
	b->next = n->next;
	if (n->next) n->next->prev = b;
	n->magic = 0;   /* inutilizado */
}

void heap_init(void) {
	memset(heap_arena, 0, sizeof(heap_arena));
	heap_head = (block_t *)heap_arena;
	heap_head->size = HEAP_ARENA_SIZE;
	heap_head->free = 1;
	heap_head->magic = BLOCK_MAGIC;
	heap_head->pad = 0;
	heap_head->next = 0;
	heap_head->prev = 0;
	allocated_payload = 0;
	allocated_blocks = 0;
	heap_ready = 1;
}

uint32_t heap_total(void) { return HEAP_ARENA_SIZE; }

uint32_t heap_used(void) { return allocated_payload; }

uint32_t heap_free(void) {
	/* espacio realmente asignable: payload de todos los bloques libres */
	uint32_t total = 0;
	block_t *b;

	if (!heap_ready) return 0;
	for (b = heap_head; b; b = b->next) {
		if (b->free)
			total += b->size - HEADER_SIZE;
	}
	return total;
}

uint32_t heap_largest_free(void) {
	uint32_t best = 0;
	block_t *b;

	if (!heap_ready) return 0;
	for (b = heap_head; b; b = b->next) {
		if (b->free) {
			uint32_t payload = b->size - HEADER_SIZE;
			if (payload > best) best = payload;
		}
	}
	return best;
}

uint32_t heap_alloc_count(void) { return allocated_blocks; }

void *kmalloc(size_t size) {
	uint32_t want;
	block_t *b;

	if (!heap_ready) heap_init();
	if (size == 0) return 0;
	want = HEADER_SIZE + ALIGN8((uint32_t)size);
	if (want < MIN_BLOCK) want = MIN_BLOCK;

	for (b = heap_head; b; b = b->next) {
		if (b->free && b->size >= want) {
			split_block(b, want);
			b->free = 0;
			allocated_payload += b->size - HEADER_SIZE;
			allocated_blocks++;
			return (void *)((uint8_t *)b + HEADER_SIZE);
		}
	}
	return 0;   /* sin memoria contigua suficiente */
}

void *kzalloc(size_t size) {
	void *p = kmalloc(size);
	if (p) memset(p, 0, size);
	return p;
}

void kfree(void *ptr) {
	block_t *b;

	if (!ptr || !heap_ready) return;
	if ((uint8_t *)ptr < heap_arena ||
	    (uint8_t *)ptr >= heap_arena + HEAP_ARENA_SIZE) return;
	b = (block_t *)((uint8_t *)ptr - HEADER_SIZE);
	if (b->magic != BLOCK_MAGIC || b->free) return;   /* puntero invalido o doble free */

	b->free = 1;
	allocated_payload -= b->size - HEADER_SIZE;
	if (allocated_blocks) allocated_blocks--;
	merge_next(b);                 /* fusiona con el siguiente si procede */
	if (b->prev && b->prev->free)  /* y con el anterior */
		merge_next(b->prev);
}

void *krealloc(void *ptr, size_t size) {
	block_t *b;
	uint32_t want;
	void *newp;
	size_t old_payload, copy;

	if (!ptr) return kmalloc(size);
	if (size == 0) { kfree(ptr); return 0; }
	if (!heap_ready) return 0;
	if ((uint8_t *)ptr < heap_arena ||
	    (uint8_t *)ptr >= heap_arena + HEAP_ARENA_SIZE) return 0;

	b = (block_t *)((uint8_t *)ptr - HEADER_SIZE);
	if (b->magic != BLOCK_MAGIC || b->free) return 0;

	old_payload = b->size - HEADER_SIZE;
	if (old_payload >= (size_t)ALIGN8((uint32_t)size)) {
		/* el bloque ya es suficientemente grande: encoger y dividir */
		uint32_t new_total = HEADER_SIZE + ALIGN8((uint32_t)size);
		if (b->size >= new_total + MIN_BLOCK) {
			split_block(b, new_total);
			allocated_payload -= old_payload;
			allocated_payload += b->size - HEADER_SIZE;
			if (b->next && b->next->free) merge_next(b->next);
		}
		return ptr;
	}

	/* intentar crecer en el sitio absorbiendo el bloque siguiente libre */
	want = HEADER_SIZE + ALIGN8((uint32_t)size);
	if (b->next && b->next->free &&
	    (uint8_t *)b + b->size == (uint8_t *)b->next &&
	    b->size + b->next->size >= want) {
		block_t *n = b->next;
		b->size += n->size;
		b->next = n->next;
		if (n->next) n->next->prev = b;
		n->magic = 0;
		split_block(b, want);
		if (b->next && b->next->free) merge_next(b->next);
		allocated_payload -= old_payload;
		allocated_payload += b->size - HEADER_SIZE;
		return ptr;
	}

	/* reasignar y copiar el minimo de los dos tamanos */
	newp = kmalloc(size);
	if (!newp) return 0;
	copy = (old_payload < size) ? old_payload : size;
	memcpy(newp, ptr, copy);
	kfree(ptr);
	return newp;
}
