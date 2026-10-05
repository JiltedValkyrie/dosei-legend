#pragma GCC optimize("Os") /* per-step logic, small: size over speed (work RAM) */
#include "player_water.h"
#include "kokiri_camera.h"
#include "link_anim_state.h"
#include "link_clips.h"

static int32_t approach(int32_t value, int32_t target, int32_t step)
{
    if (value < target) { value += step; if (value > target) value = target; }
    else if (value > target) { value -= step; if (value < target) value = target; }
    return value;
}

void player_water_reset(player_water_t *water)
{
    *water = (player_water_t){0};
}

bool player_water_hazard(const player_water_t *water)
{
    return water->submerged_steps >= 450;
}

static void play(player_water_t *water, unsigned phase, unsigned clip)
{
    water->phase = phase;
    link_anim_swim_play(clip);
}

/* func_8084B000, child ageProperties->unk_28=29.6. Q8 velocities retain
 * source magnitudes; acceleration is converted from 20 to 30 Hz (x2/3). */
static void buoyancy(player_water_t *water, int32_t depth)
{
    int32_t velocity = water->velocity_q8, acceleration, limit;
    int32_t target = 7578 + (velocity < 0 ? 256 : 0);
    if (depth * 256 < target) {
        acceleration = -17 - (velocity > 0 ? velocity / 3 : 0);
        limit = -1280;
    } else {
        acceleration = 17 + (velocity < 0 ? -velocity / 5 : 0);
        limit = 512;
    }
    velocity += acceleration;
    if ((acceleration > 0 && velocity > limit) ||
        (acceleration < 0 && velocity < limit)) velocity = limit;
    water->velocity_q8 = velocity;
}

/* Swim strokes accelerate only between source clip frames 10 and 20.
 * func_8084AEEC: target x0.8, deceleration |speed|*.02+.05, turn 1600.
 * Fractional translation is retained, rather than rounding every slow step. */
static void stroke(player_water_t *water, int32_t target, uint16_t yaw)
{
    unsigned frame = link_anim_move_phase() / 30;
    int32_t turn = (int16_t)(uint16_t)(yaw - water->yaw);
    int32_t step = water->speed_q8 / 75 + 9;
    if (frame > 10 && frame < 20) step = (int32_t)(frame - 10) * 1024;
    else target = 0;
    target = target * 4 / 5;
    if (target > 1126) target = 1126; /* 5.5 * .8 */
    water->speed_q8 = approach(water->speed_q8, target, step);
    if (turn > 1600) turn = 1600;
    if (turn < -1600) turn = -1600;
    water->yaw = (uint16_t)(water->yaw + turn);
}

static void move(player_water_t *water, bg_vec_t *feet)
{
    bg_vec_t prev = *feet, next = *feet, ray;
    bg_hit_t hit;
    int32_t sine, cosine, floor, ceiling, rise;
    int32_t delta[3], *axes[3] = { &next.x, &next.y, &next.z };
    unsigned k;
    kokiri_camera_sincos(water->yaw, &sine, &cosine);
    delta[0] = (int32_t)((int64_t)sine * water->speed_q8 / 65536);
    delta[1] = water->velocity_q8;
    delta[2] = (int32_t)((int64_t)cosine * water->speed_q8 / 65536);
    for (k = 0; k < 3; ++k) {
        water->remainder[k] += delta[k];
        *axes[k] += water->remainder[k] / 256;
        water->remainder[k] %= 256;
    }
    bg_wall(feet, &next, &prev, 14, 26, BG_IGNORE_ENTITY, false, &hit);
    next.x = feet->x; next.z = feet->z;
    /* Query from the old feet so an upward step cannot skip a thin roof. */
    ray = next; ray.y = prev.y;
    rise = next.y > prev.y ? next.y - prev.y : 0;
    if (bg_ceiling(&ceiling, &ray, 40 + rise, BG_IGNORE_ENTITY, &hit)) {
        ceiling += rise;
        if (ceiling < prev.y && (next.x != prev.x || next.z != prev.z)) {
            /* A horizontal move under a low roof cannot crush the swimmer
             * between floor and ceiling. Reject its XZ, as on land. */
            next.x = prev.x; next.z = prev.z;
        } else if (next.y > ceiling) {
            next.y = ceiling < prev.y ? prev.y : ceiling;
            water->velocity_q8 = 0; water->remainder[1] = 0;
        }
    }
    /* Same small-step floor reach as grounded movement, but no teleport up
     * a bank: a rise above 24 remains a wall/ledge action. */
    ray = next; ray.y = (prev.y > next.y ? prev.y : next.y) + 25;
    floor = bg_floor(&ray, BG_IGNORE_ENTITY, &hit);
    if (floor != BG_Y_MIN && floor > next.y) {
        ray = next;
        /* Check the headroom at the proposed bank height as well: the roof
         * may clear the old swim height but not the floor we would step onto. */
        if (bg_ceiling(&ceiling, &ray, 40 + floor - next.y,
                       BG_IGNORE_ENTITY, &hit)) {
            next.x = prev.x; next.z = prev.z;
            ray = next; ray.y = (prev.y > next.y ? prev.y : next.y) + 25;
            floor = bg_floor(&ray, BG_IGNORE_ENTITY, &hit);
        }
    }
    water->grounded = floor != BG_Y_MIN &&
        (next.y < floor || (next.y == floor && water->velocity_q8 <= 0));
    if (water->grounded) {
        next.y = floor;
        water->velocity_q8 = 0; water->remainder[1] = 0;
    }
    *feet = next;
}

bool player_water_step(player_water_t *water, const player_water_input_t *input,
                       bg_vec_t *feet, uint16_t *facing, int32_t incoming_velocity,
                       bool was_grounded)
{
    int32_t surface, depth, unused[3], target;
    unsigned clip, limit;
    bool done;
    if (!bg_water_surface(feet->x, feet->z, input->room, &surface, 0) ||
        surface - feet->y < 22) {
        if (water->phase) link_anim_move_end();
        player_water_reset(water);
        return false;
    }
    depth = surface - feet->y;
    if (!water->phase) {
        if (depth <= 32) return false;
        water->velocity_q8 = incoming_velocity;
        if (water->velocity_q8 < -1280) water->velocity_q8 = -1280;
        water->yaw = *facing;
        play(water, PLAYER_WATER_ENTER,
             was_grounded ? LINK_CLIP_SWIM_ENTER : LINK_CLIP_SWIM_FALL);
    }
    if (depth >= 32) {
        if (water->submerged_steps < 450) ++water->submerged_steps;
    } else water->submerged_steps = 0;
    target = input->blocked ? 0 : input->speed_q8;
    limit = input->scale > 2 ? 360 : 120 * (input->scale + 1);
    done = link_anim_move_step(30, unused);
    switch (water->phase) {
    case PLAYER_WATER_ENTER:
    case PLAYER_WATER_SURFACE_END:
        buoyancy(water, depth);
        water->speed_q8 = approach(water->speed_q8, 0, 171);
        if (done) play(water, PLAYER_WATER_SURFACE, LINK_CLIP_SWIM_WAIT);
        break;
    case PLAYER_WATER_SURFACE:
        buoyancy(water, depth);
        if (input->dive_pressed && !input->blocked) {
            water->velocity_q8 = 0;
            play(water, PLAYER_WATER_DIVE_START, LINK_CLIP_DIVE_START);
            break;
        }
        clip = target ? LINK_CLIP_SWIM : LINK_CLIP_SWIM_WAIT;
        if (done || link_anim_move_clip() != clip)
            link_anim_swim_play(clip);
        stroke(water, target, input->yaw);
        break;
    case PLAYER_WATER_DIVE_START:
        water->speed_q8 = approach(water->speed_q8, 0, 171);
        if (link_anim_move_crossed(20)) water->velocity_q8 = -512;
        if (done || (link_anim_move_phase() >= 22 * 30 && !input->dive_held))
            play(water, PLAYER_WATER_DIVE, LINK_CLIP_SWIM);
        break;
    case PLAYER_WATER_DIVE:
        if (done) link_anim_swim_play(LINK_CLIP_SWIM);
        if (!input->dive_held || input->blocked || water->grounded || depth >= (int32_t)limit) {
            water->rise_depth = depth;
            water->timer = 8; /* Pitch recovery, pending full upper-body tilt. */
            play(water, PLAYER_WATER_TURN, LINK_CLIP_SWIM_WAIT);
        } else {
            stroke(water, target / 2, input->yaw);
            water->velocity_q8 = approach(water->velocity_q8, -512, 171);
        }
        break;
    case PLAYER_WATER_TURN:
        buoyancy(water, depth);
        water->speed_q8 = approach(water->speed_q8, 0, 171);
        if (!--water->timer) play(water, PLAYER_WATER_RISE, LINK_CLIP_SWIM);
        break;
    case PLAYER_WATER_RISE:
        if (done) link_anim_swim_play(LINK_CLIP_SWIM);
        if (depth < 48 && water->velocity_q8 > 0)
            play(water, PLAYER_WATER_SURFACE_END, LINK_CLIP_DIVE_END);
        else {
            int32_t rise = 1024 + water->rise_depth * 576 / 125; /* (4+.018*d)*256 */
            if (rise > 2048) rise = 2048;
            water->velocity_q8 = approach(water->velocity_q8, rise, 171);
            stroke(water, target / 2, input->yaw);
        }
        break;
    default: break;
    }
    /* No stroke repeat from held buttons. X is the Saturn attack/B mapping;
     * A starts a dive on the surface and sustains it underwater. */
    if (input->stroke_pressed && !input->blocked && water->phase == PLAYER_WATER_SURFACE)
        water->speed_q8 = approach(water->speed_q8, 1126, 256);
    move(water, feet);
    *facing = water->yaw;
    if (!bg_water_surface(feet->x, feet->z, input->room, &surface, 0) ||
        surface - feet->y < 22) {
        link_anim_move_end();
        player_water_reset(water);
    }
    return true;
}
