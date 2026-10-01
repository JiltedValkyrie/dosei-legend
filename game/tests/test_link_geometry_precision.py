"""Run the real C skinner; keep sub-world-unit facial geometry intact."""
import ctypes
import os
import pathlib
import re
import subprocess
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
GEN = ROOT / 'build/generated'
GCC = pathlib.Path('C:/msys64/mingw64/bin/gcc.exe')
sys.path.insert(0, str(ROOT / 'tools'))
import build_link_model as model


class ModelIdentity(unittest.TestCase):
    def test_base_importer_cannot_silently_ignore_model_matrices(self):
        lists = model.scene_tool.DisplayLists(b'', b'')
        with self.assertRaises(ValueError):
            lists.matrix(0xDA380003, 0x0D000000)

    def test_vertex_reload_replaces_owner_and_missing_owner_fails(self):
        lists = model.LimbLists(b'', b'')
        vertex = (0,0,0,0,0,255,255,255,255)
        with self.assertRaises(ValueError):
            lists.load_vertex(0, vertex)
        lists.matrix_limbs = [2, 7]
        lists.matrix(0xDA380003, 0x0D000000)
        lists.load_vertex(0, vertex)
        lists.matrix(0xDA380003, 0x0D000040)
        self.assertEqual(lists.vertex_limbs[0], 2)
        lists.load_vertex(0, vertex)
        self.assertEqual(lists.vertex_limbs[0], 7)

    def test_matrix_owner_is_captured_when_vertex_loads_not_when_triangle_draws(self):
        lists = model.LimbLists(b'', b'')
        lists.matrix_limbs = [3, 5]
        lists.matrix(0xDA380003, 0x0D000000)
        lists.load_vertex(0, (0,0,0,0,0,255,255,255,255))
        lists.matrix(0xDA380003, 0x0D000040)
        lists.load_vertex(1, (1,0,0,0,0,255,255,255,255))
        lists.load_vertex(2, (0,1,0,0,0,255,255,255,255))
        lists.matrix(0xDA380003, 0x0D000000)
        lists.triangle(0x000204, False)
        self.assertEqual(lists.faces[0]['vertex_limbs'], [3,5,5])

    def test_unknown_matrix_commands_fail_instead_of_silently_breaking_mesh(self):
        lists = model.LimbLists(b'', b'')
        lists.matrix_limbs = [0]
        for word, address in ((0xDA380003,0x0D000040), (0xDA380001,0x0D000000),
                              (0xDA380003,0x06000000), (0xDA380003,0x0D000001)):
            with self.assertRaises(ValueError):
                lists.matrix(word, address)

    def test_distinct_locals_survive_coincident_integer_bind_positions(self):
        face = dict(vertices=[(0, 0, 0, 0, 0, 255, 255, 255, 255)] * 3,
                    local=[(0, 0, 0), (1, 0, 0), (0, 1, 0)], limb=0,
                    texture=dict(width=1, height=1, colors=[(255,255,255,255)],
                                 scale=(1,1), shifts=0, shiftt=0, uls=0, ult=0,
                                 cms=2, cmt=2, masks=0, maskt=0),
                    lighting=False, transparent=False, cull=False)
        with tempfile.TemporaryDirectory() as directory:
            positions, _, limbs, locals_ = model.write_model(
                [face], pathlib.Path(directory)/'link.bin', skinned=True)
        self.assertEqual(len(positions), 3)
        self.assertEqual(locals_, face['local'])
        self.assertEqual(limbs, [0, 0, 0])

    def test_marked_head_hair_is_flattened(self):
        texture = dict(width=2, height=2, colors=[(200,100,50,255)]*4)
        face = dict(limb=model.HEAD_LIMB, texture=texture, texture_segment=4,
                    hair_detail=True)
        self.assertEqual(model.flatten_faces([face]), 1)


@unittest.skipUnless(GCC.is_file() and (GEN/'link_clips.c').is_file(), 'build assets and host GCC required')
class LiveSkinner(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        output = pathlib.Path(cls.temp.name)/'skin.dll'
        source = re.sub(r'^#include .*$', '', (ROOT/'src/link_anim.c').read_text(), flags=re.M)
        adapter = '''
#include <stdint.h>
#include <math.h>
#include "link_clips.h"
typedef int32_t FIXED;
typedef uint16_t ANGLE;
#define X 0
#define Y 1
#define Z 2
#define toFIXED(x) ((FIXED)((x)*65536))
static FIXED slSin(ANGLE a) { return (FIXED)lround(sin(a*6.283185307179586/65536)*65536); }
static FIXED slCos(ANGLE a) { return (FIXED)lround(cos(a*6.283185307179586/65536)*65536); }
static FIXED slMulFX(FIXED a, FIXED b) { return (FIXED)(((int64_t)a*b)>>16); }
int32_t link_points[LINK_SKIN_VERTICES][3];
'''
        env = dict(os.environ)
        env['PATH'] = str(GCC.parent)+os.pathsep+env.get('PATH','')
        subprocess.run([str(GCC), '-shared', '-O2', '-I'+str(GEN), '-x', 'c', '-',
                        str(GEN/'link_clips.c'), '-lm', '-o', str(output)],
                       input=adapter+source, text=True, env=env, check=True)
        cls.lib = ctypes.CDLL(str(output))
        header = (GEN/'link_clips.h').read_text()
        cls.define = lambda name: int(re.search(r'#\s*define\s+'+name+r'\s+(-?\d+)', header)[1])
        cls.count = cls.define('LINK_SKIN_VERTICES')

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_real_skinner_matches_full_precision_reference_across_clips(self):
        self.lib.link_anim_upper_clear()    # no carry pose leaking in
        class Vec(ctypes.Structure):
            _fields_ = [('x',ctypes.c_int16),('y',ctypes.c_int16),('z',ctypes.c_int16)]
        class Limb(ctypes.Structure):
            _fields_ = [('child',ctypes.c_uint8),('sibling',ctypes.c_uint8),('pos',Vec)]
        class Clip(ctypes.Structure):
            _fields_ = [('first',ctypes.c_uint16),('count',ctypes.c_uint16)]
        limbs = (Limb*21).in_dll(self.lib,'link_limbs')
        clips = (Clip*type(self).define('LINK_CLIP_COUNT')).in_dll(self.lib,'link_clips')
        total = max(c.first+c.count for c in clips)
        roots = ((ctypes.c_int16*3)*total).in_dll(self.lib,'link_root')
        rotations = ((ctypes.c_int16*63)*total).in_dll(self.lib,'link_rotations')
        locals_ = (Vec*self.count).in_dll(self.lib,'link_vertex_local')
        owners = (ctypes.c_uint8*self.count).in_dll(self.lib,'link_vertex_limb')
        points = ((ctypes.c_int32*3)*self.count).in_dll(self.lib,'link_points')
        hierarchy = [dict(pos=(l.pos.x,l.pos.y,l.pos.z),child=l.child,sibling=l.sibling,far=1,near=1) for l in limbs]
        scale = type(self).define('LINK_ANIM_SCALE_Q16')/65536
        shift = [type(self).define('LINK_ANIM_SHIFT_'+a) for a in 'XYZ']
        pinned_flags = (ctypes.c_uint8*len(clips)).in_dll(self.lib,'link_clip_pinned')
        # AnimMovement clips draw their root at baseTransl as a child draws it.
        pinned_root = [type(self).define('LINK_PINNED_ROOT_'+a) for a in 'XYZ']
        for clip_id, clip in enumerate(clips):
            for frame in (0, clip.count//2, clip.count-1):
                self.lib.link_anim_pose(clip_id,frame,0)
                absolute = clip.first+frame
                rot = [rotations[absolute][i:i+3] for i in range(0,63,3)]
                root = list(roots[absolute])
                if pinned_flags[clip_id]:
                    root[0], root[2] = pinned_root[0], pinned_root[2]
                    if pinned_flags[clip_id] == 1:
                        root[1] = pinned_root[1]
                placed = {i:(m,o) for i,m,o,_ in model.walk_skeleton(hierarchy,rot,root)}
                blade = ((ctypes.c_int32 * 3) * 2)()
                self.lib.link_anim_blade(blade)
                matrix, origin = placed[15]  # PLAYER_LIMB_L_HAND minus one
                for end, local in enumerate(((0,400,0), (3000,400,0))):
                    expected = model.transform(matrix, origin, local)
                    for axis in range(3):
                        self.assertAlmostEqual(blade[end][axis] / 65536,
                            expected[axis] * scale + shift[axis], delta=.2,
                            msg=f'blade clip {clip_id} frame {frame} end {end}')
                # Player_PostLimbDrawGameplay attaches the child Deku Stick
                # to the same left hand.  Source RotateZYX(-0x8000,0,0x4000)
                # turns its long local +Y mesh axis into hand +X; melee line base
                # (0,400,0), tip (5000,400,0) per z_player_lib.c.
                stick = ((ctypes.c_int32 * 3) * 2)()
                self.lib.link_anim_stick(stick)
                for end, local in enumerate(((0,400,0), (5000,400,0))):
                    expected = model.transform(matrix, origin, local)
                    for axis in range(3):
                        self.assertAlmostEqual(stick[end][axis] / 65536,
                            expected[axis] * scale + shift[axis], delta=.2,
                            msg=f'stick clip {clip_id} frame {frame} end {end}')
                self.assertTrue(any(p[0] % 65536 for p in points), 'world fractions lost')
                for i, loc in enumerate(locals_):
                    matrix, origin = placed[owners[i]]
                    expected = model.transform(matrix,origin,(loc.x,loc.y,loc.z))
                    for axis in range(3):
                        value = (expected[axis]*scale+shift[axis])*(-1 if axis==1 else 1)
                        self.assertAlmostEqual(points[i][axis]/65536,value,delta=.2,
                            msg=f'clip {clip_id} frame {frame} vertex {i} axis {axis}')

    # Carrying is OoT's upper-body scheme (Player_UpdateUpperBody): the main
    # clip keeps the legs, the overlay clip owns UPPER..TORSO. OoT limbs
    # 0x01..0x15 import as 0..20, so UPPER (0x0A) is index 9.
    UPPER_FIRST_LIMB = 9
    WALK, CARRY_WAIT = 1, 90

    def _skin(self):
        points = ((ctypes.c_int32*3)*self.count).in_dll(self.lib,'link_points')
        return [tuple(p) for p in points]

    def _owners(self):
        return list((ctypes.c_uint8*self.count).in_dll(self.lib,'link_vertex_limb'))

    def test_overlay_splits_the_body_between_two_clips(self):
        """The upper limbs must take the carry clip's rotations while the
        lower limbs keep the walk pose -- that split is the whole fix, and a
        stub cannot show it.

        The comparison is against a reference skeleton walk rather than
        against a pure carry pose: the upper limbs hang off the walking
        waist, so their world positions legitimately differ from a carry
        clip posed on its own. What must match is the joint rotations."""
        owners = self._owners()
        upper = [i for i, o in enumerate(owners) if o >= self.UPPER_FIRST_LIMB]
        lower = [i for i, o in enumerate(owners) if o < self.UPPER_FIRST_LIMB]
        self.assertTrue(upper and lower, 'both halves must have vertices')

        class Vec(ctypes.Structure):
            _fields_ = [('x',ctypes.c_int16),('y',ctypes.c_int16),('z',ctypes.c_int16)]
        class Limb(ctypes.Structure):
            _fields_ = [('child',ctypes.c_uint8),('sibling',ctypes.c_uint8),('pos',Vec)]
        class Clip(ctypes.Structure):
            _fields_ = [('first',ctypes.c_uint16),('count',ctypes.c_uint16)]
        limbs = (Limb*21).in_dll(self.lib,'link_limbs')
        clips = (Clip*type(self).define('LINK_CLIP_COUNT')).in_dll(self.lib,'link_clips')
        total = max(c.first+c.count for c in clips)
        roots = ((ctypes.c_int16*3)*total).in_dll(self.lib,'link_root')
        rotations = ((ctypes.c_int16*63)*total).in_dll(self.lib,'link_rotations')
        locals_ = (Vec*self.count).in_dll(self.lib,'link_vertex_local')
        hierarchy = [dict(pos=(l.pos.x,l.pos.y,l.pos.z),child=l.child,
                          sibling=l.sibling,far=1,near=1) for l in limbs]
        scale = type(self).define('LINK_ANIM_SCALE_Q16')/65536
        shift = [type(self).define('LINK_ANIM_SHIFT_'+a) for a in 'XYZ']

        walk_at = clips[self.WALK].first + 4
        carry_at = clips[self.CARRY_WAIT].first
        # The joint table the overlay is supposed to build: walk below UPPER,
        # carry from UPPER up. This is sUpperBodyLimbCopyMap, done by hand.
        expected_rot = [list(rotations[walk_at][i:i+3]) if i//3 < self.UPPER_FIRST_LIMB
                        else list(rotations[carry_at][i:i+3])
                        for i in range(0, 63, 3)]
        placed = {i:(m,o) for i,m,o,_ in
                  model.walk_skeleton(hierarchy, expected_rot, list(roots[walk_at]))}

        self.lib.link_anim_upper_overlay(self.CARRY_WAIT, 0, 0)
        self.lib.link_anim_pose(self.WALK, 4, 0)
        blended = self._skin()
        self.lib.link_anim_upper_clear()

        for i, loc in enumerate(locals_):
            matrix, origin = placed[owners[i]]
            expected = model.transform(matrix, origin, (loc.x, loc.y, loc.z))
            for axis in range(3):
                value = (expected[axis]*scale+shift[axis])*(-1 if axis==1 else 1)
                self.assertAlmostEqual(blended[i][axis]/65536, value, delta=.2,
                    msg=f'vertex {i} (limb {owners[i]}) axis {axis} '
                        f'does not match the walk/carry split')

        # The overlay must actually change the arms, or the test proves nothing.
        self.lib.link_anim_pose(self.WALK, 4, 0)
        walk = self._skin()
        self.assertNotEqual([blended[i] for i in upper], [walk[i] for i in upper],
                            'overlay changed nothing: the two clips pose the arms alike')
        # ...and clearing must restore the plain walk pose on every limb.
        for i in lower:
            self.assertEqual(blended[i], walk[i],
                             f'lower vertex {i} (limb {owners[i]}) left the walk pose')

    def test_overlay_interpolates_between_its_own_frames(self):
        """The fraction must move the arms, or they would step while the legs
        interpolate."""
        owners = self._owners()
        upper = [i for i, o in enumerate(owners) if o >= self.UPPER_FIRST_LIMB]
        self.lib.link_anim_upper_clear()
        poses = []
        for fraction in (0, 128):
            self.lib.link_anim_upper_overlay(self.CARRY_WAIT, 0, fraction)
            self.lib.link_anim_pose(self.WALK, 4, 0)
            poses.append([self._skin()[i] for i in upper])
        self.lib.link_anim_upper_clear()
        self.assertNotEqual(poses[0], poses[1],
                            'overlay fraction was ignored; the arms would step')

    def test_airborne_mesh_does_not_sink_below_collision_origin(self):
        points = ((ctypes.c_int32*3)*self.count).in_dll(self.lib,'link_points')
        # Run -> airborne at every possible run frame. Mesh Y is inverted at
        # the render boundary; world/collision Y remains positive upwards.
        def bounds(clip, frame):
            self.lib.link_anim_pose(clip,frame,0)
            ys = [-p[1]/65536 for p in points]
            return min(ys), max(ys)
        run = [bounds(2,frame) for frame in range(20)]
        air = [bounds(3,frame) for frame in range(12)]
        for low, high in air:
            self.assertGreater(low, -12, 'baked root travel sinks mesh below actor')
            self.assertGreater(high, 40, 'head sank below expected body height')
        for _, run_head in run:
            self.assertLess(abs(air[0][1]-run_head), 20,
                            'run-to-jump must not teleport body downward')


@unittest.skipUnless(GCC.is_file(), 'host compiler required')
class FirstPersonSkinGate(unittest.TestCase):
    """Third person skins only LINK_BASE_VERTICES; the first-person arm tail is
    skinned only while aiming, and toggling forces a fresh pose."""
    def test_tail_vertices_skin_only_in_first_person(self):
        source = re.sub(r'^#include .*$', '', (ROOT/'src/link_anim.c').read_text(), flags=re.M)
        source = source.replace('#ifndef LINK_BASE_VERTICES', '#if 0')
        adapter = '''
#include <stdint.h>
#include <stdbool.h>
#include <math.h>
#include "link_clips.h"
typedef int32_t FIXED;
typedef uint16_t ANGLE;
#define X 0
#define Y 1
#define Z 2
#define LINK_BASE_VERTICES 10
#define toFIXED(x) ((FIXED)((x)*65536))
static FIXED slSin(ANGLE a) { return (FIXED)lround(sin(a*6.283185307179586/65536)*65536); }
static FIXED slCos(ANGLE a) { return (FIXED)lround(cos(a*6.283185307179586/65536)*65536); }
static FIXED slMulFX(FIXED a, FIXED b) { return (FIXED)(((int64_t)a*b)>>16); }
int32_t link_points[LINK_SKIN_VERTICES][3];
'''
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            out = pathlib.Path(tmp)/'gate.dll'
            env = dict(os.environ); env['PATH'] = str(GCC.parent)+os.pathsep+env.get('PATH','')
            subprocess.run([str(GCC), '-shared', '-O2', '-I'+str(GEN), '-x', 'c', '-',
                            str(GEN/'link_clips.c'), '-lm', '-o', str(out)],
                           input=adapter+source, text=True, env=env, check=True)
            lib = ctypes.CDLL(str(out))
            count = int(re.search(r'LINK_SKIN_VERTICES\s+(\d+)', (GEN/'link_clips.h').read_text())[1])
            points = ((ctypes.c_int32*3)*count).in_dll(lib, 'link_points')
            lib.link_anim_reset()
            lib.link_anim_first_person(False)
            lib.link_anim_pose(0, 0, 0)
            self.assertTrue(any(points[0]))
            self.assertTrue(all(points[i][a] == 0 for i in range(10, count) for a in range(3)))
            lib.link_anim_first_person(True)
            lib.link_anim_pose(0, 0, 0)            # same frame: the toggle forces it
            self.assertTrue(any(points[i][a] for i in range(10, count) for a in range(3)))

    def test_generator_puts_first_person_groups_last_and_emits_base_count(self):
        tool = (ROOT/'tools/build_link_model.py').read_text()
        self.assertIn("('fp_shoulder', 16, 'gLinkChildRightShoulderNearDL')", tool)
        self.assertIn("('fp_sling', 18, 'gLinkChildRightArmStretchedSlingshotDL')", tool)
        self.assertIn("'#define LINK_BASE_VERTICES %d'", tool)
        self.assertIn("('aim_ready','gPlayerAnim_link_bow_bow_ready',0,0,1)", tool)
        draw = (ROOT/'src/kokiri_sgl.c').read_text()
        self.assertIn('equipped.nbPoint = LINK_BASE_VERTICES;', draw)
