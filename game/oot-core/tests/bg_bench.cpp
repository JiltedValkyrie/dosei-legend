/*
 * Collision cost: the same Kokiri Forest queries through the C library
 * (shared/lib/collision) and the core (real z_bgcheck via oot_core_bg.cpp).
 * Host timing only: compares algorithmic work, not SH-2 cycles. Also counts
 * how many polygons each core query visits (z_bgcheck hook counters).
 * usage: bg_bench S1.COL   (run_bg_port_probe.sh BENCH=1)
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
int OotCoreBg_Line(CollisionContext* colCtx, const int* a, const int* b, int* at, unsigned checks, unsigned ignore,
                   OotCoreBgHit* hit);
int printf(const char*, ...);
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

/* Host TSC cycles (relative cost only). The prelude maps double to Fx:
 * integers only here. */
static unsigned long long now_c(void) {
    return __builtin_ia32_rdtsc();
}

#define MAXQ 4096
static int qx[MAXQ], qy[MAXQ], qz[MAXQ], nq;

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
    static bg_mesh_t mesh;
    if (!need || !bg_mesh_decode(file, len, store, need, &mesh)) { printf("C mesh load failed\n"); return 2; }
    bg_scene_set(&mesh);
    static uint8_t index[20 * 1024];
    kokiri_collision_index(index, sizeof index);
    static uint8_t dyna[512 * 36];
    bg_dyna_init(dyna, sizeof dyna);

    CollisionHeader* h = col->colHeader;
    int x0 = h->minBounds.x, x1 = h->maxBounds.x, z0 = h->minBounds.z, z1 = h->maxBounds.z;
    /* Query points standing on real floor: like Link, the camera and shadows. */
    for (int z = z0; z < z1 && nq < MAXQ; z += (z1 - z0) / 48) {
        for (int x = x0; x < x1 && nq < MAXQ; x += (x1 - x0) / 48) {
            bg_vec_t p = { x, (int)h->maxBounds.y + 100, z };
            int y = bg_floor(&p, BG_IGNORE_ENTITY, 0);
            if (y == BG_Y_MIN) continue;
            qx[nq] = x; qy[nq] = y; qz[nq] = z; nq++;
        }
    }
    printf("queries %d (scene polys %d, subdiv %d x %d x %d)\n", nq, h->numPolygons, col->subdivAmount.x,
           col->subdivAmount.y, col->subdivAmount.z);
#ifndef BENCH_REPS
#define BENCH_REPS 20
#endif
    const int reps = BENCH_REPS;
    unsigned long long t0, c_floor, k_floor, c_line, k_line, c_wall, k_wall;
    volatile int sink = 0;

    t0 = now_c();
    for (int r = 0; r < reps; r++)
        for (int i = 0; i < nq; i++) { bg_vec_t p = { qx[i], qy[i] + 50, qz[i] }; sink += bg_floor(&p, BG_IGNORE_ENTITY, 0); }
    c_floor = (now_c() - t0) / (reps * nq);
    t0 = now_c();
    for (int r = 0; r < reps; r++)
        for (int i = 0; i < nq; i++) { int p[3] = { qx[i], qy[i] + 50, qz[i] }; OotCoreBgHit k; sink += OotCoreBg_Floor(col, p, 2, &k); }
    k_floor = (now_c() - t0) / (reps * nq);

    t0 = now_c();
    for (int r = 0; r < reps; r++)
        for (int i = 0; i < nq; i++) {
            bg_vec_t a = { qx[i], qy[i] + 40, qz[i] }, b = { qx[i] + 150, qy[i] + 120, qz[i] - 150 }, at;
            bg_hit_t hit;
            sink += bg_line(&a, &b, &at, BG_CHECK_ALL, BG_IGNORE_CAMERA, &hit);
        }
    c_line = (now_c() - t0) / (reps * nq);
    t0 = now_c();
    for (int r = 0; r < reps; r++)
        for (int i = 0; i < nq; i++) {
            int a[3] = { qx[i], qy[i] + 40, qz[i] }, b[3] = { qx[i] + 150, qy[i] + 120, qz[i] - 150 }, at[3];
            OotCoreBgHit k;
            sink += OotCoreBg_Line(col, a, b, at, 7, 1, &k);
        }
    k_line = (now_c() - t0) / (reps * nq);

    t0 = now_c();
    for (int r = 0; r < reps; r++)
        for (int i = 0; i < nq; i++) {
            bg_vec_t prev = { qx[i], qy[i], qz[i] }, next = { qx[i] + 6, qy[i], qz[i] + 6 }, res;
            bg_hit_t hit;
            sink += bg_wall(&res, &next, &prev, 14, 26, BG_IGNORE_ENTITY, false, &hit);
        }
    c_wall = (now_c() - t0) / (reps * nq);
    t0 = now_c();
    for (int r = 0; r < reps; r++)
        for (int i = 0; i < nq; i++) {
            int prev[3] = { qx[i], qy[i], qz[i] }, next[3] = { qx[i] + 6, qy[i], qz[i] + 6 }, res[3];
            OotCoreBgHit k;
            sink += OotCoreBg_Wall(col, res, next, prev, 14, 26, 2, 0, &k);
        }
    k_wall = (now_c() - t0) / (reps * nq);

    printf("cycles/query  C lib    core  core/C x10\n");
    printf("floor   %8llu %8llu %5llu\n", c_floor, k_floor, k_floor * 10 / (c_floor ? c_floor : 1));
    printf("line    %8llu %8llu %5llu\n", c_line, k_line, k_line * 10 / (c_line ? c_line : 1));
    printf("wall    %8llu %8llu %5llu\n", c_wall, k_wall, k_wall * 10 / (c_wall ? c_wall : 1));
    return sink == 12345 ? 1 : 0;
}
