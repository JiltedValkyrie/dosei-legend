#ifndef DOSEI_DUNGEON_WEBS_H
#define DOSEI_DUNGEON_WEBS_H
#include <stdbool.h>
#include <stdint.h>
void dungeon_webs_reset(void);
bool dungeon_webs_step(unsigned scene,unsigned room);
bool dungeon_webs_land(int32_t x,int32_t y,int32_t z,int32_t fall);
bool dungeon_webs_body(unsigned index,int32_t *x,int32_t *y,int32_t *z,uint16_t *yaw);
unsigned dungeon_webs_count(void);
bool dungeon_webs_burn(const int32_t tip[3]);
unsigned dungeon_walls_count(void);
unsigned dungeon_walls_room_mask(unsigned room);
bool dungeon_walls_body(unsigned i,int32_t *x,int32_t *y,int32_t *z);
#endif
