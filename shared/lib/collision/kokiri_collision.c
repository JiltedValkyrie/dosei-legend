/* Static ROM collision, independent of rendering and controller APIs. */
#include "kokiri_collision.h"
#include <limits.h>

#define RADIUS 24
#define EYE_HEIGHT 90
#define STEP 4
/* OoT child Link checks walls at y=26 with radius 14 and checks ceilings up
 * to y=40. One sphere with those dimensions reproduces both limits here and
 * avoids treating low overhead floors as if the old eye-camera hit them. */
#define ACTOR_RADIUS 14
#define ACTOR_CHECK_HEIGHT 26
/* OoT preserves BGCHECKFLAG_GROUND while the floor is no more than 11 units
 * below the actor. Follow that nearby floor directly so descending a ramp
 * does not alternate between airborne gravity and landing every few frames. */
#define ACTOR_GROUND_FOLLOW_DROP 11
/* OoT normally gives Link gravity -1 and a terminal velocity of -20 per
 * 20 Hz update. These Q8 values preserve the same acceleration and terminal
 * speed at this viewer's 30 Hz gameplay rate. */
#define GRAVITY_Q8 (-114)
#define TERMINAL_VELOCITY_Q8 (-3413)
static const collision_triangle_t *triangles;
static uint32_t triangle_count;

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

void kokiri_collision_init(const collision_triangle_t *data, uint32_t count)
{
        triangles = data;
        triangle_count = count;
        grid_ready = false;
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

static bool collision_clear_radius(camera_position_t position, int32_t radius)
{
        const int32_t p[3] = {position.x, position.y, position.z};
        uint32_t cx0, cx1, cz0, cz1, cx, cz, slot, end, i;
        const bool indexed = candidate_span(p[0] - radius, p[0] + radius,
                p[2] - radius, p[2] + radius, &cx0, &cx1, &cz0, &cz1) != 0;
        for (cz = cz0; cz <= cz1; cz++)
        for (cx = cx0; cx <= cx1; cx++) {
        slot = indexed ? grid_offset[cz * GRID_DIM + cx] : 0;
        end = indexed ? grid_offset[cz * GRID_DIM + cx + 1] : triangle_count;
        for (; slot < end; slot++) {
                i = indexed ? grid_list[slot] : slot;
                const collision_triangle_t *t = &triangles[i];
                bool outside = false;
                for (int k = 0; k < 3; k++) outside |= p[k] < t->minimum[k]-radius || p[k] > t->maximum[k]+radius;
                if (outside) continue;
                int64_t dot = 0;
                for (int k = 0; k < 3; k++) dot += (int64_t)(p[k]-t->vertex[0][k])*t->normal[k];
                if (dot > radius*16384 || dot < -radius*16384) continue;
                int32_t projected[3];
                for (int k = 0; k < 3; k++) projected[k] = p[k] - (int32_t)(dot*t->normal[k]/268435456);
                if (inside(t, projected)) return false;
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
                        if (distance <= radius*radius) return false;
                }
        }
        }
        return true;
}

bool kokiri_collision_clear(camera_position_t position)
{
        return collision_clear_radius(position, RADIUS);
}

static bool actor_clear(camera_position_t position)
{
        position.y += ACTOR_CHECK_HEIGHT - EYE_HEIGHT;
        return collision_clear_radius(position, ACTOR_RADIUS);
}

bool kokiri_collision_floor(int32_t x, int32_t z, int32_t below, int32_t *height)
{
        int32_t best = INT32_MIN;
        uint32_t cx0, cx1, cz0, cz1, slot, end, i;
        const bool indexed = candidate_span(x, x, z, z, &cx0, &cx1, &cz0, &cz1) != 0;
        slot = indexed ? grid_offset[cz0 * GRID_DIM + cx0] : 0;
        end = indexed ? grid_offset[cz0 * GRID_DIM + cx0 + 1] : triangle_count;
        (void)cx1; (void)cz1;
        for (; slot < end; slot++) {
                i = indexed ? grid_list[slot] : slot;
                const collision_triangle_t *t = &triangles[i];
                if (t->normal[1] < 8192 || x < t->minimum[0] || x > t->maximum[0] ||
                    z < t->minimum[2] || z > t->maximum[2]) continue;
                int32_t y = t->vertex[0][1] - (int32_t)(((int64_t)t->normal[0]*(x-t->vertex[0][0]) +
                    (int64_t)t->normal[2]*(z-t->vertex[0][2]))/t->normal[1]);
                int32_t p[3] = {x,y,z};
                if (y <= below && y > best && inside(t,p)) best = y;
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

void kokiri_collision_move_actor(camera_position_t *position, int32_t dx,
        int32_t dy, int32_t dz)
{
        int32_t floor;
        bool follow_ground = false;

        if (!(dx || dy || dz)) return;
        if ((dx || dz) &&
            kokiri_collision_floor(position->x, position->z,
                                   position->y - EYE_HEIGHT + STEP, &floor) &&
            position->y == floor + EYE_HEIGHT)
                follow_ground = true;

        move_axis(position,0,dx,true);
        if (follow_ground &&
            kokiri_collision_floor(position->x, position->z,
                                   position->y - EYE_HEIGHT, &floor) &&
            position->y - (floor + EYE_HEIGHT) <= ACTOR_GROUND_FOLLOW_DROP)
                position->y = floor + EYE_HEIGHT;

        move_axis(position,2,dz,true);
        if (follow_ground &&
            kokiri_collision_floor(position->x, position->z,
                                   position->y - EYE_HEIGHT, &floor) &&
            position->y - (floor + EYE_HEIGHT) <= ACTOR_GROUND_FOLLOW_DROP)
                position->y = floor + EYE_HEIGHT;

        move_axis(position,1,dy,true);
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
                if (position->y == target_y) {
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
        if (amount) kokiri_collision_move_actor(position, 0, amount, 0);

        below = position->y - EYE_HEIGHT + STEP;
        if (kokiri_collision_floor(position->x, position->z, below, &floor) &&
            position->y == floor + EYE_HEIGHT) {
                position->y = floor + EYE_HEIGHT;
                *velocity_q8 = 0;
                *remainder_q8 = 0;
                return true;
        }
        return false;
}
