/*
 * Squares without 64-bit math (Wave 0, 2026-10-05).
 *
 * Q16.16 Fx holds +/-32767, so SQ(d) saturates once d passes ~181 units.
 * The decomp's SQ/SQXZ/SQXYZ macros (importer rewrites z_math.h) therefore
 * return an FxSqExpr: up to three Fx terms whose squares are summed, kept
 * unscaled until the use decides the scale:
 *
 *   sqrtf(SQ(a) + SQ(b) + SQ(c))  -> scaled 32-bit hypot, full Fx range.
 *   SQ(r) < SQ(dx) + SQ(dz)       -> both sides scaled by one shared shift.
 *   SQ(a) + SQ(b) < 100.0f        -> the Fx operand is a squared value; it is
 *                                    compared as SQ(sqrtf(value)).
 *   anything else (1.0f - SQ(nx)) -> implicit Fx: the plain saturating sum,
 *                                    correct for small values (normals).
 *
 * Squares that the decomp STORES (xyzDistToPlayerSq, Math3D_*DistSq) still
 * pass through plain Fx and saturate past 32767 (181 units); they need their
 * own scaled type and matching consumers. That is tracked range-audit work,
 * not solved by this header.
 */
#ifndef OOT_CORE_FX_SQ_H
#define OOT_CORE_FX_SQ_H

#include "fx.h"

struct FxSqExpr {
    Fx c[3];
    int n;
    operator Fx() const {
        Fx r = Fx::raw(0);
        for (int i = 0; i < n; i++) {
            r = r + c[i] * c[i];
        }
        return r;
    }
};

/* Out of line in oot_math.cpp (code size). */
Fx sqrtf(Fx f);                                             /* shim math.h */
fx_uraw OotFx_Isqrt32(fx_uraw n);
Fx OotFx_SqRoot(const FxSqExpr& e);                         /* sqrt of the sum */
int OotFx_SqCompare(const FxSqExpr& l, const FxSqExpr& r);  /* -1, 0, 1 */
FxSqExpr OotFx_SqMerge(const FxSqExpr& l, const FxSqExpr& r);

/* Products of two coordinates (importer rewrites in sys_math3d.c): one
 * shared output shift keeps sign and ~30 significant bits, 32-bit only. */
Fx OotFx_Det2(Fx a, Fx b, Fx c, Fx d);       /* a * b - c * d */
Fx OotFx_DotRatio2(Fx a, Fx b, Fx c, Fx d);  /* (a * c + b * d) / (c * c + d * d) */
Fx OotFx_DotRatio3(Fx ax, Fx ay, Fx az, Fx bx, Fx by, Fx bz); /* (a . b) / (b . b) */
/* a x b, one shared shift; scaled uniformly when it exceeds Fx. */
void OotFx_Cross3(Fx ax, Fx ay, Fx az, Fx bx, Fx by, Fx bz, Fx* rx, Fx* ry, Fx* rz);
/* (s16)(x * k) with k = K / 2^16, wrapping like the N64 float -> s32 -> s16
 * store instead of saturating (RAD/DEG_TO_BINANG, Math_SinF/CosF). */
short OotFx_ScaleWrap16(Fx x, unsigned long K);

static inline FxSqExpr OotSq(Fx x) {
    FxSqExpr e;
    e.c[0] = x;
    e.n = 1;
    return e;
}
/* Integer SQ keeps C integer arithmetic. */
template <class T> static constexpr FX_IF_INT(T, decltype(T() * T())) OotSq(T x) { return x * x; }

static inline FxSqExpr operator+(const FxSqExpr& a, const FxSqExpr& b) { return OotFx_SqMerge(a, b); }
static inline Fx operator-(const FxSqExpr& a) { return -(Fx)a; }

static inline Fx sqrtf(const FxSqExpr& e) { return OotFx_SqRoot(e); }

/* A plain Fx compared with a square is itself a squared value. */
static inline int OotFx_SqCompareValue(const FxSqExpr& e, Fx v) {
    if (v.v < 0) {
        return 1;
    }
    return OotFx_SqCompare(e, OotSq(sqrtf(v)));
}

/*
 * A STORED squared value (the importer retypes every decomp `f32 ...Sq`
 * field, local, parameter and return to FxSq). It keeps the scaled terms,
 * so comparisons stay correct past 181 units, and it converts to plain Fx
 * only explicitly: every consumer that needs ordinary Q16.16 must say so.
 */
FxSqExpr OotFx_SqFromValue(Fx v);           /* v is a squared value */
FxSqExpr OotFx_SqFromInt(fx_uraw v);        /* integer squared value, never via Fx */
FxSqExpr OotFx_SqScale(const FxSqExpr& e, Fx k);
struct FxSq {
    FxSqExpr e;
    FxSq() = default;
    FxSq(const FxSqExpr& x) : e(x) {}
    FxSq(Fx v) : e(OotFx_SqFromValue(v)) {}
    /* Integer squares (ATTENTION_RANGES' SQ(350) = 122500) exceed Fx: keep
     * them integer and store the root. Negative values are empty. */
    template <class T, class = FX_IF_INT(T, void)> FxSq(T v) : e(from_int(v)) {}
    template <class T> static FxSqExpr from_int(T v) {
        bool neg = false;
        fx_uraw m = fx_int_mag(v, &neg);
        if (sizeof(T) > 4 && !neg && v > (T)0xFFFFFFFFu) {
            m = 0xFFFFFFFFu;
        } else if (sizeof(T) == 4 && (T)-1 > (T)0) {
            m = (fx_uraw)v;                      /* full unsigned 32-bit range */
        }
        return OotFx_SqFromInt(neg ? 0u : m);
    }
    explicit operator Fx() const { return (Fx)e; }
};
static inline Fx sqrtf(const FxSq& s) { return OotFx_SqRoot(s.e); }
static inline FxSq operator+(const FxSq& a, const FxSq& b) { return FxSq(OotFx_SqMerge(a.e, b.e)); }
static inline FxSq operator*(const FxSq& a, Fx k) { return FxSq(OotFx_SqScale(a.e, k)); }
static inline FxSq operator*(Fx k, const FxSq& a) { return FxSq(OotFx_SqScale(a.e, k)); }
/* A pending square times a factor, used as plain Fx (small values). */
static inline Fx operator*(const FxSqExpr& a, Fx k) { return (Fx)a * k; }
static inline Fx operator*(Fx k, const FxSqExpr& a) { return k * (Fx)a; }

/* IS_ZERO (importer rewrites z_math.h): exact for squares, no saturation. */
static inline bool OotIsZero(Fx f) { return fx_abs_u(f.v) < (fx_uraw)Fx(0.008f).v; }
static inline bool OotIsZero(const FxSqExpr& e) { return OotFx_SqCompareValue(e, Fx(0.008f)) < 0; }
static inline bool OotIsZero(const FxSq& s) { return OotIsZero(s.e); }
template <class T> static inline FX_IF_INT(T, bool) OotIsZero(T i) { return i == 0; }

/* COLPOLY_GET_NORMAL (importer rewrites bgcheck.h): s16 normal n / 32767 as
 * Q16, rounded. FXL(1.0f / 32767) truncates to 2 raw (n / 32768); this is
 * 2n + round(n / 16384), exact to half an ulp, shifts only. */
static inline Fx OotFx_Q15Normal(long n) {
    fx_raw m = (fx_raw)(n < 0 ? -n : n);
    m = 2 * m + ((m + 8192) >> 14);
    return Fx::raw(n < 0 ? -m : m);
}

#define FX_SQ_CMP(op)                                                                            \
    static inline bool operator op(const FxSqExpr& a, const FxSqExpr& b) { return OotFx_SqCompare(a, b) op 0; } \
    static inline bool operator op(const FxSqExpr& a, Fx b) { return OotFx_SqCompareValue(a, b) op 0; }        \
    static inline bool operator op(Fx a, const FxSqExpr& b) { return 0 op OotFx_SqCompareValue(b, a); }        \
    template <class T> static inline FX_IF_INT(T, bool) operator op(const FxSqExpr& a, T b) { return a op Fx(b); } \
    template <class T> static inline FX_IF_INT(T, bool) operator op(T a, const FxSqExpr& b) { return Fx(a) op b; }
FX_SQ_CMP(<) FX_SQ_CMP(>) FX_SQ_CMP(<=) FX_SQ_CMP(>=) FX_SQ_CMP(==) FX_SQ_CMP(!=)
#undef FX_SQ_CMP
#define FX_SQS_CMP(op)                                                                                   \
    static inline bool operator op(const FxSq& a, const FxSq& b) { return OotFx_SqCompare(a.e, b.e) op 0; }     \
    static inline bool operator op(const FxSq& a, const FxSqExpr& b) { return OotFx_SqCompare(a.e, b) op 0; }   \
    static inline bool operator op(const FxSqExpr& a, const FxSq& b) { return OotFx_SqCompare(a, b.e) op 0; }   \
    static inline bool operator op(const FxSq& a, Fx b) { return OotFx_SqCompareValue(a.e, b) op 0; }           \
    static inline bool operator op(Fx a, const FxSq& b) { return 0 op OotFx_SqCompareValue(b.e, a); }           \
    template <class T> static inline FX_IF_INT(T, bool) operator op(const FxSq& a, T b) { return a op Fx(b); } \
    template <class T> static inline FX_IF_INT(T, bool) operator op(T a, const FxSq& b) { return Fx(a) op b; }
FX_SQS_CMP(<) FX_SQS_CMP(>) FX_SQS_CMP(<=) FX_SQS_CMP(>=) FX_SQS_CMP(==) FX_SQS_CMP(!=)
#undef FX_SQS_CMP

#endif
