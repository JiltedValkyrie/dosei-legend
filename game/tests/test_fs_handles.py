"""SDK synchronous reads must coexist with a music handle held across frames."""
import ctypes
import os
from pathlib import Path
import re
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SDK = ROOT.parent.parent / 'joengine/jo_engine/fs.c'
GCC = Path('C:/msys64/mingw64/bin/gcc.exe')


@unittest.skipUnless(SDK.exists() and GCC.exists(), 'local SDK and host compiler required')
class FileHandles(unittest.TestCase):
    def test_music_handle_and_synchronous_asset_read(self):
        sdk = SDK.read_text()
        capacity = int(re.search(r'^JO_MAX_FS_BACKGROUND_JOBS\s*=\s*(\d+)',
                                (ROOT / 'makefile').read_text(), re.M)[1])
        macros = sdk[sdk.index('#if JO_MAX_FS_BACKGROUND_JOBS > 0'):
                     sdk.index('/** @brief Maximum sector')]
        reads = sdk[sdk.index('static int\t\t        jo_fs_get_file_size'):
                    sdk.index('char*\t\t\t\t\tjo_fs_read_file_in_dir')]
        harness = r'''
#include <stdlib.h>
#include <string.h>
#include <stdint.h>
#define JO_DEBUG 1
#define JO_NULL 0
#define JO_READ_RETRY_COUNT 10
#define JO_READ_SPIN_WAIT 16
#define JO_MALLOC_TRY_REUSE_BLOCK 0
#define JO_ZERO(x) ((x)=0)
typedef int Sint32;
typedef signed char Sint8;
typedef void *GfsHn;
static int opened=1, errors, limit;
static GfsHn GFS_Open(int id) {
 (void)id; if(opened==limit) return 0;
 ++opened; return (void *)(uintptr_t)opened;
}
static void GFS_Close(GfsHn h) { (void)h; --opened; }
static void GFS_GetFileSize(GfsHn h,int *s,int *n,int *last) {
 (void)h; *s=2048; *n=1; *last=4;
}
static int GFS_NameToId(Sint8 *name) { (void)name;return 7; }
static int GFS_Load(int id,int offset,void *buf,int bytes) {
 GfsHn h=GFS_Open(id); (void)offset;
 if(!h) return -1;
 memcpy(buf,"DATA",bytes); GFS_Close(h); return bytes;
}
static void jo_core_error(const char *fmt,...) { (void)fmt; ++errors; }
static void *jo_malloc_with_behaviour(int n,int mode) { (void)mode; return malloc(n); }
static void jo_free(void *p) { free(p); }
static void jo_spin_wait(int n) { (void)n; }
''' + macros + reads + r'''
int run(int slots) {
 int length=0; char *data; opened=1; errors=0;
 limit=slots ? slots : JO_OPEN_MAX;
 data=jo_fs_read_file_ptr("NPC16.ANM",0,&length);
 if(!data) return errors ? 1 : 2;
 if(length!=4 || memcmp(data,"DATA",5) || opened!=1 || errors) return 3;
 free(data);return 0;
}
'''
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            dll = Path(tmp) / 'fs.dll'
            env = dict(os.environ, PATH=str(GCC.parent) + os.pathsep + os.environ.get('PATH', ''))
            subprocess.run([str(GCC), '-shared', '-O2',
                            '-DJO_MAX_FS_BACKGROUND_JOBS=%d' % capacity,
                            '-x', 'c', '-', '-o', str(dll)], input=harness,
                           text=True, check=True, env=env)
            lib = ctypes.CDLL(str(dll))
            self.assertEqual(lib.run(1), 1)  # reproduces screenshot path
            self.assertEqual(lib.run(0), 0)  # music handle stays open


if __name__ == '__main__':
    unittest.main()
