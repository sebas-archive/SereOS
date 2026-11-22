/* libc/string.c - implementacion propia de memoria, cadenas y formato */
#include "string.h"

void *memset(void *dst, int c, size_t n) {
	unsigned char *d = (unsigned char *)dst;
	while (n--) *d++ = (unsigned char)c;
	return dst;
}

void *memcpy(void *dst, const void *src, size_t n) {
	unsigned char *d = (unsigned char *)dst;
	const unsigned char *s = (const unsigned char *)src;
	/* copia por palabras cuando es posible (rendimiento del compositor) */
	while (n >= 4 && (((uintptr_t)d | (uintptr_t)s) & 3) == 0) {
		*(uint32_t *)d = *(const uint32_t *)s;
		d += 4; s += 4; n -= 4;
	}
	while (n--) *d++ = *s++;
	return dst;
}

void *memmove(void *dst, const void *src, size_t n) {
	unsigned char *d = (unsigned char *)dst;
	const unsigned char *s = (const unsigned char *)src;
	if (d == s || n == 0) return dst;
	if (d < s) { while (n--) *d++ = *s++; }
	else { d += n; s += n; while (n--) *--d = *--s; }
	return dst;
}

int memcmp(const void *a, const void *b, size_t n) {
	const unsigned char *x = (const unsigned char *)a, *y = (const unsigned char *)b;
	while (n--) { if (*x != *y) return (int)*x - (int)*y; x++; y++; }
	return 0;
}

size_t strlen(const char *s) { size_t n = 0; while (s[n]) n++; return n; }

size_t strnlen(const char *s, size_t max) {
	size_t n = 0; while (n < max && s[n]) n++; return n;
}

int strcmp(const char *a, const char *b) {
	while (*a && *a == *b) { a++; b++; }
	return (unsigned char)*a - (unsigned char)*b;
}

int strncmp(const char *a, const char *b, size_t n) {
	while (n && *a && *a == *b) { a++; b++; n--; }
	if (!n) return 0;
	return (unsigned char)*a - (unsigned char)*b;
}

int strcasecmp(const char *a, const char *b) {
	while (*a && *b) {
		unsigned char ca = (unsigned char)*a, cb = (unsigned char)*b;
		if (ca >= 'A' && ca <= 'Z') ca += 32;
		if (cb >= 'A' && cb <= 'Z') cb += 32;
		if (ca != cb) return ca - cb;
		a++; b++;
	}
	return (unsigned char)*a - (unsigned char)*b;
}

char *strcpy(char *dst, const char *src) {
	char *r = dst;
	while ((*dst++ = *src++)) {}
	return r;
}

char *strncpy(char *dst, const char *src, size_t n) {
	char *r = dst;
	while (n && *src) { *dst++ = *src++; n--; }
	while (n--) *dst++ = 0;
	return r;
}

char *strcat(char *dst, const char *src) {
	char *r = dst;
	while (*dst) dst++;
	while ((*dst++ = *src++)) {}
	return r;
}

char *strchr(const char *s, int c) {
	while (*s) { if (*s == (char)c) return (char *)s; s++; }
	return (c == 0) ? (char *)s : 0;
}

char *strrchr(const char *s, int c) {
	const char *last = 0;
	while (*s) { if (*s == (char)c) last = s; s++; }
	if (c == 0) return (char *)s;
	return (char *)last;
}

int atoi(const char *s) {
	int sign = 1, v = 0;
	while (*s == ' ' || *s == '\t') s++;
	if (*s == '-') { sign = -1; s++; }
	else if (*s == '+') s++;
	while (*s >= '0' && *s <= '9') { v = v * 10 + (*s - '0'); s++; }
	return v * sign;
}

int itoa(int v, char *buf) {
	char tmp[12]; int i = 0, len = 0;
	uint32_t u = (v < 0) ? (uint32_t)(-v) : (uint32_t)v;
	do { tmp[i++] = '0' + (u % 10); u /= 10; } while (u);
	if (v < 0) buf[len++] = '-';
	while (i) buf[len++] = tmp[--i];
	buf[len] = 0;
	return len;
}

int utoa(uint32_t v, char *buf, int base) {
	const char *digits = "0123456789abcdef";
	char tmp[33]; int i = 0, len = 0;
	if (base < 2) base = 10;
	do { tmp[i++] = digits[v % (uint32_t)base]; v /= (uint32_t)base; } while (v);
	while (i) buf[len++] = tmp[--i];
	buf[len] = 0;
	return len;
}

static void out_str(char *buf, size_t n, size_t *pos, const char *s) {
	while (s && *s) {
		if (*pos + 1 < n) buf[*pos] = *s;
		(*pos)++; s++;
	}
}

static void out_pad(char *buf, size_t n, size_t *pos, char c, int count) {
	while (count-- > 0) {
		if (*pos + 1 < n) buf[*pos] = c;
		(*pos)++;
	}
}

int vsnprintf(char *buf, size_t n, const char *fmt, va_list ap) {
	size_t pos = 0;
	if (n == 0) return 0;
	while (*fmt) {
		if (*fmt != '%') {
			if (pos + 1 < n) buf[pos] = *fmt;
			pos++; fmt++;
			continue;
		}
		fmt++;
		int zero_pad = 0, width = 0, left = 0;
		if (*fmt == '0') { zero_pad = 1; fmt++; }
		if (*fmt == '-') { left = 1; fmt++; }
		while (*fmt >= '0' && *fmt <= '9') { width = width * 10 + (*fmt - '0'); fmt++; }
		if (*fmt == 'l') fmt++;
		char tmp[36];
		int len = 0;
		switch (*fmt) {
		case 's': {
			const char *s = va_arg(ap, const char *);
			if (!s) s = "(null)";
			len = (int)strlen(s);
			if (!left) out_pad(buf, n, &pos, ' ', width - len);
			out_str(buf, n, &pos, s);
			if (left) out_pad(buf, n, &pos, ' ', width - len);
			break;
		}
		case 'c': {
			char c = (char)va_arg(ap, int);
			tmp[0] = c; tmp[1] = 0; len = 1;
			out_pad(buf, n, &pos, ' ', (left ? 0 : width - len));
			out_str(buf, n, &pos, tmp);
			out_pad(buf, n, &pos, ' ', (left ? width - len : 0));
			break;
		}
		case 'u': {
			len = utoa(va_arg(ap, uint32_t), tmp, 10);
			out_pad(buf, n, &pos, zero_pad ? '0' : ' ', width - len);
			out_str(buf, n, &pos, tmp);
			break;
		}
		case 'd': {
			len = itoa(va_arg(ap, int), tmp);
			int pad = width - len;
			if (zero_pad && tmp[0] == '-') {
				out_str(buf, n, &pos, "-");
				out_pad(buf, n, &pos, '0', pad);
				out_str(buf, n, &pos, tmp + 1);
			} else {
				out_pad(buf, n, &pos, zero_pad ? '0' : ' ', pad);
				out_str(buf, n, &pos, tmp);
			}
			break;
		}
		case 'x': {
			len = utoa(va_arg(ap, uint32_t), tmp, 16);
			out_pad(buf, n, &pos, zero_pad ? '0' : ' ', width - len);
			out_str(buf, n, &pos, tmp);
			break;
		}
		case 'p': {
			out_str(buf, n, &pos, "0x");
			len = utoa((uint32_t)(uintptr_t)va_arg(ap, void *), tmp, 16);
			out_pad(buf, n, &pos, '0', 8 - len);
			out_str(buf, n, &pos, tmp);
			break;
		}
		case '%': tmp[0] = '%'; tmp[1] = 0; out_str(buf, n, &pos, tmp); break;
		default:
			tmp[0] = '%'; tmp[1] = *fmt ? *fmt : 0; tmp[2] = 0;
			out_str(buf, n, &pos, tmp);
			break;
		}
		if (*fmt) fmt++;
	}
	if (pos >= n) pos = n - 1;
	buf[pos] = 0;
	return (int)pos;
}

int snprintf(char *buf, size_t n, const char *fmt, ...) {
	va_list ap;
	va_start(ap, fmt);
	int r = vsnprintf(buf, n, fmt, ap);
	va_end(ap);
	return r;
}
