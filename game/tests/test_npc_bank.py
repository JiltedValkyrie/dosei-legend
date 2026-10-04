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
#define NPC_SPRITE_SLOT_NONE UINT16_MAX
#define KOKIRI_NPC_COUNT 2
#define NAVI_NPC_COUNT 2
#define NPC_SHOPKEEPER 15
static unsigned uploaded=~0u, bank_generation, resets, failed=1;
static void *counter, *shelves, *shop_items[7];
static bool navi_cast=true;
static const struct { unsigned model; } navi_npcs[2]={{2},{1}};
static const struct { unsigned scene; } kokiri_npcs[2]={{99},{99}};
static struct { unsigned scene_id; } save_state={7};
static unsigned char sheets[2], *spr[19]={[1]=sheets,[2]=sheets+1};
static struct { uint16_t slot; } spr_inst[3];
static unsigned sprite_uploads, sprite_fail;
static unsigned model_for(unsigned i) { return i; }
static int npc_sprite_upload(unsigned char *s, void *instance) {
 unsigned i=(unsigned)(((char*)instance-(char*)spr_inst)/sizeof(spr_inst[0]));
 if (s!=spr[navi_npcs[i].model]) return false;
 ++sprite_uploads; spr_inst[i].slot=i;
 return !sprite_fail;
}
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
 if(upload_visible(6,1) || resets!=1 || sprite_uploads!=2) return 1;
 failed=0;
 if(!upload_visible(6,1) || resets!=2 || sprite_uploads!=4) return 2;
 if(!upload_visible(6,1) || resets!=2 || sprite_uploads!=4) return 3;
 for(unsigned mask=0;mask<100;++mask)
   if(!upload_visible(mask,1) || resets!=2 || sprite_uploads!=4) return 8;
 if(!upload_visible(6,2) || resets!=3) return 4;
 if(spr_inst[2].slot!=NPC_SPRITE_SLOT_NONE) return 5;
 sprite_fail=1;
 if(upload_visible(6,3)) return 6;
 sprite_fail=0;
 if(!upload_visible(6,3) || resets!=5) return 7;
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
