from pathlib import Path
import importlib.util
import json
import struct
import tempfile
import unittest

from PIL import Image

TOOL = Path(__file__).resolve().parents[1] / 'tools/mesh-workshop/mesh_assets.py'
spec = importlib.util.spec_from_file_location('mesh_assets', TOOL)
mesh = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mesh)


class MeshWorkshopTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.project = Path(self.temp.name)
        self.workspace = self.project / 'workspace'
        (self.project / 'cd').mkdir()
        vertices = [(0, 0, 0), (16, 0, 0), (16, 16, 0), (0, 16, 0)]
        vertex_data = b''.join(struct.pack('>3h', *v) for v in vertices)
        fo = 64 + len(vertex_data)
        co = fo + 40
        palette = struct.pack('>16H', *([0] + [0x801f] * 15))
        texture = palette + bytes([0x11] * 128)
        header = struct.pack('>9I3i4I', 0x4b465231, 2, 4, 2, 64, fo, co,
                             len(texture), co + len(texture), 8, 8, 0, 12, 5, co, 0)
        faces = b''.join(struct.pack('>4HIIHH', *ids, ids[-1], 32, 0, 0x210, 2)
                         for ids in ((0, 1, 2), (0, 2, 3)))
        self.source = self.project / 'cd/FOREST.BIN'
        self.source.write_bytes(header + vertex_data + faces + texture)
        (self.project / 'cd/A.BIN').write_bytes(b'executable')
        self.entry = mesh.catalog(self.project)[0]
        self.original = self.source.read_bytes()

    def candidate(self, face='f 1/1 2/2 3/3 4/4', last='0 16 0'):
        folder = self.project / 'edited'
        folder.mkdir(exist_ok=True)
        Image.new('RGBA', (16, 16), 'red').save(folder / 'atlas.png')
        (folder / 'mesh.mtl').write_text('newmtl flags_2\nmap_Kd atlas.png\n')
        path = folder / 'edited.obj'
        path.write_text('mtllib mesh.mtl\nv 0 0 0\nv 16 0 0\nv 16 16 0\nv ' + last +
                        '\nvt 0 0\nvt 1 0\nvt 1 1\nvt 0 1\nusemtl flags_2\n' + face + '\n')
        return path

    def test_discovery_excludes_executable(self):
        entries = mesh.catalog(self.project)
        self.assertEqual(len(entries), 1)
        self.assertEqual((entries[0]['vertices'], entries[0]['triangles']), (4, 2))

    def test_export_is_separate_and_textured(self):
        path = mesh.export_obj(self.entry, self.project, self.workspace)
        self.assertEqual(sum(line.startswith('f ') for line in path.read_text().splitlines()), 2)
        self.assertTrue((path.parent / 'mesh.mtl').exists())
        with Image.open(path.parent / 'atlas.png') as atlas:
            self.assertEqual(atlas.getpixel((2, 2)), (255, 0, 0, 255))
        self.assertEqual(self.source.read_bytes(), self.original)
        again = mesh.export_obj(self.entry, self.project, self.workspace)
        self.assertNotEqual(path, again)

    def test_quad_bundle_preference_and_safe_selection(self):
        folder = mesh.import_obj(self.entry, self.candidate(), self.project, self.workspace)
        meta = json.loads((folder / 'mesh.json').read_text())
        self.assertEqual((meta['triangles'], meta['quads']), (0, 1))
        self.assertFalse(meta['runtime_ready'])
        self.assertEqual(len(mesh.parse_obj(folder / 'mesh.obj')[2][0][1]), 4)
        self.assertTrue(mesh.load_settings(self.workspace)['prefer_quads'])
        selected = mesh.build_selection(self.entry, self.project, self.workspace)
        self.assertFalse(selected['using_quads'])
        self.assertEqual(selected['source'], str(self.source))
        self.assertEqual(self.source.read_bytes(), self.original)

    def test_negative_indices(self):
        self.assertEqual(len(mesh.parse_obj(self.candidate('f -4/-4 -3/-3 -2/-2 -1/-1'))[2]), 1)

    def test_split_nonplanar_preserves_corners_and_source(self):
        path = self.candidate(last='0 16 4')
        original = path.read_bytes()
        with self.assertRaises(ValueError): mesh.parse_obj(path)
        diagnostics = {}
        _, _, faces, _ = mesh.parse_obj(path, split_incompatible=True, diagnostics=diagnostics)
        self.assertEqual(diagnostics['split_quads'], 1)
        self.assertEqual([len(c) for _, c in faces], [3, 3])
        self.assertEqual({m for m, _ in faces}, {'flags_2'})
        self.assertEqual({corner for _, c in faces for corner in c}, {(0, 0), (1, 1), (2, 2), (3, 3)})
        folder = mesh.import_obj(self.entry, path, self.project, self.workspace, split_incompatible=True)
        meta = json.loads((folder / 'mesh.json').read_text())
        self.assertEqual((meta['quads'], meta['triangles'], meta['split_quads']), (0, 2, 1))
        self.assertEqual(path.read_bytes(), original)
        self.assertEqual(self.source.read_bytes(), self.original)

    def test_split_keeps_valid_quad_and_rejects_crossed(self):
        d = {}
        self.assertEqual(len(mesh.parse_obj(self.candidate(), split_incompatible=True, diagnostics=d)[2]), 1)
        self.assertEqual(d['split_quads'], 0)
        with self.assertRaises(ValueError):
            mesh.parse_obj(self.candidate('f 1/1 3/3 2/2 4/4'), split_incompatible=True)

    def test_split_concave_uses_interior_diagonal_both_windings(self):
        for order in ('f 1/1 2/2 3/3 4/4', 'f 4/4 3/3 2/2 1/1'):
            path = self.candidate(order, '8 4 0')
            vertices, _, faces, _ = mesh.parse_obj(path, split_incompatible=True)
            self.assertEqual(len(faces), 2)
            # Interior diagonal joins vertices 2 and 4 (zero-based 1 and 3).
            self.assertEqual(set(v for v, _ in faces[0][1]) & set(v for v, _ in faces[1][1]), {1, 3})

    def test_invalid_topology(self):
        for face, last in [('f 1/1 2/2 3/3 4/4 1/1', '0 16 0'),
                           ('f 1/1 3/3 2/2 4/4', '0 16 0'),
                           ('f 1/1 2/2 3/3 4/4', '0 16 4'),
                           ('f 1/1 2/2 3/3', '0 16 0'),
                           ('f 1 2 3 4', '0 16 0'),
                           ('f 1/1 2/2 3/3 0/4', '0 16 0')]:
            with self.subTest(face=face, last=last), self.assertRaises(ValueError):
                mesh.parse_obj(self.candidate(face, last))

    def test_materials_required_before_import_saved(self):
        path = self.candidate()
        (path.parent / 'mesh.mtl').write_text('newmtl flags_2\n')
        with self.assertRaises(ValueError):
            mesh.import_obj(self.entry, path, self.project, self.workspace)
        self.assertFalse(self.workspace.exists())

    def test_corrupt_container(self):
        self.source.write_bytes(self.original[:-1])
        self.assertTrue(mesh.catalog(self.project)[0]['error'])
        with self.assertRaises(ValueError): mesh.read_mesh(self.source)


if __name__ == '__main__':
    unittest.main()
