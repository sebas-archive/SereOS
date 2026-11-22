/* process/task.h - tareas cooperativas del kernel.
 *
 * IMPORTANTE: SereOS usa un modelo COOPERATIVO. No hay cambio de contexto
 * de pila: cada tarea es una funcion que se ejecuta un paso por tick desde
 * el bucle del escritorio (scheduler_tick). Es multitarea cooperativa real
 * (las tareas se turnan en round-robin), no multitarea preemptiva.
 */
#ifndef SEREOS_TASK_H
#define SEREOS_TASK_H
#include <stdint.h>

#define TASK_MAX       32
#define TASK_NAME_MAX  24

typedef enum {
	TASK_UNUSED = 0,
	TASK_READY,
	TASK_SLEEPING,
	TASK_DEAD
} task_state_t;

typedef struct task {
	int       id;
	char      name[TASK_NAME_MAX];
	void    (*entry)(void *arg);
	void     *arg;
	int       state;
	uint32_t  wake_tick;
	uint32_t  runs;
	uint32_t  created_tick;
} task_t;

void      task_init(void);
int       task_create(const char *name, void (*entry)(void *arg), void *arg);
void      task_kill(int id);
void      task_sleep_ms(int id, uint32_t ms);
void      task_wake(int id);
task_t   *task_get(int id);
task_t   *task_current(void);
int       task_active_count(void);
int       task_total_slots(void);
uint32_t  task_total_runs(void);

#endif
