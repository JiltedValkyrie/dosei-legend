"""Minimap data against z_map_data.c and the reserved resources."""
import ctypes
import os
import pathlib
import re
import subprocess
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
GEN = ROOT / 'build/generated'
BIN = ROOT / 'build/cd/MINIMAP.BIN'


@unittest.skipUnless((GEN / 'minimap_data.h').is_file() and BIN.is_file(),
                     'generated minimap required')
class Minimap(unittest.TestCase):
    def test_kokiri_row_is_source_map_index_4(self):
        header = (GEN / 'minimap_data.h').read_text()
        row = re.search(r'\{ SAVE_SCENE_KOKIRI_FOREST, ([^}]*)\}', header)[1]
        values = [int(v) for v in row.split(',')]
        # cells 12x8, 96x62 at (202,160), sOwCompassInfo[4] = {8, 8, 660, -730}
        self.assertEqual(values[:10], [12, 8, 96, 62, 202, 160, 8, 8, 660, -730])

    def test_file_header_and_size(self):
        blob = BIN.read_bytes()
        header = (GEN / 'minimap_data.h').read_text()
        self.assertEqual(blob[:4], b'KMAP')
        self.assertEqual(len(blob), int(re.search(r'MINIMAP_FILE_BYTES (\d+)', header)[1]))
        cart = (ROOT / 'src/ram_cart.h').read_text()
        size = int(re.search(r'RAM_CART_MINIMAP_BYTES\s+0x([0-9A-F]+)u', cart)[1], 16)
        self.assertLessEqual(len(blob), size)

    def test_cells_fit_their_b0_reservation(self):
        header = (GEN / 'minimap_data.h').read_text()
        for cells in re.findall(r'\{ SAVE_SCENE_\w+,(?:[^,]*,){11} (\d+) \}', header):
            self.assertLessEqual(int(cells), 0x4000)

    def test_link_arrow_formula_lands_on_the_map(self):
        # Minimap_DrawCompassIcons for Kokiri Forest at the scene origin.
        x, z, sx, sz, ox, oy = 0, 0, 8, 8, 660, -730
        px = 160 + (ox + int(x / sx)) // 10
        py = 120 - (oy - int(z / sz)) // 10
        self.assertTrue(202 <= px < 298 and 160 <= py < 222, (px, py))

    def test_runtime_has_no_float_and_dots_need_the_cheat(self):
        source = (ROOT / 'src/minimap.c').read_text()
        self.assertNotIn('toFIXED(', source)
        self.assertNotIn('float', source)
        dots = source.index('gameplay_nut_body')
        self.assertLess(source.rfind('if (enemy_dots)', 0, dots), dots)
        self.assertGreater(source.rfind('if (enemy_dots)', 0, dots), 0)


GCC = pathlib.Path('C:/msys64/mingw64/bin/gcc.exe')
UP, DOWN, LEFT, RIGHT = 0x1000, 0x2000, 0x4000, 0x8000
A, B, START = 0x0400, 0x0100, 0x0800


@unittest.skipUnless(GCC.is_file(), 'host compiler required')
class CheatCode(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        out = pathlib.Path(cls.tmp.name) / 'cheat.dll'
        src = ('#include "cheat_code.h"\n'
               'static cheat_code_t c;\n'
               'void reset(void) { c.previous = 0; c.position = 0; }\n'
               'int feed(unsigned int held) { return cheat_code_sample(&c, (uint16_t)held); }\n')
        env = dict(os.environ, PATH=str(GCC.parent) + os.pathsep + os.environ.get('PATH', ''))
        subprocess.run([str(GCC), '-shared', '-O2', '-I' + str(ROOT / 'src'),
                        '-I' + str(ROOT.parent / 'shared/lib/camera'),
                        '-I' + str(ROOT.parent / 'shared/lib/collision'),
                        '-x', 'c', '-', '-o', str(out)], input=src, text=True,
                       env=env, check=True)
        cls.lib = ctypes.CDLL(str(out))

    def press(self, keys):
        done = False
        for k in keys:
            done = self.lib.feed(k) or done
            self.lib.feed(0)
        return done

    def setUp(self):
        self.lib.reset()

    def test_code_completes_on_start(self):
        code = [UP, UP, DOWN, DOWN, LEFT, RIGHT, LEFT, RIGHT, A]
        self.assertFalse(self.press(code))
        self.assertTrue(self.press([START]))

    def test_wrong_press_breaks_it_and_extra_up_is_kept(self):
        self.assertFalse(self.press([UP, UP, DOWN, B, DOWN, LEFT, RIGHT, LEFT, RIGHT, A, START]))
        self.assertTrue(self.press([UP, UP, UP, DOWN, DOWN, LEFT, RIGHT, LEFT, RIGHT, A, START]))

    def test_holding_does_not_repeat(self):
        self.lib.feed(UP)
        self.lib.feed(UP)           # still held: not a second press
        self.lib.feed(0)
        self.assertFalse(self.press([DOWN, DOWN, LEFT, RIGHT, LEFT, RIGHT, A, START]))


if __name__ == '__main__':
    unittest.main()
