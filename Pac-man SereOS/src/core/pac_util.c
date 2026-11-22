/* PAC-MAN SereOS - utilidades minimas (portables SereOS/Linux)
 *
 * El core solo necesita memset/memcpy de <string.h>; para enteros se usan
 * estas funciones propias porque SereOS no tiene itoa y Linux no lo estandariza.
 */
#include <stddef.h>
#include "pac_util.h"

int pac_atoi(const char *s)
{
	int neg = 0;
	int value = 0;

	if (!s)
		return 0;
	while (*s == ' ' || *s == '\t')
		s++;
	if (*s == '-') {
		neg = 1;
		s++;
	} else if (*s == '+') {
		s++;
	}
	while (*s >= '0' && *s <= '9') {
		value = value * 10 + (*s - '0');
		s++;
	}
	return neg ? -value : value;
}

int pac_itoa(int value, char *buf)
{
	char tmp[12];
	int n = 0;
	int i = 0;
	unsigned int v;

	if (!buf)
		return 0;
	if (value < 0) {
		buf[i++] = '-';
		v = (unsigned int)(-value);
	} else {
		v = (unsigned int)value;
	}
	do {
		tmp[n++] = (char)('0' + (v % 10u));
		v /= 10u;
	} while (v != 0u);
	while (n > 0)
		buf[i++] = tmp[--n];
	buf[i] = '\0';
	return i;
}
