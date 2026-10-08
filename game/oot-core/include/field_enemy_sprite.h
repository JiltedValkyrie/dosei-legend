#ifndef OOT_FIELD_ENEMY_SPRITE_H
#define OOT_FIELD_ENEMY_SPRITE_H
#include "sprite_actor.h"
#include "actor.h"
struct EnSkb;
struct EnPeehat;
struct EnPoField;
Vec3f FieldSprite_Point(Actor*, f32, f32, f32);
void FieldSprite_Stalchild(EnSkb*);
void FieldSprite_Peahat(EnPeehat*);
void FieldSprite_Poe(EnPoField*, bool detach);
void FieldSprite_BreakStart(BodyBreak*, s32, PlayState*);
s32 FieldSprite_BreakStep(Actor*, BodyBreak*, PlayState*, s16);
#endif
