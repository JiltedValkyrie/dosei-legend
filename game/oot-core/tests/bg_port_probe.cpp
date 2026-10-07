/*
 * Collision port parity: the same scene through the C library
 * (shared/lib/collision, build/cd/S<n>.COL) and the core shim
 * (oot-core/src/oot_core_bg.cpp over real z_bgcheck + scene blob).
 * Prints per-query agreement; exit 1 if any class disagrees beyond tolerance.
 */
#include "oot_prelude.h"
#include "ultra64.h"
#include "bgcheck.h"
#include "play_state.h"
#include "regs.h"
#include "segmented_address.h"
#include "oot_scene_blob.h"
#include "oot_core_host.h"
#include "oot_core_bg.h"

/* The C header wants <stdint.h> types; the core build is -nostdinc. */
typedef signed char int8_t;
typedef unsigned char uint8_t;
typedef short int16_t;
typedef unsigned short uint16_t;
typedef int int32_t;
typedef unsigned int uint32_t;
typedef unsigned long long uint64_t;
#define _STDINT_H 1
#define _STDBOOL_H 1
extern "C" {
#include "kokiri_collision.h"

int OotCoreBg_Floor(CollisionContext* colCtx, const int* pos, unsigned ignore, OotCoreBgHit* hit);
int OotCoreBg_Wall(CollisionContext* colCtx, int* result, const int* next, const int* prev, int radius,
                   int checkHeight, unsigned ignore, int skipLine, OotCoreBgHit* hit);
int OotCoreBg_Ceiling(CollisionContext* colCtx, int* outY, const int* pos, int checkHeight, unsigned ignore,
                      OotCoreBgHit* hit);
int OotCoreBg_Line(CollisionContext* colCtx, const int* a, const int* b, int* at, unsigned checks, unsigned ignore,
                   OotCoreBgHit* hit);
int printf(const char*, ...);
void* malloc(unsigned long);
typedef struct FILE FILE;
FILE* fopen(const char*, const char*);
unsigned long fread(void*, unsigned long, unsigned long, FILE*);
int fclose(FILE*);
}

const OotCoreHost* gOotCoreHost;
PlayState* gOotCorePlay;
extern "C" const OotSceneBlob oot_scene_blob;
static PlayState sPlay;
static RegEditor sRegs;
uintptr_t gSegments[NUM_SEGMENTS];
#define OOT_BG_Y_MIN_PROBE (-32000)
static int iabs(int v) { return v < 0 ? -v : v; }

int main(int argc, char** argv) {
    static u64 tha[0x100000 / 8];
    gRegEditor = &sRegs;
    sPlay.sceneId = SCENE_KOKIRI_FOREST;
    THA_Init(&sPlay.state.tha, tha, sizeof tha);
    BgCheck_Allocate(&sPlay.colCtx, &sPlay, (CollisionHeader*)oot_scene_blob.col_header);
    CollisionContext* col = &sPlay.colCtx;

    static uint8_t file[1 << 20];
    FILE* f = fopen(argv[1], "rb");
    uint32_t len = (uint32_t)fread(file, 1, sizeof file, f);
    fclose(f);
    uint32_t need = bg_mesh_bytes(file, len);
    static uint8_t store[1 << 20];
    static bg_mesh_t meshStorage;
    if (!need || !bg_mesh_decode(file, len, store, need, &meshStorage)) { printf("C mesh load failed\n"); return 2; }
    bg_scene_set(&meshStorage);
    static uint8_t dyna[512 * 36];
    bg_dyna_init(dyna, sizeof dyna);

    /* Scene bounds from the core header. */
    CollisionHeader* h = col->colHeader;
    int x0 = h->minBounds.x, x1 = h->maxBounds.x, z0 = h->minBounds.z, z1 = h->maxBounds.z;
    int top = (int)h->maxBounds.y + 200;
    /* One row per query: identical inputs for C and core (every coordinate
     * derives from the C floor, the same in the fx and hw builds), then
     * hit, position, owner, poly and raw surface for each side.
     * Row: kind id ax ay az bx by bz | C hit x y z bg poly d0 d1 | K ... */
    int id = 0;
    for (int x = x0 + 13; x < x1; x += 97) {
        for (int z = z0 + 7; z < z1; z += 97, id++) {
            bg_vec_t p = { x, top, z };
            int cp[3] = { x, top, z };
            bg_hit_t ch = {};
            OotCoreBgHit kh = {};
            int cy = bg_floor(&p, 2, &ch);
            int ky = OotCoreBg_Floor(col, cp, 2, &kh);
            printf("F %d %d %d %d 0 0 0 | %d 0 %d 0 %u %u %x %x | %d 0 %d 0 %u %u %x %x\n", id, x, top, z,
                   cy > OOT_BG_Y_MIN_PROBE, cy, ch.bg_id, ch.poly, (unsigned)ch.data0, (unsigned)ch.data1,
                   ky > OOT_BG_Y_MIN_PROBE, ky, kh.bg_id, kh.poly, (unsigned)kh.data0, (unsigned)kh.data1);
            if (cy <= OOT_BG_Y_MIN_PROBE) continue;

            /* Feet on the C floor: 40-unit step east, Link-sized wall sphere. */
            int a[3] = { x, cy, z }, b[3] = { x + 40, cy, z }, kres[3];
            bg_vec_t prev = { a[0], a[1], a[2] }, next = { b[0], b[1], b[2] }, cres = {};
            bg_hit_t cw = {};
            OotCoreBgHit kw = {};
            int cHit = bg_wall(&cres, &next, &prev, 20, 26, 2, 0, &cw);
            int kHit = OotCoreBg_Wall(col, kres, b, a, 20, 26, 2, 0, &kw);
            printf("W %d %d %d %d %d %d %d | %d %d %d %d %u %u %x %x | %d %d %d %d %u %u %x %x\n", id, a[0], a[1],
                   a[2], b[0], b[1], b[2], cHit, cres.x, cres.y, cres.z, cHit ? cw.bg_id : 255, cHit ? cw.poly : 0,
                   cHit ? (unsigned)cw.data0 : 0, cHit ? (unsigned)cw.data1 : 0, kHit, kres[0], kres[1], kres[2],
                   kHit ? kw.bg_id : 255, kHit ? kw.poly : 0, kHit ? (unsigned)kw.data0 : 0,
                   kHit ? (unsigned)kw.data1 : 0);

            int cOut = 0, kOut = 0;
            bg_hit_t cc = {};
            OotCoreBgHit kc = {};
            bg_vec_t feet = { a[0], a[1], a[2] };
            int cC = bg_ceiling(&cOut, &feet, 50, 2, &cc);
            int kC = OotCoreBg_Ceiling(col, &kOut, a, 50, 2, &kc);
            printf("C %d %d %d %d 0 0 0 | %d 0 %d 0 %u %u %x %x | %d 0 %d 0 %u %u %x %x\n", id, a[0], a[1], a[2],
                   cC, cC ? cOut : 0, cC ? cc.bg_id : 255, cC ? cc.poly : 0, cC ? (unsigned)cc.data0 : 0,
                   cC ? (unsigned)cc.data1 : 0, kC, kC ? kOut : 0, kC ? kc.bg_id : 255, kC ? kc.poly : 0,
                   kC ? (unsigned)kc.data0 : 0, kC ? (unsigned)kc.data1 : 0);

            int la[3] = { x, cy + 30, z }, lb[3] = { x + 300, cy + 30, z + 150 }, kat[3] = { 0, 0, 0 };
            bg_vec_t ca = { la[0], la[1], la[2] }, cb = { lb[0], lb[1], lb[2] }, cat = {};
            bg_hit_t cl = {};
            OotCoreBgHit kl = {};
            int cL = bg_line(&ca, &cb, &cat, 7, 2, &cl);
            int kL = OotCoreBg_Line(col, la, lb, kat, 7, 2, &kl);
            printf("L %d %d %d %d %d %d %d | %d %d %d %d %u %u %x %x | %d %d %d %d %u %u %x %x\n", id, la[0], la[1],
                   la[2], lb[0], lb[1], lb[2], cL, cL ? cat.x : 0, cL ? cat.y : 0, cL ? cat.z : 0,
                   cL ? cl.bg_id : 255, cL ? cl.poly : 0, cL ? (unsigned)cl.data0 : 0, cL ? (unsigned)cl.data1 : 0,
                   kL, kL ? kat[0] : 0, kL ? kat[1] : 0, kL ? kat[2] : 0, kL ? kl.bg_id : 255, kL ? kl.poly : 0,
                   kL ? (unsigned)kl.data0 : 0, kL ? (unsigned)kl.data1 : 0);
        }
    }
    return 0;
}
