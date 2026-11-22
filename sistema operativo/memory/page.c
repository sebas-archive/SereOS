/* memory/page.c - allocator de marcos fisicos de 4 KiB y paginacion con PSE
 *
 * El allocator trabaja sobre un bitmap estatico: un bit por marco de 4 KiB.
 * Se reservan permanentemente la memoria baja (0..1 MiB: BIOS, VGA, EBDA),
 * la imagen del kernel (kernel_start..kernel_end mas un margen de seguridad)
 * y el framebuffer lineal que entrega GRUB. El resto de la RAM detectada por
 * Multiboot (mem_upper) queda disponible mediante page_alloc()/page_free().
 *
 * La identidad fisica = virtual se mantiene y ademas se resuelve el
 * framebuffer, que suele vivir por encima de 0xE0000000 (fuera de los
 * primeros 512 MiB). Para ello en paging_init() se construye un page
 * directory con paginas de 4 MiB (PSE) para 0..512 MiB y para el rango
 * [0xE0000000, 0xFFFFFFFF] (donde QEMU/GRUB colocan el LFB), mas cualquier
 * otro rango 4 MiB alineado que ocupe el framebuffer. La primera pagina del
 * directorio usa paginas normales de 4 KiB, con lo que el codigo de bajo
 * nivel y los datos del kernel quedan mapeados con granularidad fina.
 *
 * Todo el allocator vive en memoria estatica (.bss) porque page_init() se
 * llama antes de que exista ningun heap.
 */
#include "page.h"
#include "framebuffer.h"
#include "string.h"

/* Identidad maxima con PSE: 512 MiB. Los marcos por encima de este limite
 * no serian accesibles tras activar la paginacion, asi que no se entregan. */
#define MAX_PHYS_BYTES      (512u * 1024u * 1024u)
#define MAX_FRAMES          (MAX_PHYS_BYTES / PAGE_SIZE)   /* 131072 marcos */
#define BITMAP_WORDS        (MAX_FRAMES / 32u)             /* 4096 palabras */
#define LOW_MEMORY_BYTES    (1u * 1024u * 1024u)
#define RESERVE_AFTER_KERNEL (64u * 1024u)  /* margen de seguridad tras el kernel */

/* Bits de las entradas de paginacion x86 */
#define PG_PRESENT  0x001u
#define PG_RW       0x002u
#define PG_USER     0x004u
#define PG_PS       0x080u   /* page size: pagina de 4 MiB (requiere CR4.PSE) */
#define PG_4MIB     (PG_PRESENT | PG_RW | PG_PS)

#define IDENT_TOP_4MIB  (MAX_PHYS_BYTES / (4u * 1024u * 1024u))  /* 128 entradas */
#define FB_MMIO_BASE    0xE0000000u

/* --- estado del allocator de marcos ------------------------------------- */
static uint32_t frame_used_bitmap[BITMAP_WORDS];   /* 1 = usado             */
static uint32_t frame_reserved[BITMAP_WORDS];      /* 1 = no liberable      */
static uint32_t total_frames;                      /* marcos fisicos totales*/
static uint32_t free_frames;                       /* marcos libres         */
static uint32_t frame_hint;                        /* busqueda first-fit    */
static int      page_ready;

/* --- estructuras de paginacion (alineadas a 4 KiB) ---------------------- */
static uint32_t page_directory[1024] __attribute__((aligned(PAGE_SIZE)));
static uint32_t low_page_table[1024] __attribute__((aligned(PAGE_SIZE)));
static int      paging_state;

/* ======================================================================== */
/* utilidades de bitmap                                                     */
/* ======================================================================== */
static inline void bm_set(uint32_t *bm, uint32_t f)   { bm[f >> 5] |=  (1u << (f & 31u)); }
static inline void bm_clear(uint32_t *bm, uint32_t f) { bm[f >> 5] &= ~(1u << (f & 31u)); }
static inline int  bm_test(const uint32_t *bm, uint32_t f) { return (bm[f >> 5] >> (f & 31u)) & 1u; }

/* marca un rango [start, end) como reservado (usado y no liberable) */
static void reserve_range(uint32_t start, uint32_t end) {
	uint32_t first = start / PAGE_SIZE;
	uint32_t last  = (end + PAGE_SIZE - 1u) / PAGE_SIZE;   /* exclusivo, redondeo arriba */
	uint32_t total_end = total_frames;                     /* fuera de rango: se ignora */
	uint32_t f;

	if (last > total_end) last = total_end;
	for (f = first; f < last; f++) {
		bm_set(frame_used_bitmap, f);
		bm_set(frame_reserved, f);
	}
}

/* ======================================================================== */
/* init / estadisticas                                                      */
/* ======================================================================== */
void page_init(uint32_t mem_upper_kib) {
	const fb_info_t *fb;
	uint32_t mem_bytes, first_free, f;

	memset(frame_used_bitmap, 0, sizeof(frame_used_bitmap));
	memset(frame_reserved, 0, sizeof(frame_reserved));
	total_frames = 0;
	free_frames = 0;
	frame_hint = 0;
	page_ready = 0;

	/* mem_upper es la RAM por encima de 1 MiB expresada en KiB */
	mem_bytes = LOW_MEMORY_BYTES + mem_upper_kib * 1024u;
	if (mem_bytes > MAX_PHYS_BYTES) mem_bytes = MAX_PHYS_BYTES;
	if (mem_bytes < (4u * 1024u * 1024u)) mem_bytes = 4u * 1024u * 1024u;
	total_frames = mem_bytes / PAGE_SIZE;

	/* arrancamos con todos los marcos marcados como usados y liberamos
	 * solo los que estan por encima de 1 MiB y no son reservados */
	for (f = 0; f < BITMAP_WORDS; f++) frame_used_bitmap[f] = 0xFFFFFFFFu;

	/* 1) memoria baja: BIOS, tabla de vectores, VGA texto, EBDA... */
	reserve_range(0, LOW_MEMORY_BYTES);

	/* 2) imagen del kernel + margen despues de kernel_end */
	{
		uint32_t kstart = ((uint32_t)kernel_start) & ~(PAGE_SIZE - 1u);
		uint32_t kend   = (uint32_t)kernel_end + RESERVE_AFTER_KERNEL;
		if (kstart < LOW_MEMORY_BYTES) kstart = LOW_MEMORY_BYTES;
		if (kend < kstart) kend = kstart + PAGE_SIZE;
		reserve_range(kstart, kend);
	}

	/* 3) framebuffer lineal de GRUB, si el driver ya lo valido */
	fb = fb_info();
	if (fb && fb->available && fb->bytes > 0 && fb->physical > 0) {
		uint32_t fstart = fb->physical;
		uint32_t fend   = fb->physical + fb->bytes;
		if (fend > fstart) reserve_range(fstart, fend);
	}

	/* 4) liberar como disponibles los marcos que acabaron sin reserva */
	first_free = LOW_MEMORY_BYTES / PAGE_SIZE;
	for (f = first_free; f < total_frames; f++) {
		if (bm_test(frame_reserved, f)) continue;
		bm_clear(frame_used_bitmap, f);
		free_frames++;
	}

	page_ready = 1;
}

/* ======================================================================== */
/* allocator de marcos                                                      */
/* ======================================================================== */
void *page_alloc(void) {
	uint32_t scanned = 0, f;

	if (!page_ready || free_frames == 0) return 0;
	f = frame_hint;
	while (scanned < total_frames) {
		if (f >= total_frames) f = 0;
		if (!bm_test(frame_used_bitmap, f)) {
			bm_set(frame_used_bitmap, f);
			free_frames--;
			frame_hint = f + 1;
			/* direccion fisica = virtual gracias a la identidad */
			return (void *)(uintptr_t)(f * PAGE_SIZE);
		}
		/* avance rapido palabra a palabra cuando esta llena */
		if ((f & 31u) == 0 && frame_used_bitmap[f >> 5] == 0xFFFFFFFFu) {
			f += 32;
			scanned += 32;
		} else {
			f++;
			scanned++;
		}
	}
	return 0;
}

void page_free(void *p) {
	uint32_t frame;
	if (!page_ready || !p) return;
	frame = (uint32_t)(uintptr_t)p / PAGE_SIZE;
	if ((uint32_t)(uintptr_t)p % PAGE_SIZE != 0) return;   /* no es un marco */
	if (frame >= total_frames) return;                     /* fuera de la RAM */
	if (bm_test(frame_reserved, frame)) return;            /* no liberable */
	if (!bm_test(frame_used_bitmap, frame)) return;        /* doble free: ignorado */
	bm_clear(frame_used_bitmap, frame);
	free_frames++;
	if (frame < frame_hint) frame_hint = frame;
}

uint32_t page_frame_size(void)   { return PAGE_SIZE; }
uint32_t page_total_frames(void) { return total_frames; }
uint32_t page_free_frames(void)  { return free_frames; }
uint32_t page_used_frames(void)  { return total_frames - free_frames; }
uint32_t page_total_bytes(void)  { return total_frames * PAGE_SIZE; }
uint32_t page_used_bytes(void)   { return (total_frames - free_frames) * PAGE_SIZE; }

/* ======================================================================== */
/* paginacion con PSE (4 MiB)                                               */
/* ======================================================================== */
static inline uint32_t read_cr0(void) {
	uint32_t v;
	__asm__ volatile ("mov %%cr0, %0" : "=r"(v));
	return v;
}
static inline void write_cr0(uint32_t v) {
	__asm__ volatile ("mov %0, %%cr0" : : "r"(v) : "memory");
}
static inline uint32_t read_cr3(void) {
	uint32_t v;
	__asm__ volatile ("mov %%cr3, %0" : "=r"(v));
	return v;
}
static inline void write_cr3(uint32_t v) {
	__asm__ volatile ("mov %0, %%cr3" : : "r"(v) : "memory");
}
static inline uint32_t read_cr4(void) {
	uint32_t v;
	__asm__ volatile ("mov %%cr4, %0" : "=r"(v));
	return v;
}
static inline void write_cr4(uint32_t v) {
	__asm__ volatile ("mov %0, %%cr4" : : "r"(v) : "memory");
}

void paging_init(void) {
	const fb_info_t *fb;
	uint32_t f, i;

	if (paging_state) return;

	/* Tabla de 4 KiB para el primer bloque de 4 MiB: identidad fina donde
	 * viven la memoria baja del kernel, la pila y los datos estaticos. */
	for (i = 0; i < 1024; i++)
		low_page_table[i] = (i * PAGE_SIZE) | PG_PRESENT | PG_RW;

	/* Directorio vacio */
	for (i = 0; i < 1024; i++) page_directory[i] = 0;

	/* [0, 4 MiB) con paginas normales de 4 KiB */
	page_directory[0] = ((uint32_t)(uintptr_t)low_page_table) | PG_PRESENT | PG_RW;

	/* [4 MiB, 512 MiB) con paginas PSE de 4 MiB, identidad 1:1 */
	for (i = 1; i < IDENT_TOP_4MIB; i++)
		page_directory[i] = (i << 22) | PG_4MIB;

	/* Rango del framebuffer alineado a 4 MiB. Normalmente cae dentro de la
	 * ventana MMIO 0xE0000000-0xFFFFFFFF, pero lo mapeamos explicitamente
	 * por si el firmware lo coloca en otro sitio. */
	fb = fb_info();
	if (fb && fb->available && fb->bytes > 0 && fb->physical > 0) {
		uint32_t start = fb->physical & ~0x3FFFFFu;
		uint32_t end   = (fb->physical + fb->bytes + 0x3FFFFFu) & ~0x3FFFFFu;
		for (f = start; f < end; f += 0x400000u) {
			uint32_t idx = f >> 22;
			if (idx < 1024) page_directory[idx] = f | PG_4MIB;
		}
	}

	/* Ventana MMIO alta 0xE0000000-0xFFFFFFFF: incluye el LFB VGA estandar
	 * de QEMU (0xFD000000), los registros de la tarjeta grafica y el BIOS
	 * de video. Se mapea identidad como 4 MiB para que nadie la toque. */
	for (i = FB_MMIO_BASE >> 22; i < 1024; i++) {
		if (!page_directory[i]) page_directory[i] = (i << 22) | PG_4MIB;
	}

	/* CR4.PSE = 1 antes de activar CR0.PG; cargar CR3 refresca la TLB */
	write_cr4(read_cr4() | (1u << 4));
	write_cr3((uint32_t)(uintptr_t)page_directory);
	write_cr0(read_cr0() | 0x80000000u);   /* CR0.PG */

	paging_state = (read_cr0() & 0x80000000u) ? 1 : 0;
}

int paging_enabled(void) {
	return paging_state;
}

uint32_t paging_directory_phys(void) {
	return (uint32_t)(uintptr_t)page_directory;
}
