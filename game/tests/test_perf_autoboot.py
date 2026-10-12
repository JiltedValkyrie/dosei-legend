"""Exercise the temporary image's actual one-shot Play Test entry hook."""
import unittest
from test_graphics_backend import ROOT, function
import test_graphics_backend as graphics


class PerfAutoboot(unittest.TestCase):
    run_c = graphics.GraphicsBackend.run_c

    def test_ground_spawn_is_test_only_and_shared_by_scene_load_and_player(self):
        source = r'''
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#define SCENE_SPOT04 1
#define SAVE_FILE_SLOTS 3
#define RECOMP_LINK_EYE_HEIGHT 40
#define KOKIRI_PORTAL_COUNT 0
#define BG_IGNORE_ENTITY 0
#define BG_Y_MIN -30000
typedef struct {int32_t x,y,z;} camera_position_t;
typedef camera_position_t bg_vec_t;
typedef struct {unsigned spawns;} scene_entry_t;
typedef struct {unsigned room;} scene_spawn_t;
typedef struct {int scene,front,back,kind,x,y,z,yaw;} kokiri_portal;
static const kokiri_portal kokiri_portals[1];
static scene_entry_t scene_entries[3]={{1},{12},{1}};
static scene_spawn_t point={0};
static struct {unsigned scene,room;bool failed,visible;} level_select;
static struct {unsigned entrance,day_time;} save_state;
static unsigned active_slot,mode,loaded_scene,loaded_spawn,placed_scene,placed_spawn,sequence;
static bool save_reported;
static camera_position_t recomp_link,link_safe_position;
static unsigned recomp_link_yaw;
static int link_fall_peak_y;
enum {GAME_MODE_LOADING,GAME_MODE_FILE_SELECT,GAME_MODE_PLAY};
static const scene_spawn_t *scene_flow_spawn(unsigned scene,unsigned spawn) {
    point.room=0;return &point;
}
static void kokiri_camera_sincos(unsigned yaw,int32_t *sn,int32_t *cs) {*sn=0;*cs=65536;}
static void level_select_prepare(void) {save_state.entrance=0;sequence=1;}
static void health_hud_magic_start(void) {}
static void oot_core_session_reset(unsigned time) {assert(sequence==1);sequence=2;}
static void minimap_session_reset(void) {}
static void game_mode_set(unsigned value) {mode=value;}
static bool scene_flow_load(unsigned scene,unsigned spawn) {
    assert(sequence==2 && save_state.entrance==spawn && mode==GAME_MODE_LOADING);
    loaded_scene=scene;loaded_spawn=spawn;sequence=3;return true;
}
static bool kokiri_scene_load_bank(unsigned scene,unsigned room) {return true;}
static void place_at_spawn(unsigned scene,unsigned spawn) {
    assert(sequence==3);placed_scene=scene;placed_spawn=spawn;sequence=4;
}
static int bg_floor(bg_vec_t *p,unsigned flags,unsigned unused) {return 0;}
static void snap_camera_to_link(void) {}
static void gameplay_reset(void) {assert(sequence==4);}
static void scene_music(void) {}
'''
        source += function(ROOT / 'src/recomp.c', 'static void __attribute__((optimize("Os"))) level_select_enter(')
        source += r'''
int main(void) {
    level_select.scene=SCENE_SPOT04;level_select.room=0;
    level_select_enter();
#if defined(DOSEI_BOOT_KOKIRI_TEST) && !defined(DOSEI_CLEAN_TEST)
    assert(save_state.entrance==9 && loaded_spawn==9 && placed_spawn==9);
#else
    assert(save_state.entrance==0 && loaded_spawn==0 && placed_spawn==0);
#endif
    assert(loaded_scene==SCENE_SPOT04 && placed_scene==SCENE_SPOT04 && mode==GAME_MODE_PLAY);
    assert(active_slot==SAVE_FILE_SLOTS);
    level_select.scene=2;level_select_enter();
    assert(save_state.entrance==0 && loaded_spawn==0 && placed_spawn==0);
    return 0;
}
'''
        for definitions in ('', '#define DOSEI_BOOT_KOKIRI_TEST 1\n',
                            '#define DOSEI_BOOT_KOKIRI_TEST 1\n#define DOSEI_CLEAN_TEST 1\n'):
            with self.subTest(definitions=definitions):
                self.run_c(definitions + source)

    def test_autoboot_uses_legal_menu_transition_and_discards_boot_input_time(self):
        source = r'''
#include <assert.h>
#include <stdbool.h>
'''
        source += '#include "%s"\n' % (ROOT / 'src/game_mode.c').as_posix()
        source += '#include "%s"\n' % (ROOT / 'src/input_edge.h').as_posix()
        source += r'''
#define SCENE_SPOT04 1
#define NBG0ON 1u
static struct {unsigned scene,room;bool adult,max_gear;} level_select;
static input_edge_t start_edge;
static unsigned ticks=1000,previous_tick,layers,entries,resets,clears;
static bool interact_pending=true,cancel_pending=true,pause_pending=true,jump_pending=true;
static void level_select_open(void) {
    level_select.scene=7;level_select.room=5;
    level_select.adult=level_select.max_gear=true;
}
static void level_select_enter(void) {
    assert(game_mode()==GAME_MODE_FILE_SELECT);
    assert(level_select.scene==SCENE_SPOT04 && !level_select.room);
    assert(!level_select.adult && !level_select.max_gear);
    assert(game_mode_set(GAME_MODE_LOADING));
    assert(game_mode_set(GAME_MODE_PLAY));
    ticks+=500; ++entries;
}
static void player_input_reset(void) {++resets;}
static void jo_clear_screen(void) {++clears;}
static unsigned minimap_layer_flags(void) {return 4u;}
static void slScrAutoDisp(unsigned value) {layers=value;}
'''
        source += function(ROOT / 'src/recomp.c', 'static bool recomp_boot_kokiri_test(')
        source += r'''
int main(void) {
    input_edge_sample(&start_edge,true);
    assert(recomp_boot_kokiri_test());
    assert(game_mode()==GAME_MODE_PLAY && entries==1 && resets==1 && clears==1);
    assert(previous_tick==1500 && previous_tick==ticks && layers==5u);
    assert(!input_edge_consume(&start_edge));
    assert(!interact_pending && !cancel_pending && !pause_pending && !jump_pending);
    ticks+=10;assert(!recomp_boot_kokiri_test());
    assert(entries==1 && resets==1 && clears==1 && previous_tick==1500);
    return 0;
}
'''
        self.run_c(source)
