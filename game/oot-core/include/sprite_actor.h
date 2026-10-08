#ifndef OOT_CORE_SPRITE_ACTOR_H
#define OOT_CORE_SPRITE_ACTOR_H
#include "animation.h"

/* NPCs retain an animation clock for action transitions, never a pose. */
static inline bool OotCore_IsSprite(const SkelAnime* s) {
    return s->initFlags == 0x53 && s->jointTable == NULL && s->morphTable == NULL;
}
void OotCore_SpriteInitFlex(struct PlayState*, SkelAnime*, FlexSkeletonHeader*,
                           AnimationHeader*, Vec3s*, Vec3s*, s32);
void OotCore_SpriteInit(struct PlayState*, SkelAnime*, SkeletonHeader*,
                       AnimationHeader*, Vec3s*, Vec3s*, s32);
void OotCore_SpriteChange(SkelAnime*, AnimationHeader*, f32, f32, f32, u8);
s32 OotCore_SpriteUpdate(SkelAnime*);
#endif
