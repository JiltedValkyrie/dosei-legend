/* Host adapter for src/navi.c: the same sine basis demo_camera.c uses. */
#include <math.h>
#include <stdint.h>

void kokiri_camera_sincos(uint16_t yaw, int32_t *sine, int32_t *cosine)
{
    double radians = yaw * 6.283185307179586 / 65536.0;
    *sine = (int32_t)(sin(radians) * 65536);
    *cosine = (int32_t)(cos(radians) * 65536);
}
