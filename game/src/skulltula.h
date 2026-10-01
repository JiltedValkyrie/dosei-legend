#ifndef DOSEI_SKULLTULA_H
#define DOSEI_SKULLTULA_H
#include "gameplay.h"
bool skulltula_init(void *storage,unsigned bytes);
void skulltula_reset(void);
void skulltula_step(const gameplay_input_t *in);
void skulltula_register(void);
void skulltula_collect(void);
bool skulltula_room(unsigned room);
/* Live model position, source animation tick and original size multiplier. */
bool skulltula_body(unsigned i,int32_t p[3],uint16_t *yaw,uint16_t *roll,unsigned *frame,bool *big);
#define SKULLTULA_MAX 3
unsigned skulltula_filter(unsigned i);
#endif
