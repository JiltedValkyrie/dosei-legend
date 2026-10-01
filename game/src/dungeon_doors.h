#ifndef DOSEI_DUNGEON_DOORS_H
#define DOSEI_DUNGEON_DOORS_H
#include <stdbool.h>
#include <stdint.h>
#include "gameplay.h"
void dungeon_doors_reset(void);
/* 0: unclaimed, 1: opening, 2: barred/refused. */
unsigned dungeon_doors_step(const gameplay_input_t *in);
bool dungeon_doors_prompt(void);
void dungeon_doors_constrain(int32_t *x,int32_t *z,int32_t y);
unsigned dungeon_door_height(unsigned portal);
bool dungeon_door_open(unsigned portal);
#endif
