#include "kokiri_camera.h"

#ifndef ABLATE_COLLISION
#define ABLATE_COLLISION 0
#endif

void kokiri_camera_update(camera_position_t *position, uint16_t *yaw,
    int32_t *pitch, uint16_t buttons, bool title_visible)
{
        const uint16_t controls = CAMERA_L | CAMERA_R | CAMERA_X | CAMERA_Z |
            CAMERA_Y | CAMERA_C | CAMERA_UP | CAMERA_DOWN | CAMERA_LEFT | CAMERA_RIGHT;
        /* Keep the title's idle rotation, but never lock manual camera input
         * merely because the logo layer is still visible. */
        if (!(buttons & controls)) {
                if (title_visible) *yaw += CAMERA_AUTO_TURN_SPEED;
                return;
        }

        /* Unsigned angle wraps at one revolution. Opposite buttons cancel. */
        if (buttons & CAMERA_L) *yaw = (uint16_t)(*yaw - CAMERA_TURN_SPEED);
        if (buttons & CAMERA_R) *yaw = (uint16_t)(*yaw + CAMERA_TURN_SPEED);
        const int horizontal = !!(buttons & CAMERA_RIGHT) - !!(buttons & CAMERA_LEFT);
        const int vertical = !!(buttons & CAMERA_UP) - !!(buttons & CAMERA_DOWN);
        int32_t dx = 0, dz = 0;
        const int32_t dy = (!!(buttons & CAMERA_X)-!!(buttons & CAMERA_Z))*CAMERA_MOVE_SPEED;
        if (buttons & CAMERA_Y) {
                *pitch += vertical*CAMERA_PITCH_SPEED;
                if (*pitch > CAMERA_PITCH_LIMIT) *pitch = CAMERA_PITCH_LIMIT;
                if (*pitch < -CAMERA_PITCH_LIMIT) *pitch = -CAMERA_PITCH_LIMIT;
        } else if (horizontal || vertical) {
                int32_t sine, cosine;
                kokiri_camera_sincos(*yaw, &sine, &cosine);
                const int speed = horizontal && vertical ? CAMERA_DIAGONAL_SPEED : CAMERA_MOVE_SPEED;
                /* |sin|,|cos| <= 65536 and axes are -1/0/1: fits int32_t. */
                dx = (horizontal*cosine + vertical*sine)*speed/65536;
                dz = (vertical*cosine - horizontal*sine)*speed/65536;
        }
        if (buttons & CAMERA_C) *pitch = 0;
#if ABLATE_COLLISION
        /* Ablation: move freely, no collision test. Camera will pass through
         * geometry; never ship. Note this is only reachable when the camera
         * updates at all - PERF_BENCH holds a fixed pose, so in that build
         * per-frame collision is already absent and this changes nothing. */
        position->x += dx; position->y += dy; position->z += dz;
#else
        if (dx || dy || dz) kokiri_collision_move(position, dx, dy, dz);
#endif
}
