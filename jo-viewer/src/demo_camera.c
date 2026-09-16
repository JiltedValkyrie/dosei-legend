#include <jo/jo.h>
#include "../../title-screen/src/scene/kokiri_camera.c"

void kokiri_camera_sincos(uint16_t yaw, int32_t *sine, int32_t *cosine)
{
    *sine = slSin((ANGLE)yaw);
    *cosine = slCos((ANGLE)yaw);
}
