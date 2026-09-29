"""A partial actor upload must never become a valid cached bank."""
import ctypes
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
GCC = Path('C:/msys64/mingw64/bin/gcc.exe')


@unittest.skipUnless(GCC.exists(), 'host compiler required')
class NpcBank(unittest.TestCase):
    def test_failed_props_upload_retries_even_when_npcs_all_fit(self):
        source = (ROOT / 'src/npc_draw.c').read_text()
        function = source[source.index('static bool upload_visible('):
                          source.index('/* View-space projection')]
        harness = r'''
#include <stdbool.h>
#include <stdint.h>
#define NPC_MODEL_COUNT 19
#define SHOP_ITEM_MESHES 7
#define SHOP_CURSOR_PULSES 4
#define RAM_CART_CURSOR_OFFSET 0
#define RAM_CART_CURSOR_BYTES 0
#define KOKIRI_TILE_NONE (~0u)
static unsigned uploaded=~0u, bank_generation, resets, failed=1;
static void *models[19], *counter, *shelves, *shop_items[7];
static bool shop_cursor_ready, shop_cursor_loaded;
static uint16_t shop_cursor_slot[4];
void kokiri_actor_tiles_reset(void) { ++resets; }
bool actor_mesh_upload(void *p) { (void)p; return true; }
void jo_core_error(const char *fmt, ...) { (void)fmt; }
void *ram_cart_fixed(unsigned a,unsigned b) { (void)a;(void)b;return 0; }
unsigned kokiri_bank_rgb_upload(const void *p,unsigned w,unsigned h) {
 (void)p;(void)w;(void)h;return 0;
}
bool world_props_draw_upload(void) { return !failed; }
bool interior_mask_upload(void) { return true; }
''' + function + r'''
int run(void) {
 if(upload_visible(2,1) || resets!=1) return 1;
 failed=0;
 if(!upload_visible(2,1) || resets!=2) return 2;
 if(!upload_visible(2,1) || resets!=2) return 3;
 if(!upload_visible(2,2) || resets!=3) return 4;
 return 0;
}
'''
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as directory:
            dll = Path(directory) / 'bank.dll'
            env = dict(os.environ, PATH=str(GCC.parent) + os.pathsep + os.environ.get('PATH', ''))
            subprocess.run([str(GCC), '-shared', '-O2', '-x', 'c', '-', '-o', str(dll)],
                           input=harness, text=True, check=True, env=env)
            self.assertEqual(ctypes.CDLL(str(dll)).run(), 0)


if __name__ == '__main__':
    unittest.main()
