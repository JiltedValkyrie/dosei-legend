"""Real Tree collision must admit Link through lifted shutters, not frames."""
import ctypes as C
import math
from pathlib import Path
import sys
import unittest
import test_player_bg as bg

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import build_scene_table as scenes
import build_room_scene as rooms

class TreeDoorCollision(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        bg.PlayerBg.setUpClass()
        cls.lib = bg.PlayerBg.lib
        cls.oot = Path('D:/Workspace-Claude/game-decomps/n64/oot')
        cls.doors = rooms.transitions(cls.oot, prefix='ydan', room_count=12)
        cls.data = scenes.source.collision_data(
            scenes.source.extract(cls.oot, None, prefix='ydan')['ydan_scene'])
        cls.lib.bg_mesh_bytes.argtypes = [C.c_char_p, C.c_uint]
        cls.lib.bg_mesh_bytes.restype = C.c_uint
        cls.lib.bg_mesh_decode.argtypes = [C.c_char_p,C.c_uint,C.c_void_p,C.c_uint,C.POINTER(bg.Mesh)]
        cls.lib.kokiri_collision_move_actor.argtypes = [C.POINTER(bg.Vec),C.c_int32,C.c_int32,C.c_int32]

    def load(self, blob):
        n = self.lib.bg_mesh_bytes(blob, len(blob))
        self.store = C.create_string_buffer(n)
        self.mesh = bg.Mesh()
        self.assertTrue(self.lib.bg_mesh_decode(blob,len(blob),self.store,n,C.byref(self.mesh)))
        self.lib.bg_scene_set(C.byref(self.mesh))
        self.lib.bg_dyna_clear()

    def walk(self, door, direction, side=0):
        sn = math.sin(door['yaw']*math.pi/32768)
        cs = math.cos(door['yaw']*math.pi/32768)
        p = bg.Vec(round(door['x']-direction*70*sn+side*cs),door['y']+90,
                   round(door['z']-direction*70*cs-side*sn))
        speed, remainder = C.c_int32(), C.c_int32()
        for _ in range(55):
            self.lib.kokiri_collision_move_actor(C.byref(p),round(direction*sn*3),0,round(direction*cs*3))
            self.lib.kokiri_collision_fall(C.byref(p),C.byref(speed),C.byref(remainder))
        return direction*((p.x-door['x'])*sn+(p.z-door['z'])*cs)

    def test_original_seals_reproduce_first_door_block(self):
        self.load(scenes.collision_file(self.data))
        for direction in (-1,1):
            self.assertLess(self.walk(self.doors[0],direction),0)

    def test_slingshot_route_crosses_both_doors_both_ways(self):
        self.load(scenes.collision_file(self.data,self.doors))
        for door in self.doors:
            if {door['front'],door['back']} not in ({0,1},{1,2}): continue
            for direction in (-1,1):
                self.assertGreater(self.walk(door,direction),30)

    def test_frames_still_block_outside_aperture(self):
        self.load(scenes.collision_file(self.data,self.doors))
        for direction in (-1,1):
            self.assertLess(self.walk(self.doors[0],direction,side=60),0)

    def test_only_34_seal_entity_flags_change_and_staged_file_matches(self):
        original=scenes.collision_file(self.data)
        patched=scenes.collision_file(self.data,self.doors)
        changed=[i for i,p in enumerate(self.data['polys']) if scenes.shutter_cap(p,self.doors)]
        self.assertEqual(changed,list(range(34)))
        self.assertEqual(len(original),len(patched))
        info=16+len(self.data['polys'])*36
        diffs={i for i,(a,b) in enumerate(zip(original,patched)) if a!=b}
        self.assertEqual(diffs,{info+2*i for i in changed})
        for i in diffs:self.assertEqual(original[i]^patched[i],2)
        self.assertEqual((ROOT/'build/cd/S7.COL').read_bytes(),patched)

if __name__=='__main__': unittest.main()
