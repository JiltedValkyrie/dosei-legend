"""Production master actor scans: live callback ordering and one core view read."""
import unittest
from test_graphics_backend import ROOT, function
import test_graphics_backend as graphics


class MasterActorBatch(unittest.TestCase):
    run_c = graphics.GraphicsBackend.run_c

    @staticmethod
    def actor_source():
        return ('#include <assert.h>\n#include <string.h>\n' +
                '#include "%s"\n' % (ROOT / 'src/actor_sys.c').as_posix() +
                '#include "%s"\n' % (ROOT / 'src/save_state.c').as_posix())

    def test_pool_bound_preserves_holes_reuse_and_all_public_scans(self):
        self.run_c(self.actor_source() + r'''
static actor_t memory[ACTOR_POOL_MAX];
static const actor_profile_t passive={5,ACTORCAT_PROP,ACTOR_FLAG_TARGETABLE,0,0,0,0};
static unsigned random_state=1;
static unsigned next_random(void) {return random_state=random_state*1664525u+1013904223u;}
int main(void) {
    assert(actor_sys_init(memory,sizeof(memory)));
    for(unsigned n=0;n<4000;++n) {
        unsigned slot=next_random()%ACTOR_POOL_MAX;
        if(next_random()&4) {
            unsigned first=0;
            while(first<ACTOR_POOL_MAX && memory[first].profile) ++first;
            actor_t *a=actor_spawn(&passive,1,slot&1,slot,0,0,0,0);
            assert(first==ACTOR_POOL_MAX ? !a : a==&memory[first]);
            if(a) a->attention=ATTN_NPC;
        } else actor_kill(&memory[slot]);
        unsigned live=0,end=0,found=0;actor_t *a=0;
        for(unsigned j=0;j<ACTOR_POOL_MAX;++j) {
            assert(actor_sys_slot(j)==(memory[j].profile?&memory[j]:0));
            if(memory[j].profile) {
                ++live;end=j+1;
                assert(actor_resolve(actor_handle(&memory[j]))==&memory[j]);
            }
        }
        assert(pool_end==end && actor_sys_live()==live);
        while((a=actor_sys_find(5,a))) ++found;
        assert(found==live);
        actor_t *best=actor_sys_nearest_attention(0,0,0,100,1u<<ATTN_NPC);
        if(best) for(unsigned j=0;j<ACTOR_POOL_MAX;++j)
            assert(!memory[j].profile || best->x<=memory[j].x);
        if(!(n%61)) actor_sys_room_unload(1);
        if(!(n%109)) actor_sys_scene_unload();
        if(!(n%251)) actor_sys_clear();
    }
    actor_sys_clear();assert(!pool_end && !actor_sys_live());
    for(unsigned j=0;j<ACTOR_POOL_MAX;++j)
        assert(actor_spawn(&passive,0,0,0,0,0,0,0)==&memory[j]);
    assert(!actor_spawn(&passive,0,0,0,0,0,0,0));
    for(unsigned j=0;j<ACTOR_POOL_MAX;++j)actor_kill(&memory[j]);
    assert(!pool_end);
    assert(actor_sys_init(memory,sizeof(memory)) && !pool_end);
    return 0;
}
''')

    def test_update_matches_full_scan_with_callback_spawns_kills_and_profile_changes(self):
        self.run_c(self.actor_source() + r'''
static actor_t memory[ACTOR_POOL_MAX];
static actor_profile_t profiles[ACTORCAT_MAX];
static unsigned trace[512],trace_count,destroy_spawn;
static void callback(actor_t *a) {
    trace[trace_count++]=(unsigned)(a-memory)*16u+a->profile->category;
    if(a->params==1) {
        a->params=0;
        actor_spawn(&profiles[ACTORCAT_NPC],0,0,0,0,0,0,0);
        actor_spawn(&profiles[ACTORCAT_SWITCH],0,0,0,0,0,0,0);
    } else if(a->params==2) {
        a->params=0;actor_kill(&memory[2]);actor_kill(a);
    } else if(a->params==3) {
        a->params=0;memory[2].profile=&profiles[ACTORCAT_CHEST];
    } else if(a->params==4) {
        a->params=0;
        actor_spawn(&profiles[a->profile->category],0,0,0,0,0,0,0);
        actor_spawn(&profiles[a->profile->category],0,0,0,0,0,0,0);
    }
}
static void destroyed(actor_t *a) {
    trace[trace_count++]=0x10000u+(unsigned)(a-memory);
    if(destroy_spawn) {
        destroy_spawn=0;
        actor_spawn(&profiles[ACTORCAT_ENEMY],0,0,0,0,0,0,0);
    }
}
/* Original fixed-capacity category traversal, independent of the bound and
 * no-callback shortcut under test. */
static void reference_update(void) {
    for(unsigned i=0;i<ACTOR_POOL_MAX;++i)
        if(memory[i].profile && memory[i].filter_timer)--memory[i].filter_timer;
    updating=true;
    for(unsigned cat=0;cat<ACTORCAT_MAX;++cat)
        for(unsigned i=0;i<ACTOR_POOL_MAX;++i) {
            actor_t *a=&memory[i];
            if(a->profile && !a->kill && a->profile->category==cat && a->profile->update)
                a->profile->update(a);
        }
    updating=false;
    for(unsigned i=0;i<ACTOR_POOL_MAX;++i)
        if(memory[i].profile && memory[i].kill)destroy(&memory[i]);
}
static unsigned result[1024];
static unsigned run(unsigned scenario,unsigned mode) {
    assert(actor_sys_init(memory,sizeof(memory)));
    trace_count=destroy_spawn=0;
    for(unsigned i=0;i<ACTORCAT_MAX;++i)
        profiles[i]=(actor_profile_t){i+1,i,0,0,callback,0,destroyed};
    actor_spawn(&profiles[ACTORCAT_NPC],0,0,0,0,0,0,0);
    actor_spawn(&profiles[ACTORCAT_NPC],0,0,0,0,0,0,scenario);
    actor_spawn(&profiles[ACTORCAT_ENEMY],0,0,0,0,0,0,0);
    actor_spawn(&profiles[ACTORCAT_SWITCH],0,0,0,0,0,0,0);
    if(scenario==4) actor_kill(&memory[0]); /* a new earlier slot must wait */
    if(scenario==5) {
        for(unsigned i=0;i<ACTORCAT_MAX;++i)profiles[i].update=0;
        memory[0].kill=1;destroy_spawn=1;
    }
    for(unsigned i=0;i<4;++i)memory[i].filter_timer=3;
    actor_update_slow=mode==2;
    for(unsigned step=0;step<3;++step)
        if(mode==1)reference_update();else actor_sys_update();
    unsigned n=0;
    result[n++]=trace_count;
    for(unsigned i=0;i<trace_count;++i)result[n++]=trace[i];
    result[n++]=actor_sys_live();
    for(unsigned i=0;i<ACTOR_POOL_MAX;++i) {
        actor_t *a=&memory[i];
        result[n++]=a->profile?a->profile->id:0;
        result[n++]=a->params;result[n++]=a->filter_timer;
    }
    return n;
}
int main(void) {
    unsigned expected[1024];
    for(unsigned scenario=0;scenario<=5;++scenario) {
        unsigned n=run(scenario,1);memcpy(expected,result,n*sizeof(unsigned));
        for(unsigned mode=0;mode<=2;mode+=2) {
            assert(run(scenario,mode)==n);
            assert(!memcmp(expected,result,n*sizeof(unsigned)));
        }
    }
    return 0;
}
''')

    def test_npc_sync_fetches_view_once_and_preserves_live_and_legacy_proxies(self):
        source = self.actor_source() + r'''
#define DOSEI_OOT_CORE
#define KOKIRI_NPC_COUNT 5
#define KOKIRI_NPC_SARIA 1
#define KOKIRI_NPC_MIDO 2
#define GP_NPC_FOCUS_Y 40
#define GP_NPC_ARROW_Y 0
typedef struct {int scene,kind,param,x,y,z;} kokiri_npc_t;
typedef struct {int id,params,alpha,x,y,z;} OotCoreNpcView;
static kokiri_npc_t kokiri_npcs[5]={{1,3,4,1,2,3},{1,2,0,4,5,6},
    {1,1,0,7,8,9},{2,3,4,10,11,12},{1,3,9,13,14,15}};
static OotCoreNpcView views[3]={{0x163,4,255,100,200,300},
    {0x16d,0,255,400,500,600},{0x163,9,0,700,800,900}};
static unsigned owns=1,reads;
static actor_t memory[ACTOR_POOL_MAX];
static actor_handle_t npc_actor[KOKIRI_NPC_COUNT];
static unsigned npc_turned;
static const actor_profile_t npc_profile={123,ACTORCAT_NPC,ACTOR_FLAG_TARGETABLE,0,0,0,0};
static bool oot_core_owns_kokiri_npcs(void) {return owns;}
static int oot_core_npcs(const OotCoreNpcView **out) {++reads;*out=views;return 3;}
static const kokiri_npc_t *npc_at(int i) {return &kokiri_npcs[i];}
static bool gameplay_npc_present(unsigned i) {
    return kokiri_npcs[i].scene==save_state.scene_id &&
        (!owns || kokiri_npcs[i].kind==KOKIRI_NPC_SARIA);
}
'''
        path = ROOT / 'src/gameplay.c'
        source += function(path, 'static const OotCoreNpcView *core_npc_for(') + '\n'
        source += function(path, 'static void         sync_npc_actors(') + '\n'
        source += r'''
int main(void) {
    assert(actor_sys_init(memory,sizeof(memory)));save_state.scene_id=1;
    sync_npc_actors();assert(reads==1 && actor_sys_live()==3);
    assert(actor_resolve(npc_actor[0])->x==100);
    assert(actor_resolve(npc_actor[1])->y==500);
    assert(actor_resolve(npc_actor[2])->z==9);
    assert(!npc_actor[3] && !npc_actor[4]);
    actor_handle_t old=npc_actor[0];
    views[0].x=101;views[2].alpha=255;
    sync_npc_actors();assert(reads==2 && actor_sys_live()==4);
    assert(npc_actor[0]==old && actor_resolve(old)->x==101);
    assert(actor_resolve(npc_actor[4])->z==900);
    views[0].alpha=0;sync_npc_actors();
    assert(reads==3 && !npc_actor[0] && !actor_resolve(old));
    owns=0;sync_npc_actors();assert(reads==3 && actor_sys_live()==4);
    assert(actor_resolve(npc_actor[0])->x==1);
    assert(actor_resolve(npc_actor[1])->y==5);
    assert(actor_resolve(npc_actor[4])->z==15);
    save_state.scene_id=2;owns=1;sync_npc_actors();
    assert(reads==4 && actor_sys_live()==0);
    owns=0;sync_npc_actors();
    assert(reads==4 && actor_sys_live()==1 && actor_resolve(npc_actor[3])->x==10);
    return 0;
}
'''
        self.run_c(source)
