"""Host regressions for the Saturn backend; no emulator is launched."""
import os
from pathlib import Path
import shutil
import struct
import subprocess
import tempfile
import unittest
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from asset_names import room_asset, STORY_BANK_PANORAMA
GCC = shutil.which('gcc') or 'C:/msys64/mingw64/bin/gcc.exe'


def function(path, marker):
    source = path.read_text()
    start = source.index(marker)
    brace = source.index('{', start)
    depth = 1
    end = brace + 1
    while depth:
        depth += (source[end] == '{') - (source[end] == '}')
        end += 1
    return source[start:end]


class GraphicsBackend(unittest.TestCase):
    def run_c(self, source):
        # CRT abort raises an interactive Windows crash dialog. Report a normal
        # failing exit status instead; tests must never open desktop UI.
        source = source.replace('#include <assert.h>', '''#include <stdio.h>
#include <stdlib.h>
#define assert(c) do { if (!(c)) { fprintf(stderr,"check failed: %s\\n", #c); exit(1); } } while (0)
''')
        # Extracted game functions may call the 32-bit divide helpers (no
        # ___divdi3 on target); host builds get them static inline.
        if any(name in source for name in ('div64s_approx', 'muldiv_s32', 'muldiv64_s32', 'ratio64_q16')) \
                and 'div32.h' not in source:
            source = '#include "%s"\n' % (ROOT.parent / 'shared/lib/collision/div32.h').as_posix() + source
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)
            (p / 'test.c').write_text(source)
            env = dict(os.environ)
            env['PATH'] = str(Path(GCC).parent) + os.pathsep + env.get('PATH', '')
            exe = p / 'test.exe'
            subprocess.run([GCC, '-std=c99', '-O2', '-Wno-pointer-to-int-cast',
                            str(p / 'test.c'), '-o', str(exe)], check=True, env=env)
            subprocess.run([str(exe)], check=True, env=env)

    @unittest.skipUnless((ROOT / 'build/cd' / room_asset(STORY_BANK_PANORAMA,0,'MSH')).exists(), 'baked house required')
    def test_house_fade_preserves_dark_detail(self):
        mesh = (ROOT / 'build/cd' / room_asset(STORY_BANK_PANORAMA,0,'MSH')).read_bytes()
        pixels = (ROOT / 'build/cd' / room_asset(STORY_BANK_PANORAMA,0,'TEX')).read_bytes()
        header = struct.unpack_from('>8I', mesh)
        tiles = 32 + header[1] * 12 + header[2] * 32
        old_black = blended_black = total = 0
        for i in range(header[3]):
            _, _, offset, size = struct.unpack_from('>HHII', mesh, tiles + i * 12)
            palette = struct.unpack_from('>16H', mesh, tiles + header[3] * 12 + i * 32)
            for byte in pixels[offset:offset + size]:
                for index in (byte >> 4, byte & 15):
                    brightest = max((palette[index] >> shift) & 31 for shift in (0, 5, 10))
                    old_black += brightest * 255 // 31 <= 100
                    # Conservative result even if output were reduced back to 5 bits.
                    blended_black += brightest * 19 // 32 == 0
                    total += 1
        self.assertGreater(old_black / total, .59)
        self.assertLess(blended_black / total, .02)

    def test_clut_hardware_fetch_and_following_texture(self):
        upload = function(ROOT / 'src/kokiri_sgl.c',
                          'unsigned int __attribute__((optimize("Os"))) kokiri_bank_tile_upload')
        self.run_c(r'''
#include <stdint.h>
#include <assert.h>
#include <string.h>
#define KOKIRI_STREAM_ROOMS 1
#define KOKIRI_TILE_NONE 0xffffu
#define JO_MAX_SPRITE 4
#define JO_MULT_BY_32(x) ((x)*32)
#define VRAM_UNITS(x) ((x)>>3)
#define COL_16 3
static unsigned char raw_vram[65536];
#define JO_VDP1_VRAM ((uintptr_t)raw_vram)
#define TEXTURE_CAPACITY 8192
typedef struct { unsigned short width,height,adr,size; } jo_texture_definition;
static jo_texture_definition __jo_sprite_def[4];
static struct { void *data; unsigned color_mode; } __jo_sprite_pic[4];
static unsigned texture_base, vram_used, sprite_next, kokiri_sprite_peak;
''' + upload + r'''
int main(void) {
    unsigned char pixels[4000], clut[32]; unsigned col, col2, used, start, i;
    memset(pixels,0x12,sizeof(pixels)); memset(clut,0x8f,sizeof(clut));
    /* Real shipped cow cel: 136x57 => 3876 bytes, not eight-byte aligned. */
    assert(kokiri_bank_tile_upload(pixels,clut,136,57,&col)==0);
    assert((col & 0xffffu)*8==3904);
    assert(!memcmp(raw_vram+3904,clut,32));
    assert(vram_used==3936 && !(vram_used&31));
    assert(kokiri_bank_tile_upload(pixels,clut,56,63,&col2)==1);
    assert(__jo_sprite_def[1].adr*8==3936);
    assert(!memcmp(raw_vram+(col2&0xffffu)*8,clut,32));
    used=vram_used;
    assert(kokiri_bank_tile_upload(pixels,clut,7,8,&col)==KOKIRI_TILE_NONE);
    assert(kokiri_bank_tile_upload(pixels,clut,512,8,&col)==KOKIRI_TILE_NONE);
    assert(kokiri_bank_tile_upload(pixels,clut,8,256,&col)==KOKIRI_TILE_NONE);
    assert(vram_used==used && sprite_next==2);
    /* RGB uploads can leave any eight-byte-aligned start. Read all colours
     * through hardware's 32-byte LUT boundary, not the requested CPU pointer. */
    for (i=0;i<32;++i) clut[i]=(unsigned char)(0x80+i);
    for (start=0;start<32;start+=8) {
        texture_base=256; vram_used=start; sprite_next=0;
        assert(kokiri_bank_tile_upload(pixels,clut,8,3,&col)==0);
        assert(!(col&3));
        for (i=0;i<32;++i) assert(raw_vram[((col&~3u)<<3)+i]==clut[i]);
        used=vram_used; sprite_next=0;
        vram_used=TEXTURE_CAPACITY-8;
        assert(kokiri_bank_tile_upload(pixels,clut,8,3,&col2)==KOKIRI_TILE_NONE);
        assert(vram_used==TEXTURE_CAPACITY-8 && sprite_next==0);
    }
    return 0;
}
''')

    def test_mesh_bank_clut_hardware_fetch(self):
        upload = function(ROOT / 'src/kokiri_sgl.c',
                          'static bool __attribute__((optimize("Os"))) mesh_load')
        self.run_c(r'''
#include <stdint.h>
#include <stdbool.h>
#include <assert.h>
#include <string.h>
#define JO_NULL 0
#define JO_MAX_SPRITE 8
#define JO_MULT_BY_32(x) ((x)*32)
#define VRAM_UNITS(x) ((x)>>3)
#define TEXTURE_CAPACITY 32768
#define GAME_TEXTURE_BYTES TEXTURE_CAPACITY
#define ECdis 0x80u
#define SPdis 0x40u
static unsigned char raw_vram[65536];
#define JO_VDP1_VRAM ((uintptr_t)raw_vram)
typedef struct { unsigned short width,height; unsigned offset,length; } kokiri_tile;
typedef struct { unsigned char flag,sort; unsigned short texno,atrb,colno,gstb,dir; } ATTR;
typedef struct { ATTR *attbl; } PDATA;
typedef struct { unsigned short width,height,adr,size; } jo_texture_definition;
static jo_texture_definition __jo_sprite_def[8];
static unsigned texture_base=256,vram_used,sprite_next,kokiri_sprite_peak;
static PDATA kokiri_pdata;
static unsigned char *forest_palette,*opening_pixel_pool;
static const void *mesh_staged_pixels;
static int opening_pixel_pool_bytes;
static unsigned disk_bytes, errors, reads;
static void jo_core_error(const char *s,...) { ++errors; }
static void asset_loading(const char *s) {}
static void asset_loading_done(void) {}
static void slDMAWait(void) {}
static void jo_dma_copy(void *s,void *d,unsigned n) { memcpy(d,s,n); }
static char *jo_fs_read_file_ptr(const char *s,void *d,int *n) {
    ++reads; memset(d,0x12,disk_bytes); ((char *)d)[disk_bytes]=0; *n=disk_bytes; return d;
}
''' + upload + r'''
int main(void) {
    unsigned start,i,j,cached;
    unsigned short palettes[2][16];
    kokiri_tile tiles[2]={{8,2,0,8},{8,2,8,8}};
    unsigned offsets[2]={0,8}; unsigned char pool[16];
    ATTR attrs[3];
    kokiri_pdata.attbl=attrs;
    for(i=0;i<2;++i) for(j=0;j<16;++j) palettes[i][j]=0x8000+i*32+j;
    memset(pool,0x12,sizeof(pool)); opening_pixel_pool=pool; opening_pixel_pool_bytes=16;
    for(cached=0;cached<3;++cached) for(start=0;start<32;start+=8) {
        /* Actual resident Link payload (8912) has remainder 16, which broke
         * every Link palette and propagated into the house panorama bank. */
        disk_bytes=cached?16:8912; vram_used=start; sprite_next=1;
        mesh_staged_pixels=cached==2 ? pool : 0; reads=0;
        memset(attrs,0,sizeof(attrs)); attrs[0].dir=attrs[1].dir=2;
        attrs[1].texno=1; attrs[2].dir=4; attrs[2].colno=0xabcd;
        assert(mesh_load("TEST.TEX",disk_bytes,tiles,2,palettes,&kokiri_pdata,3,
                         cached==1?offsets:0));
        assert(reads==(cached==0));
        for(i=0;i<16;++i)assert(raw_vram[texture_base+start+i]==pool[i]);
        for(i=0;i<2;++i) {
            unsigned lut=(attrs[i].colno&~3u)<<3;
            assert(!(attrs[i].colno&3));
            for(j=0;j<16;++j) {
                unsigned short got; memcpy(&got,raw_vram+lut+j*2,2);
                assert(got==palettes[i][j]);
            }
            assert(__jo_sprite_def[i+1].adr*8==texture_base+start+tiles[i].offset);
        }
        assert(attrs[2].colno==0xabcd);
        assert(attrs[2].atrb==(ECdis|SPdis));
        assert(!(vram_used&31) && !errors);
        assert(forest_palette==raw_vram+(attrs[0].colno<<3));
    }
    vram_used=TEXTURE_CAPACITY-16; sprite_next=1;
    assert(!mesh_load("TEST.TEX",16,tiles,2,palettes,&kokiri_pdata,3,0));
    assert(vram_used==TEXTURE_CAPACITY-16 && sprite_next==1 && errors==1);
    return 0;
}
''')

    def test_black_fade_uses_blending_and_resets(self):
        fade = function(ROOT / 'src/main.c',
                        'static void __attribute__((optimize("Os"))) cutscene_fade(void)')
        self.run_c(r'''
#include <stdint.h>
#include <stdbool.h>
#include <assert.h>
typedef short Sint16;
#define NBG1ON 2
#define RBG0ON 16
#define SPRON 64
#define BACKON 32
#define CC_RATE 0
#define CC_TOP 0
#define CC_pr_CN 0
#define CUTSCENE_FADE_BLACK 0
static unsigned short cram[2048];
#define JO_VDP2_CRAM ((uintptr_t)cram)
static unsigned alpha, colour, hidden, flash, line, calc, rate;
static int offset;
static bool cutscene_hides_scene(void){return hidden;}
static unsigned cutscene_fade_alpha(void){return alpha;}
static unsigned cutscene_fade_colour(void){return colour;}
static int cutscene_lightning(void){return flash;}
static bool cutscene_is_playing(void){return true;}
static unsigned player_items_flash(void){return 0;}
static void slLine1ColSet(void *p,unsigned c){assert((uintptr_t)p==0x7f400 && c==2047);}
static void slLineColDisp(unsigned flags){line=flags;}
static void slColRateNbg1(unsigned r){assert(r<32);}
static void slColRateRbg0(unsigned r){assert(r<32);}
static void slColRateSpr0(unsigned r){rate=r;}
static void slSpriteCCalcCond(unsigned c){assert(c==0);}
static void slSpriteCCalcNum(unsigned n){assert(n==7);}
static void slColorCalc(unsigned flags){calc=flags;}
static void slColOffsetOff(unsigned flags){offset=0;}
static void slColOffsetOn(unsigned flags){}
static void slColOffsetBUse(unsigned flags){}
static void slColOffsetB(int r,int g,int b){assert(r==g && g==b);offset=r;}
''' + fade + r'''
int main(void) {
    alpha=100; cutscene_fade();
    assert(calc==(NBG1ON|RBG0ON|SPRON) && line==calc && rate==12);
    assert(offset==0 && cram[2047]==0);
    /* VDP2 weight (31-rate)/32 preserves a dark component instead of clipping. */
    assert(64*(31-rate)/32>0);
    alpha=0; cutscene_fade(); assert(!calc && !line && !offset);
    alpha=255; hidden=1; cutscene_fade(); assert(!calc && !line);
    alpha=100; hidden=0; flash=40; cutscene_fade(); assert(calc && offset==40);
    alpha=0; flash=0; cutscene_fade(); assert(!calc && !line && !offset);
    return 0;
}
''')


if __name__ == '__main__':
    unittest.main()
