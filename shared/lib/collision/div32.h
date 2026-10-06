/*
 * 32-bit divides for 64-bit numerators, without libgcc ___divdi3.
 *
 * Human rule (2026-10-06): the native SH-2 dmuls.l product may be 64 bits,
 * but software 64-bit helpers are banned and speed wins over exactness. These
 * normalize the numerator (and a large divisor) into 32-bit words with word
 * shifts, do ONE 32/32 divide and shift the quotient back. Results are
 * approximate when the numerator exceeds 31 bits (low bits dropped) and
 * saturate to +/-INT32_MAX. Constant 64-bit shifts and the int64 casts that
 * produce dmuls.l are inline on SH-2; nothing here calls a 64-bit helper.
 */
#ifndef DOSEI_DIV32_H
#define DOSEI_DIV32_H

#include <stdint.h>

/* SH-2: one out-of-line copy (inlining these cost ~8 KB of work RAM),
 * defined in the TU that sets DIV32_IMPLEMENTATION (recomp_collision.c via
 * kokiri_collision.c). Host fixtures compile single files: static inline. */
#if defined(__sh__)
#define DIV32_API
int32_t div64s_approx(int64_t n, int32_t d);
int32_t muldiv_s32(int32_t a, int32_t b, int32_t d);
int32_t ratio64_q16(int64_t num, int64_t den);
int32_t muldiv64_s32(int32_t a, int64_t b, int64_t d);
#else
#define DIV32_API static inline
#ifndef DIV32_IMPLEMENTATION
#define DIV32_IMPLEMENTATION
#endif
#endif

#ifdef DIV32_IMPLEMENTATION
#pragma GCC push_options
#pragma GCC optimize ("Os")
static inline int div32_bits(uint32_t v)
{
        return v ? 32 - __builtin_clz(v) : 0;
}

/* |n| as (hi, lo) words; returns true when n was negative. */
static inline int div32_abs64(int64_t n, uint32_t *hi, uint32_t *lo)
{
        uint32_t h = (uint32_t)((uint64_t)n >> 32), l = (uint32_t)n;
        int neg = (int32_t)h < 0;
        if (neg) {
                l = 0u - l;
                h = ~h + (l == 0u);
        }
        *hi = h;
        *lo = l;
        return neg;
}

/* (hi, lo) >> s for 0 <= s <= 63, as 32 bits (caller keeps it in range). */
static inline uint32_t div32_shr64(uint32_t hi, uint32_t lo, int s)
{
        if (s <= 0) return lo;
        return s >= 32 ? hi >> (s - 32) : (hi << (32 - s)) | (lo >> s);
}

/* Unsigned (hi, lo) / d, approximate, saturating at INT32_MAX. */
static inline uint32_t div32_u64(uint32_t hi, uint32_t lo, uint32_t d)
{
        int s, t, up;
        uint32_t q;
        if (!d) return INT32_MAX;
        if (!hi && lo <= (uint32_t)INT32_MAX) return lo / d;
        s = 1 + div32_bits(hi);            /* drop s bits: numerator fits 31 */
        t = div32_bits(d) - 16;            /* keep >= 16 divisor bits */
        if (t > s) t = s;
        if (t < 0) t = 0;
        q = div32_shr64(hi, lo, s) / (d >> t);
        up = s - t;
        if (up >= 31 || q > ((uint32_t)INT32_MAX >> up)) return INT32_MAX;
        return q << up;
}

/* n / d for a 64-bit numerator (sums of dmuls products) and 32-bit d. */
DIV32_API int32_t div64s_approx(int64_t n, int32_t d)
{
        uint32_t hi, lo, q;
        int32_t r32, qs;
        int64_t r;
        int neg = div32_abs64(n, &hi, &lo);
        if (d < 0) {
                neg = !neg;
                q = div32_u64(hi, lo, 0u - (uint32_t)d);
        } else {
                q = div32_u64(hi, lo, (uint32_t)d);
        }
        if (q >= (uint32_t)INT32_MAX) return neg ? -INT32_MAX : INT32_MAX;
        qs = neg ? -(int32_t)q : (int32_t)q;
        /* One exact correction: remainder from the hardware product; when it
         * fits 32 bits the result is the truncated quotient. */
        r = n - (int64_t)qs * d;
        r32 = (int32_t)r;
        if ((int64_t)r32 == r && d != 0) qs += r32 / d;
        return qs;
}

/* a * b / d with 64-bit b, d (line/edge parameters): b and d are shifted
 * together until both fit 31 bits, then one hardware product and one
 * corrected 32-bit divide. */
DIV32_API int32_t muldiv64_s32(int32_t a, int64_t b, int64_t d)
{
        uint32_t bh, bl, dh, dl;
        int nb = div32_abs64(b, &bh, &bl), nd = div32_abs64(d, &dh, &dl);
        int bits = bh ? 32 + div32_bits(bh) : div32_bits(bl);
        int dbits = dh ? 32 + div32_bits(dh) : div32_bits(dl);
        int s = (bits > dbits ? bits : dbits) - 31;
        int32_t b32, d32;
        if (s < 0) s = 0;
        b32 = (int32_t)div32_shr64(bh, bl, s);
        d32 = (int32_t)div32_shr64(dh, dl, s);
        if (!d32) return (nb != nd) != (a < 0) ? -INT32_MAX : INT32_MAX;
        return div64s_approx((int64_t)a * (nb ? -b32 : b32), nd ? -d32 : d32);
}

/* a * b / d: hardware 64-bit product, 32-bit divide. */
DIV32_API int32_t muldiv_s32(int32_t a, int32_t b, int32_t d)
{
        return div64s_approx((int64_t)a * b, d);
}

/* num / den in Q16 for 64-bit num, den (line and edge parameters). Both are
 * shifted by the same amount until den fits 15 bits; integer part and 16
 * fraction bits come from two 32/32 divides. Saturates past +/-32767. */
DIV32_API int32_t ratio64_q16(int64_t num, int64_t den)
{
        uint32_t nh, nl, dh, dl, n32, d32, q, r;
        int neg = div32_abs64(num, &nh, &nl) != div32_abs64(den, &dh, &dl);
        int s = (dh ? 32 + div32_bits(dh) : div32_bits(dl)) - 15;
        int nbits = nh ? 32 + div32_bits(nh) : div32_bits(nl);
        if (s < 0) s = 0;
        d32 = div32_shr64(dh, dl, s);
        if (!d32 || nbits - s > 32) return neg ? -INT32_MAX : INT32_MAX;
        n32 = div32_shr64(nh, nl, s);
        q = n32 / d32;
        if (q > 0x7FFFu) return neg ? -INT32_MAX : INT32_MAX;
        r = n32 - q * d32;                 /* < d32 < 2^15: r << 16 fits */
        q = (q << 16) | ((r << 16) / d32);
        return neg ? -(int32_t)q : (int32_t)q;
}

#pragma GCC pop_options
#endif

#endif
