#ifndef DOSEI_PLAYER_INPUT_H
#define DOSEI_PLAYER_INPUT_H
#include <stdbool.h>
#include <stdint.h>
#include "kokiri_camera.h"
#include "input_edge.h"

/*
** Saturn pad -> OoT control mapping, as approved 2026-09-18.
**
** This layer is deliberately platform-free: it takes a snapshot of held
** normalized CAMERA_* bits plus latched press edges, and produces the decisions
** gameplay needs. demo.c owns sampling (VBlank) and the fixed step; this file
** owns nothing but the mapping, so the host tests exercise the real code.
**
** The N64 reference is the manual at game/docs/refs: C is FOUR C BUTTONS, not
** an analog stick. Holding the Saturn C button turns the D-pad into that
** cluster. L holds the look camera; Z targets. Chord priority is L, then C, then movement,
** and a direction consumed by a modifier never leaks into locomotion.
*/

/* Persistent movement mode. Gameplay starts in run, which is what the slice
** already did before B existed. */
typedef enum
{
    PLAYER_MOVE_RUN = 0,
    PLAYER_MOVE_WALK
}                   player_move_mode_t;

/* One of the four N64 C buttons, or none this step. */
typedef enum
{
    PLAYER_C_NONE = 0,
    PLAYER_C_UP,
    PLAYER_C_DOWN,
    PLAYER_C_LEFT,
    PLAYER_C_RIGHT
}                   player_c_button_t;

/* Actions whose gameplay systems do not exist yet are reported as pending
** edges rather than being wired to some unrelated stand-in behavior. */
typedef struct
{
    /* Movement handed to kokiri_camera_update. Modifier-consumed directions
    ** are already removed. */
    uint16_t            move_buttons;
    player_move_mode_t  move_mode;
    bool                analog;
    int16_t             stick_x, stick_y; /* right/up positive, deadzone removed */
    /* Look camera. yaw/pitch deltas are binang per fixed step, zero unless
    ** look_mode is set. */
    bool                look_mode;
    bool                look_exited;        /* L released this step */
    int32_t             look_yaw_delta;
    int32_t             look_pitch_delta;
    /* C interface. `c_held` is the direction currently held (for future aiming);
    ** `c_pressed`/`c_released` are clean one-shot edges. */
    player_c_button_t   c_held;
    player_c_button_t   c_pressed;
    player_c_button_t   c_released;
    /* Wired behavior. */
    bool                jump;               /* Y */
    bool                recenter;           /* Z press edge, unless consumed by a chord */
    /* Z HELD, unless consumed by a chord. Hold targeting needs the button's
    ** state every step, not just its press edge: the lock lasts exactly as
    ** long as Z is down. Whether a press recentres is decided in gameplay.c,
    ** because it depends on whether the hold became a lock-on. */
    bool                target_held;
    /* Pending: no system implemented yet. */
    bool                cancel_pending;     /* B press, before walk/run uses it */
    int8_t              menu_dx, menu_dy, menu_page;
    int8_t              menu_step;          /* D-pad while a menu/box owns it */
    bool                interact_pending;   /* A */
    bool                attack_pending;     /* X */
    bool                attack_held;        /* raw physical X, even while UI owns pad */
    bool                attack_released;    /* consumed release edge, gameplay only */
    bool                shield_held;        /* R */
    /* A HELD: letting go of a ledge (Player_Action_8084BBE4 reads the button
    ** state, not a press). */
    bool                interact_held;
    bool                diagnostics_toggled;
    bool                camera_swap_toggled;
}                       player_input_t;

/* Look-camera aim rates, per 30 Hz step. These are deltas only: the bounds are
** OOT_LOOK_YAW_LIMIT/OOT_LOOK_PITCH_LIMIT in oot_follow.h, where the aim is
** actually accumulated, so there is one clamp rather than two. The look camera
** aims; it never translates the player and never falls back to a shoulder
** orbit. */
#define PLAYER_LOOK_YAW_SPEED   420
#define PLAYER_LOOK_PITCH_SPEED 280

void    player_input_reset(void);
/* Binding steals its original action only in gameplay; menu controls stay fixed. */
void player_input_set_jump_button(uint16_t mask);
/* Sample from VBlank: `held` is the normalized CAMERA_* snapshot. Maintains the
** press edges for B, Y, A, X and the four C directions. */
void    player_input_sample(uint16_t held);
/* 3D Pad axes: unsigned 0..255, centre 128, Y grows downward. */
void    player_input_sample_pad(uint16_t held, bool analog, uint8_t x, uint8_t y);
/* 3D Pad triggers: zero/centred rest deadzone, press >=176, release <=144. */
void    player_input_sample_3d(uint16_t held, bool analog, uint8_t x, uint8_t y,
                              uint8_t right_trigger, uint8_t left_trigger);
/* Camera-relative heading and proportional speed, including digital fallback.
** A light analog tilt (strength 1..42) returns a heading with zero speed for
** turning in place. False means no direction, not merely zero translation. */
bool    player_input_motion(const player_input_t *input, uint16_t yaw,
                            uint16_t *heading, int32_t *speed_q8);
/* controlStickSpinAngles >= 0: the stick is pushed at least 55 of 60
** (Player_ProcessControlStick). A digital direction is always full throw. */
bool    player_input_stick_pushed(const player_input_t *input);
/* Consume one fixed step's worth of decisions. `in_gameplay` false discards
** queued actions so title input never leaks into the world. */
void    player_input_step(bool in_gameplay, player_input_t *out);
/* A text box or the pause menu owns the pad: B closes it instead of toggling
** walk/run, the D-pad reports menu_step instead of movement, and no movement,
** jump, attack or guard leaves the mapper while it is open. */
void    player_input_set_dialogue(bool open);
/* Current persistent mode, for HUD/tests. */
player_move_mode_t player_input_move_mode(void);

#endif
