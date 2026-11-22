/* gui/splash.h - pantalla de arranque de SereOS */
#ifndef SEREOS_SPLASH_H
#define SEREOS_SPLASH_H

/* Muestra la pantalla de inicio con los mensajes reales registrados por el
 * kernel (klog), barra de progreso y transicion al escritorio. */
void splash_run(void);
void splash_skip(void);

#endif
