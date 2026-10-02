/*
 * Fx: fixed-point stand-in for N64 `float` on the FPU-less SH-2.
 *
 * Storage is int64 with 24 fraction bits (Q39.24). The decomp freely builds
 * floats far beyond s16 range (Rand_ZeroOne() * 0xFFFF angles, squared
 * distances ~1e8), so a 32-bit Q16.16 saturates in ordinary gameplay code.
 * 16 fraction bits also proved too coarse: reciprocals such as 1/|normal|
 * (~1e-4) lost 6% (host probe, Math3D_DefPlane). Q39.24 gives range +/-5e11
 * and 6e-8 steps; Rand_ZeroOne's 23 mantissa bits map exactly.
 *
 * Cost control: operands are split at 32 bits. Both small -> one SH-2
 * dmuls.l; one small -> two; otherwise four. Division uses int64.
 *
 * Semantics follow C float rules the decomp relies on:
 *   - implicit conversion to integers truncates toward zero, then narrows
 *     (matches MIPS trunc.w.s + halfword store for out-of-range values);
 *   - mixed Fx/integer arithmetic promotes the integer to Fx.
 *
 * The prelude macro-renames `float`/`double` to Fx AFTER this header, so the
 * hardware types are spelled with decltype here. Constructors from float are
 * constexpr: literals fold at compile time and must never emit soft-float
 * calls on target (verify with objdump: no __addsf3, __muldf3 etc.).
 */
#ifndef OOT_CORE_FX_H
#define OOT_CORE_FX_H

typedef decltype(0.0f) fx_hwfloat;
typedef decltype(0.0) fx_hwdouble;
typedef long long fx_raw;

#define FX_FRAC 24
#define FX_ONE ((fx_raw)1 << FX_FRAC)

template <class T> struct fx_is_int { static constexpr bool value = false; };
#define FX_INT_TYPE(t) template <> struct fx_is_int<t> { static constexpr bool value = true; };
FX_INT_TYPE(bool) FX_INT_TYPE(char) FX_INT_TYPE(signed char) FX_INT_TYPE(unsigned char)
FX_INT_TYPE(short) FX_INT_TYPE(unsigned short) FX_INT_TYPE(int) FX_INT_TYPE(unsigned int)
FX_INT_TYPE(long) FX_INT_TYPE(unsigned long) FX_INT_TYPE(long long) FX_INT_TYPE(unsigned long long)
#undef FX_INT_TYPE
template <bool B, class T = void> struct fx_enable_if {};
template <class T> struct fx_enable_if<true, T> { typedef T type; };
#define FX_IF_INT(T, R) typename fx_enable_if<fx_is_int<T>::value, R>::type

struct Fx {
    fx_raw v;

    Fx() = default;
    constexpr Fx(fx_hwfloat f) : v((fx_raw)((fx_hwdouble)f * (fx_hwdouble)FX_ONE)) {}
    constexpr Fx(fx_hwdouble d) : v((fx_raw)(d * (fx_hwdouble)FX_ONE)) {}
    template <class T, class = FX_IF_INT(T, void)>
    constexpr Fx(T i) : v((fx_raw)i * FX_ONE) {}

    static constexpr Fx raw(fx_raw r) {
        Fx x{};
        x.v = r;
        return x;
    }

    /* Float->int truncates toward zero, like C/MIPS trunc.w.s. */
    constexpr fx_raw trunc() const { return v >= 0 ? (v >> FX_FRAC) : -((-v) >> FX_FRAC); }
    template <class T, class = FX_IF_INT(T, void)>
    constexpr operator T() const { return (T)trunc(); }
    /* Host reference/debug only: never call on target hot paths. */
    explicit constexpr operator fx_hwfloat() const { return (fx_hwfloat)((fx_hwdouble)v / (fx_hwdouble)FX_ONE); }

    constexpr Fx operator-() const { return raw(-v); }
    constexpr Fx operator+() const { return *this; }
    constexpr bool operator!() const { return v == 0; }
};

static constexpr bool fx_fits32(fx_raw r) { return (fx_raw)(long)r == r; }

/* |a| * b where b fits 32 bits: two 32x32->64 multiplies. */
static constexpr fx_raw fx_mul_wide32(fx_raw a, long b) {
    unsigned long long ua = a < 0 ? -(unsigned long long)a : (unsigned long long)a;
    long long hi = (long long)(long)(ua >> 32) * b;            /* weight 2^32 */
    long long lo_u = (long long)((unsigned long long)(unsigned long)ua * (unsigned long long)(b < 0 ? -(long long)b : b));
    long long lo = b < 0 ? -lo_u : lo_u;
    fx_raw r = (fx_raw)(hi * ((fx_raw)1 << (32 - FX_FRAC))) + (lo >> FX_FRAC);
    return a < 0 ? -r : r;
}

static constexpr Fx fx_mul(Fx a, Fx b) {
    bool sa = fx_fits32(a.v), sb = fx_fits32(b.v);
    if (__builtin_expect(sa && sb, 1)) {
        return Fx::raw(((fx_raw)(long)a.v * (long)b.v) >> FX_FRAC);
    }
    if (sb) {
        return Fx::raw(fx_mul_wide32(a.v, (long)b.v));
    }
    if (sa) {
        return Fx::raw(fx_mul_wide32(b.v, (long)a.v));
    }
    /* Both large: middle bits of the 128-bit product. */
    bool neg = (a.v < 0) != (b.v < 0);
    unsigned long long ua = a.v < 0 ? -(unsigned long long)a.v : (unsigned long long)a.v;
    unsigned long long ub = b.v < 0 ? -(unsigned long long)b.v : (unsigned long long)b.v;
    unsigned long long al = (unsigned long)ua, ah = ua >> 32;
    unsigned long long bl = (unsigned long)ub, bh = ub >> 32;
    unsigned long long r = ((ah * bh) << (64 - FX_FRAC)) + ((ah * bl + al * bh) << (32 - FX_FRAC)) +
                           ((al * bl) >> FX_FRAC);
    return Fx::raw(neg ? -(fx_raw)r : (fx_raw)r);
}

#if defined(__sh__) && !defined(OOT_CORE_NO_DIVU)
/*
 * SH-2 on-chip divider: signed 64/32 -> 32 in ~39 cycles, vs hundreds for
 * libgcc __divdi3. Register use follows SaturnMath++ (MIT, (c) 2024 Roberto
 * Daniel Alves Duarte, impl/fxp.hpp AsyncDivSet): DVSR, DVDNTH, then writing
 * DVDNTL starts the divide; reading DVDNTL waits for the quotient.
 * Not interrupt-safe if an interrupt handler also uses the divider.
 */
/* GCC 9+ has __builtin_is_constant_evaluated; Jo's Linux GCC 8.2 does not.
 * There, a compile-time-constant operand pair keeps the pure path. */
#if __GNUC__ >= 9
#define FX_RUNTIME(a, b) (!__builtin_is_constant_evaluated())
#else
#define FX_RUNTIME(a, b) (!(__builtin_constant_p(a) && __builtin_constant_p(b)))
#endif
#define FX_DVSR (*(volatile long*)0xFFFFFF00UL)
#define FX_DVDNTH (*(volatile long*)0xFFFFFF10UL)
#define FX_DVDNTL (*(volatile long*)0xFFFFFF14UL)
static inline fx_raw fx_divu64_32(fx_raw n, long d) {
    FX_DVSR = d;
    FX_DVDNTH = (long)(n >> 32);
    FX_DVDNTL = (long)(unsigned long)n;
    return (fx_raw)FX_DVDNTL;
}
#endif

/* Inline so constant/constant (e.g. 1.0f / SHT_MAX) folds at compile time. */
static constexpr Fx fx_div(Fx a, Fx b) {
    if (b.v == 0) {
        /* N64 float gives +/-inf; keep the sign with a huge value. */
        return Fx::raw(a.v < 0 ? -((fx_raw)1 << 62) : ((fx_raw)1 << 62));
    }
    fx_raw ua = a.v < 0 ? -a.v : a.v;
#if defined(__sh__) && !defined(OOT_CORE_NO_DIVU)
    if (FX_RUNTIME(a.v, b.v) && fx_fits32(b.v)) {
        /* Hardware path when the Q24 quotient fits 32 bits:
         * |a / b| < 2^(31 - FX_FRAC)  <=>  |a.v| < |b.v| << 7 (with margin). */
        fx_raw ub = b.v < 0 ? -b.v : b.v;
        if (ua < (ub << (31 - FX_FRAC - 1))) {
            return Fx::raw(fx_divu64_32(a.v * FX_ONE, (long)b.v));
        }
    }
#endif
    if (ua < ((fx_raw)1 << (62 - FX_FRAC))) {
        return Fx::raw((a.v * FX_ONE) / b.v);
    }
    /* Huge numerator: pre-shift as far as it fits, finish after dividing. */
    int s = 0;
    while (s < FX_FRAC && ua < ((fx_raw)1 << 61)) {
        ua <<= 1;
        s++;
    }
    return Fx::raw(((a.v * ((fx_raw)1 << s)) / b.v) * ((fx_raw)1 << (FX_FRAC - s)));
}

static constexpr Fx operator+(Fx a, Fx b) { return Fx::raw(a.v + b.v); }
static constexpr Fx operator-(Fx a, Fx b) { return Fx::raw(a.v - b.v); }
static constexpr Fx operator*(Fx a, Fx b) { return fx_mul(a, b); }
static constexpr Fx operator/(Fx a, Fx b) { return fx_div(a, b); }
constexpr bool operator<(Fx a, Fx b) { return a.v < b.v; }
constexpr bool operator>(Fx a, Fx b) { return a.v > b.v; }
constexpr bool operator<=(Fx a, Fx b) { return a.v <= b.v; }
constexpr bool operator>=(Fx a, Fx b) { return a.v >= b.v; }
constexpr bool operator==(Fx a, Fx b) { return a.v == b.v; }
constexpr bool operator!=(Fx a, Fx b) { return a.v != b.v; }

/* Mixed Fx/integer: exact-match templates beat the builtin int operators that
 * the implicit integer conversion would otherwise make ambiguous. Integer
 * multiply/divide skip the fixed-point rescale. */
#define FX_MIXED(op, expr_fi, expr_if)                                                    \
    template <class T> static constexpr FX_IF_INT(T, Fx) operator op(Fx a, T b) { return expr_fi; } \
    template <class T> static constexpr FX_IF_INT(T, Fx) operator op(T a, Fx b) { return expr_if; }
FX_MIXED(+, a + Fx(b), Fx(a) + b)
FX_MIXED(-, a - Fx(b), Fx(a) - b)
FX_MIXED(*, Fx::raw(a.v * (fx_raw)b), Fx::raw((fx_raw)a * b.v))
FX_MIXED(/, a / Fx(b), Fx(a) / b)
#undef FX_MIXED
#define FX_MIXED_CMP(op)                                                                       \
    template <class T> static constexpr FX_IF_INT(T, bool) operator op(Fx a, T b) { return a op Fx(b); } \
    template <class T> static constexpr FX_IF_INT(T, bool) operator op(T a, Fx b) { return Fx(a) op b; }
FX_MIXED_CMP(<) FX_MIXED_CMP(>) FX_MIXED_CMP(<=) FX_MIXED_CMP(>=) FX_MIXED_CMP(==) FX_MIXED_CMP(!=)
#undef FX_MIXED_CMP
/* Fx with hardware-float literal operands (e.g. x * 0.5f) folds the literal. */
#define FX_HW(op, R)                                                                   \
    static constexpr R operator op(Fx a, fx_hwfloat b) { return a op Fx(b); }             \
    static constexpr R operator op(fx_hwfloat a, Fx b) { return Fx(a) op b; }             \
    static constexpr R operator op(Fx a, fx_hwdouble b) { return a op Fx(b); }            \
    static constexpr R operator op(fx_hwdouble a, Fx b) { return Fx(a) op b; }
FX_HW(+, Fx) FX_HW(-, Fx) FX_HW(*, Fx) FX_HW(/, Fx)
FX_HW(<, bool) FX_HW(>, bool) FX_HW(<=, bool) FX_HW(>=, bool) FX_HW(==, bool) FX_HW(!=, bool)
#undef FX_HW

static constexpr Fx& operator+=(Fx& a, Fx b) { return a = a + b; }
static constexpr Fx& operator-=(Fx& a, Fx b) { return a = a - b; }
static constexpr Fx& operator*=(Fx& a, Fx b) { return a = a * b; }
static constexpr Fx& operator/=(Fx& a, Fx b) { return a = a / b; }
/* int op= Fx: C computes in float then truncates back. */
template <class T> static constexpr FX_IF_INT(T, T&) operator+=(T& a, Fx b) { return a = (T)(Fx(a) + b); }
template <class T> static constexpr FX_IF_INT(T, T&) operator-=(T& a, Fx b) { return a = (T)(Fx(a) - b); }
template <class T> static constexpr FX_IF_INT(T, T&) operator*=(T& a, Fx b) { return a = (T)(Fx(a) * b); }
template <class T> static constexpr FX_IF_INT(T, T&) operator/=(T& a, Fx b) { return a = (T)(Fx(a) / b); }
static constexpr Fx& operator++(Fx& a) { return a.v += FX_ONE, a; }
static constexpr Fx& operator--(Fx& a) { return a.v -= FX_ONE, a; }
static constexpr Fx operator++(Fx& a, int) { Fx o = a; a.v += FX_ONE; return o; }
static constexpr Fx operator--(Fx& a, int) { Fx o = a; a.v -= FX_ONE; return o; }

#endif
