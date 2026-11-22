/* PAC-MAN SereOS - utilidades minimas independientes de libc */
#ifndef PACMAN_UTIL_H
#define PACMAN_UTIL_H

int pac_atoi(const char *s);
/* escribe el entero en buf y devuelve la longitud (sin '\0') */
int pac_itoa(int value, char *buf);

#endif /* PACMAN_UTIL_H */
