/* drivers/rtc.c - reloj de tiempo real CMOS (Motorola MC146818 y compatibles)
 *
 * Lectura por los puertos 0x70 (indice) y 0x71 (datos). Se respeta el bit de
 * "update in progress" (UIP) del registro de estado A y se lee la hora dos
 * veces hasta obtener dos snapshots identicos: asi nunca se mezclan campos
 * de dos segundos distintos. Se soportan los modos BCD y binario, y los
 * formatos de 12 y 24 horas (registro de estado B).
 *
 * Todo es real: si el RTC no responde o los campos no son validos,
 * rtc_available() devuelve 0 y los strings indican "--".
 */
#include "rtc.h"
#include "io.h"
#include "string.h"

#define CMOS_INDEX 0x70
#define CMOS_DATA  0x71

#define RTC_SEC      0x00
#define RTC_SEC_ALRM 0x01
#define RTC_MIN      0x02
#define RTC_HOUR     0x04
#define RTC_WEEKDAY  0x06
#define RTC_DAY      0x07
#define RTC_MONTH    0x08
#define RTC_YEAR     0x09
#define RTC_STATUS_A 0x0A
#define RTC_STATUS_B 0x0B
#define RTC_CENTURY  0x32

static int available;

static uint8_t cmos_read(uint8_t reg) {
	outb(CMOS_INDEX, reg);
	io_wait();
	return inb(CMOS_DATA);
}

/* espera a que el RTC no este actualizando sus registros (UIP = 0) */
static int wait_not_updating(void) {
	uint32_t guard = 1000000u;
	while (guard--) {
		if (!(cmos_read(RTC_STATUS_A) & 0x80)) return 1;
	}
	return 0;   /* RTC bloqueado: se intenta leer igualmente */
}

static uint8_t bcd_to_bin(uint8_t v) {
	return (uint8_t)((v & 0x0F) + ((v >> 4) * 10));
}

typedef struct {
	uint8_t sec, min, hour, weekday, day, month, year, status_b;
	uint8_t century;
} raw_snapshot_t;

static void read_raw(raw_snapshot_t *r) {
	r->sec      = cmos_read(RTC_SEC);
	r->min      = cmos_read(RTC_MIN);
	r->hour     = cmos_read(RTC_HOUR);
	r->weekday  = cmos_read(RTC_WEEKDAY);
	r->day      = cmos_read(RTC_DAY);
	r->month    = cmos_read(RTC_MONTH);
	r->year     = cmos_read(RTC_YEAR);
	r->status_b = cmos_read(RTC_STATUS_B);
	r->century  = cmos_read(RTC_CENTURY);
}

static int raw_equal(const raw_snapshot_t *a, const raw_snapshot_t *b) {
	return a->sec == b->sec && a->min == b->min && a->hour == b->hour &&
	       a->weekday == b->weekday && a->day == b->day &&
	       a->month == b->month && a->year == b->year &&
	       a->century == b->century;
}

/* convierte un snapshot crudo a campos numericos; devuelve 0 si es invalido */
static int decode(const raw_snapshot_t *r, rtc_time_t *out) {
	int sec, min, hour, day, month, year, weekday, century;
	int binary = (r->status_b & 0x04) != 0;    /* 1 = binario, 0 = BCD */
	int h24    = (r->status_b & 0x02) != 0;    /* 1 = 24h, 0 = 12h */
	int pm = 0;

	sec   = r->sec;
	min   = r->min;
	hour  = r->hour;
	day   = r->day;
	month = r->month;
	year  = r->year;
	weekday = r->weekday;
	century = r->century;

	if (!binary) {
		/* en 12h el bit 7 del registro de hora marca PM, no es BCD */
		if (!h24) pm = (hour & 0x80) ? 1 : 0;
		sec   = bcd_to_bin((uint8_t)sec);
		min   = bcd_to_bin((uint8_t)min);
		year  = bcd_to_bin((uint8_t)year);
		month = bcd_to_bin((uint8_t)month);
		day   = bcd_to_bin((uint8_t)day);
		weekday = bcd_to_bin((uint8_t)weekday);
		century = bcd_to_bin((uint8_t)century);
	}
	if (!h24) {
		hour &= 0x7F;           /* descartar el bit PM */
		if (!binary) hour = bcd_to_bin((uint8_t)hour);
		if (pm && hour != 12) hour += 12;
		if (!pm && hour == 12) hour = 0;
	} else if (!binary) {
		hour = bcd_to_bin((uint8_t)hour);
	}

	if (century < 19 || century > 99) century = 20;
	if (year < 0 || year > 99) return 0;

	/* validacion de rangos: si no es coherente, se descarta la lectura */
	if (sec < 0 || sec > 59) return 0;
	if (min < 0 || min > 59) return 0;
	if (hour < 0 || hour > 23) return 0;
	if (day < 1 || day > 31) return 0;
	if (month < 1 || month > 12) return 0;
	if (weekday < 1 || weekday > 7) weekday = 0;
	else weekday -= 1;                     /* CMOS: 1 = domingo */

	out->second = sec;
	out->minute = min;
	out->hour = hour;
	out->day = day;
	out->month = month;
	out->year = century * 100 + year;
	out->weekday = weekday;
	out->valid = 1;
	return 1;
}

void rtc_init(void) {
	raw_snapshot_t a, b;
	int tries;

	available = 0;
	if (!wait_not_updating()) return;

	read_raw(&a);
	for (tries = 0; tries < 8; tries++) {
		if (!wait_not_updating()) break;
		read_raw(&b);
		if (raw_equal(&a, &b)) break;
		a = b;
	}

	{
		rtc_time_t t;
		if (decode(&b, &t)) available = 1;
	}
}

int rtc_available(void) { return available; }

void rtc_read(rtc_time_t *out) {
	raw_snapshot_t a, b;
	int tries, ok = 0;

	if (!out) return;
	memset(out, 0, sizeof(*out));
	for (tries = 0; tries < 4; tries++) {
		if (!wait_not_updating()) break;
		read_raw(&a);
		if (!wait_not_updating()) break;
		read_raw(&b);
		if (raw_equal(&a, &b) && decode(&b, out)) { ok = 1; break; }
		a = b;
	}
	if (!ok) {
		out->valid = 0;
		out->second = out->minute = out->hour = 0;
		out->day = 0;
		out->month = 0;
		out->year = 0;
	}
	available = ok;
}

const char *rtc_time_string(char *buf, uint32_t n) {
	rtc_time_t t;
	if (!buf || n == 0) return buf;
	rtc_read(&t);
	if (!t.valid) {
		strncpy(buf, "--:--:--", n - 1);
		buf[n - 1] = 0;
		return buf;
	}
	snprintf(buf, n, "%02d:%02d:%02d", t.hour, t.minute, t.second);
	return buf;
}

const char *rtc_date_string(char *buf, uint32_t n) {
	rtc_time_t t;
	if (!buf || n == 0) return buf;
	rtc_read(&t);
	if (!t.valid) {
		strncpy(buf, "--/--/----", n - 1);
		buf[n - 1] = 0;
		return buf;
	}
	snprintf(buf, n, "%02d/%02d/%04d", t.day, t.month, t.year);
	return buf;
}
