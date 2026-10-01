#ifndef DOSEI_WALL_SKULL_H
#define DOSEI_WALL_SKULL_H
#include "gameplay.h"
#define WALL_SKULL_MAX 3
bool wall_skull_init(void *storage,unsigned bytes);
void wall_skull_reset(void);
void wall_skull_step(const gameplay_input_t *in);
void wall_skull_register(void);
void wall_skull_collect(void);
unsigned wall_skull_models(unsigned room);
unsigned wall_skull_body(unsigned i,int32_t p[3],uint16_t *yaw,uint16_t *roll,unsigned *frame);
unsigned wall_skull_filter(unsigned i);
#endif
