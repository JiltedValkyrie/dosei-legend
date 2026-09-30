import ctypes
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
GCC = Path('C:/msys64/mingw64/bin/gcc.exe')
sys.path.insert(0, str(ROOT / 'tools'))
import build_room_scene


@unittest.skipUnless(GCC.is_file(), 'host C compiler required')
class PortalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        folder = Path(cls.temp.name)
        source = folder / 'portal.c'
        source.write_text('#include "room_portal.h"\nint side(unsigned k,int x,int y,int z) '
                          '{ return room_portal_side(k,x,y,z); }\n')
        env = dict(os.environ, PATH=str(GCC.parent) + os.pathsep + os.environ.get('PATH', ''))
        subprocess.run([str(GCC), '-shared', '-O2', '-Wall', '-Wextra', '-Werror',
                        '-I' + str(ROOT / 'src'), str(source), '-o', str(folder / 'portal.dll')],
                       env=env, check=True)
        cls.lib = ctypes.CDLL(str(folder / 'portal.dll'))

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_horizontal_source_bands_and_hysteresis(self):
        self.assertEqual(self.lib.side(4, 0, 0, -75), 0)
        self.assertEqual(self.lib.side(4, 0, 0, 75), 1)
        for z in (-101, -100, -50, 0, 50, 100, 101):
            self.assertEqual(self.lib.side(4, 0, 0, z), -1)
        for y in (-50, 200):
            self.assertEqual(self.lib.side(4, 0, y, 75), -1)
        self.assertEqual(self.lib.side(4, 199, 0, 75), 1)
        self.assertEqual(self.lib.side(4, 200, 0, 75), -1)
        self.assertEqual(self.lib.side(6, 100, 0, 75), -1)
        self.assertEqual(self.lib.side(6, 99, 0, 75), 1)

    def test_vertical_uses_feet_height_and_circular_radius(self):
        self.assertEqual(self.lib.side(2, 0, 75, 0), 0)
        self.assertEqual(self.lib.side(2, 0, -75, 0), 1)
        for y in (-200, -50, 0, 50, 200):
            self.assertEqual(self.lib.side(2, 0, y, 0), -1)
        self.assertEqual(self.lib.side(2, 119, 75, 0), 0)
        self.assertEqual(self.lib.side(2, 120, 75, 0), -1)
        self.assertEqual(self.lib.side(2, 90, 75, 90), -1)
        self.assertEqual(self.lib.side(2, 1000000, 75, 1000000), -1)

    def test_unimplemented_kinds_never_open(self):
        for kind in (1, 3, 5, 7, 255):
            self.assertEqual(self.lib.side(kind, 0, 75, 75), -1)


class SourcePortals(unittest.TestCase):
    OOT = Path('D:/Workspace-Claude/game-decomps/n64/oot')

    @unittest.skipUnless(OOT.is_dir(), 'local source required')
    def test_all_nine_woods_tunnels_keep_source_endpoints(self):
        portals = build_room_scene.transitions(self.OOT, prefix='spot10', room_count=10)
        self.assertEqual(len(portals), 9)
        self.assertTrue(all(p['kind'] == 0 for p in portals))
        self.assertTrue(all(0 <= p['front'] < 10 and 0 <= p['back'] < 10 for p in portals))

    @unittest.skipUnless(OOT.is_dir(), 'local source required')
    def test_dungeon_keeps_shutter_types_and_source_gate_flags(self):
        self.assertEqual(build_room_scene.transitions(self.OOT, prefix='ydan', room_count=1), [])
        dungeon = build_room_scene.transitions(self.OOT, prefix='ydan', room_count=12)
        self.assertEqual(len(dungeon),12)
        self.assertEqual(sum(p['kind']>=8 for p in dungeon),9)
        self.assertEqual([p['flag'] for p in dungeon if p['kind']==10],[3,60,3,4])
        portals = build_room_scene.transitions(self.OOT, prefix='spot04', room_count=3)
        self.assertTrue(portals)
        self.assertTrue(all(p['kind'] == 4 for p in portals))


if __name__ == '__main__':
    unittest.main()
