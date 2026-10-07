/*
 * Dynamic polygon contract for oot_core_bg.cpp: real DynaPoly with two owners,
 * removal and slot reuse. hit.poly must be the index inside the OWNER's mesh
 * (C bg_* contract), never the shared dyna pool index; bg_id = the owner's
 * slot; surfaces come from that owner's mesh.
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
#include "oot_core_bg.h"

extern "C" {
int OotCoreBg_Floor(CollisionContext* colCtx, const int* pos, unsigned ignore, OotCoreBgHit* hit);
int printf(const char*, ...);
}

const OotCoreHost* gOotCoreHost;
PlayState* gOotCorePlay;
extern "C" const OotSceneBlob oot_scene_blob;
static PlayState sPlay;
static RegEditor sRegs;
uintptr_t gSegments[NUM_SEGMENTS];

/* 200x200 square at local y 0: tri 0 covers x+z < 200, tri 1 the rest. */
static Vec3s sVerts[4] = { { 0, 0, 0 }, { 200, 0, 0 }, { 200, 0, 200 }, { 0, 0, 200 } };

struct Owner {
    CollisionPoly polys[2];
    SurfaceType surface[1];
    CollisionHeader header;
    DynaPolyActor actor;
};

static void ActorUpdate(Actor*, PlayState*) {}

static void make(Owner* o, u32 data0, s32 x, s32 y, s32 z) {
    static const u16 tris[2][3] = { { 0, 3, 1 }, { 1, 3, 2 } };
    for (int t = 0; t < 2; t++) {
        CollisionPoly* p = &o->polys[t];
        p->type = 0;
        p->flags_vIA = tris[t][0];
        p->flags_vIB = tris[t][1];
        p->vIC = tris[t][2];
        p->normal.x = 0;
        p->normal.y = 0x7FFF;
        p->normal.z = 0;
        p->dist = 0;
    }
    o->surface[0].data[0] = data0;
    o->surface[0].data[1] = 0;
    o->header.minBounds.x = 0; o->header.minBounds.y = 0; o->header.minBounds.z = 0;
    o->header.maxBounds.x = 200; o->header.maxBounds.y = 0; o->header.maxBounds.z = 200;
    o->header.numVertices = 4;
    o->header.vtxList = sVerts;
    o->header.numPolygons = 2;
    o->header.polyList = o->polys;
    o->header.surfaceTypeList = o->surface;
    o->header.bgCamList = 0;
    o->header.numWaterBoxes = 0;
    o->header.waterBoxes = 0;
    Actor* a = &o->actor.actor;
    a->world.pos.x = x; a->world.pos.y = y; a->world.pos.z = z;
    a->scale.x = 1; a->scale.y = 1; a->scale.z = 1;
    a->update = ActorUpdate;
}

static int fails;
static void expect_not(const char* what, int x, int z, int bgId, u32 data0) {
    int pos[3] = { x, 3500, z };
    OotCoreBgHit hit = {};
    OotCoreBg_Floor(&sPlay.colCtx, pos, 0, &hit);
    if (hit.bg_id == bgId || hit.data0 == data0) {
        printf("FAIL %s: still bg %u data0 %x\n", what, hit.bg_id, (unsigned)hit.data0);
        fails++;
    }
}
static void expect(const char* what, int x, int z, int bgId, int poly, u32 data0) {
    int pos[3] = { x, 3500, z };
    OotCoreBgHit hit = {};
    int y = OotCoreBg_Floor(&sPlay.colCtx, pos, 0, &hit);
    if (hit.bg_id != bgId || hit.poly != poly || hit.data0 != data0) {
        printf("FAIL %s: y %d bg %u poly %u data0 %x (want bg %d poly %d data0 %x)\n", what, y, hit.bg_id,
               hit.poly, (unsigned)hit.data0, bgId, poly, (unsigned)data0);
        fails++;
    }
}

int main() {
    static u64 tha[0x100000 / 8];
    gRegEditor = &sRegs;
    sPlay.sceneId = SCENE_KOKIRI_FOREST;
    THA_Init(&sPlay.state.tha, tha, sizeof tha);
    BgCheck_Allocate(&sPlay.colCtx, &sPlay, (CollisionHeader*)oot_scene_blob.col_header);
    DynaCollisionContext* dyna = &sPlay.colCtx.dyna;

    static Owner A, B, C;
    make(&A, 0x1111, 1000, 3000, 1000);
    make(&B, 0x2222, 1500, 3000, 1000);
    int idA = DynaPoly_SetBgActor(&sPlay, dyna, &A.actor.actor, &A.header);
    int idB = DynaPoly_SetBgActor(&sPlay, dyna, &B.actor.actor, &B.header);
    A.actor.bgId = idA;
    B.actor.bgId = idB;
    DynaPoly_UpdateContext(&sPlay, dyna);
    DynaPoly_UpdateBgActorTransforms(&sPlay, dyna);
    printf("A slot %d start %u, B slot %d start %u\n", idA, dyna->bgActors[idA].dynaLookup.polyStartIndex, idB,
           dyna->bgActors[idB].dynaLookup.polyStartIndex);
    for (int i = 0; i < 4; i++) {
        /* Flat floor at y 3000: unit normal, plane distance -3000. */
        CollisionPoly* p = &dyna->polyList[i];
        if (p->normal.y < 32700 || p->dist > -2998 || p->dist < -3002) {
            printf("FAIL pool poly %d normal (%d,%d,%d) dist %d\n", i, p->normal.x, p->normal.y, p->normal.z, p->dist);
            fails++;
        }
    }
    printf("A sphere (%d,%d,%d) r %d minY %d floorHead %u\n", dyna->bgActors[idA].boundingSphere.center.x,
           dyna->bgActors[idA].boundingSphere.center.y, dyna->bgActors[idA].boundingSphere.center.z,
           dyna->bgActors[idA].boundingSphere.radius, (int)dyna->bgActors[idA].minY,
           dyna->bgActors[idA].dynaLookup.floor.head);
    expect("A tri0", 1050, 1050, idA, 0, 0x1111);
    expect("A tri1", 1150, 1150, idA, 1, 0x1111);
    expect("B tri0", 1550, 1050, idB, 0, 0x2222);   /* pool index 2: must report 0 */
    expect("B tri1", 1650, 1150, idB, 1, 0x2222);

    /* Remove A: B's mesh moves to the start of the pool. */
    DynaPoly_DeleteBgActor(&sPlay, dyna, idA);
    DynaPoly_UpdateContext(&sPlay, dyna);
    expect_not("A gone", 1050, 1050, idA, 0x1111);
    expect("B tri1 after removal", 1650, 1150, idB, 1, 0x2222);

    /* C reuses A's slot at a new place; A's old place stays empty. */
    make(&C, 0x3333, 2000, 3000, 1000);
    int idC = DynaPoly_SetBgActor(&sPlay, dyna, &C.actor.actor, &C.header);
    C.actor.bgId = idC;
    DynaPoly_UpdateContext(&sPlay, dyna);
    if (idC != idA) { printf("FAIL slot not reused (%d vs %d)\n", idC, idA); fails++; }
    expect("C tri1 in reused slot", 2150, 1150, idC, 1, 0x3333);
    expect("B tri0 after reuse", 1550, 1050, idB, 0, 0x2222);
    expect_not("old A place empty", 1150, 1150, idA, 0x1111);
    printf(fails ? "dyna contract FAIL\n" : "dyna contract PASS: owner-local poly ids across removal and slot reuse\n");
    return fails ? 1 : 0;
}
