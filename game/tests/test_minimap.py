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
        # 2px left padding preserves x=202 on a zero-scroll HUD page.
        self.assertEqual(values[:10], [13, 8, 96, 62, 202, 160, 8, 8, 660, -730])

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
            self.assertLessEqual(int(cells), 0x2000)

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
        code = [UP, UP, DOWN, DOWN, LEFT, RIGHT, LEFT, RIGHT, B, A]
        self.assertFalse(self.press(code))
        self.assertTrue(self.press([START]))

    def test_wrong_press_breaks_it_and_extra_up_is_kept(self):
        self.assertFalse(self.press([UP, UP, DOWN, B, DOWN, LEFT, RIGHT, LEFT, RIGHT, B, A, START]))
        self.assertTrue(self.press([UP, UP, UP, DOWN, DOWN, LEFT, RIGHT, LEFT, RIGHT, B, A, START]))

    def test_holding_does_not_repeat(self):
        self.lib.feed(UP)
        self.lib.feed(UP)           # still held: not a second press
        self.lib.feed(0)
        self.assertFalse(self.press([DOWN, DOWN, LEFT, RIGHT, LEFT, RIGHT, B, A, START]))

    def test_old_code_without_b_does_not_unlock(self):
        self.assertFalse(self.press([UP,UP,DOWN,DOWN,LEFT,RIGHT,LEFT,RIGHT,A,START]))


@unittest.skipUnless(GCC.is_file(), 'host compiler required')
class CheatSession(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        source = (ROOT/'src/minimap.c').read_text()
        def function(name):
            match = re.search(r'(?:bool|void)\s+'+name+r'\([^)]*\)\s*\{', source)
            start = match.start()
            end = match.end()
            depth = 1
            while depth:
                if source[end] == '{': depth += 1
                if source[end] == '}': depth -= 1
                end += 1
            return source[start:end]
        # Compile the real state functions and the real VBlank Start routing.
        demo = (ROOT/'src/demo.c').read_text()
        start = demo.index('static void demo_vblank(void)')
        body = demo.index('{', start)+1
        prefix = demo[body:demo.index('    skip_input_sample(',body)]
        src = '#include "cheat_code.h"\n#include "input_edge.h"\n'
        src += 'static cheat_code_t cheat; static volatile bool enemy_dots,chime;\n'
        src += '\n'.join(function(n) for n in ('minimap_cheat_sample', 'minimap_session_reset',
                                              'minimap_enemy_dots', 'minimap_cheat_chime'))
        src += '\nstatic input_edge_t start_edge; static uint16_t pad;\n'
        src += 'static bool jo_is_pad1_available(void) { return true; }\n'
        src += 'static uint16_t demo_pad_snapshot(void) { return pad; }\n'
        src += 'int tick(unsigned held) { pad=held;'+prefix+'return input_edge_consume(&start_edge); }\n'
        c = pathlib.Path(cls.tmp.name)/'session.c'
        c.write_text(src)
        dll = c.with_suffix('.dll')
        env = dict(os.environ, PATH=str(GCC.parent)+os.pathsep+os.environ.get('PATH',''))
        subprocess.run([str(GCC),'-shared','-O2','-I'+str(ROOT/'src'),
                        '-I'+str(ROOT.parent/'shared/lib/camera'),
                        '-I'+str(ROOT.parent/'shared/lib/collision'),str(c),'-o',str(dll)],check=True,env=env)
        cls.lib = ctypes.CDLL(str(dll))

    @classmethod
    def tearDownClass(cls): cls.tmp.cleanup()
    def setUp(self):
        self.lib.minimap_session_reset()
        self.lib.tick(0)
    def code(self):
        for button in (UP,UP,DOWN,DOWN,LEFT,RIGHT,LEFT,RIGHT,B,A):
            self.lib.tick(button)
            self.lib.tick(0)
        return self.lib.tick(START)

    def test_final_start_does_not_pause_or_repeat_while_held(self):
        self.assertFalse(self.code())
        self.assertTrue(self.lib.minimap_enemy_dots())
        self.assertFalse(self.lib.tick(START))
        self.lib.tick(0)
        self.assertTrue(self.lib.tick(START)) # a new ordinary Start still works

    def test_toggle_persists_until_explicit_session_reset(self):
        self.code()
        for _ in range(100): self.lib.tick(0)
        self.assertTrue(self.lib.minimap_enemy_dots())
        self.assertTrue(self.lib.minimap_cheat_chime())
        self.assertFalse(self.lib.minimap_cheat_chime())
        self.lib.minimap_session_reset()
        self.assertFalse(self.lib.minimap_enemy_dots())
        self.assertFalse(self.lib.minimap_cheat_chime())

    def test_second_code_turns_dots_off(self):
        self.code()
        self.lib.tick(0)
        self.code()
        self.assertFalse(self.lib.minimap_enemy_dots())


if __name__ == '__main__':
    unittest.main()
