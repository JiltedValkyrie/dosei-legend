"""Run the actual SDK allocator through the game profiler on bounded host zones."""
import ctypes as C
import os
import pathlib
import subprocess
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
SDK = ROOT.parent.parent / 'joengine/jo_engine'
GCC = pathlib.Path('C:/msys64/mingw64/bin/gcc.exe')

class Zone(C.Structure):
    _fields_ = [('base', C.c_size_t)] + [(n,C.c_uint32) for n in
        ('capacity','live','peak_live','extent','peak_extent')]
class Profile(C.Structure):
    _fields_ = [('zones',C.c_uint32),('failed',C.c_uint32),('zone',Zone*9)]

@unittest.skipUnless(GCC.is_file() and (SDK/'malloc.c').is_file(), 'SDK/compiler required')
class HeapProfile(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        root = pathlib.Path(self.tmp.name)
        (root/'jo').mkdir()
        common = '''#ifndef STUB_H
#define STUB_H
#include <string.h>
#include <stddef.h>
#define JO_DEBUG 1
#define JO_NULL NULL
#define JO_MOD_POW2(n,d) ((n)&((d)-1))
#define JO_ZERO(n) ((n)=0)
#define JO_PERCENT_USED(t,f) (((t)-(f))*100/(t))
#define jo_memset memset
#define __jo_force_inline inline
static inline void jo_core_error(const char *s, ...) { (void)s; }
#endif
'''
        (root/'stub.h').write_text(common)
        for name in ('sgl_prototypes','conf','types','sega_saturn','tools','math','smpc','core'):
            (root/'jo'/f'{name}.h').write_text('#include "../stub.h"\n')
        (root/'jo/malloc.h').write_bytes((SDK/'jo/malloc.h').read_bytes())
        (root/'malloc.c').write_bytes((SDK/'malloc.c').read_bytes())
        env = dict(os.environ)
        env['PATH'] = str(GCC.parent)+os.pathsep+env.get('PATH','')
        dll = root/'profile.dll'
        subprocess.run([str(GCC),'-shared','-O2','-std=gnu99','-I'+str(root),
            '-I'+str(SDK),str(ROOT/'src/heap_profile.c'),'-o',str(dll)],check=True,env=env)
        self.lib = C.CDLL(str(dll))
        self.lib.jo_add_memory_zone.argtypes = [C.c_void_p,C.c_uint]
        self.lib.jo_malloc_with_behaviour.argtypes = [C.c_uint,C.c_int]
        self.lib.jo_malloc_with_behaviour.restype = C.c_void_p
        self.lib.jo_free.argtypes = [C.c_void_p]
        self.profile = Profile.in_dll(self.lib,'dosei_heap_profile')
        self.buffers=[]
    def tearDown(self): self.tmp.cleanup()
    def zone(self,size):
        buf=C.create_string_buffer(size)
        self.buffers.append(buf)
        self.lib.jo_add_memory_zone(buf,size)
    def alloc(self,size,mode=0):
        return self.lib.jo_malloc_with_behaviour(size,mode)
    def test_headers_alignment_peaks_and_tail_free(self):
        self.zone(64)
        a=self.alloc(1);b=self.alloc(9)
        p=self.profile.zone[0]
        self.assertEqual((p.live,p.extent,p.peak_live),(32,32,32))
        self.lib.jo_free(b)
        self.assertEqual((p.live,p.extent,p.peak_extent),(12,12,32))
        self.lib.jo_free(a)
        self.assertEqual((p.live,p.extent,p.peak_live),(0,0,32))
    def test_hole_reuse_splits_block_and_compaction(self):
        self.zone(64)
        a=self.alloc(16);b=self.alloc(8)
        self.lib.jo_free(a)
        p=self.profile.zone[0]
        self.assertEqual((p.live,p.extent),(16,40))
        c=self.alloc(4,1)
        self.assertEqual(c,a)
        self.assertEqual(p.live,28)
        self.lib.jo_free(c);self.lib.jo_free(b)
        self.assertEqual(p.extent,24)
        self.lib.jo_reduce_memory_fragmentation()
        self.assertEqual((p.live,p.extent,p.peak_extent),(0,0,40))

    def test_small_probe_does_not_pin_animation_sized_hole(self):
        self.zone(1024)
        old=self.alloc(800); keep=self.alloc(128)
        self.lib.jo_free(old)
        probe=self.alloc(8,1)
        replacement=self.alloc(760,1)
        self.assertEqual(probe,old)
        self.assertTrue(replacement)
        self.assertEqual(self.profile.failed,0)

    def test_pressure_merges_adjacent_holes_before_failing(self):
        self.zone(160)
        a=self.alloc(40);b=self.alloc(40);keep=self.alloc(40)
        self.lib.jo_free(a);self.lib.jo_free(b)
        self.assertEqual(self.alloc(80,1),a)
        self.assertEqual(self.profile.failed,0)
    def test_spill_separates_cart_and_work_zone_and_counts_failure(self):
        self.zone(32);self.zone(64)
        self.alloc(24);self.alloc(40)
        self.assertEqual(self.profile.zone[0].peak_live,32)
        self.assertEqual(self.profile.zone[1].peak_live,48)
        self.assertFalse(self.alloc(64))
        self.assertEqual(self.profile.failed,1)
        self.assertEqual(self.profile.zone[0].capacity,32)

    def test_exact_size_spills_full_work_heap_and_exhausts_all_zones(self):
        self.zone(32);self.zone(40)
        self.assertTrue(self.alloc(24))
        self.assertTrue(self.alloc(12,2))
        self.assertTrue(self.alloc(12,2))
        self.assertFalse(self.alloc(12,2))
        self.assertEqual(self.profile.zone[1].live,40)
        self.assertEqual(self.profile.failed,1)

    def test_exact_size_reuses_matching_hole_only(self):
        self.zone(96)
        large=self.alloc(24);small=self.alloc(12);tail=self.alloc(12)
        self.lib.jo_free(large);self.lib.jo_free(small)
        self.assertEqual(self.alloc(12,2),small)
        self.assertNotEqual(self.alloc(12,2),large)
