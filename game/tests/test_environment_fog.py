"""Execute the renderer's fog and landmark branches with small host fixtures."""
import ctypes
import os
import pathlib
import re
import shutil
import subprocess
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
GCC = shutil.which('gcc') or ('C:/msys64/mingw64/bin/gcc.exe'
    if pathlib.Path('C:/msys64/mingw64/bin/gcc.exe').exists() else None)


def balanced(text, at, opening='{', closing='}'):
    start = text.index(opening, at)
    depth = 1
    end = start + 1
    while depth:
        depth += (text[end] == opening) - (text[end] == closing)
        end += 1
    return text[start:end]


def source_fixture():
    text = (ROOT / 'src/kokiri_sgl.c').read_text()
    macros = '\n'.join(re.findall(
        r'^#define (?:FIELD_FAR |FIELD_LANDMARK_FAR |FOREST_FACE_LANDMARK |FOREST_FAR \(|FOREST_FOG_END |FOREST_FOG_START |FOREST_MESH_START ).*',
        text, re.M))
    init_at = text.index('static void __attribute__((optimize("Os"))) forest_fog_init')
    init = text[init_at:text.index('{', init_at)] + balanced(text, init_at)
    tails = []
    for name in ('field_stream_load', 'room_load_bank'):
        definition = re.search(r'\b' + name + r'\([^;]*?\)\s*\{', text)
        body = balanced(text, definition.start())
        tails.append(re.search(r'forest_scene = \(unsigned short\)scene;.*?(?=actor_vram_base =)',
                               body, re.S).group(0))
    draw = balanced(text, text.index('kokiri_scene_draw(void)'))
    fog_at = draw.index('frame_timer_begin(FRAME_PHASE_FOG)')
    loop_at = draw.index('for (i = 0; i < forest_tile_count;', fog_at)
    loop = draw[loop_at:draw.index('{', loop_at)] + balanced(draw, loop_at)
    depth_at = draw.index('if (tile < forest_tile_count && (attr->dir & 7) != 4)')
    depth = draw[depth_at:draw.index('{', depth_at)] + balanced(draw, depth_at)
    mesh = re.search(r'attr->atrb &= ~MESHon;.*?attr->atrb \|= MESHon;', draw, re.S).group(0)
    predicates = [balanced(draw, draw.index(prefix), '(', ')') for prefix in
                  ('if (farthest < 0 || nearest >', 'while (farthest < 0 || nearest >')]
    return r'''
#include <stdint.h>
#define X __declspec(dllexport)
#define C_RGB(r,g,b) (0x8000u | (r) | ((g)<<5) | ((b)<<10))
#define SCENE_SPOT00 10
#define STORY_BANK_BASE 512
#define STORY_BANK_NAVI 513
#define STORY_BANK_FIELD 514
#define KOKIRI_FIELD_SCENE STORY_BANK_FIELD
#define ASSET_ID_LIMIT 1024
#define FOREST_FAR_DEFAULT 1310
#define MESHon 0x100u
#define KOKIRI_STREAM_ROOMS 1
static int forest_far_current;
static unsigned short forest_scene, forest_ground_colour;
static unsigned char fog_channel[2][17][32];
static unsigned char forest_mesh[1], object_visible[1], kokiri_objects[1];
static short tile_depth[1];
static unsigned char tile_fog[1];
static unsigned short output[16], kokiri_cluts[1][16];
static unsigned char *forest_palette=(unsigned char *)output;
static unsigned forest_tile_count=1;
static struct { unsigned far; } fixture_head={9000}, *field_head=&fixture_head;
static unsigned short environment_sky_floor(unsigned scene) {
    return scene==SCENE_SPOT00 ? C_RGB(16,18,9) : scene==1 ? C_RGB(2,4,28) : C_RGB(28,3,2);
}
''' + macros + '\n' + init + r'''
X void load_field(unsigned scene) { ''' + tails[0] + r''' }
X void load_room(unsigned scene) { ''' + tails[1] + r''' }
X int threshold(int which) {
    return which==0 ? FOREST_FOG_START : which==1 ? FOREST_FOG_END : FOREST_MESH_START;
}
X unsigned colour(void) { return forest_ground_colour; }
typedef struct { unsigned atrb,dir; } fixture_attr;
X unsigned render(unsigned source, int nearest, unsigned flags) {
    unsigned i=0,j,tile=0;
    fixture_attr storage={0,2}, *attr=&storage;
    forest_mesh[0]=(unsigned char)flags;
    tile_depth[0]=32767; tile_fog[0]=255;
    for(j=0;j<16;++j)kokiri_cluts[0][j]=(unsigned short)source;
    ''' + depth + '\n' + mesh + '\n' + loop + r'''
    return output[0] | (attr->atrb << 16);
}
X int rejected(int tail,int nearest,int farthest,unsigned flags,int object) {
    unsigned i=0,visible=0;
    forest_mesh[0]=(unsigned char)flags;object_visible[0]=(unsigned char)object;
    if(tail)return ''' + predicates[1] + r''';
    return ''' + predicates[0] + r''';
}
'''


@unittest.skipUnless(GCC, 'host GCC required')
class EnvironmentFog(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        binary = pathlib.Path(cls.temp.name) / 'fog.dll'
        env = dict(os.environ)
        env['PATH'] = str(pathlib.Path(GCC).parent) + os.pathsep + env.get('PATH', '')
        subprocess.run([GCC, '-shared', '-O2', '-Wall', '-Werror', '-x', 'c', '-', '-o', str(binary)],
                       input=source_fixture(), text=True, check=True, env=env)
        cls.lib = ctypes.CDLL(str(binary))

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_both_bank_load_paths_refresh_map_colour(self):
        self.lib.load_room(1)
        self.assertEqual(self.lib.colour(), 0x8000 | 2 | (4 << 5) | (28 << 10))
        self.lib.load_field(10)
        self.assertEqual(self.lib.colour(), 0x8000 | 16 | (18 << 5) | (9 << 10))
        self.lib.load_room(2)
        self.assertEqual(self.lib.colour(), 0x8000 | 28 | (3 << 5) | (2 << 10))
        self.lib.load_room(514)
        self.assertEqual(self.lib.colour(), 0x8000 | 27 | (27 << 5) | (19 << 10))

    def test_field_thresholds_are_gameplay_scene_not_story_bank(self):
        self.lib.load_field(10)
        self.assertEqual([self.lib.threshold(i) for i in range(3)], [1800, 4500, 4000])
        self.lib.load_room(514)
        self.assertEqual([self.lib.threshold(i) for i in range(3)], [4500, 9000, 7875])

    def test_ground_blend_and_landmark_no_fog_keep_smoke_authorship(self):
        self.lib.load_field(10)
        source = 0xFFFF
        self.assertEqual(self.lib.render(source, 1800, 0), source)
        ground = self.lib.colour()
        self.assertEqual(self.lib.render(source, 4500, 0) & 0xFFFF, ground)
        self.assertTrue(self.lib.render(source, 4500, 0) & (0x100 << 16))
        self.assertEqual(self.lib.render(source, 20000, 8), source)
        self.assertEqual(self.lib.render(source, 20000, 9), source | (0x100 << 16))
        self.assertEqual(self.lib.render(0, 4500, 0) & 0xFFFF, 0)

    def test_front_and_tail_keep_far_landmark_but_reject_behind(self):
        self.lib.load_field(10)
        for tail in (0, 1):
            self.assertTrue(self.lib.rejected(tail, 12000, 13000, 0, 1))
            self.assertFalse(self.lib.rejected(tail, 12000, 13000, 8, 0))
            self.assertFalse(self.lib.rejected(tail, 26000, 26100, 8, 0))
            self.assertTrue(self.lib.rejected(tail, 26001, 26100, 8, 1))
            self.assertTrue(self.lib.rejected(tail, -100, -1, 8, 1))


if __name__ == '__main__':
    unittest.main()
