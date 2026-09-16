#ifndef TEST_FRT_H
#define TEST_FRT_H
#include <stdint.h>
#define CPU_FRT_CLOCK_DIV_128 2
void cpu_frt_init(uint8_t divisor);
void cpu_frt_ovi_set(void (*handler)(void));
#endif
