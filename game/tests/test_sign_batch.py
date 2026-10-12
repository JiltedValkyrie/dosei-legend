"""Execute production sign visibility, immutable fade and snapshot ownership."""
import unittest
from test_graphics_backend import ROOT, function
import test_graphics_backend as graphics


class SignBatch(unittest.TestCase):
    run_c = graphics.GraphicsBackend.run_c

    def test_sign_query_uses_snapshot_until_slave_join(self):
        source = r'''
#include <assert.h>
#define OOT_CORE_ASYNC
#define KOKIRI_SIGN_COUNT 2
static int busy,playing=1,calls;
#define ASYNC_BUSY() (busy)
static struct {int x,z;} kokiri_signs[2]={{10,20},{30,40}};
static int snap_sign_parts[2]={0xffff,5};
static int query(short id,int x,int z) {assert(!busy);++calls;return 123;}
static struct {int (*prop_query)(short,int,int);} entry={query};
#define ENTRY (&entry)
'''
        source += function(ROOT/'src/oot_core_host.c', 'int oot_core_prop(')
        source += r'''
int main(void) {
    busy=1;
    assert(oot_core_prop(0x141,10,20)==0xffff);
    assert(oot_core_prop(0x141,30,40)==5);
    assert(oot_core_prop(0x141,1,2)==-1 && !calls);
    assert(oot_core_prop(0x142,10,20)==-1 && !calls);
    playing=0;assert(oot_core_prop(0x141,10,20)==-1);
    playing=1;busy=0;assert(oot_core_prop(0x141,10,20)==123 && calls==1);
    return 0;
}
'''
        self.run_c(source)

    def test_npc_pose_matches_individual_getters_for_live_and_turned_actors(self):
        source = r'''
#include <assert.h>
#include <stdint.h>
#define KOKIRI_NPC_COUNT 2
typedef struct {int x,y,z;uint16_t yaw;} kokiri_npc_t;
static kokiri_npc_t kokiri_npcs[2]={{1,2,3,4},{5,6,7,8}}, live={9,10,11,12};
static unsigned npc_turned=3, use_live, reads;
static uint16_t npc_turn[2]={20,21};
static const kokiri_npc_t *npc_at(int n) {++reads;return use_live?&live:&kokiri_npcs[n];}
'''
        path = ROOT/'src/gameplay.c'
        for marker in ('void gameplay_npc_pose(', 'int32_t             gameplay_npc_x(',
                       'int32_t             gameplay_npc_y(', 'int32_t             gameplay_npc_z(',
                       'uint16_t gameplay_npc_yaw('):
            source += function(path, marker) + '\n'
        source += r'''
int main(void) {
    for(use_live=0;use_live<2;++use_live)for(npc_turned=0;npc_turned<4;++npc_turned)
        for(unsigned i=0;i<3;++i) {
            int32_t p[3];uint16_t yaw;reads=0;
            gameplay_npc_pose(i,p,&yaw);assert(reads==(i<2));
            assert(p[0]==gameplay_npc_x(i) && p[1]==gameplay_npc_y(i));
            assert(p[2]==gameplay_npc_z(i) && yaw==gameplay_npc_yaw(i));
        }
    return 0;
}
'''
        self.run_c(source)

    def test_sign_fade_culls_and_draws_one_immutable_variant_per_instance(self):
        source = '#include "%s"\n' % (ROOT/'oot-core/include/oot_sign_visual.h').as_posix()
        source += r'''
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
typedef struct {int n;} actor_mesh_t;
static actor_mesh_t intact, cached, faded;
static actor_mesh_t *sign_intact=&intact, *sign_hot=&cached, *sign_fade=&faded;
static bool sign_hot_dirty=true;
static unsigned purges;
static unsigned sign_radius=100, dosei_sign_slow, calls, originals, hot, fades, pushes;
static int visible=1;
static int npc_sprite_in_view(int x,int y,int z,unsigned r) {assert(r==100);return visible;}
static void jo_3d_push_matrix(void) {++pushes;}
static void jo_3d_pop_matrix(void) {--pushes;}
static void jo_3d_translate_matrix(int x,int y,int z) {}
static void slRotY(uint16_t yaw) {}
static void sign_cache_purge(void *arg) {++purges;}
static void slSlaveFunc(void (*fn)(void *),void *arg) {fn(arg);}
static void actor_mesh_draw_static(actor_mesh_t *m,int x,int y,int z,unsigned yaw) {
    assert(z==-1);++calls;originals+=m==&intact;hot+=m==&cached;fades+=m==&faded;
}
'''
        source += function(ROOT/'src/world_props_draw.c', 'static void draw_sign(')
        source += r'''
int main(void) {
    draw_sign(OOT_SIGN_INTACT,0,0,0,0);
    assert(calls==1 && hot==1 && purges==1 && !sign_hot_dirty && !pushes);
    draw_sign(0,0,0,0,0);assert(calls==1 && !pushes);
    for(unsigned phase=OOT_SIGN_FADE_TICKS;phase;--phase) {
        unsigned before_hot=hot,before_fade=fades;
        draw_sign(phase,0,0,0,0);
        assert(hot==before_hot+(phase>OOT_SIGN_MESH_TICKS));
        assert(fades==before_fade+(phase<=OOT_SIGN_MESH_TICKS));
        assert(!pushes);
    }
    assert(calls==OOT_SIGN_FADE_TICKS+1 && purges==1);
    calls=0;visible=0;
    draw_sign(OOT_SIGN_INTACT,0,0,0,0);draw_sign(4,0,0,0,0);
    assert(!calls && !pushes);
    dosei_sign_slow=1;draw_sign(OOT_SIGN_INTACT,0,0,0,0);assert(calls==1);
    visible=1;dosei_sign_slow=0;sign_hot=0;sign_hot_dirty=true;
    draw_sign(OOT_SIGN_INTACT,0,0,0,0);assert(originals==1 && purges==2);
    sign_intact=0;calls=0;draw_sign(4,0,0,0,0);assert(!calls);
    return 0;
}
'''
        self.run_c(source)
