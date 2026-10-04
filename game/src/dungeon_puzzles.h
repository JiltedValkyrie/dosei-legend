#ifndef DOSEI_DUNGEON_PUZZLES_H
#define DOSEI_DUNGEON_PUZZLES_H
#include <stdbool.h>
#include <stdint.h>
#include "gameplay.h"
void dungeon_puzzles_reset(void);
bool dungeon_puzzles_sync(unsigned scene,unsigned room);
void dungeon_puzzles_step(const gameplay_input_t *in);
bool dungeon_puzzles_shot(const int32_t from[3],int32_t to[3]);
unsigned dungeon_puzzles_count(void);
uint32_t dungeon_puzzles_models(unsigned room);
/* Model ID + 1, zero when hidden. */
unsigned dungeon_puzzles_body(unsigned i,int32_t *x,int32_t *y,int32_t *z,uint16_t *yaw,uint16_t *roll);
void dungeon_puzzles_register(void);
#endif
