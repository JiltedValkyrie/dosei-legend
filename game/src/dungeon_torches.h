#ifndef DOSEI_DUNGEON_TORCHES_H
#define DOSEI_DUNGEON_TORCHES_H
#include <stdbool.h>
#include <stdint.h>
void dungeon_torches_reset(void);
void dungeon_torches_step(unsigned scene,unsigned room,const int32_t *stick_tip);
unsigned dungeon_torches_count(void);
unsigned dungeon_torches_room_models(unsigned room);
/* Returns model type + 1, or zero for a nonresident torch. */
unsigned dungeon_torches_body(unsigned i,int32_t *x,int32_t *y,int32_t *z,uint16_t *yaw,bool *lit);
#endif
