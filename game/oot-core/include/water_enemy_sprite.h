#ifndef OOT_WATER_ENEMY_SPRITE_H
#define OOT_WATER_ENEMY_SPRITE_H
#include "field_enemy_sprite.h"
struct EnTite;
struct EnFirefly;
struct EnNy;
void WaterSprite_Tektite(EnTite*);
Vec3f WaterSprite_KeeseAnchor(EnFirefly*, s32 limb);
void WaterSprite_Spikes(EnNy*);
#endif
