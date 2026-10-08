"""SPR2 malformed-input and shared-cel command lifetime regressions."""
from pathlib import Path
import struct
import sys
import unittest

import test_graphics_backend as graphics

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from build_sprite_keys import groups, pack, resolve


def sheet():
    data = bytearray(76)
    struct.pack_into('>4s8H', data, 0, b'SPR1', 8, 1, 5, 1, 1, 0, 256, 1)
    return bytes(data)


class SpriteArchive(unittest.TestCase):
    run_c = graphics.GraphicsBackend.run_c

    def test_cow_identity_and_all_clip_keys_survive_relink(self):
        rows = [(395, 5, 'chew', 0, 'body'), (395, 5, 'move', 1, 'body'),
                (395, 5, 'swish', 2, 'tail')]
        symbols = '_body = 0x06000100; _tail = 0x06000200; ' \
                  '_chew = 0x06000300; _move = 0x06000400; _swish = 0x06000500;'
        result = groups(rows, symbols)
        self.assertEqual([len(v) for v in result.values()], [2, 1])
        self.assertIn('0x000200', resolve(rows, symbols))
        self.assertIn('0x000240', resolve(rows, symbols.replace('06000200', '06000240')))
        with self.assertRaises(ValueError):
            pack(0x100, [(1, sheet()), (1, sheet())])
        with self.assertRaises(ValueError):
            pack(0x100, [(1, b'SPR1'+bytes(72))])

    def test_archive_checks_offsets_lengths_duplicates_and_nested_packets(self):
        data = pack(0x100, [(0x200, sheet()), (0x300, sheet())])
        source = '#include <stdint.h>\n#include <string.h>\n#include <assert.h>\n'
        source += '#include "' + (ROOT / 'oot-core/include/oot_sprite_archive.h').as_posix() + '"\n'
        source += '#define U16(s,o) ((unsigned)((s)[o]<<8 | (s)[(o)+1]))\n'
        source += '#define U32(s,o) ((uint32_t)U16(s,o)<<16 | U16(s,(o)+2))\n'
        source += '#define CELS(s) (0x34u + ((U16(s,0x0c)*2u+3u)&~3u))\n'
        for marker in ('int npc_sprite_valid(', 'int npc_sprite_archive_valid(',
                       'const unsigned char *npc_sprite_archive_clip(',
                       'const unsigned char *npc_sprite_archive_largest('):
            source += graphics.function(ROOT / 'src/npc_sprite.c', marker) + '\n'
        source += 'static const unsigned char valid[]={' + ','.join(map(str, data)) + '};\n'
        source += r'''
int main(void) {
    unsigned char s[sizeof valid]; memcpy(s,valid,sizeof s);
    assert(npc_sprite_archive_valid(s,sizeof s,0x100));
    assert(npc_sprite_archive_clip(s,0x06000200)==s+40);
    assert(npc_sprite_archive_clip(s,0x06000300)==s+116);
    assert(!npc_sprite_archive_clip(s,0x400));
    assert(npc_sprite_archive_largest(s)==s+40);
    assert(!npc_sprite_archive_valid(s,sizeof s,0x200));
    for(unsigned n=0;n<sizeof s;++n) assert(!npc_sprite_archive_valid(s,n,0x100));
    s[5]=1; assert(!npc_sprite_archive_valid(s,sizeof s,0x100)); memcpy(s,valid,sizeof s);
    s[20]=0xff; assert(!npc_sprite_archive_valid(s,sizeof s,0x100)); memcpy(s,valid,sizeof s);
    s[24]=0xff; assert(!npc_sprite_archive_valid(s,sizeof s,0x100)); memcpy(s,valid,sizeof s);
    s[31]=0; s[30]=2; assert(!npc_sprite_archive_valid(s,sizeof s,0x100)); memcpy(s,valid,sizeof s);
    s[35]=40; assert(!npc_sprite_archive_valid(s,sizeof s,0x100)); memcpy(s,valid,sizeof s);
    s[40]='X'; assert(!npc_sprite_archive_valid(s,sizeof s,0x100));
    return 0;
}
'''
        self.run_c(source)

    def test_shared_cels_stable_across_order_and_pinned_until_frame_end(self):
        self.run_c('#include <stdint.h>\n#include <assert.h>\n#include "' +
                   (ROOT / 'src/npc_sprite.h').as_posix() + '"\n' +
                   graphics.function(ROOT / 'src/npc_sprite.c', 'npc_sprite_inst_t *npc_sprite_cache_claim(') + r'''
int main(void) {
    unsigned char a[1],b[1]; unsigned pinned=0;
    npc_sprite_inst_t slots[2]={{a,10,20,3},{b,11,21,4}};
    assert(npc_sprite_cache_claim(slots,2,&pinned,b,4)==slots+1);
    assert(npc_sprite_cache_claim(slots,2,&pinned,b,4)==slots+1); /* instances share */
    assert(npc_sprite_cache_claim(slots,2,&pinned,a,3)==slots);
    assert(!npc_sprite_cache_claim(slots,2,&pinned,a,5)); /* cannot alter queued commands */
    assert(slots[0].shown==3 && slots[1].shown==4);
    pinned=0;
    assert(npc_sprite_cache_claim(slots,2,&pinned,a,3)==slots);
    assert(npc_sprite_cache_claim(slots,2,&pinned,b,4)==slots+1); /* order change keeps slots */
    pinned=0;
    assert(npc_sprite_cache_claim(slots,2,&pinned,a,5)==slots);
    slots[0].shown=5;
    assert(npc_sprite_cache_claim(slots,2,&pinned,a,5)==slots);
    return 0;
}
''')

    def test_empty_libraries_never_dispatch_to_unloaded_core(self):
        self.run_c(r'''
#include <stdint.h>
#include <assert.h>
#define DOSEI_OOT_CORE 1
typedef struct { const unsigned char* (*sprite_clip)(const unsigned char*,unsigned); } OotCoreEntry;
static unsigned calls,last_animation;
static const unsigned char* clip(const unsigned char *s,unsigned animation) {
    assert(s); ++calls; last_animation=animation; return s;
}
static OotCoreEntry api={clip};
#define OOT_CORE_LOAD_ADDR ((uintptr_t)&api)
''' + graphics.function(ROOT/'src/npc_sprite.c', 'const unsigned char *npc_sprite_archive_clip(') + '\n' +
                   graphics.function(ROOT/'src/npc_sprite.c', 'const unsigned char *npc_sprite_archive_largest(') + r'''
int main(void) {
    unsigned char archive[1];
    assert(!npc_sprite_archive_clip(0,123) && !npc_sprite_archive_largest(0) && !calls);
    assert(npc_sprite_archive_clip(archive,123)==archive && calls==1 && last_animation==123);
    assert(npc_sprite_archive_largest(archive)==archive && calls==2 && last_animation==~0u);
    return 0;
}
''')

    def test_direction_sample_shares_mirrored_pixels_and_computes_facing_once(self):
        self.run_c(r'''
#include <stdint.h>
#include <assert.h>
#define U16(s,o) ((unsigned)((s)[o]<<8 | (s)[(o)+1]))
static struct { int x,z; } recomp_camera;
static unsigned char npc_sprite_shadow_off;
static int last_depth=100, facing_calls;
static unsigned gameplay_facing(int x,int z) { ++facing_calls; return 0; }
''' + graphics.function(ROOT / 'src/npc_sprite.c', 'unsigned int npc_sprite_cel(') + r'''
int main(void) {
    unsigned char sheet[60]={0}; unsigned dirs[]={0,1,2,3,4,3,2,1};
    sheet[9]=5; sheet[13]=2; sheet[55]=1; /* two ticks select poses0,1 */
    for(unsigned i=0;i<8;++i) {
        unsigned sample=npc_sprite_cel(sheet,1,0,0,(uint16_t)(i*8192));
        assert((sample&0xffffu)==5+dirs[i]);
        assert(!!(sample&0x10000u)==(i>4));
    }
    assert(facing_calls==8);
    last_depth=800; assert(npc_sprite_cel(sheet,1,0,0,0)==0);
    npc_sprite_shadow_off=1; assert(npc_sprite_cel(sheet,1,0,0,0)==5);
    return 0;
}
''')


if __name__ == '__main__':
    unittest.main()
