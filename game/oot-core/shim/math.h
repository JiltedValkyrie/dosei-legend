/*
 * oot-core: replaces decomp include/libc/math.h. Same names, Fx-backed
 * implementations in oot-core/src/oot_math.cpp (no FPU, no soft-float).
 */
#ifndef MATH_H
#define MATH_H

#include "ultra64/ultratypes.h"

#define M_PI FXL(3.14159265358979323846f)
#define M_SQRT2 FXL(1.41421356237309504880f)
#define MAXFLOAT FXL(3.0e14) /* near the Fx (Q47.16) ceiling */
#define SHT_MAX FXL(32767.0f)
#define SHT_MINV FXL(1.0f / 32767.0f)

f32 floorf(f32);
f32 ceilf(f32);
f32 truncf(f32);
f32 roundf(f32);
f32 nearbyintf(f32);
long lfloorf(f32);
long lceilf(f32);
long ltruncf(f32);
long lroundf(f32);
long lnearbyintf(f32);

static inline f32 oot_fabsf(f32 f) {
#if OOT_CORE_HWFLOAT
    return __builtin_fabsf(f);
#else
    return f < 0.0f ? -f : f;
#endif
}
#define fabsf(f) oot_fabsf((f32)(f))
#define fabs(f) oot_fabsf((f32)(f))

f32 sqrtf(f32 f);
#define sqrt(f) sqrtf((f32)(f))

#endif
