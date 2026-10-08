/* Offline gameplay points, transformed only by the whole actor. */
#include "oot_prelude.h"
#include "water_enemy_sprite.h"
#include "array_count.h"
#include "overlays/actors/ovl_En_Tite/z_en_tite.h"
#include "overlays/actors/ovl_En_Firefly/z_en_firefly.h"
#include "overlays/actors/ovl_En_Ny/z_en_ny.h"
struct FieldAnchorClip { AnimationHeader* animation; u16 frames, points; const s16* xyz; };
#include "../../build/oot-core/water_anchors.inc"

static Vec3f water_anchor(Actor* actor, SkelAnime* skel, unsigned point) {
    for (unsigned i=0; i<ARRAY_COUNT(field_anchor_clips); ++i) {
        const FieldAnchorClip& clip=field_anchor_clips[i];
        if (clip.animation!=skel->animation || point>=clip.points) continue;
        int frame=(int)skel->curFrame;
        if (frame<0) frame=0;
        if (frame>=clip.frames) frame=clip.frames-1;
        const s16* xyz=clip.xyz+(frame*clip.points+point)*3;
        return FieldSprite_Point(actor,xyz[0],xyz[1],xyz[2]);
    }
    return actor->world.pos; /* Every referenced animation is baked before admission. */
}

/* Source Collider_UpdateSpheres(0) under the actor matrix, without Draw. */
static void water_sphere(Actor* actor, ColliderJntSphElement* element) {
    Vec3f p=FieldSprite_Point(actor,element->dim.modelSphere.center.x,
                             element->dim.modelSphere.center.y,element->dim.modelSphere.center.z);
    element->dim.worldSphere.center={(s16)(int)p.x,(s16)(int)p.y,(s16)(int)p.z};
    element->dim.worldSphere.radius=(s16)(int)(element->dim.modelSphere.radius*element->dim.scale);
}

void WaterSprite_Tektite(EnTite* actor) {
    actor->backRightFootPos=water_anchor(&actor->actor,&actor->skelAnime,0);
    actor->frontRightFootPos=water_anchor(&actor->actor,&actor->skelAnime,1);
    actor->backLeftFootPos=water_anchor(&actor->actor,&actor->skelAnime,2);
    actor->frontLeftFootPos=water_anchor(&actor->actor,&actor->skelAnime,3);
    water_sphere(&actor->actor,&actor->collider.elements[0]);
}

Vec3f WaterSprite_KeeseAnchor(EnFirefly* actor, s32 limb) {
    unsigned point=limb==KEESE_LIMB_LEFT_WING_END ? 0 :
                   limb==KEESE_LIMB_RIGHT_WING_END_ROOT ? 1 : 2;
    return water_anchor(&actor->actor,&actor->skelAnime,point);
}

void WaterSprite_Spikes(EnNy* actor) {
    water_sphere(&actor->actor,&actor->collider.elements[0]);
}
