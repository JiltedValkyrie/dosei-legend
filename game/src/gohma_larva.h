#ifndef DOSEI_GOHMA_LARVA_H
#define DOSEI_GOHMA_LARVA_H
#include "gameplay.h"
#define GOHMA_LARVA_MAX 3
bool gohma_larva_init(void *memory,unsigned bytes);
void gohma_larva_reset(void);
void gohma_larva_step(const gameplay_input_t *in);
void gohma_larva_register(void);
void gohma_larva_collect(void);
bool gohma_larva_room(unsigned scene,unsigned room);
/* Boss child slots 0..2. False while that child is still live. */
bool gohma_larva_spawn(unsigned slot,int32_t x,int32_t y,int32_t z,uint16_t yaw);
bool gohma_larva_alive(unsigned slot);
unsigned gohma_larva_body(unsigned i,int32_t p[3],uint16_t *yaw,unsigned *frame,int32_t *scale);
unsigned gohma_larva_filter(unsigned i);
#endif
