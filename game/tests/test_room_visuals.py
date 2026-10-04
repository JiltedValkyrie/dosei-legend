"""Source-backed material, generic house camera and cache regressions."""
import os
from pathlib import Path
import struct
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'tools'), str(ROOT.parent / 'shared/tools')]
import build_all_scenes as all_scenes
import build_hybrid_scene as hybrid
import build_kokiri_scene as source
from interior_panorama import PANORAMAS, panorama_room
import test_graphics_backend as graphics

OOT = Path(os.environ.get('DOSEI_OOT') or 'D:/Workspace-Claude/game-decomps/n64/oot')


def alpha_mux(first, second):
    a, b, c, d = first
    e, f, g, h = second
    return 0xFC000000 | a << 12 | c << 9, b << 12 | d << 9 | e << 21 | g << 18 | f << 3 | h


class MaterialAlpha(unittest.TestCase):
    def test_constant_alpha_does_not_turn_dark_intensity_into_holes(self):
        opaque = alpha_mux((7, 7, 7, 6), (7, 7, 7, 0))
        texture = alpha_mux((7, 7, 7, 1), (7, 7, 7, 0))
        self.assertTrue(source.combine_alpha_opaque(*opaque))
        self.assertFalse(source.combine_alpha_opaque(*texture))
        dl = source.DisplayLists(b'\x01\x23\x45\x67', b'')
        dl.texture_on = True
        dl.images[0] = (0x02000000, 8, 4, 0)
        dl.tiles[0] = dict(tmem=0, fmt=4, size=0, palette=0,
                           uls=0, ult=0, lrs=28, lrt=0)
        dl.alpha_opaque = source.combine_alpha_opaque(*opaque)
        solid = dl.texture()
        self.assertEqual([c[3] for c in solid['colors']], [255] * 8)
        self.assertEqual([c[0] for c in solid['colors']], list(range(0, 128, 17)))
        dl.alpha_opaque = source.combine_alpha_opaque(*texture)
        cutout = dl.texture()
        self.assertEqual(cutout['colors'][0][3], 0)
        self.assertIsNot(solid, cutout)  # material change must invalidate texture decode cache

    def test_dynamic_alpha_never_folds_to_opaque(self):
        for selector in (1, 2, 3, 4, 5):
            self.assertFalse(source.combine_alpha_opaque(*alpha_mux(
                (7, 7, 7, selector), (7, 7, 7, 0))))

    def test_generic_cache_requires_matching_source_decoder_and_files(self):
        with tempfile.TemporaryDirectory() as temp:
            out = Path(temp)
            fingerprint = all_scenes.scene_fingerprint('decoder-a', {'room': b'rom'})
            rows = [dict(prefix='tomb', room=0, status='baked', fingerprint=fingerprint)]
            self.assertFalse(all_scenes.cache_current(rows, fingerprint, out))
            folder = out / 'tomb_room_0'
            folder.mkdir()
            for file in ('room.msh', 'room.tex', 'texture_manifest.json'):
                (folder / file).write_bytes(b'old bake')
            self.assertTrue(all_scenes.cache_current(rows, fingerprint, out))
            self.assertFalse(all_scenes.cache_current(rows,
                all_scenes.scene_fingerprint('decoder-b', {'room': b'rom'}), out))
            self.assertFalse(all_scenes.cache_current(rows,
                all_scenes.scene_fingerprint('decoder-a', {'room': b'changed rom'}), out))
            self.assertFalse(all_scenes.cache_current([dict(rows[0], fingerprint=None)], fingerprint, out))


@unittest.skipUnless((OOT / 'assets/xml/objects/gameplay_field_keep.xml').is_file(), 'source assets required')
class SourceVisuals(unittest.TestCase):
    def test_handle_door_uses_textured_wood_not_coloured_normals(self):
        from build_shop_props import static_mesh
        import build_link_model as link
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'ENDOOR.BIN'
            static_mesh(OOT, None, 'gameplay_field_keep', 'gFieldDoorLeftDL', path, .01,
                        matrix=link.rotation_matrix((-0x4000, 0, 0)), setup25=True)
            data = path.read_bytes()
            _, _, _, faces, _, records, tex, _, _ = struct.unpack_from('>9I', data)
            self.assertGreater(faces, 2)
            for face in range(2):
                pixel, clut, size = struct.unpack_from('>IIH', data, records + face * 20 + 8)
                palette = struct.unpack_from('>16H', data, tex + clut)
                packed = data[tex + pixel:tex + pixel + (size >> 8) * 8 * (size & 255) // 2]
                colours = {palette[n] for byte in packed for n in (byte >> 4, byte & 15)}
                self.assertNotIn(0, colours)
                self.assertGreater(len(colours), 6)
                for colour in colours:
                    red, green, blue = colour & 31, (colour >> 5) & 31, (colour >> 10) & 31
                    self.assertGreaterEqual(red, green)
                    self.assertGreaterEqual(green, blue)

    def test_grave_floor_keeps_dark_texture_pixels_opaque(self):
        faces = hybrid.load_faces(OOT, prefix='hakaana2')
        floor = [f for f in faces if f['texture'] and f['texture']['address'] == 0x02004890]
        self.assertGreater(len(floor), 20)
        for face in floor:
            self.assertTrue(any(c[0] < 64 for c in face['texture']['colors']))
            self.assertTrue(all(c[3] == 255 for c in face['texture']['colors']))
        self.assertTrue(any(f['texture'] and any(c[3] < 64 for c in f['texture']['colors'])
                            for f in faces))  # real effect/cutout alpha still survives

    def test_generic_houses_have_source_pivot_cameras_and_bounded_panorama(self):
        from build_opening_banks import house_panorama
        from vdp1_budget import bank_bytes
        for prefix in ('kakariko', 'kakariko3', 'impa', 'malon_stable', 'labo', 'tent'):
            scene = source.extract(OOT, None, prefix=prefix)[prefix + '_scene']
            bank, _, asset, sides, angle = PANORAMAS[prefix]
            self.assertEqual(panorama_room(prefix, scene, source), bank)
            vertices, faces, tiles = house_panorama(OOT, asset, sides, angle)
            self.assertEqual((len(vertices), len(faces)), (sides * 128, sides * 32))
            self.assertLessEqual(bank_bytes(sum(len(t['pixels']) for t in tiles.values()), len(tiles)), 140000)
        self.assertEqual(panorama_room('market_alley', b'', source), 255)


class RuntimeInteriorViews(unittest.TestCase):
    run_c = graphics.GraphicsBackend.run_c

    def test_generic_house_toggles_and_restores_view_after_failed_read(self):
        self.run_c(r'''
#include <stdbool.h>
#include <assert.h>
#define SCENE_KOKIRI_SHOP 2
#define STORY_BANK_PANORAMA 1026
static unsigned current_scene=43, last_scene,last_room,loads,failures;
static bool interior=true, backdrop=false,wait_ok=true;
static struct { unsigned panorama; } entry={10};
static bool scene_flow_is_interior(void) { return interior; }
static bool scene_flow_pivot(void) { return interior && !backdrop; }
#define scene_flow_entry() (&entry)
static bool vdp1_wait_for_draw_end(void) { return wait_ok; }
static bool load(unsigned s,unsigned r,bool image) {
    ++loads; last_scene=s; last_room=r;
    if(failures) {--failures; return false;}
    backdrop=image; return true;
}
static bool kokiri_scene_load_backdrop(unsigned s,unsigned r) {return load(s,r,true);}
static bool kokiri_scene_load_bank(unsigned s,unsigned r) {return load(s,r,false);}
static void jo_core_error(const char*s) {assert(0);}
''' + graphics.function(ROOT / 'src/scene_flow.c', 'bool scene_flow_toggle_view(') + r'''
int main(void) {
    assert(scene_flow_toggle_view() && backdrop && last_scene==43 && last_room==0);
    assert(scene_flow_toggle_view() && !backdrop && last_scene==1026 && last_room==10);
    failures=1; assert(!scene_flow_toggle_view() && !backdrop && last_room==10);
    entry.panorama=255; assert(!scene_flow_toggle_view());
    entry.panorama=2;current_scene=2;assert(!scene_flow_toggle_view());
    current_scene=43;wait_ok=false;assert(!scene_flow_toggle_view());
    assert(loads==4);
    return 0;
}
''')


if __name__ == '__main__':
    unittest.main()
