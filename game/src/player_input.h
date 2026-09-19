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
** cluster. Z holds the look camera. Chord priority is Z, then C, then movement,
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
    /* Look camera. yaw/pitch deltas are binang per fixed step, zero unless
    ** look_mode is set. */
    bool                look_mode;
    bool                look_exited;        /* Z released this step */
    int32_t             look_yaw_delta;
    int32_t             look_pitch_delta;
    /* C interface. `c_held` is the direction currently held (for future aiming);
    ** `c_pressed`/`c_released` are clean one-shot edges. */
    player_c_button_t   c_held;
    player_c_button_t   c_pressed;
    player_c_button_t   c_released;
    /* Wired behavior. */
    bool                jump;               /* Y */
    bool                recenter;           /* L, unless consumed by a chord */
    /* Pending: no system implemented yet. */
    bool                cancel_pending;     /* B press, before walk/run uses it */
    int8_t              menu_step;          /* D-pad while a menu/box owns it */
    bool                interact_pending;   /* A */
    bool                attack_pending;     /* X */
    bool                shield_held;        /* R */
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
/* Sample from VBlank: `held` is the normalized CAMERA_* snapshot. Maintains the
** press edges for B, Y, A, X and the four C directions. */
void    player_input_sample(uint16_t held);
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
