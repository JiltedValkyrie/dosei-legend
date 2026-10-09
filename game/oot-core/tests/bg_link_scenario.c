/*
 * C Link collision wrappers (kokiri_collision_floor/clear/spawn/move_actor/
 * fall/jump/move) on Kokiri Forest. Built twice: with
 * shared/lib/collision/kokiri_collision.c (C reference) and with
 * src/bg_core_link.c + src/bg_core_shim.c over the real core
 * (CORE_COLLISION). Rows to stdout; compare_bg_link.py classifies them.
 * scene_init() comes from bg_shim_scene_c.c / bg_shim_scene_core.cpp.
 */
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>

#include "kokiri_collision.h"

void scene_init(const char *col_file);

#define EYE 90

static void walk(int id, camera_position_t p, int dx, int dz, int steps)
{
        int32_t v = 0, r = 0;
        int i;
        for (i = 1; i <= steps; i++) {
                bool ground;
                kokiri_collision_actor_begin_step();
                kokiri_collision_move_actor(&p, dx, 0, dz);
                ground = kokiri_collision_fall(&p, &v, &r);
                if (i % 10 == 0)
                        printf("W %d %d %d %d %d %d\n", id, i, p.x, p.y - EYE, p.z, ground);
        }
}

int main(int argc, char **argv)
{
        static const int dir[8][2] = { { 6, 0 }, { 4, 4 }, { 0, 6 }, { -4, 4 },
                                       { -6, 0 }, { -4, -4 }, { 0, -6 }, { 4, -4 } };
        camera_position_t spawn;
        int x, z, id = 0;
        int32_t h;
#ifdef CORE_COLLISION
        /* Before the scene exists every query misses and nothing crashes. */
        {
                bg_vec_t a = { 0, 100, 0 }, b = { 0, 100, 40 }, res;
                bool floor = kokiri_collision_floor(0, 0, 200, &h);
                bool wall = bg_wall(&res, &b, &a, 14, 26, BG_IGNORE_ENTITY, false, 0);
                printf("G %d %d %d\n", floor, wall, res.z == 40);
        }
#endif
        scene_init(argc > 1 ? argv[1] : "");
        {
                bool got = kokiri_collision_spawn(&spawn);
                printf("S %d %d %d %d\n", got, spawn.x, spawn.y, spawn.z);
        }
        /* Floor contract: below-limited highest floor on a coarse grid. */
        for (z = -1600; z <= 1600; z += 160)
                for (x = -2400; x <= 1600; x += 160) {
                        int below;
                        for (below = 0; below <= 400; below += 200) {
                                bool got = kokiri_collision_floor(x, z, below, &h);
                                printf("F %d %d %d %d %d\n", x, z, below, got, got ? h : 0);
                        }
                }
        /* Camera sphere (radius 24, CAMERA ignore) above each found floor. */
        for (z = -1600; z <= 1600; z += 320)
                for (x = -2400; x <= 1600; x += 320) {
                        camera_position_t p = { x, 0, z };
                        if (!kokiri_collision_floor(x, z, 1000, &h)) continue;
                        p.y = h + EYE;
                        printf("C %d %d %d\n", x, z, kokiri_collision_clear(p));
                }
        /* Walks: 8 directions from floor points, wall slide + gravity. */
        for (z = -1200; z <= 1200; z += 400)
                for (x = -2000; x <= 1200; x += 400) {
                        camera_position_t p = { x, 0, z };
                        int d;
                        if (!kokiri_collision_floor(x, z, 600, &h)) continue;
                        p.y = h + EYE;
                        for (d = 0; d < 8; d++) walk(id++, p, dir[d][0], dir[d][1], 60);
                }
        /* Custom Y jump from spawn: rise, apex, land. */
        {
                camera_position_t p = spawn;
                int32_t v = 0, r = 0;
                int i;
                printf("J %d\n", kokiri_collision_jump(&p, &v, &r));
                for (i = 0; i < 30; i++) {
                        bool ground = kokiri_collision_fall(&p, &v, &r);
                        printf("Y %d %d %d\n", i, p.y - EYE, ground);
                }
        }
        /* Free camera move (raised eye after spawn). */
        {
                camera_position_t p = spawn;
                kokiri_collision_move(&p, 0, 24, 0);
                kokiri_collision_move(&p, 200, 0, 120);
                printf("M %d %d %d\n", p.x, p.y, p.z);
        }
        return 0;
}
