/* Static ROM collision, independent of rendering and controller APIs. */
#include "kokiri_collision.h"
#include <limits.h>

#define RADIUS 24
#define EYE_HEIGHT 90
#define STEP 4
static const collision_triangle_t *triangles;
static uint32_t triangle_count;

void kokiri_collision_init(const collision_triangle_t *data, uint32_t count)
{
        triangles = data;
        triangle_count = count;
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

bool kokiri_collision_clear(camera_position_t position)
{
        const int32_t p[3] = {position.x, position.y, position.z};
        for (uint32_t i = 0; i < triangle_count; i++) {
                const collision_triangle_t *t = &triangles[i];
                bool outside = false;
                for (int k = 0; k < 3; k++) outside |= p[k] < t->minimum[k]-RADIUS || p[k] > t->maximum[k]+RADIUS;
                if (outside) continue;
                int64_t dot = 0;
                for (int k = 0; k < 3; k++) dot += (int64_t)(p[k]-t->vertex[0][k])*t->normal[k];
                if (dot > RADIUS*16384 || dot < -RADIUS*16384) continue;
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
                        if (distance <= RADIUS*RADIUS) return false;
                }
        }
        return true;
}

bool kokiri_collision_floor(int32_t x, int32_t z, int32_t below, int32_t *height)
{
        int32_t best = INT32_MIN;
        for (uint32_t i = 0; i < triangle_count; i++) {
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
                if (kokiri_collision_floor(next.x,next.z,position->y-RADIUS,&floor) && next.y < floor+EYE_HEIGHT)
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
