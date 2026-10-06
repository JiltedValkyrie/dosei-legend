/*
 * Host probe: real z_bgcheck on a real scene collision blob. Raycast down at
 * every En_Kusa spawn (all rooms/layers) like EnKusa_SnapToFloor, plus a
 * grid sweep. Built Fx and OOT_CORE_HWFLOAT=1; compare_probe.py diffs.
 */
#include "oot_prelude.h"
#include "ultra64.h"
#include "bgcheck.h"
#include "play_state.h"
#include "regs.h"
#include "actor.h"
#include "segmented_address.h"
#include "oot_scene_blob.h"
#include "oot_core_host.h"

const OotCoreHost* gOotCoreHost;
extern "C" const OotSceneBlob oot_scene_blob;
extern "C" int printf(const char*, ...);
extern "C" int puts(const char*);

typedef decltype(0.0) hw_double;
static hw_double D(f32 f) { return (hw_double)(decltype(0.0f))f; }

/* Scene id selects BgCheck's custom memSize/subdivisions (Field: 0xB798). */
#ifndef PROBE_SCENE
#define PROBE_SCENE SCENE_KOKIRI_FOREST
#endif

static PlayState sPlay;
static RegEditor sRegs;
uintptr_t gSegments[NUM_SEGMENTS];

static void Ray(const char* tag, int i, s32 x, s32 y, s32 z) {
    Vec3f pos;
    CollisionPoly* poly;
    s32 bgId;
    pos.x = x;
    pos.y = y;
    pos.z = z;
    f32 fy = BgCheck_EntityRaycastDown4(&sPlay.colCtx, &poly, &bgId, NULL, &pos);
    printf("%s_%d(%ld,%ld,%ld) %.6f\n", tag, i, (long)x, (long)y, (long)z, D(fy));
}

int main() {
    const unsigned long thaSize = 0x100000;
    static u64 buf[0x100000 / 8]; /* static: low address (see run script image base) */
    gRegEditor = &sRegs;
    sPlay.sceneId = PROBE_SCENE;
    THA_Init(&sPlay.state.tha, buf, thaSize);
    BgCheck_Allocate(&sPlay.colCtx, &sPlay, (CollisionHeader*)oot_scene_blob.col_header);
    printf("subdivLen.x %.6f\nsubdivLen.y %.6f\nsubdivLen.z %.6f\n", D(sPlay.colCtx.subdivLength.x),
           D(sPlay.colCtx.subdivLength.y), D(sPlay.colCtx.subdivLength.z));
    printf("subdivInv.x %.9f\nsubdivInv.y %.9f\nsubdivInv.z %.9f\n", D(sPlay.colCtx.subdivLengthInv.x),
           D(sPlay.colCtx.subdivLengthInv.y), D(sPlay.colCtx.subdivLengthInv.z));
    printf("polyNodes %ld\n", (long)sPlay.colCtx.polyNodes.count);
    printf("polyNodesMax %ld\n", (long)sPlay.colCtx.polyNodes.max);
    if (sPlay.colCtx.polyNodes.count > sPlay.colCtx.polyNodes.max) {
        puts("polyNodes OVERFLOW");
        return 1;
    }

    int n = 0;
    u32 total = oot_scene_blob.num_rooms * oot_scene_blob.num_layers;
    for (u32 l = 0; l < total; l++) {
        const OotSceneLayer* L = &oot_scene_blob.layers[l];
        const ActorEntry* a = (const ActorEntry*)L->actors;
        for (u32 k = 0; a != NULL && k < L->num_actors; k++) {
            if (a[k].id == ACTOR_EN_KUSA) {
                Ray("kusa", n++, a[k].pos.x, a[k].pos.y + 30, a[k].pos.z);
            }
        }
    }
    printf("kusa_count %d\n", n);
    CollisionHeader* h = (CollisionHeader*)oot_scene_blob.col_header;
    int g = 0;
    for (s32 z = h->minBounds.z; z <= h->maxBounds.z; z += 97) {
        for (s32 x = h->minBounds.x; x <= h->maxBounds.x; x += 97) {
            Ray("grid", g++, x, h->maxBounds.y, z);
        }
    }
    return 0;
}
