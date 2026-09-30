#ifndef DOSEI_DUNGEON_WEBS_H
#define DOSEI_DUNGEON_WEBS_H
#include <stdbool.h>
#include <stdint.h>
void dungeon_webs_reset(void);
bool dungeon_webs_step(unsigned scene,unsigned room);
bool dungeon_webs_land(int32_t x,int32_t y,int32_t z,int32_t fall);
bool dungeon_webs_body(unsigned index,int32_t *x,int32_t *y,int32_t *z,uint16_t *yaw);
unsigned dungeon_webs_count(void);
#endif
