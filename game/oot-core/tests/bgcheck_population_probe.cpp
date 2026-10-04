/* Host-only differential probe: real scene collision and source contact code.
 * Counter wraps only z_bgcheck sqrt calls; elapsed host time is not target FPS. */
#include "oot_prelude.h"
#include "ultra64.h"
#include "bgcheck.h"
#include "play_state.h"
#include "regs.h"
#include "actor.h"
#include "segmented_address.h"
#include "oot_scene_blob.h"
#include "oot_core_host.h"
#include "libc/math.h"

extern "C" int printf(const char*, ...);
extern "C" const OotSceneBlob probe_souko, probe_spot01, probe_spot20;
const OotCoreHost* gOotCoreHost;
uintptr_t gSegments[NUM_SEGMENTS];
static PlayState sPlay;
static RegEditor sRegs;
static u32 sSqrt;

f32 OotProbe_Sqrt(f32 value) {
    sSqrt++;
    return sqrtf(value);
}

static s32 PolyIndex(CollisionPoly* poly) {
    return poly == NULL ? -1 : poly - sPlay.colCtx.colHeader->polyList;
}

static void Contact(s32 x, s32 y, s32 z) {
    Vec3f pos = { x, y, z }, prev, result;
    CollisionPoly *floor = NULL, *wall = NULL, *ceiling = NULL;
    s32 bgId = BGCHECK_SCENE;
    f32 floorY = BgCheck_EntityRaycastDown4(&sPlay.colCtx, &floor, &bgId, NULL, &pos);
    pos.y = floorY + FXL(0.25f);
    prev = pos;
    prev.x -= FXL(8.0f);
    prev.z += FXL(8.0f);
    s32 hit = BgCheck_EntitySphVsWall3(&sPlay.colCtx, &result, &pos, &prev,
                                     FXL(20.0f), &wall, &bgId, NULL, FXL(20.0f));
    f32 ceilingY;
    pos.y += FXL(10.0f);
    s32 ceilHit = BgCheck_EntityCheckCeiling(&sPlay.colCtx, &ceilingY, &pos,
                                          FXL(50.0f), &ceiling, &bgId, NULL);
    printf("%ld %ld %ld %ld %ld %ld %ld %ld\n", (long)PolyIndex(floor),
           (long)(floorY * 16), (long)hit, (long)PolyIndex(wall),
           (long)(result.x * 16), (long)(result.z * 16), (long)ceilHit,
           (long)(ceilHit ? (s32)(ceilingY * 16) : -1));
}

static void Scene(const OotSceneBlob* blob, s16 sceneId) {
    static u64 memory[0x100000 / 8];
    __builtin_memset(&sPlay, 0, sizeof(sPlay));
    sPlay.sceneId = sceneId;
    THA_Init(&sPlay.state.tha, memory, sizeof(memory));
    BgCheck_Allocate(&sPlay.colCtx, &sPlay, (CollisionHeader*)blob->col_header);
    CollisionHeader* h = sPlay.colCtx.colHeader;
    printf("SCENE %d\n", sceneId);
    for (s32 z = h->minBounds.z; z <= h->maxBounds.z; z += 193) {
        for (s32 x = h->minBounds.x; x <= h->maxBounds.x; x += 193) {
            Contact(x, h->maxBounds.y, z);
        }
    }
    /* Every source Cucco placement/layer, nearby movement and thrown heights. */
    for (u32 r = 0; r < blob->num_rooms * blob->num_layers; r++) {
        const OotSceneLayer* layer = &blob->layers[r];
        const ActorEntry* actors = (const ActorEntry*)layer->actors;
        for (u32 a = 0; actors != NULL && a < layer->num_actors; a++) {
            if (actors[a].id != ACTOR_EN_NIW) continue;
            for (s32 dx = -40; dx <= 40; dx += 20) {
                for (s32 dz = -40; dz <= 40; dz += 20) {
                    Contact(actors[a].pos.x + dx, actors[a].pos.y + 60,
                            actors[a].pos.z + dz);
                }
            }
        }
    }
}

int main(void) {
    gRegEditor = &sRegs;
    Scene(&probe_souko, SCENE_LON_LON_BUILDINGS);
    Scene(&probe_spot01, SCENE_KAKARIKO_VILLAGE);
    Scene(&probe_spot20, SCENE_LON_LON_RANCH);
    printf("SQRT %lu\n", (unsigned long)sSqrt);
    return 0;
}
