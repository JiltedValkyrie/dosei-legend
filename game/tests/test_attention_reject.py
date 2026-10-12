"""Distance-first attention preserves selection, cones and visibility ordering."""
import unittest
from test_graphics_backend import ROOT, function
import test_graphics_backend as graphics


class AttentionReject(unittest.TestCase):
    run_c = graphics.GraphicsBackend.run_c

    def test_old_selector_matches_all_angles_and_random_actor_pools(self):
        source = '#include "%s"\n' % (ROOT/'src/actor_sys.h').as_posix()
        source += r'''
#include <assert.h>
#include <string.h>
#include <math.h>
static actor_t pool[ACTOR_POOL_MAX];
static const actor_profile_t profile={1,ACTORCAT_NPC,ACTOR_FLAG_TARGETABLE,0,0,0,0};
static bool offscreen[ACTOR_POOL_MAX],blocked[ACTOR_POOL_MAX];
static unsigned trace[ACTOR_POOL_MAX*2],trace_n,angles,forced;
static bool force_angle;
actor_t *actor_sys_slot(unsigned i) {return i<ACTOR_POOL_MAX&&pool[i].profile?&pool[i]:0;}
static uint16_t gameplay_facing(int32_t x,int32_t z) {
    ++angles;
    return force_angle?(uint16_t)forced:(uint16_t)(int32_t)lround(atan2((double)x,(double)z)*32768.0/3.14159265358979323846);
}
bool attention_on_screen(const int32_t at[3]) {
    unsigned i=(unsigned)(at[1]-1000);assert(i<ACTOR_POOL_MAX);
    trace[trace_n++]=i*2;return !offscreen[i];
}
bool attention_sight_blocked(const int32_t from[3],const int32_t at[3]) {
    unsigned i=(unsigned)(at[1]-1000);assert(i<ACTOR_POOL_MAX);
    trace[trace_n++]=i*2+1;return blocked[i];
}
'''
        ranges = (ROOT/'src/actor_sys.c').read_text()
        start = ranges.index('static const uint16_t attention_ranges')
        source += ranges[start:ranges.index('};', start)+2]
        source += function(ROOT/'src/actor_sys.c', 'uint32_t        actor_attention_range_sq(')
        for marker in ('void        attention_focus(', 'static bool dist_sq(',
                       'static bool attention_enabled(', 'actor_t    *attention_find('):
            source += function(ROOT/'src/attention.c', marker)
        source += r'''
/* Pre-optimization implementation. Keep atan before distance/range checks. */
static actor_t *original(const int32_t feet[3],const int32_t focus[3],uint16_t yaw,const actor_t *locked) {
    actor_t *best=0;uint32_t best_d=UINT32_MAX;
    for(unsigned i=0;i<ACTOR_POOL_MAX;++i) {
        actor_t *a=actor_sys_slot(i);uint32_t d,w;int32_t turn,at[3];
        if(a==locked || !attention_enabled(a) || !dist_sq(feet,a,&d))continue;
        turn=(int16_t)(gameplay_facing(a->x-feet[0],a->z-feet[2])-yaw);
        if(turn<0)turn=-turn;
        if(locked) {
            if(turn>0x4000)continue;
            uint32_t f=(uint32_t)(0x4000-turn);
            w=d-(d/40960u)*f-((d%40960u)*f)/40960u;
        } else {
            if(turn>0x2aaa)continue;
            w=d;
        }
        if(w>=best_d || w>=actor_attention_range_sq(a))continue;
        attention_focus(a,at);
        if(!attention_on_screen(at) || attention_sight_blocked(focus,at))continue;
        best=a;best_d=w;
    }
    return best;
}
static unsigned old_total,new_total;
static actor_t *check(const int32_t feet[3],uint16_t yaw,const actor_t *locked) {
    int32_t focus[3]={feet[0],feet[1]+40,feet[2]};
    unsigned expected_trace[ACTOR_POOL_MAX*2];
    angles=trace_n=0;
    actor_t *expected=original(feet,focus,yaw,locked);
    unsigned expected_angles=angles,expected_n=trace_n;
    memcpy(expected_trace,trace,trace_n*sizeof(*trace));
    angles=trace_n=0;
    actor_t *actual=attention_find(feet,focus,yaw,locked);
    assert(actual==expected && angles<=expected_angles);
    assert(trace_n==expected_n && !memcmp(trace,expected_trace,trace_n*sizeof(*trace)));
    old_total+=expected_angles;new_total+=angles;
    return actual;
}
static void place(unsigned i,int x,int y,int z,unsigned range) {
    actor_t *a=&pool[i];*a=(actor_t){0};a->profile=&profile;
    a->x=x;a->y=y;a->z=z;a->range=range;
    a->flags=ACTOR_FLAG_TARGETABLE;a->attention=ATTN_NPC;
    a->focus[1]=(int16_t)(1000+(int)i-y);
}
static uint32_t rng=0x23847561;
static unsigned random_u32(void) {rng^=rng<<13;rng^=rng>>17;rng^=rng<<5;return rng;}
int main(void) {
    int32_t feet[3]={0,0,0};
    force_angle=true;forced=0;
    /* Exhaust every signed angular delta: both cone boundaries and yaw wrap,
     * locked/unlocked, same-distance ties and a far actor before the winner. */
    place(0,0,0,-9999,0);place(1,0,0,100,ATTN_RANGE_1);
    place(2,0,0,100,ATTN_RANGE_1);place(5,0,0,10000,ATTN_RANGE_5);
    for(unsigned yaw=0;yaw<65536;++yaw) {
        check(feet,(uint16_t)yaw,0);check(feet,(uint16_t)yaw,&pool[0]);
    }
    /* Source weighted acquisition deliberately admits actors outside their
     * raw range. A naive d>=range early check must fail this case. */
    memset(pool,0,sizeof(pool));place(0,0,0,-9999,0);
    place(1,0,0,150,ATTN_RANGE_7); /* 22500*.6 < 140^2 */
    assert(check(feet,0,&pool[0])==&pool[1]);assert(!check(feet,0,0));
    /* Off-screen and blocked candidates cannot hide a later valid candidate.
     * Pool holes, dead actors and exact ties retain the old visit order. */
    place(2,0,0,160,ATTN_RANGE_7);place(8,0,0,161,ATTN_RANGE_7);
    offscreen[1]=true;blocked[2]=true;
    assert(check(feet,0,&pool[0])==&pool[8]);
    pool[8].kill=true;assert(!check(feet,0,&pool[0]));
    memset(pool,0,sizeof(pool));memset(offscreen,0,sizeof(offscreen));memset(blocked,0,sizeof(blocked));
    /* Strict squared-range boundary for every range, plus very large
     * distances close to dist_sq's safe 32-bit limit. */
    for(unsigned range=0;range<ATTN_RANGE_COUNT+1;++range) {
        unsigned radius=attention_ranges[range<ATTN_RANGE_COUNT?range:0][0];
        place(0,0,0,-9999,0);
        for(int delta=-1;delta<=1;++delta) {
            place(1,0,0,(int)radius+delta,range);
            check(feet,0,0);check(feet,0,&pool[0]);
        }
        place(1,36999,36999,36999,range);check(feet,0,0);check(feet,0,&pool[0]);
        place(1,37000,0,0,range);check(feet,0,0);check(feet,0,&pool[0]);
    }
    force_angle=false;
    for(unsigned trial=0;trial<12000;++trial) {
        memset(pool,0,sizeof(pool));
        feet[0]=(int)(random_u32()%2001)-1000;feet[1]=(int)(random_u32()%101)-50;
        feet[2]=(int)(random_u32()%2001)-1000;
        for(unsigned i=0;i<ACTOR_POOL_MAX;++i) {
            unsigned span=i%3?10001:801;
            place(i,feet[0]+(int)(random_u32()%span)-(int)span/2,
                    feet[1]+(int)(random_u32()%201)-100,
                    feet[2]+(int)(random_u32()%span)-(int)span/2,random_u32()%(ATTN_RANGE_COUNT+1));
            if((random_u32()&7)==0)pool[i].profile=0;
            pool[i].kill=(random_u32()&31)==0;
            if((random_u32()&15)==0)pool[i].attention=ATTN_NONE;
            if((random_u32()&15)==0)pool[i].flags=0;
            offscreen[i]=(random_u32()&3)==0;blocked[i]=(random_u32()&3)==0;
        }
        uint16_t yaw=(uint16_t)random_u32();
        check(feet,yaw,0);check(feet,yaw,&pool[random_u32()%ACTOR_POOL_MAX]);
    }
    /* Far population: all 96 old atan calls disappear; there are no lost
     * projection/occlusion calls because nobody could have entered range. */
    feet[0]=feet[1]=feet[2]=0;
    for(unsigned i=0;i<ACTOR_POOL_MAX;++i)place(i,10000+(int)i,0,10000,ATTN_RANGE_SLICE_NPC);
    old_total=new_total=0;check(feet,0,0);assert(old_total==96 && !new_total);
    check(feet,0,&pool[0]);assert(old_total==191 && !new_total);
    return 0;
}
'''
        self.run_c(source)


if __name__ == '__main__':
    unittest.main()
