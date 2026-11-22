/* kernel/panic.c - pantalla de excepciones del procesador y parada segura */
#include "panic.h"
#include "interrupts.h"
#include "terminal.h"
#include "serial.h"
#include "gui.h"
#include "io.h"
#include "string.h"
#include "sereos_version.h"

static const char *exception_names[32] = {
	"Division por cero", "Depuracion", "NMI", "Breakpoint", "Desbordamiento", "Fuera de rango",
	"Opcode invalido", "Dispositivo no disponible", "Doble fallo", "Coprocesador", "TSS invalido",
	"Segmento no presente", "Fallo de pila", "Proteccion general", "Fallo de pagina", "Reservada",
	"Error de punto flotante x87", "Alineacion", "Machine check", "Error SIMD", "Virtualizacion",
	"Control protection", "Reservada", "Reservada", "Reservada", "Reservada", "Reservada", "Reservada",
	"Hypervisor injection", "VMM communication", "Seguridad", "Reservada" };

/* Nombres con acentos correctos para la pantalla grafica (VGA usa CP437,
 * por eso la consola de texto conserva la tabla ASCII de arriba). */
static const char *exception_names_utf8[32] = {
	"División por cero", "Depuración", "NMI", "Breakpoint", "Desbordamiento", "Fuera de rango",
	"Opcode inválido", "Dispositivo no disponible", "Doble fallo", "Coprocesador", "TSS inválido",
	"Segmento no presente", "Fallo de pila", "Protección general", "Fallo de página", "Reservada",
	"Error de punto flotante x87", "Alineación", "Machine check", "Error SIMD", "Virtualización",
	"Control protection", "Reservada", "Reservada", "Reservada", "Reservada", "Reservada", "Reservada",
	"Hypervisor injection", "VMM communication", "Seguridad", "Reservada" };

void panic_exception(struct regs *r) {
	char detail[256];
	char line[128];
	cli();
	snprintf(detail, sizeof(detail),
	         "EIP = 0x%08x   CS = 0x%04x   EFLAGS = 0x%08x\n"
	         "EAX = 0x%08x   EBX = 0x%08x   ECX = 0x%08x   EDX = 0x%08x\n"
	         "Codigo de error = 0x%08x",
	         r->eip, r->cs, r->eflags, r->eax, r->ebx, r->ecx, r->edx, r->err_code);
	serial_printf("SEREOS_EXCEPTION %s\n", detail);

	/* consola de texto (visible si el escritorio no esta activo) */
	terminal_panic_screen();
	terminal_write("  *** " SEREOS_NAME ": EXCEPCION DEL PROCESADOR ***\n\n");
	snprintf(line, sizeof(line), "  Excepcion %u: %s\n",
	         r->int_no, (r->int_no < 32) ? exception_names[r->int_no] : "?");
	terminal_write(line);
	snprintf(line, sizeof(line), "  EIP = 0x%08x   Codigo de error = 0x%08x\n", r->eip, r->err_code);
	terminal_write(line);
	snprintf(line, sizeof(line), "  EAX = 0x%08x   EFLAGS = 0x%08x\n", r->eax, r->eflags);
	terminal_write(line);
	terminal_write("\n  El sistema se detuvo de forma segura. Reinicie la maquina.\n");

	/* si el escritorio grafico esta activo, se dibuja encima del framebuffer */
	if (gui_active()) {
		snprintf(line, sizeof(line), "Excepción %u: %s", r->int_no,
		         (r->int_no < 32) ? exception_names_utf8[r->int_no] : "?");
		gui_panic(line, detail);
	}
	for (;;) __asm__ volatile ("hlt");
}

void panic(const char *msg) {
	cli();
	serial_printf("SEREOS_PANIC %s\n", msg);
	terminal_panic_screen();
	terminal_write("  *** " SEREOS_NAME ": PANICO DEL KERNEL ***\n\n  ");
	terminal_write(msg);
	terminal_write("\n");
	if (gui_active()) gui_panic("Panico del kernel", msg);
	for (;;) __asm__ volatile ("hlt");
}
