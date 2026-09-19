/*
** Saturn pad -> OoT control mapping. See player_input.h for the layout and the
** approved requirements; game/docs/OPUS_HANDOFF.md holds the directive itself.
**
** All state lives here so the mapping is one place, not spread between the
** VBlank callback and the fixed step. VBlank only calls player_input_sample();
** the fixed step only calls player_input_step().
*/

#include "player_input.h"

#define DPAD_MASK (CAMERA_UP | CAMERA_DOWN | CAMERA_LEFT | CAMERA_RIGHT)

static volatile uint16_t    held_snapshot;
static player_move_mode_t   move_mode;
static bool                 dialogue_open;
static input_edge_t         edge_walk_toggle;   /* B */
static input_edge_t         edge_jump;          /* Y */
static input_edge_t         edge_interact;      /* A */
static input_edge_t         edge_attack;        /* X */
static input_edge_t         edge_recenter;      /* L */
/* One edge per C direction, so holding C+Up does not repeat and a future held
** item (aiming) needs no further input rewrite. */
static input_edge_t         edge_c[4];
/* Menu cursor edges: the raw D-pad, taken before the modifier routing, so a
** paused game can step the list without C or Z having any say. */
static input_edge_t         edge_menu[4];
/* Release counters for the C directions. A rising-edge latch counts presses, so
** releases are counted with their own pair of counters rather than by inverting
** the input (which would report a phantom release before the first press). */
static volatile unsigned int c_release_produced[4];
static unsigned int          c_release_consumed[4];
static bool                  c_direction_held[4];
static bool                 look_was_active;
static bool                 diagnostics_chord_held;

static const uint16_t       c_direction_bit[4] = {
    CAMERA_UP, CAMERA_DOWN, CAMERA_LEFT, CAMERA_RIGHT
};

void player_input_reset(void)
{
    unsigned int i;

    held_snapshot = 0;
    /* Run, not walk: this preserves the speed the slice already shipped. */
    move_mode = PLAYER_MOVE_RUN;
    dialogue_open = false;
    edge_walk_toggle = edge_jump = edge_interact = edge_attack =
        edge_recenter = (input_edge_t){0};
    for (i = 0; i < 4; ++i)
    {
        edge_c[i] = (input_edge_t){0};
        edge_menu[i] = (input_edge_t){0};
        c_release_produced[i] = c_release_consumed[i] = 0;
        c_direction_held[i] = false;
    }
    look_was_active = false;
    diagnostics_chord_held = false;
}

void player_input_sample(uint16_t held)
{
    unsigned int i;
    bool look = (held & CAMERA_Z) != 0;
    bool c_mode = !look && (held & CAMERA_C) != 0;

    held_snapshot = held;
    input_edge_sample(&edge_walk_toggle, (held & CAMERA_B) != 0);
    input_edge_sample(&edge_jump, (held & CAMERA_Y) != 0);
    input_edge_sample(&edge_interact, (held & CAMERA_A) != 0);
    input_edge_sample(&edge_attack, (held & CAMERA_X) != 0);
    input_edge_sample(&edge_recenter, (held & CAMERA_L) != 0);
    for (i = 0; i < 4; ++i)
        input_edge_sample(&edge_menu[i], (held & c_direction_bit[i]) != 0);
    for (i = 0; i < 4; ++i)
    {
        bool down = c_mode && (held & c_direction_bit[i]) != 0;
        input_edge_sample(&edge_c[i], down);
        if (!down && c_direction_held[i])
            ++c_release_produced[i];
        c_direction_held[i] = down;
    }
}

/* Priority order: Z look, then C buttons, then ordinary movement. */
void player_input_step(bool in_gameplay, player_input_t *out)
{
    uint16_t held = held_snapshot;
    uint16_t dpad = held & DPAD_MASK;
    bool look = (held & CAMERA_Z) != 0;
    bool c_mode = !look && (held & CAMERA_C) != 0;
    bool toggled = input_edge_consume(&edge_walk_toggle);
    bool jumped = input_edge_consume(&edge_jump);
    bool interacted = input_edge_consume(&edge_interact);
    bool attacked = input_edge_consume(&edge_attack);
    bool recentered = input_edge_consume(&edge_recenter);
    bool c_pressed[4], c_released[4];
    unsigned int i;
    int horizontal, vertical;

    for (i = 0; i < 4; ++i)
    {
        unsigned int releases = c_release_produced[i];

        c_pressed[i] = input_edge_consume(&edge_c[i]);
        c_released[i] = releases != c_release_consumed[i];
        c_release_consumed[i] = releases;
    }

    out->move_buttons = 0;
    out->look_mode = false;
    out->look_exited = false;
    out->look_yaw_delta = 0;
    out->look_pitch_delta = 0;
    out->c_held = PLAYER_C_NONE;
    out->c_pressed = PLAYER_C_NONE;
    out->c_released = PLAYER_C_NONE;
    out->jump = false;
    out->recenter = false;
    out->interact_pending = false;
    out->attack_pending = false;
    out->shield_held = false;
    out->diagnostics_toggled = false;
    out->camera_swap_toggled = false;
    out->cancel_pending = false;
    out->menu_step = 0;
    out->move_mode = move_mode;

    if (!in_gameplay)
    {
        /* Title input is discarded, not queued for the first gameplay step. */
        look_was_active = false;
        diagnostics_chord_held = false;
        return;
    }

    /* L+R is the development diagnostics chord and CONSUMES both buttons, so
    ** asking for diagnostics never also recenters or raises the shield. It is
    ** gated to diagnostic builds: the clean player-facing disc leaves L and R
    ** free to be pressed together for targeting plus shielding, which the
    ** chord would otherwise block. */
#ifndef DOSEI_CLEAN_TEST
    if ((held & CAMERA_L) && (held & CAMERA_R))
    {
        bool swap = (dpad & CAMERA_UP) != 0;

        if (!diagnostics_chord_held)
        {
            if (swap) out->camera_swap_toggled = true;
            else out->diagnostics_toggled = true;
        }
        diagnostics_chord_held = true;
        look_was_active = look;
        return;
    }
    diagnostics_chord_held = false;
#endif

    out->shield_held = (held & CAMERA_R) != 0;
    out->cancel_pending = toggled;
    /* Menu cursor: up/left step back, down/right step forward, one slot per
    ** physical press. Taken from the raw D-pad so the pause menu still works
    ** with C or Z held, and consumed here so a press never reaches both the
    ** menu and locomotion. */
    out->menu_step = 0;
    for (i = 0; i < 4; ++i)
    {
        if (!input_edge_consume(&edge_menu[i]))
            continue;
        if (!dialogue_open)
            continue;
        out->menu_step = (c_direction_bit[i] == CAMERA_UP ||
                          c_direction_bit[i] == CAMERA_LEFT) ? -1 : 1;
    }
    /* B toggles the persistent mode once per physical press -- unless a text
    ** box has the pad, where the same press closes the box instead. One press
    ** never does both. */
    if (toggled && !dialogue_open)
        move_mode = move_mode == PLAYER_MOVE_RUN ? PLAYER_MOVE_WALK
                                                 : PLAYER_MOVE_RUN;
    out->move_mode = move_mode;
    out->interact_pending = interacted;
    out->attack_pending = attacked;

    if (dialogue_open)
    {
        out->attack_pending = false;
        out->shield_held = false;
        out->look_exited = look_was_active;
        look_was_active = false;
        return;
    }

    if (look)
    {
        /* Look mode aims the view only: no translation, no C items, no shield
        ** substitution and no shoulder orbit. */
        horizontal = !!(dpad & CAMERA_RIGHT) - !!(dpad & CAMERA_LEFT);
        vertical = !!(dpad & CAMERA_UP) - !!(dpad & CAMERA_DOWN);
        out->look_mode = true;
        out->look_yaw_delta = horizontal * PLAYER_LOOK_YAW_SPEED;
        out->look_pitch_delta = vertical * PLAYER_LOOK_PITCH_SPEED;
        out->shield_held = false;
        look_was_active = true;
        /* Y is consumed rather than queued: a jump must not fire the instant Z
        ** is released. */
        return;
    }
    if (look_was_active)
        out->look_exited = true;
    look_was_active = false;

    if (c_mode)
    {
        /* Literal direction mapping, and the D-pad is consumed: nothing here
        ** reaches locomotion. */
        for (i = 0; i < 4; ++i)
        {
            if (held & c_direction_bit[i])
                out->c_held = (player_c_button_t)(PLAYER_C_UP + i);
            if (c_pressed[i])
                out->c_pressed = (player_c_button_t)(PLAYER_C_UP + i);
            if (c_released[i])
                out->c_released = (player_c_button_t)(PLAYER_C_UP + i);
        }
        return;
    }
    /* Report C releases that happened as C itself was let go, so a held item
    ** cannot be left stuck on. */
    for (i = 0; i < 4; ++i)
        if (c_released[i])
            out->c_released = (player_c_button_t)(PLAYER_C_UP + i);

    out->move_buttons = dpad;
    out->jump = jumped;
    out->recenter = recentered;
}

void    player_input_set_dialogue(bool open)
{
    dialogue_open = open;
}

player_move_mode_t player_input_move_mode(void)
{
    return move_mode;
}
