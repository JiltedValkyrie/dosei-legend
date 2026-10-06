/*
 * oot-core prelude: force-included ahead of every imported decomp file.
 *
 * Decomp C is compiled as C++ so `float` can become the fixed-point Fx type
 * without touching game logic. C++ keywords used as C identifiers in the
 * decomp (`this`, `new`, ...) are renamed here, AFTER fx.h, so they never
 * reach a header that needs the real keyword.
 *
 * OOT_CORE_HWFLOAT=1 keeps real float (host reference build for diffing).
 */
#ifndef OOT_PRELUDE_H
#define OOT_PRELUDE_H

#if !OOT_CORE_HWFLOAT
#include "fx.h"
#include "fx_sq.h"
#define OOT_SQ(x) OotSq(x)
#define OOT_IS_ZERO(f) OotIsZero(f)
#define OOT_Q15_NORMAL(n) OotFx_Q15Normal(n)
#define float Fx
#define double Fx
/* The importer wraps every floating literal: FXL(0.5f) is an Fx constant. */
#define FXL(lit) (Fx(lit))
#else
#define FXL(lit) (lit)
#define OOT_SQ(x) ((x) * (x))
#define OOT_IS_ZERO(f) (fabsf(f) < 0.008f)
#define OOT_Q15_NORMAL(n) ((n) * COLPOLY_NORMAL_FRAC)
typedef float FxSq;
#define OotFx_Det2(a, b, c, d) (((a) * (b)) - ((c) * (d)))
#define OotFx_ScaleWrap16(x, K) ((short)(long)((x) * ((K) / 65536.0f)))
#define OotFx_DotRatio2(a, b, c, d) ((((a) * (c)) + ((b) * (d))) / (((c) * (c)) + ((d) * (d))))
#define OotFx_Cross3(ax, ay, az, bx, by, bz, rx, ry, rz)                                        \
    (*(rx) = ((ay) * (bz)) - ((az) * (by)), *(ry) = ((az) * (bx)) - ((ax) * (bz)), \
     *(rz) = ((ax) * (by)) - ((ay) * (bx)))
#define OotFx_DotRatio3(ax, ay, az, bx, by, bz) \
    ((((ax) * (bx)) + ((ay) * (by)) + ((az) * (bz))) / (((bx) * (bx)) + ((by) * (by)) + ((bz) * (bz))))
#endif

/* Importer fix_rand_ranges targets (oot_rand.cpp): random ranges past Fx. */
long OotRand_ZeroOneTimes(unsigned long n); /* s32(u32) */
long OotRand_CenteredTimes(unsigned long n);
/* Bounded XZ segment-vs-circle roots for the cylinder quadratics (importer
 * rewrites in sys_math3d.c / z_collision_check.c; oot_math.cpp, both modes).
 * Returns 0 (no side hit), 1 (tangent) or 2; fracA = larger root. */
long OotFx_LineVsCircleXZ(float ax, float az, float dx, float dz, float r, float* fracA, float* fracB);
float OotFx_RadSqDiffXZ(float ax, float az, float r); /* |a|^2 - r^2, as (|a| - r)(|a| + r) */

/*
 * C `c ? a : b` with mixed int/Fx operands converts to float; in C++ the
 * implicit conversions both ways make it ambiguous. OOT_SEL casts both arms
 * to the C common type (Fx wins) and still evaluates only one arm.
 */
template <class T> struct oot_decay { typedef T type; };
template <class T> struct oot_decay<T&> { typedef T type; };
template <class T> struct oot_decay<const T> { typedef T type; };
template <class T> struct oot_decay<const T&> { typedef T type; };
template <class T> struct oot_decay<volatile T> { typedef T type; };
template <class T> struct oot_decay<volatile T&> { typedef T type; };
template <class T> T oot_declval();
template <class A, class B> struct oot_common {
    typedef decltype(true ? oot_declval<A>() : oot_declval<B>()) type;
};
#if !OOT_CORE_HWFLOAT
template <class A> struct oot_common<A, Fx> { typedef Fx type; };
template <class B> struct oot_common<Fx, B> { typedef Fx type; };
template <> struct oot_common<Fx, Fx> { typedef Fx type; };
#endif
/* No `typename` in these: the keyword is macro-renamed below. */
#define OOT_COMMON_T(a, b) oot_common<oot_decay<decltype(a)>::type, oot_decay<decltype(b)>::type>::type
#define OOT_SEL(c, a, b) ((c) ? (OOT_COMMON_T(a, b))(a) : (OOT_COMMON_T(a, b))(b))

#define this thisx_
#define new new_
#define delete delete_
#define class class_
#define template template_
#define private private_
#define public public_
#define protected protected_
#define operator operator_
#define namespace namespace_
#define typename typename_
#define virtual virtual_
#define friend friend_
#define mutable mutable_
#define explicit explicit_
#define export export_

#endif
