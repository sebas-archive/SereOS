/* kernel/kernel.c - arranque de SereOS v1.0 (SereOS Desktop) */
#include <stdint.h>
#include "sereos_version.h"
#include "terminal.h"
#include "interrupts.h"
#include "panic.h"
#include "io.h"
#include "serial.h"
#include "log.h"
#include "timer.h"
#include "rtc.h"
#include "input.h"
#include "speaker.h"
#include "audio.h"
#include "framebuffer.h"
#include "graphics.h"
#include "page.h"
#include "kmalloc.h"
#include "fs.h"
#include "task.h"
#include "scheduler.h"
#include "gui.h"
#include "app.h"
#include "splash.h"
#include "desktop.h"
#include "shell.h"

#define MULTIBOOT_BOOTLOADER_MAGIC 0x2BADB002
#define MB_FLAG_MEM      (1u << 0)
#define MB_FLAG_VIDEO    (1u << 2)
#define MB_FLAG_FB       (1u << 12)

struct multiboot_info {
	uint32_t flags;
	uint32_t mem_lower, mem_upper;
	uint32_t boot_device;
	uint32_t cmdline;
	uint32_t mods_count, mods_addr;
	uint32_t syms[4];
	uint32_t mmap_length, mmap_addr;
	uint32_t drives_length, drives_addr;
	uint32_t config_table;
	uint32_t boot_loader_name;
	uint32_t apm_table;
	uint32_t vbe_control_info, vbe_mode_info;
	uint16_t vbe_mode, vbe_interface_seg, vbe_interface_off, vbe_interface_len;
	uint64_t framebuffer_addr;
	uint32_t framebuffer_pitch, framebuffer_width, framebuffer_height;
	uint8_t  framebuffer_bpp, framebuffer_type;
} __attribute__((packed));

static struct multiboot_info *mbi;

static void boot_fail(const char *msg) {
	terminal_write_color("[FAIL] ", VGA_LIGHT_RED);
	terminal_write(msg);
	terminal_write("\n");
	klog_fail("%s", msg);
	for (;;) __asm__ volatile ("hlt");
}

void kernel_main(uint32_t magic, uint32_t mbi_addr) {
	cli();
	serial_init();
	terminal_init();
	klog_init();

	terminal_write_color(SEREOS_NAME " " SEREOS_VERSION " - Sistema operativo propio\n", VGA_YELLOW);
	terminal_write_color("Proyecto final de Sistemas Operativos - UMB 2026\n\n", VGA_YELLOW);

	if (magic != MULTIBOOT_BOOTLOADER_MAGIC) boot_fail("No fue cargado por un gestor Multiboot");
	mbi = (struct multiboot_info *)mbi_addr;
	klog_ok("Arranque Multiboot verificado (GRUB 2)");

	uint32_t mem_mib = 0, mem_upper_kib = 0;
	if (mbi->flags & MB_FLAG_MEM) {
		mem_upper_kib = mbi->mem_upper;
		mem_mib = (mbi->mem_lower + mbi->mem_upper) / 1024;
	}

	/* --- arquitectura basica x86 --- */
	gdt_init();
	klog_ok("GDT propia: 5 segmentos (kernel y usuario)");
	idt_init();
	klog_ok("IDT: 32 excepciones + 16 IRQ (PIC remapeado a 32-47)");

	/* --- drivers de entrada y tiempo --- */
	input_init();
	timer_init(100);
	klog_ok("Temporizador PIT a 100 Hz (IRQ 0)");
	keyboard_init();
	klog_ok("Teclado PS/2 con eventos (IRQ 1)");
	mouse_init();
	klog_ok(mouse_present() ? "Raton PS/2 con eventos (IRQ 12)" : "Raton PS/2 no detectado (navegacion por teclado)");
	rtc_init();
	klog_ok(rtc_available() ? "Reloj CMOS RTC" : "RTC no disponible");
	speaker_init();

	/* --- video: framebuffer de GRUB con reserva de VGA texto --- */
	if (fb_init(mbi_addr))
		klog_ok("Framebuffer grafico %ux%ux%u validado",
		        (unsigned)fb_width(), (unsigned)fb_height(), (unsigned)fb_bpp());
	else
		klog("Framebuffer no disponible: se conserva la terminal VGA");

	/* --- memoria --- */
	page_init(mem_upper_kib);
	klog_ok("Allocator de marcos fisicos inicializado");
	heap_init();
	klog_ok("Heap del kernel (kmalloc/kfree) inicializado");
	paging_init();
	klog_ok(paging_enabled() ? "Paginacion activada (identidad, PSE 4 MiB)" : "Paginacion no disponible");
	input_set_mouse_bounds(fb_available() ? (int)fb_width() : 80,
	                       fb_available() ? (int)fb_height() : 25);

	/* --- sistema de archivos y tareas --- */
	fs_init();
	klog_ok("RAMFS montado en /");
	task_init();
	scheduler_init();
	klog_ok("Planificador cooperativo round-robin listo");

	sti();
	klog_ok("Interrupciones habilitadas");

	/* --- audio: deteccion real del hardware (SB16 0x220..0x280, IRQ 5,
	 * DMA 1) con fallback al altavoz del PC. Se inicializa en el arranque
	 * para que Acerca de y la shell muestren siempre el backend real, sin
	 * depender de que se abra antes una aplicacion. */
	audio_init();
	klog_ok("Audio: %s", audio_detail());
	terminal_write("\nMemoria detectada: ");
	terminal_write_uint(mem_mib);
	terminal_write(" MiB\n");

	if (fb_available() && fb_has_backbuffer()) {
		gfx_init();
		klog_ok("Motor grafico nativo inicializado");
		apps_register();
		klog_ok("Aplicaciones del escritorio registradas");
		gui_init();
		serial_printf("SEREOS_BOOT_OK mem=%uMiB\n", mem_mib);
		splash_run();
		serial_write("GUI_READY\n");
		gui_run();
	}

	/* Alternativa de arranque sin framebuffer: terminal VGA + shell completa */
	klog("Iniciando consola de texto de respaldo");
	serial_write("SEREOS_TEXT_MODE\n");
	shell_run_text();
	for (;;) __asm__ volatile ("hlt");
}
