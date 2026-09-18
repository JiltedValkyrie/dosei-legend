"""Run the pure-C actor insertion solver against independent order oracles."""

import ctypes
import itertools
import os
import pathlib
import random
import shutil
import subprocess
import tempfile
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
GCC = shutil.which('gcc') or 'C:/msys64/mingw64/bin/gcc.exe'
COMPILER_AVAILABLE = pathlib.Path(GCC).is_file()


class Interval(ctypes.Structure):
    _fields_ = [('lo', ctypes.c_uint16), ('hi', ctypes.c_uint16),
                ('original', ctypes.c_uint16)]


@unittest.skipUnless(COMPILER_AVAILABLE, 'host C compiler required')
class ActorOrderTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        output = pathlib.Path(cls.tmp.name) / 'actor_order.dll'
        adapters = r'''
#include "actor_order.h"
int solve(const actor_order_interval *input, unsigned int count,
          unsigned int world_count, uint16_t *output, unsigned int capacity)
{
    return actor_order_solve(input, count, world_count, output, capacity);
}
int classify(int64_t camera, int64_t low, int64_t high, int64_t epsilon)
{
    return actor_order_classify_plane(camera, low, high, epsilon);
}
'''
        env = dict(os.environ)
        env['PATH'] = str(pathlib.Path(GCC).parent) + os.pathsep + env.get('PATH', '')
        subprocess.run([GCC, '-shared', '-O2', '-std=c99', '-Wall', '-Wextra',
                        '-Werror', '-I', str(ROOT / 'src'), '-x', 'c', '-',
                        '-o', str(output)], input=adapters, text=True,
                       env=env, check=True)
        cls.lib = ctypes.CDLL(str(output))
        cls.lib.solve.argtypes = [ctypes.POINTER(Interval), ctypes.c_uint,
                                 ctypes.c_uint, ctypes.POINTER(ctypes.c_uint16),
                                 ctypes.c_uint]
        cls.lib.solve.restype = ctypes.c_int
        cls.lib.classify.argtypes = [ctypes.c_int64] * 4
        cls.lib.classify.restype = ctypes.c_int

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def solve(self, entries, world_count, capacity=None):
        count = len(entries)
        inputs = (Interval * count)(*(Interval(*entry) for entry in entries))
        before = bytes(inputs)
        # Canaries verify that neither success nor failure writes past count.
        storage = (ctypes.c_uint16 * (count + 2))(*([0xA55A] * (count + 2)))
        output = ctypes.cast(ctypes.byref(storage, 2),
                             ctypes.POINTER(ctypes.c_uint16))
        accepted = self.lib.solve(inputs, count, world_count, output,
                                  count if capacity is None else capacity)
        self.assertEqual(bytes(inputs), before)
        self.assertEqual(storage[0], 0xA55A)
        self.assertEqual(storage[count + 1], 0xA55A)
        result = list(storage)[1:-1]
        if not accepted:
            self.assertEqual(result, [0xA55A] * count)
        return bool(accepted), result

    def test_no_constraints_keeps_every_original_slot(self):
        entries = [(0, 6, slot) for slot in (0, 0, 1, 3, 3, 6)]
        self.assertEqual(self.solve(entries, 6),
                         (True, [entry[2] for entry in entries]))

    def test_floor_then_actor_then_wall_preserves_both_input_orders(self):
        # W2 is floor that must precede both actors; W4 is an occluding wall.
        accepted, slots = self.solve([(3, 4, 1), (3, 4, 5)], 6)
        self.assertTrue(accepted)
        self.assertEqual(slots, [3, 4])
        merged = []
        actor = 0
        for slot in range(7):
            while actor < len(slots) and slots[actor] == slot:
                merged.append(('A', actor))
                actor += 1
            if slot < 6:
                merged.append(('W', slot))
        self.assertEqual([i for kind, i in merged if kind == 'W'], list(range(6)))
        self.assertEqual([i for kind, i in merged if kind == 'A'], [0, 1])
        for i in range(2):
            self.assertLess(merged.index(('W', 2)), merged.index(('A', i)))
            self.assertLess(merged.index(('A', i)), merged.index(('W', 4)))

    def test_later_upper_bound_moves_earlier_actor_without_reversing_it(self):
        self.assertEqual(self.solve([(0, 8, 6), (0, 3, 7)], 8),
                         (True, [3, 3]))

    def test_earlier_lower_bound_moves_later_actor_without_reversing_it(self):
        self.assertEqual(self.solve([(6, 8, 1), (0, 8, 2)], 8),
                         (True, [6, 6]))

    def test_conflicting_floor_wall_constraints_leave_output_untouched(self):
        self.assertFalse(self.solve([(5, 8, 2), (0, 4, 6)], 8)[0])
        self.assertFalse(self.solve([(5, 4, 2)], 8)[0])

    def test_invalid_input_and_capacity_leave_output_untouched(self):
        for entries, world_count, capacity in (
                ([(0, 7, 1)], 6, 1),
                ([(0, 6, 7)], 6, 1),
                ([(0, 6, 4), (0, 6, 3)], 6, 2),
                ([(0, 6, 1), (0, 6, 2)], 6, 1),
                ([(0, 6, 1)], 65536, 1)):
            with self.subTest(entries=entries, world_count=world_count):
                self.assertFalse(self.solve(entries, world_count, capacity)[0])
        marker = ctypes.c_uint16(0xA55A)
        self.assertEqual(self.lib.solve(None, 1, 1, ctypes.byref(marker), 1), 0)
        self.assertEqual(marker.value, 0xA55A)
        entry = Interval(0, 1, 0)
        self.assertEqual(self.lib.solve(ctypes.byref(entry), 1, 1, None, 1), 0)

    def test_empty_inputs_world_and_uint16_final_slot(self):
        self.assertEqual(self.lib.solve(None, 0, 0, None, 0), 1)
        self.assertEqual(self.solve([(0, 0, 0)] * 3, 0), (True, [0, 0, 0]))
        self.assertEqual(self.solve([(65535, 65535, 0)], 65535),
                         (True, [65535]))

    def test_random_cases_match_exhaustive_feasibility_and_nearest_oracle(self):
        rng = random.Random(18371)
        for _ in range(600):
            world_count, count = rng.randrange(6), rng.randrange(1, 6)
            originals = sorted(rng.randrange(world_count + 1) for _ in range(count))
            bounds = [sorted((rng.randrange(world_count + 1),
                              rng.randrange(world_count + 1))) for _ in originals]
            entries = [(lo, hi, original) for (lo, hi), original in zip(bounds, originals)]
            feasible = [candidate for candidate in itertools.combinations_with_replacement(
                range(world_count + 1), count)
                if all(lo <= slot <= hi for (lo, hi), slot in zip(bounds, candidate))]
            accepted, slots = self.solve(entries, world_count)
            self.assertEqual(accepted, bool(feasible), entries)
            if not accepted:
                continue
            self.assertIn(tuple(slots), feasible)
            for i, original in enumerate(originals):
                self.assertEqual(abs(slots[i] - original),
                                 min(abs(candidate[i] - original) for candidate in feasible))

    def test_plane_side_support_contact_and_wall_occlusion(self):
        # Ground y=0, saved camera y=71, posed actor wholly y>=0.
        self.assertEqual(self.lib.classify(71, 0, 90, 0), 1)
        self.assertEqual(self.lib.classify(-71, -90, 0, 0), 1)
        # Wall x=700 separates saved camera x=651 from Link near x=773.
        self.assertEqual(self.lib.classify(-49, 55, 90, 0), 2)
        self.assertEqual(self.lib.classify(49, -90, -55, 0), 2)

    def test_plane_ambiguity_does_not_forgive_penetration(self):
        for camera, low, high, epsilon in (
                (71, -1, 90, 2), (71, 0, 0, 0), (0, 1, 90, 0),
                (2, 10, 90, 2), (-2, -90, -10, 2), (71, 90, 0, 0),
                (71, 0, 90, -1)):
            self.assertEqual(self.lib.classify(camera, low, high, epsilon), 0)
        self.assertEqual(self.lib.classify(-(1 << 63), -(1 << 63), -1, 0), 1)
        self.assertEqual(self.lib.classify((1 << 63) - 1, 1, (1 << 63) - 1, 0), 1)

    def test_saved_neighbor_decal_is_behind_actor_without_center_containment(self):
        # Source faces 566/567 form this y=0 decal. The saved Link center is
        # outside its XZ footprint, but nearby posed boot vertices overlap it.
        footprint = [(666, 255), (707, 399), (851, 370), (814, 223)]
        center = (773, 224)
        crosses = [(b[0] - a[0]) * (center[1] - a[1]) -
                   (b[1] - a[1]) * (center[0] - a[0])
                   for a, b in zip(footprint, footprint[1:] + footprint[:1])]
        self.assertTrue(any(value < 0 for value in crosses))
        self.assertTrue(any(value > 0 for value in crosses))
        self.assertEqual(self.lib.classify(71, 0, 90, 0), 1)


if __name__ == '__main__':
    unittest.main()
