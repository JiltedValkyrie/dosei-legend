#ifndef DOSEI_ROOM_PORTAL_H
#define DOSEI_ROOM_PORTAL_H
#include <stdint.h>

/* Source En_Holl tunnel volumes. Kind 0 uses a single resident room rather
 * than source dual-room prefetch; swap after crossing its plane. Its fading
 * plane presentation is tracked separately from the room connectivity.
 * Shutters still require their actor lifecycle and are not open portals.
 * Coordinates are actor-local source units, not Q16 or Link eye height. */
static inline int room_portal_side(unsigned int kind, int32_t x, int32_t y, int32_t z)
{
    if (kind == 0) {
        if (y > -50 && y < 200 && x > -100 && x < 100 &&
            ((z > 5 && z < 100) || (z < -5 && z > -100)))
            return z < 0 ? 0 : 1;
    } else if (kind == 2) {
        if (x <= -120 || x >= 120 || z <= -120 || z >= 120 ||
            x*x + z*z >= 120*120) return -1;
        if ((y > 50 && y < 200) || (y < -50 && y > -200))
            return y > 0 ? 0 : 1;
    } else if (kind == 4 || kind == 6) {
        int width = kind == 6 ? 100 : 200;
        if (y > -50 && y < 200 && x > -width && x < width &&
            ((z > 50 && z < 100) || (z < -50 && z > -100)))
            return z < 0 ? 0 : 1;
    }
    return -1;
}
#endif
