"""Offline Jo heap (jo_malloc) peak model: allocator replay + current disc fit."""
import contextlib
import io
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import heap_peak_model as model


class AllocatorReplay(unittest.TestCase):
    """The replay must behave like malloc.c through heap_profile.c."""

    def test_header_rounding_and_zone_order(self):
        h = model.Heap([('a', 64), ('b', 1024)])
        self.assertEqual(h.malloc('x', 10, model.FAST), 0)      # 10 + 8 -> 20 B in zone a
        self.assertEqual(h.keys['x'][1][1], 20)
        self.assertEqual(h.malloc('y', 60, model.FAST), 1)      # 68 B does not fit a's 44 B
        self.assertEqual(h.live, 20 + 68)

    def test_reuse_takes_first_hole_and_splits_tail(self):
        h = model.Heap([('a', 4096)])
        h.malloc('p', 1000, model.FAST)
        h.malloc('q', 100, model.FAST)
        h.free('p')                                             # hole below q, not retracted
        self.assertEqual(h.high[0], 1008 + 108)
        h.malloc('r', 100, model.REUSE)                         # first fit in the hole, tail split
        self.assertEqual(h.keys['r'][1][0], 0)
        self.assertEqual(h.keys['r'][1][1], 108)
        self.assertEqual([b[1] for b in h.blocks[0] if b[2]], [900])

    def test_fast_bumps_before_reusing_and_free_top_retracts(self):
        h = model.Heap([('a', 300)])
        h.malloc('p', 100, model.FAST)
        h.malloc('q', 100, model.FAST)
        h.free('p')
        h.malloc('r', 50, model.FAST)                           # FAST bumps at the top first
        self.assertEqual(h.keys['r'][1][0], 216)
        h.free('r')
        self.assertEqual(h.high[0], 216)

    def test_oom_merges_adjacent_holes_then_retries(self):
        h = model.Heap([('a', 256)])
        for k in 'abcd':
            h.malloc(k, 56, model.FAST)                         # 4 x 64 B fills the zone
        h.free('a')
        h.free('b')
        h.malloc('big', 100, model.FAST)                        # needs the merged 128 B hole
        self.assertEqual(h.keys['big'][1][0], 0)
        with self.assertRaises(model.OutOfMemory):
            h.malloc('none', 100, model.FAST)

    def test_sprite_guard_limit_matches_integer_percent(self):
        h = model.Heap([('a', 2475008)])
        limit = h.guard_limit()
        h.live = limit - 1
        self.assertLessEqual(h.percent(), model.SPRITE_GUARD_PERCENT)
        h.live = limit
        self.assertGreater(h.percent(), model.SPRITE_GUARD_PERCENT)


@unittest.skipUnless((ROOT / 'build' / 'cd' / 'SCENETAB.BIN').exists(), 'build/cd is not staged')
class CurrentDisc(unittest.TestCase):
    def test_every_scene_fits_the_jo_heap(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            rc = model.main([])
        text = out.getvalue()
        bad = [line for line in text.splitlines()
               if ' FAIL ' in line or ' DEGR ' in line or line.startswith('RESULT')]
        self.assertEqual(rc, 0, '\n'.join(bad))


if __name__ == '__main__':
    unittest.main()
