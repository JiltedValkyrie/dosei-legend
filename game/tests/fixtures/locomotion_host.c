/* Host-only adapters: exercise the real controller and animation state code. */
#include <math.h>
#include "kokiri_camera.h"
#include "../../src/input_edge.h"

static input_edge_t test_edge;
void edge_reset(void) { test_edge = (input_edge_t){0}; }
void edge_sample(bool held) { input_edge_sample(&test_edge, held); }
int edge_consume(void) { return input_edge_consume(&test_edge); }

void kokiri_camera_sincos(uint16_t yaw, int32_t *sine, int32_t *cosine)
{
    double radians = yaw * 6.283185307179586 / 65536.0;
    *sine = (int32_t)(sin(radians) * 65536);
    *cosine = (int32_t)(cos(radians) * 65536);
}

void kokiri_collision_move_actor(camera_position_t *p, int32_t x,
                                 int32_t y, int32_t z)
{
    p->x += x; p->y += y; p->z += z;
}

void kokiri_collision_move(camera_position_t *p, int32_t x,
                           int32_t y, int32_t z)
{
    kokiri_collision_move_actor(p, x, y, z);
}
