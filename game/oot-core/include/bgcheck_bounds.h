/* Conservative integer broad phase for the imported collision narrow phase.
 * Source triangles, surface flags, displacement and dynamic geometry still
 * decide each contact. Reject distant triangles before constructing Fx
 * vectors, normals, square roots and divisions for each actor every step. */
#ifndef OOT_CORE_BGCHECK_BOUNDS_H
#define OOT_CORE_BGCHECK_BOUNDS_H

/* z_bgcheck line tests: stamp of the current query in polyCheckTbl
 * (importer rewrite of BgCheck_ResetPolyCheckTbl). */
extern u8 gOotCoreBgCheckStamp;

/* Fx is one 32-bit Q16.16 word: the whole part, truncated toward zero. */
static inline s32 OotCore_BgInt(f32 value) {
#if OOT_CORE_HWFLOAT
    return (s32)value;
#else
    static_assert(FX_FRAC == 16, "collision bounds require Q16 Fx storage");
    /* v >= -FX_MAX (saturated), so negation cannot overflow. */
    return value.v >= 0 ? value.v >> 16 : -((-value.v) >> 16);
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

/* 2026-10-09 speed (20 FPS push): integer pre-classification for
 * CollisionPoly_CheckYIntersect (Math3D_TriChkPointParaYImpl, detMax 0).
 * The point is floored to whole units; each edge determinant is linear in
 * the point, so the floor moves it by at most that edge's L1 length e.
 *   -1: more than chkDist + 1 outside one edge line: no vertex, edge or
 *       determinant test of the source can accept; false.
 *    1: inside all three edges by more than e: every source determinant
 *       has the triangle's sign; true (caller still checks ny).
 *    0: near an edge or out of range: run the source test.
 * 32-bit only: every offset is kept within +-16383 so products and sums fit.
 * Disabled for the host-float reference build. */
static inline s32 OotCore_BgEdgeL1(s32 x0, s32 z0, s32 x1, s32 z1) {
    s32 dx = x1 - x0, dz = z1 - z0;
    return (dx < 0 ? -dx : dx) + (dz < 0 ? -dz : dz);
}

static inline s32 OotCore_BgFloorClass(CollisionPoly* poly, Vec3s* vertices, f32 x, f32 z, f32 chkDist) {
#if OOT_CORE_HWFLOAT || OOT_CORE_BG_NOFAST
    return 0;
#else
    const Vec3s* a = &vertices[COLPOLY_VTX_INDEX(poly->flags_vIA)];
    const Vec3s* b = &vertices[COLPOLY_VTX_INDEX(poly->flags_vIB)];
    const Vec3s* c = &vertices[poly->vIC];
    s32 px = x.v >> 16, pz = z.v >> 16; /* floor */
    s32 ax = a->x - px, az = a->z - pz, bx = b->x - px, bz = b->z - pz;
    s32 cx = c->x - px, cz = c->z - pz;
    s32 chk = (s32)(((u32)chkDist.v + 0xFFFFu) >> 16);
    s32 d0, d1, d2, e0, e1, e2, area, out;

    if ((u32)(ax + 16383) > 32766u || (u32)(az + 16383) > 32766u || (u32)(bx + 16383) > 32766u ||
        (u32)(bz + 16383) > 32766u || (u32)(cx + 16383) > 32766u || (u32)(cz + 16383) > 32766u ||
        chkDist.v < 0 || chk > 64) {
        return 0;
    }
    d0 = az * bx - ax * bz;
    d1 = bz * cx - bx * cz;
    d2 = cz * ax - cx * az;
    area = d0 + d1 + d2; /* twice the signed area: the same for every point */
    if (area == 0) {
        return 0;
    }
    if (area < 0) {
        d0 = -d0;
        d1 = -d1;
        d2 = -d2;
    }
    e0 = OotCore_BgEdgeL1(a->x, a->z, b->x, b->z);
    e1 = OotCore_BgEdgeL1(b->x, b->z, c->x, c->z);
    e2 = OotCore_BgEdgeL1(c->x, c->z, a->x, a->z);
    if (d0 > e0 && d1 > e1 && d2 > e2) {
        return 1;
    }
    /* Outside edge k by -d/|e|2 >= (-d - e)/e > chk + 1. */
    out = chk + 2;
    if (-d0 > out * e0 || -d1 > out * e1 || -d2 > out * e2) {
        return -1;
    }
    return 0;
#endif
}

/* CollisionPoly_LineVsPoly returns false first when both segment ends lie
 * on the same side of the plane. Same test in integers (2026-10-09 speed):
 * S = n . floor(p) + 32767 * dist with Q15 normals; flooring moves S by less
 * than |nx| + |ny| + |nz|, one more 32767 covers the Fx normal rounding.
 * True only when both ends are certainly on one side. Coordinates within
 * +-10922 keep every sum below 2^31. */
static inline s32 OotCore_BgLineSameSide(CollisionPoly* poly, Vec3f* posA, Vec3f* posB) {
#if OOT_CORE_HWFLOAT || OOT_CORE_BG_NOFAST
    return false;
#else
    s32 nx = poly->normal.x, ny = poly->normal.y, nz = poly->normal.z;
    s32 ax = posA->x.v >> 16, ay = posA->y.v >> 16, az = posA->z.v >> 16;
    s32 bx = posB->x.v >> 16, by = posB->y.v >> 16, bz = posB->z.v >> 16;
    s32 margin, base, sa, sb;

    if ((u32)(ax + 10922) > 21844u || (u32)(ay + 10922) > 21844u || (u32)(az + 10922) > 21844u ||
        (u32)(bx + 10922) > 21844u || (u32)(by + 10922) > 21844u || (u32)(bz + 10922) > 21844u) {
        return false;
    }
    margin = (nx < 0 ? -nx : nx) + (ny < 0 ? -ny : ny) + (nz < 0 ? -nz : nz) + 32767;
    base = 32767 * (s32)poly->dist;
    sa = nx * ax + ny * ay + nz * az;
    sb = nx * bx + ny * by + nz * bz;
    /* Compared as sa > margin - base: sa + base could pass 2^31. */
    if (sa > margin - base && sb > margin - base) return true;
    if (sa < -margin - base && sb < -margin - base) return true;
    return false;
#endif
}
#endif
