"""Shield provenance, exclusive variant selection and live-facing arithmetic."""
import ctypes
import math
import os
from pathlib import Path
import random
import re
import struct
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
OOT = Path(os.environ.get('OOT_DECOMP', 'D:/Workspace-Claude/game-decomps/n64/oot'))
GCC = Path('C:/msys64/mingw64/bin/gcc.exe')
sys.path.insert(0, str(ROOT / 'tools'))
import build_link_gear as gear
import build_link_model as model


@unittest.skipUnless(GCC.is_file(), 'host GCC required')
class LiveFacing(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        path = Path(cls.tmp.name) / 'shield.dll'
        draw = (ROOT / 'src/kokiri_sgl.c').read_text()
        selection = draw[draw.index('        unsigned visible_gear ='):]
        selection = selection[:selection.index('        /* One submission:')]
        enums = re.search(r'enum \{ GEAR_LEFT_MASTER.*?};', draw, re.S)[0]
        adapter = '''
#include <stdint.h>
#include <stdbool.h>
typedef int32_t FIXED;
typedef FIXED POINT[3];
#include "link_shield_normal.h"
#include "link_equipment.h"
#define GP_SWORD 1u
#define GP_SHIELD 2u
#define EQUIP_VALUE_SWORD_BIGGORON 3
#define EQUIP_VALUE_SHIELD_MIRROR 3
#define SAVE_BOOTS_IRON 1
struct { unsigned equipped; } gameplay;
struct { unsigned link_age, equip_sword, equip_shield, tunic, boots; } save_state;
static unsigned gear_active, equipped_count, equipped_mask;
static unsigned flat_shields, flat_parts, input_out, input_ocarina;
static bool gear_ready;
static unsigned player_items_stick(void) { return 0; }
static unsigned oot_core_ocarina_state(void) { return input_ocarina; }
static bool recomp_sword_out(void) { return input_out; }
static void link_part(unsigned first, unsigned count) {
    (void)count; ++flat_parts;
    if (first==LINK_RIGHT_SHIELD_FIRST || first==LINK_SHEATH_SHIELD_FIRST) ++flat_shields;
}
void normal(const POINT a,const POINT b,const POINT c,FIXED *out) {
    link_shield_normal(a,b,c,out);
}
'''
        adapter += enums + '''
unsigned select_groups(unsigned adult, unsigned sword_id, unsigned shield_id,
                       unsigned out, unsigned playing, unsigned uploaded) {
    save_state.link_age=!adult; save_state.equip_sword=sword_id; save_state.equip_shield=shield_id;
    gameplay.equipped=(sword_id ? GP_SWORD:0)|(shield_id ? GP_SHIELD:0);
    gear_ready=adult && uploaded; input_out=out; input_ocarina=playing;
    equipped_mask=0xFFFFFFFFu; flat_shields=flat_parts=0;
''' + selection + '''
    return gear_active | (flat_shields<<16);
}
'''
        env = dict(os.environ)
        env['PATH'] = str(GCC.parent) + os.pathsep + env.get('PATH', '')
        subprocess.run([str(GCC), '-shared', '-O2', '-Wall', '-Werror',
                        '-I' + str(ROOT / 'src'), '-I' + str(ROOT / 'build/generated'),
                        '-x', 'c', '-', '-o', str(path)], input=adapter, text=True,
                       check=True, env=env)
        cls.lib = ctypes.CDLL(str(path))

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def normal(self, points):
        point = ctypes.c_int32 * 3
        out = point()
        self.lib.normal(*(point(*(round(v * 65536) for v in p)) for p in points), out)
        return tuple(out)

    def test_actual_selection_never_draws_two_equipped_shields(self):
        shield_bits = sum(1 << n for n in (1, 3, 5, 6, 9, 10))
        for adult in (0, 1):
            for sword in (0, 1, 2, 3):
                for shield in (0, 1, 2, 3):
                    for drawn in (0, 1):
                        for ocarina in (0, 1):
                            for upload in (0, 1):
                                active = self.lib.select_groups(adult, sword, shield, drawn, ocarina, upload)
                                self.assertLessEqual((active & shield_bits).bit_count() + (active >> 16), 1)
                                if not shield:
                                    self.assertEqual(active & shield_bits, 0)
                                if adult and upload and shield in (2, 3):
                                    stowed = ocarina or not drawn
                                    expected = ((6 if shield == 3 else 3) if sword else
                                                (10 if shield == 3 else 9)) if stowed else (5 if shield == 3 else 1)
                                    self.assertEqual(active & shield_bits, 1 << expected)

    def test_winding_and_small_triangles_survive_live_rotation(self):
        rng = random.Random(410)
        for scale in (.125, 1, 35, 1000):
            for _ in range(50):
                rotate = model.rotation_matrix([rng.randrange(65536) for _ in range(3)])
                points = [model.transform(rotate, (23.7, -18.1, 6.25), p)
                          for p in ((0, 0, 0), (scale, 0, 0), (0, scale, 0))]
                result = self.normal(points)
                expected = tuple(-rotate[k][2] for k in range(3))
                length = math.sqrt(sum(n*n for n in result))
                self.assertGreater(length, 0)
                self.assertGreater(sum(a*b for a, b in zip(result, expected))/length, .997)
                self.assertLessEqual(max(map(abs, result)), 65536)
                opposite = self.normal((points[0], points[2], points[1]))
                self.assertLess(sum(a*b for a, b in zip(result, opposite)), 0)

    def test_degenerate_and_large_fixed_coordinates_are_bounded(self):
        self.assertEqual(self.normal(((2, 3, 4),)*3), (0, 0, 0))
        result = self.normal(((-32767, -32767, -32767), (32767, -32767, -32767),
                              (-32767, 32767, -32767)))
        self.assertEqual(result[:2], (0, 0))
        self.assertLess(result[2], 0)
        self.assertLessEqual(abs(result[2]), 65536)

    @unittest.skipUnless((OOT / 'assets/xml/objects/object_link_boy.xml').is_file(), 'OoT source required')
    def test_actual_hylian_wood_faces_away_from_front_in_live_poses(self):
        faces = gear.gear_faces(OOT, None)
        for group in ('right_hylian', 'sheath_hylian', 'back_hylian'):
            shield = [f for f in faces if f['group'] == group and f['cull']]
            for angle in (0, 8192, 16384, 32768, 48000):
                rotate = model.rotation_matrix((angle // 2, angle, 4096))
                normals = []
                for face in shield:
                    points = [model.transform(rotate, (0, 0, 0), [v*.01 for v in p])
                              for p in face['local']]
                    result = self.normal([(x, -y, z) for x, y, z in points])
                    normals.append((face['texture']['address'] == 0x04000400, result))
                front = [sum(n[k] for is_front, n in normals if is_front) for k in range(3)]
                for is_front, normal in normals:
                    dot = sum(a*b for a, b in zip(front, normal))
                    self.assertGreater(dot if is_front else -dot, 0)


@unittest.skipUnless((OOT / 'assets/xml/objects/object_link_boy.xml').is_file(), 'OoT source required')
class ShieldSource(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.faces = gear.gear_faces(OOT, None)

    def test_hylian_keeps_original_front_and_wood_back(self):
        materials = gear.shield_materials(OOT)
        counts = {}
        for group in ('right_hylian', 'sheath_hylian', 'back_hylian'):
            faces = [f for f in self.faces if f['group'] == group and f['cull']]
            self.assertEqual(len(faces), 10)
            counts[group] = sorted(sum(f['texture']['address'] == image for f in faces)
                                   for image in materials['hylian'])
            self.assertEqual(counts[group], [4, 6])
        source = (OOT / 'src/code/z_player_lib.c').read_text()
        self.assertIn('gSPSegment(POLY_OPA_DISP++, 0x0C, gCullBackDList)', source)
        self.assertRegex(source, r'gCullBackDList\[\].*?\{\s*gsSPSetGeometryMode\(G_CULL_BACK\)')

    def test_culling_is_limited_to_source_shield_materials(self):
        materials = gear.shield_materials(OOT)
        for face in self.faces:
            selected = any(kind in face['group'] and face['texture'].get('address') in images
                           for kind, images in materials.items())
            self.assertEqual(face['cull'], selected)
            if face['cull']:
                self.assertTrue(face['full_texture'])
        for group in ('right_mirror', 'sheath_mirror', 'back_mirror'):
            self.assertTrue(any(f['group'] == group and f['cull'] for f in self.faces))
        # Adult bank never imports a Deku list; child bank still explicitly uses
        # Deku. A child Hylian variant is separate missing coverage, not proof
        # of a second shield being drawn over the adult Hylian front.
        self.assertFalse(any('Deku' in symbol for _, parts in gear.GROUPS for _, symbol in parts))
        self.assertTrue(any('DekuShield' in symbol for _, _, symbol in model.GEAR_LISTS))

    def test_bake_changes_only_shield_plane_flags(self):
        with tempfile.TemporaryDirectory() as temp:
            out = Path(temp)
            values = gear.build(OOT, None, out, out)
            data = (out / 'LGEARMSH.BIN').read_bytes()
            first = values['POLYGON_COUNT'] * 20
            flags = [data[first + i*12] for i in range(values['POLYGON_COUNT'])]
            self.assertEqual(flags, [0 if f['cull'] else 1 for f in self.faces])
            self.assertEqual(len(data), values['POLYGON_COUNT'] * 32)
            skin = (out / 'LGEARSKN.BIN').read_bytes()
            self.assertEqual(struct.unpack_from('>H', skin, 6)[0], len(self.faces))


if __name__ == '__main__':
    unittest.main()
