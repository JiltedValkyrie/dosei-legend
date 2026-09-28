#ifndef DOSEI_WORLD_PROPS_H
#define DOSEI_WORLD_PROPS_H
#include "gameplay.h"
#include "actor_sys.h"
#include "collide.h"
#define WORLD_PROP_ID 0x702
void world_props_reset(void);
void world_props_step(const gameplay_input_t *in);
bool world_props_interact(const gameplay_input_t *in);
bool world_props_carrying(void);
bool world_props_lift_action(void);
void world_props_lift_sync(unsigned int events, int speed_q8, int vy_q8,
                           uint16_t yaw, const int32_t hand[3]);
void world_props_drop_carried(void);
void world_props_grass_drop(unsigned int index, unsigned int random);
void world_props_register(collider_t *storage, unsigned int capacity, const gameplay_input_t *in);
void world_props_collect(void);
bool world_props_present(unsigned int index);
/* OC displacement only; caller applies it through world collision. */
void world_props_displace(int32_t x, int32_t y, int32_t z, unsigned int room, int32_t out[2]);
#endif
