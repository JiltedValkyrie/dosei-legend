#include <jo/jo.h>
#include "../../shared/lib/camera/kokiri_camera.c"

void kokiri_camera_sincos(uint16_t yaw, int32_t *sine, int32_t *cosine)
{
    *sine = slSin((ANGLE)yaw);
    *cosine = slCos((ANGLE)yaw);
}

/* Heading of a movement delta, in the same basis kokiri_camera_update uses:
 * forward is (sin,cos), so the heading is atan2(dx, dz). */
uint16_t kokiri_camera_facing(int32_t dx, int32_t dz)
{
    return (uint16_t)slAtan(toFIXED(dz), toFIXED(dx));
}
