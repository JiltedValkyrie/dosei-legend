"""Execute production scene collision admission and buffer ownership changes."""
from pathlib import Path
import re
import unittest

import test_graphics_backend as graphics


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'src/scene_flow.c'


class SceneCollisionCapacity(unittest.TestCase):
    run_c = graphics.GraphicsBackend.run_c

    def run_collision(self, body):
        source = SOURCE.read_text()
        start = source.index('#define SCENE_COLLISION_MAX')
        end = re.search(r'static\s+bool\s+dyna_ready;', source).end()
        declarations = source[start:end]
        self.run_c(r'''
#include <assert.h>
#include <stdint.h>
#include <stdbool.h>
#include <stdlib.h>
#include <string.h>
''' + '#include "' + (ROOT.parent / 'shared/lib/collision/kokiri_collision.h').as_posix() + '"\n' +
            declarations + r'''
#define RAM_CART_DYNA_OFFSET 0x2000u
#define RAM_CART_DYNA_BYTES 0x4800u
typedef struct { void *p; unsigned bytes; bool alive; } allocation_t;
static allocation_t allocations[32];
static unsigned allocated, requests[32], request_count;
static unsigned required_bytes, decoded_triangles;
static unsigned published, resets, index_calls, dyna_inits, read_calls;
static int failure;
static bool fail_index, fail_index_alloc;
static unsigned char file_data[4], dyna_data[RAM_CART_DYNA_BYTES];
static bg_mesh_t bound;

static void *new_block(unsigned bytes) {
    assert(allocated < 32);
    unsigned char *p = malloc(bytes + 16);
    assert(p);
    memset(p, 0xa5, bytes);
    memset(p + bytes, 0xe7, 16);
    allocations[allocated++] = (allocation_t){p, bytes, true};
    return p;
}
static allocation_t *allocation(void *p) {
    for (unsigned i=0; i<allocated; ++i)
        if (allocations[i].p == p && allocations[i].alive) return &allocations[i];
    return 0;
}
static void *jo_malloc(unsigned bytes) {
    requests[request_count++] = bytes;
    if (failure == 6 || (fail_index_alloc && bytes == SCENE_COLLISION_INDEX_BYTES)) return 0;
    return new_block(bytes);
}
static void jo_free(void *p) {
    if (!p) return;
    assert(p != file_data); /* borrowed cart scratch is never heap-owned */
    allocation_t *a=allocation(p);
    assert(a && a->alive);
    /* Never release the geometry still visible to collision queries. */
    assert(bound.triangles != p);
    for (unsigned i=0; i<16; ++i) assert(((unsigned char *)p)[a->bytes+i] == 0xe7);
    a->alive=false;
    free(p);
}
static bool asset_scene_name(char *name, unsigned scene, int room, const char *ext) {
    assert(scene == 23 && room == -1 && !strcmp(ext,"COL"));
    strcpy(name,"Z23.COL");
    return failure != 1;
}
static const void *ram_cart_load_scratch(const char *name, int *length) {
    assert(!strcmp(name,"Z23.COL"));
    ++read_calls;
    if (failure == 2) return 0;
    *length=failure == 3 ? 0 : sizeof file_data;
    return file_data;
}
uint32_t bg_mesh_bytes(const uint8_t *data, uint32_t length) {
    assert(data == file_data && length == sizeof file_data);
    if (failure == 4) return 0;
    if (failure == 5) return SCENE_COLLISION_BYTES + 1u;
    return required_bytes;
}
bool bg_mesh_decode(const uint8_t *data, uint32_t length, void *dest,
                    uint32_t bytes, bg_mesh_t *mesh) {
    allocation_t *a=allocation(dest);
    assert(data == file_data && length == sizeof file_data);
    assert(a && a->bytes == required_bytes && bytes == required_bytes);
    /* Decoder can write before rejecting a corrupt file. The live scene
     * must retain its old data and descriptor throughout those writes. */
    assert(dest != bound.triangles && mesh != &collision_mesh);
    memset(dest,0xc3,bytes);
    memset(mesh,0,sizeof *mesh);
    mesh->triangles=dest;
    mesh->triangle_count=failure == 8 ? SCENE_COLLISION_MAX + 1u : decoded_triangles;
    return failure != 7;
}
void bg_scene_set(const bg_mesh_t *mesh) {
    assert(mesh == &collision_mesh);
    assert(mesh->triangles == collision_buffer && allocation(collision_buffer));
    assert(mesh->triangle_count == decoded_triangles);
    bound=*mesh;
    ++published;
}
static void *ram_cart_fixed(unsigned offset, unsigned bytes) {
    assert(offset == RAM_CART_DYNA_OFFSET && bytes == RAM_CART_DYNA_BYTES);
    return dyna_data;
}
void bg_dyna_init(void *data, uint32_t bytes) {
    assert(data == dyna_data && bytes == RAM_CART_DYNA_BYTES && published);
    ++dyna_inits;
}
static void tree_mouth_reset(void) { assert(published); ++resets; }
static void dungeon_doors_reset(void) { assert(published); ++resets; }
static void actor_sys_scene_unload(void) { assert(published); ++resets; }
void bg_dyna_clear(void) { assert(published); ++resets; }
bool kokiri_collision_index(void *data, uint32_t bytes) {
    assert(published && data == collision_index && allocation(data));
    assert(bytes == SCENE_COLLISION_INDEX_BYTES);
    ++index_calls;
    return !fail_index;
}
static void old_scene(void) {
    collision_buffer=new_block(1024);
    memset(&collision_mesh,0,sizeof collision_mesh);
    collision_mesh.triangles=collision_buffer;
    collision_mesh.triangle_count=12;
    bound=collision_mesh;
    dyna_ready=true;
    collision_index=new_block(SCENE_COLLISION_INDEX_BYTES);
    scene_collision_indexed=true;
}
''' + graphics.function(SOURCE, 'static bool __attribute__((optimize("Os"))) collision_load(') +
            '\nint main(void) {\n' + body + '\nreturn 0;\n}\n')

    def test_castle_collision_allocates_exact_size_then_shrinks_for_small_scene(self):
        self.run_collision(r'''
    old_scene();
    void *old=collision_buffer, *index=collision_index;
    required_bytes=194520; decoded_triangles=5096;
    assert(collision_load(23));
    assert(request_count == 1 && requests[0] == 194520);
    assert(!allocation(old) && allocation(collision_buffer)->bytes == 194520);
    assert(published == 1 && resets == 4 && index_calls == 1 && !dyna_inits);
    assert(collision_index == index && scene_collision_indexed);
    old=collision_buffer;
    required_bytes=784; decoded_triangles=20;
    assert(collision_load(23));
    assert(request_count == 2 && requests[1] == 784);
    assert(!allocation(old) && allocation(collision_buffer)->bytes == 784);
    assert(bound.triangle_count == 20 && published == 2 && resets == 8);
    assert(collision_index == index && index_calls == 2 && read_calls == 2);
''')

    def test_failed_replacement_preserves_live_geometry_index_and_actors(self):
        self.run_collision(r'''
    old_scene();
    void *old=collision_buffer, *index=collision_index;
    bg_mesh_t original=collision_mesh;
    required_bytes=194520; decoded_triangles=5096;
    for (failure=1; failure<=8; ++failure) {
        assert(!collision_load(23));
        assert(collision_buffer == old && allocation(old));
        assert(collision_index == index && scene_collision_indexed);
        assert(!memcmp(&original,&collision_mesh,sizeof original));
        assert(!memcmp(&original,&bound,sizeof original));
        for (unsigned i=0; i<1024; ++i) assert(((unsigned char *)old)[i] == 0xa5);
        assert(!published && !resets && !index_calls && !dyna_inits);
        unsigned live=0;
        for (unsigned i=0; i<allocated; ++i) live += allocations[i].alive;
        assert(live == 2); /* old mesh and index; no failed staging buffer leak */
    }
    failure=0;
    assert(collision_load(23));
    assert(published == 1 && bound.triangle_count == 5096 && !allocation(old));
''')

    def test_first_scene_load_and_index_failure_keep_complete_collision(self):
        self.run_collision(r'''
    required_bytes=194520; decoded_triangles=5096;
    fail_index_alloc=true;
    assert(collision_load(23));
    assert(allocation(collision_buffer)->bytes == 194520 && !collision_index);
    assert(!scene_collision_indexed && dyna_inits == 1 && !index_calls);
    assert(bound.triangle_count == 5096 && published == 1 && resets == 4);
    fail_index_alloc=false; fail_index=true;
    required_bytes=784; decoded_triangles=20;
    assert(collision_load(23));
    assert(collision_index && !scene_collision_indexed && index_calls == 1);
    assert(dyna_inits == 1 && bound.triangle_count == 20);
    fail_index=false;
    assert(collision_load(23));
    assert(scene_collision_indexed && index_calls == 2 && dyna_inits == 1);
''')


if __name__ == '__main__':
    unittest.main()
