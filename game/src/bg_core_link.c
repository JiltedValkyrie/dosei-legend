/*
 * CORE_COLLISION: the C Link movement wrappers of kokiri_collision.h over the
 * core's z_bgcheck (bg_core_shim.c). Same constants, order and contract as
 * shared/lib/collision/kokiri_collision.c, which stays the CORE_COLLISION=0
 * rollback. The C triangle grid is gone: floors are the core's floor-class
 * raycast, spheres its SphVsFirstPoly. Retired with C Link (phase 7).
 */
#include "bg_core_shim.h"
/* The div32 helpers' one definition (kokiri_collision.c owns it when the C
 * library links): many game files call them. */
#define DIV32_IMPLEMENTATION
#include "div32.h"
#undef DIV32_IMPLEMENTATION

#define RADIUS 24
#define EYE_HEIGHT 90
/* Head sphere centre above the feet: radius 8 tops out at the child's 44. */
#define LINK_HEAD_SPHERE_Y 36
#define STEP 4
/* Child Player_ProcessSceneCollision wall sphere / ceiling height. */
#define ACTOR_RADIUS 14
#define ACTOR_CHECK_HEIGHT 26
#define ACTOR_CEILING_HEIGHT 40
/* A grounded step's dy before the ceiling check (see actor_step_xz). */
#define ACTOR_GROUND_DIP 7
/* OoT keeps BGCHECKFLAG_GROUND while the floor is <= 11 below the actor. */
#define ACTOR_GROUND_FOLLOW_DROP 11
/* Gravity -1.0 / terminal -20 per 20 Hz update, at 30 Hz steps
 * (game/docs/TRAVERSAL_TIMING.md). */
#define GRAVITY_Q8 (-171)
#define TERMINAL_VELOCITY_Q8 (-20 * 256)
/* Custom Y jump (the human's control): apex 51 units, airtime 25 steps. */
#define JUMP_VELOCITY_Q8 2208

void kokiri_collision_init(const collision_triangle_t *data, uint32_t count)
{
        (void)data;     /* the core owns the scene */
        (void)count;
}

static bool clear_radius(camera_position_t position, int32_t radius,
        bool skip_ceilings, uint32_t ignore)
{
        return !bg_core_sphere(&position, radius, ignore, skip_ceilings);
}

bool kokiri_collision_clear(camera_position_t position)
{
        return clear_radius(position, RADIUS, false, BG_IGNORE_CAMERA);
}

/* Highest floor-class poly at or below `below` under (x, z). The core's
 * raycast takes floors strictly below its start, so it starts one above. */
bool kokiri_collision_floor(int32_t x, int32_t z, int32_t below, int32_t *height)
{
        bg_vec_t at = { x, below + 1, z };
        int32_t y = bg_core_floor_class(&at, BG_IGNORE_ENTITY);
        if (y == BG_Y_MIN) return false;
        *height = y;
        return true;
}

bool kokiri_collision_spawn(camera_position_t *position)
{
        /* Prefer the village clearing, then search nearby points on actual floors. */
        for (int ring = 0; ring <= 6; ring++) {
                for (int x = -ring; x <= ring; x++) for (int z = -ring; z <= ring; z++) {
                        if (ring && x != -ring && x != ring && z != -ring && z != ring) continue;
                        camera_position_t p = {-300+x*80,0,z*80};
                        int32_t floor;
                        if (!kokiri_collision_floor(p.x,p.z,200,&floor)) continue;
                        p.y = floor+EYE_HEIGHT;
                        if (kokiri_collision_clear(p)) { *position = p; return true; }
                }
        }
        return false;
}

static void move_axis(camera_position_t *position, int axis, int32_t amount)
{
        while (amount) {
                int32_t step = amount > STEP ? STEP : amount < -STEP ? -STEP : amount;
                camera_position_t next = *position;
                if (axis == 0) next.x += step;
                if (axis == 1) next.y += step;
                if (axis == 2) next.z += step;
                if (next.x < -12000 || next.x > 12000 || next.y < -4000 || next.y > 12000 ||
                    next.z < -12000 || next.z > 12000) break;
                int32_t floor;
                if (kokiri_collision_floor(next.x,next.z,position->y-RADIUS,&floor) &&
                    next.y < floor+EYE_HEIGHT)
                        next.y = floor+EYE_HEIGHT;
                /* No snapping through ceilings or climbing tall steps. */
                if (next.y-position->y > STEP || !kokiri_collision_clear(next)) break;
                *position = next;
                amount -= step;
        }
}

void kokiri_collision_move(camera_position_t *position, int32_t dx, int32_t dy, int32_t dz)
{
        if (!(dx || dy || dz)) return;
        /* Small swept steps avoid tunnelling; separate axes slide along walls. */
        move_axis(position,0,dx);
        move_axis(position,2,dz);
        move_axis(position,1,dy);
}

/* Last horizontal actor step's wall contact (BGCHECKFLAG_WALL). */
static bool actor_wall_valid, actor_stepped;
static bg_hit_t actor_wall_hit;
/* Player_ProcessSceneCollision's wall radius / height and ceiling height:
 * child 14 / 26 / 40, crawling 10 / 15 / 30. */
static int32_t actor_radius = ACTOR_RADIUS, actor_check_height = ACTOR_CHECK_HEIGHT,
        actor_ceiling = ACTOR_CEILING_HEIGHT;

void kokiri_collision_actor_probe_still(const camera_position_t *position)
{
        /* Actor_UpdateBgCheckInfo still runs the sphere with prev == pos. */
        bg_vec_t at = { position->x, position->y - EYE_HEIGHT, position->z }, res;
        bg_hit_t wall;
        if (actor_stepped) return;
        if (bg_wall(&res, &at, &at, actor_radius, actor_check_height,
                    BG_IGNORE_ENTITY, false, &wall)) {
                actor_wall_valid = true;
                actor_wall_hit = wall;
        }
        actor_stepped = true;
}

void kokiri_collision_actor_set_crawl(bool crawling)
{
        actor_radius = crawling ? 10 : ACTOR_RADIUS;
        actor_check_height = crawling ? 15 : ACTOR_CHECK_HEIGHT;
        actor_ceiling = crawling ? 30 : ACTOR_CEILING_HEIGHT;
}

void kokiri_collision_actor_begin_step(void)
{
        actor_stepped = false;
        actor_wall_valid = false;
}

bool kokiri_collision_actor_wall(bool *stepped, bg_hit_t *hit)
{
        if (stepped) *stepped = actor_stepped;
        if (actor_wall_valid && hit) *hit = actor_wall_hit;
        return actor_wall_valid;
}

/* One horizontal step of Actor_UpdateBgCheckInfo with the player's flags:
 * wall sphere, ceiling, floor (kokiri_collision.c actor_step_xz). */
static void actor_step_xz(camera_position_t *position, int32_t dx, int32_t dz)
{
        bg_vec_t prev = { position->x, position->y - EYE_HEIGHT, position->z };
        bg_vec_t next = prev, res, at;
        bg_hit_t wall, ceiling, floor_hit;
        int32_t floor, ceiling_y, y, glue;
        bool standing, roof;

        next.x += dx; next.z += dz;
        if (next.x < -12000 || next.x > 12000 || next.z < -12000 || next.z > 12000)
                return;
        actor_stepped = true;
        standing = kokiri_collision_floor(prev.x, prev.z, prev.y + STEP, &floor) &&
                   floor == prev.y;

        if (bg_wall(&res, &next, &prev, actor_radius, actor_check_height,
                    BG_IGNORE_ENTITY, false, &wall)) {
                next.x = res.x; next.z = res.z;
                actor_wall_valid = true;
                actor_wall_hit = wall;
        }

        glue = standing ? ACTOR_GROUND_DIP : 0;
        y = prev.y;
        at = next;
        at.y = prev.y + 10;
        roof = bg_ceiling(&ceiling_y, &at, actor_ceiling - 10 - glue,
                          BG_IGNORE_ENTITY, &ceiling);
        if (roof)
                y = ceiling_y - glue - 10;      /* (outY + dy) - 10 */

        if (kokiri_collision_floor(next.x, next.z, y + 49, &floor) && floor >= y) {
                if (roof) {
                        at.x = next.x; at.y = y + 50; at.z = next.z;
                        bg_floor(&at, BG_IGNORE_ENTITY, &floor_hit);
                        if (floor_hit.bg_id == ceiling.bg_id) {
                                next.x = prev.x; next.z = prev.z;
                        }
                }
                y = floor;
        } else if (standing && kokiri_collision_floor(next.x, next.z, y, &floor) &&
                   y - floor <= ACTOR_GROUND_FOLLOW_DROP) {
                y = floor;
        }
        position->x = next.x;
        position->y = y + EYE_HEIGHT;
        position->z = next.z;
}

/* The vertical part: ceiling (UPDBGCHECKINFO_FLAG_1), floor, and this port's
 * head sphere for the custom Y jump (kokiri_collision.c actor_step_y). */
static void actor_step_y(camera_position_t *position, int32_t dy)
{
        int32_t feet = position->y - EYE_HEIGHT, next = feet + dy, floor, ceiling_y;
        bg_vec_t at = { position->x, feet + 10, position->z };
        bg_hit_t hit;

        if (next < -4000 || next > 12000) return;
        if (ACTOR_CEILING_HEIGHT + dy - 10 > 0 &&
            bg_ceiling(&ceiling_y, &at, ACTOR_CEILING_HEIGHT + dy - 10,
                       BG_IGNORE_ENTITY, &hit)) {
                next = ceiling_y + dy - 10;
                if (dy > 0 && next < feet) next = feet;
        }
        if (dy > 0) {
                camera_position_t head = *position;
                int32_t y = feet, to;
                while (y < next) {
                        to = next - y > STEP ? y + STEP : next;
                        head.y = to + LINK_HEAD_SPHERE_Y;
                        if (!clear_radius(head, 8, true, BG_IGNORE_ENTITY)) { next = y; break; }
                        y = to;
                }
        } else if (kokiri_collision_floor(position->x, position->z, feet + STEP, &floor) &&
                   next < floor) {
                next = floor;
        }
        position->y = next + EYE_HEIGHT;
}

void kokiri_collision_move_actor(camera_position_t *position, int32_t dx,
        int32_t dy, int32_t dz)
{
        if (!(dx || dy || dz)) return;
        if (dx || dz)
                actor_step_xz(position, dx, dz);
        if (dy)
                actor_step_y(position, dy);
}

bool kokiri_collision_jump(const camera_position_t *position, int32_t *velocity_q8,
        int32_t *remainder_q8)
{
        int32_t floor;
        if (*velocity_q8 > 0 ||
            !kokiri_collision_floor(position->x, position->z,
                                   position->y - EYE_HEIGHT, &floor) ||
            position->y != floor + EYE_HEIGHT)
                return false;
        *velocity_q8 = JUMP_VELOCITY_Q8;
        *remainder_q8 = 0;
        return true;
}

bool kokiri_collision_fall(camera_position_t *position, int32_t *velocity_q8,
        int32_t *remainder_q8)
{
        int32_t floor, target_y, amount;
        int32_t below = position->y - EYE_HEIGHT + STEP;

        if (kokiri_collision_floor(position->x, position->z, below, &floor)) {
                target_y = floor + EYE_HEIGHT;
                if (position->y == target_y && *velocity_q8 <= 0) {
                        *velocity_q8 = 0;
                        *remainder_q8 = 0;
                        return true;
                }
        }

        *velocity_q8 += GRAVITY_Q8;
        if (*velocity_q8 < TERMINAL_VELOCITY_Q8)
                *velocity_q8 = TERMINAL_VELOCITY_Q8;
        *remainder_q8 += *velocity_q8;
        amount = *remainder_q8 / 256;
        *remainder_q8 -= amount * 256;
        if (amount) {
                int32_t old_y = position->y;
                kokiri_collision_move_actor(position, 0, amount, 0);
                if (amount > 0 && position->y - old_y < amount) {
                        /* Head hit: start falling now. */
                        *velocity_q8 = 0;
                        *remainder_q8 = 0;
                }
        }

        below = position->y - EYE_HEIGHT + STEP;
        if (kokiri_collision_floor(position->x, position->z, below, &floor) &&
            position->y == floor + EYE_HEIGHT && *velocity_q8 <= 0) {
                *velocity_q8 = 0;
                *remainder_q8 = 0;
                return true;
        }
        return false;
}
