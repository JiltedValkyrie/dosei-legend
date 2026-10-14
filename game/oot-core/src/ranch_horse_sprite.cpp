/* The source head-overlap collider uses a cheap semantic contact. No pose. */
#include "oot_prelude.h"
#include "ranch_horse_sprite.h"
#include "play_state.h"
#include "z_lib.h"
#include "ranch_horse_anchors.inc"

/* z_horse.c: source child Epona facing helper. */
void Horse_RotateToPoint(Actor* actor, Vec3f* pos, s16 turnAmount) {
    s16 x = Math_Vec3f_Yaw(&actor->world.pos, pos) - actor->world.rot.y;
    if (x > turnAmount) {
        actor->world.rot.y += turnAmount;
    } else if (x < -turnAmount) {
        actor->world.rot.y -= turnAmount;
    } else {
        actor->world.rot.y += x;
    }
    actor->shape.rot.y = actor->world.rot.y;
}

void RanchSprite_Head(PlayState* play, Actor* actor, SkelAnime* clock,
                      ColliderJntSph* head, s32 animation, s32 child) {
    if (animation < 0 || animation >= (child ? 5 : 9)) return;
    int length = (int)clock->animLength;
    int frame = (int)clock->curFrame;
    int sample = length > 0 ? frame * 4 / length : 0;
    if (sample < 0) sample = 0;
    if (sample > 3) sample = 3;
    const s16* local = child ? sRanchChildHead[animation][sample] : sRanchNormalHead[animation][sample];
    /* Samples already include the authored horse scale. Source rotations and
     * yOffset remain actor-owned, and no animation data is read at runtime. */
    f32 s = Math_SinS(actor->shape.rot.x), c = Math_CosS(actor->shape.rot.x);
    f32 y = local[1] * c - local[2] * s;
    f32 z = local[1] * s + local[2] * c;
    s = Math_SinS(actor->shape.rot.y); c = Math_CosS(actor->shape.rot.y);
    Vec3f point = {actor->world.pos.x + local[0] * c + z * s,
                  actor->world.pos.y + y + actor->shape.yOffset * actor->scale.y,
                  actor->world.pos.z + z * c - local[0] * s};
    for (s32 i = 0; i < head->count; ++i) {
        ColliderJntSphElement* element = &head->elements[i];
        element->dim.worldSphere.center = {(s16)(int)point.x, (s16)(int)point.y, (s16)(int)point.z};
        element->dim.worldSphere.radius = (s16)(int)(element->dim.modelSphere.radius * element->dim.scale);
    }
    CollisionCheck_SetOC(play, &play->colChkCtx, &head->base);
}
