/* Host adapters for traversal tests: the real collision, movement basis,
** departure rules and animation state are compiled in; only the SGL trig the
** Saturn gets from demo_camera.c is replaced here. */
#include <math.h>
#include <stdint.h>

void kokiri_camera_sincos(uint16_t yaw, int32_t *sine, int32_t *cosine)
{
    double radians = yaw * 6.283185307179586 / 65536.0;
    *sine = (int32_t)(sin(radians) * 65536);
    *cosine = (int32_t)(cos(radians) * 65536);
}

uint16_t kokiri_camera_facing(int32_t dx, int32_t dz)
{
    double a = atan2((double)dx, (double)dz) * 65536.0 / 6.283185307179586;
    return (uint16_t)(int32_t)(a < 0 ? a + 65536.0 : a);
}
