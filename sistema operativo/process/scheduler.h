/* process/scheduler.h - planificador cooperativo round-robin */
#ifndef SEREOS_SCHEDULER_H
#define SEREOS_SCHEDULER_H
#include <stdint.h>

void     scheduler_init(void);
/* ejecuta un paso de cada tarea READY en round-robin, despierta dormidas.
 * Se llama una vez por frame desde el bucle del escritorio. */
void     scheduler_tick(void);
uint32_t scheduler_steps(void);
uint32_t scheduler_activations(void);
int      scheduler_current_id(void);

#endif
