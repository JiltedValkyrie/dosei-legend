"""Immutable CPU atlas load and bitmap parity with no VDP2 readback."""
import unittest
from test_graphics_backend import ROOT, function
import test_graphics_backend as graphics


class HealthAtlas(unittest.TestCase):
    run_c = graphics.GraphicsBackend.run_c

    def test_file_cache_exact_pixels_and_no_vram_access_after_init(self):
        path = ROOT/'src/health_hud.c'
        source = r'''
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <string.h>
#define HEARTS_FILE_BYTES 823
static unsigned short cram[1024],vram_atlas[320],source_guard[322],original_atlas[320];
static unsigned char file_bytes[HEARTS_FILE_BYTES];
static bool ready,atlas_allowed;
static unsigned atlas_accesses,reads,closes,fail_at,file_size=HEARTS_FILE_BYTES;
static unsigned char meter_end[128],meter_mid[16],meter_fill[7];
static int last_key;
typedef struct {unsigned size,at;} jo_file;
static bool jo_fs_open(jo_file *f,const char *name) {
    assert(!strcmp(name,"HEARTS.BIN"));*f=(jo_file){file_size,0};reads=0;return true;
}
static int jo_fs_read_next_bytes(jo_file *f,char *out,unsigned n) {
    if(++reads==fail_at)return 0;
    assert(f->at+n<=sizeof(file_bytes));memcpy(out,file_bytes+f->at,n);f->at+=n;return n;
}
static void jo_fs_close(jo_file *f) {++closes;}
static unsigned short *atlas_access(void) {
    ++atlas_accesses;assert(atlas_allowed);return vram_atlas;
}
#define JO_VDP2_CRAM cram
#define HEART_ATLAS (atlas_access())
#define HEART_SOURCE (source_guard+1)
'''
        source += (ROOT/'src/health_hud_state.h').read_text()
        for marker in ('void health_hud_reset(', 'bool __attribute__((optimize("Os"))) health_hud_init(',
                       'static void heart_draw('):
            source += function(path, marker)
        source += r'''
/* Full old raster operation, independently reading the original file image.
 * No cache pointer or VRAM accessor is used by the reference. */
static void reference(unsigned short *out,unsigned health,unsigned heart,unsigned size,const unsigned char *samples) {
    unsigned filled=health>heart*16?health-heart*16:0;
    unsigned fill=!filled?0:filled>=16?4:filled<=5?1:filled<=10?2:3;
    unsigned left=14+(heart%10)*10-size/2,top=10+(heart/10)*10-size/2;
    for(unsigned y=0;y<size;++y)for(unsigned x=0;x<size;++x) {
        unsigned sx=samples[x],sy=samples[y],px=left+x,py=top+y;
        unsigned ink=(original_atlas[fill*64+sy*4+sx/4]>>(12-(sx&3)*4))&15;
        if(ink) {
            unsigned word=((py>>3)*15+(px>>3))*16+(py&7)*2+((px&7)>>2);
            unsigned shift=12-(px&3)*4;
            out[word]=(out[word]&~(15u<<shift))|(ink<<shift);
        }
    }
}
int main(void) {
    static const unsigned char sample11[11]={0,1,2,4,5,7,8,10,11,13,14};
    unsigned short actual[960],expected[960];
    unsigned char samples[16];
    for(unsigned i=0;i<sizeof(file_bytes);++i)file_bytes[i]=(unsigned char)(i*13+71);
    for(unsigned i=0;i<320;++i) {
        original_atlas[i]=(unsigned short)((i*1709u)^(i>>2));
        memcpy(file_bytes+32+i*2,&original_atlas[i],2);
    }
    source_guard[0]=source_guard[321]=0xa5a5;atlas_allowed=true;
    assert(health_hud_init() && ready && last_key==-2 && closes==1);
    assert(atlas_accesses==320 && !memcmp(HEART_SOURCE,original_atlas,640));
    assert(!memcmp(vram_atlas,original_atlas,640) && !memcmp(cram+832,file_bytes,32));
    assert(!memcmp(meter_end,file_bytes+672,128) && !memcmp(meter_mid,file_bytes+800,16));
    assert(!memcmp(meter_fill,file_bytes+816,7));
    /* A read through the VDP2 accessor now fails; poisoned VRAM also makes
     * an accidental direct read render different pixels. CPU copy persists. */
    atlas_allowed=false;memset(vram_atlas,0,640);atlas_accesses=0;
    for(unsigned heart=0;heart<20;++heart)
    for(unsigned fill=0;fill<=16;++fill)
    for(unsigned size=11;size<=16;++size) {
        for(unsigned i=0;i<size;++i)samples[i]=i*16/size;
        const unsigned char *map=size==11?sample11:samples;
        memset(actual,0x5a,sizeof(actual));memcpy(expected,actual,sizeof(actual));
        heart_draw(actual,heart*16+fill,heart,size,map);
        reference(expected,heart*16+fill,heart,size,map);
        assert(!memcmp(actual,expected,sizeof(actual)));
    }
    assert(!atlas_accesses && source_guard[0]==0xa5a5 && source_guard[321]==0xa5a5);
    /* Every truncated chunk leaves the HUD unready; a later successful
     * reload completely replaces the cache before rendering resumes. */
    atlas_allowed=true;
    for(fail_at=1;fail_at<=24;++fail_at) {
        assert(!health_hud_init() && !ready && last_key==-2);
        assert(source_guard[0]==0xa5a5 && source_guard[321]==0xa5a5);
    }
    fail_at=0;file_size=HEARTS_FILE_BYTES-1;
    assert(!health_hud_init() && !ready);
    file_size=HEARTS_FILE_BYTES;
    memset(HEART_SOURCE,0x33,640);
    assert(health_hud_init() && !memcmp(HEART_SOURCE,original_atlas,640));
    return 0;
}
'''
        self.run_c(source)


if __name__ == '__main__':
    unittest.main()
