/* kernel/log.h - registro de arranque y diagnostico (serial + VGA) */
#ifndef SEREOS_LOG_H
#define SEREOS_LOG_H
#include <stdint.h>

#define KLOG_MAX 96

void        klog_init(void);
void        klog(const char *fmt, ...);
void        klog_ok(const char *fmt, ...);
void        klog_fail(const char *fmt, ...);
int         klog_count(void);
const char *klog_line(int i);
uint32_t    klog_entry_tick(int i);
int         klog_errors(void);
/* printf de proposito general: serial + VGA */
int         kprintf(const char *fmt, ...);

#endif
