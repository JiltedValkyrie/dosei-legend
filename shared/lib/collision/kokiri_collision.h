#ifndef KOKIRI_COLLISION_H
#define KOKIRI_COLLISION_H
#include <stdbool.h>
#include <stdint.h>
typedef struct { int32_t x, y, z; } camera_position_t;
typedef struct {
        int16_t vertex[3][3], normal[3], minimum[3], maximum[3];
} collision_triangle_t;
void kokiri_collision_init(const collision_triangle_t *triangles, uint32_t count);
/* Optional: build an XZ lookup grid in the caller's buffer so the queries visit
 * only nearby triangles. Returns false (and leaves the original full scan in
 * place) if the buffer is too small or the set is too large to index. Call
 * after kokiri_collision_init(); the buffer must outlive the collision data. */
bool kokiri_collision_index(void *buffer, uint32_t bytes);
bool kokiri_collision_clear(camera_position_t position);
bool kokiri_collision_floor(int32_t x, int32_t z, int32_t below, int32_t *height);
bool kokiri_collision_spawn(camera_position_t *position);
void kokiri_collision_move(camera_position_t *position, int32_t dx, int32_t dy, int32_t dz);
/* Move child Link using OoT-sized scene checks rather than the taller free
 * camera sphere. Position remains the existing floor+EYE_HEIGHT anchor. */
void kokiri_collision_move_actor(camera_position_t *position, int32_t dx,
        int32_t dy, int32_t dz);
/* Apply one 30 Hz gravity step. Velocity and sub-unit motion use Q8 fixed
 * point so OoT's 20 Hz gravity can be time-scaled without losing precision.
 * Returns true while standing on a floor. */
bool kokiri_collision_fall(camera_position_t *position, int32_t *velocity_q8,
        int32_t *remainder_q8);
#endif
