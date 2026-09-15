#include "kokiri_clip.h"
#include <string.h>
#ifdef __sh__
#include <cpu/divu.h>
#endif

static int32_t divide(int32_t numerator, int32_t denominator)
{
#ifdef __sh__
        cpu_divu_32_32_set((uint32_t)numerator, (uint32_t)denominator);
        return (int32_t)cpu_divu_quotient_get();
#else
        return numerator / denominator;
#endif
}

int32_t kokiri_project_offset(int32_t coordinate, int32_t z)
{
        return divide(coordinate * 240, z);
}

static int32_t intersection_fraction(int32_t numerator, int32_t denominator)
{
#ifdef __sh__
        /* Intersections bracket the plane, so the Q16 quotient is 0..65536.
         * Neither audio nor the controller ISR uses the hardware divider. */
        cpu_divu_fix16_set(numerator, denominator);
        return (int32_t)cpu_divu_quotient_get();
#else
        return (int32_t)((int64_t)numerator*65536/denominator);
#endif
}

static int32_t plane_distance(clip_vertex_t p, int plane)
{
        switch (plane) {
        case 0: return p.z - NEAR_Z;
        case 1: return p.x*240 + p.z*160;
        case 2: return p.z*159 - p.x*240;
        case 3: return p.z*120 - p.y*240;
        default: return p.z*119 + p.y*240;
        }
}

unsigned kokiri_clip_outcode(clip_vertex_t p)
{
        unsigned code = 0;
        for (int plane = 0; plane < 5; plane++)
                if (plane_distance(p, plane) < 0) code |= 1u << plane;
        return code;
}

void kokiri_clip_texture(const uint8_t *source, unsigned size,
    const clip_vertex_t quad[4], uint8_t tile[128])
{
        for (int y = 0; y < 16; y++) {
                const int32_t lb = quad[0].b + (quad[3].b-quad[0].b)*y/15;
                const int32_t lc = quad[0].c + (quad[3].c-quad[0].c)*y/15;
                const int32_t rb = quad[1].b + (quad[2].b-quad[1].b)*y/15;
                const int32_t rc = quad[1].c + (quad[2].c-quad[1].c)*y/15;
                for (int x = 0; x < 16; x++) {
                        int32_t b = lb + (rb-lb)*x/15;
                        int32_t c = lc + (rc-lc)*x/15;
                        if (c < 0) c = 0;
                        if (c > 65536) c = 65536;
                        if (b < 0) b = 0;
                        if (b > 65536-c) b = 65536-c;
                        /* The original A/B/C/C tile maps b=u*(1-v), c=v.
                         * All operands fit 32 bits; use DIVU, not libgcc's
                         * long 64-bit software division loop per texel. */
                        unsigned u = c == 65536 ? 0 :
                            (unsigned)divide(b*(int32_t)(size-1)+(65536-c)/2,65536-c);
                        unsigned v = (c*(size-1)+32768)/65536;
                        unsigned texel = v*size+u;
                        unsigned index = (source[texel/2] >> ((texel&1) ? 0 : 4)) & 15;
                        unsigned dest = y*8+x/2;
                        if (x&1) tile[dest] |= index;
                        else tile[dest] = index << 4;
                }
        }
}

/* Clip in camera space BEFORE projection/culling; clamping changes winding. */
int kokiri_clip_frustum(const clip_vertex_t input[3], clip_vertex_t out[12], bool *changed)
{
        unsigned outside[3] = {0,0,0};
        for (int plane = 0; plane < 5; plane++) for (int i = 0; i < 3; i++)
                if (plane_distance(input[i],plane) < 0) outside[i] |= 1u << plane;
        *changed = (outside[0] | outside[1] | outside[2]) != 0;
        if (outside[0] & outside[1] & outside[2]) return 0;
        if (!*changed) {
                for (int i = 0; i < 3; i++) {
                        out[i] = input[i];
                        out[i].b = i == 1 ? 65536 : 0;
                        out[i].c = i == 2 ? 65536 : 0;
                }
                return 3;
        }
        clip_vertex_t buffers[2][12];
        int n = 3, current = 0;
        *changed = false;
        for (int i = 0; i < 3; i++) {
                buffers[0][i] = input[i];
                buffers[0][i].b = i == 1 ? 65536 : 0;
                buffers[0][i].c = i == 2 ? 65536 : 0;
        }
        for (int plane = 0; plane < 5 && n; plane++) {
                int count = 0;
                clip_vertex_t *in = buffers[current], *dest = buffers[1-current];
                for (int i = 0; i < n; i++) {
                        clip_vertex_t a = in[i ? i-1 : n-1], b = in[i];
                        int32_t da = plane_distance(a,plane), db = plane_distance(b,plane);
                        if ((da >= 0) != (db >= 0)) {
                                int32_t t = intersection_fraction(da,da-db);
                                clip_vertex_t v = {
                                    a.x + (int32_t)((int64_t)(b.x-a.x)*t/65536),
                                    a.y + (int32_t)((int64_t)(b.y-a.y)*t/65536),
                                    a.z + (int32_t)((int64_t)(b.z-a.z)*t/65536),
                                    a.b + (int32_t)((int64_t)(b.b-a.b)*t/65536),
                                    a.c + (int32_t)((int64_t)(b.c-a.c)*t/65536)
                                };
                                if (plane == 0) v.z = NEAR_Z;
                                dest[count++] = v;
                        }
                        if (db >= 0) dest[count++] = b;
                        else *changed = true;
                }
                n = count;
                current = 1-current;
        }
        memcpy(out, buffers[current], n*sizeof(*out));
        return n;
}
