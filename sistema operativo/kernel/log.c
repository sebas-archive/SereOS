/* kernel/log.c - registro circular del kernel (klog) y kprintf
 *
 * klog guarda las ultimas KLOG_MAX entradas en un anillo estatico con la
 * marca de tiempo real de timer_ticks(). Cada entrada conserva su nivel
 * (info / ok / fail) para que la splash y el monitor puedan mostrar el
 * arranque real y contar errores. klog_line() devuelve un puntero estable a
 * la cadena almacenada: sigue siendo valido hasta que el anillo se llena y
 * esa ranura se reutiliza.
 *
 * kprintf() es el printf de proposito general del kernel: formatea con la
 * vsnprintf propia y replica la salida en COM1 (serial) y en la terminal
 * VGA. Asi el log tambien se puede leer desde el host con -serial file:...,
 * que es lo que usan los marcadores de QA.
 *
 * Todo tiene proteccion para llamarse antes de klog_init(): en ese caso el
 * anillo permanece intacto y kprintf solo escribe en los destinos de salida.
 */
#include "log.h"
#include "string.h"
#include "serial.h"
#include "terminal.h"
#include "timer.h"

#define KLOG_LINE_MAX 120

#define LEVEL_INFO 0
#define LEVEL_OK   1
#define LEVEL_FAIL 2

typedef struct {
	uint32_t tick;
	uint8_t  level;
	char     text[KLOG_LINE_MAX];
} klog_item_t;

static klog_item_t ring[KLOG_MAX];
static int head;         /* proxima ranura a escribir */
static int count;        /* entradas validas (maximo KLOG_MAX) */
static int errors;       /* entradas de nivel FAIL presentes en el anillo */
static int ready;        /* klog_init() ya se ejecuto */

/* ======================================================================== */
/* kprintf: serial + terminal VGA                                           */
/* ======================================================================== */
int kprintf(const char *fmt, ...) {
	char buf[256];
	va_list ap;
	int n;

	if (!fmt) return 0;
	va_start(ap, fmt);
	n = vsnprintf(buf, sizeof(buf), fmt, ap);
	va_end(ap);
	if (n < 0) return 0;
	if ((size_t)n >= sizeof(buf)) n = (int)sizeof(buf) - 1;

	serial_write(buf);
	terminal_write(buf);
	return n;
}

/* ======================================================================== */
/* anillo circular                                                          */
/* ======================================================================== */
static void klog_add(int level, const char *text) {
	klog_item_t *e;
	const char *prefix = "";

	if (!ready) return;                 /* proteccion: aun no inicializado */
	if (!text) text = "";

	/* si el anillo esta lleno se sobrescribe la entrada mas antigua */
	e = &ring[head];
	if (count == KLOG_MAX) {
		if (e->level == LEVEL_FAIL && errors > 0) errors--;
	} else {
		count++;
	}

	e->tick = timer_ticks();
	e->level = (uint8_t)level;
	if (level == LEVEL_OK) prefix = "[OK] ";
	else if (level == LEVEL_FAIL) prefix = "[FAIL] ";
	/* el prefijo de nivel forma parte de la linea almacenada: asi klog_line()
	 * (splash, dmesg) muestra la severidad real de cada mensaje */
	snprintf(e->text, KLOG_LINE_MAX, "%s%s", prefix, text);

	head = (head + 1) % KLOG_MAX;
	if (level == LEVEL_FAIL) errors++;

	kprintf("%s\n", e->text);
}

/* indice real del anillo para la entrada logica i (0 = mas antigua) */
static int ring_index(int i) {
	if (!ready || i < 0 || i >= count) return -1;
	return (head - count + i + KLOG_MAX * 2) % KLOG_MAX;
}

void klog_init(void) {
	memset(ring, 0, sizeof(ring));
	head = 0;
	count = 0;
	errors = 0;
	ready = 1;
}

void klog(const char *fmt, ...) {
	char buf[KLOG_LINE_MAX];
	va_list ap;

	if (!ready || !fmt) return;
	va_start(ap, fmt);
	vsnprintf(buf, sizeof(buf), fmt, ap);
	va_end(ap);
	klog_add(LEVEL_INFO, buf);
}

void klog_ok(const char *fmt, ...) {
	char buf[KLOG_LINE_MAX];
	va_list ap;

	if (!ready || !fmt) return;
	va_start(ap, fmt);
	vsnprintf(buf, sizeof(buf), fmt, ap);
	va_end(ap);
	klog_add(LEVEL_OK, buf);
}

void klog_fail(const char *fmt, ...) {
	char buf[KLOG_LINE_MAX];
	va_list ap;

	if (!ready || !fmt) return;
	va_start(ap, fmt);
	vsnprintf(buf, sizeof(buf), fmt, ap);
	va_end(ap);
	klog_add(LEVEL_FAIL, buf);
}

int klog_count(void) { return count; }

const char *klog_line(int i) {
	int idx = ring_index(i);
	return idx >= 0 ? ring[idx].text : "";
}

uint32_t klog_entry_tick(int i) {
	int idx = ring_index(i);
	return idx >= 0 ? ring[idx].tick : 0;
}

int klog_errors(void) { return errors; }
