"""Boss eye vulnerability, source combat timing and clear transaction."""
import ctypes as C
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
GCC=Path('C:/msys64/mingw64/bin/gcc.exe')

@unittest.skipUnless(GCC.exists(),'host compiler required')
class Gohma(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        folder=Path(cls.tmp.name)
        source=r'''
#include <math.h>
#include "gohma.c"
gameplay_t gameplay;
static actor_t actors[ACTOR_POOL_MAX];
static uint64_t memory[1024];
static uint8_t poses[GOHMA_POSE_BYTES];
static unsigned children;
static unsigned heart_offers;
bool gameplay_boss_heart(void){++heart_offers;save_item_give(SAVE_ITEM_HEART_CONTAINER);save_set_collectible(SAVE_SCENE_DEKU_TREE_BOSS,31);return true;}
void kokiri_camera_sincos(uint16_t a,int32_t *s,int32_t *c){*s=round(sin(a*6.283185307179586/65536)*65536);*c=round(cos(a*6.283185307179586/65536)*65536);}
uint16_t collide_heading(int32_t x,int32_t z){return (uint16_t)(int32_t)(atan2(x,z)*65536/6.283185307179586);}
void collide_world_push(actor_t *a,int32_t x,int32_t z){a->x+=x;a->z+=z;}
bool gohma_larva_alive(unsigned i){return (children&(1u<<i))!=0;}
bool gohma_larva_spawn(unsigned i,int32_t x,int32_t y,int32_t z,uint16_t yaw){(void)x;(void)y;(void)z;(void)yaw;children|=1u<<i;return true;}
int32_t bg_floor(const bg_vec_t *p,uint32_t flags,bg_hit_t *hit){(void)p;(void)flags;(void)hit;return -640;}
void reset(void){gohma_reset();actor_sys_init(actors,sizeof(actors));gohma_init(memory,sizeof(memory));save_new_game();save_state.scene_id=SAVE_SCENE_DEKU_TREE_BOSS;gohma_bind(poses,sizeof(poses));spawn(1);children=0;boss->patience=200;state(FLOOR,100);actor_t *a=actor_resolve(boss->handle);a->y=-640;boss->yq=-640*256;boss->pitch=0;}
void mode(int s){state(s,70);boss->stun=150;boss->eye_closed=0;boss->invuln=0;}
void hit(unsigned damage){static collider_t weapon;weapon.at_dmg=damage;boss->spheres[0].ac_hit=&weapon;boss->spheres[0].result=COL_RES_AC_HIT;gohma_collect();}
void step(int n){gameplay_input_t in={0};in.room=1;in.x=900;in.y=-640;in.z=0;while(n--)gohma_step(&in);}
void closed(int yes){boss->eye_closed=yes?7:0;}
void reward_step(int n,int x,int y,int z,int grounded){gameplay_input_t in={0};in.room=1;in.x=x;in.y=y;in.z=z;in.grounded=grounded;while(n--)gohma_step(&in);}
void cleared_room(void){save_set_clear(SAVE_SCENE_DEKU_TREE_BOSS,1);gohma_reset();spawn(1);heart_offers=0;}
int offers(void){return heart_offers;}
int reward_visible(int kind){int32_t p[3];uint16_t yaw;return gohma_reward_body(kind,p,&yaw);}
int health(void){return boss->health;}
int current(void){return boss->state;}
int mode_floor(void){return FLOOR;}int mode_stun(void){return STUN;}
int mode_ceiling(void){return CEILING;}int mode_struck(void){return STRUCK;}
int mode_eggs(void){return EGGS;}int mode_death(void){return DEATH;}
int mode_hurt(void){return HURT;}
int clear(void){return gohma_defeated();}
'''
        src=folder/'test.c';src.write_text(source)
        dll=folder/'test.dll'
        env=dict(os.environ,PATH=str(GCC.parent)+os.pathsep+os.environ.get('PATH',''))
        subprocess.run([str(GCC),'-shared','-O2','-Wall','-Wextra','-Werror','-Wno-misleading-indentation',
                        '-I'+str(ROOT/'src'),'-I'+str(ROOT/'build/generated'),
                        '-I'+str(ROOT.parent/'shared/lib/collision'),'-I'+str(ROOT.parent/'shared/lib/camera'),
                        str(src),str(ROOT/'src/actor_sys.c'),str(ROOT/'src/save_state.c'),str(ROOT/'src/collide.c'),
                        '-o',str(dll),'-lm'],check=True,env=env)
        cls.lib=C.CDLL(str(dll))
        for name in ('gohma_warp_active','gohma_warp_ready','save_finish_deku_warp',
                     'save_check_quest_item','save_get_event_chk_inf'):
            getattr(cls.lib,name).restype=C.c_bool

    @classmethod
    def tearDownClass(cls):cls.tmp.cleanup()
    def setUp(self):self.lib.reset()

    def test_sword_cannot_damage_before_stun_and_seed_does_not_remove_health(self):
        g=self.lib;g.hit(1<<8);self.assertEqual(g.health(),10)
        g.hit(1<<2);self.assertEqual(g.current(),g.mode_stun());self.assertEqual(g.health(),10)
        g.step(16);g.hit(1<<8)
        self.assertEqual(g.health(),9);self.assertEqual(g.current(),g.mode_hurt())
        g.hit(1<<8);self.assertEqual(g.health(),9)

    def test_ceiling_hit_drops_boss_but_closed_eye_and_egg_laying_reject_it(self):
        g=self.lib;g.mode(g.mode_ceiling());g.closed(1);g.hit(4)
        self.assertEqual(g.current(),g.mode_ceiling())
        g.closed(0);g.hit(4);self.assertEqual(g.current(),g.mode_struck())
        g.mode(g.mode_eggs());g.hit(4);self.assertEqual(g.current(),g.mode_eggs())

    def test_jump_sword_death_clear_is_delayed_until_defeat_sequence_ends(self):
        g=self.lib
        for _ in range(5):g.mode(g.mode_stun());g.hit(1<<25)
        self.assertEqual(g.health(),0);self.assertEqual(g.current(),g.mode_death());self.assertFalse(g.clear())
        g.step(403);self.assertFalse(g.clear());g.step(2);self.assertTrue(g.clear())

    def test_defeat_skip_commits_same_clear(self):
        g=self.lib;g.mode(g.mode_death());g.gohma_skip_shot();g.step(2);self.assertTrue(g.clear())

    def test_cleared_room_rewards_return_but_collected_heart_never_duplicates(self):
        g=self.lib;g.cleared_room()
        self.assertTrue(g.reward_visible(0));self.assertTrue(g.reward_visible(1))
        g.reward_step(6,141,-640,-84,0);self.assertEqual(g.offers(),0)
        g.reward_step(6,141,-640,-84,1);self.assertEqual(g.offers(),1)
        self.assertFalse(g.reward_visible(0))
        g.cleared_room();g.reward_step(6,141,-640,-84,1)
        self.assertFalse(g.reward_visible(0));self.assertEqual(g.offers(),0)

    def test_warp_requires_clear_appearance_and_source_height_then_waits(self):
        g=self.lib
        g.reward_step(200,0,-640,0,1);self.assertFalse(g.gohma_warp_active())
        g.cleared_room();g.reward_step(120,0,-600,0,1)
        self.assertFalse(g.gohma_warp_active())
        g.reward_step(2,0,-640,0,1);self.assertTrue(g.gohma_warp_active())
        self.assertFalse(g.gohma_warp_ready())
        g.reward_step(155,0,-640,0,1);self.assertTrue(g.gohma_warp_ready())
        self.assertTrue(g.reward_visible(0))  # Warp never auto-collects heart.

    def test_emerald_commit_requires_cleared_boss_and_preserves_optional_heart(self):
        g=self.lib
        self.assertFalse(g.save_finish_deku_warp())
        g.cleared_room();self.assertTrue(g.save_finish_deku_warp())
        self.assertTrue(g.save_check_quest_item(18))
        self.assertTrue(g.save_get_event_chk_inf(7));self.assertTrue(g.save_get_event_chk_inf(9))
        self.assertTrue(g.reward_visible(0))

if __name__=='__main__':unittest.main()
