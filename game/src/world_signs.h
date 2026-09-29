#ifndef DOSEI_WORLD_SIGNS_H
#define DOSEI_WORLD_SIGNS_H
#include "gameplay.h"
#include "collide.h"
#define SIGN_PIECE_ID 0x703
void world_signs_reset(void);
void world_signs_step(const gameplay_input_t *in);
unsigned int world_signs_parts(unsigned int index);
unsigned int world_signs_text(const gameplay_input_t *in);
/* Read-only: true when a sign is within reach and in the facing cone. */
bool world_signs_near(void);
void world_signs_register(collider_t *storage, unsigned int capacity, const gameplay_input_t *in);
void world_signs_collect(void);
#endif
