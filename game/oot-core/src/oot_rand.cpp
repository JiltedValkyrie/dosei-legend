/*
 * oot-core replacement for decomp src/libc64/qrand.c (N64 path).
 *
 * The original builds a float in [1,2) by OR-ing 23 LCG bits into the IEEE
 * mantissa of 1.0f, then subtracts 1. Same LCG and same bits here; the
 * mantissa m maps to m / 2^23, i.e. Fx raw m >> (23 - FX_FRAC) in Q16.16
 * (the 7 lowest mantissa bits are dropped).
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
    return Fx::raw((fx_raw)((bits & 0x007FFFFF) >> (23 - FX_FRAC))); /* low mantissa bits dropped */
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

/*
 * Importer fix_rand_ranges: Rand_ZeroOne() * n and Rand_CenteredFloat(n)
 * with n past the Q16.16 range (random binangles, n <= 0x20000). One
 * Rand_Next() draw, same as the original call; 32-bit integer result, so
 * an s16 store wraps exactly as the float->int->halfword original did.
 * (m >> 8) < 2^15 and n <= 2^17 keep the product below 2^32.
 */
s32 OotRand_ZeroOneTimes(u32 n) {
#if OOT_CORE_HWFLOAT
    return (s32)(Rand_ZeroOne() * (f32)n);
#else
    u32 m = (Rand_Next() & 0x007FFFFF) >> 8;
    return (s32)((m * n) >> 15);
#endif
}

s32 OotRand_CenteredTimes(u32 n) {
#if OOT_CORE_HWFLOAT
    return (s32)((Rand_ZeroOne() - 0.5f) * (f32)n);
#else
    return OotRand_ZeroOneTimes(n) - (s32)(n >> 1);
#endif
}
