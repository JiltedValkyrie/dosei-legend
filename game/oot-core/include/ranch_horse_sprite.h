#ifndef RANCH_HORSE_SPRITE_H
#define RANCH_HORSE_SPRITE_H
#include "sprite_actor.h"
#include "collision_check.h"
/* One source animation clock. Skin matrices and vertex tables stay offline. */
typedef struct RanchHorseSprite { SkelAnime skelAnime; } RanchHorseSprite;
static inline void RanchSprite_Init(PlayState* play, RanchHorseSprite* skin,
                                    SkeletonHeader* skeleton, AnimationHeader* animation) {
    OotCore_SpriteInit(play, &skin->skelAnime, skeleton, animation, NULL, NULL, 0);
}
static inline void RanchSprite_Free(PlayState*, RanchHorseSprite*) { }
void RanchSprite_Head(PlayState*, Actor*, SkelAnime*, ColliderJntSph*, s32 animation, s32 child);
#endif
