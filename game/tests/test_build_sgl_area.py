"""Guards for the project-local SGL work area (tools/build_sgl_area.py).

These check the layout arithmetic and the patched object on the host. They
cannot prove SGL accepts the area at runtime -- that is what the Kronos
acceptance check (subm 2060 / rej 0 / ok mask 1) is for.
"""

import pathlib
import struct
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))

import build_sgl_area as area  # noqa: E402

sys.path.insert(0, str(ROOT.parent / 'tools/launcher'))
from project_config import read_paths

SDK_OBJECT = (pathlib.Path(read_paths()['jo_engine']) / 'Compiler' / 'COMMON'
              / 'SGL_302j' / 'LIB_ELF' / 'SGLAREA.O')
GENERATED = ROOT / 'build/generated' / 'sglarea.o'

# The scene this area exists to fit.
SCENE_POLYGONS = 2060
SCENE_VERTICES = 1268


@unittest.skipUnless(SDK_OBJECT.is_file(), '%s not present' % SDK_OBJECT)
class StockAreaTest(unittest.TestCase):
    """The formulas must keep matching the SDK object they were derived from."""

    @classmethod
    def setUpClass(cls):
        cls.head = area.read_header(SDK_OBJECT.read_bytes())

    def test_stock_header_matches_known_sgl_302j_area(self):
        area.verify_stock_layout(self.head)   # exits the process on mismatch

    def test_stock_limits_are_the_ones_that_refused_the_scene(self):
        self.assertEqual(self.head['MaxPolygons'], 1761)
        self.assertEqual(self.head['MaxVertices'], 2500)
        self.assertLess(self.head['MaxPolygons'], SCENE_POLYGONS,
                        'stock area would not have refused the scene')

    def test_documented_buffer_formulas(self):
        mp, mv = self.head['MaxPolygons'], self.head['MaxVertices']
        self.assertEqual(self.head['SortListSize'], 12 * (mp + 6))
        self.assertEqual(self.head['SpriteBufSize'], 72 * (mp + 5))
        self.assertEqual(self.head['CommandBuf'] - self.head['Pbuffer'], 16 * mv)
        self.assertEqual(self.head['SpriteBuf'] - self.head['Zbuffer'],
                         area.ZBUFFER_BYTES)

    def test_sdk_object_is_never_written_to(self):
        """The generator must only ever read the shared SDK."""
        source = ROOT / 'tools' / 'build_sgl_area.py'
        text = source.read_text()
        self.assertIn('read_bytes()', text)
        for forbidden in ('args.source.write', 'source.write_bytes'):
            self.assertNotIn(forbidden, text)


class LayoutTest(unittest.TestCase):
    def test_layout_is_aligned_contiguous_and_ends_at_work_ram_top(self):
        base, total, layout = area.plan(2100, 2500, 1.10)
        area.check_layout(layout, base)       # alignment + overlap + end
        self.assertEqual(base + total, area.WORK_RAM_END)

    def test_layout_covers_the_scene_with_headroom(self):
        _, _, layout = area.plan(2100, 2500, 1.10)
        sizes = {name: size for name, _, size in layout}
        self.assertGreaterEqual(sizes['SortList'], 12 * (SCENE_POLYGONS + 6))
        self.assertGreaterEqual(sizes['SpriteBuf'], 72 * (SCENE_POLYGONS + 5))
        self.assertGreaterEqual(sizes['Pbuffer'], 16 * SCENE_VERTICES)

    def test_tail_buffers_keep_their_stock_addresses(self):
        """Only the growing buffers move; TransList/MasterStack must not."""
        _, _, layout = area.plan(2100, 2500, 1.10)
        addrs = {name: addr for name, addr, _ in layout}
        self.assertEqual(addrs['TransList'], area.STOCK['TransList'])
        self.assertEqual(addrs['MasterStack'], area.STOCK['MasterStack'])

    def test_larger_limits_lower_the_base(self):
        small, _, _ = area.plan(2100, 2500, 1.10)
        large, _, _ = area.plan(3000, 2500, 1.10)
        self.assertLess(large, small)

    def test_overlap_is_rejected(self):
        base, _, layout = area.plan(2100, 2500, 1.10)
        name, addr, size = layout[1]
        corrupted = list(layout)
        corrupted[1] = (name, addr - area.ALIGN, size)   # overlap the previous
        with self.assertRaises(SystemExit):
            area.check_layout(corrupted, base)


@unittest.skipUnless(GENERATED.is_file(), 'generated/sglarea.o not built')
class GeneratedAreaTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.blob = GENERATED.read_bytes()
        cls.head = area.read_header(cls.blob)

    def test_limits_cover_the_scene(self):
        self.assertGreaterEqual(self.head['MaxPolygons'], SCENE_POLYGONS)
        self.assertGreaterEqual(self.head['MaxVertices'], SCENE_VERTICES)

    def test_sizes_follow_the_formulas_for_the_new_limit(self):
        mp = self.head['MaxPolygons']
        self.assertEqual(self.head['SortListSize'], 12 * (mp + 6))
        self.assertEqual(self.head['SpriteBufSize'], 72 * (mp + 5))

    def test_buffers_are_aligned_and_inside_work_ram(self):
        for name in ('SortList', 'CLOfstBuf', 'Zbuffer', 'SpriteBuf', 'Pbuffer',
                     'CommandBuf', 'TransList', 'MasterStack'):
            addr = self.head[name]
            self.assertEqual(addr % area.ALIGN, 0, name)
            self.assertLess(addr, area.WORK_RAM_END, name)
            self.assertGreaterEqual(addr, 0x06000000, name)

    def test_declared_sizes_do_not_overrun_the_next_buffer(self):
        self.assertLessEqual(self.head['SortList'] + self.head['SortListSize'],
                             self.head['CLOfstBuf'])
        self.assertLessEqual(self.head['SpriteBuf'] + self.head['SpriteBufSize'],
                             self.head['Pbuffer'])

    @unittest.skipUnless(SDK_OBJECT.is_file(), 'SDK object not present')
    def test_only_the_header_differs_from_the_sdk_object(self):
        stock = SDK_OBJECT.read_bytes()
        self.assertEqual(len(self.blob), len(stock), 'object size changed')
        header_end = area.SLPROG_FILE_OFFSET + 0x40
        self.assertEqual(self.blob[header_end:], stock[header_end:],
                         'generator modified more than the SLPROG header')

    def test_untouched_fields_are_preserved(self):
        stock = area.read_header(SDK_OBJECT.read_bytes())
        for name in ('SlaveStack', 'PCM_Work', 'PCM_WkSize', 'MaxEvents',
                     'EventSize', 'MaxWorks', 'WorkSize'):
            self.assertEqual(self.head[name], stock[name], name)


@unittest.skipUnless((ROOT / 'build/game.map').is_file(), 'game.map not built')
class BoundaryTest(unittest.TestCase):
    def test_bss_ends_below_the_work_area(self):
        base, _, _ = area.plan(2100, 2500, 1.10)
        end = area.check_boundary(ROOT / 'build/game.map', base, fatal=False)
        if end is None:
            self.skipTest('no _end symbol in map')
        self.assertLessEqual(end, base,
                             '.bss overruns the SGL work area base')


if __name__ == '__main__':
    unittest.main()
