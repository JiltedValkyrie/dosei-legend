"""Real adult assets and transactional age swaps in the production loader."""
from pathlib import Path
import struct
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import build_sgl_scene as sgl
from vdp1_budget import tile_bytes
import test_graphics_backend as graphics


class AdultAssets(unittest.TestCase):
    @unittest.skipUnless((ROOT / 'build/cd/ADULTSKN.BIN').is_file(), 'adult assets required')
    def test_real_adult_skin_geometry_and_shared_budget(self):
        skin = (ROOT / 'build/cd/ADULTSKN.BIN').read_bytes()
        magic, size, verts, polys, tiles, pixels, digest, frames = struct.unpack_from('>8I', skin)
        self.assertEqual((magic, size), (0x4C415331, len(skin)))
        self.assertLess(size + 1, 0x2000)
        self.assertLess(verts * 12, 0x2000)
        self.assertEqual(len((ROOT / 'build/cd/ADLTMESH.BIN').read_bytes()), polys * 32)
        self.assertEqual(len((ROOT / 'build/cd/ADLTTEX.BIN').read_bytes()), tiles * 44)
        self.assertEqual(len((ROOT / 'build/cd/ADULT.TEX').read_bytes()), pixels)
        anim = (ROOT / 'build/cd/ADULTANM.BIN').read_bytes()
        self.assertEqual(struct.unpack_from('>4I', anim), (0x4C414E31, frames, 21, digest))
        self.assertEqual(len(anim), 16 + frames * 132)
        self.assertTrue(all(owner < 21 for owner in skin[244:244 + verts]))
        groups = [struct.unpack_from('>2H', skin, 40 + i * 4) for i in range(9)]
        self.assertEqual(sum(count for _, count in groups), polys)
        self.assertTrue(all(first + count <= polys for first, count in groups))
        # Repose actual adult source limbs/local vertices with the first source
        # animation frame. This catches a child skeleton or doubled root scale.
        import build_link_model as link
        limbs = []
        for i in range(21):
            child_index, sibling, x, y, z = struct.unpack_from('>BB3h', skin, 76 + i * 8)
            limbs.append(dict(child=child_index, sibling=sibling, pos=(x, y, z), near=1, far=1))
        placed = None
        if link.OOT_DEFAULT.is_dir():
            keep = link.read_object(link.OOT_DEFAULT, 'gameplay_keep')
            animation = link.read_object(link.OOT_DEFAULT, 'link_animetion')
            # The bind-pose address anchor is deliberately different from the
            # free-hands playback idle clip's first frame.
            _, root, rotations = link.read_animation(keep, animation, link.IDLE_ANIMATION, 0, 21)
            placed = {index: (matrix, origin) for index, matrix, origin, _ in
                      link.walk_skeleton(limbs, rotations, root)}
        shift = struct.unpack_from('>3h', skin, 32)
        local_offset = 244 + ((verts + 3) & ~3)
        # Adult is a separate source mesh, with a taller unscaled pelvis.
        child = ROOT / 'build/generated/LINK.BIN'
        adult = child.with_name('ADULT.BIN')
        banks = []
        heights = []
        for path in (child, adult):
            data, header, positions, faces = sgl.read_scene(path)
            textures = sgl.collect_tiles(data, header, faces)
            banks.append(dict(tiles=[(t['width'], t['height']) for t in textures.values()],
                              vertices=len(positions), polygons=len(faces)))
            heights.append(max(v[1] for v in positions) - min(v[1] for v in positions))
            if path == adult and placed:
                for i, position in enumerate(positions):
                    local = struct.unpack_from('>3h', skin, local_offset + i * 6)
                    matrix, origin = placed[skin[244 + i]]
                    posed = link.transform(matrix, origin, local)
                    for axis in range(3):
                        self.assertLessEqual(abs(posed[axis] * .01 + shift[axis] - position[axis]), 1.1)
        self.assertGreater(heights[1], heights[0] * 1.3)
        self.assertNotEqual(banks[0]['vertices'], banks[1]['vertices'])
        budget = sgl.link_actor_budget(child)
        for bank in banks:
            self.assertGreaterEqual(len(budget['tiles']), len(bank['tiles']))
            self.assertGreaterEqual(sum(tile_bytes(*t) for t in budget['tiles']),
                                    sum(tile_bytes(*t) for t in bank['tiles']))
            self.assertGreaterEqual(budget['polygons'], bank['polygons'])
            self.assertGreaterEqual(budget['vertices'], bank['vertices'])


class AgeLoadTransaction(unittest.TestCase):
    run_c = graphics.GraphicsBackend.run_c

    def test_real_animation_prepare_cancel_commit_preserves_live_age(self):
        source = ROOT / 'src/link_anim.c'
        def digest(byte):
            value = 0x811C9DC5
            for word in b'\0\0\0\1' + bytes([byte]) * 132:
                value = ((value ^ word) * 0x01000193) & 0xFFFFFFFF
            return value
        parts = ('static uint32_t read_be32(',
                 'static unsigned char *__attribute__((optimize("Os"))) read_frames(',
                 'static void publish_frames(', 'bool link_anim_load(',
                 'void link_anim_cancel_age(',
                 'bool __attribute__((optimize("Os"))) link_anim_prepare_age(',
                 'void link_anim_commit_age(', 'bool link_anim_set_age(')
        self.run_c(r'''
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#define LINK_FRAME_COUNT 1
#define LINK_LIMB_COUNT 21
#define LINK_CLIP_COUNT 1
#define LINK_VERTEX_COUNT 4
#define ADULT_LINK_VERTEX_COUNT 3
#define ADULT_LINK_POLYGON_COUNT 3
#define ADULT_LINK_TILE_COUNT 3
#define ADULT_LINK_PIXEL_BYTES 24
#define ADULT_LINK_VISIBLE_POLYGONS 3
#define ADULT_LINK_SKIN_BYTES 272
#define RAM_LOW_LINK_SKIN_BYTES 8192
#define RAM_LOW_LINK_SKIN_OFFSET 0
''' + '#define LINK_FRAMES_DIGEST %du\n#define ADULT_LINK_FRAMES_DIGEST %du\n' % (digest(1), digest(2)) + r'''
typedef struct { uint8_t child,sibling;int16_t pos[3]; } link_limb_t;
typedef struct {
 uint32_t magic,bytes,vertices,polygons,tiles,pixels,digest,frames;
 int16_t shift[3];uint16_t visible,gear[9][2];link_limb_t limbs[21];
} link_age_model_t;
static const struct {uint16_t first,count;} link_clips[1]={{0,1}};
static uint32_t skin_words[2048],disc_skin_words[2048];
#define RAM_LOW(offset) ((void *)skin_words)
static unsigned char child_file[148],adult_file[148];
static const int16_t (*link_root)[3];
static const int16_t (*link_rotations)[63];
static const link_age_model_t *link_age_model,*pending_model;
static unsigned char *pending_frames;
static unsigned allocations,frees,resets;
static int missing,short_skin,bad_owner,missing_frames,short_frames;
typedef struct {int size;} jo_file;
static bool link_anim_is_adult(void) {return link_age_model!=0;}
static void link_anim_reset(void) {++resets;}
static void jo_free(void *p) {assert(p);++frees;free(p);}
static bool jo_fs_open(jo_file *f,const char *name) {assert(!strcmp(name,"ADULTSKN.BIN"));f->size=272-short_skin;return !missing;}
static void jo_fs_close(jo_file *f) {(void)f;}
static void *jo_fs_read_file_ptr(const char *name,void *dest,int *length) {
    assert(!strcmp(name,"ADULTSKN.BIN"));*length=272;memcpy(dest,disc_skin_words,272);
    if(bad_owner)((unsigned char *)dest)[244]=21;
    return dest;
}
static unsigned char *jo_fs_read_file(const char *name,int *length) {
    unsigned char *data;bool adult=!strcmp(name,"ADULTANM.BIN");
    if(missing_frames)return 0;
    *length=148-short_frames;data=malloc(*length);++allocations;
    memcpy(data,adult ? adult_file : child_file,*length);return data;
}
''' + '\n'.join(graphics.function(source, part) for part in parts) + r'''
static void be32(unsigned char *p,uint32_t value) {
    p[0]=value>>24;p[1]=value>>16;p[2]=value>>8;p[3]=value;
}
static void frame_file(unsigned char *p,unsigned byte,unsigned digest) {
    memcpy(p,"LAN1",4);be32(p+4,1);be32(p+8,21);be32(p+12,digest);memset(p+16,byte,132);
}
int main(void) {
    const int16_t (*old)[3];unsigned before,i;
    link_age_model_t *skin=(link_age_model_t *)disc_skin_words;
    skin->magic=0x4c415331;skin->bytes=272;skin->vertices=3;skin->polygons=3;
    skin->tiles=3;skin->pixels=24;skin->digest=ADULT_LINK_FRAMES_DIGEST;skin->frames=1;skin->visible=3;
    for(i=0;i<21;++i) {skin->limbs[i].child=255;skin->limbs[i].sibling=i==20 ? 255 : i+1;}
    frame_file(child_file,1,LINK_FRAMES_DIGEST);frame_file(adult_file,2,ADULT_LINK_FRAMES_DIGEST);
    assert(link_anim_load() && !link_anim_is_adult());old=link_root;
    missing=1;assert(!link_anim_prepare_age(true));missing=0;
    short_skin=1;assert(!link_anim_prepare_age(true));short_skin=0;
    bad_owner=1;assert(!link_anim_prepare_age(true));bad_owner=0;
    skin->limbs[0].child=0;assert(!link_anim_prepare_age(true));skin->limbs[0].child=255;
    missing_frames=1;assert(!link_anim_prepare_age(true));missing_frames=0;
    short_frames=1;assert(!link_anim_prepare_age(true));short_frames=0;
    adult_file[90]^=1;assert(!link_anim_prepare_age(true));adult_file[90]^=1;
    assert(link_root==old && !link_anim_is_adult() && allocations==frees+1);
    assert(link_anim_prepare_age(true) && link_root==old && !link_anim_is_adult());
    link_anim_cancel_age();link_anim_cancel_age();assert(link_root==old && allocations==frees+1);
    assert(link_anim_prepare_age(true));link_anim_commit_age();
    assert(link_root!=old && link_anim_is_adult() && allocations==frees+1);
    before=allocations;assert(link_anim_set_age(true) && allocations==before);
    old=link_root;missing_frames=1;assert(!link_anim_set_age(false));missing_frames=0;
    assert(link_root==old && link_anim_is_adult());
    assert(link_anim_set_age(false) && !link_anim_is_adult() && allocations==frees+1);
    jo_free((unsigned char *)link_root-16);link_root=0;
    link_anim_cancel_age();assert(allocations==frees);
    return 0;
}
''')

    def test_partial_reads_bad_indices_failed_upload_and_repeated_age_switch(self):
        source = ROOT / 'src/kokiri_sgl.c'
        self.run_c(r'''
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
typedef struct { int32_t norm[3];uint16_t Vertices[4]; } POLYGON;
typedef struct { uint8_t flag,sort;uint16_t texno,atrb,colno,gstb,dir; } ATTR;
typedef struct { void *points;unsigned nbPoint;POLYGON *pltbl;unsigned nbPolygon;ATTR *attbl; } PDATA;
typedef struct { uint16_t width,height;uint32_t offset,length; } link_tile;
typedef link_tile kokiri_tile;
typedef struct { uint16_t width,height,adr,size; } texture;
#define LINK_VERTEX_COUNT 2
#define LINK_POLYGON_COUNT 2
#define LINK_TILE_COUNT 2
#define LINK_PIXEL_BYTES 16
#define ADULT_LINK_VERTEX_COUNT 3
#define ADULT_LINK_POLYGON_COUNT 3
#define ADULT_LINK_TILE_COUNT 3
#define ADULT_LINK_PIXEL_BYTES 24
#define LINK_MESH_FILE "LINKMESH.BIN"
#define LINK_TEX_FILE "LINKTEX.BIN"
#define LINK_PIXEL_FILE "LINK.TEX"
#define RAM_CART_LINKMESH_BYTES 1024
#define RAM_CART_LINKTEX_BYTES 1024
#define RAM_CART_LINKMESH_OFFSET 0
#define RAM_CART_LINKTEX_OFFSET 1
#define TEXTURE_CAPACITY 4096
#define JO_MAX_SPRITE 64
static unsigned char vram[4096],cart_mesh[1024],cart_tex[1024];
#define JO_VDP1_VRAM ((uintptr_t)vram)
static texture __jo_sprite_def[64];
static unsigned texture_base,vram_used=3000,sprite_next=20;
static unsigned link_vram_start=64,link_sprite_start=2;
static bool link_model_ready=true,adult_live,adult_pending;
static unsigned reads,allocations,frees,prepares,commits,cancels;
static unsigned fail_read,short_read,bad_vertex,bad_tile,fail_alloc,fail_prepare,fail_upload;
static bool wait_ok=true;
static bool vdp1_wait_for_draw_end(void) {return wait_ok;}
static const void *mesh_staged_pixels;
static PDATA link_pdata={0,2,(POLYGON *)cart_mesh,2,(ATTR *)(cart_mesh+40)};
static void *ram_cart_fixed(unsigned offset,unsigned bytes) { (void)bytes;return offset ? cart_tex : cart_mesh; }
static void *jo_malloc(unsigned bytes) { if(fail_alloc)return 0;++allocations;return malloc(bytes); }
static void jo_free(void *p) { assert(p);++frees;free(p); }
static void *jo_fs_read_file(const char *file,int *length) {
    bool adult=file[0]=='A';unsigned n=adult ? 3 : 2,i;
    unsigned bytes=strstr(file,"MESH") ? n*32 : strstr(file,"TEX.BIN") ? n*44 : n*8;
    unsigned char *data;
    ++reads;if(fail_read==reads)return 0;
    data=jo_malloc(bytes);if(!data)return 0;
    memset(data,0,bytes);
    if(strstr(file,"MESH")) {
        POLYGON *poly=(POLYGON *)data;ATTR *attr=(ATTR *)(data+n*20);
        for(i=0;i<n;++i) {poly[i].Vertices[0]=bad_vertex ? 999 : i;attr[i].texno=i;}
    } else if(strstr(file,"TEX.BIN")) {
        link_tile *tile=(link_tile *)data;
        for(i=0;i<n;++i) {tile[i].width=8;tile[i].height=1;tile[i].offset=i*8;tile[i].length=bad_tile ? 999 : 4;}
    } else memset(data,adult ? 0xa7 : 0xc7,bytes);
    *length=bytes-(short_read==reads ? 1 : 0);return data;
}
static bool link_anim_is_adult(void) {return adult_live;}
static bool link_anim_prepare_age(bool adult) {++prepares;adult_pending=adult;return !fail_prepare;}
static void link_anim_commit_age(void) {++commits;adult_live=adult_pending;}
static void link_anim_cancel_age(void) {++cancels;adult_pending=adult_live;}
static void slDMAWait(void) {}
static void jo_dma_copy(void *a,void *b,unsigned bytes) {memcpy(b,a,bytes);}
static void invalidate_equipped(void) {}
static bool mesh_load(const char *name,unsigned pixels,const kokiri_tile *tiles,unsigned count,
    const unsigned short (*cluts)[16],PDATA *pdata,unsigned polygons,const void *cached) {
    unsigned i;(void)name;(void)tiles;(void)cluts;(void)cached;
    assert(mesh_staged_pixels && pdata!=&link_pdata && polygons==count);
    memcpy(vram+vram_used,mesh_staged_pixels,pixels);
    memset(vram+vram_used+pixels,0x88,32*count);
    for(i=0;i<count;++i) {__jo_sprite_def[sprite_next+i].width=8;pdata->attbl[i].texno+=sprite_next;}
    vram_used+=128;sprite_next+=count;
    return !fail_upload;
}
''' + graphics.function(source, 'static bool __attribute__((optimize("Os"))) link_model_load(') +
        graphics.function(source, 'bool __attribute__((optimize("Os"))) kokiri_link_set_age(') + r'''
static void rejected(void) {
    unsigned char before_vram[4096],before_mesh[1024],before_tex[1024];texture before_defs[64];
    unsigned old_commits=commits;
    memcpy(before_vram,vram,sizeof vram);memcpy(before_mesh,cart_mesh,sizeof cart_mesh);
    memcpy(before_tex,cart_tex,sizeof cart_tex);memcpy(before_defs,__jo_sprite_def,sizeof before_defs);
    reads=0;assert(!kokiri_link_set_age(true));
    assert(!adult_live && commits==old_commits && vram_used==3000 && sprite_next==20);
    assert(!memcmp(before_vram,vram,sizeof vram));assert(!memcmp(before_mesh,cart_mesh,sizeof cart_mesh));
    assert(!memcmp(before_tex,cart_tex,sizeof cart_tex));assert(!memcmp(before_defs,__jo_sprite_def,sizeof before_defs));
    assert(allocations==frees && !mesh_staged_pixels);
}
int main(void) {
    unsigned i,previous;
    memset(vram,0x11,sizeof vram);memset(cart_mesh,0x22,sizeof cart_mesh);memset(cart_tex,0x33,sizeof cart_tex);
    for(i=1;i<=3;++i) {fail_read=i;rejected();fail_read=0;short_read=i;rejected();short_read=0;}
    bad_vertex=1;rejected();bad_vertex=0;bad_tile=1;rejected();bad_tile=0;
    fail_alloc=1;rejected();fail_alloc=0;fail_prepare=1;rejected();fail_prepare=0;
    fail_upload=1;rejected();fail_upload=0;
    wait_ok=false;rejected();wait_ok=true;
    for(i=0;i<3;++i) {
        reads=0;assert(kokiri_link_set_age(true) && adult_live && link_pdata.nbPoint==3);
        previous=reads;assert(kokiri_link_set_age(true) && reads==previous);
        assert(vram[64]==0xa7 && vram[128+64]==0x11 && vram_used==3000 && sprite_next==20);
        assert(kokiri_link_set_age(false) && !adult_live && link_pdata.nbPoint==2);
        previous=reads;assert(kokiri_link_set_age(false) && reads==previous);
        assert(vram[64]==0xc7 && allocations==frees);
    }
    return 0;
}
''')


if __name__ == '__main__':
    unittest.main()
