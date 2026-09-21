/* Host-only adapters: exercise the real controller and animation state code. */
#include <math.h>
#include "kokiri_camera.h"
#include "../../src/input_edge.h"

static input_edge_t test_edge;
void edge_reset(void) { test_edge = (input_edge_t){0}; }
void edge_sample(bool held) { input_edge_sample(&test_edge, held); }
int edge_consume(void) { return input_edge_consume(&test_edge); }

void kokiri_camera_sincos(uint16_t yaw, int32_t *sine, int32_t *cosine)
{
    double radians = yaw * 6.283185307179586 / 65536.0;
    *sine = (int32_t)(sin(radians) * 65536);
    *cosine = (int32_t)(cos(radians) * 65536);
}

void kokiri_collision_move_actor(camera_position_t *p, int32_t x,
                                 int32_t y, int32_t z)
{
    p->x += x; p->y += y; p->z += z;
}

void kokiri_collision_move(camera_position_t *p, int32_t x,
                           int32_t y, int32_t z)
{
    kokiri_collision_move_actor(p, x, y, z);
}

/* Control-mapping adapters. The real player_input.c and oot_follow.c are
** compiled in; these only expose their outputs to ctypes. */
#include "../../src/player_input.h"
#include "oot_follow.h"

static player_input_t   mapped;

void control_reset(void)
{
    player_input_reset();
    kokiri_camera_set_walk(false);
}

void control_sample(uint16_t held) { player_input_sample(held); }

void control_step(bool in_gameplay)
{
    player_input_step(in_gameplay, &mapped);
    kokiri_camera_set_walk(mapped.move_mode == PLAYER_MOVE_WALK);
}

/* One press-and-release of `held`, sampled across `vblanks` frames before the
** step runs, so a tap has to survive a slow rendered frame. */
void control_tap(uint16_t held, int vblanks)
{
    int i;

    player_input_sample(held);
    for (i = 0; i < vblanks; ++i)
        player_input_sample(0);
}

uint16_t control_move_buttons(void) { return mapped.move_buttons; }
int control_walking(void) { return mapped.move_mode == PLAYER_MOVE_WALK; }
int control_look_mode(void) { return mapped.look_mode; }
int control_look_exited(void) { return mapped.look_exited; }
int32_t control_look_yaw(void) { return mapped.look_yaw_delta; }
int32_t control_look_pitch(void) { return mapped.look_pitch_delta; }
int control_c_held(void) { return mapped.c_held; }
int control_c_pressed(void) { return mapped.c_pressed; }
int control_c_released(void) { return mapped.c_released; }
int control_jump(void) { return mapped.jump; }
int control_recenter(void) { return mapped.recenter; }
int control_interact(void) { return mapped.interact_pending; }
int control_cancel(void)   { return mapped.cancel_pending; }
int control_menu_step(void){ return mapped.menu_step; }
int control_attack(void) { return mapped.attack_pending; }
int control_shield(void) { return mapped.shield_held; }

/* Follow-camera look aim, so the bounds and the clean exit are checked against
** the real camera rather than a restatement of them. */
static oot_follow_t     follow;

void look_reset(void)
{
    camera_position_t player = {0, 0, 0};

    follow = (oot_follow_t){0};
    oot_follow_snap(&follow, &player, 0);
}

void look_drive(int steps, int32_t yaw_delta, int32_t pitch_delta)
{
    int i;

    for (i = 0; i < steps; ++i)
        oot_follow_look(&follow, yaw_delta, pitch_delta);
}

void look_exit(void) { oot_follow_look_exit(&follow); }
int32_t look_yaw(void) { return follow.look_yaw; }
int32_t look_pitch(void) { return follow.look_pitch; }
int look_active(void) { return oot_follow_looking(&follow); }

/* Eye position with the aim applied, to confirm look mode never translates the
** player and that releasing Z restores the plain follow eye exactly. */
void look_eye(camera_position_t *player, camera_position_t *eye_out,
              uint16_t *yaw_out, int32_t *pitch_out)
{
    oot_follow_update(&follow, player, 0, false, eye_out, yaw_out, pitch_out);
}
