"""Check imported topology, per-frame head bases and the target integer pose math."""
import ctypes
import json
import math
import os
from pathlib import Path
import struct
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
MODELS = ROOT / 'build/generated/npcs'
GCC = Path('C:/msys64/mingw64/bin/gcc.exe')


class NpcModels(unittest.TestCase):
    def test_greeting_clips_share_idle_vertex_and_material_order(self):
        idle = (MODELS / 'NPC01.BIN').read_bytes()
        header = struct.unpack_from('>8I', idle)
        for model in (16, 17, 18):
            data = (MODELS / ('NPC%02d.BIN' % model)).read_bytes()
            self.assertEqual(struct.unpack_from('>8I', data), header)
            # Positions change; indices and texture records must not. Runtime
            # swaps only ANM/TRK and retains the idle polygons and VDP1 bank.
            self.assertEqual(data[header[5]:], idle[header[5]:])

    def test_every_child_model_has_complete_motion_and_tracking(self):
        manifest = json.loads((MODELS / 'manifest.json').read_text())
        self.assertEqual([r['model'] for r in manifest], list(range(19)))
        # 16-18 are Saria's greeting-cutscene poses. EnSa_HandleCutscene indexes
        # sAnimationInfo1 with the actor cue id, so these three must be exactly
        # the clips cues 1, 2 and 3 of gKokiriForestSariaGreetingCs name -- a
        # wrong clip here plays a wrong-looking greeting rather than failing.
        # Cue 4 is model 1's own gSariaWaitArmsToSideAnim, so there is
        # deliberately no fourth model.
        greeting = {r['model']: r['clip'] for r in manifest if r['model'] >= 16}
        self.assertEqual(greeting, {16: 'gSariaLookUpArmExtendedAnim',
                                    17: 'gSariaWaveAnim',
                                    18: 'gSariaRunAnim'})
        for row in manifest:
            if row['model'] >= 16:
                self.assertEqual(row['object'], 'object_sa')
        for row in manifest:
            with self.subTest(model=row['model']):
                stem = MODELS / ('NPC%02d' % row['model'])
                mesh = stem.with_suffix('.BIN').read_bytes()
                motion = stem.with_suffix('.ANM').read_bytes()
                tracking = stem.with_suffix('.TRK').read_bytes()
                magic, version, vertices, faces, vo, ro, to, tb = struct.unpack_from('>4s7I', mesh)
                self.assertEqual((magic, version), (b'KFR1', 2))
                self.assertEqual((vertices, faces), (row['vertices'], row['faces']))
                self.assertEqual(len(mesh), to + tb)
                for i in range(faces):
                    indices = struct.unpack_from('>4H', mesh, ro + 20*i)
                    self.assertLess(max(indices), vertices)
                magic, av, poses, ticks = struct.unpack_from('>4s3I', motion)
                self.assertEqual((magic, av), (b'CVA1', vertices))
                self.assertEqual(len(motion), 16 + ticks*2 + poses*vertices*6)
                self.assertLess(max(struct.unpack_from('>%dH' % ticks, motion, 16)), poses)
                magic, tv, tt, pivot = struct.unpack_from('>4s3I', tracking)
                self.assertEqual((magic, tv, tt), (b'NTR2', vertices, ticks))
                # The head pivot is the skeleton's, not the clip's: Saria's
                # greeting models share object_sa with model 1 and so share
                # its pivot height.
                self.assertEqual(pivot, 576 if row['object'] == 'object_sa' else 768)
                flags = tracking[16:16+vertices]
                self.assertEqual(sum(f & 1 for f in flags), row['head_vertices'])
                self.assertEqual(sum(f >> 1 & 1 for f in flags), row['torso_vertices'])
                self.assertLessEqual(max(flags), 3)
                self.assertGreater(row['head_vertices'], 0)
                # Head sits inside the torso subtree; legs stay outside it.
                self.assertTrue(all(f & 2 for f in flags if f & 1))
                self.assertLess(row['torso_vertices'], vertices)
                start = 16 + ((vertices + 3) & ~3)
                self.assertEqual(len(tracking), start + ticks*54)
                for frame in range(ticks):
                    for at in (0, 30):
                        basis = struct.unpack_from('>9h', tracking, start + frame*54 + at)
                        for axis in range(3):
                            self.assertAlmostEqual(sum((v / 16384)**2 for v in basis[axis*3:axis*3+3]),
                                                   1, delta=.0002)

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
