/* Static ROM collision, independent of rendering and controller APIs. */
#include "kokiri_collision.h"
#include <limits.h>

#define RADIUS 24
#define EYE_HEIGHT 90
/* Head sphere centre above the feet: radius 8 tops out at the child's 44. */
#define LINK_HEAD_SPHERE_Y 36
#define STEP 4
/* OoT child Link checks walls at y=26 with radius 14 and checks ceilings up
 * to y=40. One sphere with those dimensions reproduces both limits here and
 * avoids treating low overhead floors as if the old eye-camera hit them. */
#define ACTOR_RADIUS 14
#define ACTOR_CHECK_HEIGHT 26
/* Child ageProperties->ceilingCheckHeight. */
#define ACTOR_CEILING_HEIGHT 40
/* A grounded step's dy before the ceiling check (see actor_step_xz). */
#define ACTOR_GROUND_DIP 7
/* OoT preserves BGCHECKFLAG_GROUND while the floor is no more than 11 units
 * below the actor. Follow that nearby floor directly so descending a ramp
 * does not alternate between airborne gravity and landing every few frames. */
#define ACTOR_GROUND_FOLLOW_DROP 11
/* OoT gives Link gravity REG(68) = -1.0 and minVelocityY -20 per 20 Hz
 * update, and Actor_UpdatePos moves by velocity * 1.5 (R_UPDATE_RATE * 0.5).
 * Per 30 Hz step (game/docs/TRAVERSAL_TIMING.md): velocity keeps its value,
 * acceleration is x2/3. So -1.0 -> -0.667 u/step^2 and terminal -20 u/step.
 * (The earlier -114 / -3413 left out the 1.5 and fell at 2/3 source speed.) */
#define GRAVITY_Q8 (-171)
#define TERMINAL_VELOCITY_Q8 (-20 * 256)
/* Custom Y jump (the human's control, not an OoT action). Rescaled with the
 * gravity fix to keep its apex: 51 units, as before; airtime 25 steps. */
#define JUMP_VELOCITY_Q8 2208

/* Poly classes, z_bgcheck.c: floor ny > 0.5, ceiling ny < -0.8, else wall.
 * Normals here are Q14. The floor test is >= because this runtime always
 * used it; exactly-0.5 slopes are the only difference. */
#define FLOOR_NY 8192
#define CEILING_NY (-13107)
#define IS_FLOOR(t) ((t)->normal[1] >= FLOOR_NY)
#define IS_CEILING(t) ((t)->normal[1] < CEILING_NY)
#define IS_WALL(t) (!IS_FLOOR(t) && !IS_CEILING(t))

static const collision_triangle_t *triangles;
static uint32_t triangle_count;
static bg_mesh_t scene_mesh;

/* Optional XZ lookup grid. Both queries below reject a triangle first on its
 * XZ bounds, so scanning all of them costs the same whether or not anything is
 * near. With an index built, only the triangles bucketed into the queried
 * cells are visited. It is opt-in: until kokiri_collision_index() succeeds the
 * queries behave exactly as before, scanning every triangle. */
#define GRID_DIM 16
static uint32_t *grid_offset;   /* GRID_DIM*GRID_DIM+1 entries: cell starts */
static uint16_t *grid_list;     /* triangle ids, grouped by cell */
static int32_t grid_x0, grid_z0, grid_step_x, grid_step_z;
static bool grid_ready;

/* Dyna slots. World-space triangles for every live slot sit in one caller
 * buffer; a slot owns [first, first+count). */
typedef struct {
        const bg_mesh_t *mesh;
        uint16_t first, count;
        uint8_t used, enabled, transform;
        int32_t pos[3], prev_pos[3];
        uint16_t rot_y, prev_rot_y;
        int32_t scale_q16, prev_scale_q16;
} dyna_slot_t;
static dyna_slot_t dyna[BG_DYNA_MAX];
static collision_triangle_t *dyna_world;
static uint32_t dyna_capacity;
static uint32_t poly_info(uint32_t bg_id, uint32_t poly);

void kokiri_collision_init(const collision_triangle_t *data, uint32_t count)
{
        bg_mesh_t mesh = {0};
        mesh.triangles = data;
        mesh.triangle_count = count;
        bg_scene_set(&mesh);
}

void bg_scene_set(const bg_mesh_t *mesh)
{
        scene_mesh = *mesh;
        triangles = mesh->triangles;
        triangle_count = mesh->triangle_count;
        grid_ready = false;
}

const bg_mesh_t *bg_scene_mesh(void)
{
        return &scene_mesh;
}

static uint32_t grid_cell(int32_t value, int32_t origin, int32_t step)
{
        int32_t cell = (value - origin) / step;
        if (cell < 0) cell = 0;
        if (cell >= GRID_DIM) cell = GRID_DIM - 1;
        return (uint32_t)cell;
}

bool kokiri_collision_index(void *buffer, uint32_t bytes)
{
        const uint32_t cells = GRID_DIM * GRID_DIM;
        int32_t min_x, max_x, min_z, max_z;
        uint32_t i, c, total, need;

        grid_ready = false;
        /* Ids are stored as uint16_t, so a larger set stays on the linear path. */
        if (!triangles || !triangle_count || triangle_count > 65535) return false;
        if (bytes < (cells + 1) * sizeof(uint32_t)) return false;

        min_x = max_x = triangles[0].minimum[0];
        min_z = max_z = triangles[0].minimum[2];
        for (i = 0; i < triangle_count; i++) {
                if (triangles[i].minimum[0] < min_x) min_x = triangles[i].minimum[0];
                if (triangles[i].maximum[0] > max_x) max_x = triangles[i].maximum[0];
                if (triangles[i].minimum[2] < min_z) min_z = triangles[i].minimum[2];
                if (triangles[i].maximum[2] > max_z) max_z = triangles[i].maximum[2];
        }
        grid_x0 = min_x;
        grid_z0 = min_z;
        grid_step_x = (max_x - min_x) / GRID_DIM + 1;
        grid_step_z = (max_z - min_z) / GRID_DIM + 1;

        grid_offset = (uint32_t *)buffer;
        for (c = 0; c <= cells; c++) grid_offset[c] = 0;
        for (i = 0; i < triangle_count; i++) {
                uint32_t x0 = grid_cell(triangles[i].minimum[0], grid_x0, grid_step_x);
                uint32_t x1 = grid_cell(triangles[i].maximum[0], grid_x0, grid_step_x);
                uint32_t z0 = grid_cell(triangles[i].minimum[2], grid_z0, grid_step_z);
                uint32_t z1 = grid_cell(triangles[i].maximum[2], grid_z0, grid_step_z);
                uint32_t x, z;
                for (z = z0; z <= z1; z++)
                        for (x = x0; x <= x1; x++) grid_offset[z * GRID_DIM + x]++;
        }
        /* Inclusive prefix sum leaves each entry at its cell's end; the fill
         * below then decrements them back down to each cell's start. */
        for (c = 1; c < cells; c++) grid_offset[c] += grid_offset[c - 1];
        total = grid_offset[cells - 1];
        grid_offset[cells] = total;

        need = (cells + 1) * sizeof(uint32_t) + total * sizeof(uint16_t);
        if (bytes < need) return false;
        grid_list = (uint16_t *)(grid_offset + cells + 1);
        for (i = 0; i < triangle_count; i++) {
                uint32_t x0 = grid_cell(triangles[i].minimum[0], grid_x0, grid_step_x);
                uint32_t x1 = grid_cell(triangles[i].maximum[0], grid_x0, grid_step_x);
                uint32_t z0 = grid_cell(triangles[i].minimum[2], grid_z0, grid_step_z);
                uint32_t z1 = grid_cell(triangles[i].maximum[2], grid_z0, grid_step_z);
                uint32_t x, z;
                for (z = z0; z <= z1; z++)
                        for (x = x0; x <= x1; x++)
                                grid_list[--grid_offset[z * GRID_DIM + x]] = (uint16_t)i;
        }
        grid_ready = true;
        return true;
}

/* Triangle ids that can matter for an XZ box. A triangle bucketed into several
 * queried cells is visited more than once, which is harmless: both queries are
 * idempotent (one takes a maximum, the other returns on the first hit). */
static uint32_t candidate_span(int32_t min_x, int32_t max_x, int32_t min_z,
        int32_t max_z, uint32_t *cx0, uint32_t *cx1, uint32_t *cz0, uint32_t *cz1)
{
        if (!grid_ready) { *cx0 = *cx1 = *cz0 = *cz1 = 0; return 0; }
        *cx0 = grid_cell(min_x, grid_x0, grid_step_x);
        *cx1 = grid_cell(max_x, grid_x0, grid_step_x);
        *cz0 = grid_cell(min_z, grid_z0, grid_step_z);
        *cz1 = grid_cell(max_z, grid_z0, grid_step_z);
        return 1;
}

static bool inside(const collision_triangle_t *t, const int32_t p[3])
{
        /* Project onto the dominant plane, avoiding long normal cross products. */
        int drop = 0;
        for (int i = 1; i < 3; i++)
                if ((int32_t)t->normal[i]*t->normal[i] > (int32_t)t->normal[drop]*t->normal[drop]) drop = i;
        int u = (drop+1)%3, v = (drop+2)%3;
        bool positive = false, negative = false;
        for (int i = 0; i < 3; i++) {
                const int16_t *a = t->vertex[i], *b = t->vertex[(i+1)%3];
                int64_t cross = (int64_t)(b[u]-a[u])*(p[v]-a[v]) - (int64_t)(b[v]-a[v])*(p[u]-a[u]);
                positive |= cross > 0;
                negative |= cross < 0;
        }
        return !(positive && negative);
}

/* The world-space triangles of enabled dyna slots, for the loops below. */
static bool dyna_live(uint32_t id)
{
        return dyna[id].used && dyna[id].enabled && dyna_world;
}

static bool sphere_touches(const collision_triangle_t *t, const int32_t p[3],
        int32_t radius)
{
        bool outside = false;
        for (int k = 0; k < 3; k++) outside |= p[k] < t->minimum[k]-radius || p[k] > t->maximum[k]+radius;
        if (outside) return false;
        int64_t dot = 0;
        for (int k = 0; k < 3; k++) dot += (int64_t)(p[k]-t->vertex[0][k])*t->normal[k];
        if (dot > radius*16384 || dot < -radius*16384) return false;
        int32_t projected[3];
        for (int k = 0; k < 3; k++) projected[k] = p[k] - (int32_t)(dot*t->normal[k]/268435456);
        if (inside(t, projected)) return true;
        /* Include triangle edges and vertices, not only face interiors. */
        for (int edge = 0; edge < 3; edge++) {
                const int16_t *a = t->vertex[edge], *b = t->vertex[(edge+1)%3];
                int64_t length = 0, along = 0, distance = 0;
                for (int k = 0; k < 3; k++) {
                        length += (int64_t)(b[k]-a[k])*(b[k]-a[k]);
                        along += (int64_t)(p[k]-a[k])*(b[k]-a[k]);
                }
                if (along < 0) along = 0;
                if (along > length) along = length;
                for (int k = 0; k < 3; k++) {
                        int32_t q = a[k] + (length ? (int32_t)((b[k]-a[k])*along/length) : 0);
                        distance += (int64_t)(p[k]-q)*(p[k]-q);
                }
                if (distance <= radius*radius) return true;
        }
        return false;
}

static bool clear_radius(camera_position_t position, int32_t radius,
        bool skip_ceilings, uint32_t ignore)
{
        const int32_t p[3] = {position.x, position.y, position.z};
        uint32_t cx0, cx1, cz0, cz1, cx, cz, slot, end, i, id;
        const bool indexed = candidate_span(p[0] - radius, p[0] + radius,
                p[2] - radius, p[2] + radius, &cx0, &cx1, &cz0, &cz1) != 0;
        for (cz = cz0; cz <= cz1; cz++)
        for (cx = cx0; cx <= cx1; cx++) {
        slot = indexed ? grid_offset[cz * GRID_DIM + cx] : 0;
        end = indexed ? grid_offset[cz * GRID_DIM + cx + 1] : triangle_count;
        for (; slot < end; slot++) {
                i = indexed ? grid_list[slot] : slot;
                if ((poly_info(BG_SCENE, i) >> 8) & ignore) continue;
                if (skip_ceilings && triangles[i].normal[1] < -13107) continue;
                if (sphere_touches(&triangles[i], p, radius)) return false;
        }
        }
        for (id = 0; id < BG_DYNA_MAX; id++) {
                if (!dyna_live(id)) continue;
                for (i = 0; i < dyna[id].count; i++) {
                        const collision_triangle_t *t = &dyna_world[dyna[id].first + i];
                        if ((poly_info(id, i) >> 8) & ignore) continue;
                        if (skip_ceilings && t->normal[1] < -13107) continue;
                        if (sphere_touches(t, p, radius)) return false;
                }
        }
        return true;
}

static bool collision_clear_radius(camera_position_t position, int32_t radius)
{
        return clear_radius(position, radius, false, BG_IGNORE_ENTITY);
}

bool kokiri_collision_clear(camera_position_t position)
{
        return clear_radius(position, RADIUS, false, BG_IGNORE_CAMERA);
}

static bool actor_clear(camera_position_t position)
{
        position.y += ACTOR_CHECK_HEIGHT - EYE_HEIGHT;
        return collision_clear_radius(position, ACTOR_RADIUS);
}

static bool old_floor_at(const collision_triangle_t *t, int32_t x, int32_t z,
        int32_t *y)
{
        if (t->normal[1] < 8192 || x < t->minimum[0] || x > t->maximum[0] ||
            z < t->minimum[2] || z > t->maximum[2]) return false;
        *y = t->vertex[0][1] - (int32_t)(((int64_t)t->normal[0]*(x-t->vertex[0][0]) +
            (int64_t)t->normal[2]*(z-t->vertex[0][2]))/t->normal[1]);
        int32_t p[3] = {x,*y,z};
        return inside(t,p);
}

bool kokiri_collision_floor(int32_t x, int32_t z, int32_t below, int32_t *height)
{
        int32_t best = INT32_MIN, y;
        uint32_t cx0, cx1, cz0, cz1, slot, end, i, id;
        const bool indexed = candidate_span(x, x, z, z, &cx0, &cx1, &cz0, &cz1) != 0;
        slot = indexed ? grid_offset[cz0 * GRID_DIM + cx0] : 0;
        end = indexed ? grid_offset[cz0 * GRID_DIM + cx0 + 1] : triangle_count;
        (void)cx1; (void)cz1;
        for (; slot < end; slot++) {
                i = indexed ? grid_list[slot] : slot;
                if ((poly_info(BG_SCENE, i) >> 8) & BG_IGNORE_ENTITY) continue;
                if (old_floor_at(&triangles[i], x, z, &y) && y <= below && y > best) best = y;
        }
        for (id = 0; id < BG_DYNA_MAX; id++) {
                if (!dyna_live(id)) continue;
                for (i = 0; i < dyna[id].count; i++)
                        if (!((poly_info(id, i) >> 8) & BG_IGNORE_ENTITY) &&
                            old_floor_at(&dyna_world[dyna[id].first + i], x, z, &y) &&
                            y <= below && y > best) best = y;
        }
        if (best == INT32_MIN) return false;
        *height = best;
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

static void move_axis(camera_position_t *position, int axis, int32_t amount,
        bool actor)
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
                /* Link only considers ground at/below his feet plus one step.
                 * The old eye-camera search reached 66 units above his feet,
                 * so a walkable bridge overhead looked like a giant step and
                 * blocked horizontal movement underneath it. */
                int32_t below = actor ? position->y-EYE_HEIGHT+STEP
                                      : position->y-RADIUS;
                if (kokiri_collision_floor(next.x,next.z,below,&floor) &&
                    next.y < floor+EYE_HEIGHT)
                        next.y = floor+EYE_HEIGHT;
                /* No snapping through ceilings or climbing tall steps. */
                if (next.y-position->y > STEP ||
                    !(actor ? actor_clear(next) : kokiri_collision_clear(next))) break;
                if (actor && axis == 1 && step > 0) {
                        /* Rendered child is 44 units tall (BUG-009). Sweep a small head
                         * sphere too when rising; don't jump through a bridge. */
                        camera_position_t head = next;
                        head.y += LINK_HEAD_SPHERE_Y - EYE_HEIGHT;
                        if (!collision_clear_radius(head, 8)) break;
                }
                *position = next;
                amount -= step;
        }
}

void kokiri_collision_move(camera_position_t *position, int32_t dx, int32_t dy, int32_t dz)
{
        if (!(dx || dy || dz)) return;
        /* Small swept steps avoid tunnelling; separate axes slide along walls. */
        move_axis(position,0,dx,false);
        move_axis(position,2,dz,false);
        move_axis(position,1,dy,false);
}

/* Last horizontal actor step's wall contact (BGCHECKFLAG_WALL), for the
 * player's wall/ledge probe. See kokiri_collision_actor_wall(). */
static bool actor_wall_valid, actor_stepped;
static bg_hit_t actor_wall_hit;
/* Player_ProcessSceneCollision's wall radius / height and ceiling height:
 * child 14 / 26 / 40, crawling 10 / 15 / 30. */
static int32_t actor_radius = ACTOR_RADIUS, actor_check_height = ACTOR_CHECK_HEIGHT,
        actor_ceiling = ACTOR_CEILING_HEIGHT;

void kokiri_collision_actor_probe_still(const camera_position_t *position)
{
        /* Actor_UpdateBgCheckInfo still runs the sphere with prev == pos: a
         * wall at exactly the radius is touched with no push. */
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

/* One horizontal step of Actor_UpdateBgCheckInfo with the player's flags,
 * in its order (z_actor.c):
 *  1. UPDBGCHECKINFO_FLAG_0: BgCheck_EntitySphVsWall3, prev -> new, radius
 *     14 at 26 above the feet (Player_ProcessSceneCollision, child).
 *  2. FLAG_1: BgCheck_EntityCheckCeiling from prev.y + 10 over
 *     ceilingCheckHeight (child 40) + dy - 10; a hit puts y at ceiling - 40.
 *  3. func_8002E2AC: floor raycast from y + 50 (strictly below). At or above
 *     the feet: stand on it -- unless a ceiling was hit on the same bgId, in
 *     which case x/z revert to prev (no headroom). Below: keep y; the source
 *     only leaves the ground when the drop exceeds 11 (func_8002E234), which
 *     the ground follow below reproduces.
 * Water (FLAG_2) is M1k. The floor height uses the floor-class query the
 * gravity step also uses, so standing stays exact; RaycastDown's up-facing
 * steep walls and isSoft are not floors here (BUG_FEATURE_LOG). */
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

        /* dy: a grounded actor carries velocity.y -4 (UPDBGCHECKINFO_FLAG_3)
         * and gravity makes it -5 before this check: dy = -5 x 1.5 = -7.5
         * a source update, so the range ceilingCheckHeight + dy - 10 is 7.5
         * shorter. Kept as that distance, not rescaled to 30 Hz: it is the
         * headroom geometry (the sword maze's 24-high crawlspace needs it).
         * Integer distances: d < h - 7.5 is exactly d < h - 7. */
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

/* The vertical part of the same update. Walls never stop vertical motion in
 * the source -- only UPDBGCHECKINFO_FLAG_1's ceiling check (from prev.y + 10
 * over ceilingCheckHeight + dy - 10; a hit puts y at ceiling - 40) and the
 * floor. The old wall sphere is not used here: Link now rests exactly on a
 * wall's radius, where it would pin him in the air. The old rise's head
 * sphere is kept for everything but ceiling polys, so a jump still cannot
 * pass up through a walkable bridge -- this port's rule, for the custom Y
 * jump. */
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
                /* The old rise's head sphere at the drawn height (the child
                 * mesh is 44 tall), in its STEP increments, so a jump cannot
                 * pass up through a walkable bridge. Ceiling polys are left to
                 * the source rule above. */
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

        /* Horizontal movement already snaps upward onto walkable ramps. Reset
         * falling state whenever Link is exactly on that floor. A lower floor
         * does not qualify, so walking off an edge starts a real fall. Probe
         * from his feet, not the camera sphere: otherwise a bridge overhead
         * can hide the actual ground beneath him. */
        if (kokiri_collision_floor(position->x, position->z,
                                   below, &floor)) {
                target_y = floor + EYE_HEIGHT;
                if (position->y == target_y && *velocity_q8 <= 0) {
                        position->y = target_y;
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
                        /* Head hit: start falling now, not after an invisible
                         * upward velocity counts down against the ceiling. */
                        *velocity_q8 = 0;
                        *remainder_q8 = 0;
                }
        }

        below = position->y - EYE_HEIGHT + STEP;
        if (kokiri_collision_floor(position->x, position->z, below, &floor) &&
            position->y == floor + EYE_HEIGHT && *velocity_q8 <= 0) {
                position->y = floor + EYE_HEIGHT;
                *velocity_q8 = 0;
                *remainder_q8 = 0;
                return true;
        }
        return false;
}

/* ------------------------------------------------------------------------
 * World-collision contract. Everything below is integer: positions in world
 * units, normals Q14, plane distances Q14 (world units * 16384) in int64.
 * ---------------------------------------------------------------------- */

/* D_80119D90 (z_bgcheck.c): wall type -> WALL_FLAG_*; types 8..31 are 0. */
static const uint8_t wall_type_flags[8] = {
        0, BG_WALL_FLAG_0, BG_WALL_FLAG_0 | BG_WALL_FLAG_1,
        BG_WALL_FLAG_0 | BG_WALL_FLAG_2, BG_WALL_FLAG_3,
        BG_WALL_CRAWLSPACE_1, BG_WALL_CRAWLSPACE_2, BG_WALL_FLAG_6,
};

uint32_t bg_wall_flags(const bg_hit_t *hit)
{
        uint32_t type = bg_wall_type(hit);
        return type < 8 ? wall_type_flags[type] : 0;
}

static uint32_t isqrt32(uint32_t v)
{
        uint32_t r = 0, bit = 1u << 30;
        while (bit > v) bit >>= 2;
        while (bit) {
                if (v >= r + bit) { v -= r + bit; r = (r >> 1) + bit; }
                else r >>= 1;
                bit >>= 2;
        }
        return r;
}

static const bg_mesh_t *owner_mesh(uint32_t bg_id)
{
        return bg_id == BG_SCENE ? &scene_mesh : dyna[bg_id].mesh;
}

static uint32_t poly_info(uint32_t bg_id, uint32_t poly)
{
        const bg_mesh_t *m = owner_mesh(bg_id);
        return m && m->info ? m->info[poly] : 0;
}

static void fill_hit(bg_hit_t *hit, const collision_triangle_t *t,
        uint32_t bg_id, uint32_t poly)
{
        const bg_mesh_t *m = owner_mesh(bg_id);
        uint32_t info = poly_info(bg_id, poly), s = info & 0xFF;
        if (!hit) return;
        hit->normal[0] = t->normal[0];
        hit->normal[1] = t->normal[1];
        hit->normal[2] = t->normal[2];
        hit->poly = (uint16_t)poly;
        hit->bg_id = (uint8_t)bg_id;
        hit->ignore = (uint8_t)(info >> 8 & 7);
        hit->conveyor = (uint8_t)(info >> 11 & 1);
        hit->data0 = hit->data1 = 0;
        if (m && m->surfaces && s < m->surface_count) {
                hit->data0 = m->surfaces[s * 2];
                hit->data1 = m->surfaces[s * 2 + 1];
        }
}

/* Visit every static and dyna triangle whose cell overlaps an XZ box. Dyna
 * first, then the scene, the order BgCheck_CheckWallImpl tests them in.
 * The callback returns false to stop. */
typedef bool (*visit_fn)(const collision_triangle_t *t, uint32_t bg_id,
        uint32_t poly, void *ctx);

static void visit(int32_t min_x, int32_t max_x, int32_t min_z, int32_t max_z,
        uint32_t ignore, visit_fn fn, void *ctx)
{
        uint32_t cx0, cx1, cz0, cz1, cx, cz, slot, end, i, id;
        bool indexed;

        for (id = 0; id < BG_DYNA_MAX; id++) {
                if (!dyna_live(id)) continue;
                for (i = 0; i < dyna[id].count; i++) {
                        const collision_triangle_t *t = &dyna_world[dyna[id].first + i];
                        if (t->maximum[0] < min_x || t->minimum[0] > max_x ||
                            t->maximum[2] < min_z || t->minimum[2] > max_z) continue;
                        if ((poly_info(id, i) >> 8) & ignore) continue;
                        if (!fn(t, id, i, ctx)) return;
                }
        }
        indexed = candidate_span(min_x, max_x, min_z, max_z, &cx0, &cx1, &cz0, &cz1) != 0;
        for (cz = cz0; cz <= cz1; cz++)
        for (cx = cx0; cx <= cx1; cx++) {
                slot = indexed ? grid_offset[cz * GRID_DIM + cx] : 0;
                end = indexed ? grid_offset[cz * GRID_DIM + cx + 1] : triangle_count;
                for (; slot < end; slot++) {
                        const collision_triangle_t *t;
                        i = indexed ? grid_list[slot] : slot;
                        t = &triangles[i];
                        if (t->maximum[0] < min_x || t->minimum[0] > max_x ||
                            t->maximum[2] < min_z || t->minimum[2] > max_z) continue;
                        if ((poly_info(BG_SCENE, i) >> 8) & ignore) continue;
                        if (!fn(t, BG_SCENE, i, ctx)) return;
                }
        }
}

/* Point in triangle, projected along axis `drop`, allowing `tol` units past
 * an edge (the source's chkDist / "Approx" tests). */
static bool inside_tol(const collision_triangle_t *t, const int32_t p[3],
        int drop, int32_t tol)
{
        int u = (drop + 1) % 3, v = (drop + 2) % 3, i;
        const int16_t *a0 = t->vertex[0], *b0 = t->vertex[1], *c0 = t->vertex[2];
        int64_t area = (int64_t)(b0[u]-a0[u])*(c0[v]-a0[v]) - (int64_t)(b0[v]-a0[v])*(c0[u]-a0[u]);
        if (!area) return false;
        for (i = 0; i < 3; i++) {
                const int16_t *a = t->vertex[i], *b = t->vertex[(i+1)%3];
                int32_t du = b[u]-a[u], dv = b[v]-a[v];
                int64_t cross = (int64_t)du*(p[v]-a[v]) - (int64_t)dv*(p[u]-a[u]);
                if (area < 0) cross = -cross;
                if (cross >= 0) continue;
                /* Outside this edge: within tol of it? |cross| = dist * len. */
                {
                        int64_t l1 = (int64_t)(du < 0 ? -du : du) + (dv < 0 ? -dv : dv);
                        int64_t len2 = (int64_t)du*du + (int64_t)dv*dv;
                        if (-cross > tol * l1) return false;
                        if (cross * cross > (int64_t)tol * tol * len2) return false;
                }
        }
        return true;
}

/* Math3D_TriChkPointPara{X,Y,Z}Impl(detMax 300, chkDist 1): the "Approx"
 * point-in-triangle test of floors, ceilings and the wall sphere, projected
 * along `drop`. Inside, near a vertex, within the triangle's box and with
 * every edge determinant (edge length x distance) on one side within 300 --
 * about 300 / edge length units of slack -- or, for a poly facing the drop
 * axis (> 0.5), within 1 of an edge. Lines use inside_tol. */
static bool inside_approx(const collision_triangle_t *t, const int32_t p[3], int drop)
{
        int u = (drop + 1) % 3, v = (drop + 2) % 3, i;
        int32_t lu = t->vertex[0][u], hu = lu, lv = t->vertex[0][v], hv = lv;
        int64_t det[3];
        for (i = 1; i < 3; i++) {
                if (t->vertex[i][u] < lu) lu = t->vertex[i][u];
                if (t->vertex[i][u] > hu) hu = t->vertex[i][u];
                if (t->vertex[i][v] < lv) lv = t->vertex[i][v];
                if (t->vertex[i][v] > hv) hv = t->vertex[i][v];
        }
        /* Math3D_CirSquareVsTriSquare. */
        if (p[u] < lu - 1 || p[u] > hu + 1 || p[v] < lv - 1 || p[v] > hv + 1)
                return false;
        for (i = 0; i < 3; i++) {
                int32_t du = t->vertex[i][u] - p[u], dv = t->vertex[i][v] - p[v];
                if (du * du + dv * dv < 1) return true;
        }
        for (i = 0; i < 3; i++) {
                const int16_t *a = t->vertex[i], *b = t->vertex[(i + 1) % 3];
                det[i] = (int64_t)(a[u] - p[u]) * (b[v] - p[v]) -
                         (int64_t)(a[v] - p[v]) * (b[u] - p[u]);
        }
        if ((det[0] <= 300 && det[1] <= 300 && det[2] <= 300) ||
            (det[0] >= -300 && det[1] >= -300 && det[2] >= -300))
                return true;
        if ((t->normal[drop] < 0 ? -t->normal[drop] : t->normal[drop]) > 8192) {
                /* Math3D_PointDistSqToLine2D: only a foot on the segment. */
                for (i = 0; i < 3; i++) {
                        const int16_t *a = t->vertex[i], *b = t->vertex[(i + 1) % 3];
                        int64_t eu = b[u] - a[u], ev = b[v] - a[v];
                        int64_t len = eu * eu + ev * ev;
                        int64_t along = (int64_t)(p[u] - a[u]) * eu + (int64_t)(p[v] - a[v]) * ev;
                        int64_t cross;
                        if (!len || along < 0 || along > len) continue;
                        cross = (int64_t)(p[u] - a[u]) * ev - (int64_t)(p[v] - a[v]) * eu;
                        if (cross * cross < len) return true;   /* dist^2 < 1 */
                }
        }
        return false;
}

static int dominant_axis(const collision_triangle_t *t)
{
        int drop = 0, i;
        for (i = 1; i < 3; i++)
                if ((int32_t)t->normal[i]*t->normal[i] > (int32_t)t->normal[drop]*t->normal[drop]) drop = i;
        return drop;
}

static int64_t plane_q14(const collision_triangle_t *t, int32_t x, int32_t y, int32_t z)
{
        return (int64_t)t->normal[0]*(x-t->vertex[0][0]) +
               (int64_t)t->normal[1]*(y-t->vertex[0][1]) +
               (int64_t)t->normal[2]*(z-t->vertex[0][2]);
}

static const collision_triangle_t *hit_triangle(const bg_hit_t *hit)
{
        if (hit->bg_id == BG_SCENE)
                return hit->poly < triangle_count ? &triangles[hit->poly] : 0;
        if (hit->bg_id >= BG_DYNA_MAX || !dyna_live(hit->bg_id) ||
            hit->poly >= dyna[hit->bg_id].count)
                return 0;
        return &dyna_world[dyna[hit->bg_id].first + hit->poly];
}

bool bg_poly_vertices(const bg_hit_t *hit, int16_t vertex[3][3])
{
        const collision_triangle_t *t = hit_triangle(hit);
        int i, k;
        if (!t) return false;
        for (i = 0; i < 3; i++)
                for (k = 0; k < 3; k++)
                        vertex[i][k] = t->vertex[i][k];
        return true;
}

int32_t bg_poly_plane_distance(const bg_hit_t *hit, const bg_vec_t *pos)
{
        const collision_triangle_t *t;
        int64_t d;
        if (hit->bg_id == BG_SCENE) {
                if (hit->poly >= triangle_count) return -1;
                t = &triangles[hit->poly];
        } else {
                if (hit->bg_id >= BG_DYNA_MAX || !dyna_live(hit->bg_id) ||
                    hit->poly >= dyna[hit->bg_id].count) return -1;
                t = &dyna_world[dyna[hit->bg_id].first + hit->poly];
        }
        d = plane_q14(t, pos->x, pos->y, pos->z);
        if (d < 0) d = -d;
        return (int32_t)(d >> 14);
}

/* Plane height at x/z; false for a vertical plane. */
static bool plane_y(const collision_triangle_t *t, int32_t x, int32_t z, int32_t *y)
{
        if (!t->normal[1]) return false;
        *y = t->vertex[0][1] - (int32_t)(((int64_t)t->normal[0]*(x-t->vertex[0][0]) +
            (int64_t)t->normal[2]*(z-t->vertex[0][2]))/t->normal[1]);
        return true;
}

/* ---- RaycastDown ---- */
typedef struct { int32_t x, y, z, best; const collision_triangle_t *t; uint32_t id, poly; } floor_ctx_t;

static bool floor_visit(const collision_triangle_t *t, uint32_t bg_id, uint32_t poly, void *c)
{
        floor_ctx_t *f = (floor_ctx_t *)c;
        int32_t y, p[3];
        /* Floors, plus walls facing up (CHECK_WALLS_SIMPLE | GROUND_ONLY). */
        if (IS_CEILING(t) || t->normal[1] <= 0) return true;
        if (!plane_y(t, f->x, f->z, &y)) return true;
        p[0] = f->x; p[1] = y; p[2] = f->z;
        if (y < f->y && y > f->best && inside_approx(t, p, 1)) {
                f->best = y; f->t = t; f->id = bg_id; f->poly = poly;
        }
        return true;
}

int32_t bg_floor(const bg_vec_t *pos, uint32_t ignore, bg_hit_t *hit)
{
        floor_ctx_t f;
        f.x = pos->x; f.y = pos->y; f.z = pos->z; f.best = BG_Y_MIN; f.t = 0;
        f.id = BG_NONE; f.poly = 0;
        visit(pos->x, pos->x, pos->z, pos->z, ignore, floor_visit, &f);
        if (!f.t) {
                if (hit) { hit->bg_id = BG_NONE; hit->data0 = hit->data1 = 0; }
                return BG_Y_MIN;
        }
        {
                bg_hit_t h;
                fill_hit(&h, f.t, f.id, f.poly);
                if (bg_is_soft(&h)) f.best -= 1;
                if (hit) *hit = h;
        }
        return f.best;
}

/* ---- Ceiling ---- */
typedef struct { int32_t x, y, z, h, best; const collision_triangle_t *t; uint32_t id, poly; } ceil_ctx_t;

static bool ceiling_visit(const collision_triangle_t *t, uint32_t bg_id, uint32_t poly, void *c)
{
        ceil_ctx_t *f = (ceil_ctx_t *)c;
        int32_t y, p[3], d;
        if (!IS_CEILING(t) || !plane_y(t, f->x, f->z, &y)) return true;
        p[0] = f->x; p[1] = y; p[2] = f->z;
        d = y - f->y;
        if (d > 0 && d < f->h && y < f->best && inside_approx(t, p, 1)) {
                f->best = y; f->t = t; f->id = bg_id; f->poly = poly;
        }
        return true;
}

bool bg_ceiling(int32_t *out_y, const bg_vec_t *pos, int32_t check_height,
        uint32_t ignore, bg_hit_t *hit)
{
        ceil_ctx_t f;
        f.x = pos->x; f.y = pos->y; f.z = pos->z; f.h = check_height;
        f.best = INT32_MAX; f.t = 0; f.id = BG_NONE; f.poly = 0;
        *out_y = pos->y;
        visit(pos->x, pos->x, pos->z, pos->z, ignore, ceiling_visit, &f);
        if (!f.t) return false;
        *out_y = f.best - check_height;
        fill_hit(hit, f.t, f.id, f.poly);
        return true;
}

/* ---- Line ---- */
typedef struct {
        bg_vec_t a, b, at; uint32_t checks; int64_t best;
        const collision_triangle_t *t; uint32_t id, poly;
} line_ctx_t;

static bool line_visit(const collision_triangle_t *t, uint32_t bg_id, uint32_t poly, void *c)
{
        line_ctx_t *f = (line_ctx_t *)c;
        int64_t da, db, dd, dist;
        int32_t p[3];
        uint32_t cls = IS_FLOOR(t) ? BG_CHECK_FLOOR : IS_CEILING(t) ? BG_CHECK_CEILING : BG_CHECK_WALL;
        if (!(cls & f->checks)) return true;
        da = plane_q14(t, f->a.x, f->a.y, f->a.z);
        db = plane_q14(t, f->b.x, f->b.y, f->b.z);
        dd = da - db;
        /* CollisionPoly_LineVsPoly rejects. */
        if ((da >= 0 && db >= 0) || (da < 0 && db < 0) ||
            ((f->checks & BG_CHECK_ONE_FACE) && da < 0 && db > 0) || !dd) return true;
        p[0] = f->a.x + (int32_t)((int64_t)(f->b.x - f->a.x) * da / dd);
        p[1] = f->a.y + (int32_t)((int64_t)(f->b.y - f->a.y) * da / dd);
        p[2] = f->a.z + (int32_t)((int64_t)(f->b.z - f->a.z) * da / dd);
        if (!inside_tol(t, p, dominant_axis(t), 1)) return true;
        dist = (int64_t)(p[0]-f->a.x)*(p[0]-f->a.x) + (int64_t)(p[1]-f->a.y)*(p[1]-f->a.y) +
               (int64_t)(p[2]-f->a.z)*(p[2]-f->a.z);
        if (f->t && dist >= f->best) return true;
        f->best = dist; f->t = t; f->id = bg_id; f->poly = poly;
        f->at.x = p[0]; f->at.y = p[1]; f->at.z = p[2];
        return true;
}

bool bg_line(const bg_vec_t *a, const bg_vec_t *b, bg_vec_t *at,
        uint32_t checks, uint32_t ignore, bg_hit_t *hit)
{
        line_ctx_t f;
        f.a = *a; f.b = *b; f.checks = checks; f.t = 0; f.best = 0;
        f.id = BG_NONE; f.poly = 0;
        visit(a->x < b->x ? a->x : b->x, a->x < b->x ? b->x : a->x,
              a->z < b->z ? a->z : b->z, a->z < b->z ? b->z : a->z,
              ignore, line_visit, &f);
        if (!f.t) return false;
        if (at) *at = f.at;
        fill_hit(hit, f.t, f.id, f.poly);
        return true;
}

/* ---- Wall (sphere vs walls, BgCheck_SphVsStaticWall / SphVsDynaWall) ---- */
typedef struct {
        int32_t x, cy, z, radius; bool z_pass; bool found;
        const collision_triangle_t *t; uint32_t id, poly; bool dyna;
} wall_ctx_t;

static int32_t round_div(int64_t n, int64_t d)
{
        /* Round away from zero: a push must clear the radius, not stop short. */
        int64_t q = n / d;
        if (q * d != n) q += ((n < 0) == (d < 0)) ? 1 : -1;
        return (int32_t)q;
}

static bool wall_visit(const collision_triangle_t *t, uint32_t bg_id, uint32_t poly, void *c)
{
        wall_ctx_t *f = (wall_ctx_t *)c;
        int32_t nx = t->normal[0], nz = t->normal[2];
        int32_t na = f->z_pass ? nz : nx, nxz, lo, hi, q, p[3], intersect, dist;
        int64_t pd;
        int k = f->z_pass ? 2 : 0;
        if (!IS_WALL(t)) return true;
        /* Every vertex above the sphere centre: not this wall. */
        if (f->cy < t->vertex[0][1] && f->cy < t->vertex[1][1] && f->cy < t->vertex[2][1]) return true;
        pd = plane_q14(t, f->x, f->cy, f->z);
        if (pd > (int64_t)f->radius * 16384 || pd < -(int64_t)f->radius * 16384) return true;
        nxz = (int32_t)isqrt32((uint32_t)(nx * nx + nz * nz));
        if (!nxz || !na) return true;
        /* |n_axis| / |n_xz| < 0.4: the other pass handles this wall. */
        if ((na < 0 ? -na : na) * 10 < nxz * 4) return true;
        q = f->z_pass ? f->z : f->x;
        lo = t->minimum[k] - f->radius; hi = t->maximum[k] + f->radius;
        if (q < lo || q > hi) return true;
        /* Where the axis line through the sphere centre meets the plane. */
        p[0] = f->x; p[1] = f->cy; p[2] = f->z;
        /* Solve n.(P - v0) = 0 for the axis coordinate. */
        {
                int64_t rest = 0;
                int j;
                for (j = 0; j < 3; j++)
                        if (j != k) rest += (int64_t)t->normal[j] * (p[j] - t->vertex[0][j]);
                intersect = t->vertex[0][k] - (int32_t)(rest / na);
        }
        p[k] = intersect;
        if (!inside_approx(t, p, k)) return true;
        dist = intersect - q;
        /* |dist| <= radius / (|n_axis| / |n_xz|), and not far behind the face. */
        if ((int64_t)(dist < 0 ? -dist : dist) * (na < 0 ? -na : na) > (int64_t)f->radius * nxz)
                return true;
        if ((int64_t)dist * na > 4 * 16384) return true;
        /* BgCheck_ComputeWallDisplacement: (radius - planeDist) / |n_xz| along n. */
        {
                int64_t push = (int64_t)f->radius * 16384 - pd;     /* Q14 */
                f->x += round_div(push * nx, (int64_t)nxz * 16384);
                f->z += round_div(push * nz, (int64_t)nxz * 16384);
        }
        /* Keep an earlier wall carrying data1 bit 27 (wall damage); else the
         * newest wall wins. */
        if (f->t) {
                bg_hit_t h;
                fill_hit(&h, f->t, f->id, f->poly);
                if (bg_wall_damage(&h)) { f->found = true; if (bg_id != BG_SCENE) f->dyna = true; return true; }
        }
        f->t = t; f->id = bg_id; f->poly = poly; f->found = true;
        if (bg_id != BG_SCENE) f->dyna = true;
        return true;
}

static bool sphere_vs_walls(int32_t *x, int32_t *z, int32_t cy, int32_t radius,
        uint32_t ignore, wall_ctx_t *f)
{
        f->x = *x; f->z = *z; f->cy = cy; f->radius = radius;
        f->found = false;
        f->z_pass = true;
        visit(*x - radius, *x + radius, *z - radius, *z + radius, ignore, wall_visit, f);
        f->z_pass = false;
        visit(f->x - radius, f->x + radius, f->z - radius, f->z + radius, ignore, wall_visit, f);
        *x = f->x; *z = f->z;
        return f->found;
}

bool bg_wall(bg_vec_t *result, const bg_vec_t *next, const bg_vec_t *prev,
        int32_t radius, int32_t check_height, uint32_t ignore, bool skip_line,
        bg_hit_t *hit)
{
        int32_t dx = next->x - prev->x, dy = next->y - prev->y, dz = next->z - prev->z;
        bool found = false;
        bg_hit_t line_hit;
        bg_vec_t at;
        wall_ctx_t f;

        f.t = 0; f.id = BG_NONE; f.poly = 0; f.dyna = false;
        *result = *next;
        if (hit) hit->bg_id = BG_NONE;
        if ((dx || dz) && !skip_line) {
                if (check_height + dy < 5) {
                        /* Source bug kept: checkHeight is not applied here. */
                        if (bg_line(prev, next, &at, BG_CHECK_WALL | BG_CHECK_FLOOR,
                                    ignore, &line_hit)) {
                                if (line_hit.normal[1] >= FLOOR_NY) {
                                        result->x = at.x;
                                        result->y = at.y - (check_height > 1 ? 1 : check_height);
                                        result->z = at.z;
                                } else {
                                        result->x = at.x + radius * line_hit.normal[0] / 16384;
                                        result->y = at.y + radius * line_hit.normal[1] / 16384;
                                        result->z = at.z + radius * line_hit.normal[2] / 16384;
                                }
                                if (hit) *hit = line_hit;
                                found = true;
                        }
                } else {
                        bg_vec_t a = *prev, b = *next;
                        uint32_t checks = (int64_t)radius * radius < (int64_t)dx * dx + (int64_t)dz * dz
                                ? (BG_CHECK_WALL | BG_CHECK_FLOOR) : BG_CHECK_WALL;
                        b.y += check_height;
                        a.y = b.y;
                        if (bg_line(&a, &b, &at, checks, ignore, &line_hit)) {
                                int32_t nxz = (int32_t)isqrt32((uint32_t)(line_hit.normal[0] * line_hit.normal[0] +
                                        line_hit.normal[2] * line_hit.normal[2]));
                                if (nxz) {
                                        result->x = at.x + round_div((int64_t)radius * line_hit.normal[0], nxz);
                                        result->z = at.z + round_div((int64_t)radius * line_hit.normal[2], nxz);
                                        if (hit) *hit = line_hit;
                                        found = true;
                                }
                        }
                }
        }
        if (sphere_vs_walls(&result->x, &result->z, result->y + check_height, radius,
                            ignore, &f)) {
                found = true;
                fill_hit(hit, f.t, f.id, f.poly);
        }
        if (f.dyna) {
                /* A dyna wall moved into us: never end up behind any wall. */
                if (bg_line(prev, result, &at, BG_CHECK_ONE_FACE | BG_CHECK_WALL,
                            ignore, &line_hit)) {
                        int32_t nxz = (int32_t)isqrt32((uint32_t)(line_hit.normal[0] * line_hit.normal[0] +
                                line_hit.normal[2] * line_hit.normal[2]));
                        if (nxz) {
                                result->x = at.x + round_div((int64_t)radius * line_hit.normal[0], nxz);
                                result->z = at.z + round_div((int64_t)radius * line_hit.normal[2], nxz);
                                if (hit) *hit = line_hit;
                                found = true;
                        }
                }
        }
        return found;
}

/* ---- Water ---- */
bool bg_water_surface(int32_t x, int32_t z, uint32_t room, int32_t *surface,
        const bg_waterbox_t **box)
{
        uint32_t i;
        for (i = 0; i < scene_mesh.water_count; i++) {
                const bg_waterbox_t *w = &scene_mesh.water[i];
                uint32_t r = BG_WATERBOX_ROOM(w->properties);
                if (r != room && r != BG_WATERBOX_ROOM_ALL) continue;
                if (w->properties & BG_WATERBOX_DISABLED) continue;
                if (w->x_min < x && x < w->x_min + w->x_length &&
                    w->z_min < z && z < w->z_min + w->z_length) {
                        *surface = w->y_surface;
                        if (box) *box = w;
                        return true;
                }
        }
        return false;
}

/* ---- KBG2 decode ---- */
static uint32_t be16(const uint8_t *p) { return (uint32_t)p[0] << 8 | p[1]; }
static uint32_t be32(const uint8_t *p) { return be16(p) << 16 | be16(p + 2); }

typedef struct {
        uint32_t tris, surfaces, water, cameras, vectors;
        uint32_t o_tris, o_info, o_surf, o_water, o_cam, o_vec, file_end;
} kbg2_layout_t;

static bool kbg2_layout(const uint8_t *file, uint32_t length, kbg2_layout_t *l)
{
        if (!file || length < 16 || file[0] != 'K' || file[1] != 'B' ||
            file[2] != 'G' || file[3] != '2') return false;
        l->tris = be16(file + 4); l->surfaces = be16(file + 6);
        l->water = be16(file + 8); l->cameras = be16(file + 10);
        l->vectors = be16(file + 12);
        if (!l->tris || l->surfaces > 256) return false;
        l->o_tris = 16;
        l->o_info = l->o_tris + l->tris * 36;
        l->o_surf = l->o_info + ((l->tris * 2 + 3) & ~3u);
        l->o_water = l->o_surf + l->surfaces * 8;
        l->o_cam = l->o_water + l->water * 16;
        l->o_vec = l->o_cam + l->cameras * 8;
        l->file_end = l->o_vec + l->vectors * 6;
        return l->file_end == length;
}

static uint32_t native_bytes(const kbg2_layout_t *l, uint32_t *o_info,
        uint32_t *o_surf, uint32_t *o_water, uint32_t *o_cam, uint32_t *o_vec)
{
        uint32_t o = l->tris * sizeof(collision_triangle_t);
        o = (o + 3) & ~3u; *o_info = o; o += l->tris * 2;
        o = (o + 3) & ~3u; *o_surf = o; o += l->surfaces * 8;
        *o_water = o; o += l->water * sizeof(bg_waterbox_t);
        *o_cam = o; o += l->cameras * sizeof(bg_camera_t);
        *o_vec = o; o += l->vectors * 6;
        return (o + 3) & ~3u;
}

uint32_t bg_mesh_bytes(const uint8_t *file, uint32_t length)
{
        kbg2_layout_t l;
        uint32_t a, b, c, d, e;
        if (!kbg2_layout(file, length, &l)) return 0;
        return native_bytes(&l, &a, &b, &c, &d, &e);
}

bool bg_mesh_decode(const uint8_t *file, uint32_t length, void *dest,
        uint32_t dest_bytes, bg_mesh_t *mesh)
{
        kbg2_layout_t l;
        uint32_t o_info, o_surf, o_water, o_cam, o_vec, i, k, need;
        uint8_t *out = (uint8_t *)dest;
        collision_triangle_t *tris;
        uint16_t *info;
        uint32_t *surf;
        bg_waterbox_t *water;
        bg_camera_t *cam;
        int16_t *vec;

        if (!kbg2_layout(file, length, &l)) return false;
        need = native_bytes(&l, &o_info, &o_surf, &o_water, &o_cam, &o_vec);
        if (!dest || dest_bytes < need) return false;
        tris = (collision_triangle_t *)out;
        info = (uint16_t *)(out + o_info);
        surf = (uint32_t *)(out + o_surf);
        water = (bg_waterbox_t *)(out + o_water);
        cam = (bg_camera_t *)(out + o_cam);
        vec = (int16_t *)(out + o_vec);
        for (i = 0; i < l.tris; i++) {
                int16_t *v = &tris[i].vertex[0][0];
                const uint8_t *p = file + l.o_tris + i * 36;
                for (k = 0; k < 18; k++) v[k] = (int16_t)be16(p + k * 2);
                info[i] = (uint16_t)be16(file + l.o_info + i * 2);
                if ((info[i] & 0xFF) >= l.surfaces && l.surfaces) return false;
        }
        for (i = 0; i < l.surfaces * 2; i++) surf[i] = be32(file + l.o_surf + i * 4);
        for (i = 0; i < l.water; i++) {
                const uint8_t *p = file + l.o_water + i * 16;
                water[i].x_min = (int16_t)be16(p);
                water[i].y_surface = (int16_t)be16(p + 2);
                water[i].z_min = (int16_t)be16(p + 4);
                water[i].x_length = (int16_t)be16(p + 6);
                water[i].z_length = (int16_t)be16(p + 8);
                water[i].properties = be32(p + 12);
        }
        for (i = 0; i < l.cameras; i++) {
                const uint8_t *p = file + l.o_cam + i * 8;
                cam[i].setting = (uint16_t)be16(p);
                cam[i].count = (int16_t)be16(p + 2);
                cam[i].first = be32(p + 4);
                if (cam[i].count > 0 && (cam[i].first > l.vectors ||
                    (uint32_t)cam[i].count > l.vectors - cam[i].first)) return false;
        }
        for (i = 0; i < l.vectors * 3; i++) vec[i] = (int16_t)be16(file + l.o_vec + i * 2);
        mesh->triangles = tris; mesh->triangle_count = l.tris;
        mesh->info = info;
        mesh->surfaces = surf; mesh->surface_count = l.surfaces;
        mesh->water = water; mesh->water_count = l.water;
        mesh->cameras = cam; mesh->camera_count = l.cameras;
        mesh->camera_vectors = vec; mesh->camera_vector_count = l.vectors;
        return true;
}

/* ---- DynaPoly ---- */

/* sin(i * 90 / 64 degrees) in Q14, i = 0..64: a quarter wave in 256-binang
 * steps, linearly interpolated. Exact on host and SH-2 alike. */
static const int16_t sine_q14[65] = {
            0,   402,   804,  1205,  1606,  2006,  2404,  2801,  3196,  3590,
         3981,  4370,  4756,  5139,  5520,  5897,  6270,  6639,  7005,  7366,
         7723,  8076,  8423,  8765,  9102,  9434,  9760, 10080, 10394, 10702,
        11003, 11297, 11585, 11866, 12140, 12406, 12665, 12916, 13160, 13395,
        13623, 13842, 14053, 14256, 14449, 14635, 14811, 14978, 15137, 15286,
        15426, 15557, 15679, 15791, 15893, 15986, 16069, 16143, 16207, 16261,
        16305, 16340, 16364, 16379, 16384,
};

static int32_t sin_q14(uint16_t angle)
{
        uint32_t quadrant = angle >> 14, index = (angle >> 8) & 63, frac = angle & 255;
        int32_t a, b;
        if (quadrant & 1) {             /* descending quarter: mirror */
                a = sine_q14[64 - index];
                b = sine_q14[63 - index];
        } else {
                a = sine_q14[index];
                b = sine_q14[index + 1];
        }
        a += (b - a) * (int32_t)frac / 256;
        return quadrant & 2 ? -a : a;
}

static int32_t cos_q14(uint16_t angle)
{
        return sin_q14((uint16_t)(angle + 0x4000));
}

/* Current transform becomes the previous one, for one slot. */
static void dyna_snapshot(dyna_slot_t *d)
{
        d->prev_pos[0] = d->pos[0];
        d->prev_pos[1] = d->pos[1];
        d->prev_pos[2] = d->pos[2];
        d->prev_rot_y = d->rot_y;
        d->prev_scale_q16 = d->scale_q16;
}

void bg_dyna_init(void *buffer, uint32_t bytes)
{
        dyna_world = (collision_triangle_t *)buffer;
        dyna_capacity = buffer ? bytes / sizeof(collision_triangle_t) : 0;
        bg_dyna_clear();
}

void bg_dyna_clear(void)
{
        uint32_t i;
        for (i = 0; i < BG_DYNA_MAX; i++) dyna[i].used = 0;
}

uint32_t bg_dyna_triangles_used(void)
{
        uint32_t i, n = 0;
        for (i = 0; i < BG_DYNA_MAX; i++) if (dyna[i].used) n += dyna[i].count;
        return n;
}

/* First gap of `count` triangles between live slots' ranges. */
static bool dyna_alloc(uint32_t count, uint32_t *first)
{
        uint32_t start = 0, i;
        bool moved = true;
        while (moved) {
                moved = false;
                for (i = 0; i < BG_DYNA_MAX; i++) {
                        if (!dyna[i].used) continue;
                        if (start < (uint32_t)dyna[i].first + dyna[i].count &&
                            dyna[i].first < start + count) {
                                start = (uint32_t)dyna[i].first + dyna[i].count;
                                moved = true;
                        }
                }
        }
        if (start + count > dyna_capacity) return false;
        *first = start;
        return true;
}

uint32_t bg_dyna_register(const bg_mesh_t *mesh, uint32_t transform)
{
        uint32_t id, first;
        bg_vec_t origin = {0, 0, 0};
        if (!mesh || !mesh->triangle_count || mesh->triangle_count > 0xFFFF) return BG_NONE;
        for (id = 0; id < BG_DYNA_MAX; id++) if (!dyna[id].used) break;
        if (id == BG_DYNA_MAX || !dyna_alloc(mesh->triangle_count, &first)) return BG_NONE;
        dyna[id].mesh = mesh;
        dyna[id].first = (uint16_t)first;
        dyna[id].count = (uint16_t)mesh->triangle_count;
        dyna[id].used = 1;
        dyna[id].enabled = 1;
        dyna[id].transform = (uint8_t)transform;
        dyna[id].rot_y = 0;
        bg_dyna_set(id, &origin, 0, 65536);
        /* Only this slot starts with previous == current. A global
         * bg_dyna_step here would erase other platforms' motion this step. */
        dyna_snapshot(&dyna[id]);
        return id;
}

void bg_dyna_set(uint32_t id, const bg_vec_t *pos, uint16_t rot_y, int32_t scale_q16)
{
        dyna_slot_t *d;
        uint32_t i, k;
        int32_t s, c;
        if (id >= BG_DYNA_MAX || !dyna[id].used) return;
        d = &dyna[id];
        d->pos[0] = pos->x; d->pos[1] = pos->y; d->pos[2] = pos->z;
        d->rot_y = rot_y;
        d->scale_q16 = scale_q16;
        s = sin_q14(rot_y);
        c = cos_q14(rot_y);
        for (i = 0; i < d->count; i++) {
                const collision_triangle_t *src = &d->mesh->triangles[i];
                collision_triangle_t *dst = &dyna_world[d->first + i];
                for (k = 0; k < 3; k++) {
                        /* Scale, then Y rotation [c 0 s; 0 1 0; -s 0 c], then move. */
                        int32_t x = (int32_t)((int64_t)src->vertex[k][0] * scale_q16 / 65536);
                        int32_t y = (int32_t)((int64_t)src->vertex[k][1] * scale_q16 / 65536);
                        int32_t z = (int32_t)((int64_t)src->vertex[k][2] * scale_q16 / 65536);
                        dst->vertex[k][0] = (int16_t)(pos->x + (x * c + z * s) / 16384);
                        dst->vertex[k][1] = (int16_t)(pos->y + y);
                        dst->vertex[k][2] = (int16_t)(pos->z + (z * c - x * s) / 16384);
                }
                dst->normal[0] = (int16_t)((src->normal[0] * c + src->normal[2] * s) / 16384);
                dst->normal[1] = src->normal[1];
                dst->normal[2] = (int16_t)((src->normal[2] * c - src->normal[0] * s) / 16384);
                for (k = 0; k < 3; k++) {
                        int16_t lo = dst->vertex[0][k], hi = lo;
                        if (dst->vertex[1][k] < lo) lo = dst->vertex[1][k];
                        if (dst->vertex[2][k] < lo) lo = dst->vertex[2][k];
                        if (dst->vertex[1][k] > hi) hi = dst->vertex[1][k];
                        if (dst->vertex[2][k] > hi) hi = dst->vertex[2][k];
                        dst->minimum[k] = lo;
                        dst->maximum[k] = hi;
                }
        }
}

void bg_dyna_enable(uint32_t id, bool enabled)
{
        if (id < BG_DYNA_MAX) dyna[id].enabled = enabled ? 1 : 0;
}

void bg_dyna_remove(uint32_t id)
{
        if (id < BG_DYNA_MAX) dyna[id].used = 0;
}

void bg_dyna_step(void)
{
        uint32_t i;
        for (i = 0; i < BG_DYNA_MAX; i++)
                if (dyna[i].used) dyna_snapshot(&dyna[i]);
}

/* DynaPolyActor_TransformCarriedActor (z_bg_collect.c). The two transform
 * flags act independently:
 *   POS    position = cur * inverse(prev) * position, i.e. the rider follows
 *          the mesh's translation, Y rotation and scale since bg_dyna_step
 *          (DynaPolyActor_UpdateCarriedActorPos). A zero previous scale
 *          cannot be inverted, so the position is left alone, as source.
 *   ROT_Y  facing += cur.rot.y - prev.rot.y (UpdateCarriedActorRotY); the
 *          position is not touched by this flag.
 * True when either flag applied, as the source returns. A removed slot, and
 * a disabled one (it cannot be stood on), carries nothing. */
bool bg_dyna_carry(uint32_t id, bg_vec_t *pos, uint16_t *yaw)
{
        dyna_slot_t *d;
        uint16_t turn;
        bool result = false;
        if (id >= BG_DYNA_MAX || !dyna[id].used || !dyna[id].enabled) return false;
        d = &dyna[id];
        turn = (uint16_t)(d->rot_y - d->prev_rot_y);
        if (d->transform & BG_DYNA_POS) {
                if (d->prev_scale_q16) {
                        int64_t rx = pos->x - d->prev_pos[0];
                        int64_t ry = pos->y - d->prev_pos[1];
                        int64_t rz = pos->z - d->prev_pos[2];
                        int64_t s = sin_q14(turn), c = cos_q14(turn);
                        int64_t den = (int64_t)16384 * d->prev_scale_q16;
                        /* R(cur) R(-prev) = R(cur - prev) about the one axis;
                         * then the scale ratio cur / prev. */
                        pos->x = d->pos[0] + (int32_t)((rx * c + rz * s) * d->scale_q16 / den);
                        pos->y = d->pos[1] + (int32_t)(ry * d->scale_q16 / d->prev_scale_q16);
                        pos->z = d->pos[2] + (int32_t)((rz * c - rx * s) * d->scale_q16 / den);
                }
                result = true;
        }
        if (d->transform & BG_DYNA_ROT_Y) {
                if (yaw) *yaw = (uint16_t)(*yaw + turn);
                result = true;
        }
        return result;
}
