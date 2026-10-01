"""Real shutter rules and source web collision against host DynaPoly."""
import ctypes as C
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[1]
GCC=Path('C:/msys64/mingw64/bin/gcc.exe')
@unittest.skipUnless(GCC.exists(),'host compiler required')
class Mechanisms(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        folder=Path(cls.tmp.name)
        doors=(ROOT/'src/dungeon_doors.c').read_text().replace('#include <jo/jo.h>','').replace('#include "kokiri_scene.h"','')
        pre=r'''#include <stdint.h>
#include <math.h>
#include "gameplay.h"
#include "attention.h"
#include "save_state.h"
#include "kokiri_collision.h"
#include "dungeon_webs.h"
#include "dungeon_torches.h"
#include "dungeon_puzzles.h"
#include "collide.h"
#include "skulltula.h"
#include "wall_skull.h"
#include "dekubaba.h"
#include "hintnuts.h"
#include "gohma_larva.h"
bool gameplay_actor_message(uint16_t text) {gameplay.talking=true;return text!=0;}
bool gameplay_ball_move(int32_t p[3],int32_t x,int32_t y,int32_t z) {p[0]+=x;p[1]+=y;p[2]+=z;return false;}
void gameplay_drop_message(unsigned item) {(void)item;}
bool gameplay_token_message(void) {return true;}
void collide_world_push(actor_t *a,int32_t dx,int32_t dz) {a->x+=dx;a->z+=dz;}
static unsigned reward_count,reward_item;
bool world_props_enemy_drop(int32_t x,int32_t y,int32_t z,unsigned item,unsigned count) {(void)x;(void)y;(void)z;reward_count+=count;reward_item=item;return true;}
uint16_t collide_heading(int32_t x,int32_t z) {return (uint16_t)(int32_t)(atan2(x,z)*65536/6.283185307179586);}
static unsigned burn;
bool player_items_stick(void) {return true;}
unsigned player_items_burning(void) {return burn;}
void player_items_ignite(void) {burn=315;}
typedef struct {short front,back,x,y,z,yaw;unsigned char scene,kind,flag;} kokiri_portal;
#define KOKIRI_PORTAL_COUNT 1
static kokiri_portal kokiri_portals[1]={{0,1,0,0,0,0,7,9,3}};
static unsigned loaded_scene=7;
unsigned scene_flow_scene(void) {return loaded_scene;}
void set_loaded_scene(unsigned scene) {loaded_scene=scene;}
gameplay_t gameplay;
void kokiri_camera_sincos(uint16_t yaw,int32_t *s,int32_t *c) {
    *s=(int32_t)round(sin(yaw*6.283185307179586/65536)*65536);
    *c=(int32_t)round(cos(yaw*6.283185307179586/65536)*65536);
}
'''
        post=r'''
static unsigned char dyna[0x4800];
static actor_t actor_pool[ACTOR_POOL_MAX];
static uint64_t skull_storage[512];
static uint64_t wall_storage[256];
static uint64_t baba_storage[512];
static uint64_t hint_storage[512];
static uint64_t goma_storage[512];
static bg_mesh_t empty;
uint16_t gameplay_facing(int32_t x,int32_t z){return collide_heading(x,z);}
unsigned sfx_take(void) {unsigned e=gameplay.world_sfx;gameplay.world_sfx=0;return e;}
bool attention_sight_blocked(const int32_t a[3],const int32_t b[3]){(void)a;(void)b;return false;}
bool attention_on_screen(const int32_t p[3]){(void)p;return true;}
int hint_target(int distance){actor_t *a=actor_sys_find(0x192,0);if(!a)return 0;int32_t feet[3]={a->x,a->y,a->z-distance},focus[3]={a->x,a->y+44,a->z-distance};return attention_find(feet,focus,0,0)==a;}
void reset(void) {gameplay.world_sfx=0;hintnuts_reset();skulltula_reset();wall_skull_reset();dekubaba_reset();dungeon_webs_reset();dungeon_torches_reset();dungeon_puzzles_reset();actor_sys_init(actor_pool,sizeof(actor_pool));skulltula_init(skull_storage,sizeof(skull_storage));wall_skull_init(wall_storage,sizeof(wall_storage));dekubaba_init(baba_storage,sizeof(baba_storage));hintnuts_init(hint_storage,sizeof(hint_storage));gameplay.talking=false;burn=0;reward_count=0;bg_dyna_init(dyna,sizeof(dyna));bg_scene_set(&empty);save_new_game();dungeon_doors_reset();save_state.scene_id=2;}
void hint_step(int room,int x,int y,int z,int talk) {gameplay_input_t in={0};in.room=room;in.x=x;in.y=y;in.z=z;in.interact=talk;hintnuts_step(&in);}
void goma_reset(void) {gohma_larva_reset();gohma_larva_init(goma_storage,sizeof(goma_storage));save_state.scene_id=SAVE_SCENE_DEKU_TREE;}
void goma_step(int x,int z) {gameplay_input_t in={0};in.room=7;in.x=x;in.y=-400;in.z=z;gohma_larva_step(&in);}
int goma_kind(unsigned i) {int32_t p[3],scale;uint16_t yaw;unsigned frame;return gohma_larva_body(i,p,&yaw,&frame,&scale);}
int goma_hit(unsigned index,unsigned dmg) {
    collider_t weapon={0};actor_t *a=0;unsigned n=0;
    while((a=actor_sys_find(0x2B,a)))if(n++==index)break;
    if(!a)return 0;
    weapon.shape=COLSHAPE_CYLINDER;weapon.radius=20;weapon.height=40;weapon.x=a->x;weapon.y=a->y;weapon.z=a->z;
    weapon.at_type=AT_TYPE_PLAYER;weapon.at_dmg=dmg;weapon.ac_flags=COL_OUTSIDE_ACTOR;
    collide_begin();collide_set_at(&weapon);gohma_larva_register();collide_run();gohma_larva_collect();return weapon.result;
}
int hint_hit(unsigned index,int reflected) {
    static collider_t ball;actor_t *a=0;unsigned n=0;
    while((a=actor_sys_find(0x192,a)))if(n++==index)break;
    if(!a)return 0;memset(&ball,0,sizeof(ball));
    ball.shape=COLSHAPE_CYLINDER;ball.radius=10;ball.height=15;ball.x=a->x;ball.y=a->y+10;ball.z=a->z;
    ball.at_type=AT_TYPE_PLAYER;ball.at_dmg=DMG_DEKU_STICK;ball.ac_flags=COL_OUTSIDE_ACTOR;ball.tag=reflected?0x7700:123;
    collide_begin();collide_set_at(&ball);hintnuts_register();collide_run();hintnuts_collect();return ball.result;
}
int hint_pos(unsigned index,unsigned axis) {int32_t p[3];uint16_t yaw;unsigned frame;return hintnuts_body(index,p,&yaw,&frame)?p[axis]:-99999;}
void hint_close(void) {gameplay.talking=false;}
int hint_clear(int room) {return save_get_clear(SAVE_SCENE_DEKU_TREE,room);}
int hint_balls(void) {unsigned i,n=0;int32_t p[3];uint16_t roll;for(i=0;i<HINTNUTS_BALLS;++i)n+=hintnuts_ball(i,p,&roll);return n;}
void flat_ground(int y) {
    static collision_triangle_t tri[2]={{{{-4000,0,-4000},{4000,0,4000},{4000,0,-4000}},{0,16384,0},{-4000,0,-4000},{4000,0,4000}},{{{-4000,0,-4000},{-4000,0,4000},{4000,0,4000}},{0,16384,0},{-4000,0,-4000},{4000,0,4000}}};
    static bg_mesh_t mesh;unsigned i,j;for(i=0;i<2;++i){for(j=0;j<3;++j)tri[i].vertex[j][1]=y;tri[i].minimum[1]=tri[i].maximum[1]=y;}
    mesh.triangles=tri;mesh.triangle_count=2;bg_scene_set(&mesh);
}
void baba_step(int x,int y,int z) {gameplay_input_t in={0};in.x=x;in.y=y;in.z=z;in.grounded=true;dekubaba_step(&in);}
int baba_pos(unsigned axis) {const dekubaba_view *v=dekubaba_body(0);return v?v->head[axis]:-99999;}
int baba_pruned(void) {const dekubaba_view *v=dekubaba_body(0);return v?v->pruned:0;}
int baba_hit(unsigned dmg) {
    collider_t sword={0};actor_t *a=actor_sys_find(0x55,0);if(!a)return 0;
    sword.shape=COLSHAPE_CAPSULE;sword.radius=5;
    sword.ax=a->x-30;sword.bx=a->x+30;sword.ay=sword.by=a->y;sword.az=sword.bz=a->z;
    sword.x=a->x;sword.y=a->y;sword.z=a->z;sword.at_type=AT_TYPE_PLAYER;sword.at_dmg=dmg;sword.at_damage=1;sword.ac_flags=COL_OUTSIDE_ACTOR;
    collide_begin();collide_set_at(&sword);dekubaba_register();collide_run();dekubaba_collect();return sword.result;
}
int capsules(int mode) {
    collider_t a={0},b={0};a.shape=b.shape=COLSHAPE_CAPSULE;a.radius=b.radius=5;
    a.ax=-40;a.bx=40;
    if(mode==0) {b.az=-40;b.bz=40;}
    if(mode==1) {b.az=b.bz=11;b.ax=-40;b.bx=40;}
    if(mode==2) {b.az=b.bz=9;b.ax=-40;b.bx=40;}
    if(mode==3) {b.ax=b.bx=49;}
    if(mode==4) {b.ax=b.bx=50;}
    if(mode==5) {a.ax=a.bx=0;b.ay=b.by=9;}
    if(mode==6) {a.ax=a.bx=0;b.ay=b.by=11;}
    return collide_overlap(&a,&b,0) && collide_overlap(&b,&a,0);
}
int rewards(void) {return reward_count;}
int reward_type(void) {return reward_item;}
int sticks(void) {return save_state.stick_ammo;}
void wall_sk_step(int room,int x,int y,int z,int climbing) {gameplay_input_t in={0};in.room=room;in.x=x;in.y=y;in.z=z;in.climbing=climbing;wall_skull_step(&in);}
int wall_sk_kind(unsigned i) {int32_t p[3];uint16_t yaw,roll;unsigned frame;return wall_skull_body(i,p,&yaw,&roll,&frame);}
int wall_sk_hit(unsigned dmg) {
    collider_t sword={0};actor_t *a=actor_sys_find(0x95,0);if(!a)return 0;
    sword.shape=COLSHAPE_CYLINDER;sword.radius=25;sword.height=60;sword.y_shift=-30;
    sword.x=a->x;sword.y=a->y;sword.z=a->z;sword.at_type=AT_TYPE_PLAYER;sword.at_dmg=dmg;sword.at_damage=1;sword.ac_flags=COL_OUTSIDE_ACTOR;
    collide_begin();collide_set_at(&sword);wall_skull_register();collide_run();wall_skull_collect();return sword.result;
}
void skull_step(int room,int x,int y,int z) {gameplay_input_t in={0};in.room=room;in.x=x;in.y=y;in.z=z;skulltula_step(&in);}
int skull_y(unsigned i) {int32_t p[3];uint16_t yaw,roll;unsigned frame;bool big;return skulltula_body(i,p,&yaw,&roll,&frame,&big)?p[1]:-99999;}
int skull_alive(void) {return actor_sys_live();}
int skull_hit(unsigned dmg,int side) {
    collider_t sword={0};actor_t *a=actor_sys_find(0x37,0);if(!a)return 0;
    /* Freeze source facing to isolate mask behavior from turn timing. */
    a->yaw=side?0x8000:0;
    sword.shape=COLSHAPE_CYLINDER;sword.radius=80;sword.height=100;sword.y_shift=-50;
    sword.x=a->x;sword.y=a->y;sword.z=a->z;sword.at_type=AT_TYPE_PLAYER;sword.at_dmg=dmg;sword.at_damage=1;sword.ac_flags=COL_OUTSIDE_ACTOR;
    collide_begin();collide_set_at(&sword);skulltula_register();collide_run();skulltula_collect();
    return sword.result;
}
void puzzle_step(int x,int y,int z,int grounded) {gameplay_input_t in={0};in.x=x;in.y=y;in.z=z;in.grounded=grounded;bg_dyna_step();dungeon_puzzles_step(&in);}
int puzzle_model(unsigned i) {int32_t x,y,z;uint16_t yaw,roll;return dungeon_puzzles_body(i,&x,&y,&z,&yaw,&roll);}
int puzzle_y(unsigned i) {int32_t x,y,z;uint16_t yaw,roll;dungeon_puzzles_body(i,&x,&y,&z,&yaw,&roll);return y;}
int puzzle_shot(int x,int y,int z,int ex,int ey,int ez) {int32_t a[3]={x,y,z},b[3]={ex,ey,ez};return dungeon_puzzles_shot(a,b);}
void water_scene(void) {static bg_waterbox_t water[2]={{0},{-1500,-905,800,1000,1000,5u<<13}};static bg_mesh_t mesh;mesh.water=water;mesh.water_count=2;bg_scene_set(&mesh);}
int water_y(void) {int32_t y=0;bg_water_surface(-835,1050,5,&y,0);return y;}
void torch_tip(int room,int x,int y,int z) {int32_t p[3]={x,y,z};dungeon_torches_step(2,room,p);}
int torch_lit(unsigned i) {int32_t x,y,z;uint16_t yaw;bool lit=false;dungeon_torches_body(i,&x,&y,&z,&yaw,&lit);return lit;}
int web_burn(int x,int y,int z) {int32_t p[3]={x,y,z};return dungeon_webs_burn(p);}
int door_step(int type,int room,int press,int z) {
    gameplay_input_t in={0};kokiri_portals[0].kind=8+type;
    in.room=room;in.z=z;in.yaw=z>0?0x8000:0;in.grounded=true;in.interact=press;
    return dungeon_doors_step(&in);
}
int wall(int from,int to) {int32_t x=0,z=to;door_step(1,1,0,from);dungeon_doors_constrain(&x,&z,0);return z;}
int switch_rider_delta(int x,int y,int z) {
 bg_vec_t feet={x,y+1,z};bg_hit_t hit;uint16_t yaw=0;
 bg_floor(&feet,BG_IGNORE_ENTITY,&hit);feet.y=y;
 bg_dyna_step();gameplay_input_t in={0};in.x=x;in.y=y;in.z=z;in.grounded=true;
 dungeon_puzzles_step(&in);bg_dyna_carry(hit.bg_id,&feet,&yaw);
 return (feet.x!=x || feet.z!=z) ? 32000 : feet.y-y;
}
int floor_at(int x,int y,int z) {bg_vec_t p={x,y,z};return bg_floor(&p,BG_IGNORE_ENTITY,0);}
int wall_web_hit(void) {bg_vec_t a={-1455,-740,3},b={-1255,-740,3},hit;return bg_line(&a,&b,&hit,BG_CHECK_WALL,BG_IGNORE_ENTITY,0);}
int wall_visible(unsigned i) {int32_t x,y,z;return dungeon_walls_body(i,&x,&y,&z);}
'''
        src=folder/'test.c';src.write_text(pre+doors+post)
        dll=folder/'test.dll'
        env=dict(os.environ,PATH=str(GCC.parent)+os.pathsep+os.environ.get('PATH',''))
        subprocess.run([str(GCC),'-shared','-O2','-Wall','-Wextra','-Werror','-Wno-misleading-indentation',
            '-I'+str(ROOT/'src'),'-I'+str(ROOT/'build/generated'),
            '-I'+str(ROOT.parent/'shared/lib/collision'),'-I'+str(ROOT.parent/'shared/lib/camera'),
            str(src),str(ROOT/'src/dungeon_webs.c'),str(ROOT/'src/dungeon_torches.c'),str(ROOT/'src/dungeon_puzzles.c'),str(ROOT/'src/save_state.c'),
            str(ROOT/'src/actor_sys.c'),str(ROOT/'src/attention.c'),str(ROOT/'src/push_block.c'),
            str(ROOT/'src/skulltula.c'),str(ROOT/'src/wall_skull.c'),str(ROOT/'src/collide.c'),str(ROOT/'src/item_drop.c'),
            str(ROOT/'src/dekubaba.c'),str(ROOT/'src/hintnuts.c'),str(ROOT/'src/gohma_larva.c'),
            str(ROOT.parent/'shared/lib/collision/kokiri_collision.c'),'-o',str(dll),'-lm'],check=True,env=env)
        cls.lib=C.CDLL(str(dll))
        for name in ('dungeon_webs_step','dungeon_webs_land','save_get_switch','dungeon_door_open'):
            getattr(cls.lib,name).restype=C.c_bool
    @classmethod
    def tearDownClass(cls):cls.tmp.cleanup()
    def setUp(self):
        self.lib.set_loaded_scene(7)
        self.lib.reset()

    def test_other_scene_shutter_cannot_prompt_open_or_block_movement(self):
        g=self.lib
        g.set_loaded_scene(9)
        for _ in range(24):
            self.assertEqual(g.door_step(0,0,1,-40),0)
        self.assertFalse(g.dungeon_doors_prompt())
        self.assertEqual(g.dungeon_door_height(0),0)
        self.assertEqual(g.wall(-40,40),40)
    def test_gohma_egg_break_has_no_item_drop(self):
        g=self.lib;g.goma_reset();g.flat_ground(-400);g.goma_step(0,0)
        self.assertEqual([g.goma_kind(i) for i in range(3)], [1,1,1])
        self.assertTrue(g.goma_hit(0,1 << 8)&1)
        self.assertEqual(g.goma_kind(0),0)
        self.assertEqual(g.rewards(),0)

    def test_gohma_hatches_then_two_sword_hits_kill_with_source_drop(self):
        g=self.lib;g.goma_reset();g.flat_ground(-400)
        for _ in range(80):g.goma_step(-1869,14)
        self.assertEqual(g.goma_kind(0),2)
        self.assertTrue(g.goma_hit(0,1 << 8)&1)
        for _ in range(30):g.goma_step(-1869,14)
        self.assertEqual(g.goma_kind(0),2)
        self.assertTrue(g.goma_hit(0,1 << 8)&1)
        for _ in range(100):g.goma_step(-1869,14)
        self.assertEqual(g.goma_kind(0),0)
        self.assertEqual(g.rewards(),1)
    def test_scrub_targets_at_spit_range_and_emits_source_motion_and_hit_events(self):
        g=self.lib
        for _ in range(38):g.hint_step(1,-695,400,950,0)
        self.assertTrue(g.hint_target(200))
        self.assertFalse(g.hint_target(400))
        self.assertTrue(g.sfx_take()&1) # rise
        for _ in range(50):g.hint_step(1,-695,400,950,0)
        self.assertTrue(g.sfx_take()&(1<<2)) # spit
        # Return to an exposed state before the reflected nut connects.
        for _ in range(200):
            g.hint_step(1,-695,400,950,0)
            if g.hint_hit(0,1)&1: break
        else:self.fail('scrub never became exposed')
        self.assertTrue(g.sfx_take()&(1<<4))

    def test_hint_scrub_sword_hides_but_reflection_clears_gate_and_gives_heart_after_talk(self):
        g=self.lib
        for _ in range(38):g.hint_step(1,-695,400,950,0)
        self.assertTrue(g.hint_hit(0,0)&1)
        self.assertFalse(g.hint_clear(1))
        for _ in range(65):g.hint_step(1,-695,400,950,0)
        self.assertTrue(g.hint_hit(0,1)&1)
        self.assertTrue(g.hint_clear(1))
        for _ in range(25):g.hint_step(1,-695,400,950,0)
        g.hint_step(1,g.hint_pos(0,0),400,g.hint_pos(0,2),1)
        g.hint_step(1,g.hint_pos(0,0),400,g.hint_pos(0,2),1)
        self.assertEqual(g.rewards(),0)
        g.hint_close()
        for _ in range(4):g.hint_step(1,-695,400,950,0)
        self.assertEqual((g.rewards(),g.reward_type()),(1,3))

    def test_hint_puzzle_wrong_order_resets_then_correct_order_opens_final_gate(self):
        g=self.lib
        for _ in range(38):g.hint_step(9,-600,-1880,-650,0)
        for index in (1,0,2):self.assertTrue(g.hint_hit(index,1)&1)
        for _ in range(40):g.hint_step(9,-600,-1880,-650,0)
        self.assertFalse(g.hint_clear(9))
        for _ in range(38):g.hint_step(9,-600,-1880,-650,0)
        for index in (0,1,2):self.assertTrue(g.hint_hit(index,1)&1)
        for _ in range(25):g.hint_step(9,-600,-1880,-650,0)
        for _ in range(2):g.hint_step(9,g.hint_pos(2,0),-1880,g.hint_pos(2,2),1)
        g.hint_close()
        for _ in range(160):g.hint_step(9,-600,-1880,-650,0)
        self.assertTrue(g.hint_clear(9))
        self.assertEqual((g.rewards(),g.reward_type()),(1,3))

    def test_hint_scrubs_keep_multiple_projectiles_live(self):
        g=self.lib
        for _ in range(70):g.hint_step(9,-600,-1880,-650,0)
        self.assertEqual(g.hint_balls(),3)
    def test_dekubaba_closed_head_bounces_and_lethal_seed_drops_nuts(self):
        g=self.lib;g.flat_ground(0);g.baba_step(-218,0,163)
        self.assertTrue(g.baba_hit(4)&2)
        self.assertEqual(g.dekubaba_filter(0),0)
        for _ in range(95):g.baba_step(-218,0,163)
        self.assertFalse(g.baba_hit(4)&2)
        for _ in range(35):g.baba_step(-218,0,163)
        g.baba_hit(4)
        for _ in range(60):g.baba_step(-218,0,163)
        self.assertEqual(g.rewards(),1)
        self.assertEqual(g.reward_type(),12)

    def test_dekubaba_nut_then_jump_sword_prunes_into_one_stick(self):
        g=self.lib;g.flat_ground(0)
        for _ in range(95):g.baba_step(-218,0,163)
        self.assertTrue(g.baba_hit(1)&1)
        self.assertGreater(g.dekubaba_filter(0),16)
        for _ in range(35):g.baba_step(-218,0,163)
        self.assertTrue(g.baba_hit(1<<25)&1)
        self.assertTrue(g.baba_pruned())
        self.assertTrue(0 < g.dekubaba_filter(0) <= 16)
        for _ in range(80):g.baba_step(-218,0,163)
        x,z=g.baba_pos(0),g.baba_pos(2)
        for _ in range(3):g.baba_step(x,0,z)
        self.assertEqual(g.sticks(),1)
        self.assertEqual(g.rewards(),0)

    def test_gold_skull_requires_damage_then_reachable_token_and_persists(self):
        g=self.lib;g.wall_sk_step(3,0,0,0,0)
        self.assertEqual(g.wall_sk_kind(0),2)
        self.assertFalse(g.wall_sk_hit(1)&1)
        self.assertEqual(g.wall_skull_filter(0),0) # EnSw source excludes nut damage.
        self.assertTrue(g.wall_sk_hit(2)&1)
        self.assertTrue(0 < g.wall_skull_filter(0) <= 16) # Stick does 2, gold health is 2.
        for _ in range(45):g.wall_sk_step(3,0,0,0,0)
        self.assertEqual(g.wall_sk_kind(0),3)
        self.assertEqual(g.save_skull_count(),0)
        for _ in range(3):g.wall_sk_step(3,-281,-835,-436,0)
        self.assertEqual(g.save_skull_count(),1)
        self.assertTrue(g.save_skull_collected(0,2))
        g.wall_sk_step(0,0,0,0,0);g.wall_sk_step(3,0,0,0,0)
        self.assertEqual(g.wall_sk_kind(0),0)

    def test_skulltula_front_bounces_back_takes_seed_and_room_unloads(self):
        g=self.lib
        # Room 5 source actor at (-1360,-806,1079), player in +Z.
        g.skull_step(5,-1360,-850,1179)
        self.assertEqual(g.skull_alive(),1)
        self.assertTrue(g.skull_hit(4,0)&2)
        for _ in range(15):g.skull_step(5,-1360,-850,1179)
        self.assertFalse(g.skull_hit(4,1)&2)
        for _ in range(15):g.skull_step(5,-1360,-850,1179)
        self.assertFalse(g.skull_hit(4,1)&2)
        # Death disables attention but retains the actor for bounce/drop.
        g.skull_step(4,0,0,0)
        self.assertEqual(g.skull_alive(),0)

    def test_skulltula_nut_stun_stops_descent_then_resumes(self):
        g=self.lib;g.skull_step(5,-1360,-850,1179)
        g.skull_hit(1,0)
        self.assertGreater(g.skulltula_filter(0),16)
        y=g.skull_y(0)
        for _ in range(150):g.skull_step(5,-1360,-850,1179)
        self.assertEqual(g.skull_y(0),y)
        for _ in range(60):g.skull_step(5,-1360,-850,1179)
        self.assertLess(g.skull_y(0),y)

    def test_eye_front_seed_toggles_but_rear_and_outside_miss(self):
        g=self.lib;self.assertTrue(g.dungeon_puzzles_sync(2,4))
        self.assertFalse(g.puzzle_shot(-360,-759,960,-270,-759,960))
        self.assertFalse(g.puzzle_shot(-270,-730,960,-360,-730,960))
        self.assertTrue(g.puzzle_shot(-270,-759,960,-360,-759,960))
        self.assertTrue(g.save_get_switch(2,4))
        for _ in range(5):g.puzzle_step(0,0,0,0)
        self.assertEqual(g.puzzle_model(4),7)
        self.assertTrue(g.puzzle_shot(-270,-759,960,-360,-759,960))
        self.assertFalse(g.save_get_switch(2,4))

    def test_floor_switch_depressing_never_teleports_rider(self):
        g=self.lib;self.assertTrue(g.dungeon_puzzles_sync(2,10))
        y=g.floor_at(-739,840,-147)
        for _ in range(8):
            self.assertEqual(g.switch_rider_delta(-739,y,-147),0)
            y=g.floor_at(-739,y+2,-147)
        self.assertTrue(g.save_get_switch(2,61))
        self.assertTrue(g.sfx_take()&(1<<6))
        g.switch_rider_delta(-739,y,-147)
        self.assertEqual(g.sfx_take(),0)

    def test_floor_switch_requires_ground_contact_and_raises_platform(self):
        g=self.lib;g.dungeon_puzzles_sync(2,10)
        y=g.floor_at(-739,840,-147)
        for _ in range(4):g.puzzle_step(-739,y,-147,0)
        self.assertFalse(g.save_get_switch(2,61))
        for _ in range(64):g.puzzle_step(-739,y,-147,1)
        self.assertTrue(g.save_get_switch(2,61))
        self.assertEqual(g.puzzle_y(10),700)
        # Link leaves before timer expires; the switch then rises again.
        for _ in range(450):g.puzzle_step(0,0,0,0)
        self.assertFalse(g.save_get_switch(2,61))
        self.assertEqual(g.puzzle_model(10),0)
        self.assertEqual(g.puzzle_model(9),1)

    def test_ladder_seed_falls_280_units_and_reload_keeps_it_down(self):
        g=self.lib;g.dungeon_puzzles_sync(2,2)
        self.assertTrue(g.puzzle_shot(-1100,600,1100,-1030,600,1030))
        self.assertTrue(g.save_get_switch(2,35))
        for _ in range(90):g.puzzle_step(0,0,0,0)
        self.assertEqual(g.puzzle_y(1),280)
        g.dungeon_puzzles_sync(2,0);g.dungeon_puzzles_sync(2,2)
        self.assertEqual(g.puzzle_y(1),280)

    def test_water_drain_hold_restore_and_room_reset(self):
        g=self.lib;g.water_scene();g.dungeon_puzzles_sync(2,5)
        self.assertEqual(g.water_y(),-905)
        g.save_set_switch(2,62)
        for _ in range(150):g.puzzle_step(0,0,0,0)
        self.assertEqual(g.water_y(),-952)
        for _ in range(975):g.puzzle_step(0,0,0,0)
        self.assertEqual(g.water_y(),-905)
        self.assertFalse(g.save_get_switch(2,62))
        g.save_set_switch(2,62)
        for _ in range(150):g.puzzle_step(0,0,0,0)
        g.dungeon_puzzles_sync(2,0)
        self.assertEqual(g.water_y(),-905)

    def test_capsule_contacts_cross_parallel_endpoints_and_spheres(self):
        for mode,want in enumerate((True,False,True,True,False,True,False)):
            self.assertEqual(bool(self.lib.capsules(mode)),want,mode)

    def test_open_shutter_survives_crossing_to_other_room(self):
        g=self.lib
        for _ in range(24):g.door_step(0,0,1,-40)
        self.assertTrue(g.dungeon_door_open(0))
        g.door_step(0,1,0,6)
        self.assertTrue(g.dungeon_door_open(0))
        self.assertEqual(g.wall(6,30),30)

    def test_clear_door_keeps_back_locked_until_clear_and_front_opens(self):
        g=self.lib
        for _ in range(30):g.door_step(1,1,1,40)
        self.assertFalse(g.dungeon_door_open(0))
        g.save_set_clear(2,1)
        for _ in range(24):g.door_step(1,1,1,40)
        self.assertTrue(g.dungeon_door_open(0))
        g.reset()
        for _ in range(24):g.door_step(1,0,1,-40)
        self.assertTrue(g.dungeon_door_open(0))
    def test_switch_gate_uses_own_flag_and_swept_closed_collision(self):
        g=self.lib
        g.save_set_switch(2,4)
        for _ in range(24):g.door_step(2,1,1,40)
        self.assertFalse(g.dungeon_door_open(0))
        self.assertEqual(g.wall(40,-40),22)
        g.save_set_switch(2,3)
        for _ in range(24):g.door_step(2,1,1,40)
        self.assertTrue(g.dungeon_door_open(0))
    def test_open_prompt_and_refusal_follow_gate_without_writing_events(self):
        g=self.lib
        self.assertEqual(g.door_step(1,1,1,40),2)
        self.assertFalse(g.dungeon_doors_prompt())
        g.save_set_clear(2,1)
        self.assertEqual(g.door_step(1,1,0,40),0)
        self.assertTrue(g.dungeon_doors_prompt())
        self.assertEqual(g.door_step(1,1,1,40),1)
        g.door_step(1,1,0,200)
        self.assertFalse(g.dungeon_doors_prompt())
    def test_web_catches_small_fall_breaks_high_central_fall_and_stays_gone(self):
        g=self.lib
        self.assertTrue(g.dungeon_webs_step(2,0))
        floor=g.floor_at(0,30,0)
        self.assertGreater(floor,-20)
        self.assertFalse(g.dungeon_webs_land(0,floor,0,750))
        self.assertFalse(g.dungeon_webs_land(90,0,0,900))
        self.assertTrue(g.dungeon_webs_land(0,floor,0,751))
        for _ in range(30):self.assertTrue(g.dungeon_webs_step(2,3))
        self.assertTrue(g.save_get_switch(2,5))
        self.assertEqual(g.floor_at(0,30,0),-32000)
        g.dungeon_webs_step(2,1);g.dungeon_webs_step(2,0)
        self.assertEqual(g.floor_at(0,30,0),-32000)
    def test_room_unload_removes_web_collision_without_granting_switch(self):
        g=self.lib;g.dungeon_webs_step(2,0);g.dungeon_webs_step(2,1)
        self.assertEqual(g.floor_at(0,30,0),-32000)
        self.assertFalse(g.save_get_switch(2,5))
    def test_floor_web_fire_requires_tip_below_web_and_removes_collision_after_burn(self):
        g=self.lib;g.dungeon_webs_step(2,0)
        self.assertFalse(g.web_burn(0,1,0))
        self.assertFalse(g.web_burn(71,-10,0))
        self.assertTrue(g.web_burn(0,-10,0))
        self.assertTrue(g.save_get_switch(2,5))
        self.assertGreater(g.floor_at(0,30,0),-20)
        for _ in range(45):g.dungeon_webs_step(2,0)
        self.assertEqual(g.floor_at(0,30,0),-32000)
    def test_two_torches_require_fire_and_both_lit_then_persist(self):
        g=self.lib
        g.torch_tip(6,-1966,-693,964)
        self.assertFalse(g.torch_lit(6))
        g.torch_tip(6,-1855,-693,1212)
        g.torch_tip(6,-1966,-693,964)
        self.assertTrue(g.torch_lit(6))
        self.assertFalse(g.save_get_switch(2,3))
        g.torch_tip(6,-1743,-693,965)
        self.assertTrue(g.save_get_switch(2,3))
        g.torch_tip(0,0,0,0);g.torch_tip(6,0,0,0)
        self.assertTrue(g.torch_lit(6));self.assertTrue(g.torch_lit(7))
    def test_wall_web_has_rotated_collision_burns_and_stays_gone(self):
        g=self.lib;g.dungeon_webs_step(2,7)
        self.assertTrue(g.wall_web_hit())
        self.assertTrue(g.wall_visible(3))
        self.assertTrue(g.web_burn(-1354,-740,3))
        self.assertTrue(g.save_get_switch(2,7))
        for _ in range(45):g.dungeon_webs_step(2,7)
        self.assertFalse(g.wall_visible(3));self.assertFalse(g.wall_web_hit())
        g.dungeon_webs_step(2,0);g.dungeon_webs_step(2,7)
        self.assertFalse(g.wall_web_hit())
    def test_wall_web_burn_switch_and_room_unload(self):
        g=self.lib;g.dungeon_webs_step(2,3)
        self.assertTrue(g.wall_visible(1))
        g.save_set_switch(2,2)
        for _ in range(45):g.dungeon_webs_step(2,3)
        self.assertTrue(g.save_get_switch(2,0));self.assertFalse(g.wall_visible(1))
        g.dungeon_webs_step(2,7);g.dungeon_webs_step(2,0)
        self.assertFalse(g.wall_web_hit());self.assertFalse(g.save_get_switch(2,7))
    def test_single_timed_torch_uses_temporary_switch_60(self):
        g=self.lib
        g.torch_tip(10,-635,867,-132)
        g.torch_tip(10,-722,867,157)
        self.assertTrue(g.save_get_switch(2,60))
        g.save_reset_temp_switches(2)
        self.assertFalse(g.save_get_switch(2,60))
        g.save_set_switch(2,33);g.save_set_switch(2,60)
        g.save_room_changed(2)
        self.assertTrue(g.save_get_switch(2,33))
        self.assertFalse(g.save_get_switch(2,60))
        g.save_set_switch(2,3);g.save_set_switch(2,60)
        g.save_unset_switch(2,60)
        self.assertTrue(g.save_get_switch(2,3))
        self.assertFalse(g.save_get_switch(2,60))
if __name__=='__main__':unittest.main()
