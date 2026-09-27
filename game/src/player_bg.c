/*
** Wall contact, ledge probe and the ground ledge climb. Contract in
** player_bg.h.
**
** Source: ovl_player_actor/z_player.c Player_ProcessSceneCollision (after
** Actor_UpdateBgCheckInfo), Player_PosVsWallLineTest, Player_ActionHandler_12,
** Player_Action_80845668; child sAgeProperties.
*/

#include "player_bg.h"
#include "kokiri_camera.h"

/* Player_ProcessSceneCollision: sInteractWallCheckOffset (0, 18, r + 10). */
#define INTERACT_HEIGHT     18
#define INTERACT_REACH      (PLAYER_WALL_RADIUS + 10)
/* |wallPoly->normal.y| < 600 of 32767; Q14 -> 300.0, so < 300 exactly. */
#define WALL_NY_MAX_Q14     300
/* |ledgeFloorPoly->normal.y| > 0x6D60 (28000 of 32767 = 14000.4 in Q14):
** > 14000 in Q14 selects the same normals our Q14 rounding can express. */
#define LEDGE_FLOOR_NY_Q14  14000

static int32_t  magnitude(int32_t v)
{
    return v < 0 ? -v : v;
}

static uint16_t yaw_diff(uint16_t a, uint16_t b)
{
    return (uint16_t)magnitude((int16_t)(uint16_t)(a - b));
}

/* v * n / 16384, rounded to nearest (n Q14). */
static int32_t  scale_q14(int32_t v, int32_t n)
{
    int32_t p = v * n;
    return (p + (p < 0 ? -8192 : 8192)) / 16384;
}

static uint16_t normal_yaw(const bg_hit_t *hit)
{
    /* Math_Atan2S(normal.z, normal.x): the yaw the normal points along. */
    return kokiri_camera_facing(hit->normal[0], hit->normal[2]);
}

/* Player_PosVsWallLineTest: BgCheck_EntityLineTest1 from pos + (0, y, 0) to
** pos + rotate(shape yaw)(0, y, reach), walls only, one face. */
static bool     wall_line(const bg_vec_t *feet, uint16_t shape_yaw, int32_t height,
                          bg_hit_t *hit)
{
    bg_vec_t a = *feet, b = *feet, at;
    int32_t sine, cosine;

    kokiri_camera_sincos(shape_yaw, &sine, &cosine);
    a.y += height;
    b.y += height;
    b.x += (sine * INTERACT_REACH + (sine < 0 ? -32768 : 32768)) / 65536;
    b.z += (cosine * INTERACT_REACH + (cosine < 0 ? -32768 : 32768)) / 65536;
    return bg_line(&a, &b, &at, BG_CHECK_WALL | BG_CHECK_ONE_FACE,
                   BG_IGNORE_ENTITY, hit);
}

void            player_bg_reset(player_bg_t *bg)
{
    bg->wall = false;
    bg->interact = false;
    bg->wall_hit.bg_id = BG_NONE;
    bg->wall_hit.data0 = bg->wall_hit.data1 = 0;
    bg->wall_yaw = 0;
    bg->touched_flags = 0;
    bg->shape_yaw_to_wall = bg->world_yaw_to_wall = 0;
    bg->dist_to_wall = 0;
    bg->y_dist_to_ledge = 0;
    bg->ledge_type = PLAYER_LEDGE_NONE;
    bg->delay_timer = 0;
}

/* The ledge behind an interact wall: fills y_dist_to_ledge, returns the
** climb type. */
static player_ledge_type_t  probe_ledge(player_bg_t *bg, const bg_vec_t *feet,
                                        uint16_t shape_yaw)
{
    const bg_hit_t *wall = &bg->wall_hit;
    bg_vec_t probe;
    bg_hit_t ledge_floor, line, ceiling;
    int32_t ledge_y, ceiling_y, reach;

    bg->dist_to_wall = bg_poly_plane_distance(wall, feet);
    if (bg->dist_to_wall < 0)
        bg->dist_to_wall = 0;
    reach = bg->dist_to_wall + 10;
    probe.x = feet->x - scale_q14(reach, wall->normal[0]);
    probe.z = feet->z - scale_q14(reach, wall->normal[2]);
    probe.y = feet->y + PLAYER_LEDGE_CHECK_HEIGHT;
    /* BgCheck_EntityRaycastDown1. */
    ledge_y = bg_floor(&probe, BG_IGNORE_ENTITY, &ledge_floor);
    bg->y_dist_to_ledge = ledge_y - feet->y;
    if (ledge_y == BG_Y_MIN)
        bg->y_dist_to_ledge = -32000;

    if (bg->y_dist_to_ledge < PLAYER_LEDGE_MIN ||
        bg_ceiling(&ceiling_y, feet, bg->y_dist_to_ledge + 20,
                   BG_IGNORE_ENTITY, &ceiling)) {
        bg->y_dist_to_ledge = PLAYER_LEDGE_DIST_MAX;
        return PLAYER_LEDGE_NONE;
    }
    /* Something else in the way just above the ledge. */
    if (wall_line(feet, shape_yaw, ledge_y + 5 - feet->y, &line) &&
        yaw_diff(bg->wall_yaw, normal_yaw(&line)) < 0x4000 &&
        !(bg_wall_flags(&line) & BG_WALL_FLAG_1)) {
        bg->y_dist_to_ledge = PLAYER_LEDGE_DIST_MAX;
        return PLAYER_LEDGE_NONE;
    }
    if (bg_wall_flags(wall) & BG_WALL_FLAG_0)
        return PLAYER_LEDGE_NONE;
    if (bg->y_dist_to_ledge < PLAYER_LEDGE_STEP100_MIN)
        return PLAYER_LEDGE_CLIMB_1;
    if (magnitude(ledge_floor.normal[1]) <= LEDGE_FLOOR_NY_Q14)
        return PLAYER_LEDGE_NONE;
    if (bg->y_dist_to_ledge >= PLAYER_LEDGE_JUMP_MIN)
        return PLAYER_LEDGE_CLIMB_4;
    if (bg->y_dist_to_ledge >= PLAYER_LEDGE_STEP150_MIN)
        return PLAYER_LEDGE_CLIMB_3;
    return PLAYER_LEDGE_CLIMB_2;
}

void            player_bg_update(player_bg_t *bg, bool wall, const bg_hit_t *wall_hit,
                                 const bg_vec_t *feet, uint16_t shape_yaw,
                                 uint16_t world_yaw, int32_t speed_q8)
{
    player_ledge_type_t next = PLAYER_LEDGE_NONE;
    bg_hit_t line;

    bg->wall = wall;
    bg->interact = false;
    if (wall) {
        /* Actor_UpdateBgCheckInfo: the sphere's wall and its yaw. */
        bg->wall_hit = *wall_hit;
        bg->wall_yaw = normal_yaw(wall_hit);
        if (wall_line(feet, shape_yaw, INTERACT_HEIGHT, &line)) {
            bg->interact = true;
            if (line.poly != bg->wall_hit.poly || line.bg_id != bg->wall_hit.bg_id) {
                bg->wall_hit = line;
                bg->wall_yaw = normal_yaw(&line);
            }
        }
        bg->touched_flags = bg_wall_flags(&bg->wall_hit);
        bg->shape_yaw_to_wall = yaw_diff(shape_yaw, (uint16_t)(bg->wall_yaw + 0x8000));
        bg->world_yaw_to_wall = yaw_diff(world_yaw, (uint16_t)(bg->wall_yaw + 0x8000));
        if (bg->interact && bg->shape_yaw_to_wall < 0x3000 &&
            magnitude(bg->wall_hit.normal[1]) < WALL_NY_MAX_Q14)
            next = probe_ledge(bg, feet, shape_yaw);
    } else {
        bg->delay_timer = 0;
        bg->y_dist_to_ledge = 0;
    }

    if (next == bg->ledge_type) {
        if (speed_q8 != 0 && bg->delay_timer < PLAYER_LEDGE_TIMER_MAX)
            ++bg->delay_timer;
    } else {
        bg->ledge_type = (uint8_t)next;
        bg->delay_timer = 0;
    }
}

player_ledge_act_t  player_ledge_action(const player_bg_t *bg, bool grounded,
                                        bool a_pressed, int32_t *velocity_q8)
{
    bool go;

    if (bg->ledge_type >= PLAYER_LEDGE_CLIMB_2) {
        if (!grounded)
            return PLAYER_LEDGE_ACT_NONE;
        if (bg->wall_hit.bg_id != BG_SCENE && (bg->touched_flags & BG_WALL_FLAG_6))
            go = bg->delay_timer >= PLAYER_LEDGE_CLIMB_STEPS && a_pressed;
        else
            go = bg->delay_timer >= PLAYER_LEDGE_CLIMB_STEPS || a_pressed;
        if (!go)
            return PLAYER_LEDGE_ACT_NONE;
        if (bg->y_dist_to_ledge >= PLAYER_LEDGE_JUMP_MIN)
            return PLAYER_LEDGE_ACT_JUMP250;
        if (bg->y_dist_to_ledge >= PLAYER_LEDGE_STEP150_MIN)
            return PLAYER_LEDGE_ACT_STEP150;
        return PLAYER_LEDGE_ACT_STEP100;
    }
    if (grounded && bg->ledge_type == PLAYER_LEDGE_CLIMB_1 &&
        bg->delay_timer >= PLAYER_LEDGE_HOP_STEPS) {
        /* yDistToLedge * 0.08 + 5.5 */
        *velocity_q8 = bg->y_dist_to_ledge * 2048 / 100 + 1408;
        return PLAYER_LEDGE_ACT_HOP;
    }
    return PLAYER_LEDGE_ACT_NONE;
}

int32_t         player_ledge_jump250_velocity_q8(int32_t y_dist_to_ledge)
{
    if (y_dist_to_ledge > PLAYER_LEDGE_CHECK_HEIGHT)
        y_dist_to_ledge = PLAYER_LEDGE_CHECK_HEIGHT;
    return y_dist_to_ledge * 256 * 72 / 1000 + 256;
}

player_hang_t   player_hang_walk_off(const bg_vec_t *pos, const bg_vec_t *prev,
                                     int32_t depth_in_water,
                                     uint8_t prev_floor_property,
                                     bg_hit_t *wall, int32_t *dist)
{
    bg_vec_t back, at;
    int32_t dx = prev->x - pos->x, dz = prev->z - pos->z;
    uint32_t length;

    /* floorPitch is always 0 here (the source's own @bug), so only water. */
    if (depth_in_water >= -80)
        return (PLAYER_HANG_NONE);
    /* The line runs from where he is to 5 units behind where he was. */
    length = (uint32_t)(dx * dx + dz * dz);
    back = *prev;
    back.y = pos->y;
    if (length) {
        uint32_t root = 0, bit;
        for (bit = 1u << 15; bit; bit >>= 1)
            if ((root + bit) * (root + bit) <= length) root += bit;
        if (!root) root = 1;
        back.x += dx * 5 / (int32_t)root;
        back.z += dz * 5 / (int32_t)root;
    }
    if (!bg_line(pos, &back, &at, BG_CHECK_WALL | BG_CHECK_ONE_FACE,
                 BG_IGNORE_ENTITY, wall) ||
        magnitude(wall->normal[1]) >= WALL_NY_MAX_Q14)
        return (PLAYER_HANG_NONE);
    *dist = bg_poly_plane_distance(wall, pos);
    if (*dist < 0)
        *dist = 0;
    if (prev_floor_property == 6 || (bg_wall_flags(wall) & BG_WALL_FLAG_3))
        return (PLAYER_HANG_CLIMB);
    return (PLAYER_HANG_LEDGE);
}

bool            player_hang_grab(const player_bg_t *bg, int32_t speed_q8,
                                 int32_t feet_y, int32_t floor_y)
{
    return bg->interact && speed_q8 > 0 &&
           bg->ledge_type >= PLAYER_LEDGE_CLIMB_2 &&
           bg->y_dist_to_ledge < PLAYER_HANG_CLIMB_WALL &&
           feet_y - floor_y + bg->y_dist_to_ledge >= PLAYER_HANG_GRAB_MIN;
}

void            player_hang_place(const bg_hit_t *wall, int32_t dist, bg_vec_t *feet,
                                  uint16_t *facing, bool face_wall)
{
    int32_t reach = dist + 1;
    int32_t nx = wall->normal[0], nz = wall->normal[2];

    feet->x -= scale_q14(reach, nx);
    feet->z -= scale_q14(reach, nz);
    *facing = normal_yaw(wall);
    if (face_wall)
        *facing = (uint16_t)(*facing + 0x8000);
}

void            player_ledge_step_target(const player_bg_t *bg, bg_vec_t *feet,
                                         uint16_t *facing)
{
    /* distToInteractWall + 0.5 in the source. The integer distance is
    ** rounded down, so + 1 is what keeps him past the edge, on the ledge. */
    int32_t reach = bg->dist_to_wall + 1;
    int32_t nx = bg->wall_hit.normal[0], nz = bg->wall_hit.normal[2];

    feet->x -= (reach * nx + (nx < 0 ? -16383 : 16383)) / 16384;
    feet->z -= (reach * nz + (nz < 0 ? -16383 : 16383)) / 16384;
    feet->y += bg->y_dist_to_ledge;
    *facing = (uint16_t)(bg->wall_yaw + 0x8000);
}
