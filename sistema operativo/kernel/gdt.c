/* kernel/gdt.c - Tabla Global de Descriptores propia (modelo de memoria plano)
 * 0: nulo | 0x08: codigo kernel | 0x10: datos kernel | 0x18: codigo usuario | 0x20: datos usuario */
#include <stdint.h>

struct gdt_entry {
	uint16_t limit_low, base_low;
	uint8_t base_mid, access, granularity, base_high;
} __attribute__((packed));
struct gdt_ptr { uint16_t limit; uint32_t base; } __attribute__((packed));

static struct gdt_entry gdt[5];
static struct gdt_ptr gp;
extern void gdt_flush(uint32_t);

static void gdt_set(int i, uint32_t base, uint32_t limit, uint8_t access, uint8_t gran) {
	gdt[i].base_low = base & 0xFFFF;
	gdt[i].base_mid = (base >> 16) & 0xFF;
	gdt[i].base_high = (base >> 24) & 0xFF;
	gdt[i].limit_low = limit & 0xFFFF;
	gdt[i].granularity = ((limit >> 16) & 0x0F) | (gran & 0xF0);
	gdt[i].access = access;
}

void gdt_init(void) {
	gp.limit = sizeof(gdt) - 1;
	gp.base = (uint32_t)&gdt;
	gdt_set(0, 0, 0, 0, 0);
	gdt_set(1, 0, 0xFFFFFFFF, 0x9A, 0xCF);   /* codigo, anillo 0 */
	gdt_set(2, 0, 0xFFFFFFFF, 0x92, 0xCF);   /* datos,  anillo 0 */
	gdt_set(3, 0, 0xFFFFFFFF, 0xFA, 0xCF);   /* codigo, anillo 3 */
	gdt_set(4, 0, 0xFFFFFFFF, 0xF2, 0xCF);   /* datos,  anillo 3 */
	gdt_flush((uint32_t)&gp);
}
