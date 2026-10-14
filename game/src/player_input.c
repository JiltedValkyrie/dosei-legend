#pragma GCC optimize("Os") /* per-step logic, small: size over speed (work RAM) */
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
static volatile bool analog_snapshot;
static volatile uint8_t axis_x, axis_y;
static bool trigger_right_held, trigger_left_held;
static player_move_mode_t   move_mode;
static bool                 dialogue_open;
/* B: hold = walk, short tap = cancel / put away the held item. Counted per
** VBlank in sample_pad. A press that lands while a text box, menu or first-
** person view owns the pad is CLAIMED: it cancels on the press itself and then
** neither walks nor taps on release, so one press never acts twice. */
#define B_TAP_TICKS 12
static volatile unsigned int b_ticks;
static volatile bool         b_down, b_claimed;
static volatile unsigned int b_cancel_produced;     /* claimed press or tap */
static unsigned int          b_cancel_consumed;
static volatile uint16_t jump_button = CAMERA_Y;
static input_edge_t         edge_jump;          /* Y */
static input_edge_t         edge_interact;      /* A */
static input_edge_t         edge_attack;        /* X */
static volatile unsigned int attack_release_produced;
static unsigned int attack_release_consumed;
static input_edge_t         edge_recenter;      /* Z: tap recentres */
/* One edge per C direction, so holding C+Up does not repeat and a future held
** item (aiming) needs no further input rewrite. */
static input_edge_t         edge_c[4];
/* Menu cursor edges: the raw D-pad, taken before the modifier routing, so a
** paused game can step the list without C or L having any say. */
static input_edge_t         edge_menu[4];
static input_edge_t         edge_assign[4];
static input_edge_t         edge_page[2];
/* Release counters for the C directions. A rising-edge latch counts presses, so
** releases are counted with their own pair of counters rather than by inverting
** the input (which would report a phantom release before the first press). */
static volatile unsigned int c_release_produced[4];
static unsigned int          c_release_consumed[4];
static bool                  c_direction_held[4];
static bool                 look_was_active;
static bool                 view_look;
static bool orbit_active;
static int8_t orbit_direction;
static bool orbit_b_claimed;
void player_input_set_orbit(bool active) { orbit_active=active; }
void player_input_set_view_look(bool active) { view_look = active; }
/* Item aim (human 2026-10-12): B tap cancels on release; held B steadies
 * the digital aim at low frame rates instead of cancelling on press. */
static bool view_aim;
void player_input_set_item_aim(bool active) { view_aim = active; }
static bool                 diagnostics_chord_held;
static input_edge_t edge_camera_experiment;
static volatile bool camera_experiment_held;

static const uint16_t       c_direction_bit[4] = {
    CAMERA_UP, CAMERA_DOWN, CAMERA_LEFT, CAMERA_RIGHT
};

void player_input_set_jump_button(uint16_t mask) { jump_button = mask; }

void player_input_reset(void)
{
    unsigned int i;

    edge_page[0] = edge_page[1] = (input_edge_t){0};
    held_snapshot = 0;
    analog_snapshot = false;
    trigger_right_held = trigger_left_held = false;
    axis_x = axis_y = 128;
    /* Run, not walk: this preserves the speed the slice already shipped. */
    move_mode = PLAYER_MOVE_RUN;
    dialogue_open = false;
    orbit_active=false;orbit_direction=0;orbit_b_claimed=false;
    attack_release_produced = attack_release_consumed = 0;
    edge_jump = edge_interact = edge_attack =
        edge_recenter = (input_edge_t){0};
    b_ticks = 0;
    b_down = b_claimed = false;
    b_cancel_consumed = b_cancel_produced;
    for (i = 0; i < 4; ++i)
    {
        edge_c[i] = (input_edge_t){0};
        edge_menu[i] = edge_assign[i] = (input_edge_t){0};
        c_release_produced[i] = c_release_consumed[i] = 0;
        c_direction_held[i] = false;
    }
    look_was_active = view_look = false;
    diagnostics_chord_held = false;
    edge_camera_experiment = (input_edge_t){0};
    camera_experiment_held = false;
}

void player_input_sample(uint16_t held)
{
    player_input_sample_pad(held, false, 128, 128);
}

void player_input_sample_3d(uint16_t held, bool analog, uint8_t x, uint8_t y,
                            uint8_t right_trigger, uint8_t left_trigger)
{
    /* Accept zero-rest and centred-rest axes. 128 is neutral on some host
     * mappings, not a press. Separate press/release thresholds prevent
     * chatter; returning to the neutral band always releases the latch. */
    if (analog) {
        trigger_right_held = right_trigger >= (trigger_right_held ? 145 : 176);
        trigger_left_held = left_trigger >= (trigger_left_held ? 145 : 176);
        if (trigger_right_held) held |= CAMERA_R;
        if (trigger_left_held) held |= CAMERA_L;
    } else
        trigger_right_held = trigger_left_held = false;
    player_input_sample_pad(held, analog, x, y);
}

void player_input_sample_pad(uint16_t held, bool analog, uint8_t x, uint8_t y)
{
    unsigned int i;
    const uint16_t chord = CAMERA_L | CAMERA_R | CAMERA_B;
    bool pressed = !dialogue_open && (held & chord) == chord;
    input_edge_sample(&edge_camera_experiment, pressed && !camera_experiment_held);
    if (pressed) camera_experiment_held = true;
    if (!(held & chord)) camera_experiment_held = false;
    if (camera_experiment_held) {
        held &= (uint16_t)~chord;
        b_down = b_claimed = false;
        b_ticks = 0;
    }
    if (!(held & CAMERA_B)) orbit_b_claimed=false;
    /* Overhead camera (human 2026-10-08): C-Up turns one way, B+C-Up the
     * other; Z stays Z-targeting. C-Up is C+Up digital, D-pad Up analog. */
    if (orbit_active && !dialogue_open && !view_look &&
        (analog || (held & CAMERA_C)) && (held & CAMERA_UP)) {
        if (!edge_c[0].held) orbit_direction=(held & CAMERA_B) ? -1 : 1;
        /* Claim B until release, including when B was held before C-Up. */
        if (held & CAMERA_B) orbit_b_claimed=true;
    }
    if (orbit_b_claimed) { held &= (uint16_t)~CAMERA_B; b_down=false; }
    input_edge_sample(&edge_jump, (held & jump_button) != 0);
    if (!dialogue_open) held &= (uint16_t)~jump_button;
    bool c_mode = analog || (held & CAMERA_C) != 0;

    input_edge_sample(&edge_page[0], (held & CAMERA_L) != 0);
    input_edge_sample(&edge_page[1], (held & CAMERA_R) != 0);
    held_snapshot = held;
    analog_snapshot = analog;
    axis_x = x; axis_y = y;
    if (held & CAMERA_B) {
        if (!b_down) {
            b_down = true;
            b_claimed = dialogue_open || (view_look && !view_aim);
            if (b_claimed) ++b_cancel_produced;
        }
        if (b_ticks < 255) ++b_ticks;
    } else {
        if (b_down && !b_claimed && b_ticks < B_TAP_TICKS) ++b_cancel_produced;
        b_down = b_claimed = false;
        b_ticks = 0;
    }
    input_edge_sample(&edge_interact, (held & CAMERA_A) != 0);
    if (!(held & CAMERA_X) && edge_attack.held) ++attack_release_produced;
    input_edge_sample(&edge_attack, (held & CAMERA_X) != 0);
    input_edge_sample(&edge_recenter, (held & CAMERA_Z) != 0);
    for (i = 0; i < 4; ++i) {
        bool assign = dialogue_open && (held & CAMERA_C) != 0;
        input_edge_sample(&edge_menu[i], !assign && (held & c_direction_bit[i]) != 0);
        input_edge_sample(&edge_assign[i], assign && (held & c_direction_bit[i]) != 0);
    }
    for (i = 0; i < 4; ++i)
    {
        bool down = c_mode && (held & c_direction_bit[i]) != 0;
        input_edge_sample(&edge_c[i], down);
        if (!down && c_direction_held[i])
            ++c_release_produced[i];
        c_direction_held[i] = down;
    }
}

/* Integer radius, bounded to 181 for the two signed byte axes. */
static int stick_radius(int x, int y)
{
    unsigned int square = x * x + y * y;
    unsigned int root = 0, bit;
    for (bit = 128; bit; bit >>= 1)
        if ((root + bit) * (root + bit) <= square) root += bit;
    return (int)root;
}

/* Priority order: active C-Up view, then C buttons, then movement. Z is the
** target button and is read on the movement path, so holding it strafes. */
void player_input_step(bool in_gameplay, player_input_t *out)
{
    bool camera_experiment = input_edge_consume(&edge_camera_experiment);
    bool analog = analog_snapshot;
    uint16_t held = held_snapshot;
    uint16_t dpad = held & DPAD_MASK;
    bool look = view_look;
    bool c_mode = analog || (held & CAMERA_C) != 0;
    unsigned int b_cancels = b_cancel_produced;
    bool toggled = b_cancels != b_cancel_consumed;
    bool jumped = input_edge_consume(&edge_jump);
    bool interacted = input_edge_consume(&edge_interact);
    bool attacked = input_edge_consume(&edge_attack);
    unsigned int attack_releases = attack_release_produced;
    bool attack_released = attack_releases != attack_release_consumed;
    bool recentered = input_edge_consume(&edge_recenter);
    bool page_left = input_edge_consume(&edge_page[0]);
    bool page_right = input_edge_consume(&edge_page[1]);
    bool c_pressed[4], c_released[4], assigned[4];
    unsigned int i;
    int horizontal, vertical;
    attack_release_consumed = attack_releases;
    b_cancel_consumed = b_cancels;
    /* In the world holding B walks; a claimed press never walks. */
    move_mode = (!dialogue_open && !look && !b_claimed && (held & CAMERA_B))
                    ? PLAYER_MOVE_WALK : PLAYER_MOVE_RUN;

    for (i = 0; i < 4; ++i)
    {
        unsigned int releases = c_release_produced[i];

        assigned[i] = input_edge_consume(&edge_assign[i]);
        c_pressed[i] = input_edge_consume(&edge_c[i]);
        c_released[i] = releases != c_release_consumed[i];
        c_release_consumed[i] = releases;
    }

    out->analog = analog;
    out->stick_x = out->stick_y = 0;
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
    out->target_held = false;
    out->interact_pending = false;
    out->attack_pending = false;
    out->attack_held = (held & CAMERA_X) != 0;
    out->attack_released = false;
    out->shield_held = false;
    out->interact_held = false;
    out->diagnostics_toggled = false;
    out->camera_swap_toggled = false;
    out->job_order_toggled = false;
    out->envelope_toggled = false;
    out->camera_experiment_toggled = false;
    out->camera_orbit_turn = 0;
    out->map_toggled = false;
    out->cancel_pending = false;
    out->menu_dx = out->menu_dy = out->menu_page = 0;
    out->menu_hold_x = out->menu_hold_y = 0;
    out->menu_step = 0;
    out->move_mode = move_mode;

    if (!in_gameplay)
    {
        /* Title input is discarded, not queued for the first gameplay step. */
        look_was_active = false;
        diagnostics_chord_held = false;
        return;
    }

    if (!dialogue_open && (camera_experiment || camera_experiment_held)) {
        out->camera_experiment_toggled = camera_experiment;
        out->attack_held = false;
        return;
    }

    /* Development diagnostics chord: L+R plus a direction, and it CONSUMES all
    ** of them, so asking for diagnostics never also looks or raises the shield.
    ** A DIRECTION is required because L is the look button as of this layout:
    ** plain L+R is looking while guarding, an ordinary gameplay combination the
    ** chord must not swallow. Up swaps the camera, Down toggles the panel,
    ** Left flips the second-SH-2 job order (performance A/B).
    ** Gated to diagnostic builds; the clean player disc has neither. */
#ifndef DOSEI_CLEAN_TEST
    /* 3D pad analog mode: the stick also gives the direction (up = small y). */
    uint16_t chord_dir = dpad & (CAMERA_UP | CAMERA_DOWN | CAMERA_LEFT | CAMERA_RIGHT);
    if (analog) {
        if (axis_y < 64) chord_dir |= CAMERA_UP;
        else if (axis_y > 192) chord_dir |= CAMERA_DOWN;
    }   /* Left/Right are D-pad only: guarding while strafing must not flip jobs. */
    if (!dialogue_open && (held & CAMERA_L) && (held & CAMERA_R) && chord_dir)
    {
        bool swap = (chord_dir & CAMERA_UP) != 0;

        if (!diagnostics_chord_held)
        {
            if (swap) out->camera_swap_toggled = true;
            else if (chord_dir & CAMERA_DOWN) out->diagnostics_toggled = true;
            else if (chord_dir & CAMERA_LEFT) out->job_order_toggled = true;
            else out->envelope_toggled = true;
        }
        diagnostics_chord_held = true;
        look_was_active = look;
        return;
    }
    diagnostics_chord_held = false;
#endif

    out->shield_held = (held & CAMERA_R) != 0;
    out->interact_held = (held & CAMERA_A) != 0;
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

        if (i < 2) out->menu_dy = i == 0 ? -1 : 1;
        else out->menu_dx = i == 2 ? -1 : 1;
        out->menu_step = (c_direction_bit[i] == CAMERA_UP ||
                          c_direction_bit[i] == CAMERA_LEFT) ? -1 : 1;
    }
    if (dialogue_open) {
        out->menu_page = page_right - page_left;
        for (i = 0; i < 4; ++i)
            if (assigned[i]) out->c_pressed = (player_c_button_t)(PLAYER_C_UP + i);
        if (out->c_pressed != PLAYER_C_NONE)
            out->menu_step = out->menu_dx = out->menu_dy = 0;
    }
    out->move_mode = move_mode;
    out->interact_pending = interacted;
    out->attack_pending = attacked;
    out->attack_released = attack_released;

    if (dialogue_open)
    {
        int hx = !!(held & c_direction_bit[3]) - !!(held & c_direction_bit[2]);
        int hy = !!(held & c_direction_bit[0]) - !!(held & c_direction_bit[1]);
        hx *= 70; hy *= 70;
        if (analog) {
            /* N64 stick reaches about +-80; ours +-127 from the centre. */
            int sx = ((int)axis_x - 128) * 80 / 127, sy = (128 - (int)axis_y) * 80 / 127;
            if (sx > 30 || sx < -30) hx = sx;
            if (sy > 30 || sy < -30) hy = sy;
        }
        out->menu_hold_x = (int8_t)hx;
        out->menu_hold_y = (int8_t)hy;
        out->attack_pending = false;
        out->attack_released = false;
        out->shield_held = false;
        out->interact_held = false;
        out->look_exited = look_was_active;
        look_was_active = false;
        return;
    }

    if (analog)
    {
        int x = (int)axis_x - 128, y = 128 - (int)axis_y;
        int radius = stick_radius(x, y);
        /* Circular 16-unit deadzone; full throw at 127. Preserve direction. */
        if (radius > 16)
        {
            int strength = radius >= 127 ? 127 : (radius - 16) * 127 / 111;
            out->stick_x = x * strength / radius;
            out->stick_y = y * strength / radius;
        }
    }

    if (look)
    {
        /* Look mode aims the view only: no translation, no C items, no shield
        ** substitution and no shoulder orbit. */
        horizontal = !!(dpad & CAMERA_RIGHT) - !!(dpad & CAMERA_LEFT);
        vertical = !!(dpad & CAMERA_UP) - !!(dpad & CAMERA_DOWN);
        if (!analog && (held & CAMERA_C)) horizontal = vertical = 0;
        out->look_mode = true;
        for (i = 0; i < 4; ++i) {
            if (c_released[i]) out->c_released = (player_c_button_t)(PLAYER_C_UP + i);
            if (c_pressed[i]) out->c_pressed = (player_c_button_t)(PLAYER_C_UP + i);
        }
        out->look_exited = interacted || attacked || toggled || recentered ||
            (held & CAMERA_R) || jumped || out->c_pressed != PLAYER_C_NONE;
        /* NEGATED, same handedness correction as the movement basis. With a
        ** +Y-up, +Z-forward camera, screen right is (f x up) = -X, so
        ** INCREASING yaw swings the view to the left. Pressing right must
        ** therefore decrease it. */
        out->look_yaw_delta = analog ? -out->stick_x * PLAYER_LOOK_YAW_SPEED / 127
                                    : -horizontal * PLAYER_LOOK_YAW_SPEED;
        out->look_pitch_delta = analog ? out->stick_y * PLAYER_LOOK_PITCH_SPEED / 127
                                      : vertical * PLAYER_LOOK_PITCH_SPEED;
        if (view_aim && !analog && (held & CAMERA_B)) {
            out->look_yaw_delta /= 3;
            out->look_pitch_delta /= 3;
        }
        out->stick_x = out->stick_y = 0;
        out->shield_held = false;
        look_was_active = true;
        out->attack_pending = false;
        /* Y is consumed rather than queued: a jump must not fire the instant L
        ** is released. */
        return;
    }
    if (look_was_active)
        out->look_exited = true;
    look_was_active = false;

    if (orbit_active) {
        /* C-Up is the camera turn here, never first person or an item. */
        if (c_pressed[0]) out->camera_orbit_turn=orbit_direction;
        c_pressed[0]=c_released[0]=false;
        if (c_mode) held &= (uint16_t)~CAMERA_UP;
    }
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
        if (!analog) {
            /* Z is its own button: holding C for a C direction must not read
            ** as releasing the lock (human report: C+Up dropped the lock-on,
            ** so C-Up on a locked enemy never reached Navi). */
            out->target_held = (held & CAMERA_Z) != 0;
            return;
        }
    }
    /* Report C releases that happened as C itself was let go, so a held item
    ** cannot be left stuck on. */
    for (i = 0; i < 4; ++i)
        if (c_released[i])
            out->c_released = (player_c_button_t)(PLAYER_C_UP + i);

    out->map_toggled = page_left;
    out->move_buttons = analog
        ? ((out->stick_x > 0 ? CAMERA_RIGHT : out->stick_x < 0 ? CAMERA_LEFT : 0) |
           (out->stick_y > 0 ? CAMERA_UP : out->stick_y < 0 ? CAMERA_DOWN : 0))
        : dpad;
    out->jump = jumped;
    out->recenter = recentered;
    /* Set only on the path that reaches here: the diagnostics chord and the
    ** dialogue branch both return early, so L consumed by either never reads
    ** as a targeting hold. */
    out->target_held = (held & CAMERA_Z) != 0;
}

void    player_input_set_dialogue(bool open)
{
    dialogue_open = open;
}

player_move_mode_t player_input_move_mode(void)
{
    return move_mode;
}

/* Use the same movement basis and collision/remainder path as digital input. */
bool player_input_stick_pushed(const player_input_t *input)
{
    if (!input->analog)
        return input->move_buttons != 0;
    /* stick_x/y are 0..127 after the deadzone; 55 of 60 is 116.4 of 127. */
    return stick_radius(input->stick_x, input->stick_y) * 60 >= 55 * 127;
}

bool player_input_motion(const player_input_t *input, uint16_t yaw,
                         uint16_t *heading, int32_t *speed_q8)
{
    int32_t sine, cosine;
    int speed = input->move_mode == PLAYER_MOVE_WALK
              ? LINK_WALK_SPEED_Q8 : LINK_RUN_SPEED_Q8;
    *speed_q8 = speed;
    if (!input->analog)
        return kokiri_camera_input_heading(yaw, input->move_buttons, heading);
    int strength = stick_radius(input->stick_x, input->stick_y);
    *speed_q8 = strength <= 42 ? 0 : speed * strength / 127;
    if (!strength) return false;
    kokiri_camera_sincos(yaw, &sine, &cosine);
    *heading = kokiri_camera_facing(
        (-input->stick_x * cosine + input->stick_y * sine) / 256,
        (input->stick_y * cosine + input->stick_x * sine) / 256);
    return true;
}
