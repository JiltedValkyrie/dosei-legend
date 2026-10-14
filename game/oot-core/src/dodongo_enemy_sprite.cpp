/* Scene-pack contacts from offline semantic samples; never skeletal state. */
#include "oot_prelude.h"
#include "dodongo_enemy_sprite.h"
#include "array_count.h"
#include "z_lib.h"
#include "z_math.h"
#include "play_state.h"
#include "overlays/actors/ovl_En_Dodojr/z_en_dodojr.h"
#include "overlays/actors/ovl_En_Dodongo/z_en_dodongo.h"
#include "overlays/actors/ovl_En_Am/z_en_am.h"
#include "overlays/actors/ovl_En_Zf/z_en_zf.h"
#include "overlays/actors/ovl_En_Vm/z_en_vm.h"
#include "overlays/actors/ovl_En_Sw/z_en_sw.h"
#include "overlays/actors/ovl_En_Wf/z_en_wf.h"

struct DodongoAnchorClip {
    AnimationHeader* animation;
    const void* skeleton;
    u16 frames, samples, points;
    const u16* times;
    const s16* xyz;
};
#ifndef OOT_DODONGO_ANCHORS
#define OOT_DODONGO_ANCHORS "../../build/oot-core/dodongo_anchors.inc"
#endif
#include OOT_DODONGO_ANCHORS

static const DodongoAnchorClip* sprite_clip(SkelAnime* skel) {
    for (unsigned i = 0; i < ARRAY_COUNT(dodongo_anchor_clips); ++i) {
        const DodongoAnchorClip* clip = &dodongo_anchor_clips[i];
        if (clip->animation == skel->animation && clip->skeleton == skel->skeleton)
            return clip;
    }
    return NULL; /* Complete archive/contact admission is checked offline. */
}

static Vec3f sprite_local(const DodongoAnchorClip* clip, SkelAnime* skel, unsigned point) {
    if (!clip || point >= clip->points) return {0, 0, 0};
    int frame = (int)skel->curFrame;
    if (frame < 0) frame = 0;
    if (frame >= clip->frames) frame = clip->frames - 1;
    unsigned high = 0;
    while (high + 1 < clip->samples && clip->times[high] < frame) ++high;
    unsigned low = high ? high - 1 : 0;
    int span = clip->times[high] - clip->times[low];
    int offset = frame - clip->times[low];
    const s16* a = clip->xyz + (low * clip->points + point) * 3;
    const s16* b = clip->xyz + (high * clip->points + point) * 3;
    /* s16 endpoint delta * a source clip frame span fits s32. */
    return {a[0] + (span ? (b[0] - a[0]) * offset / span : 0),
            a[1] + (span ? (b[1] - a[1]) * offset / span : 0),
            a[2] + (span ? (b[2] - a[2]) * offset / span : 0)};
}

static Vec3f sprite_world(Actor* actor, Vec3f p) {
    p.x *= actor->scale.x;
    p.y = (p.y + actor->shape.yOffset) * actor->scale.y;
    p.z *= actor->scale.z;
    f32 s = Math_SinS(actor->shape.rot.z), c = Math_CosS(actor->shape.rot.z);
    f32 x = p.x * c - p.y * s;
    p.y = p.x * s + p.y * c; p.x = x;
    s = Math_SinS(actor->shape.rot.x); c = Math_CosS(actor->shape.rot.x);
    f32 y = p.y * c - p.z * s;
    p.z = p.y * s + p.z * c; p.y = y;
    s = Math_SinS(actor->shape.rot.y); c = Math_CosS(actor->shape.rot.y);
    return {actor->world.pos.x + p.x * c + p.z * s,
            actor->world.pos.y + p.y,
            actor->world.pos.z + p.z * c - p.x * s};
}

static Vec3f sprite_point(Actor* actor, SkelAnime* skel,
                         const DodongoAnchorClip* clip, unsigned point) {
    return sprite_world(actor, sprite_local(clip, skel, point));
}

static void sprite_sphere(ColliderJntSphElement* element, Vec3f point) {
    element->dim.worldSphere.center = {(s16)(int)point.x, (s16)(int)point.y, (s16)(int)point.z};
    element->dim.worldSphere.radius = (s16)(int)(element->dim.modelSphere.radius * element->dim.scale);
}

void DodongoSprite_Wolfos(EnWf* actor) {
    const DodongoAnchorClip* clip = sprite_clip(&actor->skelAnime);
    for(unsigned i=0;i<4;++i)
        sprite_sphere(&actor->colliderJntSph.elements[i],sprite_point(&actor->actor,&actor->skelAnime,clip,i));
    Vec3f tail=sprite_point(&actor->actor,&actor->skelAnime,clip,4);
    actor->tailColliderCylinder.dim.pos={(s16)(int)tail.x,(s16)(int)tail.y,(s16)(int)tail.z};
    if(actor->fireTimer || actor->actor.colorFilterTimer){
        /* Flames use combat bounds; no ten-limb cosmetic pose track. */
        static const u8 anchors[]={2,0,1,3,3,4,0,3,0,1};
        for(unsigned i=0;i<10;++i){
            Vec3f p=sprite_point(&actor->actor,&actor->skelAnime,clip,anchors[i]);
            actor->bodyPartsPos[i]={(s16)(int)p.x,(s16)(int)p.y,(s16)(int)p.z};
        }
    }
}

static Vec3f beamos_point(EnVm* actor, Vec3f p) {
    /* Scalar beam orientation, not a limb pose. Source aim owns these angles. */
    f32 s = Math_SinS(actor->beamRot.x), c = Math_CosS(actor->beamRot.x);
    f32 y = p.y * c - p.z * s;
    p.z = p.y * s + p.z * c; p.y = y;
    s = Math_SinS(actor->actor.shape.rot.y + actor->headRotY);
    c = Math_CosS(actor->actor.shape.rot.y + actor->headRotY);
    return {actor->beamPos1.x + p.x * c + p.z * s, actor->beamPos1.y + p.y,
            actor->beamPos1.z + p.z * c - p.x * s};
}

void DodongoSprite_Beamos(EnVm* actor, PlayState* play) {
    const DodongoAnchorClip* clip = sprite_clip(&actor->skelAnime);
    actor->beamPos1 = sprite_point(&actor->actor, &actor->skelAnime, clip, 0);
    f32 scale = actor->actor.scale.y;
    actor->beamPos2 = beamos_point(actor, {0, 0, 1600 * scale});
    if (actor->unk_260 >= 3) {
        /* Multiply in world-unit order: source's intermediate model-space
         * ray can exceed Q16 range even though its world endpoint fits. */
        f32 distance = (actor->beamScale.z + 500) * scale * (scale * 10000);
        actor->beamPos3 = beamos_point(actor, {0, 0, distance});
        CollisionPoly* poly = NULL;
        Vec3f hit;
        s32 bgId;
        if (BgCheck_EntityLineTest1(&play->colCtx, &actor->beamPos1, &actor->beamPos3,
                                   &hit, &poly, true, true, false, true, &bgId)) {
            actor->beamScale.z = Math_Vec3f_DistXYZ(&actor->beamPos1, &hit) - 5;
            actor->unk_260 = 4;
            actor->beamPos3 = hit;
        }
        if (actor->beamScale.z != 0) {
            distance = Math_Vec3f_DistXYZ(&actor->beamPos1, &actor->beamPos3) *
                       (scale * (scale > FXL(0.01) ? 70 : 100));
            Vec3f quad[4] = {beamos_point(actor, {-500 * scale, 0, distance}),
                            beamos_point(actor, {500 * scale, 0, distance}),
                            beamos_point(actor, {-500 * scale, 0, 0}),
                            beamos_point(actor, {500 * scale, 0, 0})};
            Collider_SetQuadVertices(&actor->colliderQuad1, &quad[0], &quad[1], &quad[2], &quad[3]);
        }
    }
    Vec3f eye[4] = {beamos_point(actor, {1000 * scale, -700 * scale, 2000 * scale}),
                   beamos_point(actor, {1000 * scale, 700 * scale, 2000 * scale}),
                   beamos_point(actor, {-1000 * scale, -700 * scale, 1500 * scale}),
                   beamos_point(actor, {-1000 * scale, 700 * scale, 1500 * scale})};
    Collider_SetQuadVertices(&actor->colliderQuad2, &eye[0], &eye[1], &eye[2], &eye[3]);
}

void DodongoSprite_Skulltula(EnSw* actor) {
    const DodongoAnchorClip* clip = sprite_clip(&actor->skelAnime);
    Vec3f* points[] = {&actor->unk_454, &actor->unk_460, &actor->unk_46C, &actor->unk_478,
                      &actor->unk_484, &actor->actor.focus.pos};
    Vec3f center = {};
    for (unsigned i = 0; i < 7; ++i) {
        Vec3f p = sprite_local(clip, &actor->skelAnime, i);
        if ((actor->actor.params >> 13) & 7) {
            if (actor->actor.colChkInfo.health) p.z += 200;
            const f32 s = Math_SinS(-14564), c = Math_CosS(-14564); /* source -80 degrees */
            f32 y = p.y * c - p.z * s;
            p.z = p.y * s + p.z * c; p.y = y;
        }
        p = sprite_world(&actor->actor, p);
        if (i < 6) *points[i] = p;
        else center = p;
    }
    sprite_sphere(&actor->collider.elements[0], center);
}

void DodongoSprite_Baby(EnDodojr* actor) {
    const DodongoAnchorClip* clip = sprite_clip(&actor->skelAnime);
    Vec3f point = sprite_local(clip, &actor->skelAnime, 0);
    /* Source root swelling changes its bomb mouth, independent of skeletons. */
    point.x *= actor->rootScale / 2 + 1;
    point.y *= actor->rootScale + 1;
    point.z *= actor->rootScale / 2 + 1;
    actor->headPos = sprite_world(&actor->actor, point);
}

void DodongoSprite_Dodongo(EnDodongo* actor) {
    const DodongoAnchorClip* clip = sprite_clip(&actor->skelAnime);
    for (unsigned i = 0; i < 6; ++i)
        sprite_sphere(&actor->bodyCollider.elements[i], sprite_point(&actor->actor, &actor->skelAnime, clip, i));
    for (unsigned i = 0; i < 3; ++i) {
        Vec3f a = sprite_point(&actor->actor, &actor->skelAnime, clip, 6 + i * 3);
        Vec3f b = sprite_point(&actor->actor, &actor->skelAnime, clip, 7 + i * 3);
        Vec3f c = sprite_point(&actor->actor, &actor->skelAnime, clip, 8 + i * 3);
        Collider_SetTrisVertices(&actor->colliderHard, i, &a, &b, &c);
    }
    actor->mouthPos = sprite_point(&actor->actor, &actor->skelAnime, clip, 15);
    actor->headPos = sprite_point(&actor->actor, &actor->skelAnime, clip, 16);
    actor->leftFootPos = sprite_point(&actor->actor, &actor->skelAnime, clip, 3);
    actor->rightFootPos = sprite_point(&actor->actor, &actor->skelAnime, clip, 4);
    Vec3f quad[4];
    for (unsigned i = 0; i < 4; ++i) quad[i] = sprite_point(&actor->actor, &actor->skelAnime, clip, 17 + i);
    Collider_SetQuadVertices(&actor->colliderAT, &quad[0], &quad[1], &quad[2], &quad[3]);
    if (actor->iceTimer)
        for (unsigned i = 0; i < 9; ++i) {
            /* Cosmetic ice uses existing body/head bounds, no extra pose data. */
            static const u8 point[] = {16, 2, 1, 0, 0, 3, 4, 3, 4};
            actor->icePos[i] = sprite_point(&actor->actor, &actor->skelAnime, clip, point[i]);
        }
}

void DodongoSprite_Armos(EnAm* actor) {
    if (actor->unk_264 == 0 || actor->dyna.actor.params == 0) return;
    const DodongoAnchorClip* clip = sprite_clip(&actor->skelAnime);
    Vec3f quad[4];
    for (unsigned i = 0; i < 4; ++i)
        quad[i] = sprite_point(&actor->dyna.actor, &actor->skelAnime, clip, i);
    Collider_SetQuadVertices(&actor->hitCollider, &quad[0], &quad[1], &quad[2], &quad[3]);
}

void DodongoSprite_Lizalfos(EnZf* actor) {
    const DodongoAnchorClip* clip = sprite_clip(&actor->skelAnime);
    if (clip) { /* Source only registers sword AT during gZfSlashAnim. */
        Vec3f quad[4];
        for (unsigned i = 0; i < 4; ++i) quad[i] = sprite_point(&actor->actor, &actor->skelAnime, clip, i);
        Collider_SetQuadVertices(&actor->swordCollider, &quad[0], &quad[1], &quad[2], &quad[3]);
    }
    actor->leftFootPos = sprite_world(&actor->actor, {dodongo_zf_passive[0][0], dodongo_zf_passive[0][1], dodongo_zf_passive[0][2]});
    actor->rightFootPos = sprite_world(&actor->actor, {dodongo_zf_passive[1][0], dodongo_zf_passive[1][1], dodongo_zf_passive[1][2]});
    actor->actor.shape.feetPos[0] = actor->leftFootPos;
    actor->actor.shape.feetPos[1] = actor->rightFootPos;
    if (actor->frozenTimer)
        for (unsigned i = 0; i < 9; ++i) {
            const s16* point = dodongo_zf_passive[i + 2];
            actor->bodyPartsPos[i] = sprite_world(&actor->actor, {point[0], point[1], point[2]});
        }
}
