"""Source melee windows and selection, independent of the old slice swing."""
import ctypes as C
import os
import pathlib
import re
import subprocess
import tempfile
import unittest

ROOT=pathlib.Path(__file__).resolve().parents[1]
GCC=pathlib.Path('C:/msys64/mingw64/bin/gcc.exe')
SOURCE=pathlib.Path('D:/Workspace-Claude/game-decomps/n64/oot/src/overlays/actors/ovl_player_actor/z_player.c')

@unittest.skipUnless(GCC.is_file(),'host compiler required')
class PlayerAttack(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        source=pathlib.Path(cls.tmp.name)/'attack.c'
        source.write_text('''#include "player_attack.h"
int state(unsigned id,int f,int air) { return player_attack_weapon_state(id,f,air); }
unsigned damage(unsigned id) { return player_attack_damage_flags(id); }
unsigned select_attack(int d,int z,int s) { return player_attack_select(d,z,s); }
''')
        env=dict(os.environ);env['PATH']=str(GCC.parent)+os.pathsep+env.get('PATH','')
        dll=source.with_suffix('.dll')
        subprocess.run([str(GCC),'-shared','-O2','-Wall','-Werror','-I'+str(ROOT/'src'),
                        str(source),'-o',str(dll)],check=True,env=env)
        cls.lib=C.CDLL(str(dll))
    @classmethod
    def tearDownClass(cls): cls.tmp.cleanup()
    def test_forward_windup_damage_and_end_at_fractional_frames(self):
        self.assertEqual([self.lib.state(0,f,0) for f in (0,2,3,11,12,13)],
                         [-1,-1,1,1,1,0])
    def test_airborne_jump_uses_action_override_not_ground_table(self):
        for attack in (16,17):
            self.assertEqual([self.lib.state(attack,f,1) for f in (17,18,20,21,297,298)],
                             [0,-1,-1,1,1,0])
        self.assertEqual(self.lib.state(19,7,0),0)
    def test_damage_flags_not_universal_damage_or_magic_spin(self):
        for attack in (0,2,4,6,8,10,12,14,20,21,24):
            self.assertEqual(self.lib.damage(attack),1<<8)
        for attack in (16,17,18,19):
            self.assertEqual(self.lib.damage(attack),1<<25)
        # BIG_SPIN_1H: func_80844BE4 picks it at unk_858 >= 0.85 with no
        # magic check; func_80837948 gives its quads D_80854488[..][0], the
        # slash flags. Only EnMThunder's magic cylinder needs magic.
        self.assertEqual(self.lib.damage(26),1<<8)
    def test_still_targeted_forward_stab_and_directional_selection(self):
        self.assertEqual(self.lib.select_attack(-1,0,0),4)
        self.assertEqual(self.lib.select_attack(-1,1,0),0)
        self.assertEqual(self.lib.select_attack(0,0,0),0)
        self.assertEqual(self.lib.select_attack(0,1,0),12)
        self.assertEqual([self.lib.select_attack(d,1,0) for d in (1,2,3)],[4,4,8])
        self.assertEqual(self.lib.select_attack(0,1,1),24)
    def test_invalid_ids_and_negative_frames_do_not_register(self):
        for attack in (1,3,22,25,255):
            self.assertEqual(self.lib.state(attack,0,0),0)
        self.assertEqual(self.lib.state(0,-1,0),0)
    @unittest.skipUnless(SOURCE.is_file(),'local OoT source required')
    def test_all_windows_match_source_table(self):
        table=SOURCE.read_text().split('D_80854190[PLAYER_MWA_MAX] = {',1)[1].split('\n};',1)[0]
        rows=re.findall(r'\{\s*&\w+,\s*&\w+,\s*&\w+,\s*(\d+),\s*(\d+)\s*\}',table)
        self.assertEqual(len(rows),28)
        for attack in (0,2,4,6,8,10,12,14,16,17,18,19,20,21,24):
            begin,end=map(int,rows[attack])
            for f in range(0,(end+2)*3):
                expected=0 if f>end*3 else (1 if f>=begin*3 else -1)
                self.assertEqual(self.lib.state(attack,f,0),expected,(attack,f))
