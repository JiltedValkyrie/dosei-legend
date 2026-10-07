/*
 * One dyna/rider scenario written only against the bg_* API. Built twice:
 * with shared/lib/collision/kokiri_collision.c (C reference) and with
 * src/bg_core_shim.c over the real core (oot_core_bg.cpp). Rows go to stdout;
 * compare_bg_shim.py diffs them. Covers a flat platform, a ramp rotated 45
 * degrees, a box rotated 30 degrees, floor/wall/line/ceiling queries on them,
 * a rider carried over moving + turning frames, disable/enable, removal and
 * slot reuse. scene_init() (per build) loads Kokiri Forest.
 */
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>

#include "kokiri_collision.h"

void scene_init(const char *col_file);   /* per build */
void scene_reenter(const char *col_file); /* per build: exit + load again */

static collision_triangle_t tri(int ax, int ay, int az, int bx, int by, int bz, int cx, int cy, int cz)
{
        collision_triangle_t t;
        int i;
        int16_t v[3][3] = { { ax, ay, az }, { bx, by, bz }, { cx, cy, cz } };
        memset(&t, 0, sizeof t);
        memcpy(t.vertex, v, sizeof v);
        /* C library reads the normal/bounds from the mesh; compute them. */
        {
                int ux = bx - ax, uy = by - ay, uz = bz - az, wx = cx - ax, wy = cy - ay, wz = cz - az;
                long nx = (long)uy * wz - (long)uz * wy, ny = (long)uz * wx - (long)ux * wz,
                     nz = (long)ux * wy - (long)uy * wx;
                double m = 0;
                m = nx * (double)nx + ny * (double)ny + nz * (double)nz;
                {
                        double s = 1.0, r = m;
                        /* sqrt without libm: Newton */
                        if (r > 0) { s = r; for (i = 0; i < 40; i++) s = 0.5 * (s + r / s); }
                        t.normal[0] = (int16_t)(nx * 16384.0 / s);
                        t.normal[1] = (int16_t)(ny * 16384.0 / s);
                        t.normal[2] = (int16_t)(nz * 16384.0 / s);
                }
        }
        for (i = 0; i < 3; i++) {
                int16_t a = v[0][i], b = v[1][i], c = v[2][i];
                t.minimum[i] = a < b ? (a < c ? a : c) : (b < c ? b : c);
                t.maximum[i] = a > b ? (a > c ? a : c) : (b > c ? b : c);
        }
        return t;
}

static collision_triangle_t plat_t[2], ramp_t[2], box_t[12], late_t[2];
static uint16_t plat_i[2] = { 0, 0 }, ramp_i[2] = { 1, 1 }, box_i[12], late_i[2] = { 0, 0 };
static uint32_t plat_s[2] = { 0x01000000u, 0x11 }, ramp_s[4] = { 0, 0, 0x02000000u, 0x22 },
                box_s[2] = { 0x00200000u, 0x33 }, late_s[2] = { 0x03000000u, 0x44 };

static bg_mesh_t mesh(collision_triangle_t *t, uint32_t n, const uint16_t *info, const uint32_t *s, uint32_t ns)
{
        bg_mesh_t m;
        memset(&m, 0, sizeof m);
        m.triangles = t; m.triangle_count = n; m.info = info; m.surfaces = s; m.surface_count = ns;
        return m;
}

static void build(void)
{
        int i;
        /* Flat 300x300 square, up-facing (winding: (0,0,300)x(300,0,0) = +y). */
        plat_t[0] = tri(0, 0, 0, 0, 0, 300, 300, 0, 0);
        plat_t[1] = tri(300, 0, 0, 0, 0, 300, 300, 0, 300);
        /* Ramp: rises 100 over 300 along +x. */
        ramp_t[0] = tri(0, 0, 0, 0, 0, 300, 300, 100, 0);
        ramp_t[1] = tri(300, 100, 0, 0, 0, 300, 300, 100, 300);
        /* Box 100 cube: 6 faces x 2, outward normals. */
        {
                static const int f[12][9] = {
                        { 0,100,0, 0,100,100, 100,100,0 }, { 100,100,0, 0,100,100, 100,100,100 },      /* top */
                        { 0,0,0, 100,0,0, 0,0,100 }, { 100,0,0, 100,0,100, 0,0,100 },                  /* bottom */
                        { 0,0,0, 0,100,0, 100,0,0 }, { 100,0,0, 0,100,0, 100,100,0 },                  /* -z */
                        { 0,0,100, 100,0,100, 0,100,100 }, { 100,0,100, 100,100,100, 0,100,100 },      /* +z */
                        { 0,0,0, 0,0,100, 0,100,0 }, { 0,0,100, 0,100,100, 0,100,0 },                  /* -x */
                        { 100,0,0, 100,100,0, 100,0,100 }, { 100,0,100, 100,100,0, 100,100,100 },      /* +x */
                };
                for (i = 0; i < 12; i++) {
                        box_t[i] = tri(f[i][0], f[i][1], f[i][2], f[i][3], f[i][4], f[i][5], f[i][6], f[i][7], f[i][8]);
                        box_i[i] = 0;
                }
        }
        late_t[0] = plat_t[0];
        late_t[1] = plat_t[1];
}

static void floor_row(const char *tag, int x, int y, int z)
{
        bg_vec_t p = { x, y, z };
        bg_hit_t h;
        int32_t fy;
        memset(&h, 0, sizeof h);
        fy = bg_floor(&p, BG_IGNORE_ENTITY, &h);
        printf("F %s %d %d %d | %d %u %u %x %x\n", tag, x, y, z, fy, h.bg_id, h.poly,
               (unsigned)h.data0, (unsigned)h.data1);
}

int main(int argc, char **argv)
{
        bg_mesh_t pm, rm, bm, lm;
        uint32_t P, R, B, L;
        bg_vec_t at;
        int i;
        static uint8_t carve[512 * 36];
        scene_init(argv[1]);
        bg_dyna_init(carve, sizeof carve);
        build();
        pm = mesh(plat_t, 2, plat_i, plat_s, 1);
        rm = mesh(ramp_t, 2, ramp_i, ramp_s, 2);
        bm = mesh(box_t, 12, box_i, box_s, 1);
        lm = mesh(late_t, 2, late_i, late_s, 1);
        P = bg_dyna_register(&pm, BG_DYNA_POS | BG_DYNA_ROT_Y);
        R = bg_dyna_register(&rm, BG_DYNA_POS | BG_DYNA_ROT_Y);
        B = bg_dyna_register(&bm, BG_DYNA_POS | BG_DYNA_ROT_Y);
        printf("I ids %u %u %u | 0 0 0 0 0\n", P, R, B);
        at = (bg_vec_t){ 500, 2500, 500 };  bg_dyna_set(P, &at, 0, 65536);
        at = (bg_vec_t){ 1500, 2500, 500 }; bg_dyna_set(R, &at, 0x2000, 65536);   /* 45 degrees */
        at = (bg_vec_t){ 1000, 2500, 1500 }; bg_dyna_set(B, &at, 0x1555, 65536);  /* 30 degrees */
        bg_dyna_step();

        /* Floors on top of each object (local points rotated by hand below
         * would differ per build: sample a world grid around each instead). */
        for (i = 0; i < 25; i++) {
                int dx = (i % 5) * 60 + 20, dz = (i / 5) * 60 + 20;
                floor_row("plat", 500 + dx, 2700, 500 + dz);
                floor_row("ramp", 1500 + dx - 150, 2700, 500 + dz);
                floor_row("box", 1000 + dx / 3, 2700, 1500 + dz / 3);
        }
        /* Where is the rotated box? 9x9 scan around its pivot. */
        for (i = 0; i < 81; i++)
                floor_row("boxscan", 1000 + (i % 9) * 25 - 100, 2700, 1500 + (i / 9) * 25 - 100);
        /* Wall into the box side, line through the ramp, ceiling under platform. */
        {
                bg_vec_t prev = { 900, 2510, 1550 }, next = { 1010, 2510, 1550 }, res;
                bg_hit_t h;
                int32_t cy;
                memset(&h, 0, sizeof h);
                bool w = bg_wall(&res, &next, &prev, 20, 26, BG_IGNORE_ENTITY, false, &h);
                printf("W box %d %d %d | %d %d %d %u %u\n", next.x, next.y, next.z, w, res.x, res.z, h.bg_id, h.poly);
                bg_vec_t a = { 1300, 2550, 650 }, b = { 1800, 2550, 650 }, cross;
                memset(&h, 0, sizeof h);
                bool l = bg_line(&a, &b, &cross, BG_CHECK_ALL, BG_IGNORE_ENTITY, &h);
                printf("L ramp 0 0 0 | %d %d %d %d %u %u\n", l, l ? cross.x : 0, l ? cross.y : 0, l ? cross.z : 0,
                       h.bg_id, h.poly);
                bg_vec_t under = { 650, 2440, 650 };
                memset(&h, 0, sizeof h);
                bool c = bg_ceiling(&cy, &under, 80, BG_IGNORE_ENTITY, &h);
                printf("C plat 0 0 0 | %d %d %u %u\n", c, c ? cy : 0, h.bg_id, h.poly);
        }

        /* Rider: stands on the platform; platform moves and turns 10 frames. */
        {
                bg_vec_t rider = { 650, 2500, 600 };
                uint16_t yaw = 0x1000;
                bg_vec_t pos = { 500, 2500, 500 };
                uint16_t rot = 0;
                for (i = 0; i < 10; i++) {
                        bg_dyna_step();
                        pos.x += 7; pos.y += 3; pos.z -= 5; rot += 0x200;
                        bg_dyna_set(P, &pos, rot, 65536);
                        bg_dyna_carry(P, &rider, &yaw);
                        printf("R frame%d 0 0 0 | %d %d %d %u\n", i, rider.x, rider.y, rider.z, yaw);
                }
                floor_row("rider", rider.x, rider.y + 50, rider.z);
        }

        /* Disable/enable the box, remove the platform, reuse its slot. */
        bg_dyna_enable(B, false);
        floor_row("box-off", 1030, 2700, 1530);
        bg_dyna_enable(B, true);
        floor_row("box-on", 1030, 2700, 1530);
        bg_dyna_remove(P);
        floor_row("plat-gone", 650, 2700, 650);
        L = bg_dyna_register(&lm, BG_DYNA_POS);
        at = (bg_vec_t){ 2500, 2600, 500 };
        bg_dyna_set(L, &at, 0, 65536);
        bg_dyna_step();
        printf("I reuse %u %u 0 | 0 0 0 0 0\n", L, P);
        floor_row("late", 2650, 2800, 650);
        floor_row("plat-still-gone", 650, 2700, 650);

        /* Water level bookkeeping, then scene exit + re-entry: proxies, ids
         * and raised water must all be gone, new registrations start fresh. */
        {
                const bg_mesh_t *m = bg_scene_mesh();
                int32_t s = 0;
                if (m && m->water_count) {
                        bg_waterbox_t w = m->water[0];
                        int32_t wx = w.x_min + w.x_length / 2, wz = w.z_min + w.z_length / 2;
                        uint32_t room = BG_WATERBOX_ROOM(w.properties);
                        bool got = bg_water_surface(wx, wz, room, &s, 0);
                        printf("Q water-authored %d %d %u | %d %d\n", wx, wz, room, got, s);
                        bg_water_set_surface(0, w.y_surface + 77);
                        got = bg_water_surface(wx, wz, room, &s, 0);
                        printf("Q water-raised %d %d %u | %d %d\n", wx, wz, room, got, s);
                        scene_reenter(argv[1]);
                        got = bg_water_surface(wx, wz, room, &s, 0);
                        printf("Q water-after-reentry %d %d %u | %d %d\n", wx, wz, room, got, s);
                } else {
                        printf("Q water-none 0 0 0 | 0 0\n");
                        scene_reenter(argv[1]);
                }
        }
        floor_row("box-after-reentry", 1030, 2700, 1530);
        floor_row("late-after-reentry", 2650, 2800, 650);
        L = bg_dyna_register(&lm, BG_DYNA_POS);
        at = (bg_vec_t){ 2500, 2600, 500 };
        bg_dyna_set(L, &at, 0, 65536);
        bg_dyna_step();
        printf("I reentry %u 0 0 | 0 0 0 0 0\n", L);
        floor_row("late-fresh", 2650, 2800, 650);
        printf("Q tris-used 0 0 0 | %u 0\n", bg_dyna_triangles_used());
        return 0;
}
