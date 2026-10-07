import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'mesh-workshop'))
import asset_catalog as assets


class AssetCatalogTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.repo = Path(self.tmp.name)
        self.game = self.repo / 'game'
        self.folder = self.game / 'assets/room-meshes/ydan_room_0'
        self.folder.mkdir(parents=True)
        self.obj = self.folder / 'mesh.obj'
        self.obj.write_text('example mesh')
        self.texture = self.folder / 'atlas.png'
        self.texture.write_bytes(b'preview')
        self.input = self.game / 'levels/edit.obj'
        self.input.parent.mkdir()
        self.input.write_text('edited source')
        self.config = self.game / 'assets/room_imports.json'
        self.record = dict(obj='room-meshes/ydan_room_0/mesh.obj', uv_mode='keep', publication=dict(
            published_at='2026-09-29T12:34:56+00:00', source='game/levels/edit.obj',
            source_sha256=assets.sha(self.input),
            files={'mesh.obj':assets.sha(self.obj), 'atlas.png':assets.sha(self.texture)}))
        self.write_config()

    def write_config(self):
        self.config.write_text(json.dumps({'ydan_room_0':self.record}))

    def rows(self):
        return assets.catalog(self.game)

    def test_link_exports_are_categorised_by_age(self):
        root = Path('workspace/meshes/link')
        self.assertEqual(assets.classify(root / 'child/swords/kokiri_sword_in_hand.obj', b'# Ex'),
                         'Link (Child)')
        self.assertEqual(assets.classify(root / 'adult/boots/iron_boot_left.obj', b'# Ex'),
                         'Link (Adult)')
        self.assertEqual(assets.classify(root / 'adult/boots/iron_boot_left_m0.png', b'PNG!'),
                         'Texture')
        self.assertEqual(assets.classify(Path('workspace/meshes/room.obj'), b'# Ex'), 'Mesh')

    def test_publication_and_timestamp_are_recorded_not_file_mtime(self):
        rows = self.rows()
        mesh = next(r for r in rows if r['path'] == self.obj)
        self.assertEqual(mesh['publication'], 'Published')
        self.assertEqual(mesh['published_at'], '2026-09-29T12:34:56+00:00')
        self.assertEqual(mesh['targets'], 'ydan_room_0')
        self.record.pop('publication')
        self.write_config()
        mesh = next(r for r in self.rows() if r['path'] == self.obj)
        self.assertEqual(mesh['publication'], 'Assigned')
        self.assertEqual(mesh['published_at'], '')

    def test_modified_and_missing_dependencies_and_stable_missing_id(self):
        before = next(r for r in self.rows() if r['path'] == self.texture)
        self.texture.write_bytes(b'new texture')
        mesh = next(r for r in self.rows() if r['path'] == self.obj)
        self.assertEqual(mesh['publication'], 'Modified')
        self.texture.unlink()
        rows = self.rows()
        missing = next(r for r in rows if r['path'] == self.texture)
        self.assertEqual(missing['publication'], 'Missing')
        self.assertEqual(missing['id'], before['id'])
        self.assertEqual(next(r for r in rows if r['path'] == self.obj)['publication'], 'Missing')

    def test_obj_bundle_export_copies_mtl_texture_and_json(self):
        folder = self.repo / 'workspace/meshes/link/adult/body'
        folder.mkdir(parents=True)
        obj = folder / 'adult_link.obj'
        obj.write_text('mtllib adult_link.mtl\nusemtl body\n')
        (folder / 'adult_link.mtl').write_text('newmtl body\nmap_Kd adult_link.png\n')
        (folder / 'adult_link.png').write_bytes(b'png')
        (folder / 'adult_link.actor.json').write_text('{}')
        (folder / 'other.png').write_bytes(b'no')
        dest = self.repo / 'out' / 'hero.obj'
        written = assets.copy_mesh_bundle(obj, dest)
        self.assertEqual(dest.read_text(), obj.read_text())
        self.assertEqual((dest.parent / 'adult_link.mtl').read_text().split()[-1], 'adult_link.png')
        self.assertEqual((dest.parent / 'adult_link.png').read_bytes(), b'png')
        self.assertTrue((dest.parent / 'adult_link.actor.json').is_file())
        self.assertFalse((dest.parent / 'other.png').exists())
        self.assertEqual(len(written), 4)
        row = dict(path=obj, exportable=False, origin='Workspace')
        self.assertTrue(assets.can_export(row))
        self.assertTrue(assets.can_replace(row))
        self.assertFalse(assets.can_replace(dict(path=obj, exportable=False, origin='Generated')))

    def test_source_edit_does_not_mark_unchanged_installed_copy_modified(self):
        self.input.write_text('new edit')
        rows = self.rows()
        self.assertEqual(next(r for r in rows if r['path'] == self.input)['publication'], 'Modified')
        self.assertEqual(next(r for r in rows if r['path'] == self.obj)['publication'], 'Published')

    def test_full_roots_types_and_numeric_sort(self):
        for name in ('shared/assets/music.wav', 'workspace/meshes/revision/mesh.obj',
                     'game/build/generated/motion.anm', 'game/build/cd/ROOM.MSH', 'game/build/TRACK02.BIN'):
            path = self.repo / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b'1234567890')
        rows = self.rows()
        self.assertTrue({'Shared','Source','Workspace','Generated','Staged','CD audio'} <= {r['origin'] for r in rows})
        matched = assets.select_rows(rows, 'ROOM mesh', kind='Mesh', status='Published')
        self.assertEqual({r['path'] for r in matched}, {self.obj, self.input})
        sizes = [r['size'] for r in assets.select_rows(rows, sort='size')]
        self.assertEqual(sizes, sorted(sizes))
        self.assertEqual(assets.select_rows(rows, query='does not exist'), [])

    def test_publishing_over_input_path_uses_installed_fingerprint(self):
        self.record['publication']['source'] = self.obj.relative_to(self.repo).as_posix()
        self.record['publication']['source_sha256'] = 'previous unnormalized input'
        self.write_config()
        mesh = next(r for r in self.rows() if r['path'] == self.obj)
        self.assertEqual(mesh['publication'], 'Published')


if __name__ == '__main__':
    unittest.main()
