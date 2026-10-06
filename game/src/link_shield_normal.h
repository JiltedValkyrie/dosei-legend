#ifndef LINK_SHIELD_NORMAL_H
#define LINK_SHIELD_NORMAL_H

/* Shield only: use the animated triangle, never its bind-pose normal.
 * POINT/FIXED come from SGL. The sign matches build_sgl_scene.face_normal
 * in the already Y-negated POINT space. No lighting uses this vector, so
 * a bounded positive scale suffices for SGL's facing test; no sqrt/divide.
 * Q8 edges retain 1/256-unit detail. Bound edges before the 32-bit cross:
 * each product <= 16384^2, each subtraction <= 2*16384^2. */
static void __attribute__((noinline, optimize("Os"))) link_shield_normal(
    const POINT a, const POINT b, const POINT c, FIXED *normal)
{
    int32_t edge[6], peak = 0;
    unsigned i;
    for (i = 0; i < 3; ++i) {
        edge[i] = (b[i] >> 8) - (a[i] >> 8);
        edge[i + 3] = (c[i] >> 8) - (a[i] >> 8);
    }
    for (i = 0; i < 6; ++i) {
        int32_t value = edge[i] < 0 ? -edge[i] : edge[i];
        if (value > peak) peak = value;
    }
    while (peak > 16383) {
        for (i = 0; i < 6; ++i) edge[i] >>= 1;
        peak = (peak + 1) >> 1;
    }
    normal[0] = edge[2] * edge[4] - edge[1] * edge[5];
    normal[1] = edge[0] * edge[5] - edge[2] * edge[3];
    normal[2] = edge[1] * edge[3] - edge[0] * edge[4];
    peak = 0;
    for (i = 0; i < 3; ++i) {
        int32_t value = normal[i] < 0 ? -normal[i] : normal[i];
        if (value > peak) peak = value;
    }
    if (!peak) return;              /* degenerate triangle remains invisible */
    while (peak > 65536) {
        for (i = 0; i < 3; ++i) normal[i] >>= 1;
        peak = (peak + 1) >> 1;
    }
    while (peak < 32768) {
        for (i = 0; i < 3; ++i) normal[i] *= 2;
        peak *= 2;
    }
}
#endif
