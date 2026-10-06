/*
 * oot-core Fx math runtime: the libc/libultra float primitives the decomp
 * calls, rebuilt on 32-bit integers for the FPU-less SH-2 (no 64-bit
 * runtime math since Wave 0, 2026-10-05). Game-side math
 * (sys_math*.c, z_lib.c, math64.c, sins/coss) is the real decomp code.
 */
#include "oot_prelude.h"
#include "ultra64.h"

extern "C++" {

#if !OOT_CORE_HWFLOAT
/* floor(sqrt(n)) for a 32-bit n: bit-by-bit, 16 rounds, 32-bit only. */
fx_uraw OotFx_Isqrt32(fx_uraw n) {
    fx_uraw res = 0;
    fx_uraw bit = 1u << 30;
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
    return res;
}
#define isqrt32 OotFx_Isqrt32

/* fx.h runtime ops, out of line for blob size. */
fx_raw OotFx_Mul(fx_raw a, fx_raw b) { return fx_mul_fold(a, b); }
fx_raw OotFx_MulInt(fx_raw a, fx_uraw ub, bool nb) {
    return fx_signed(fx_muli_u(fx_abs_u(a), ub), (a < 0) != nb);
}
fx_raw OotFx_Div(fx_raw a, fx_raw b) { return fx_div_fold(a, b); }
fx_raw OotFx_IntDiv(fx_uraw ua, bool na, fx_raw b) {
    return fx_signed(fx_div_u(ua, 2 * FX_FRAC, fx_abs_u(b)), na != (b < 0));
}
fx_raw OotFx_DivInt(fx_raw a, fx_uraw ub, bool nb) {
    return fx_signed(fx_abs_u(a) / ub, (a < 0) != nb);
}

/*
 * FxSqExpr (fx_sq.h): sums of up to three squares, scaled so no product
 * leaves 32 bits. One shift k brings the largest |term| below 2^14, so
 * each square is < 2^28 and six of them still fit 31 bits.
 */
static int sq_shift(const FxSqExpr& a, const FxSqExpr* b) {
    fx_uraw m = 0;
    for (int i = 0; i < a.n; i++) {
        m |= fx_abs_u(a.c[i].v);
    }
    for (int i = 0; b && i < b->n; i++) {
        m |= fx_abs_u(b->c[i].v);
    }
    int bits = 32 - fx_clz(m);
    return bits > 14 ? bits - 14 : 0;
}

static fx_uraw sq_sum(const FxSqExpr& e, int k) {
    fx_uraw s = 0;
    for (int i = 0; i < e.n; i++) {
        fx_uraw u = fx_abs_u(e.c[i].v) >> k;
        s += u * u;
    }
    return s;
}

/* |a| * |b| >> sh (16 <= sh < 64); the caller picks sh so the result fits 32
 * bits. Native dmulu.l product, shifted as two 32-bit words (a variable
 * 64-bit shift would call a libgcc helper). */
static fx_uraw mul_shr(fx_uraw a, fx_uraw b, int sh) {
    fx_uraw hi, lo;
#if defined(__sh__)
    __asm__("dmulu.l %2,%3\n\tsts mach,%0\n\tsts macl,%1"
            : "=&r"(hi), "=&r"(lo) : "r"(a), "r"(b) : "mach", "macl");
#else
    unsigned long long p = (unsigned long long)a * b;
    hi = (fx_uraw)(p >> 32);
    lo = (fx_uraw)p;
#endif
    return sh >= 32 ? hi >> (sh - 32) : (hi << (32 - sh)) | (lo >> sh);
}

static int bits_of(fx_uraw v) {
    return 32 - fx_clz(v);
}

/* Shift so a product of operands with `bits` total bits stays below 2^30. */
static int prod_shift(int bits) {
    return bits - 30 > FX_FRAC ? bits - 30 : FX_FRAC;
}

Fx OotFx_Det2(Fx a, Fx b, Fx c, Fx d) {
    fx_uraw ua = fx_abs_u(a.v), ub = fx_abs_u(b.v), uc = fx_abs_u(c.v), ud = fx_abs_u(d.v);
    int b1 = bits_of(ua) + bits_of(ub), b2 = bits_of(uc) + bits_of(ud);
    int sh = prod_shift(b1 > b2 ? b1 : b2);
    fx_raw p1 = (fx_raw)mul_shr(ua, ub, sh), p2 = (fx_raw)mul_shr(uc, ud, sh);
    if ((a.v < 0) != (b.v < 0)) {
        p1 = -p1;
    }
    if ((c.v < 0) != (d.v < 0)) {
        p2 = -p2;
    }
    fx_raw diff = p1 - p2;                 /* |p| < 2^30: no overflow */
    int up = sh - FX_FRAC;
    if (up > 0 && fx_abs_u(diff) > ((fx_uraw)FX_MAX >> up)) {
        return Fx::raw(fx_sat(diff < 0));
    }
    return Fx::raw(diff << up);
}

Fx OotFx_DotRatio2(Fx a, Fx b, Fx c, Fx d) {
    fx_uraw ua = fx_abs_u(a.v), ub = fx_abs_u(b.v), uc = fx_abs_u(c.v), ud = fx_abs_u(d.v);
    int top = bits_of(ua) + bits_of(uc);
    int m = bits_of(ub) + bits_of(ud);
    if (m > top) top = m;
    m = 2 * bits_of(uc > ud ? uc : ud);
    if (m > top) top = m;
    int sh = prod_shift(top + 1);         /* sums of two terms stay < 2^30 */
    fx_raw ac = (fx_raw)mul_shr(ua, uc, sh), bd = (fx_raw)mul_shr(ub, ud, sh);
    if ((a.v < 0) != (c.v < 0)) ac = -ac;
    if ((b.v < 0) != (d.v < 0)) bd = -bd;
    fx_raw num = ac + bd;
    fx_uraw den = mul_shr(uc, uc, sh) + mul_shr(ud, ud, sh);
    if (den == 0) {
        return Fx::raw(fx_sat(num < 0));
    }
    return Fx::raw(num == 0 ? 0 : fx_signed(fx_div_u(fx_abs_u(num), FX_FRAC, den), num < 0));
}

/*
 * a x b with ONE shift for all six products (Math3D_Vec3f_Cross, importer).
 * (300,0,300) x (300,0,600) has y = -90000: per-product saturation made it
 * 0. Each component keeps sign and ~30 bits; when any exceeds Fx, all three
 * are scaled down by the same power of two (direction kept). Every decomp
 * caller normalizes the result (Math3D_SurfaceNorm users) or passes unit
 * normals (plane intersection, never scaled).
 */
void OotFx_Cross3(Fx ax, Fx ay, Fx az, Fx bx, Fx by, Fx bz, Fx* rx, Fx* ry, Fx* rz) {
    const Fx* p[6][2] = { { &ay, &bz }, { &az, &by }, { &az, &bx }, { &ax, &bz }, { &ax, &by }, { &ay, &bx } };
    int top = 0;
    for (int i = 0; i < 6; i++) {
        int m = bits_of(fx_abs_u(p[i][0]->v)) + bits_of(fx_abs_u(p[i][1]->v));
        if (m > top) top = m;
    }
    int sh = prod_shift(top);
    fx_raw d[3];
    fx_uraw big = 0;
    for (int c = 0; c < 3; c++) {
        fx_raw t[2];
        for (int j = 0; j < 2; j++) {
            const Fx* u = p[2 * c + j][0];
            const Fx* w = p[2 * c + j][1];
            t[j] = (fx_raw)mul_shr(fx_abs_u(u->v), fx_abs_u(w->v), sh);
            if ((u->v < 0) != (w->v < 0)) t[j] = -t[j];
        }
        d[c] = t[0] - t[1];                /* |t| < 2^30 */
        big |= fx_abs_u(d[c]);
    }
    int up = sh - FX_FRAC;
    if (up > 0 && big > ((fx_uraw)FX_MAX >> up)) {
        up = 0;                            /* uniform 2^-(sh-16) scale */
    }
    *rx = Fx::raw(d[0] << up);
    *ry = Fx::raw(d[1] << up);
    *rz = Fx::raw(d[2] << up);
}

Fx OotFx_DotRatio3(Fx ax, Fx ay, Fx az, Fx bx, Fx by, Fx bz) {
    fx_uraw ua[3] = { fx_abs_u(ax.v), fx_abs_u(ay.v), fx_abs_u(az.v) };
    fx_uraw ub[3] = { fx_abs_u(bx.v), fx_abs_u(by.v), fx_abs_u(bz.v) };
    bool neg[3] = { (ax.v < 0) != (bx.v < 0), (ay.v < 0) != (by.v < 0), (az.v < 0) != (bz.v < 0) };
    int top = 0;
    for (int i = 0; i < 3; i++) {
        int m = bits_of(ua[i]) + bits_of(ub[i]);
        if (m > top) top = m;
        m = 2 * bits_of(ub[i]);
        if (m > top) top = m;
    }
    int sh = prod_shift(top + 2);         /* sums of three terms stay < 2^30 */
    fx_raw num = 0;
    fx_uraw den = 0;
    for (int i = 0; i < 3; i++) {
        fx_raw p = (fx_raw)mul_shr(ua[i], ub[i], sh);
        num += neg[i] ? -p : p;
        den += mul_shr(ub[i], ub[i], sh);
    }
    if (den == 0) {
        return Fx::raw(fx_sat(num < 0));
    }
    return Fx::raw(num == 0 ? 0 : fx_signed(fx_div_u(fx_abs_u(num), FX_FRAC, den), num < 0));
}

short OotFx_ScaleWrap16(Fx x, unsigned long K) {
    /* bits 32..47 of |x.v| * K from 16-bit partial products; carries out of
     * the middle sum only reach bit 48+, which the s16 result drops. */
    fx_uraw u = fx_abs_u(x.v), uh = u >> 16, ul = u & 0xFFFFu;
    fx_uraw kh = (fx_uraw)K >> 16, kl = (fx_uraw)K & 0xFFFFu;
    fx_uraw mid = uh * kl + ul * kh;
    mid += (ul * kl) >> 16;
    fx_uraw r = (uh * kh + (mid >> 16)) & 0xFFFFu;
    return (short)(x.v < 0 ? 0u - r : r);
}

Fx OotFx_SqRoot(const FxSqExpr& e) {
    int k = sq_shift(e, 0);
    fx_uraw s = sq_sum(e, k);
    if (s == 0) {
        return Fx::raw(0);
    }
    int sh = fx_clz(s) & ~1;               /* more root bits: sqrt(s * 2^sh) */
    fx_uraw root = isqrt32(s << sh);
    int net = k - sh / 2;                  /* raw = root * 2^k / 2^(sh / 2) */
    if (net >= 0) {
        if (root > ((fx_uraw)FX_MAX >> net)) {
            return Fx::raw(fx_sat(false));
        }
        return Fx::raw((fx_raw)(root << net));
    }
    return Fx::raw((fx_raw)(root >> -net));
}

int OotFx_SqCompare(const FxSqExpr& l, const FxSqExpr& r) {
    int k = sq_shift(l, &r);
    fx_uraw a = sq_sum(l, k), b = sq_sum(r, k);
    return a < b ? -1 : a > b;
}

/* A squared VALUE as one term: sqrt(v); saturated (MAXFLOAT, 1e38f
 * sentinels) stays the largest square; zero or negative is empty. */
FxSqExpr OotFx_SqFromValue(Fx v) {
    FxSqExpr e;
    e.n = v.v > 0;
    e.c[0] = v.v >= FX_MAX ? Fx::raw(FX_MAX) : sqrtf(v);
    return e;
}

/* An integer squared value: root = sqrt(v) with up to 16 fraction bits,
 * 32-bit isqrt only. Roots past Fx (v >= 2^30) become two terms of
 * sqrt(v / 2), each clamped to FX_MAX (2^32 - 1 tops out ~0.3% low). */
FxSqExpr OotFx_SqFromInt(fx_uraw v) {
    FxSqExpr e;
    e.n = 0;
    if (v == 0) {
        return e;
    }
    int twice = v >= (1u << 30);
    if (twice) {
        v >>= 1;
    }
    int s = fx_clz(v) & ~1;                /* v << s fits; s <= 30 */
    fx_uraw root = isqrt32(v << s);        /* sqrt(v) * 2^(s / 2) */
    int up = FX_FRAC - s / 2;              /* >= 1 */
    e.c[0] = Fx::raw(root > ((fx_uraw)FX_MAX >> up) ? FX_MAX : (fx_raw)(root << up));
    e.c[1] = e.c[0];
    e.n = twice ? 2 : 1;
    return e;
}

/* e * k (k >= 0) scales each term by sqrt(k). */
FxSqExpr OotFx_SqScale(const FxSqExpr& e, Fx k) {
    FxSqExpr r = e;
    Fx s = k.v > 0 ? sqrtf(k) : Fx::raw(0);
    for (int i = 0; i < r.n; i++) {
        r.c[i] = r.c[i] * s;
    }
    return r;
}

FxSqExpr OotFx_SqMerge(const FxSqExpr& l, const FxSqExpr& r) {
    FxSqExpr a = l, b = r;
    if (a.n + b.n > 3 && a.n > 1) {        /* sum of squares == SQ(hypot) */
        a.c[0] = OotFx_SqRoot(a);
        a.n = 1;
    }
    if (a.n + b.n > 3) {
        b.c[0] = OotFx_SqRoot(b);
        b.n = 1;
    }
    for (int i = 0; i < b.n; i++) {
        a.c[a.n++] = b.c[i];
    }
    return a;
}
#endif

f32 sqrtf(f32 f) {
#if OOT_CORE_HWFLOAT
    return __builtin_sqrtf(f);
#else
    if (f.v <= 0) {
        return Fx::raw(0);
    }
    /* sqrt(v / 2^16) * 2^16 == sqrt(v * 2^16). Shift v left by the largest
     * even s <= 16 that fits 32 bits, then scale the root by 2^((16 - s) / 2).
     * v < 1.0 is exact; larger values keep >= 15 significant bits. */
    fx_uraw v = (fx_uraw)f.v;
    int s = fx_clz(v) & ~1;
    if (s > FX_FRAC) {
        s = FX_FRAC;
    }
    return Fx::raw((fx_raw)(isqrt32(v << s) << ((FX_FRAC - s) / 2)));
#endif
}

#if !OOT_CORE_HWFLOAT
/*
 * libultra sinf/cosf are float polynomials; same idea on integers. Radians
 * -> binang with a 16-bit fraction (a u32 turn), fold to one quadrant, then
 * an interpolated quarter-wave table in Q30. All runtime work is 32-bit.
 * (The sins() table is NOT used: it samples i*pi/(2*1023), so interpolating
 * it at 16-binang steps is biased by up to one step.)
 */
#define Q30_MUL(a, b) (((long long)(a) * (b)) >> 30)

/* sin(x) for x in [0, pi/2] as Q30. Compile time only: fills the table. */
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
 * SaturnMath++ Trigonometry, at Q30 and 256 steps). Built at compile time
 * from the series above (constexpr only; no runtime 64-bit work). */
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

/* inq: position in the quadrant, 2^30 = pi/2. Returns sin as Q30. A table
 * step is < 2^23, so (step >> 8) * frac16 < 2^31: one 32-bit multiply. */
static inline s32 sin_q30_lookup(u32 inq) {
    u32 i = inq >> 22;
    s32 a = kSinQuadrant.v[i];
    s32 d = kSinQuadrant.v[i + (i < SIN_STEPS)] - a;
    s32 frac16 = (s32)((inq >> 6) & 0xFFFF);
    return a + (((d >> 8) * frac16) >> 8);
}

/* turn: binang * 2^16 (2^32 per turn, wraps). Returns sin as Fx. */
static f32 sin_turn(u32 turn) {
    u32 quadrant = turn >> 30;
    u32 inq = turn & 0x3FFFFFFF; /* position in quadrant, 2^30 = pi/2 */
    if (quadrant & 1) {
        inq = 0x40000000 - inq;
    }
    s32 s = sin_q30_lookup(inq);
    if (quadrant & 2) {
        s = -s;
    }
    return Fx::raw(s >> (30 - FX_FRAC));
}

/* Radians (Q16) -> binang * 2^16, mod 2^32: bits 16..47 of |v| * K with
 * K = 32768/pi * 2^16, from 16-bit partial products (wrapping on purpose:
 * the angle is periodic). */
#define RAD_TO_TURN_K 0x28BE60DBu
static inline u32 rad_to_turn(fx_raw v) {
    u32 u = fx_abs_u(v);
    u32 uh = u >> 16, ul = u & 0xFFFF;
    u32 kh = RAD_TO_TURN_K >> 16, kl = RAD_TO_TURN_K & 0xFFFF;
    u32 t = ((uh * kh) << 16) + uh * kl + ul * kh + ((ul * kl) >> 16);
    return v < 0 ? 0u - t : t;
}

f32 sinf(f32 angle) {
    return sin_turn(rad_to_turn(angle.v));
}

f32 cosf(f32 angle) {
    return sin_turn(rad_to_turn(angle.v) + 0x40000000u);
}

#define FX_FRAC_MASK (FX_ONE - 1)
#define FX_HALF (FX_ONE >> 1)
f32 floorf(f32 x) { return Fx::raw(x.v & ~FX_FRAC_MASK); }
f32 ceilf(f32 x) { return Fx::raw(fx_add_raw(x.v, FX_FRAC_MASK) & ~FX_FRAC_MASK); }
f32 truncf(f32 x) { return Fx(x.trunc()); }
f32 roundf(f32 x) {
    return x.v >= 0 ? Fx::raw(fx_add_raw(x.v, FX_HALF) & ~FX_FRAC_MASK)
                    : -Fx::raw(fx_add_raw(-x.v, FX_HALF) & ~FX_FRAC_MASK);
}
/* Round half to even, like the default FPU mode. */
f32 nearbyintf(f32 x) {
    fx_raw whole = x.v & ~FX_FRAC_MASK;
    fx_raw frac = x.v & FX_FRAC_MASK;
    if (frac > FX_HALF || (frac == FX_HALF && (whole & FX_ONE))) {
        whole = fx_add_raw(whole, FX_ONE) & ~FX_FRAC_MASK;
    }
    return Fx::raw(whole);
}
long lfloorf(f32 x) { return (long)(x.v >> FX_FRAC); }
long lceilf(f32 x) { return (long)(ceilf(x).v >> FX_FRAC); }
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

/*
 * Cylinder side test (Math3D_CylVsLineSeg, CollisionCheck_CylSideVsLineSeg):
 * the decomp solves |a + t d|^2 = r^2 in XZ from (2 a.d)^2 - 4 |d|^2 (|a|^2 - r^2),
 * fourth powers of coordinates. Same roots from the closest approach
 * t0 = -a.d / |d|^2, its distance h and the half chord sqrt((r - h)(r + h)) / |d|:
 * every intermediate stays a coordinate-sized value. Both builds.
 */
long OotFx_LineVsCircleXZ(f32 ax, f32 az, f32 dx, f32 dz, f32 r, f32* fracA, f32* fracB) {
    f32 t0 = -OotFx_DotRatio2(ax, az, dx, dz);
    f32 cx = ax + dx * t0;
    f32 cz = az + dz * t0;
    f32 h = sqrtf(OOT_SQ(cx) + OOT_SQ(cz));
    if (h > r) {
        return 0;
    }
    f32 half = sqrtf(r - h) * sqrtf(r + h);
    f32 dt = half / sqrtf(OOT_SQ(dx) + OOT_SQ(dz));
    *fracA = t0 + dt;
    *fracB = t0 - dt;
    return half > 0 ? 2 : 1;
}

f32 OotFx_RadSqDiffXZ(f32 ax, f32 az, f32 r) {
    f32 h = sqrtf(OOT_SQ(ax) + OOT_SQ(az));
    return (h - r) * (h + r);
}
}
