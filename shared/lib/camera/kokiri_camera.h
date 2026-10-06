#ifndef KOKIRI_CAMERA_H
#define KOKIRI_CAMERA_H
#include "kokiri_collision.h"
/* Normalized libyaul digital-pad bits; no platform bitfield layout dependency. */
#define CAMERA_L 0x0008
#define CAMERA_Z 0x0010
#define CAMERA_Y 0x0020
#define CAMERA_X 0x0040
#define CAMERA_R 0x0080
#define CAMERA_B 0x0100
#define CAMERA_C 0x0200
#define CAMERA_A 0x0400
#define CAMERA_START 0x0800
#define CAMERA_UP 0x1000
#define CAMERA_DOWN 0x2000
#define CAMERA_LEFT 0x4000
#define CAMERA_RIGHT 0x8000
#define CAMERA_AUTO_TURN_SPEED 90
#define CAMERA_MOVE_SPEED 16
/* Child Kokiri boots: 5.5 * (3/2) units at 20 Hz = 165 units/s.
 * At our 30 Hz update this is 5.5 units; keep its fractional part. */
#define LINK_RUN_SPEED_Q8 1408
/* Walking mode, selected by the B toggle. A digital pad carries no stick
 * magnitude, so walking is a fixed 3 units/step (90 units/s) -- deliberately
 * under link_anim_state's RUN_SPEED_MIN so the walk clip is chosen from the
 * distance actually travelled. */
#define LINK_WALK_SPEED_Q8 768
#define CAMERA_DIAGONAL_SPEED 12
#define CAMERA_TURN_SPEED 360
#define CAMERA_PITCH_SPEED 240
#define CAMERA_PITCH_LIMIT 14500
void kokiri_camera_sincos(uint16_t yaw, int32_t *sine, int32_t *cosine);
/* Heading of a movement delta, atan2(dx, dz) in this basis. Supplied by the
 * platform (recomp_camera.c on Saturn, libm in the host tests). */
uint16_t kokiri_camera_facing(int32_t dx, int32_t dz);
void kokiri_camera_reset_actor_motion(void);
/* Persistent grounded locomotion speed for the actor path. false = run (the
 * default), true = walk. Does not affect the free diagnostic camera. */
void kokiri_camera_set_walk(bool walk);
bool kokiri_camera_walking(void);
/* Move the actor `speed_q8` world units along `heading`, through the same
 * collision and sub-unit remainder the button path uses. Used by moves that
 * travel on their own (roll today; sidehop and backflip later), so they share
 * one integer accumulator instead of each inventing a second one. */
/* Heading the D-pad is asking to travel in, given the camera's yaw. false when
 * no direction is held. Built from the same basis kokiri_camera_update() moves
 * in, so callers never re-derive it and get the handedness wrong. */
bool kokiri_camera_input_heading(uint16_t camera_yaw, uint16_t buttons,
    uint16_t *heading);
void kokiri_camera_move_heading(camera_position_t *position, uint16_t heading,
    int32_t speed_q8);
void kokiri_camera_update(camera_position_t *position, uint16_t *yaw,
    int32_t *pitch, uint16_t buttons, bool title_visible, bool actor_collision);
#endif
