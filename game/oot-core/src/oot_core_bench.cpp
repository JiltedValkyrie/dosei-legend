/*
 * Phase 0 gate: time the imported decomp math on the SH-2 itself.
 * Each entry runs OOT_CORE_BENCH_ITERS calls; with the result in
 * microseconds per 1000 calls, the number reads directly as ns per call.
 * Inputs go through volatile storage so nothing folds at compile time.
 */
#include "oot_prelude.h"
#include "ultra64.h"
#include "z_lib.h"
#include "sys_math.h"
#include "sys_math3d.h"
#include "libc64/math64.h"
#include "oot_core_bench.h"

#define OOT_CORE_BENCH_ITERS 1000

static volatile s32 sSeed = 12345;
static Vec3f sA, sB;
static volatile f32 sSink;
static volatile s32 sSinkI;

static f32 vf(s32 i) {
    return (f32)(sSeed + i) * FXL(0.731f);
}

/* Entry-table slot (oot_core_api.cpp). */
void oot_core_bench_run(OotCoreBench* out, unsigned int (*ticks)(void),
                               unsigned int (*ticks_to_us)(unsigned int)) {
    unsigned int t0, i;
    f32 acc;

    /* 0: Fx multiply-add, small operands (positions * scale). */
    acc = vf(1);
    t0 = ticks();
    for (i = 0; i < OOT_CORE_BENCH_ITERS; i++) {
        acc = acc * FXL(0.999f) + vf(i);
    }
    out->ns[OOT_BENCH_MULADD] = ticks_to_us(ticks() - t0);
    sSink = acc;

    /* 1: Fx divide. */
    t0 = ticks();
    for (i = 0; i < OOT_CORE_BENCH_ITERS; i++) {
        acc = vf(i) / (vf(i + 3) + FXL(1.0f));
    }
    out->ns[OOT_BENCH_DIV] = ticks_to_us(ticks() - t0);
    sSink = acc;

    /* 2: Math_SmoothStepToF (common actor movement helper). */
    acc = FXL(0.0f);
    t0 = ticks();
    for (i = 0; i < OOT_CORE_BENCH_ITERS; i++) {
        Math_SmoothStepToF(&acc, vf(i & 63) * FXL(10.0f), FXL(0.3f), FXL(40.0f), FXL(1.0f));
    }
    out->ns[OOT_BENCH_SMOOTHSTEP] = ticks_to_us(ticks() - t0);
    sSink = acc;

    /* 3: 3D distance (sys_math3d Math3D_Vec3f_DistXYZ, sqrtf). */
    t0 = ticks();
    for (i = 0; i < OOT_CORE_BENCH_ITERS; i++) {
        sA.x = vf(i);
        sB.z = vf(i + 7) * FXL(40.0f);
        acc = Math3D_Vec3f_DistXYZ(&sA, &sB);
    }
    out->ns[OOT_BENCH_DIST] = ticks_to_us(ticks() - t0);
    sSink = acc;

    /* 4: Math_SinS (table) + sinf (polynomial). */
    t0 = ticks();
    for (i = 0; i < OOT_CORE_BENCH_ITERS; i++) {
        acc = Math_SinS((s16)(sSeed * i)) + sinf(vf(i));
    }
    out->ns[OOT_BENCH_SIN] = ticks_to_us(ticks() - t0);
    sSink = acc;

    /* 5: Math_Atan2S (yaw toward target). */
    t0 = ticks();
    for (i = 0; i < OOT_CORE_BENCH_ITERS; i++) {
        sSinkI = Math_Atan2S(vf(i) - FXL(300.0f), vf(i + 11) - FXL(200.0f));
    }
    out->ns[OOT_BENCH_ATAN2] = ticks_to_us(ticks() - t0);
}
