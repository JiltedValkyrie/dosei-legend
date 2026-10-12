/*
 * Fx: fixed-point stand-in for N64 `float` on the FPU-less SH-2.
 *
 * Storage is ONE signed 32-bit word, Q16.16 (2026-10-05, Wave 0). Human rule
 * (narrowed 2026-10-06): stored values 32-bit, no software 64-bit helpers or
 * soft-float; the native dmuls.l product (MACH:MACL) is allowed for speed.
 * Multiply = dmuls.l + xtrct; division stays 32-bit (out of line).
 *
 * Range is +/-32767.99998. Results past it SATURATE to +/-FX_MAX (symmetric,
 * so negation never overflows). Saturation is an overflow guard only; it is
 * not a substitute for range-correct logic. Values the decomp builds past
 * this range (squared distances, 0xFFFF random angles) need their own
 * bounded helpers (see Wave 0 plan, range audit) rather than relying on it.
 * Precision is 1/65536; approximation is allowed by the human rule.
 *
 * Semantics follow C float rules the decomp relies on:
 *   - implicit conversion to integers truncates toward zero, then narrows;
 *   - mixed Fx/integer arithmetic promotes the integer to Fx, except that
 *     Fx * int and Fx / int skip the rescale (exact integer scaling).
 *
 * The prelude macro-renames `float`/`double` to Fx AFTER this header, so the
 * hardware types are spelled with decltype here. Constructors from float are
 * constexpr: literals fold at compile time and must never emit soft-float
 * calls on target (verify with objdump: no __addsf3, __muldf3 etc.).
 *
 * Host overflow audit: build with -DFX_SAT_AUDIT and define
 * `void fx_sat_hit(void* site)`; every saturation reports its caller.
 */
#ifndef OOT_CORE_FX_H
#define OOT_CORE_FX_H

typedef decltype(0.0f) fx_hwfloat;
typedef decltype(0.0) fx_hwdouble;
typedef int fx_raw;           /* 32 bits on SH-2 and on the host */
typedef unsigned int fx_uraw;

#define FX_FRAC 16
#define FX_ONE ((fx_raw)1 << FX_FRAC)
#define FX_MAX ((fx_raw)0x7FFFFFFF)
/* -Os outlined every Fx op (bench 2026-10-02). Hot ops are forced inline. */
#define FX_INL __attribute__((always_inline))

#if defined(FX_SAT_AUDIT)
void fx_sat_hit(void* site);
#define FX_SAT_NOTE() (__builtin_is_constant_evaluated() ? (void)0 : fx_sat_hit(__builtin_return_address(0)))
#else
#define FX_SAT_NOTE() ((void)0)
#endif

/* Signed saturation of a magnitude with a sign. */
static constexpr FX_INL fx_raw fx_sat(bool neg) {
    return FX_SAT_NOTE(), neg ? -FX_MAX : FX_MAX;
}
static constexpr FX_INL fx_raw fx_signed(fx_uraw mag, bool neg) {
    return mag > (fx_uraw)FX_MAX ? fx_sat(neg) : (neg ? -(fx_raw)mag : (fx_raw)mag);
}
static constexpr FX_INL fx_uraw fx_abs_u(fx_raw v) {
    return v < 0 ? (fx_uraw)0 - (fx_uraw)v : (fx_uraw)v;
}
static constexpr FX_INL int fx_clz(fx_uraw v) {
    return v ? __builtin_clz(v) : 32;
}

template <class T> struct fx_is_int { static constexpr bool value = false; };
#define FX_INT_TYPE(t) template <> struct fx_is_int<t> { static constexpr bool value = true; };
FX_INT_TYPE(bool) FX_INT_TYPE(char) FX_INT_TYPE(signed char) FX_INT_TYPE(unsigned char)
FX_INT_TYPE(short) FX_INT_TYPE(unsigned short) FX_INT_TYPE(int) FX_INT_TYPE(unsigned int)
FX_INT_TYPE(long) FX_INT_TYPE(unsigned long) FX_INT_TYPE(long long) FX_INT_TYPE(unsigned long long)
#undef FX_INT_TYPE
template <bool B, class T = void> struct fx_enable_if {};
template <class T> struct fx_enable_if<true, T> { typedef T type; };
#define FX_IF_INT(T, R) typename fx_enable_if<fx_is_int<T>::value, R>::type

/* Integer -> magnitude clamped to 31 bits (wider/unsigned sources compare
 * only; the decomp's own s64 values are its business, not Fx's). */
template <class T> static constexpr FX_INL fx_uraw fx_int_mag(T i, bool* neg) {
    *neg = ((T)-1 < (T)0) && i < (T)0;
    if (*neg) {
        /* int's INT_MIN negates to FX_MAX + 1, which callers saturate. */
        return (sizeof(T) > 4 && i < -(T)FX_MAX) ? (fx_uraw)FX_MAX + 1u : (fx_uraw)0 - (fx_uraw)(fx_raw)i;
    }
    return (sizeof(T) >= 4 && i > (T)FX_MAX) ? (fx_uraw)FX_MAX + 1u : (fx_uraw)i;
}

/* Compile-time float -> Q16.16, truncating toward zero, saturating. Must
 * stay always_inline: an outlined copy runs soft-double for every literal. */
static constexpr FX_INL fx_raw fx_from_double(fx_hwdouble d) {
    return d * (fx_hwdouble)FX_ONE >= (fx_hwdouble)FX_MAX ? FX_MAX
         : d * (fx_hwdouble)FX_ONE <= -(fx_hwdouble)FX_MAX ? -FX_MAX
         : (fx_raw)(d * (fx_hwdouble)FX_ONE);
}

struct Fx {
    fx_raw v;

    Fx() = default;
    constexpr FX_INL Fx(fx_hwfloat f) : v(fx_from_double((fx_hwdouble)f)) {}
    constexpr FX_INL Fx(fx_hwdouble d) : v(fx_from_double(d)) {}
    template <class T, class = FX_IF_INT(T, void)>
    constexpr FX_INL Fx(T i) : v(from_int(i)) {}

    template <class T> static constexpr FX_INL fx_raw from_int(T i) {
        bool neg = false;
        fx_uraw m = fx_int_mag(i, &neg);
        return m > 0x7FFFu ? fx_sat(neg) : (neg ? -(fx_raw)(m << FX_FRAC) : (fx_raw)(m << FX_FRAC));
    }
    static constexpr FX_INL Fx raw(fx_raw r) {
        Fx x{};
        x.v = r;
        return x;
    }

    /* Float->int truncates toward zero, like C/MIPS trunc.w.s. */
    constexpr FX_INL fx_raw trunc() const { return v >= 0 ? v >> FX_FRAC : -(fx_raw)(fx_abs_u(v) >> FX_FRAC); }
    template <class T, class = FX_IF_INT(T, void)>
    constexpr operator T() const { return (T)trunc(); }
    /* Host reference/debug only: never call on target hot paths. */
    explicit constexpr operator fx_hwfloat() const { return (fx_hwfloat)((fx_hwdouble)v / (fx_hwdouble)FX_ONE); }

    constexpr Fx operator-() const { return raw(v < -FX_MAX ? FX_MAX : -v); }
    constexpr Fx operator+() const { return *this; }
    constexpr bool operator!() const { return v == 0; }
};

/* a + b, saturating. Overflow iff both operands share a sign the sum lacks. */
static constexpr FX_INL fx_raw fx_add_raw(fx_raw a, fx_raw b) {
    fx_raw r = (fx_raw)((fx_uraw)a + (fx_uraw)b);
    return (((a ^ r) & (b ^ r)) < 0) ? fx_sat(a < 0) : (r < -FX_MAX ? -FX_MAX : r);
}
static constexpr FX_INL fx_raw fx_sub_raw(fx_raw a, fx_raw b) {
    return fx_add_raw(a, b < -FX_MAX ? FX_MAX : -b);
}

/*
 * |a| * |b| >> 16 from 16-bit halves: each partial product is 16x16 -> 32,
 * so no 64-bit value or MACH:MACL pair exists. Saturates past FX_MAX.
 */
static constexpr FX_INL fx_uraw fx_mulq_u(fx_uraw ua, fx_uraw ub) {
    fx_uraw ah = ua >> 16, al = ua & 0xFFFFu, bh = ub >> 16, bl = ub & 0xFFFFu;
    fx_uraw hh = ah * bh;
    if (hh > 0x7FFFu) {
        return (fx_uraw)FX_MAX + 1u;
    }
    fx_uraw r = hh << 16;
    fx_uraw m = ah * bl;          /* ah < 2^15: m < 2^31, r + m < 2^32 */
    r += m;
    m = al * bh;
    r += m;
    if (r < m) {
        return (fx_uraw)FX_MAX + 1u;
    }
    m = (al * bl) >> 16;
    r += m;
    return r < m ? (fx_uraw)FX_MAX + 1u : r;
}
static constexpr FX_INL fx_raw fx_mul_fold(fx_raw a, fx_raw b) {
    return fx_signed(fx_mulq_u(fx_abs_u(a), fx_abs_u(b)), (a < 0) != (b < 0));
}
/* Runtime divides stay out of line (oot_math.cpp): inlined split-multiply
 * saturation cost ~90 KB of blob. Multiply is the inline dmuls.l below. */
fx_raw OotFx_Mul(fx_raw a, fx_raw b);
fx_raw OotFx_MulInt(fx_raw a, fx_uraw ub, bool nb);
fx_raw OotFx_Div(fx_raw a, fx_raw b);
fx_raw OotFx_DivInt(fx_raw a, fx_uraw ub, bool nb);
fx_raw OotFx_IntDiv(fx_uraw ua, bool na, fx_raw b);
#if defined(__sh__)
/* Native SH-2 multiply (human 2026-10-06: allowed, speed wins): dmuls.l puts
 * the product in MACH:MACL, xtrct takes its middle 32 bits (product >> 16).
 * MACH beyond a sign-extended 16-bit value means the result left Fx: saturate.
 * Stored values stay 32-bit; no libgcc helper. */
static inline FX_INL fx_raw fx_mul_hw(fx_raw a, fx_raw b) {
    fx_raw hi, mid;
    __asm__("dmuls.l %2,%3\n\tsts mach,%0\n\tsts macl,%1\n\txtrct %0,%1"
            : "=&r"(hi), "=&r"(mid) : "r"(a), "r"(b) : "mach", "macl");
    return (fx_uraw)(hi + 0x8000) > 0xFFFFu ? fx_sat(hi < 0) : (mid < -FX_MAX ? -FX_MAX : mid);
}
/* a * b without rescale: MACH must be MACL's sign extension. */
static inline FX_INL fx_raw fx_muli_hw(fx_raw a, fx_raw b) {
    fx_raw hi, lo;
    __asm__("dmuls.l %2,%3\n\tsts mach,%0\n\tsts macl,%1"
            : "=&r"(hi), "=&r"(lo) : "r"(a), "r"(b) : "mach", "macl");
    return hi != (lo >> 31) ? fx_sat(hi < 0) : (lo < -FX_MAX ? -FX_MAX : lo);
}
#else
/* Host reference of the same hardware product. */
static inline fx_raw fx_mul_hw(fx_raw a, fx_raw b) {
    long long p = ((long long)a * b) >> 16;
    return p > FX_MAX ? fx_sat(false) : p < -FX_MAX ? fx_sat(true) : (fx_raw)p;
}
static inline fx_raw fx_muli_hw(fx_raw a, fx_raw b) {
    long long p = (long long)a * b;
    return p > FX_MAX ? fx_sat(false) : p < -FX_MAX ? fx_sat(true) : (fx_raw)p;
}
#endif
static constexpr FX_INL fx_raw fx_mul_raw(fx_raw a, fx_raw b) {
    return __builtin_is_constant_evaluated() ? fx_mul_fold(a, b) : fx_mul_hw(a, b);
}

/* |a| * |b| as integers (no rescale), saturating; 16-bit halves again. */
static constexpr FX_INL fx_uraw fx_muli_u(fx_uraw ua, fx_uraw ub) {
    fx_uraw ah = ua >> 16, al = ua & 0xFFFFu, bh = ub >> 16, bl = ub & 0xFFFFu;
    if (ah && bh) {
        return (fx_uraw)FX_MAX + 1u;
    }
    fx_uraw cross = ah * bl + al * bh;  /* one term is zero */
    if (cross > 0x7FFFu) {
        return (fx_uraw)FX_MAX + 1u;
    }
    fx_uraw lo = al * bl, r = (cross << 16) + lo;
    return r < lo ? (fx_uraw)FX_MAX + 1u : r;
}

/*
 * n * 2^e / d for magnitudes (d > 0), truncated, saturating at FX_MAX + 1.
 * The numerator is pre-shifted as far as 32 bits allow. One 32/32 divide
 * obtains its quotient; remaining bits use restoring remainder steps.
 * On SH-2 a general divide is a software loop: repeating it for remainder
 * chunks made large divisors especially costly (only one bit per chunk).
 * Since r < d <= FX_MAX, doubling r stays in one unsigned word. Exact
 * truncated result and the same saturation, with no wide intermediate.
 */
static constexpr fx_uraw fx_div_u(fx_uraw n, int e, fx_uraw d) {
    if (n == 0) {
        return 0;                    /* also avoids shifting zero by 32 */
    }
    if (d > (fx_uraw)FX_MAX) {
        d = (fx_uraw)FX_MAX;
    }
    int s = fx_clz(n);
    if (s > e) {
        s = e;
    }
    fx_uraw num = n << s;
    fx_uraw q = num / d;
    fx_uraw r = num - q * d;          /* q*d <= num: exact 32-bit product */
    int t = e - s;
    while (t > 0) {
        if (q > ((fx_uraw)FX_MAX >> 1)) {
            return (fx_uraw)FX_MAX + 1u;
        }
        r <<= 1;
        q <<= 1;
        if (r >= d) {
            r -= d;
            ++q;
        }
        --t;
    }
    return q;
}
static constexpr fx_raw fx_div_fold(fx_raw a, fx_raw b) {
    bool neg = (a < 0) != (b < 0);
    if (b == 0) {
        /* N64 float gives +/-inf; keep the sign with the largest value. */
        return a < 0 ? -FX_MAX : FX_MAX;
    }
    return a == 0 ? 0 : fx_signed(fx_div_u(fx_abs_u(a), FX_FRAC, fx_abs_u(b)), neg);
}

static constexpr FX_INL fx_raw fx_div_raw(fx_raw a, fx_raw b) {
    return __builtin_is_constant_evaluated() ? fx_div_fold(a, b) : OotFx_Div(a, b);
}

static constexpr FX_INL Fx operator+(Fx a, Fx b) { return Fx::raw(fx_add_raw(a.v, b.v)); }
static constexpr FX_INL Fx operator-(Fx a, Fx b) { return Fx::raw(fx_sub_raw(a.v, b.v)); }
static constexpr FX_INL Fx operator*(Fx a, Fx b) { return Fx::raw(fx_mul_raw(a.v, b.v)); }
static constexpr Fx operator/(Fx a, Fx b) { return Fx::raw(fx_div_raw(a.v, b.v)); }
constexpr FX_INL bool operator<(Fx a, Fx b) { return a.v < b.v; }
constexpr FX_INL bool operator>(Fx a, Fx b) { return a.v > b.v; }
constexpr FX_INL bool operator<=(Fx a, Fx b) { return a.v <= b.v; }
constexpr FX_INL bool operator>=(Fx a, Fx b) { return a.v >= b.v; }
constexpr FX_INL bool operator==(Fx a, Fx b) { return a.v == b.v; }
constexpr FX_INL bool operator!=(Fx a, Fx b) { return a.v != b.v; }

/* Fx raw * integer (no rescale). */
template <class T> static constexpr FX_INL fx_raw fx_mul_int(fx_raw a, T b) {
    bool nb = false;
    fx_uraw ub = fx_int_mag(b, &nb);
    if (__builtin_is_constant_evaluated()) {
        return fx_signed(fx_muli_u(fx_abs_u(a), ub), (a < 0) != nb);
    }
    if (ub <= (fx_uraw)FX_MAX) {            /* every s32/int16/char operand */
        return fx_muli_hw(a, nb ? -(fx_raw)ub : (fx_raw)ub);
    }
    return OotFx_MulInt(a, ub, nb);
}
/* Fx / integer: divide the raw value directly (exact, no saturated Fx(b)). */
template <class T> static constexpr FX_INL fx_raw fx_div_int(fx_raw a, T b) {
    bool nb = false;
    fx_uraw ub = fx_int_mag(b, &nb);
    if (ub == 0) {
        return a < 0 ? -FX_MAX : FX_MAX;
    }
    if (__builtin_is_constant_evaluated()) {
        return fx_signed(fx_abs_u(a) / ub, (a < 0) != nb);
    }
    /* Constant divisor (x / 2, x / 3 ...), 2026-10-09: a power of two is a
     * shift; any other constant is GCC's reciprocal multiply, a native
     * dmulu.l (allowed) instead of a libgcc ___udivsi3 call (~100+ cycles).
     * Same truncation toward zero as the runtime divide. 32-bit values only. */
    if (__builtin_constant_p(ub)) {
        if ((ub & (ub - 1)) == 0) {
            return fx_signed(fx_abs_u(a) >> __builtin_ctz(ub), (a < 0) != nb);
        }
        return fx_signed(fx_abs_u(a) / ub, (a < 0) != nb);
    }
    return OotFx_DivInt(a, ub, nb);
}
/* integer / Fx: |i| * 2^32 / |b.v| without first saturating Fx(i). */
template <class T> static constexpr fx_raw fx_int_div(T a, fx_raw b) {
    bool na = false;
    fx_uraw ua = fx_int_mag(a, &na);
    if (b == 0) {
        return na ? -FX_MAX : FX_MAX;
    }
    if (ua == 0) {
        return 0;
    }
    return __builtin_is_constant_evaluated() ? fx_signed(fx_div_u(ua, 2 * FX_FRAC, fx_abs_u(b)), na != (b < 0))
                                             : OotFx_IntDiv(ua, na, b);
}

/* Mixed Fx/integer: exact-match templates beat the builtin int operators that
 * the implicit integer conversion would otherwise make ambiguous. Integer
 * multiply/divide skip the fixed-point rescale. */
#define FX_MIXED(op, expr_fi, expr_if)                                                    \
    template <class T> static constexpr FX_INL FX_IF_INT(T, Fx) operator op(Fx a, T b) { return expr_fi; } \
    template <class T> static constexpr FX_INL FX_IF_INT(T, Fx) operator op(T a, Fx b) { return expr_if; }
FX_MIXED(+, a + Fx(b), Fx(a) + b)
FX_MIXED(-, a - Fx(b), Fx(a) - b)
FX_MIXED(*, Fx::raw(fx_mul_int(a.v, b)), Fx::raw(fx_mul_int(b.v, a)))
FX_MIXED(/, Fx::raw(fx_div_int(a.v, b)), Fx::raw(fx_int_div(a, b.v)))
#undef FX_MIXED
#define FX_MIXED_CMP(op)                                                                       \
    template <class T> static constexpr FX_INL FX_IF_INT(T, bool) operator op(Fx a, T b) { return a op Fx(b); } \
    template <class T> static constexpr FX_INL FX_IF_INT(T, bool) operator op(T a, Fx b) { return Fx(a) op b; }
FX_MIXED_CMP(<) FX_MIXED_CMP(>) FX_MIXED_CMP(<=) FX_MIXED_CMP(>=) FX_MIXED_CMP(==) FX_MIXED_CMP(!=)
#undef FX_MIXED_CMP
/* Fx with hardware-float literal operands (e.g. x * 0.5f) folds the literal. */
#define FX_HW(op, R)                                                                   \
    static constexpr FX_INL R operator op(Fx a, fx_hwfloat b) { return a op Fx(b); }             \
    static constexpr FX_INL R operator op(fx_hwfloat a, Fx b) { return Fx(a) op b; }             \
    static constexpr FX_INL R operator op(Fx a, fx_hwdouble b) { return a op Fx(b); }            \
    static constexpr FX_INL R operator op(fx_hwdouble a, Fx b) { return Fx(a) op b; }
FX_HW(+, Fx) FX_HW(-, Fx) FX_HW(*, Fx) FX_HW(/, Fx)
FX_HW(<, bool) FX_HW(>, bool) FX_HW(<=, bool) FX_HW(>=, bool) FX_HW(==, bool) FX_HW(!=, bool)
#undef FX_HW

static constexpr FX_INL Fx& operator+=(Fx& a, Fx b) { return a = a + b; }
static constexpr FX_INL Fx& operator-=(Fx& a, Fx b) { return a = a - b; }
static constexpr FX_INL Fx& operator*=(Fx& a, Fx b) { return a = a * b; }
static constexpr Fx& operator/=(Fx& a, Fx b) { return a = a / b; }
/* int op= Fx: C computes in float then truncates back. */
template <class T> static constexpr FX_INL FX_IF_INT(T, T&) operator+=(T& a, Fx b) { return a = (T)(Fx(a) + b); }
template <class T> static constexpr FX_INL FX_IF_INT(T, T&) operator-=(T& a, Fx b) { return a = (T)(Fx(a) - b); }
template <class T> static constexpr FX_INL FX_IF_INT(T, T&) operator*=(T& a, Fx b) { return a = (T)(Fx(a) * b); }
template <class T> static constexpr FX_IF_INT(T, T&) operator/=(T& a, Fx b) { return a = (T)(Fx(a) / b); }
static constexpr FX_INL Fx& operator++(Fx& a) { return a.v = fx_add_raw(a.v, FX_ONE), a; }
static constexpr FX_INL Fx& operator--(Fx& a) { return a.v = fx_sub_raw(a.v, FX_ONE), a; }
static constexpr FX_INL Fx operator++(Fx& a, int) { Fx o = a; ++a; return o; }
static constexpr FX_INL Fx operator--(Fx& a, int) { Fx o = a; --a; return o; }

#endif
