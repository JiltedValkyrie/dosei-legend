/*
 * Phase 2 draw shim. The real draw code runs: Actor_Draw (lights, the actor
 * matrix, segment 6, actor->draw) writes N64 display lists into scratch
 * buffers. Nothing executes them. This file walks what each actor wrote and
 * turns every call of a placeholder display list (the one-word stand-ins for
 * object/gameplay_keep DLs, oot_core_import.py) into a draw item: which
 * prebuilt Saturn mesh, and the modelview transform at the call. The C side
 * draws the items with its existing mesh renderer.
 *
 * Walker scope (F3DEX2): G_MTX (modelview load/mul, push), G_POPMTX, G_DL
 * (call/branch into display lists the draw code built at run time), G_ENDDL,
 * G_MOVEWORD segment (gSPSegment), G_TEXRECT's two extra words. Everything
 * else (render modes, colours, textures) is skipped: the Saturn mesh carries
 * its own. APPROXIMATE: skinned (flex) limbs are drawn rigidly per limb.
 *
 * Transform: decomposed into translate * Ry * Rx * Rz * scale (the order of
 * Matrix_SetTranslateRotateYXZ + Matrix_Scale), so the C side can rebuild it
 * with SGL's own rotate calls instead of a raw matrix layout.
 */
#include "oot_prelude.h"
#include "ultra64.h"
#include "actor.h"
#include "gfx.h"
#include "play_state.h"
#include "segmented_address.h"
#include "skin_matrix.h"
#include "sys_math.h"
#include "sys_matrix.h"
#include "oot_core_api.h"
#include "array_count.h"
#include "z_math.h"

extern PlayState* gOotCorePlay;
void Actor_Draw(PlayState* play, Actor* actor); /* z_actor.c */
GraphicsContext* OotCore_GfxCtx(void);

/* gameplay_keep placeholders (bridge_assets.cpp, section .keep_ph, sorted by
 * the importer): index = (address - start) / 8. */
extern "C" u64 oot_keep_ph_start[], oot_keep_ph_end[];

/* Object data blob header (oot-core/object.ld .ph_head): placeholders follow
 * it, so a DL address inside [base + 8, base + 8 + count * 8) is one. */
typedef struct OotObjectHead {
    u32 magic; /* 'OOB1' */
    u32 ph_count;
} OotObjectHead;
#define OOT_OBJECT_MAGIC 0x4F4F4231u

/* Actor ids drawn through this shim. Everything else is still drawn by the
 * C renderer (npc_draw, kokiri_sgl, world_props) or not at all. */
static const s16 sGenericDrawIds[] = {
#include "../../build/oot-core/generic_draw_ids.h"
};

static OotCoreDrawItem sItems[OOT_CORE_DRAW_ITEMS_MAX];
static s32 sItemCount;
static u32 sDropped; /* items over the buffer this frame */

static s32 Draw_IsGeneric(s16 id) {
    u32 i;

    for (i = 0; i < ARRAY_COUNT(sGenericDrawIds); i++) {
        if (sGenericDrawIds[i] == id) {
            return true;
        }
    }
    return false;
}

#define WALK_MTX_DEPTH 12
#define WALK_DL_DEPTH 10

typedef struct Walker {
    uintptr_t segments[16];
    MtxF stack[WALK_MTX_DEPTH];
    s32 depth; /* stack[depth] = current modelview */
    s16 actorId;
    u8 xlu;
} Walker;

static uintptr_t Walk_Resolve(Walker* w, u32 addr) {
    u32 seg = (addr >> 24) & 0xF;

    /* gSPSegment values hold full Saturn addresses; any address is passed
     * through the table like the RSP does (segment 2 = cart identity). */
    return w->segments[seg] + (addr & 0x00FFFFFF);
}

static s32 Walk_InArena(uintptr_t p) {
    GraphicsContext* g = OotCore_GfxCtx();
    uintptr_t opa0 = (uintptr_t)g->polyOpa.start, opa1 = opa0 + g->polyOpa.size;
    uintptr_t ovl0 = (uintptr_t)g->overlay.start, ovl1 = ovl0 + g->overlay.size;

    return (p >= opa0 && p < opa1) || (p >= ovl0 && p < ovl1);
}

static s32 Draw_Key(uintptr_t p, u16* kind, u16* object, u16* index) {
    PlayState* play = gOotCorePlay;
    s32 i;

    if (p >= (uintptr_t)oot_keep_ph_start && p < (uintptr_t)oot_keep_ph_end) {
        *kind = OOT_CORE_DRAW_KEEP;
        *object = 0;
        *index = (u16)((p - (uintptr_t)oot_keep_ph_start) / 8);
        return true;
    }
    for (i = 1; i < play->objectCtx.numEntries; i++) {
        uintptr_t base = (uintptr_t)play->objectCtx.slots[i].segment;
        const OotObjectHead* head = (const OotObjectHead*)base;

        if (base == 0 || head->magic != OOT_OBJECT_MAGIC) {
            continue;
        }
        if (p >= base + sizeof(OotObjectHead) && p < base + sizeof(OotObjectHead) + head->ph_count * 8) {
            *kind = OOT_CORE_DRAW_OBJECT;
            *object = (u16)ABS(play->objectCtx.slots[i].id);
            *index = (u16)((p - base - sizeof(OotObjectHead)) / 8);
            return true;
        }
    }
    return false;
}

static void Draw_Emit(Walker* w, uintptr_t p) {
    OotCoreDrawItem* it;
    MtxF* m = &w->stack[w->depth];
    u16 kind, object, index;
    f32 cx, cy, cz, sx, sy, sz, r12;

    if (!Draw_Key(p, &kind, &object, &index)) {
        return; /* not a placeholder (e.g. gEmptyDL): nothing to draw */
    }
    if (sItemCount >= OOT_CORE_DRAW_ITEMS_MAX) {
        sDropped++;
        return;
    }
    it = &sItems[sItemCount++];
    it->kind = kind;
    it->object = object;
    it->index = index;
    it->actor = w->actorId;
    it->xlu = w->xlu;
    it->x = (s32)m->mf[3][0];
    it->y = (s32)m->mf[3][1];
    it->z = (s32)m->mf[3][2];
    /* Column scales (Matrix_Scale scales columns), then Euler YXZ of the
     * normalised rotation: R = Ry * Rx * Rz. */
    sx = sqrtf(SQ(m->mf[0][0]) + SQ(m->mf[0][1]) + SQ(m->mf[0][2]));
    sy = sqrtf(SQ(m->mf[1][0]) + SQ(m->mf[1][1]) + SQ(m->mf[1][2]));
    sz = sqrtf(SQ(m->mf[2][0]) + SQ(m->mf[2][1]) + SQ(m->mf[2][2]));
    it->sx = (s32)(sx * 65536.0f);
    it->sy = (s32)(sy * 65536.0f);
    it->sz = (s32)(sz * 65536.0f);
    if (sx == 0.0f || sy == 0.0f || sz == 0.0f) {
        it->yaw = it->pitch = it->roll = 0;
        return;
    }
    r12 = m->mf[2][1] / sz;                                   /* -sin(x) */
    cx = sqrtf(SQ(m->mf[0][1] / sx) + SQ(m->mf[1][1] / sy));        /* cos(x) >= 0 */
    it->pitch = Math_Atan2S(cx, -r12);
    if (cx > 0.001f) {
        it->yaw = Math_Atan2S(m->mf[2][2] / sz, m->mf[2][0] / sz);  /* atan2(R02, R22) */
        it->roll = Math_Atan2S(m->mf[1][1] / sy, m->mf[0][1] / sx); /* atan2(R10, R11) */
    } else {
        /* Gimbal: fold roll into yaw. */
        cy = m->mf[0][0] / sx;
        cz = m->mf[0][2] / sx;
        it->yaw = Math_Atan2S(cy, -cz);
        it->roll = 0;
    }
}

static void Walk_List(Walker* w, const Gfx* g, s32 dlDepth) {
    s32 guard = 4096;

    while (guard-- > 0) {
        u32 w0 = g->words.w0;
        u32 w1 = g->words.w1;
        u8 op = (u8)(w0 >> 24);

        g++;
        switch (op) {
            case G_ENDDL:
                return;
            case G_DL: {
                uintptr_t p = Walk_Resolve(w, w1);
                s32 branch = ((w0 >> 16) & 0xFF) != 0;

                if (Walk_InArena(p)) {
                    if (branch) {
                        g = (const Gfx*)p;
                        continue;
                    }
                    if (dlDepth < WALK_DL_DEPTH) {
                        Walk_List(w, (const Gfx*)p, dlDepth + 1);
                    }
                } else {
                    Draw_Emit(w, p);
                    if (branch) {
                        return;
                    }
                }
                break;
            }
            case G_MTX: {
                u8 params = (u8)(w0 & 0xFF) ^ G_MTX_PUSH;
                MtxF loaded;

                if (params & G_MTX_PROJECTION) {
                    break;
                }
                Matrix_MtxToMtxF((Mtx*)Walk_Resolve(w, w1), &loaded);
                if ((params & G_MTX_PUSH) && w->depth + 1 < WALK_MTX_DEPTH) {
                    w->stack[w->depth + 1] = w->stack[w->depth];
                    w->depth++;
                }
                if (params & G_MTX_LOAD) {
                    w->stack[w->depth] = loaded;
                } else {
                    MtxF cur = w->stack[w->depth];
                    SkinMatrix_MtxFMtxFMult(&cur, &loaded, &w->stack[w->depth]);
                }
                break;
            }
            case G_POPMTX: {
                s32 n = (s32)(w1 / 64);

                w->depth = (w->depth > n) ? w->depth - n : 0;
                break;
            }
            case G_MOVEWORD:
                if (((w0 >> 16) & 0xFF) == G_MW_SEGMENT) {
                    w->segments[((w0 & 0xFFFF) / 4) & 0xF] = w1;
                }
                break;
            case G_TEXRECT:
            case G_TEXRECTFLIP:
                g += 2; /* RDPHALF_1 / RDPHALF_2 */
                break;
            default:
                break;
        }
    }
}

/* Walk [from, to) of one display list buffer for one actor. */
static void Walk_Range(Walker* w, const Gfx* from, const Gfx* to) {
    static const Gfx sEnd = { { (u32)G_ENDDL << 24, 0 } };
    s32 guard = 8192;

    /* The buffer has no ENDDL between actors: walk command by command up to
     * `to`, entering called lists, stopping at the end. */
    while (from < to && guard-- > 0) {
        Gfx one[2];

        one[0] = *from;
        one[1] = sEnd;
        if ((u8)(from->words.w0 >> 24) == G_TEXRECT || (u8)(from->words.w0 >> 24) == G_TEXRECTFLIP) {
            from += 3;
            continue;
        }
        Walk_List(w, one, 0);
        from++;
    }
}

/* Actor_DrawAll's actor loop for the generic-draw actors only (culling flag
 * from OotCore_CullActors). Returns the item count. */
s32 OotCore_DrawActors(PlayState* play) {
    GraphicsContext* gfx = OotCore_GfxCtx();
    Walker w;
    s32 i;

    sItemCount = 0;
    sDropped = 0;
    if (ARRAY_COUNT(sGenericDrawIds) <= 1) { /* only the -1 sentinel */
        return 0;
    }
    for (i = 0; i < ACTORCAT_MAX; i++) {
        Actor* actor;

        for (actor = play->actorCtx.actorLists[i].head; actor != NULL; actor = actor->next) {
            Gfx* opa0;
            Gfx* xlu0;
            u32 s;

            if (actor->init != NULL || actor->draw == NULL || actor->update == NULL ||
                !(actor->flags & (ACTOR_FLAG_DRAW_CULLING_DISABLED | ACTOR_FLAG_INSIDE_CULLING_VOLUME)) ||
                !Draw_IsGeneric(actor->id)) {
                continue;
            }
            /* Leave room: one actor's lists plus its GRAPH_ALLOC matrices. */
            if ((u8*)gfx->polyOpa.d - (u8*)gfx->polyOpa.p < 0x1800 ||
                (u8*)gfx->polyXlu.d - (u8*)gfx->polyXlu.p < 0x800) {
                sDropped++;
                return sItemCount;
            }
            opa0 = gfx->polyOpa.p;
            xlu0 = gfx->polyXlu.p;
            Actor_Draw(play, actor);
            actor->isDrawn = true;

            for (s = 0; s < 16; s++) {
                w.segments[s] = gSegments[s];
            }
            w.segments[6] = (uintptr_t)play->objectCtx.slots[actor->objectSlot].segment;
            SkinMatrix_SetTranslate(&w.stack[0], 0.0f, 0.0f, 0.0f);
            w.depth = 0;
            w.actorId = actor->id;
            w.xlu = 0;
            Walk_Range(&w, opa0, gfx->polyOpa.p);
            for (s = 0; s < 16; s++) {
                w.segments[s] = gSegments[s];
            }
            w.segments[6] = (uintptr_t)play->objectCtx.slots[actor->objectSlot].segment;
            SkinMatrix_SetTranslate(&w.stack[0], 0.0f, 0.0f, 0.0f);
            w.depth = 0;
            w.xlu = 1;
            Walk_Range(&w, xlu0, gfx->polyXlu.p);
        }
    }
    return sItemCount;
}

static const OotCoreMeshKey sMeshes[] = {
#include "../../build/oot-core/generic_meshes.h"
};
static OotCoreMeshKey sSceneMeshes[ARRAY_COUNT(sMeshes)];

s32 OotCore_IsGenericDraw(s16 id) {
    return Draw_IsGeneric(id);
}

int OotCore_MeshList(const OotCoreMeshKey** out) {
    PlayState* play = gOotCorePlay;
    u32 i;
    s32 j, n = 0;

    *out = sSceneMeshes;
    if (play == NULL) {
        return 0;
    }
    for (i = 0; i < ARRAY_COUNT(sMeshes); i++) {
        if (sMeshes[i].kind == OOT_CORE_DRAW_KEEP) {
            sSceneMeshes[n++] = sMeshes[i];
            continue;
        }
        for (j = 1; j < play->objectCtx.numEntries; j++) {
            if (sMeshes[i].kind == OOT_CORE_DRAW_OBJECT && ABS(play->objectCtx.slots[j].id) == sMeshes[i].object) {
                sSceneMeshes[n++] = sMeshes[i];
                break;
            }
        }
    }
    return n;
}

int OotCore_DrawItems(const OotCoreDrawItem** out) {
    *out = sItems;
    return sItemCount;
}
