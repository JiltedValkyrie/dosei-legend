"""Checks for the baked locomotion clips and the data the runtime skinner uses.

The skinner itself runs on the SH-2 and cannot be exercised here. What these
tests can do is pin the things that would silently produce a wrong pose: the
animation offsets resolved out of gameplay_keep, the per-vertex limb ownership,
and -- most importantly -- that re-posing the bind-pose frame from the emitted
skinning tables reproduces the vertices that were baked into the model. That is
the one invariant tying the Python pipeline and the C skinner together.
"""

import pathlib
import re
import struct
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))

import build_link_model as blm  # noqa: E402

GENERATED = ROOT / 'build' / 'generated'


class PlayerFrameLayout(unittest.TestCase):
    """Independent packed fixtures include the trailing player face word.

    Frame-zero round trips cannot detect an incorrect frame stride.
    """

    def setUp(self):
        self.expected = []
        chunks = []
        words = (blm.LIMB_COUNT + 1) * 3
        for frame in range(8):
            values = tuple(frame * 100 + i for i in range(words))
            self.expected.append((values[:3], [values[i:i + 3]
                                 for i in range(3, words, 3)]))
            chunks.append(struct.pack('>%dhH' % words, *values, 0xABCD))
        self.data = b''.join(chunks)
        self.header = struct.pack('>hhI', 8, 0, 0x07000000)

    def test_nonzero_frames_skip_face_word(self):
        for frame in range(8):
            with self.subTest(frame=frame):
                _, root, rotations = blm.read_animation(
                    self.header, self.data, 0, frame, blm.LIMB_COUNT)
                self.assertEqual((root, rotations), self.expected[frame])

    def test_decimated_frames_skip_face_word(self):
        _, frames = blm.read_animation_frames(
            self.header, self.data, 0, 1, 3, 3, blm.LIMB_COUNT)
        self.assertEqual(frames, [self.expected[i] for i in (1, 4, 7)])


def rom_available():
    try:
        blm.read_object(blm.OOT_DEFAULT, 'gameplay_keep')
    except SystemExit:
        return False
    return True


@unittest.skipUnless(rom_available(), 'verified US 1.2 ROM not configured')
class AnimationOffsets(unittest.TestCase):
    """The clip offsets are derived from one anchor, so validate the anchor."""

    @classmethod
    def setUpClass(cls):
        cls.keep = blm.read_object(blm.OOT_DEFAULT, 'gameplay_keep')
        cls.animetion = blm.read_object(blm.OOT_DEFAULT, 'link_animetion')
        cls.offsets = blm.resolve_animations(blm.OOT_DEFAULT, cls.keep, 0x3200)

    def test_idle_anchor_matches_the_recipe(self):
        """The anchor is the recipe's own animation, so it must map to itself."""
        self.assertEqual(self.offsets[blm.IDLE_SYMBOL], 0x3200)

    def test_idle_is_complete_standing_cycle_with_small_loop_seam(self):
        # Player_GetIdleAnim: PLAYER_ANIMGROUP_wait, free hands. The old
        # 20-frame prefix of the 184-frame look-around fidget cannot loop.
        _, symbol, first, count, stride = next(
            clip for clip in blm.CLIPS if clip[0] == 'idle')
        self.assertEqual(symbol, 'gPlayerAnim_link_normal_wait_free')
        total, frames = blm.read_animation_frames(
            self.keep, self.animetion, self.offsets[symbol],
            first, count, stride, blm.LIMB_COUNT)
        self.assertEqual(first, 0)
        self.assertEqual(len(frames), total)
        for a, b in zip(frames[0][0], frames[-1][0]):
            self.assertLessEqual(abs(a - b), 2)
        for start, end in zip(frames[0][1], frames[-1][1]):
            for a, b in zip(start, end):
                delta = (b - a + 32768) % 65536 - 32768
                self.assertLessEqual(abs(delta), 32)

    def test_every_clip_resolves_and_decodes(self):
        for name, symbol, first, count, stride in blm.CLIPS:
            with self.subTest(clip=name):
                self.assertIn(symbol, self.offsets)
                total, frames = blm.read_animation_frames(
                    self.keep, self.animetion, self.offsets[symbol],
                    first, count, stride, blm.LIMB_COUNT)
                self.assertGreater(total, 0)
                expected = count if count else (total - 1 + stride - 1) // stride + 1
                self.assertEqual(len(frames), expected)
                if not count:
                    _, root, rotations = blm.read_animation(
                        self.keep, self.animetion, self.offsets[symbol], total - 1,
                        blm.LIMB_COUNT)
                    self.assertEqual(frames[-1], (root, rotations))
                for root, rotations in frames:
                    self.assertEqual(len(root), 3)
                    self.assertEqual(len(rotations), blm.LIMB_COUNT)

    def test_decimation_never_samples_past_the_clip(self):
        """A strided clip wraps rather than reading another animation's data."""
        for name, symbol, first, count, stride in blm.CLIPS:
            with self.subTest(clip=name):
                total, _ = blm.read_animation_frames(
                    self.keep, self.animetion, self.offsets[symbol],
                    first, count, stride, blm.LIMB_COUNT)
                self.assertLessEqual(first + (count - 1) * stride,
                                     total + first + total)

    def test_walk_and_run_are_not_decimated(self):
        """These two carry the locomotion read; they are kept at full rate."""
        for name, _symbol, _first, _count, stride in blm.CLIPS:
            if name in ('walk', 'run'):
                self.assertEqual(stride, 1, '%s must not be decimated' % name)

    def test_child_root_adjustment_matches_source(self):
        """Player_OverrideLimbDrawGameplayCommon: child root x/y/z * 0.64,
        except clips the source plays with DISABLE_CHILD_ROOT_ADJUSTMENT."""
        self.assertEqual(blm.CHILD_ROOT_SCALE, 0.64)
        self.assertEqual(blm.child_root((3377, -638, -2526)), (2161, -408, -1617))
        self.assertEqual(blm.child_root((5, -5, 0)), (3, -3, 0))
        names = {clip[0] for clip in blm.CLIPS}
        self.assertTrue(blm.RAW_ROOT_CLIPS <= names)
        for scaled in ('idle', 'walk', 'run', 'fall', 'landing', 'roll', 'jump',
                       'run_jump', 'run_jump_end', 'step100', 'step150',
                       'jump250', 'turn_look'):
            self.assertNotIn(scaled, blm.RAW_ROOT_CLIPS)
        # Child-authored clip ends standing at exactly the adjusted adult
        # standing pelvis: the two scalings agree, no double adjustment.
        _, stand, _ = blm.read_animation(
            self.keep, self.animetion, self.offsets['gPlayerAnim_clink_op3_tatiagari'],
            109, blm.LIMB_COUNT)
        _, idle, _ = blm.read_animation(self.keep, self.animetion, 0x3200, 0,
                                        blm.LIMB_COUNT)
        self.assertLessEqual(abs(stand[1] - blm.child_root(idle)[1]), 2)


@unittest.skipUnless(GENERATED.joinpath('link_clips.c').is_file(),
                     'link_clips.c not generated yet')
class GeneratedTables(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.source = GENERATED.joinpath('link_clips.c').read_text()
        cls.header = GENERATED.joinpath('link_clips.h').read_text()

    def define(self, name):
        return int(re.search(r'#\s*define\s+%s\s+(\d+)' % name, self.header)[1])

    def test_vertex_tables_match_the_scene_vertex_count(self):
        """Every POINT the skinner writes needs an owner and a local position.

        If these disagree the skinner walks off the end of one table, which on
        the SH-2 is silent corruption rather than a crash.
        """
        scene = GENERATED.joinpath('link_scene.h').read_text()
        vertices = int(re.search(r'#\s*define\s+LINK_VERTEX_COUNT\s+(\d+)', scene)[1])
        self.assertEqual(self.define('LINK_SKIN_VERTICES'), vertices)

        limbs = re.search(r'link_vertex_limb\[LINK_SKIN_VERTICES\] = \{(.*?)\};',
                          self.source, re.S)[1]
        self.assertEqual(len(re.findall(r'-?\d+', limbs)), vertices)

        locals_ = re.search(r'link_vertex_local\[LINK_SKIN_VERTICES\] = \{(.*?)\};',
                            self.source, re.S)[1]
        self.assertEqual(len(re.findall(r'\{[^}]*\}', locals_)), vertices)

    def test_every_vertex_owner_is_a_real_limb(self):
        limbs = re.search(r'link_vertex_limb\[LINK_SKIN_VERTICES\] = \{(.*?)\};',
                          self.source, re.S)[1]
        count = self.define('LINK_LIMB_COUNT')
        for value in re.findall(r'-?\d+', limbs):
            self.assertLess(int(value), count)

    def test_clip_ranges_stay_inside_the_frame_table(self):
        clips = re.findall(r'\{\s*(\d+),\s*(\d+)\s*\}',
                           re.search(r'link_clips\[LINK_CLIP_COUNT\] = \{(.*?)\};',
                                     self.source, re.S)[1])
        rotations = re.search(
            r'link_rotations\[\]\[LINK_LIMB_COUNT \* 3\] = \{(.*?)\};',
            self.source, re.S)[1]
        total = len(re.findall(r'\{[^}]*\}', rotations))
        self.assertEqual(len(clips), self.define('LINK_CLIP_COUNT'))
        for first, count in clips:
            self.assertGreater(int(count), 0)
            self.assertLessEqual(int(first) + int(count), total)

    def test_root_and_rotation_tables_have_the_same_frame_count(self):
        root = re.search(r'link_root\[\]\[3\] = \{(.*?)\};', self.source, re.S)[1]
        rotations = re.search(
            r'link_rotations\[\]\[LINK_LIMB_COUNT \* 3\] = \{(.*?)\};',
            self.source, re.S)[1]
        self.assertEqual(len(re.findall(r'\{[^}]*\}', root)),
                         len(re.findall(r'\{[^}]*\}', rotations)))

    def test_rotation_rows_carry_every_limb(self):
        rotations = re.search(
            r'link_rotations\[\]\[LINK_LIMB_COUNT \* 3\] = \{(.*?)\};',
            self.source, re.S)[1]
        expected = self.define('LINK_LIMB_COUNT') * 3
        for row in re.findall(r'\{([^}]*)\}', rotations):
            self.assertEqual(len(re.findall(r'-?\d+', row)), expected)

    def test_disc_frame_file_matches_the_host_arrays(self):
        """LINKANIM.BIN is what the Saturn poses from; the arrays are host-only.

        Header fields and the compiled digest are what link_anim_load()
        validates (see LinkAnimLoader for the rejection cases).
        """
        data = GENERATED.joinpath('LINKANIM.BIN').read_bytes()
        frames, limbs, digest = struct.unpack_from('>III', data, 4)
        self.assertEqual(data[:4], b'LAN1')
        self.assertEqual(frames, self.define('LINK_FRAME_COUNT'))
        self.assertEqual(limbs, self.define('LINK_LIMB_COUNT'))
        values = struct.unpack_from('>%dh' % ((len(data) - 16) // 2), data, 16)
        self.assertEqual(len(data), 16 + frames * (3 + limbs * 3) * 2)
        self.assertEqual(digest, int(re.search(
            r'#\s*define\s+LINK_FRAMES_DIGEST\s+0x([0-9A-F]+)u', self.header)[1], 16))
        clips = [tuple(map(int, m)) for m in re.findall(
            r'\{\s*(\d+),\s*(\d+)\s*\}',
            re.search(r'link_clips\[LINK_CLIP_COUNT\] = \{(.*?)\};', self.source, re.S)[1])]
        self.assertEqual(blm.frames_digest(clips, data[16:]), digest)
        root = re.search(r'link_root\[\]\[3\] = \{(.*?)\};', self.source, re.S)[1]
        rotations = re.search(
            r'link_rotations\[\]\[LINK_LIMB_COUNT \* 3\] = \{(.*?)\};',
            self.source, re.S)[1]
        expected = ([int(v) for v in re.findall(r'-?\d+', root)] +
                    [int(v) for v in re.findall(r'-?\d+', rotations)])
        self.assertEqual(list(values), expected)

    def test_saturn_build_takes_frames_from_the_disc(self):
        """The tables must not come back as work-RAM .rodata on the target."""
        makefile = (ROOT / 'makefile').read_text()
        self.assertIn('-DLINK_FRAMES_FROM_DISC', makefile)
        self.assertRegex(self.source, r'#ifndef LINK_FRAMES_FROM_DISC\s*\n'
                                      r'const int16_t link_root')
        self.assertIn('LINKANIM.BIN', (ROOT / 'build.sh').read_text())


GCC = pathlib.Path('C:/msys64/mingw64/bin/gcc.exe')

LOADER_ADAPTER = r'''
#include <stdint.h>
#include <stdbool.h>
#include <stdlib.h>
#include <string.h>
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
static unsigned char *disc; static int disc_length;
void test_disc(const unsigned char *data, int length)
{
    free(disc); disc = 0; disc_length = length;
    if (data) { disc = malloc(length); memcpy(disc, data, length); }
}
static void *jo_fs_read_file(const char *name, int *length)
{
    unsigned char *copy;
    if (!disc || strcmp(name, "LINKANIM.BIN")) return 0;
    copy = malloc(disc_length); memcpy(copy, disc, disc_length);
    *length = disc_length;
    return copy;
}
static void jo_free(void *p) { free(p); }
'''
LOADER_RESET = r'''
void test_unload(void) { free((void *)((const char *)link_root - 16)); link_root = 0; link_rotations = 0; }
'''


@unittest.skipUnless(GCC.is_file() and GENERATED.joinpath('LINKANIM.BIN').is_file(),
                     'host GCC and generated LINKANIM.BIN required')
class LinkAnimLoader(unittest.TestCase):
    """The real link_anim_load() (LINK_FRAMES_FROM_DISC) against disc variants."""

    @classmethod
    def setUpClass(cls):
        import ctypes, os, subprocess, tempfile
        cls.ctypes = ctypes
        cls.temp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        output = pathlib.Path(cls.temp.name) / 'loader.dll'
        source = re.sub(r'^#include .*$', '', (ROOT / 'src/link_anim.c').read_text(), flags=re.M)
        env = dict(os.environ)
        env['PATH'] = str(GCC.parent) + os.pathsep + env.get('PATH', '')
        subprocess.run([str(GCC), '-shared', '-O2', '-DLINK_FRAMES_FROM_DISC',
                        '-I' + str(GENERATED), '-x', 'c', '-', str(GENERATED / 'link_clips.c'),
                        '-lm', '-o', str(output)],
                       input=LOADER_ADAPTER + source + LOADER_RESET, text=True, env=env,
                       check=True)
        cls.lib = ctypes.CDLL(str(output))
        cls.lib.link_anim_load.restype = ctypes.c_bool
        cls.lib.test_disc.argtypes = [ctypes.c_char_p, ctypes.c_int]
        cls.good = GENERATED.joinpath('LINKANIM.BIN').read_bytes()

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def load(self, data):
        self.lib.test_disc(data, len(data) if data is not None else 0)
        ok = self.lib.link_anim_load()
        if ok:
            self.lib.test_unload()
        return ok

    def restamp(self, data):
        """What a stale-but-valid older build would ship: its own digest."""
        clips = [tuple(map(int, m)) for m in re.findall(
            r'\{\s*(\d+),\s*(\d+)\s*\}',
            re.search(r'link_clips\[LINK_CLIP_COUNT\] = \{(.*?)\};',
                      GENERATED.joinpath('link_clips.c').read_text(), re.S)[1])]
        return data[:12] + struct.pack('>I', blm.frames_digest(clips, data[16:])) + data[16:]

    def test_current_file_loads(self):
        self.assertTrue(self.load(self.good))

    def test_missing_truncated_and_corrupt_files_are_refused(self):
        self.assertFalse(self.load(None))
        self.assertFalse(self.load(self.good[:-2]))
        self.assertFalse(self.load(b'XAN1' + self.good[4:]))
        corrupt = bytearray(self.good)
        corrupt[1000] ^= 0x40
        self.assertFalse(self.load(bytes(corrupt)))

    def test_same_shape_stale_file_is_refused(self):
        """Edited root value, header digest recomputed: shape and header agree."""
        stale = bytearray(self.good)
        stale[16] ^= 0x01
        self.assertFalse(self.load(self.restamp(bytes(stale))))

    def test_reordered_frames_are_refused(self):
        """Swapping two root rows keeps any additive sum; the digest catches it."""
        body = bytearray(self.good)
        a, b = 16, 16 + 6 * 30
        body[a:a + 6], body[b:b + 6] = body[b:b + 6], body[a:a + 6]
        self.assertNotEqual(bytes(body), self.good)
        self.assertFalse(self.load(self.restamp(bytes(body))))


@unittest.skipUnless(rom_available(), 'verified US 1.2 ROM not configured')
class SkinningReproducesTheBakedPose(unittest.TestCase):
    """Re-pose the bind-pose frame from the skinning tables and compare.

    This is the invariant the C skinner depends on: posing a vertex through its
    owning limb's matrix must land where build_link_model.py baked it. If the
    limb walk, the joint offsets or the grounding shift drift apart, Link's
    limbs separate in game, and nothing else in the suite would catch it.
    """

    def test_bind_pose_round_trips(self):
        data = blm.read_object(blm.OOT_DEFAULT, blm.OBJECT)
        keep = blm.read_object(blm.OOT_DEFAULT, 'gameplay_keep')
        animetion = blm.read_object(blm.OOT_DEFAULT, 'link_animetion')
        limbs = blm.read_limbs(data)
        _frames, root, rotations = blm.read_animation(
            keep, animetion, 0x3200, 0, blm.LIMB_COUNT)
        root = blm.child_root(root)
        placed = blm.walk_skeleton(limbs, rotations, root)

        faces, original = blm.collect_equipment(data, keep, placed, blm.OOT_DEFAULT)
        blm.apply_primitive_colour(faces)
        scale = 0.0145
        faces = blm.scale_faces(faces, scale)
        faces = blm.drop_degenerate(faces)
        _, shift = blm.ground_and_centre(blm.scale_faces(original, scale))

        # Recompose the limb matrices independently, the way link_anim.c does:
        # an explicit child/sibling walk that accumulates each joint offset in
        # its parent's frame. Reusing walk_skeleton()'s own output here would
        # compare the baked pose against itself and pass no matter what the
        # skeleton said, so the traversal is rebuilt from link_limbs' fields.
        identity = ((1, 0, 0), (0, 1, 0), (0, 0, 1))
        matrices = {}
        stack = [(0, identity, (0, 0, 0))]
        while stack:
            index, parent_matrix, parent_origin = stack.pop()
            if index == blm.LIMB_NONE or index >= len(limbs):
                continue
            limb = limbs[index]
            offset = root if index == 0 else limb['pos']
            origin = blm.transform(parent_matrix, parent_origin, offset)
            matrix = blm.matmul(parent_matrix, blm.rotation_matrix(rotations[index]))
            matrices[index] = (matrix, origin)
            if limb['sibling'] != blm.LIMB_NONE:
                stack.append((limb['sibling'], parent_matrix, parent_origin))
            if limb['child'] != blm.LIMB_NONE:
                stack.append((limb['child'], matrix, origin))

        self.assertEqual(len(matrices), len(placed),
                         'the independent walk visited a different limb set')

        # Same composition the skinner performs, in the same order: pose the
        # limb-local vertex, scale to world units, then apply the grounding
        # shift that ground_and_centre() reported.
        # Compare against LINK.BIN's own vertex table rather than against the
        # `faces` this test just built. That file is what the game loads, so a
        # skeleton or joint offset that changed after it was written shows up
        # here as a mismatch instead of perturbing both sides of the comparison.
        model = GENERATED / 'LINK.BIN'
        if not model.is_file():
            self.skipTest('LINK.BIN not generated yet')
        baked_positions = self.read_positions(model)

        rebuilt = set()
        for face in faces:
            for local, owner in zip(face['local'], face['vertex_limbs']):
                matrix, origin = matrices[owner]
                posed = blm.transform(matrix, origin, local)
                rebuilt.add(tuple(
                    int(round(posed[i] * scale)) + shift[i] for i in range(3)))

        # Every vertex the file carries must be reachable from the skinning
        # tables. One world unit of slack absorbs the integer rounding the
        # baked path applies after scaling.
        for position in baked_positions:
            self.assertTrue(
                any(max(abs(position[i] - candidate[i]) for i in range(3)) <= 1
                    for candidate in rebuilt),
                'LINK.BIN vertex %s is not reproduced by the skinning tables'
                % (position,))

    @staticmethod
    def read_positions(path):
        """Vertex table out of the KFR1 container write_model() emitted."""
        import struct

        blob = path.read_bytes()
        magic, _version, count, _faces, vertex_offset = struct.unpack_from(
            '>5I', blob, 0)
        assert magic == blm.KFR1_MAGIC, 'not a KFR1 container'
        return [struct.unpack_from('>3h', blob, vertex_offset + i * 6)
                for i in range(count)]


if __name__ == '__main__':
    unittest.main()


class LandingRules(unittest.TestCase):
    """The landing thresholds mirror z_player.c; pin them against drift.

    The state machine itself is C and is not run here, but the constants and
    the branch order it encodes are worth holding still: they were read out of
    the decomp rather than recalled, and a later edit that "rounds" them would
    silently change how every fall in the slice resolves.
    """

    @classmethod
    def setUpClass(cls):
        cls.source = (ROOT / 'src' / 'link_anim_state.c').read_text()

    def constant(self, name):
        return int(re.search(r'#\s*define\s+%s\s+(\d+)' % name, self.source)[1])

    def test_thresholds_match_the_decomp(self):
        """fallDistance is world-space, so OoT's gates transfer unchanged.

        z_player.c:5831 computes it as fallStartHeight - world.pos.y, and this
        project keeps the scene's native collision coordinates without a scale
        conversion. An earlier revision rescaled these to 4/40 on the theory
        that 80/800 were model units; they are not.
        """
        self.assertEqual(self.constant('SHORT_LANDING_FALL'), 80)
        self.assertEqual(self.constant('ROLL_LANDING_FALL'), 800)

    def test_no_ground_follow_debounce(self):
        """Ordinary slope motion keeps the grounded flag, so no debounce.

        kokiri_collision_move_actor() snaps y onto the floor plane when it
        follows ground downhill, which is what kokiri_collision_fall() then
        tests for equality. A guard counting ungrounded steps was added for a
        blip that the collision code does not actually produce.
        """
        self.assertNotIn('FALL_STATE_STEPS', self.source)

    def test_roll_requires_forward_motion(self):
        """OoT rolls only with the stick forward; ours needs him still moving."""
        branch = re.search(
            r'if \(fall_units < ROLL_LANDING_FALL([^)]*)\)', self.source)
        self.assertIsNotNone(branch, 'landing roll branch not found')
        self.assertIn('speed', branch[1],
                      'the landing roll must still depend on forward motion')

    def test_short_landing_is_checked_before_the_roll(self):
        """A short fall must never reach the roll branch, as in z_player.c."""
        short = self.source.index('SHORT_LANDING_FALL')
        roll = self.source.index('ROLL_LANDING_FALL')
        self.assertLess(short, roll)


class DiagnosticsChord(unittest.TestCase):
    """The L+R+direction chord must consume its buttons and leave A alone.

    A is reserved for the action button, and the g/L/d readout is the only
    evidence for the unexplained rolling, so losing the toggle to a conflict
    would cost the one measurement that can settle it.
    """

    @classmethod
    def setUpClass(cls):
        cls.demo = (ROOT / 'src' / 'demo.c').read_text()
        cls.main = (ROOT / 'src' / 'main.c').read_text()
        # The chord moved into the control-mapping layer with the 2026-09-18
        # remap; demo.c only applies the decision now.
        cls.input = (ROOT / 'src' / 'player_input.c').read_text()

    def test_chord_still_detects_both_shoulders(self):
        # A direction is required as of the 2026-09-22 remap: L alone is look,
        # so plain L+R has to stay available as looking while guarding.
        self.assertIn('(held & CAMERA_L) && (held & CAMERA_R) &&', self.input)
        self.assertIn('(dpad & (CAMERA_UP | CAMERA_DOWN))', self.input)

    def test_recenter_is_skipped_while_the_chord_is_held(self):
        """Otherwise asking for diagnostics also recenters the camera."""
        chord = self.input.index('(held & CAMERA_L) && (held & CAMERA_R) &&')
        recenter = self.input.index('out->recenter = recentered;')
        self.assertGreater(recenter, chord,
                           'recenter must sit after the chord early return')

    def test_chord_is_gated_out_of_the_player_facing_build(self):
        """L+R must not block targeting plus shielding for the player."""
        gate = self.input.index('#ifndef DOSEI_CLEAN_TEST')
        chord = self.input.index('(held & CAMERA_L) && (held & CAMERA_R) &&')
        self.assertGreater(chord, gate)

    def test_a_no_longer_toggles_diagnostics(self):
        self.assertNotIn('jo_is_pad1_key_down(JO_KEY_A)', self.main,
                         'A is reserved for the action button')

    def test_state_and_evidence_share_one_line(self):
        """Corrupted poses can look like a roll without the state being ROLL.

        Reading the state and the landing evidence off separate rows is how
        that distinction gets recorded wrongly, so they print together.
        """
        self.assertIn('"s%d g%d L%d d%d', self.main)


class SkinningReposeRate(unittest.TestCase):
    """Measure how often the pose cache actually misses.

    An earlier revision masked the low bits of `fraction` to hit the cache
    more often, and a test checked that the mask was PRESENT rather than that
    it saved anything. It saved nothing: link_anim_state.c advances
    phase_ninths by 6 per step -- two thirds of a source frame -- so fraction
    only takes 0, 85 or 170 and a 32-step mask merges none of them.

    This measures the miss count instead, so a future quantisation attempt has
    to demonstrate a saving rather than merely exist.
    """

    @staticmethod
    def misses(step, updates=30, mask=0):
        """Distinct (frame, fraction) pairs, which is what link_anim_pose
        keys its early-out on. Mirrors advance() and link_anim_fraction()."""
        phase, last, missed = 0, None, 0
        for _ in range(updates):
            phase += step
            fraction = (phase % 9) * 256 // 9
            if mask:
                fraction &= ~mask
            key = (phase // 9, fraction)
            if key != last:
                missed += 1
                last = key
        return missed

    def test_fraction_only_takes_three_values_per_frame(self):
        """Six ninths per step means thirds of a frame, nothing finer."""
        seen = {(phase % 9) * 256 // 9 for phase in range(6, 6 * 30 + 1, 6)}
        self.assertEqual(sorted(seen), [0, 85, 170])

    def test_masking_the_phase_saves_nothing_at_this_cadence(self):
        """The reason the quantisation was reverted, pinned as a fact."""
        for step in (6, 2):     # locomotion, and fall's slower cadence
            self.assertEqual(self.misses(step, mask=31),
                             self.misses(step, mask=0),
                             'a 32-step mask merged no poses at step %d' % step)

    def test_no_phase_quantisation_is_present(self):
        """If one is reintroduced, the test above must justify it first."""
        source = (ROOT / 'src' / 'link_anim.c').read_text()
        self.assertNotIn('& ~31u', source)
