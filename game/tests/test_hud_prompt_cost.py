"""Prompt angle rejection and complete HUD profiling on real runtime functions."""
import re
import unittest
from test_graphics_backend import ROOT, function
import test_graphics_backend as graphics


class HudPromptCost(unittest.TestCase):
    run_c = graphics.GraphicsBackend.run_c

    def test_sign_prompt_matches_original_boundaries_without_distant_angles(self):
        path = ROOT/'src/world_signs.c'
        source = r'''
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <math.h>
#define KOKIRI_SIGN_COUNT 10
#define OOT_SIGN_INTACT 65535u
#define SAVE_SCENE_KOKIRI_FOREST 0x55
typedef struct {int x,y,z,room;uint16_t yaw;} gameplay_input_t;
typedef struct {int x,y,z,room;} kokiri_prop_t;
static kokiri_prop_t kokiri_signs[KOKIRI_SIGN_COUNT];
static uint16_t kokiri_sign_yaws[KOKIRI_SIGN_COUNT],kokiri_sign_params[KOKIRI_SIGN_COUNT];
static uint16_t visual[KOKIRI_SIGN_COUNT],core_visual[KOKIRI_SIGN_COUNT];
static gameplay_input_t last_sign_in;
static struct {unsigned scene_id;} save_state;
static unsigned angles,queries;
static bool core_owned;
static bool oot_core_owns_kokiri_npcs(void) {return core_owned;}
static unsigned world_signs_visual(unsigned i) {++queries;return core_owned?core_visual[i]:visual[i];}
static uint16_t gameplay_facing(int x,int z) {
    ++angles;return (uint16_t)(int32_t)lround(atan2((double)x,(double)z)*32768.0/3.14159265358979323846);
}
'''
        source += function(path, 'unsigned int world_signs_text(')
        source += function(path, 'bool world_signs_near(')
        source += r'''
/* Original predicate/order: atan was called twice even for every far sign. */
static unsigned original(const gameplay_input_t *in,bool text) {
    if(save_state.scene_id!=SAVE_SCENE_KOKIRI_FOREST || (text && core_owned))return 0;
    for(unsigned i=0;i<KOKIRI_SIGN_COUNT;++i) {
        const kokiri_prop_t *p=&kokiri_signs[i];
        int dx=in->x-p->x,dz=in->z-p->z,dy=in->y-p->y;
        int16_t facing=(int16_t)(gameplay_facing(-dx,-dz)-in->yaw);
        int16_t side=(int16_t)(gameplay_facing(dx,dz)-kokiri_sign_yaws[i]);
        if(p->room==in->room && (!text || visual[i]==OOT_SIGN_INTACT) &&
           dx>-70 && dx<70 && dz>-70 && dz<70 && dx*dx+dz*dz<4900 &&
           dy>-40 && dy<60 && facing>-0x4000 && facing<0x4000 &&
           side>-0x4000 && side<0x4000 && (text || world_signs_visual(i)==OOT_SIGN_INTACT))
            return text?(kokiri_sign_params[i]|0x300):1;
    }
    return 0;
}
static void check(void) {
    unsigned expected_text=original(&last_sign_in,true);
    queries=0;
    bool expected_near=original(&last_sign_in,false);
    unsigned expected_queries=queries;
    angles=queries=0;
    assert(world_signs_near()==expected_near);
    assert(queries==expected_queries && angles<=2); /* at most one reachable sign */
    angles=queries=0;
    assert(world_signs_text(&last_sign_in)==expected_text && angles<=2);
}
int main(void) {
    static const int xy[]={-71,-70,-69,-50,-49,-1,0,1,49,50,69,70,71};
    static const int heights[]={-41,-40,-39,0,59,60,61};
    static const uint16_t yaws[]={0,1,0x3fff,0x4000,0x4001,0x7fff,0x8000,0xbfff,0xc000,0xc001,0xffff};
    static const uint16_t states[]={OOT_SIGN_INTACT,12,8,1,0};
    save_state.scene_id=SAVE_SCENE_KOKIRI_FOREST;
    for(unsigned i=0;i<KOKIRI_SIGN_COUNT;++i) {
        kokiri_signs[i]=(kokiri_prop_t){500+(int)i*1000,100,500,0};
        kokiri_sign_params[i]=(uint16_t)(0x50+i);
        visual[i]=core_visual[i]=OOT_SIGN_INTACT;
    }
    for(unsigned own=0;own<2;++own)
    for(unsigned state=0;state<5;++state)
    for(unsigned yaw=0;yaw<sizeof(yaws)/sizeof(*yaws);++yaw)
    for(unsigned y=0;y<sizeof(heights)/sizeof(*heights);++y)
    for(unsigned x=0;x<sizeof(xy)/sizeof(*xy);++x)
    for(unsigned z=0;z<sizeof(xy)/sizeof(*xy);++z) {
        core_owned=own;visual[0]=core_visual[0]=states[state];
        last_sign_in=(gameplay_input_t){500+xy[x],100+heights[y],500+xy[z],0,yaws[yaw]};
        check();
    }
    /* Different sign orientations/text ids, wrong rooms and nonforest scenes. */
    for(unsigned i=0;i<KOKIRI_SIGN_COUNT;++i) {
        core_owned=false;visual[i]=OOT_SIGN_INTACT;
        for(unsigned yaw=0;yaw<sizeof(yaws)/sizeof(*yaws);++yaw) {
            kokiri_sign_yaws[i]=yaws[yaw];
            last_sign_in=(gameplay_input_t){kokiri_signs[i].x,100,550,0,0x8000};
            check();last_sign_in.room=1;check();
            angles=0;assert(!world_signs_near() && !angles);
        }
    }
    last_sign_in=(gameplay_input_t){-10000,100,-10000,0,0};
    angles=queries=0;assert(!world_signs_near() && !angles && !queries);
    assert(!world_signs_text(&last_sign_in) && !angles);
    save_state.scene_id=0;check();
    return 0;
}
'''
        self.run_c(source)

    def minimap_fixture(self):
        body = function(ROOT/'src/minimap.c', 'uint32_t minimap_layer_flags(')
        # Same uninstrumented control flow: prove profiling changes no calls,
        # short circuits, pause restoration, HUD state or returned layer flags.
        reference = re.sub(r'PS_(?:T0|ADD)\([^)]*\);', '', body)
        reference = reference.replace('minimap_layer_flags(', 'original_layer_flags(')
        source = '#include "%s"\n' % (ROOT/'src/perf_sub.h').as_posix()
        source += r'''
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <string.h>
unsigned perf_sub[PS_COUNT];
static unsigned clock_ticks;
unsigned frame_timer_ticks(void) {return clock_ticks;}
unsigned frame_timer_ticks_to_us(unsigned n) {return n;}
static char trace[1024];static unsigned trace_n;
static unsigned call(char tag,unsigned cost) {trace[trace_n++]=tag;clock_ticks+=cost;return 0;}
#define NBG0ON 1u
#define NBG2ON 4u
#define GP_SWORD 1u
#define UI_KEY_A 0
#define UI_KEY_X 1
static bool hud_ready=true,recomp_link_active=true;
static bool paused,title,file_select,cutscene,talking,carrying,hide;
static unsigned jump_key=UI_KEY_X;
static int hud_blink;
static struct {unsigned save_scene;} map_row={3},*row=&map_row;
static struct {bool navi_calling,shop_prompt;int chest_prompt,prompt;unsigned equipped;} gameplay={false,false,-1,-1,GP_SWORD};
static bool gameplay_is_paused(void) {call('p',1);return paused;}
static bool recomp_title_is_visible(void) {call('t',1);return title;}
static bool recomp_file_select_is_visible(void) {call('f',1);return file_select;}
static bool cutscene_is_playing(void) {call('c',1);return cutscene;}
static bool gameplay_is_talking(void) {call('k',1);return talking;}
static bool pause_windows_update(void) {call('P',500);return !hide;}
static void pause_windows_reset(void) {call('R',600);}
static void minimap_scene(unsigned scene) {call('S',700);assert(scene==(row?row->save_scene:~0u));}
static unsigned recomp_clock(void) {call('C',1);return 123;}
static bool gameplay_hud_blink(int *b,unsigned tick,bool navi,bool visible) {call(visible?'B':'b',1);return navi&&visible;}
static bool world_props_carrying(void) {call('w',1);return carrying;}
static bool recomp_enter_prompt(void) {call('e',1);return false;}
static bool dungeon_doors_prompt(void) {call('d',1);return false;}
static bool world_signs_near(void) {call('s',97);return false;}
static bool world_props_near_liftable(void) {call('l',1);return false;}
static bool recomp_push_prompt(void) {call('u',1);return true;}
static bool recomp_lift_hold_actionable(void) {call('a',1);return false;}
static bool recomp_lift_throw_ready(void) {call('r',1);return false;}
static unsigned gameplay_hud_action(bool e,bool chest,bool talk,bool sign,bool lift,bool hold,bool throw_ready) {
    call('A',1);return e?1:chest?2:talk?3:sign?4:lift?5:hold?6:throw_ready?7:0;
}
static unsigned ui_jump_key(void) {call('j',1);return jump_key;}
static void health_hud_draw(bool visible) {call(visible?'H':'h',10000);}
static void map_visibility(bool visible) {call(visible?'M':'m',20000);}
static void hud_visibility(int variant) {call((char)('0'+variant),30000);}
static bool shown(void) {call('v',2);return row&&!hide&&recomp_link_active&&!title&&!file_select&&!cutscene&&!talking&&!paused;}
'''
        source += body + '\n' + reference
        source += r'''
static void check(void) {
    char saved[1024];unsigned start=clock_ticks;
    trace_n=0;memset(perf_sub,0,sizeof(perf_sub));
    uint32_t actual=minimap_layer_flags();
    unsigned elapsed=clock_ticks-start;
    assert(perf_sub[PS_HQUERY]+perf_sub[PS_HHEALTH]+perf_sub[PS_HVIS]==elapsed);
    if(paused && recomp_link_active) {
        assert(perf_sub[PS_HVIS]==501 && !perf_sub[PS_HQUERY] && !perf_sub[PS_HHEALTH]);
    } else {
        assert(perf_sub[PS_HQUERY]>=97 && perf_sub[PS_HQUERY]<200);
#ifdef DOSEI_HIRES
        assert(!perf_sub[PS_HHEALTH]);
#else
        assert(perf_sub[PS_HHEALTH]==(hud_ready?10000:0));
        if(hud_ready)assert(perf_sub[PS_HVIS]>=50005);
#endif
    }
    unsigned length=trace_n;memcpy(saved,trace,length);
    start=clock_ticks;trace_n=0;
    assert(original_layer_flags()==actual && clock_ticks-start==elapsed);
    assert(trace_n==length && !memcmp(saved,trace,length));
}
int main(void) {
    check();paused=true;check();hide=true;check();
    paused=false;check(); /* pause reset+scene restoration are visibility cost */
    hide=false;hud_ready=false;check();hud_ready=true;
    title=true;check();title=false;file_select=true;check();file_select=false;
    talking=true;check();talking=false;cutscene=true;check();cutscene=false;
    recomp_link_active=false;check();paused=true;check();paused=false;
    recomp_link_active=true;carrying=true;check();carrying=false;
    gameplay.chest_prompt=1;gameplay.prompt=1;gameplay.navi_calling=true;check();
    jump_key=UI_KEY_A;check();jump_key=UI_KEY_X;check();
    paused=true;check();row=0;paused=false;check();
    return 0;
}
'''
        return source

    def test_hud_timers_cover_normal_hidden_pause_and_reload_paths(self):
        self.run_c(self.minimap_fixture())

    def test_hires_query_only_path_is_accounted(self):
        self.run_c('#define DOSEI_HIRES 1\n'+self.minimap_fixture())


if __name__ == '__main__':
    unittest.main()
