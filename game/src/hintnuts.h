#ifndef DOSEI_HINTNUTS_H
#define DOSEI_HINTNUTS_H
#include "gameplay.h"
#define HINTNUTS_MAX 3
#define HINTNUTS_BALLS 6
bool hintnuts_init(void *storage,unsigned bytes);
void hintnuts_reset(void);
void hintnuts_step(const gameplay_input_t *in);
void hintnuts_register(void);
void hintnuts_collect(void);
bool hintnuts_room(unsigned room);
bool hintnuts_body(unsigned i,int32_t p[3],uint16_t *yaw,unsigned *frame);
bool hintnuts_flower(unsigned i,int32_t p[3],uint16_t *yaw);
bool hintnuts_ball(unsigned i,int32_t p[3],uint16_t *roll);
unsigned hintnuts_filter(unsigned i);
#endif
