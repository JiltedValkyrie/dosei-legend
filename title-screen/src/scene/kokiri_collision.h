#ifndef KOKIRI_COLLISION_H
#define KOKIRI_COLLISION_H
#include <stdbool.h>
#include <stdint.h>
typedef struct { int32_t x, y, z; } camera_position_t;
typedef struct {
        int16_t vertex[3][3], normal[3], minimum[3], maximum[3];
} collision_triangle_t;
void kokiri_collision_init(const collision_triangle_t *triangles, uint32_t count);
bool kokiri_collision_clear(camera_position_t position);
bool kokiri_collision_floor(int32_t x, int32_t z, int32_t below, int32_t *height);
bool kokiri_collision_spawn(camera_position_t *position);
void kokiri_collision_move(camera_position_t *position, int32_t dx, int32_t dy, int32_t dz);
#endif
