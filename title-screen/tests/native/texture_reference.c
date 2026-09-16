/* Pre-optimization resampler, retained solely as a byte-exact test oracle.
 * Keep its multiply/divide interpolation independent of the optimized stepper. */
#include "kokiri_clip.h"
void reference_clip_texture(const uint8_t *source, unsigned size,
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
                        unsigned u = c == 65536 ? 0 :
                            (unsigned)((b*(int32_t)(size-1)+(65536-c)/2)/(65536-c));
                        unsigned v = (c*(size-1)+32768)/65536;
                        unsigned texel = v*size+u;
                        unsigned index = (source[texel/2] >> ((texel&1) ? 0 : 4)) & 15;
                        unsigned dest = y*8+x/2;
                        if (x&1) tile[dest] |= index;
                        else tile[dest] = index << 4;
                }
        }
}
