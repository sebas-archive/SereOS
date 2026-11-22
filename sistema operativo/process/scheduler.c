/* process/scheduler.c - planificador cooperativo round-robin
 *
 * Se llama a scheduler_tick() una vez por frame (y tambien desde el bucle de
 * respaldo). En cada llamada:
 *   1) se despiertan las tareas SLEEPING cuyo wake_tick ya paso;
 *   2) se ejecuta UN paso de cada tarea READY, en orden circular empezando
 *      en el cursor round-robin (asi ninguna tarea acapara el primer turno);
 *   3) el cursor avanza para repartir el orden en la ronda siguiente.
 *
 * No hay cambio de pila ni de contexto: cada `entry()` retorna antes de que
 * el planificador continue. Una tarea cooperativa debe ser corta y no
 * bloquear. Contadores expuestos:
 *   - scheduler_steps():       pasos de tarea ejecutados en total.
 *   - scheduler_activations(): rondas de planificacion que ejecutaron al
 *                              menos una tarea (actividad real del sistema).
 *   - scheduler_current_id():  ultima tarea que corrio (0 = ninguna aun).
 */
#include "scheduler.h"
#include "task.h"
#include "timer.h"

/* API interna implementada en process/task.c (no congelada en el header) */
extern void task_set_current(int id);

static uint32_t steps;
static uint32_t activations;
static int      last_id;
static uint32_t rr_cursor;

void scheduler_init(void) {
	steps = 0;
	activations = 0;
	last_id = 0;
	rr_cursor = 0;
}

void scheduler_tick(void) {
	uint32_t now;
	int i, ran = 0;

	now = timer_ticks();

	/* 1) despertar tareas dormidas cuyo plazo ya vencio.
	 * Se compara con aritmetica sin signo tolerante a desbordamiento. */
	for (i = 1; i <= task_total_slots(); i++) {
		task_t *t = task_get(i);
		if (!t || t->state != TASK_SLEEPING) continue;
		if (t->wake_tick == 0) { task_wake(i); continue; }
		if ((int32_t)(now - t->wake_tick) >= 0) task_wake(i);
	}

	/* 2) un paso por cada tarea READY, en orden circular */
	for (i = 0; i < task_total_slots(); i++) {
		int id = 1 + (int)((rr_cursor + (uint32_t)i) % (uint32_t)task_total_slots());
		task_t *t = task_get(id);

		if (!t || t->state != TASK_READY || !t->entry) continue;

		task_set_current(id);
		t->runs++;
		steps++;
		ran = 1;
		t->entry(t->arg);

		/* la tarea pudo matarse a si misma o dormirse durante el paso */
		task_set_current(0);
		if (task_get(id)) last_id = id;
	}

	/* 3) avanzar el cursor para repartir el primer turno entre rondas */
	if (task_total_slots() > 0)
		rr_cursor = (rr_cursor + 1u) % (uint32_t)task_total_slots();

	if (ran) activations++;
}

uint32_t scheduler_steps(void) { return steps; }
uint32_t scheduler_activations(void) { return activations; }
int scheduler_current_id(void) { return last_id; }
