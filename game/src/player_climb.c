/*
** Ladder and vine climbing. Contract in player_climb.h.
**
** Source: ovl_player_actor/z_player.c func_8083EC18, Player_Action_8084BF1C,
** Player_Action_8084C5F8, func_8083F360, func_8083FBC0, func_8083FB7C,
** func_8083973C; child sAgeProperties (unk_3C 12, unk_40 55, unk_A4..CC).
*/

#include "player_climb.h"
#include "gameplay.h"
#include "kokiri_camera.h"
#include "link_anim_state.h"
#include "link_clips.h"

/* func_8083F360(play, this, 26, unk_3C, 50, -20): the climbing wall line. */
#define CLIMB_LINE_HEIGHT   26
#define CLIMB_WALL_GAP      12      /* unk_3C */
#define CLIMB_LINE_AHEAD    50
#define CLIMB_LINE_BEHIND   20
/* Math_ScaledStepToS(&shape.rot.y, ..., 800): 800 x 1.5 a 20 Hz update. */
#define CLIMB_TURN_STEP     800
/* D_8085488C (0, unk_40, 26): where the top-of-climb floor is looked for. */
#define CLIMB_TOP_UP        55
#define CLIMB_TOP_AHEAD     26
/* Ladder rungs, func_8083EC18's y snap. */
#define CLIMB_RUNG          15
/* playSpeed = |stick| x 0.05 (0.0325 sideways), 1.0 .. 3.35; in 30ths. */
#define CLIMB_SPEED_MIN     30
#define CLIMB_SPEED_MAX     100
/* func_8083F070: LinkAnimation_PlayOnceSetSpeed(..., 4/3). */
#define CLIMB_END_SPEED     40
/* The climbable wall flags (func_8083FBC0). */
#define CLIMBABLE           (BG_WALL_FLAG_3 | BG_WALL_FLAG_1 | BG_WALL_FLAG_2)

static int32_t  magnitude(int32_t v)
{
    return v < 0 ? -v : v;
}

/* sAgeProperties (child) unk_AC / unk_BC / unk_C4 / unk_CC. */
static const unsigned int climb_up_clips[4] = {
    LINK_CLIP_LADDER_UPL, LINK_CLIP_LADDER_UPR, LINK_CLIP_VINE_UPL, LINK_CLIP_VINE_UPR };
static const unsigned int climb_side_clips[2] = {
    LINK_CLIP_VINE_SIDEL, LINK_CLIP_VINE_SIDER };
static const unsigned int climb_bottom_clips[2] = {
    LINK_CLIP_LADDER_ENDAL, LINK_CLIP_LADDER_ENDAR };
static const unsigned int climb_top_clips[2] = {
    LINK_CLIP_LADDER_ENDBR, LINK_CLIP_LADDER_ENDBL };

/* Root motion (raw model units, model-local) -> world, at actor scale 0.01,
** turned by the facing as SkelAnime_UpdateTranslation does. Carried in Q8
** so sub-unit steps add up. */
static int32_t  carry_x_q8, carry_y_q8, carry_z_q8;

static void     apply_motion(bg_vec_t *feet, uint16_t facing, const int32_t d[3])
{
    int32_t sine, cosine, wx, wz;

    kokiri_camera_sincos(facing, &sine, &cosine);
    wx = d[0] * (cosine / 256) + d[2] * (sine / 256);   /* model x 256 */
    wz = d[2] * (cosine / 256) - d[0] * (sine / 256);
    carry_x_q8 += wx / 100;
    carry_z_q8 += wz / 100;
    carry_y_q8 += d[1] * 256 / 100;
    feet->x += carry_x_q8 / 256; carry_x_q8 %= 256;
    feet->y += carry_y_q8 / 256; carry_y_q8 %= 256;
    feet->z += carry_z_q8 / 256; carry_z_q8 %= 256;
}

static void     play(player_climb_t *climb, unsigned int clip, bool reverse)
{
    (void)climb;
    link_anim_move_play(clip, reverse, false);
}

bool            player_climb_start(player_climb_t *climb, const player_bg_t *bg,
                                   bg_vec_t *feet, uint16_t *facing, bool grounded)
{
    const bg_hit_t *wall = &bg->wall_hit;
    uint32_t flags = bg->touched_flags;
    int32_t nx = wall->normal[0], nz = wall->normal[2];
    int32_t sx, sz, reach, snap = 0;
    int8_t vine = (flags & BG_WALL_FLAG_3) ? 2 : 0;
    unsigned int clip;

    if (bg->y_dist_to_ledge < PLAYER_CLIMB_MIN_WALL)
        return false;
    if (!vine && !(flags & BG_WALL_FLAG_1) && !(bg_wall_flags(wall) & BG_WALL_FLAG_2))
        return false;
    if (vine) {
        sx = feet->x * 2;
        sz = feet->z * 2;
    } else {
        /* The poly's x/z box centre (the source's min/max scan, which can
        ** miss a middle vertex; kept), and its lowest vertex. */
        int16_t v[3][3];
        int32_t x0, x1, z0, z1, y0, lateral, height, i;
        if (!bg_poly_vertices(wall, v))
            return false;
        x0 = x1 = v[0][0]; z0 = z1 = v[0][2]; y0 = v[0][1];
        for (i = 1; i < 3; i++) {
            if (x0 > v[i][0]) x0 = v[i][0]; else if (x1 < v[i][0]) x1 = v[i][0];
            if (z0 > v[i][2]) z0 = v[i][2]; else if (z1 < v[i][2]) z1 = v[i][2];
            if (y0 > v[i][1]) y0 = v[i][1];
        }
        sx = x0 + x1;
        sz = z0 + z1;
        /* |(pos - centre) x normal| < 8: in front of the ladder's middle. */
        lateral = (feet->x * 2 - sx) * nz - (feet->z * 2 - sz) * nx;
        if (magnitude(lateral) >= 16 * 16384)
            return false;
        /* Rungs every 15 above the poly's foot: (s32)(h / 15 + 0.5) * 15 - h. */
        height = feet->y - y0;
        snap = (2 * height + CLIMB_RUNG) / (2 * CLIMB_RUNG) * CLIMB_RUNG - height;
    }

    climb->interact = true;
    climb->wall = *wall;
    climb->events = 0;
    climb->phase = PLAYER_CLIMB_ON;
    if (vine || (flags & BG_WALL_FLAG_1)) {
        climb->var1 = vine;
        if (vine) {
            clip = grounded ? LINK_CLIP_VINE_START : LINK_CLIP_VINE_HOLD;
            reach = PLAYER_WALL_RADIUS - 1 - bg->dist_to_wall;
        } else {
            clip = LINK_CLIP_LADDER_START;
            reach = bg->dist_to_wall - 1;
        }
        climb->var2 = -2;
        feet->y += snap;
        *facing = (uint16_t)(bg->wall_yaw + 0x8000);
    } else {
        /* A ladder top (WALL_FLAG_2): turn round and climb down onto it. */
        climb->var1 = 0;
        clip = LINK_CLIP_LADDER_DOWN;
        reach = bg->dist_to_wall;
        climb->var2 = -4;
        *facing = bg->wall_yaw;
    }
    feet->x = (sx * 16384 + 2 * reach * nx) / (2 * 16384);
    feet->z = (sz * 16384 + 2 * reach * nz) / (2 * 16384);
    carry_x_q8 = carry_y_q8 = carry_z_q8 = 0;
    /* ANIM_FLAG_ADJUST_STARTING_POS: the first step does not move. */
    link_anim_move_play(clip, false, true);
    return true;
}

void            player_climb_start_walk_off(player_climb_t *climb, const bg_hit_t *wall,
                                            uint16_t *facing)
{
    climb->interact = true;
    climb->wall = *wall;
    climb->events = 0;
    climb->phase = PLAYER_CLIMB_ON;
    climb->var1 = 1;
    climb->var2 = -1;
    *facing = (uint16_t)(*facing + 0x8000);
    carry_x_q8 = carry_y_q8 = carry_z_q8 = 0;
    link_anim_move_play(LINK_CLIP_VINE_DOWN, false, true);
}

/* func_8083F360(26, 12, 50, -20): stay on the wall -- face it and hold 12
** from the line hit. False = the wall is gone (WALL_INTERACT cleared). */
static bool     hold_wall(player_climb_t *climb, bg_vec_t *feet, uint16_t *facing)
{
    bg_vec_t a = *feet, b = *feet, at;
    int32_t sine, cosine;
    bg_hit_t hit;
    uint16_t target;
    int16_t turn;

    kokiri_camera_sincos(*facing, &sine, &cosine);
    a.x -= CLIMB_LINE_BEHIND * sine / 65536;
    a.z -= CLIMB_LINE_BEHIND * cosine / 65536;
    b.x += CLIMB_LINE_AHEAD * sine / 65536;
    b.z += CLIMB_LINE_AHEAD * cosine / 65536;
    a.y += CLIMB_LINE_HEIGHT;
    b.y += CLIMB_LINE_HEIGHT;
    if (!bg_line(&a, &b, &at, BG_CHECK_WALL | BG_CHECK_ONE_FACE, BG_IGNORE_ENTITY, &hit))
        return false;
    climb->wall = hit;
    target = kokiri_camera_facing(-hit.normal[0], -hit.normal[2]);
    turn = (int16_t)(uint16_t)(target - *facing);
    if (turn > CLIMB_TURN_STEP) *facing = (uint16_t)(*facing + CLIMB_TURN_STEP);
    else if (turn < -CLIMB_TURN_STEP) *facing = (uint16_t)(*facing - CLIMB_TURN_STEP);
    else *facing = target;
    kokiri_camera_sincos(*facing, &sine, &cosine);
    feet->x = at.x - CLIMB_WALL_GAP * sine / 65536;
    feet->z = at.z - CLIMB_WALL_GAP * cosine / 65536;
    return true;
}

/* func_8083973C(D_8085488C): floor under (0, 55, 26) ahead of him. */
static int32_t  top_floor(const bg_vec_t *feet, uint16_t facing)
{
    bg_vec_t p = *feet;
    int32_t sine, cosine;
    bg_hit_t hit;

    kokiri_camera_sincos(facing, &sine, &cosine);
    p.x += CLIMB_TOP_AHEAD * sine / 65536;
    p.z += CLIMB_TOP_AHEAD * cosine / 65536;
    p.y += CLIMB_TOP_UP;
    return bg_floor(&p, BG_IGNORE_ENTITY, &hit);
}

static int32_t  floor_under(const bg_vec_t *feet)
{
    int32_t floor;
    return kokiri_collision_floor(feet->x, feet->z, feet->y, &floor) ? floor : BG_Y_MIN;
}

/* Player_ProcessSceneCollision's floor ray (from +50) still runs while he
** climbs: stepping over a ledge's top stands him on it. */
static void     floor_snap(bg_vec_t *feet)
{
    int32_t floor;
    if (kokiri_collision_floor(feet->x, feet->z, feet->y + 49, &floor) && floor >= feet->y)
        feet->y = floor;
}

/* Player_Action_8084C5F8: a ladder step-off at 4/3, interruptible in its last
** 4 frames by input (Player_TryActionInterrupt). */
static void     ending_step(player_climb_t *climb, const player_climb_input_t *in,
                            bg_vec_t *feet, uint16_t facing)
{
    unsigned int clip = link_anim_move_clip();
    unsigned int end = link_clips[clip].count - 1;
    int32_t delta[3];

    if (link_anim_move_step(CLIMB_END_SPEED, delta) ||
        (in->stick_pushed && link_anim_move_phase() >= (end - 4) * 30)) {
        link_anim_move_end();
        climb->phase = PLAYER_CLIMB_DONE;
        return;
    }
    apply_motion(feet, facing, delta);
    floor_snap(feet);
    /* D_80854898 / D_808548A0 landing sounds (and the wood steps). */
    if (link_anim_move_crossed(climb->var2 ? 40 : 10) ||
        link_anim_move_crossed(climb->var2 ? 50 : 20))
        climb->events |= GP_EVENT_FOOTSTEP;
}

void            player_climb_update(player_climb_t *climb, const player_climb_input_t *in,
                                    bg_vec_t *feet, uint16_t *facing)
{
    int32_t up = in->stick_y, side = in->stick_x, speed, delta[3];
    int sp68;

    climb->events = 0;
    if (climb->phase == PLAYER_CLIMB_ENDING) {
        ending_step(climb, in, feet, *facing);
        return;
    }
    if (climb->phase != PLAYER_CLIMB_ON)
        return;

    /* playSpeed from the stick: sideways on a vine when it is pushed more
    ** sideways than up or down. */
    if (climb->var1 != 0 && magnitude(up) < magnitude(side)) {
        speed = magnitude(side) * 39 / 40;      /* x 0.0325, in 30ths */
        up = 0;
    } else {
        speed = magnitude(up) * 3 / 2;          /* x 0.05, in 30ths */
        side = 0;
    }
    if (speed < CLIMB_SPEED_MIN) speed = CLIMB_SPEED_MIN;
    if (speed > CLIMB_SPEED_MAX) speed = CLIMB_SPEED_MAX;

    if (climb->var2 >= 0) {
        climb->interact = hold_wall(climb, feet, facing);
        /* func_8083FBC0: A, no wall, or a wall that is not climbable. */
        if (in->a_pressed || !climb->interact ||
            !(bg_wall_flags(&climb->wall) & CLIMBABLE)) {
            climb->phase = PLAYER_CLIMB_LET_GO;
            climb->events |= GP_EVENT_JUMP;     /* NA_SE_VO_LI_AUTO_JUMP */
            return;
        }
    }

    if (link_anim_move_step((unsigned int)speed, delta)) {
        if (climb->var2 < 0) {
            climb->var2 = (int8_t)(magnitude(climb->var2) & 1);
            return;
        }
        if (up != 0) {
            sp68 = climb->var1 + climb->var2;
            if (up > 0) {
                int32_t top = top_floor(feet, *facing);
                if (feet->y < top) {
                    if (climb->var1 != 0) {
                        feet->y = top;
                        climb->phase = PLAYER_CLIMB_VINE_TOP;
                        return;
                    }
                    /* func_8083F070(unk_CC[var2]): prevTransl carries on. */
                    play(climb, climb_top_clips[climb->var2], false);
                    link_anim_move_keep_prev();
                    climb->phase = PLAYER_CLIMB_ENDING;
                } else
                    play(climb, climb_up_clips[sp68], false);
            } else {
                if (feet->y - floor_under(feet) < CLIMB_RUNG) {
                    if (climb->var1 != 0) {
                        climb->phase = PLAYER_CLIMB_LET_GO;
                        return;
                    }
                    /* func_8083F070(unk_C4[var2]); prevTransl = unk_44 only
                    ** for the right hand: the left keeps the last clip's. */
                    link_anim_move_play(climb_bottom_clips[climb->var2], false,
                                        false);
                    if (climb->var2 == 0)
                        link_anim_move_keep_prev();
                    climb->phase = PLAYER_CLIMB_ENDING;
                    climb->var2 = 1;
                } else {
                    sp68 ^= 1;
                    play(climb, climb_up_clips[sp68], true);
                }
            }
            climb->var2 ^= 1;
        } else if (climb->var1 != 0 && side != 0) {
            play(climb, climb_side_clips[climb->var2], side < 0);
        }
        return;
    }
    apply_motion(feet, *facing, delta);
    floor_snap(feet);

    /* func_8084BEE4: the hand/foot sounds. */
    if (climb->var2 < 0) {
        if ((climb->var2 == -2 && (link_anim_move_crossed(14) || link_anim_move_crossed(29))) ||
            (climb->var2 == -4 && (link_anim_move_crossed(22) || link_anim_move_crossed(35) ||
                                   link_anim_move_crossed(49) || link_anim_move_crossed(55))))
            climb->events |= GP_EVENT_FOOTSTEP;
    } else if (link_anim_move_crossed(link_anim_move_reversed() ? 0 : 20))
        climb->events |= GP_EVENT_FOOTSTEP;
}
