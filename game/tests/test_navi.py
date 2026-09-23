"""Run the real Navi follow code on the host; no emulator needed."""
import ctypes
import math
import os
import pathlib
import re
import subprocess
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
GCC = pathlib.Path('C:/msys64/mingw64/bin/gcc.exe')


def posed_head_height():
    """World height of Link's head joint over his feet, from the built model.

    Repeats link_anim.c's pose_skeleton() for the idle frame in floating
    point: each limb translates by its jointPos inside the parent's frame and
    then rotates ZYX. Limb 10 is the head, as tools/build_link_model.py names
    it (HEAD_LIMB). This is what src/navi.c's LINK_HEAD has to agree with.
    """
    source = (ROOT / 'build/generated/link_clips.c').read_text()
    header = (ROOT / 'build/generated/link_clips.h').read_text()
    define = lambda name: int(re.search(r'LINK_ANIM_' + name + r'\s+(-?\d+)',
                                        header).group(1))
    scale, shift_y = define('SCALE_Q16'), define('SHIFT_Y')
    table = re.search(r'link_limbs\[LINK_LIMB_COUNT\] = \{(.*?)\n\};',
                      source, re.S).group(1)
    limbs = [(int(c), int(sibling), (int(x), int(y), int(z)))
             for c, sibling, x, y, z in re.findall(
                 r'\{\s*(\d+),\s*(\d+),\s*\{\s*(-?\d+),\s*(-?\d+),\s*(-?\d+)\s*\}\s*\}',
                 table)]
    roots = re.search(r'link_root\[\]\[3\] = \{(.*?)\n\};', source, re.S).group(1)
    root = [int(v) for v in re.findall(r'-?\d+',
                                       re.findall(r'\{([^{}]*)\}', roots)[0])]
    spin = re.search(r'link_rotations\[\]\[LINK_LIMB_COUNT \* 3\] = \{(.*?)\n\};',
                     source, re.S).group(1)
    frame = [int(v) for v in re.findall(r'-?\d+',
                                        re.findall(r'\{([^{}]*)\}', spin)[0])]

    def rotation(values):
        ax, ay, az = [v * 2 * math.pi / 65536 for v in values]
        rx = [[1, 0, 0], [0, math.cos(ax), -math.sin(ax)],
              [0, math.sin(ax), math.cos(ax)]]
        ry = [[math.cos(ay), 0, math.sin(ay)], [0, 1, 0],
              [-math.sin(ay), 0, math.cos(ay)]]
        rz = [[math.cos(az), -math.sin(az), 0], [math.sin(az), math.cos(az), 0],
              [0, 0, 1]]
        mul = lambda a, b: [[sum(a[i][k] * b[k][j] for k in range(3))
                             for j in range(3)] for i in range(3)]
        return mul(mul(rz, ry), rx)

    parent = {0: None}

    def walk(index, above):
        while index != 255:
            parent[index] = above
            if limbs[index][0] != 255:
                walk(limbs[index][0], index)
            index = limbs[index][1]

    walk(limbs[0][0], 0)
    origin, matrix, queue, done = {}, {}, [0], set()
    while queue:
        index = queue.pop(0)
        offset = root if index == 0 else limbs[index][2]
        local = rotation(frame[index * 3:index * 3 + 3])
        above = parent[index]
        if above is None:
            origin[index], matrix[index] = list(offset), local
        else:
            up, base = matrix[above], origin[above]
            origin[index] = [base[a] + sum(up[a][k] * offset[k] for k in range(3))
                             for a in range(3)]
            matrix[index] = [[sum(up[a][k] * local[k][b] for k in range(3))
                              for b in range(3)] for a in range(3)]
        done.add(index)
        queue += [i for i in parent if parent[i] == index and i not in done]
    return origin[10][1] * scale / 65536 + shift_y


@unittest.skipUnless(GCC.is_file(), 'host compiler required')
class Navi(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        output = pathlib.Path(cls.tmp.name) / 'navi.dll'
        camera = ROOT.parent / 'shared/lib/camera'
        env = dict(os.environ)
        env['PATH'] = str(GCC.parent) + os.pathsep + env.get('PATH', '')
        subprocess.run([str(GCC), '-shared', '-O2', '-o', str(output),
                        '-I' + str(camera),
                        '-I' + str(ROOT.parent / 'shared/lib/collision'),
                        '-I' + str(ROOT / 'src'),
                        str(ROOT / 'src/navi.c'),
                        str(ROOT / 'tests/fixtures/navi_host.c'), '-lm'],
                       check=True, env=env)
        cls.lib = ctypes.CDLL(str(output))
        for name in ('navi_reset', 'navi_step'):
            getattr(cls.lib, name).argtypes = [ctypes.c_int32] * 3
        for name in ('navi_x', 'navi_y', 'navi_z'):
            getattr(cls.lib, name).restype = ctypes.c_int32
        cls.lib.navi_active.restype = ctypes.c_bool
        cls.lib.navi_dash_started.restype = ctypes.c_bool

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def distance(self, x, y, z):
        return max(abs(self.lib.navi_x() - x), abs(self.lib.navi_y() - y),
                   abs(self.lib.navi_z() - z))

    def test_spawns_beside_links_head(self):
        """At a real spawn she is beside his HEAD, not floating over it.

        demo.c hands over his FEET. The whole model is 66 units tall
        (LINK_CENTER_Y + LINK_RADIUS), so much more than that is the camera
        eye height (90) creeping back in as the anchor."""
        feet = (1000, 500, -200)
        self.lib.navi_reset(*feet)
        self.assertTrue(self.lib.navi_active())
        above = self.lib.navi_y() - feet[1]
        self.assertGreater(above, 40)
        self.assertLess(above, 70)
        self.assertLessEqual(max(abs(self.lib.navi_x() - feet[0]),
                                 abs(self.lib.navi_z() - feet[2])), 10)

    def test_head_anchor_matches_the_posed_model(self):
        """LINK_HEAD is the model's own head joint, re-derived here."""
        if not (ROOT / 'build/generated/link_clips.c').is_file():
            self.skipTest('generated clips required')
        declared = int(re.search(r'#define LINK_HEAD\s+(\d+)',
                                 (ROOT / 'src/navi.c').read_text()).group(1))
        self.assertEqual(declared, round(posed_head_height()))

    def test_follows_a_running_link(self):
        """Source state 1 keeps her within the orbit while he runs away."""
        x, y, z = 0, 0, 0
        self.lib.navi_reset(x, y, z)
        for _ in range(300):
            x += 5          # a shade under the run speed, every fixed step
            self.lib.navi_step(x, y, z)
        self.assertLessEqual(self.distance(x, y + 57, z), 40)

    def test_dash_cue_on_a_teleport(self):
        """Past 100 units she breaks into the source catch-up dash, once."""
        self.lib.navi_reset(0, 0, 0)
        # Two fixed steps make one 20 Hz En_Elf update, which is where the
        # source tests the distance.
        self.lib.navi_step(4000, 0, 0)
        self.lib.navi_step(4000, 0, 0)
        self.assertTrue(self.lib.navi_dash_started())
        cues = 0
        for _ in range(200):
            self.lib.navi_step(4000, 0, 0)
            cues += self.lib.navi_dash_started()
        self.assertEqual(cues, 0)
        self.assertLessEqual(self.distance(4000, 57, 0), 40)


if __name__ == '__main__':
    unittest.main()
