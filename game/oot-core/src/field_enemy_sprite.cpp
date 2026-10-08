/* Scene-pack sprite gameplay: sampled attachment points, never skeletal poses. */
#include "oot_prelude.h"
#include "field_enemy_sprite.h"
#include "array_count.h"
#include "play_state.h"
#include "z_lib.h"
#include "z_math.h"
#include "overlays/actors/ovl_En_Skb/z_en_skb.h"
#include "overlays/actors/ovl_En_Peehat/z_en_peehat.h"
#include "overlays/actors/ovl_En_Po_Field/z_en_po_field.h"

struct FieldAnchorClip { AnimationHeader* animation; u16 frames, points; const s16* xyz; };
#include "../../build/oot-core/field_anchors.inc"

static Vec3f field_point(Actor* a, f32 x, f32 y, f32 z) {
    x *= a->scale.x;
    y = (y + a->shape.yOffset) * a->scale.y;
    z *= a->scale.z;
    f32 s = Math_SinS(a->shape.rot.z), c = Math_CosS(a->shape.rot.z);
    f32 t = x * c - y * s;
    y = x * s + y * c; x = t;
    s = Math_SinS(a->shape.rot.x); c = Math_CosS(a->shape.rot.x);
    t = y * c - z * s; z = y * s + z * c; y = t;
    s = Math_SinS(a->shape.rot.y); c = Math_CosS(a->shape.rot.y);
    return {a->world.pos.x + x * c + z * s, a->world.pos.y + y,
            a->world.pos.z + z * c - x * s};
}

static Vec3f field_anchor(Actor* a, SkelAnime* skel, unsigned point) {
    for (unsigned i = 0; i < ARRAY_COUNT(field_anchor_clips); ++i) {
        const FieldAnchorClip& clip = field_anchor_clips[i];
        if (clip.animation != skel->animation || point >= clip.points) continue;
        int frame = (int)skel->curFrame;
        if (frame < 0) frame = 0;
        if (frame >= clip.frames) frame = clip.frames - 1;
        const s16* p = clip.xyz + (frame * clip.points + point) * 3;
        return field_point(a, p[0], p[1], p[2]);
    }
    return a->world.pos; /* Build validation requires every actor clip. */
}

Vec3f FieldSprite_Point(Actor* actor, f32 x, f32 y, f32 z) {
    return field_point(actor, x, y, z);
}

static void field_sphere(ColliderJntSphElement* element, Vec3f p) {
    element->dim.worldSphere.center = {(s16)(int)p.x, (s16)(int)p.y, (s16)(int)p.z};
    element->dim.worldSphere.radius = (s16)(int)(element->dim.modelSphere.radius * element->dim.scale);
}

void FieldSprite_Stalchild(EnSkb* a) {
    for (unsigned i = 0; i < 2; ++i)
        field_sphere(&a->collider.elements[i], field_anchor(&a->actor, &a->skelAnime, i));
}

void FieldSprite_Peahat(EnPeehat* a) {
    field_sphere(&a->colliderJntSph.elements[0], field_anchor(&a->actor, &a->skelAnime, 0));
    const f32 s = Math_SinS(a->bladeRot), c = Math_CosS(a->bladeRot);
    a->bladeTip[0] = field_point(&a->actor, 5500 * s, 0, 5500 * c);
    a->bladeTip[1] = field_point(&a->actor, -5500 * s, 0, -5500 * c);
    Vec3f p[4] = {field_point(&a->actor, -4500, 0, 0), field_point(&a->actor, 0, 0, -4500),
                  field_point(&a->actor, 0, 0, 4500), field_point(&a->actor, 4500, 0, 0)};
    Collider_SetQuadVertices(&a->colliderQuad, &p[0], &p[1], &p[2], &p[3]);
}

void FieldSprite_Poe(EnPoField* a, bool detach) {
    Vec3f lantern = field_anchor(&a->actor, &a->skelAnime, 0);
    if (detach) a->actor.world.pos = lantern;
    Lights_PointGlowSetInfo(&a->lightInfo, (s16)(int)lantern.x, (s16)(int)lantern.y,
                            (s16)(int)lantern.z, a->soulColor.r, a->soulColor.g,
                            a->soulColor.b, a->soulColor.a * 200 / 255);
}

void FieldSprite_BreakStart(BodyBreak* b, s32 count, PlayState*) {
    /* Two update ticks replace draw-collection readiness. No En_Part meshes,
     * matrix arrays or allocator ownership; source death/drop actions follow. */
    b->count = 0;
    b->val = count;
}

s32 FieldSprite_BreakStep(Actor*, BodyBreak* b, PlayState*, s16) {
    if (b->count < 2) ++b->count;
    return b->count >= 2;
}
