"""Decomp DynaPoly actors -> C bg_dyna bridge (oot_core_host.c core_dyna_*)."""
import unittest
from pathlib import Path

import test_graphics_backend as graphics

ROOT = Path(__file__).resolve().parents[1]
HOST = ROOT / 'src/oot_core_host.c'


class CoreDyna(graphics.GraphicsBackend):
    def test_convert_register_transform_and_remove(self):
        source = r'''
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
typedef struct { int32_t x, y, z; } bg_vec_t;
typedef struct { int16_t vertex[3][3], normal[3], minimum[3], maximum[3]; } collision_triangle_t;
typedef struct {
    const collision_triangle_t *triangles; uint32_t triangle_count; const uint16_t *info;
    const uint32_t *surfaces; uint32_t surface_count; const void *water; uint32_t water_count;
    const void *cameras; uint32_t camera_count; const int16_t *camera_vectors; uint32_t camera_vector_count;
} bg_mesh_t;
#define BG_NONE 0xFF
#define BG_DYNA_POS 1
#define BG_DYNA_ROT_Y 2
#define OOT_CORE_DYNA_VIEWS_MAX 16
typedef struct {
    unsigned int key; const short *vertices; const unsigned short *polys; const unsigned int *surfaces;
    unsigned short num_vertices, num_polys; int x, y, z; unsigned short rot_y;
    unsigned char transform, enabled; int scale_q16;
} OotCoreDynaView;
static const bg_mesh_t *registered; static uint32_t reg_transform, removed = BG_NONE;
static uint32_t next_id=3,registered_id;
static bool registry_live;
static unsigned remove_calls,free_calls;
static bg_vec_t at; static uint16_t at_rot; static int32_t at_scale; static bool at_enabled;
static uint32_t bg_dyna_register(const bg_mesh_t *m, uint32_t t) {
    assert(!registry_live); registry_live=true;
    registered = m; reg_transform = t; registered_id=next_id; return next_id;
}
static void bg_dyna_remove(uint32_t id) {
    assert(registry_live && id==registered_id);
    registry_live=false; removed=id; ++remove_calls;
}
static void bg_dyna_set(uint32_t id, const bg_vec_t *p, uint16_t r, int32_t s) { assert(registry_live && id == registered_id); at = *p; at_rot = r; at_scale = s; }
static void bg_dyna_enable(uint32_t id, bool e) { assert(registry_live && id == registered_id); at_enabled = e; }
#define jo_malloc malloc
static void jo_free(void *p) {
    assert(!registry_live && p==registered->triangles); /* unregister BEFORE free */
    ++free_calls; free(p);
}
static OotCoreDynaView views[1]; static int view_count;
static struct { int (*dyna_view)(const OotCoreDynaView **); } entry;
static int dyna_view(const OotCoreDynaView **out) { *out = views; return view_count; }
#define ENTRY (&entry)
''' + graphics.function(HOST, 'typedef struct {\n    unsigned int key;\n    uint32_t id;') + ''' core_dyna_t;
static core_dyna_t core_dyna[OOT_CORE_DYNA_VIEWS_MAX];
''' + '\n'.join(graphics.function(HOST, m) for m in (
            'static void core_dyna_drop(', 'static void core_dyna_reset(',
            'static int16_t q15_to_q14(', 'static bool core_dyna_add(', 'static void core_dyna_sync(')) + r'''
int main(void) {
    static const short vtx[] = { 0,0,0, 100,0,0, 0,0,100 };
    /* type 5 (surface), flags_vIA ignore bits 1, vIB conveyor bit, vIC, normal (0,32767,-3) */
    static const unsigned short poly[] = { 5, 0 | (1u << 13), 2 | (1u << 13), 1,
                                           0, 32767, (unsigned short)-3, 0 };
    static const unsigned int surf[] = { 1,2, 3,4, 5,6, 7,8, 9,10, 11,12 };
    entry.dyna_view = dyna_view;
    views[0] = (OotCoreDynaView){ 0x1234, vtx, poly, surf, 3, 1, 10, 20, 30, 0x4000, 1, 1, 6553 };
    view_count = 1;
    core_dyna_sync();
    assert(registered && registered->triangle_count == 1 && reg_transform == BG_DYNA_POS);
    const collision_triangle_t *t = registered->triangles;
    assert(t->vertex[1][2] == 100 && t->vertex[2][0] == 100);       /* vIB = 2, vIC = 1 */
    assert(t->normal[0] == 0 && t->normal[1] == 16384 && t->normal[2] == -2);
    assert(t->minimum[0] == 0 && t->maximum[0] == 100 && t->maximum[2] == 100);
    assert(registered->info[0] == (5 | (1 << 8) | (1 << 11)) && registered->surface_count == 6);
    assert(at.x == 10 && at.y == 20 && at.z == 30 && at_rot == 0x4000 && at_scale == 6553 && at_enabled);
    views[0].enabled = 0; views[0].x = 11;
    core_dyna_sync();
    assert(!at_enabled && at.x == 11 && removed == BG_NONE);       /* same actor: no re-register */
    view_count = 0;
    core_dyna_sync();
    assert(removed == 3 && remove_calls==1 && free_calls==1);          /* actor gone */
    removed = BG_NONE; view_count = 1; next_id=0;                     /* slot zero is valid */
    core_dyna_sync();
    assert(registry_live && core_dyna[0].id==0);
    core_dyna_reset();                                               /* frontend may precede collision reset */
    assert(removed == 0 && !registry_live && remove_calls==2 && free_calls==2);
    assert(!core_dyna[0].key && !core_dyna[0].tri);
    core_dyna_reset(); core_dyna_reset();
    assert(remove_calls==2 && free_calls==2);                         /* no stale unregister or double free */
    return 0;
}
'''
        self.run_c(source)


if __name__ == '__main__':
    unittest.main()
