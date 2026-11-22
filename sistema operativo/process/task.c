/* process/task.c - tabla de tareas cooperativas de SereOS
 *
 * Modelo COOPERATIVO (documentado en process/task.h): no existe cambio de
 * pila ni de contexto hardware. Cada tarea es una funcion `entry(arg)` que el
 * planificador ejecuta un paso por ronda desde el bucle del escritorio.
 * Por tanto:
 *  - Las tareas NO deben bloquearse (nada de esperas con hlt ni bucles
 *    infinitos): deben guardar su estado y retornar.
 *  - task_sleep_ms() no duerme al CPU: marca la tarea como SLEEPING y el
 *    planificador la despierta cuando timer_ticks() alcanza wake_tick.
 *  - Al matar una tarea su ranura se libera inmediatamente (estado UNUSED).
 *
 * Los identificadores son estables mientras la tarea vive: id = indice + 1.
 */
#include "task.h"
#include "timer.h"
#include "string.h"

static task_t tasks[TASK_MAX];
static task_t *current_task;
static int    initialized_tasks;

static task_t *slot_of(int id) {
	if (id <= 0 || id > TASK_MAX) return 0;
	return &tasks[id - 1];
}

void task_init(void) {
	int i;
	memset(tasks, 0, sizeof(tasks));
	for (i = 0; i < TASK_MAX; i++) {
		tasks[i].id = i + 1;         /* id estable por ranura */
		tasks[i].state = TASK_UNUSED;
	}
	current_task = 0;
	initialized_tasks = 1;
}

int task_create(const char *name, void (*entry)(void *arg), void *arg) {
	int i;
	task_t *t;

	if (!initialized_tasks) task_init();
	if (!entry) return -1;

	for (i = 0; i < TASK_MAX; i++) {
		if (tasks[i].state != TASK_UNUSED) continue;
		t = &tasks[i];
		t->id = i + 1;
		memset(t->name, 0, sizeof(t->name));
		if (name) {
			strncpy(t->name, name, TASK_NAME_MAX - 1);
			t->name[TASK_NAME_MAX - 1] = 0;
		}
		t->entry = entry;
		t->arg = arg;
		t->state = TASK_READY;
		t->wake_tick = 0;
		t->runs = 0;
		t->created_tick = timer_ticks();
		return t->id;
	}
	return -1;   /* tabla llena */
}

void task_kill(int id) {
	task_t *t = slot_of(id);
	if (!t || t->state == TASK_UNUSED) return;
	/* estado transitorio DEAD y liberacion inmediata de la ranura */
	t->state = TASK_DEAD;
	t->entry = 0;
	t->arg = 0;
	t->wake_tick = 0;
	if (current_task == t) current_task = 0;
	t->runs = 0;
	t->name[0] = 0;
	t->state = TASK_UNUSED;
}

void task_sleep_ms(int id, uint32_t ms) {
	task_t *t = slot_of(id);
	uint32_t hz, ticks;

	if (!t || t->state == TASK_UNUSED || t->state == TASK_DEAD) return;

	/* convertir milisegundos a ticks del PIT (actualmente 100 Hz) */
	hz = timer_hz();
	if (hz == 0) hz = 1000u;         /* sin PIT: se asume 1 tick por ms */
	ticks = (ms * hz + 999u) / 1000u;
	if (ticks == 0) ticks = 1;       /* dormir "0 ms" cede un turno */

	t->wake_tick = timer_ticks() + ticks;
	t->state = TASK_SLEEPING;
}

void task_wake(int id) {
	task_t *t = slot_of(id);
	if (!t || t->state != TASK_SLEEPING) return;
	t->wake_tick = 0;
	t->state = TASK_READY;
}

task_t *task_get(int id) {
	task_t *t = slot_of(id);
	if (!t || t->state == TASK_UNUSED || t->state == TASK_DEAD) return 0;
	return t;
}

task_t *task_current(void) { return current_task; }

int task_active_count(void) {
	int i, n = 0;
	for (i = 0; i < TASK_MAX; i++)
		if (tasks[i].state == TASK_READY || tasks[i].state == TASK_SLEEPING) n++;
	return n;
}

int task_total_slots(void) { return TASK_MAX; }

uint32_t task_total_runs(void) {
	int i;
	uint32_t n = 0;
	for (i = 0; i < TASK_MAX; i++)
		if (tasks[i].state != TASK_UNUSED) n += tasks[i].runs;
	return n;
}

/* ======================================================================== */
/* API interna compartida con scheduler.c (no forma parte del header)       */
/* ======================================================================== */

/* marca la tarea que el planificador esta ejecutando en este momento.
 * id = 0 limpia la tarea actual. */
void task_set_current(int id) {
	current_task = task_get(id);
}
