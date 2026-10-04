/* Conservative integer broad phase for the imported collision narrow phase.
 * Source triangles, surface flags, displacement and dynamic geometry still
 * decide each contact. Reject distant triangles before constructing Fx
 * vectors, normals, square roots and divisions for each actor every step. */
#ifndef OOT_CORE_BGCHECK_BOUNDS_H
#define OOT_CORE_BGCHECK_BOUNDS_H

/* Fx retains its legacy wide ABI. Reading its two words and shifting each
 * word separately adds no wide arithmetic to this hot path. */
static inline s32 OotCore_BgInt(f32 value) {
#if OOT_CORE_HWFLOAT
    return (s32)value;
#else
    u32 words[2], lo, hi;
    __builtin_memcpy(words, &value, sizeof(words));
#if __BYTE_ORDER__ == __ORDER_BIG_ENDIAN__
    hi = words[0]; lo = words[1];
#else
    lo = words[0]; hi = words[1];
#endif
    static_assert(FX_FRAC == 16, "collision bounds require Q16 Fx storage");
    /* Only the signed 32-bit integer range is useful for scene bounds. */
    if ((s32)hi > 32767) return 2147483647;
    if ((s32)hi < -32768) return (-2147483647 - 1);
    s32 whole = (s32)((hi << 16) | (lo >> 16));
    if ((s32)hi < 0 && (lo & 65535u)) whole++;
    return whole;
#endif
}

static inline s32 OotCore_BgAxisNear(s32 p, s32 a, s32 b, s32 c, s32 pad) {
    s32 low = a < b ? a : b, high = a > b ? a : b;
    if (c < low) low = c;
    if (c > high) high = c;
    return p >= low - pad && p <= high + pad;
}

static inline s32 OotCore_BgPolyNear(CollisionPoly* poly, Vec3s* vertices,
                                   f32 x, f32 y, f32 z, f32 radius, s32 axes) {
    const Vec3s* a = &vertices[COLPOLY_VTX_INDEX(poly->flags_vIA)];
    const Vec3s* b = &vertices[COLPOLY_VTX_INDEX(poly->flags_vIB)];
    const Vec3s* c = &vertices[poly->vIC];
    s32 pad = OotCore_BgInt(radius);
    /* Source narrow checks use inclusive bounds plus edge tolerance. Two
     * extra units conservatively cover truncation of position and radius. */
    if (pad < 0 || pad > 32767) return true;
    pad += 2;
    return (!(axes & 1) || OotCore_BgAxisNear(OotCore_BgInt(x), a->x, b->x, c->x, pad)) &&
           (!(axes & 2) || OotCore_BgAxisNear(OotCore_BgInt(y), a->y, b->y, c->y, pad)) &&
           (!(axes & 4) || OotCore_BgAxisNear(OotCore_BgInt(z), a->z, b->z, c->z, pad));
}
#endif
