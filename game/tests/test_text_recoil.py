"""Execute recomp.c recoil functions with a text box owning the world."""
import ctypes
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
ROOT = Path(__file__).resolve().parents[1]
GCC = Path('C:/msys64/mingw64/bin/gcc.exe')

@unittest.skipUnless(GCC.exists(), 'host compiler required')
class Recoil(unittest.TestCase):
    def test_text_blocks_damage_and_weapon_recoil(self):
        source = (ROOT/'src/recomp.c').read_text()
        def function(name):
            start = source.index('static void '+name+'(void)')
            end = source.index('\n}', start)+2
            return source[start:end]
        code = r"""
#include <stdint.h>
#include <stdbool.h>
struct {int knock_speed, knock_yaw, lunge_q16, swing_count;} gameplay;
static int blocked, moves, recomp_link, recomp_link_yaw;
static int knock_rx, knock_rz, attack_carry_x_q8, attack_carry_z_q8;
static unsigned attack_root_clip, attack_root_swing;
static int32_t attack_root_prev[3];
bool gameplay_blocks_world(void) { return blocked; }
void kokiri_camera_sincos(int y,int32_t *s,int32_t *c) { *s=0; *c=65536; }
void kokiri_collision_move_actor(int *p,int x,int y,int z) { moves += x || z; }
bool gameplay_attack_time(unsigned *c,unsigned *t) { return false; }
void link_anim_clip_root(unsigned c,unsigned t,int32_t *p) { }
""" + function('link_knockback') + '\n' + function('attack_root_motion') + r"""
int run(int text, int weapon) {
    blocked=text; moves=0;
    gameplay.knock_speed=gameplay.lunge_q16=65536*5;
    for (int i=0;i<60;++i) {
        if (weapon) attack_root_motion(); else link_knockback();
    }
    return moves;
}
"""
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            src=Path(tmp,'recoil.c'); src.write_text(code)
            dll=src.with_suffix('.dll')
            env=dict(os.environ); env['PATH']=str(GCC.parent)+os.pathsep+env.get('PATH','')
            subprocess.run([str(GCC),'-shared','-O2','-o',str(dll),str(src)],check=True,env=env)
            lib=ctypes.CDLL(str(dll))
            for weapon in (0,1):
                self.assertEqual(lib.run(1,weapon),0)
                self.assertGreater(lib.run(0,weapon),0)
