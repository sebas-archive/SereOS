/* drivers/rtc.h - reloj de tiempo real CMOS (Mc146818) */
#ifndef SEREOS_RTC_H
#define SEREOS_RTC_H
#include <stdint.h>

typedef struct {
	int second, minute, hour;
	int day, month, year;
	int weekday;      /* 0 = domingo */
	int valid;
} rtc_time_t;

void rtc_init(void);
int  rtc_available(void);
void rtc_read(rtc_time_t *out);
/* hora formateada "HH:MM:SS"; devuelve buf */
const char *rtc_time_string(char *buf, uint32_t n);
/* fecha formateada "DD/MM/YYYY" */
const char *rtc_date_string(char *buf, uint32_t n);

#endif
