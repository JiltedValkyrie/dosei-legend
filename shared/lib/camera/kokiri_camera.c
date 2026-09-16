#include "kokiri_camera.h"

static int32_t actor_remainder_x, actor_remainder_z;

void kokiri_camera_reset_actor_motion(void)
{
        actor_remainder_x = actor_remainder_z = 0;
}

void kokiri_camera_update(camera_position_t *position, uint16_t *yaw,
    int32_t *pitch, uint16_t buttons, bool title_visible, bool actor_collision)
{
        /* Shoulder orbit belongs to the free-camera diagnostic only. Never
         * turn the gameplay camera as a side effect of targeting/shielding. */
        if (actor_collision)
                buttons &= (uint16_t)~(CAMERA_L | CAMERA_R);
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
                if (actor_collision) {
                        const int32_t rate = horizontal && vertical
                            ? LINK_RUN_SPEED_Q8 * 181 / 256 : LINK_RUN_SPEED_Q8;
                        actor_remainder_x += (horizontal*cosine + vertical*sine)*rate/256;
                        actor_remainder_z += (vertical*cosine - horizontal*sine)*rate/256;
                        dx = actor_remainder_x / 65536;
                        dz = actor_remainder_z / 65536;
                        actor_remainder_x -= dx * 65536;
                        actor_remainder_z -= dz * 65536;
                }
        }
        if (buttons & CAMERA_C) *pitch = 0;
        if (dx || dy || dz) {
                if (actor_collision)
                        kokiri_collision_move_actor(position, dx, dy, dz);
                else
                        kokiri_collision_move(position, dx, dy, dz);
        }
}
