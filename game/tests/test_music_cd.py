"""Exercise real music stream code against a single-owner mock CD server."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
GCC = shutil.which('gcc') or 'C:/msys64/mingw64/bin/gcc.exe'


class MusicCD(unittest.TestCase):
    def test_yield_resume_and_failures(self):
        music = (ROOT / 'shared/lib/music/music.c').read_text()
        streams = music[music.index('typedef struct {'):music.index('static bool swap_failed;')]
        fs = (ROOT / 'game/src/fs_low.c').read_text()
        hooks = fs[fs.index('#define GFS_Open'):fs.index('#include "fs.c"')]
        source = r'''
#include <stdio.h>
#include <stdlib.h>
#define assert(c) do { if (!(c)) { fprintf(stderr,"check failed: %s\n", #c); exit(1); } } while (0)
#include <stdbool.h>
#include <string.h>
typedef int Sint32;
typedef char Sint8;
typedef struct { int pos, active; } File;
typedef File *GfsHn;
#define GFS_TMODE_CPU 0
#define GFS_SEEK_SET 0
#define STREAM_STALL 20
#define LOAD_CHUNK 8192
static File file;
static int stops, seeks, stop_error, start_error;
static Sint32 GFS_NameToId(Sint8 *name) { return 1; }
static GfsHn GFS_Open(int id) { file.pos=0; return &file; }
static void GFS_Close(GfsHn h) { assert(!h->active); }
static void GFS_GetFileSize(GfsHn h,int *s,int *n,int *last)
{ *s=2048; *n=5; *last=17; }
static void GFS_SetTmode(GfsHn h,int mode) {}
static int GFS_NwCdRead(GfsHn h,int count)
{ assert(!h->active); if(start_error)return -1; h->active=1; return 0; }
Sint32 GFS_NwStop(GfsHn h)
{ if(stop_error)return -1; ++stops; h->active=0; return h->pos; }
static int GFS_Seek(GfsHn h,int pos,int origin)
{ assert(!h->active); ++seeks; h->pos=pos; return pos; }
static int GFS_NwExecOne(GfsHn h) { return 0; }
Sint32 GFS_GetNumCdbuf(GfsHn h) { return 4; }
static int GFS_Fread(GfsHn h,int n,void *buf,int size)
{ memset(buf,h->pos,size); h->pos+=n; return size; }
static int GFS_Load(int id,int off,void *buf,int size)
{ return file.active ? -1 : size; }
'''
        source += streams + '\n' + hooks + r'''
int main(void) {
    unsigned char buf[8192];
    assert(stream_open(&level_stream,"MUSIC",8209));
    assert(stream_read(&level_stream,buf,4096)==4096);
    assert(level_stream.offset==4096);
    /* Real fs_low whole-file hook must release music before asset loading. */
    assert(GFS_Load(2,0,buf,32)==32);
    assert(stops==1 && level_stream.suspended);
    assert(GFS_Load(3,0,buf,32)==32 && stops==1);
    assert(stream_read(&level_stream,buf,4096)==4096);
    assert(seeks==1 && buf[0]==2 && level_stream.offset==8192);
    stop_error=1;
    assert(GFS_Load(4,0,buf,32)==-1);
    assert(!level_stream.suspended && file.active);
    stop_error=0;
    assert(GFS_Load(4,0,buf,32)==32);
    assert(stream_read(&level_stream,buf,8192)==17);
    assert(buf[0]==4 && level_stream.offset==8209);
    stream_close(&level_stream);
    assert(!level_stream.gfs && !file.active);
    start_error=1;
    assert(!stream_open(&swap_stream,"MUSIC",8209));
    assert(!swap_stream.gfs);
    return 0;
}
'''
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)
            (path / 'test.c').write_text(source)
            env = dict(os.environ)
            env['PATH'] = str(Path(GCC).parent) + os.pathsep + env.get('PATH', '')
            exe = path / 'test.exe'
            subprocess.run([GCC, '-std=c99', '-O2', str(path / 'test.c'), '-o', str(exe)],
                           check=True, env=env)
            subprocess.run([str(exe)], check=True, env=env)


if __name__ == '__main__':
    unittest.main()
