"""Run the SGL 3.02j queue adapter on fake 32-bit Saturn addresses."""
import ctypes
import os
import pathlib
import random
import subprocess
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
GCC = pathlib.Path('C:/msys64/mingw64/bin/gcc.exe')
BASE = 0x06000000
SLOTS = 2605
FIXTURE = r'''
#include <string.h>
#include "sgl_order_queue.h"
static sgl_order_command commands[5210], saved[5210];
static uint32_t heads[512], saved_heads[512], output[2600];
static uint16_t scratch[512];
static unsigned int count;
static sgl_order_queue queue = {
    heads, (volatile unsigned char *)commands, 0x06000000, sizeof(commands)
};
void reset(void) { memset(commands,0,sizeof(commands)); memset(heads,0,sizeof(heads)); }
void add(unsigned int slot,unsigned int key,unsigned int tag,unsigned int window) {
    unsigned int head = window*128+(key>>8);
    commands[slot].key=(uint16_t)key; commands[slot].grda=(uint16_t)tag;
    commands[slot].next=heads[head]; heads[head]=queue.sprite_address+slot*36;
}
int collect(unsigned int window) { return sgl_order_collect(&queue,window,output,2600,scratch,&count); }
unsigned int output_count(void) { return count; }
unsigned int output_at(unsigned int index) { return output[index]; }
int rebuild(unsigned int window,uint32_t *order,unsigned int n) {
    return sgl_order_rebuild(&queue,window,order,n,(unsigned char *)scratch,sizeof(scratch));
}
int find_window(void) {
    unsigned int window=99;
    int result=sgl_order_find_window(&queue,0x8000,0x8000,2600,&window);
    return result ? -result : (int)window;
}
void set_next(unsigned int slot,unsigned int address) { commands[slot].next=address; }
void set_head(unsigned int head,unsigned int address) { heads[head]=address; }
unsigned int head_at(unsigned int head) { return heads[head]; }
void set_key(unsigned int slot,unsigned int key) { commands[slot].key=(uint16_t)key; }
void snapshot(void) { memcpy(saved,commands,sizeof(commands)); memcpy(saved_heads,heads,sizeof(heads)); }
int unchanged(void) { return !memcmp(saved,commands,sizeof(commands)) && !memcmp(saved_heads,heads,sizeof(heads)); }
unsigned int seen_bytes(void) { return sgl_order_seen_bytes(&queue); }
'''


@unittest.skipUnless(GCC.is_file(), 'host compiler required')
class SglOrderQueue(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        output = pathlib.Path(cls.tmp.name) / 'sgl_order_queue.dll'
        env = dict(os.environ)
        env['PATH'] = str(GCC.parent) + os.pathsep + env.get('PATH', '')
        subprocess.run([str(GCC), '-shared', '-std=c99', '-Wall', '-Wextra',
                        '-Werror', '-O2', '-I' + str(ROOT / 'src'),
                        '-x', 'c', '-', '-o', str(output)], input=FIXTURE,
                       text=True, env=env, check=True)
        cls.lib = ctypes.CDLL(str(output))
        cls.lib.rebuild.argtypes = [ctypes.c_uint, ctypes.POINTER(ctypes.c_uint32), ctypes.c_uint]

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def setUp(self):
        self.lib.reset()

    def collect(self, window=0):
        self.assertEqual(self.lib.collect(window), 0)
        return [self.lib.output_at(i) for i in range(self.lib.output_count())]

    def rebuild(self, order, window=0):
        array = (ctypes.c_uint32 * len(order))(*order)
        return self.lib.rebuild(window, array, len(order))

    def test_exact_hardware_order_randomized_and_equal_key_ties(self):
        rng = random.Random(71)
        for trial in range(200):
            self.lib.reset()
            window = trial & 1
            offset = window * SLOTS
            count = 2600 if trial < 2 else rng.randrange(1, 2601)
            keys = [7 if trial == 0 else rng.randrange(32768) for _ in range(count)]
            for i, key in enumerate(keys):
                self.lib.add(offset + i, key, 0x8000 if i == 0 else 0, window)
            expected = [BASE + (offset + i) * 36
                        for i in sorted(range(count), key=lambda i: (-keys[i], i))]
            self.assertEqual(self.lib.find_window(), window)
            self.assertEqual(self.collect(window), expected)
            rng.shuffle(expected)
            self.assertEqual(self.rebuild(expected, window), 0)
            self.assertEqual(self.collect(window), expected)

    def test_duplicate_or_missing_commands_fail_without_mutation(self):
        for i in range(4):
            self.lib.add(i, 100 + i, i, 0)
        order = self.collect()
        for bad in (order[:-1], [order[0], order[0], *order[2:]],
                    [BASE + 100 * 36, *order[1:]]):
            self.lib.snapshot()
            self.assertNotEqual(self.rebuild(bad), 0)
            self.assertTrue(self.lib.unchanged())

    def test_other_window_and_radix_scratch_are_not_changed(self):
        self.lib.add(0, 100, 0x8000, 0)
        self.lib.add(1, 200, 1, 0)
        self.lib.add(2, 300, 0, 1)
        self.lib.set_head(256, 0x12345678)
        other_before = self.collect(1)
        order = self.collect(0)[::-1]
        self.assertEqual(self.rebuild(order), 0)
        self.assertEqual(self.collect(1), other_before)
        self.assertEqual(self.collect(0), order)
        self.assertEqual(self.lib.head_at(256), 0x12345678)

    def test_cycle_invalid_pointer_and_wrong_bucket_are_rejected(self):
        self.lib.add(0, 5, 0x8000, 0)
        self.lib.set_next(0, BASE)
        self.assertNotEqual(self.lib.collect(0), 0)
        self.lib.set_next(0, 0)
        self.lib.set_head(0, BASE + 1)
        self.assertNotEqual(self.lib.collect(0), 0)
        self.lib.set_head(0, BASE)
        self.lib.set_key(0, 256)
        self.assertNotEqual(self.lib.collect(0), 0)

    def test_old_frame_half_is_rejected(self):
        self.lib.add(0, 5, 0x8000, 0)
        self.lib.add(SLOTS, 6, 0, 0)
        self.assertNotEqual(self.lib.collect(0), 0)

    def test_actor_in_multiple_windows_is_rejected(self):
        self.lib.add(0, 5, 0x8000, 0)
        self.lib.add(1, 6, 0x8000, 1)
        self.assertLess(self.lib.find_window(), 0)

    def test_current_work_area_scratch_size(self):
        self.assertEqual(self.lib.seen_bytes(), 652)


if __name__ == '__main__':
    unittest.main()
