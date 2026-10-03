/*
 * oot-core Fx math runtime: the libc/libultra float primitives the decomp
 * calls, rebuilt on integers for the FPU-less SH-2. Game-side math
 * (sys_math*.c, z_lib.c, math64.c, sins/coss) is the real decomp code.
 */
#include "oot_prelude.h"
#include "ultra64.h"

extern "C++" {

/* Integer square root of a 64-bit value (bit-by-bit, no division). */
static unsigned long isqrt64(unsigned long long n) {
    unsigned long long res = 0;
    unsigned long long bit = 1ULL << 62;
    while (bit > n) {
        bit >>= 2;
    }
    while (bit != 0) {
        if (n >= res + bit) {
            n -= res + bit;
            res = (res >> 1) + bit;
        } else {
            res >>= 1;
        }
        bit >>= 2;
    }
    return (unsigned long)res;
}

#if defined(__sh__) && !defined(OOT_CORE_NO_DIVU)
/*
 * floor(sqrt(n)) for n < 2^62 on the SH-2 divider (method after SaturnMath++,
 * MIT, (c) 2024 Roberto Daniel Alves Duarte: hardware DIVU instead of a
 * bit loop; here exact, not its estimate). Start at 2^ceil(bits/2) >= sqrt(n);
 * Newton then falls monotonically to the floor. Each step is one 64/32
 * divide (~39 cycles) vs 31 rounds of 64-bit compare/subtract in isqrt64.
 */
static unsigned long isqrt64_divu(unsigned long long n) {
    unsigned long hi = (unsigned long)(n >> 32);
    int bits = hi ? 64 - __builtin_clz(hi) : (n ? 32 - __builtin_clz((unsigned long)n) : 0);
    long x = 1L << ((bits + 1) / 2); /* n < 2^60: x <= 2^30, n/x < 2^31 */
    for (;;) {
        /* x and n/x are both < 2^31; their sum needs the 32nd bit. */
        long y = (long)(((unsigned long)x + (unsigned long)fx_divu64_32((fx_raw)n, x)) >> 1);
        if (y >= x) {
            return (unsigned long)x;
        }
        x = y;
    }
}
#define ISQRT64 isqrt64_divu
#else
#define ISQRT64 isqrt64
#endif

f32 sqrtf(f32 f) {
#if OOT_CORE_HWFLOAT
    return __builtin_sqrtf(f);
#else
    if (f.v <= 0) {
        return Fx::raw(0);
    }
    /* sqrt(v / 2^F) * 2^F == sqrt(v * 2^F); exact while v * 2^F fits. */
    if (f.v < ((fx_raw)1 << (60 - FX_FRAC))) {
        return Fx::raw((fx_raw)ISQRT64((unsigned long long)fx_shl_frac(f.v)));
    }
    if (f.v < ((fx_raw)1 << 60)) {
        /* sqrt(v * 2^24) = sqrt(v * 2^s) * 2^((24 - s) / 2), s even, the
         * largest keeping v * 2^s < 2^60 (ISQRT64's range): >= 30 bits kept. */
        int s = FX_FRAC;
        while ((unsigned long long)f.v >= (1ULL << (60 - s))) {
            s -= 2;
        }
        return Fx::raw((fx_raw)ISQRT64((unsigned long long)f.v << s) << ((FX_FRAC - s) / 2));
    }
    {
        /* v >= 2^60: sqrt(v * 2^24) = sqrt(v >> t) * 2^((24 + t) / 2), t even. */
        int t = 2;
        while (((unsigned long long)f.v >> t) >= (1ULL << 60)) {
            t += 2;
        }
        return Fx::raw((fx_raw)ISQRT64((unsigned long long)f.v >> t) << ((FX_FRAC + t) / 2));
    }
#endif
}

#if !OOT_CORE_HWFLOAT
/*
 * libultra sinf/cosf are float polynomials; same idea on integers. Radians
 * -> binang with a 16-bit fraction, fold to one quadrant, then a degree-9
 * Taylor series in Q30 (32x32->64 multiplies). Error ~2e-7.
 * (The sins() table is NOT used: it samples i*pi/(2*1023), so interpolating
 * it at 16-binang steps is biased by up to one step.)
 */
#define Q30_MUL(a, b) (((long long)(a) * (b)) >> 30)

/* sin(x) for x in [0, pi/2] as Q30. x^2 reaches 2.47, so terms are 64-bit.
 * Compile time only now: it fills kSinQuadrant below. */
static constexpr s32 sin_q30_quadrant(s32 x) {
    long long x2 = Q30_MUL(x, x);
    /* Horner: x * (1 - x2/6 * (1 - x2/20 * (1 - x2/42 * (1 - x2/72)))) */
    long long r = (1 << 30) - x2 / 72;
    r = (1 << 30) - Q30_MUL(x2 / 42, r);
    r = (1 << 30) - Q30_MUL(x2 / 20, r);
    r = (1 << 30) - Q30_MUL(x2 / 6, r);
    return (s32)Q30_MUL(x, r);
}

/* Quarter-wave table, interpolated (lookup + interpolation as in
 * SaturnMath++ Trigonometry, at Q30 and 256 steps instead of its 16.16 and
 * 5.6-degree steps). Built at compile time from the series above, so no
 * runtime series, 64-bit divides or float. Interpolation error <= 5e-6. */
#define SIN_STEPS 256
struct SinQuadrant {
    s32 v[SIN_STEPS + 1];
    constexpr SinQuadrant() : v() {
        for (int i = 0; i <= SIN_STEPS; i++) {
            u32 inq = (u32)i << 22; /* 2^30 = pi/2 */
            v[i] = sin_q30_quadrant((s32)(((unsigned long long)inq * 0x6487ED51ULL) >> 30));
        }
    }
};
static constexpr SinQuadrant kSinQuadrant{};

/* inq: position in the quadrant, 2^30 = pi/2. Returns sin as Q30. */
static inline s32 sin_q30_lookup(u32 inq) {
    u32 i = inq >> 22;
    s32 a = kSinQuadrant.v[i];
    s32 d = kSinQuadrant.v[i + (i < SIN_STEPS)] - a;
    fx_raw p = fx_dmuls(d, (long)((inq >> 6) & 0xFFFF)); /* d * frac16 */
    return a + (s32)(((unsigned long)(p >> 32) << 16) | ((unsigned long)p >> 16));
}

/* b: binang * 2^16 (any sign, wraps per turn). Returns sin as Fx. */
static f32 sin_binang_q16(fx_raw b) {
    u32 turn = (u32)b; /* 2^32 per turn */
    u32 quadrant = turn >> 30;
    u32 inq = turn & 0x3FFFFFFF; /* position in quadrant, 2^30 = pi/2 */
    if (quadrant & 1) {
        inq = 0x40000000 - inq;
    }
    /* x = inq / 2^30 * pi/2, in Q30: inq * (pi/2) */
    s32 s = sin_q30_lookup(inq);
    if (quadrant & 2) {
        s = -s;
    }
    return Fx::raw((fx_raw)s >> (30 - FX_FRAC));
}

/* 32768/pi * 2^16 */
#define RAD_TO_BINANG_Q16 0x28BE60DBLL

/* Radians (Fx) -> binang * 2^16. |angle| < 128 rad takes one dmuls.l. */
static inline fx_raw rad_to_binang_q16(fx_raw v) {
    if (fx_fits32(v)) {
        return fx_sar_frac(fx_dmuls((long)v, (long)RAD_TO_BINANG_Q16));
    }
    return (v * RAD_TO_BINANG_Q16) >> FX_FRAC;
}

f32 sinf(f32 angle) {
    return sin_binang_q16(rad_to_binang_q16(angle.v));
}

f32 cosf(f32 angle) {
    return sin_binang_q16(rad_to_binang_q16(angle.v) + ((fx_raw)0x4000 << 16));
}

#define FX_FRAC_MASK (FX_ONE - 1)
#define FX_HALF (FX_ONE >> 1)
f32 floorf(f32 x) { return Fx::raw(x.v & ~FX_FRAC_MASK); }
f32 ceilf(f32 x) { return Fx::raw((x.v + FX_FRAC_MASK) & ~FX_FRAC_MASK); }
f32 truncf(f32 x) { return Fx(x.trunc()); }
f32 roundf(f32 x) {
    return x.v >= 0 ? Fx::raw((x.v + FX_HALF) & ~FX_FRAC_MASK) : -Fx::raw((-x.v + FX_HALF) & ~FX_FRAC_MASK);
}
/* Round half to even, like the default FPU mode. */
f32 nearbyintf(f32 x) {
    fx_raw whole = x.v & ~FX_FRAC_MASK;
    fx_raw frac = x.v & FX_FRAC_MASK;
    if (frac > FX_HALF || (frac == FX_HALF && (whole & FX_ONE))) {
        whole += FX_ONE;
    }
    return Fx::raw(whole);
}
long lfloorf(f32 x) { return (long)(x.v >> FX_FRAC); }
long lceilf(f32 x) { return (long)((x.v + FX_FRAC_MASK) >> FX_FRAC); }
long ltruncf(f32 x) { return (long)x.trunc(); }
long lroundf(f32 x) { return (long)(roundf(x).v >> FX_FRAC); }
long lnearbyintf(f32 x) { return (long)(nearbyintf(x).v >> FX_FRAC); }
#else
f32 sinf(f32 angle) { return __builtin_sinf(angle); }
f32 cosf(f32 angle) { return __builtin_cosf(angle); }
f32 floorf(f32 x) { return __builtin_floorf(x); }
f32 ceilf(f32 x) { return __builtin_ceilf(x); }
f32 truncf(f32 x) { return __builtin_truncf(x); }
f32 roundf(f32 x) { return __builtin_roundf(x); }
f32 nearbyintf(f32 x) { return __builtin_nearbyintf(x); }
long lfloorf(f32 x) { return (long)__builtin_floorf(x); }
long lceilf(f32 x) { return (long)__builtin_ceilf(x); }
long ltruncf(f32 x) { return (long)x; }
long lroundf(f32 x) { return (long)__builtin_roundf(x); }
long lnearbyintf(f32 x) { return (long)__builtin_nearbyintf(x); }
#endif
}
