/*
 * oot-core replacement for decomp src/libc64/qrand.c (N64 path).
 *
 * The original builds a float in [1,2) by OR-ing 23 LCG bits into the IEEE
 * mantissa of 1.0f, then subtracts 1. Same LCG and same bits here; the
 * mantissa m maps to m / 2^23, i.e. Fx raw m << (FX_FRAC - 23): exact.
 */
#include "oot_prelude.h"
#include "libc64/qrand.h"

#define RAND_MULTIPLIER 1664525
#define RAND_INCREMENT 1013904223

static u32 sRandInt = 1;

u32 Rand_Next(void) {
    u32 next = sRandInt * RAND_MULTIPLIER + RAND_INCREMENT;

    sRandInt = next;
    return next;
}

void Rand_Seed(u32 seed) {
    sRandInt = seed;
}

static f32 Rand_MantissaToUnit(u32 bits) {
#if OOT_CORE_HWFLOAT
    return (f32)(bits & 0x007FFFFF) / 8388608.0f;
#else
#if FX_FRAC >= 23
    return Fx::raw((fx_raw)(bits & 0x007FFFFF) << (FX_FRAC - 23));
#else
    return Fx::raw((fx_raw)(bits & 0x007FFFFF) >> (23 - FX_FRAC)); /* low mantissa bits dropped */
#endif
#endif
}

f32 Rand_ZeroOne(void) {
    return Rand_MantissaToUnit(Rand_Next());
}

void Rand_Seed_Variable(u32* rndNum, u32 seed) {
    *rndNum = seed;
}

u32 Rand_Next_Variable(u32* rndNum) {
    return *rndNum = *rndNum * RAND_MULTIPLIER + RAND_INCREMENT;
}

f32 Rand_ZeroOne_Variable(u32* rndNum) {
    return Rand_MantissaToUnit(Rand_Next_Variable(rndNum));
}
