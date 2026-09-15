#ifndef KOKIRI_CAMERA_H
#define KOKIRI_CAMERA_H
#include "kokiri_collision.h"
/* Normalized libyaul digital-pad bits; no platform bitfield layout dependency. */
#define CAMERA_L 0x0008
#define CAMERA_Z 0x0010
#define CAMERA_Y 0x0020
#define CAMERA_X 0x0040
#define CAMERA_R 0x0080
#define CAMERA_C 0x0200
#define CAMERA_UP 0x1000
#define CAMERA_DOWN 0x2000
#define CAMERA_LEFT 0x4000
#define CAMERA_RIGHT 0x8000
#define CAMERA_AUTO_TURN_SPEED 90
#define CAMERA_MOVE_SPEED 16
#define CAMERA_DIAGONAL_SPEED 12
#define CAMERA_TURN_SPEED 360
#define CAMERA_PITCH_SPEED 240
#define CAMERA_PITCH_LIMIT 14500
void kokiri_camera_sincos(uint16_t yaw, int32_t *sine, int32_t *cosine);
void kokiri_camera_update(camera_position_t *position, uint16_t *yaw,
    int32_t *pitch, uint16_t buttons, bool title_visible);
#endif
