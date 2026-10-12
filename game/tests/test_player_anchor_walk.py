"""Compare source and anchor-only walkers: hierarchy, callbacks and matrices."""
import unittest
import test_graphics_backend as graphics
from test_graphics_backend import ROOT, function


class PlayerAnchorWalk(unittest.TestCase):
    run_c = graphics.GraphicsBackend.run_c

    def test_matches_source_callbacks_without_rsp_matrix_output(self):
        original = ROOT / 'build/oot-core/decomp/src/code/z_skelanime.cpp'
        optimized = ROOT / 'oot-core/src/oot_core_draw.cpp'
        source = r'''
#include <stdint.h>
#include <assert.h>
#include <string.h>
typedef int s32;
typedef struct {int x,y,z;} Vec3f, Vec3s;
typedef int Gfx, Mtx;
typedef struct {struct {void* gfxCtx;} state;} PlayState;
typedef struct {Vec3s jointPos; unsigned char child,sibling; Gfx* dLists[2];} LodLimb;
typedef int (*OverrideLimbDrawOpa)(PlayState*,int,Gfx**,Vec3f*,Vec3s*,void*);
typedef void (*PostLimbDrawOpa)(PlayState*,int,Gfx**,Vec3s*,void*);
#define LIMB_DONE 255
#define SEGMENTED_TO_VIRTUAL(p) (p)
#define GRAPH_ALLOC(g,n) matrices
#define OPEN_DISPS(...)
#define CLOSE_DISPS(...)
#define PRINTF_COLOR_RED(...)
#define PRINTF(...)
#define PRINTF_RST(...)
#define gSPSegment(...)
#define gSPMatrix(...)
#define gSPDisplayList(...)
#define MATRIX_TO_MTX(...) (++serialized)
static Mtx matrices[32];
static Vec3f stack[32];
static int sp, serialized, events[512], at;
static void Matrix_Push(void){stack[sp+1]=stack[sp];++sp;}
static void Matrix_Pop(void){assert(sp>0);--sp;}
static void Matrix_TranslateRotateZYX(Vec3f* p,Vec3s* r){
    stack[sp].x+=p->x+r->x;stack[sp].y+=p->y+r->y;stack[sp].z+=p->z+r->z;
}
static void OotCore_PlayerTranslateRotateZYX(Vec3f* p,Vec3s* r){Matrix_TranslateRotateZYX(p,r);}
static int over(PlayState* p,int i,Gfx** d,Vec3f* pos,Vec3s* rot,void* arg){
    events[at++]=-i; pos->x+=i;rot->z-=i;
    if(i==3)*d=0;
    if(i==4){stack[sp].y+=123;return 1;}
    return 0;
}
static void post(PlayState* p,int i,Gfx** d,Vec3s* r,void* arg){
    events[at++]=i;events[at++]=stack[sp].x;events[at++]=stack[sp].y;
    events[at++]=stack[sp].z;events[at++]=*d!=0;events[at++]=r->z;
    stack[sp].x+=7; /* children inherit post-callback matrix edits */
}
'''
        for name in ('void SkelAnime_DrawFlexLimbLod(', 'void SkelAnime_DrawFlexLod('):
            source += function(original, name) + '\n'
        for name in ('static void PlayerAnchor_Limb(', 'void OotCore_PlayerAnchorPose('):
            source += function(optimized, name) + '\n'
        source += r'''
int main(void){
    PlayState play={0};LodLimb limbs[6];void* skeleton[6];Vec3s joints[7];Gfx dl=0;
    for(int i=0;i<6;++i){
        limbs[i]=(LodLimb){{i*3,i*5,-i},255,255,{&dl,i%2?0:&dl}};
        skeleton[i]=&limbs[i];joints[i]=(Vec3s){i*7,-i*3,i*9};
    }
    joints[6]=(Vec3s){5,6,7};
    limbs[0].child=1;limbs[1].child=2;limbs[1].sibling=4;
    limbs[2].sibling=3;limbs[4].child=5;
    for(int lod=0;lod<2;++lod)for(int callbacks=0;callbacks<4;++callbacks){
        int expected[512], n;
        OverrideLimbDrawOpa o=callbacks&1?over:0;
        PostLimbDrawOpa p=callbacks&2?post:0;
        at=sp=serialized=0;memset(stack,0,sizeof(stack));
        SkelAnime_DrawFlexLod(&play,skeleton,joints,6,o,p,0,lod);
        assert(sp==0 && serialized>0);n=at;memcpy(expected,events,n*sizeof(int));
        at=serialized=0;memset(stack,0,sizeof(stack));
        OotCore_PlayerAnchorPose(&play,skeleton,joints,o,p,0,lod);
        assert(sp==0 && serialized==0 && at==n && !memcmp(expected,events,n*sizeof(int)));
    }
    OotCore_PlayerAnchorPose(&play,0,joints,over,post,0,0);assert(sp==0);
    return 0;
}
'''
        self.run_c(source)
