"""Geometry preservation, sprite cache lifetime and joined DMA upload checks."""
import unittest
import test_graphics_backend as graphics
from test_graphics_backend import ROOT, function


class RenderBatch(unittest.TestCase):
    run_c = graphics.GraphicsBackend.run_c

    def test_draw_gather_restores_indices_and_overflow_is_lossless(self):
        self.run_c(r'''
#include <stdint.h>
#include <assert.h>
#include <string.h>
typedef int32_t POINT[3];
typedef struct {uint16_t Vertices[4];} POLYGON;
''' + '#include "' + (ROOT/'src/forest_vertex_pack.h').as_posix() + '"\n' + r'''
int main(void) {
    POINT source[24], saved[24], draw[12], spill[24], *selected;
    POLYGON faces[6], before[6];
    unsigned short map[24], inverse[24];
    for(unsigned i=0;i<24;++i)for(unsigned k=0;k<3;++k)source[i][k]=i*100+k;
    memcpy(saved,source,sizeof(source));
    for(unsigned turn=0;turn<24;++turn) {
        for(unsigned i=0;i<6;++i)for(unsigned k=0;k<4;++k)faces[i].Vertices[k]=(i*4+k+turn)%24;
        memcpy(before,faces,sizeof(faces));
        for(unsigned visible=0;visible<=6;++visible) {
            unsigned n=forest_gather_vertices(source,24,faces,visible,draw,12,map,inverse);
            assert(!memcmp(saved,source,sizeof(source)));
            if(visible>3 || !visible) assert(!n && !memcmp(before,faces,sizeof(faces)));
            else {
                assert(n==visible*4);
                for(unsigned i=0;i<visible;++i)for(unsigned k=0;k<4;++k)
                    assert(!memcmp(draw[faces[i].Vertices[k]],source[before[i].Vertices[k]],sizeof(POINT)));
                assert(!memcmp(faces+visible,before+visible,(6-visible)*sizeof(POLYGON)));
                forest_restore_vertices(faces,visible,inverse);
                assert(!memcmp(before,faces,sizeof(faces)));
            }
            n=forest_gather_vertices_dual(source,24,faces,visible,draw,12,spill,24,
                                          &selected,map,inverse);
            assert(n==visible*4);
            assert(selected==(n>12?spill:draw));
            assert(!memcmp(saved,source,sizeof(source)));
            for(unsigned i=0;i<visible;++i)for(unsigned k=0;k<4;++k)
                assert(!memcmp(selected[faces[i].Vertices[k]],source[before[i].Vertices[k]],sizeof(POINT)));
            assert(!memcmp(faces+visible,before+visible,(6-visible)*sizeof(POLYGON)));
            forest_restore_vertices(faces,visible,inverse);
            assert(!memcmp(before,faces,sizeof(faces)));
        }
    }
    return 0;
}
''')

    def test_full_bank_gather_capacity_and_canaries(self):
        self.run_c(r'''
#include <stdint.h>
#include <assert.h>
#include <string.h>
typedef int32_t POINT[3];
typedef struct {uint16_t Vertices[4];} POLYGON;
''' + '#include "' + (ROOT/'src/forest_vertex_pack.h').as_posix() + '"\n' + r'''
static POINT source[2048], high[512], spill[2050];
static POLYGON faces[512], saved[512];
static unsigned short map[2048], inverse[2048];
int main(void) {
    for(unsigned i=0;i<2048;++i)for(unsigned j=0;j<3;++j)source[i][j]=i*100+j;
    for(unsigned i=0;i<512;++i)for(unsigned j=0;j<4;++j)faces[i].Vertices[j]=i*4+j;
    memcpy(saved,faces,sizeof(faces));spill[0][0]=12345;spill[2049][2]=54321;
    POINT *selected;
    unsigned n=forest_gather_vertices_dual(source,2048,faces,512,high,512,
                                          spill+1,2048,&selected,map,inverse);
    assert(n==2048 && selected==spill+1);
    for(unsigned i=0;i<512;++i)for(unsigned j=0;j<4;++j)
        assert(!memcmp(selected[faces[i].Vertices[j]],source[saved[i].Vertices[j]],sizeof(POINT)));
    forest_restore_vertices(faces,512,inverse);
    assert(!memcmp(saved,faces,sizeof(faces)) && spill[0][0]==12345 && spill[2049][2]==54321);
    return 0;
}
''')

    def test_vertex_pack_preserves_hidden_faces_across_camera_and_room_changes(self):
        self.run_c(r'''
#include <stdint.h>
#include <assert.h>
#include <string.h>
typedef int32_t POINT[3];
typedef struct {uint16_t Vertices[4];} POLYGON;
''' + '#include "' + (ROOT/'src/forest_vertex_pack.h').as_posix() + '"\n' + r'''
static POINT p[2048], before[300][4];
static POLYGON polys[300];
static unsigned short scratch[4098];
static unsigned seed=123;
static unsigned rnd(void){seed=seed*1664525u+1013904223u;return seed;}
int main(void) {
    for(unsigned room=0;room<4;++room) {
        unsigned vertices=room==0?2048:31+room*27;
        for(unsigned i=0;i<vertices;++i)for(unsigned k=0;k<3;++k)p[i][k]=(i*17+k*3)*65536;
        for(unsigned i=0;i<300;++i)for(unsigned k=0;k<4;++k)polys[i].Vertices[k]=rnd()%vertices;
        scratch[0]=1234;scratch[4097]=5678;
        for(unsigned frame=0;frame<100;++frame) {
            unsigned visible=frame==0?0:frame==1?300:rnd()%301;
            unsigned unique=0;unsigned char seen[2048]={0};
            /* Simulate cull partition changes before packing. */
            for(unsigned i=0;i<30;++i) {
                unsigned a=rnd()%300,b=rnd()%300;POLYGON t=polys[a];polys[a]=polys[b];polys[b]=t;
            }
            for(unsigned i=0;i<300;++i)for(unsigned k=0;k<4;++k) {
                unsigned id=polys[i].Vertices[k];
                memcpy(before[i][k],p[id],sizeof(POINT));
                if(i<visible && !seen[id]) {seen[id]=1;++unique;}
            }
            unsigned used=forest_pack_vertices(p,vertices,polys,300,visible,scratch+1,scratch+2049);
            assert(used==unique && scratch[0]==1234 && scratch[4097]==5678);
            for(unsigned i=0;i<300;++i)for(unsigned k=0;k<4;++k) {
                unsigned id=polys[i].Vertices[k];assert(id<vertices);
                assert(i>=visible || id<used);
                assert(!memcmp(before[i][k],p[id],sizeof(POINT)));
            }
            assert(forest_pack_vertices(p,vertices,polys,300,visible,scratch+1,scratch+2049)==used);
            /* A changed polygon order with the same visible set must not
             * reshuffle points or rewrite indices (the moving-view fast path). */
            static POINT stable[2048];
            static POLYGON ordered[300];
            for(unsigned i=0;i<visible/2;++i) {
                POLYGON t=polys[i];polys[i]=polys[visible-1-i];polys[visible-1-i]=t;
            }
            memcpy(stable,p,sizeof(p));memcpy(ordered,polys,sizeof(polys));
            scratch[1]=54321;
            assert(forest_pack_vertices(p,vertices,polys,300,visible,scratch+1,scratch+2049)==used);
            assert(!memcmp(stable,p,sizeof(p)) && !memcmp(ordered,polys,sizeof(polys)));
            assert(scratch[1]==54321); /* no remap initialization required */
        }
    }
    return 0;
}
''')

    def test_dma_finishes_before_cel_publication_and_same_cel_does_not_copy(self):
        source = r'''
#include <stdint.h>
#include <assert.h>
#include <string.h>
#define U16(p,n) ((unsigned)((p)[n]<<8|(p)[(n)+1]))
#define CELS(p) 64u
#define JO_MULT_BY_32(n) ((n)*32)
typedef struct {unsigned short width,height,size;} jo_texture_definition;
static jo_texture_definition __jo_sprite_def[1];
static struct {void *data;} __jo_sprite_pic[1];
static unsigned short palettes[32];
#define JO_VDP1_VRAM ((uintptr_t)palettes)
typedef struct {const unsigned char *sheet;uint16_t slot,colno,shown;} npc_sprite_inst_t;
static unsigned npc_sprite_cpu_copy,ticks,copies,waits;
static void *pending_to;static const void *pending_from;static unsigned pending_bytes;
static unsigned frame_timer_ticks(void){return ++ticks;}
static unsigned frame_timer_ticks_to_us(unsigned n){return n;}
#define PS_ACC(i,n) ((void)(n))
static void slDMAWait(void) {
    ++waits;
    if(pending_to){memcpy(pending_to,pending_from,pending_bytes);pending_to=0;}
}
static void jo_dma_copy(void *src,void *dst,unsigned bytes) {
    assert(waits && !pending_to);++copies;
    pending_from=src;pending_to=dst;pending_bytes=bytes;
}
'''
        source += function(ROOT/'src/npc_sprite.c','static void npc_sprite_bind_sample(')
        source += r'''
int main(void) {
    union {uint32_t align;unsigned char b[160];} sheet={0};uint32_t output[4]={0};
    unsigned char *s=sheet.b;s[5]=8;s[7]=4;
    for(unsigned i=64;i<160;++i)s[i]=(unsigned char)i;
    __jo_sprite_pic[0].data=output;npc_sprite_inst_t slot={s,0,0,0};
    npc_sprite_bind_sample(s,&slot,2);
    assert(copies==1 && waits==2 && !pending_to && slot.shown==2);
    assert(!memcmp(output,s+96,16));
    npc_sprite_bind_sample(s,&slot,2);assert(copies==1 && waits==2);
    npc_sprite_cpu_copy=1;npc_sprite_bind_sample(s,&slot,3);
    assert(copies==1 && slot.shown==3 && !memcmp(output,s+112,16));
    return 0;
}
'''
        self.run_c(source)

    def test_reserving_later_hits_prevents_order_dependent_cache_eviction(self):
        source = '#include <assert.h>\n#include "'+(ROOT/'src/npc_sprite.h').as_posix()+'"\n'
        source += function(ROOT/'src/npc_sprite.c','npc_sprite_inst_t *npc_sprite_cache_claim(')
        source += r'''
int main(void) {
    unsigned char a,b,c;unsigned pinned=0,locked=~0u;
    npc_sprite_inst_t slots[3]={{&a,0,0,1},{&b,1,0,2},{&a,2,0,3}},*p;
    p=npc_sprite_cache_claim(slots,3,&locked,&a,1);assert(p==slots);pinned|=1u<<(p-slots);
    p=npc_sprite_cache_claim(slots,3,&pinned,&c,4);assert(p && p!=slots);
    p->sheet=&c;p->shown=4;
    assert(npc_sprite_cache_claim(slots,3,&pinned,&a,1)==slots);
    /* Misses across frames use more than the first slot; all three cached
     * frames can be hit again without any replacement. */
    for(unsigned frame=10;frame<13;++frame) {
        pinned=0;p=npc_sprite_cache_claim(slots,3,&pinned,&b,frame);assert(p);
        p->sheet=&b;p->shown=frame;
    }
    for(unsigned frame=10;frame<13;++frame) {
        locked=~0u;assert(npc_sprite_cache_claim(slots,3,&locked,&b,frame));
    }
    return 0;
}
'''
        self.run_c(source)

    def test_master_prepare_skips_hidden_and_panorama_and_publishes_once(self):
        source = r'''
#include <assert.h>
#include <stdbool.h>
#define STORY_BANK_PANORAMA 9
static bool prep_master_ready,forest_reused;
static unsigned forest_scene,calls,timer,purges;
static void scene_bank_purge(void *arg){++purges;}
static void slSlaveFunc(void (*f)(void*),void *arg){assert(prep_master_ready==false);f(arg);}
static unsigned frame_timer_ticks(void){return ++timer;}
static unsigned frame_timer_ticks_to_us(unsigned n){return n;}
#define PS_ACC(i,n) ((void)(n))
static unsigned scene_prepare(bool slave){assert(!slave);++calls;return 3;}
'''
        source += function(ROOT/'src/kokiri_sgl.c','void kokiri_frame_master_prepare(')
        source += r'''
int main(void) {
    kokiri_frame_master_prepare(false);assert(!prep_master_ready && !calls);
    forest_scene=9;kokiri_frame_master_prepare(true);assert(!prep_master_ready && !calls);
    forest_scene=1;kokiri_frame_master_prepare(true);assert(prep_master_ready && calls==1 && purges==1);
    forest_reused=true;kokiri_frame_master_prepare(true);assert(prep_master_ready && calls==2 && purges==1);
    kokiri_frame_master_prepare(false);assert(!prep_master_ready && calls==2);
    return 0;
}
'''
        self.run_c(source)
