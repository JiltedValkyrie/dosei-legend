#ifndef TEST_YAUL_H
#define TEST_YAUL_H
#include <stdint.h>
#include <stdbool.h>
uint8_t cpu_intc_mask_get(void);
void cpu_intc_mask_set(uint8_t mask);
#endif
