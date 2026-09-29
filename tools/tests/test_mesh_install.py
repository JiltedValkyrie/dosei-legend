from pathlib import Path
import json
import os
import struct
import sys
import tempfile
import unittest
from unittest.mock import patch

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'mesh-workshop'))
import game_install as install
import room_imports


class MeshInstallTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        generated = self.root / 'build/generated'
        generated.mkdir(parents=True)
        # Small real KFR1 actor container, including one texture and CLUT.
        vertices = struct.pack('>9h', 0, 0, 0, 16, 0, 0, 0, 16, 0)
        fo = 64 + len(vertices)
        to = fo + 20
        texture = struct.pack('>16H', *([0x801f] * 16)) + bytes([0x11] * 128)
        face = struct.pack('>4HIIHH', 0, 1, 2, 2, 32, 0, 0x210, 2)
        header = struct.pack('>9I3i4I', 0x4b465231, 2, 3, 1, 64, fo, to,
                             len(texture), to + len(texture), 0, 0, 0, 16, 1, to, 0)
        (generated / 'LINK.BIN').write_bytes(header + vertices + face + texture)
        self.obj = self.root / 'edit.obj'
        self.obj.write_text('mtllib edit.mtl\nv 0 0 0\nv 16 0 0\nv 16 16 0\nv 0 16 0\n'
                            'vt 0 0\nvt 1 0\nvt 1 1\nvt 0 1\nusemtl flags_3\nf 1/1 2/2 3/3 4/4\n')
        (self.root / 'edit.mtl').write_text('newmtl flags_3\nmap_Kd atlas.png\n')
        Image.new('RGBA', (16, 16), 'red').save(self.root / 'atlas.png')
        self.config = self.root / 'assets/room_imports.json'
        self.target = next(iter(install.GAME_TARGETS))

    def use(self, target=None):
        return install.install_mesh(self.obj, target or self.target, project=self.root)

    def test_all_targets_persist_overwrite_and_pack(self):
        from build_room_scene import pack_room
        from build_sgl_scene import face_normal
        for target, key in install.GAME_TARGETS.items():
            folder = self.use(target)
            self.assertTrue((folder / 'mesh.obj').is_file())
            published = json.loads(self.config.read_text())[key]['publication']
            from datetime import datetime
            self.assertIsNotNone(datetime.fromisoformat(published['published_at']).tzinfo)
            self.assertIn('mesh.obj', published['files'])
            with patch.object(room_imports, 'DEFAULT_CONFIG', self.config), patch.dict(os.environ, {}, clear=True):
                prefix, _, room = key.rpartition('_room_')
                entry = room_imports.selected(prefix, int(room))
                v, f, t, m = room_imports.convert(entry, dict(tiles=[], polygons=0, vertices=0))
                self.assertTrue(f[0]['cull'])
                self.assertTrue(f[0]['mesh'])
                blob, pixels, _ = pack_room(v, f, t, m['faces'], face_normal)
                self.assertEqual(blob[:4], b'KRM1')
                self.assertTrue(pixels)
                self.assertEqual(any(p['label'] == 'actors' for p in m['budget']), prefix == 'spot04')
            self.obj.write_text(self.obj.read_text().replace('v 16 16 0', 'v 16 17 0'))
            self.use(target)
            self.assertIn('v 16 17 0', (folder / 'mesh.obj').read_text())
        self.assertEqual(set(json.loads(self.config.read_text())), set(install.GAME_TARGETS.values()))

    def test_invalid_geometry_preserves_installed_files(self):
        self.use()
        before = {p: p.read_bytes() for p in (self.root / 'assets').rglob('*') if p.is_file()}
        self.obj.write_text(self.obj.read_text().replace('v 16 16 0', 'v 99999 16 0'))
        with self.assertRaisesRegex(ValueError, 'signed-16-bit'):
            self.use()
        self.assertEqual(before, {p: p.read_bytes() for p in (self.root / 'assets').rglob('*') if p.is_file()})

    def test_failed_replace_rolls_back(self):
        self.use()
        before = {p: p.read_bytes() for p in (self.root / 'assets').rglob('*') if p.is_file()}
        self.obj.write_text(self.obj.read_text().replace('v 16 16 0', 'v 16 17 0'))
        original = Path.replace
        def fail_manifest(path, destination):
            if destination == self.config:
                raise OSError('simulated write failure')
            return original(path, destination)
        with patch.object(Path, 'replace', fail_manifest), self.assertRaises(OSError):
            self.use()
        self.assertEqual(before, {p: p.read_bytes() for p in (self.root / 'assets').rglob('*') if p.is_file()})

    def test_triangles_allowed_and_missing_actor_reported(self):
        self.obj.write_text(self.obj.read_text().replace(' 4/4', ''))
        self.use()
        (self.root / 'build/generated/LINK.BIN').unlink()
        with self.assertRaisesRegex(ValueError, 'Build the game Clean once'):
            self.use()

    def test_explicit_config_overrides_default(self):
        self.use()
        other = self.root / 'manual.json'
        other.write_text('{}')
        with patch.object(room_imports, 'DEFAULT_CONFIG', self.config), patch.dict(os.environ, ROOM_IMPORTS=str(other)):
            self.assertIsNone(room_imports.selected('spot04', 0))

    def test_targets_match_playable_rooms(self):
        from build_scene_table import SCENES
        expected = {f"{s['prefix']}_room_{i}" for s in SCENES if s['shape'] == 'mesh' for i in range(s['rooms'])}
        self.assertEqual(set(install.GAME_TARGETS.values()), expected)

    def test_over_budget_rejected_before_overwrite(self):
        self.use()
        before = self.config.read_bytes()
        installed = self.root / 'assets/room-meshes/spot04_room_0/mesh.obj'
        original = installed.read_bytes()
        # Unused vertices still consume runtime table space and must count.
        self.obj.write_text(self.obj.read_text() + 'v 1 2 3\n' * 2500)
        with self.assertRaisesRegex(ValueError, 'vertices exceed'):
            self.use()
        self.assertEqual(self.config.read_bytes(), before)
        self.assertEqual(installed.read_bytes(), original)


if __name__ == '__main__':
    unittest.main()
