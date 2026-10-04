"""Actual cleanup functions against the SDK's non-null free contract."""
from pathlib import Path
import unittest
import test_graphics_backend as graphics

ROOT = Path(__file__).resolve().parents[1]


class SpriteCleanup(unittest.TestCase):
    run_c = graphics.GraphicsBackend.run_c

    def test_production_story_load_failures_roll_back_and_retry(self):
        source = ROOT / 'src'
        self.run_c(r'''
#include <stdint.h>
#include <stdbool.h>
#include <assert.h>
#include <string.h>
typedef int actor_mesh_t;
static unsigned char *saria[4],*owl[2],*ganon,*horse;
static actor_mesh_t *body,*aura,*triforce,*jewel;
static unsigned uploaded,owl_phase,owl_frame,clock_phase,owl_handle,part;
static int owl_x,owl_y,owl_z,owl_yaw,owl_speed,owl_vy;
static unsigned char allocations[32],live[32];
static unsigned attempts,fail_at,count;
static void *acquire(void) {
    if (++attempts==fail_at) return 0;
    for(unsigned i=0;i<32;++i)if(!live[i]) {
        live[i]=1; ++count;return &allocations[i];
    }
    assert(0);return 0;
}
static void jo_free(void *p) {
    assert(p);
    for(unsigned i=0;i<32;++i)if(p==&allocations[i]) {
        assert(live[i]);live[i]=0;--count;return;
    }
    assert(0);
}
static unsigned char *npc_sprite_load(const char *s){return acquire();}
static actor_mesh_t *actor_mesh_load_static(const char *s){return acquire();}
static void actor_mesh_free(actor_mesh_t *p){if(p)jo_free(p);}
static void *actor_resolve(unsigned h){return 0;}
static void actor_kill(void *p){}
#define SAVE_SCENE_LOST_WOODS 1
#define SAVE_SCENE_HYRULE_FIELD 10
#define EVENTCHKINF_FAIRY_OCARINA_RECEIVED 0xc1
static unsigned completed;
static bool save_get_event_chk_inf(unsigned e){return completed;}
static bool save_get_switch(unsigned scene,unsigned flag){return completed;}
''' + graphics.function(source / 'story_route.c', 'void story_route_free(')
            + graphics.function(source / 'story_route.c', 'bool story_route_load(')
            + graphics.function(source / 'emerald_story.c', 'void emerald_story_free(')
            + graphics.function(source / 'emerald_story.c', 'bool emerald_story_load(') + r'''
int main(void) {
    for(unsigned scene=1;scene<=10;scene+=9) {
        unsigned expected=scene==1?4:2;
        for(unsigned fail=1;fail<=expected;++fail) {
            attempts=0;fail_at=fail;
            assert(!story_route_load(scene));assert(!count && !owl_phase);
            story_route_free();story_route_free();assert(!count);
            attempts=0;fail_at=0;
            assert(story_route_load(scene));assert(count==expected);
            assert(story_route_load(scene));assert(count==expected);
            story_route_free();story_route_free();assert(!count);
        }
        completed=1;assert(story_route_load(scene));assert(!count);completed=0;
    }
    for(unsigned p=1;p<=9;++p) {
        unsigned expected=p==2?2:p==8?3:p>=3&&p<=7?2:p==9?1:0;
        for(unsigned fail=0;fail<=expected;++fail) {
            attempts=0;fail_at=fail;
            assert(emerald_story_load(p)==!fail);
            assert(count==(fail?0:expected));
            attempts=0;fail_at=0;
            assert(emerald_story_load(p));assert(count==expected);
            emerald_story_free();emerald_story_free();assert(!count);
        }
    }
    return 0;
}
''')

    def test_cutscene_load_failure_at_every_allocation_and_retry(self):
        path = ROOT / 'src/cutscene_actor.c'
        source = path.read_text()
        declarations = source[source.index('#define KFR1_MAGIC'):source.index('static uint32_t read_be32(')]
        self.run_c(r'''
#include <stdint.h>
#include <stdbool.h>
#include <assert.h>
#include <string.h>
#define CUTSCENE_ACTOR_COUNT 8
#define CUTSCENE_ACTOR_BRIDGE 5
#define CUTSCENE_ACTOR_GATE_FIRE 7
typedef int32_t FIXED,POINT[3],Sint32;
typedef uint16_t Uint16;
typedef struct { unsigned short Vertices[4];int norm[3]; } POLYGON;
typedef struct { unsigned short flag,sort,texno,atrb,colno,gstb,dir; } ATTR;
typedef struct { POINT *pntbl;POLYGON *pltbl;ATTR *attbl;int nbPoint,nbPolygon; } PDATA;
typedef struct { int slot; } npc_sprite_inst_t;
#define X 0
#define Y 1
#define Z 2
#define toFIXED(x) ((int)((x)*65536))
#define Dual_Plane 0
#define SORT_CEN 0
#define UseNearClip 0
#define UseTexture 0
#define UsePalette 0
#define CL16Look 0
#define ECdis 0
#define SPdis 0
#define sprNoflip 0
static union { unsigned char bytes[4096];int align; } allocations[32];
static unsigned char live[32];
static unsigned attempts,fail_at,count;
static void *jo_malloc(unsigned n) {
    assert(n<=4096);
    if(++attempts==fail_at)return 0;
    for(unsigned i=0;i<32;++i)if(!live[i]) {
        live[i]=1;++count;memset(allocations[i].bytes,0,4096);return allocations[i].bytes;
    }
    assert(0);return 0;
}
static void jo_free(void *p) {
    assert(p);
    for(unsigned i=0;i<32;++i)if(p==allocations[i].bytes) {
        assert(live[i]);live[i]=0;--count;return;
    }
    assert(0);
}
static void put32(unsigned char *p,unsigned v) {p[0]=v>>24;p[1]=v>>16;p[2]=v>>8;p[3]=v;}
static unsigned char *jo_fs_read_file(const char *name,int *length) {
    unsigned char *p=jo_malloc(64+24+32*20+64);
    if(!p)return 0;
    *length=64+24+32*20+64;
    put32(p,0x4b465231);put32(p+8,4);put32(p+12,32);
    put32(p+16,64);put32(p+20,88);put32(p+24,88+32*20);put32(p+28,64);
    for(unsigned i=0;i<32;++i) {p[88+i*20+16]=1;p[88+i*20+17]=8;}
    return p;
}
static unsigned char *npc_sprite_load(const char *name){return jo_malloc(64);}
static void asset_loading(const char *name){}
void cutscene_actors_free(void);
''' + declarations
            + graphics.function(path, 'static uint32_t read_be32(')
            + graphics.function(path, 'static uint16_t read_be16(')
            + graphics.function(path, 'static void free_actor(')
            + graphics.function(path, 'static bool __attribute__((optimize("Os"))) load_actor(')
            + graphics.function(path, 'bool cutscene_actors_load(')
            + graphics.function(path, 'void cutscene_actors_free(') + r'''
int main(void) {
    cutscene_actors_free();cutscene_actors_free();assert(!count);
    /* Five sheets, then three static props with file + three render tables. */
    for(unsigned failure=1;failure<=17;++failure) {
        attempts=0;fail_at=failure;
        assert(!cutscene_actors_load());assert(!count && !actors_ready && !resident_mask);
        cutscene_actors_free();cutscene_actors_free();assert(!count);
        attempts=0;fail_at=0;
        assert(cutscene_actors_load());assert(count==17);
        assert(cutscene_actors_load());assert(count==17 && attempts==17);
        cutscene_actors_free();cutscene_actors_free();assert(!count);
        for(unsigned i=0;i<5;++i)assert(!actor_sprites[i]);
        for(unsigned i=5;i<8;++i)assert(!actors[i].loaded && !actors[i].points &&
            !actors[i].polygons && !actors[i].attributes && !actors[i].model_data);
    }
    return 0;
}
''')

    def test_empty_partial_full_and_repeated_teardown(self):
        self.run_c(r'''
#include <stdint.h>
#include <assert.h>
#include <string.h>
typedef int actor_mesh_t;
static unsigned char *saria[4],*owl[2],*ganon,*horse;
static actor_mesh_t *body,*aura,*triforce,*jewel;
static unsigned uploaded,owl_phase,owl_frame,clock_phase,owl_handle;
static unsigned char allocations[8],live[8];
static unsigned freed;
static void jo_free(void *p) {
    assert(p); /* The SDK raises an error here, unlike libc free(NULL). */
    unsigned i=(unsigned)((unsigned char *)p-allocations);
    assert(i<8 && live[i]); live[i]=0; ++freed;
}
static void actor_mesh_free(actor_mesh_t *p) { assert(!p); }
static void *actor_resolve(unsigned h) { return 0; }
static void actor_kill(void *p) {}
''' + graphics.function(ROOT / 'src/story_route.c', 'void story_route_free(')
            + graphics.function(ROOT / 'src/emerald_story.c', 'void emerald_story_free(') + r'''
int main(void) {
    for(unsigned mask=0;mask<256;++mask) {
        freed=0; unsigned expected=0;
        for(unsigned i=0;i<8;++i) {
            live[i]=(mask>>i)&1; expected+=live[i];
            unsigned char *p=live[i]?&allocations[i]:0;
            if(i<4)saria[i]=p;else if(i<6)owl[i-4]=p;
            else if(i==6)ganon=p;else horse=p;
        }
        story_route_free(); emerald_story_free();
        assert(freed==expected);
        story_route_free(); emerald_story_free();
        assert(freed==expected);
        for(unsigned i=0;i<8;++i)assert(!live[i]);
        for(unsigned i=0;i<4;++i)assert(!saria[i]);
        assert(!owl[0] && !owl[1] && !ganon && !horse);
    }
    return 0;
}
''')


if __name__ == '__main__':
    unittest.main()
