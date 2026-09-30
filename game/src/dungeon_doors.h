#ifndef DOSEI_DUNGEON_DOORS_H
#define DOSEI_DUNGEON_DOORS_H
#include <stdbool.h>
#include <stdint.h>
#include "gameplay.h"
void dungeon_doors_reset(void);
bool dungeon_doors_step(const gameplay_input_t *in);
void dungeon_doors_constrain(int32_t *x,int32_t *z,int32_t y);
unsigned dungeon_door_height(unsigned portal);
bool dungeon_door_open(unsigned portal);
#endif
