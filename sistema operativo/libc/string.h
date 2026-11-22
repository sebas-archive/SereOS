/* libc/string.h - primitivas de cadenas y memoria propias (sin libc) */
#ifndef SEREOS_LIBC_STRING_H
#define SEREOS_LIBC_STRING_H
#include <stddef.h>
#include <stdint.h>
#include <stdarg.h>

void *memset(void *dst, int c, size_t n);
void *memcpy(void *dst, const void *src, size_t n);
void *memmove(void *dst, const void *src, size_t n);
int   memcmp(const void *a, const void *b, size_t n);

size_t strlen(const char *s);
size_t strnlen(const char *s, size_t max);
int    strcmp(const char *a, const char *b);
int    strncmp(const char *a, const char *b, size_t n);
int    strcasecmp(const char *a, const char *b);
char  *strcpy(char *dst, const char *src);
char  *strncpy(char *dst, const char *src, size_t n);
char  *strcat(char *dst, const char *src);
char  *strchr(const char *s, int c);
char  *strrchr(const char *s, int c);

int    atoi(const char *s);
int    itoa(int v, char *buf);                  /* decimal, devuelve longitud */
int    utoa(uint32_t v, char *buf, int base);   /* base 10 o 16, devuelve longitud */

int    vsnprintf(char *buf, size_t n, const char *fmt, va_list ap);
int    snprintf(char *buf, size_t n, const char *fmt, ...);
/* printf al log del kernel (serial + VGA). Definido en kernel/log.c */
int    kprintf(const char *fmt, ...);

#endif
