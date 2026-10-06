"""Exercise the real split Field loader with bounded allocations and failed reads."""
import ctypes as C
import os
from pathlib import Path
import struct
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
GCC = Path('C:/msys64/mingw64/bin/gcc.exe')

@unittest.skipUnless(GCC.exists(), 'host compiler required')
class FieldStorage(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        p = Path(cls.tmp.name)
        (p/'test.c').write_text(r'''
#include <stdbool.h>
#include <stdlib.h>
#include <string.h>
static unsigned char *data, *geo, *pix;
static unsigned int size, length, limit, live, calls, fail_alloc, fail_read, reads;
#define JO_MALLOC_TRY_REUSE_BLOCK 1
static void *jo_malloc_with_behaviour(unsigned int n, int mode) {
    ++calls;
    if (n>limit || calls==fail_alloc) return 0;
    void *p=malloc(n); if(p)++live; return p;
}
static void jo_free(void *p) { if(p){free(p);--live;} }
int fs_file_size(const char *name) { return size; }
bool fs_read_sectors(const char *name,unsigned int sector,void *dst,unsigned int n) {
    ++reads;
    if(reads==fail_read || sector*2048u>size || n>size-sector*2048u)return false;
    memcpy(dst,data+sector*2048u,n);return true;
}
#include "field_storage.h"
int run(unsigned char *d,unsigned int n,unsigned int cap,unsigned int fa,unsigned int fr) {
    data=d;size=n;limit=cap;calls=reads=0;fail_alloc=fa;fail_read=fr;
    return field_storage_load("TEST.STM",&geo,&pix,&length);
}
unsigned int active(void){return live;}
void *geometry(void){return geo;}
void *pixels(void){return pix;}
void release(void){jo_free(geo);jo_free(pix);geo=pix=0;}
''')
        env = dict(os.environ, PATH=str(GCC.parent)+os.pathsep+os.environ.get('PATH',''))
        subprocess.run([str(GCC),'-shared','-O2','-I'+str(ROOT/'src'),str(p/'test.c'),
                        '-o',str(p/'test.dll')],check=True,env=env)
        cls.lib=C.CDLL(str(p/'test.dll'))
        cls.lib.run.argtypes=[C.c_void_p,C.c_uint,C.c_uint,C.c_uint,C.c_uint]
        cls.lib.geometry.restype=cls.lib.pixels.restype=C.c_void_p

    @classmethod
    def tearDownClass(cls):cls.tmp.cleanup()
    def tearDown(self):self.lib.release()

    def fixture(self,offset=6000,pixels=10000):
        h=[0x4b524d32,1,1,1,pixels,1,1,offset+pixels,4,1,1,0,offset,1,9000,0]
        return bytearray(struct.pack('=16I',*h)+bytes((i%251 for i in range(offset+pixels-64))))

    def run_data(self,data,cap=12500,fa=0,fr=0):
        self.buf=C.create_string_buffer(bytes(data))
        return self.lib.run(self.buf,len(data),cap,fa,fr)

    def test_split_reconstructs_unaligned_and_aligned_pool(self):
        for offset in (6000,6144):
            data=self.fixture(offset)
            self.assertGreater(len(data),12500)
            self.assertTrue(self.run_data(data))
            self.assertEqual(C.string_at(self.lib.geometry(),offset),data[:offset])
            self.assertEqual(C.string_at(self.lib.pixels()+(offset%2048),10000),data[offset:])
            self.lib.release();self.assertEqual(self.lib.active(),0)

    def test_allocation_and_read_failures_release_storage(self):
        for fa,fr in ((1,0),(2,0),(0,1),(0,2),(0,3)):
            self.assertFalse(self.run_data(self.fixture(),fa=fa,fr=fr))
            self.assertEqual(self.lib.active(),0)
            self.assertFalse(self.lib.geometry());self.assertFalse(self.lib.pixels())

    def test_rejects_truncated_and_invalid_header_before_allocation(self):
        for word,value in ((0,0),(2,256),(3,65535),(4,9999),(7,0),(12,16),(12,0xffffffff)):
            data=self.fixture();struct.pack_into('=I',data,4*word,value)
            self.assertFalse(self.run_data(data));self.assertEqual(self.lib.active(),0)
        self.assertFalse(self.run_data(self.fixture()[:32]))

    def test_real_candidate_payloads_fit_separate_blocks(self):
        for cell in (184,256):
            path=ROOT/f'build/square-retopo/r2-{cell}/oot-sat/game/build/cd/SAR0.STM'
            if not path.exists():self.skipTest('candidate assets absent')
            data=bytearray(path.read_bytes());h=struct.unpack_from('>16I',data)
            data[:64]=struct.pack('=16I',*h)
            self.assertGreater(len(data),481280)
            self.assertTrue(self.run_data(data,cap=481280))
            self.assertEqual(C.string_at(self.lib.geometry(),h[12]),data[:h[12]])
            self.assertEqual(C.string_at(self.lib.pixels()+(h[12]%2048),h[4]),data[h[12]:])
            self.lib.release()

if __name__=='__main__':unittest.main()
