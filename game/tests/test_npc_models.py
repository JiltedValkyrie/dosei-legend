"""Check the target integer NPC pose math."""
import ctypes
import math
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
GCC = Path('C:/msys64/mingw64/bin/gcc.exe')


class NpcModels(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.folder = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        cls.lib = None
        if GCC.exists():
            dll = Path(cls.folder.name) / 'pose.dll'
            env = dict(os.environ, PATH=str(GCC.parent) + os.pathsep + os.environ.get('PATH', ''))
            subprocess.run([str(GCC), '-shared', '-O2', str(ROOT / 'src/npc_pose.c'),
                            '-o', str(dll)], check=True, env=env)
            cls.lib = ctypes.CDLL(str(dll))

    @classmethod
    def tearDownClass(cls):
        cls.lib = None
        cls.folder.cleanup()

    @unittest.skipUnless(GCC.exists(), 'host compiler required')
    def test_target_head_rotation_matches_parent_space_reference(self):
        if True:
            lib = self.lib
            # Rotated parent: head yaw is local X, NOT global Y. A world-axis
            # shortcut would produce a different result for seated Kokiri.
            basis = (0, -16384, 0, 16384, 0, 0, 0, 0, 16384)
            origin = (40, 1200, -80)
            pivot = 768
            for angle_y, angle_p in ((0, 0), (.5, 0), (-.5, .3)):
                point = (ctypes.c_int32 * 3)(120, 2500, 130)
                b = (ctypes.c_int16 * 9)(*basis)
                o = (ctypes.c_int16 * 3)(*origin)
                d = [point[i]-origin[i] for i in range(3)]
                local = [sum(basis[k*3+i]*d[k]/16384 for k in range(3)) for i in range(3)]
                x = local[0]-pivot
                x, y = math.cos(angle_p)*x - math.sin(angle_p)*local[1], math.sin(angle_p)*x + math.cos(angle_p)*local[1]
                y, z = math.cos(angle_y)*y - math.sin(angle_y)*local[2], math.sin(angle_y)*y + math.cos(angle_y)*local[2]
                local = (x+pivot, y, z)
                expected = [origin[i]+sum(basis[i*3+k]*local[k]/16384 for k in range(3)) for i in range(3)]
                trig = [round(f(a)*16384) for a in (angle_y, angle_p) for f in (math.sin, math.cos)]
                rot = (ctypes.c_int16 * 9)()
                lib.npc_rot_matrix(rot, 0, trig[0], trig[1], 2, trig[2], trig[3])
                lib.npc_limb_transform(point, b, o, pivot, rot)
                for actual, want in zip(point, expected):
                    self.assertAlmostEqual(actual, want, delta=3)  # <0.05 world units

    @unittest.skipUnless(GCC.exists(), 'host compiler required')
    def test_track_point_follows_source_limits_and_body_turn(self):
        class Track(ctypes.Structure):
            _fields_ = [('head', ctypes.c_int16 * 2), ('torso', ctypes.c_int16 * 2)]
        lib = self.lib
        t, yaw = Track(), ctypes.c_uint16(0)
        # Preset 2, Link far to the right: head caps at 0x31C4, torso takes
        # the rest up to 0x0E38, body stays put (HEAD_AND_TORSO).
        for _ in range(200):
            lib.npc_track_point(ctypes.byref(t), ctypes.byref(yaw), 0x6000, 0, 2, 2)
        self.assertEqual((t.head[1], t.torso[1], yaw.value), (0x31C4, 0x0E38, 0))
        # NONE relaxes both back to zero.
        for _ in range(200):
            lib.npc_track_point(ctypes.byref(t), ctypes.byref(yaw), 0x6000, 0, 2, 1)
        self.assertEqual((t.head[1], t.torso[1]), (0, 0))
        # FULL_BODY turns shape.rot.y onto the target, head/torso settle at 0.
        for _ in range(400):
            lib.npc_track_point(ctypes.byref(t), ctypes.byref(yaw), 0x6000, 0x0800, 2, 4)
        self.assertEqual(yaw.value, 0x6000)
        self.assertEqual((t.head[1], t.torso[1]), (0, 0))
        # Pitch: head clamps to maxHeadPitch 0x0E38, torso to 0x071C.
        self.assertEqual((t.head[0], t.torso[0]), (0x0800, 0))
        for _ in range(200):
            lib.npc_track_point(ctypes.byref(t), ctypes.byref(yaw), 0x6000, 0x3000, 2, 2)
        self.assertEqual((t.head[0], t.torso[0]), (0x0E38, 0x071C))
        # Math_SmoothStepToS: 1/6 of the gap, 2000 cap, min step 1.
        v = ctypes.c_int16(0)
        lib.npc_smooth_step(ctypes.byref(v), 30000, 6, 2000, 1)
        self.assertEqual(v.value, 2000)
        v = ctypes.c_int16(0)
        lib.npc_smooth_step(ctypes.byref(v), 5, 6, 2000, 1)
        self.assertEqual(v.value, 1)


if __name__ == '__main__':
    unittest.main()
