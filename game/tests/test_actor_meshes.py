"""Character OBJ exchange keeps limb ownership, locals and materials."""
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import actor_meshes

IDENTITY = ((1, 0, 0), (0, 1, 0), (0, 0, 1))
TURN = ((0, 0, 1), (0, 1, 0), (-1, 0, 0))     # 90 degrees about Y
POSES = {0: (IDENTITY, (0, 0, 0)), 1: (TURN, (0, 100, 0))}
TEXTURE = dict(width=2, height=2, colors=[(255, 0, 0, 255)] * 4, scale=(1.0, 1.0),
               shifts=0, shiftt=0, uls=0, ult=0, cms=0, cmt=0, masks=1, maskt=1)


def face(limb, owners, locals_, group='body'):
    posed = [actor_meshes._apply(*POSES[o], l) for o, l in zip(owners, locals_)]
    return dict(vertices=[p + (i * 32, 32, 255, 255, 255, 255) for i, p in enumerate(posed)],
                vertex_limbs=list(owners), local=[tuple(l) for l in locals_], limb=limb,
                group=group, texture=dict(TEXTURE), prim=(255, 255, 255, 255),
                transparent=False, cull=True, lighting=False, texture_segment=6)


def faces():
    return [face(0, (0, 0, 0), ((0, 0, 0), (10, 0, 0), (0, 10, 0))),
            face(1, (0, 1, 1), ((0, 10, 0), (5, 0, 0), (0, 0, 5))),
            face(1, (1, 1, 1), ((5, 0, 0), (0, 0, 5), (5, 5, 5)), 'left_sword')]


class ActorMeshes(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.obj = Path(self.temp.name) / 'link.obj'
        actor_meshes.export_obj(faces(), self.obj, 'link')

    def tearDown(self):
        self.temp.cleanup()

    def test_named_files(self):
        names = {p.suffix for p in Path(self.temp.name).iterdir()}
        self.assertTrue({'.obj', '.mtl', '.json', '.png'} <= names)
        self.assertIn('m000.body.L00', self.obj.read_text())

    def test_unchanged_round_trip(self):
        out = actor_meshes.load_obj(self.obj, 'link', faces(), POSES)
        for a, b in zip(faces(), out):
            self.assertEqual(a['vertex_limbs'], b['vertex_limbs'])
            self.assertEqual(a['local'], b['local'])
            self.assertEqual(a['group'], b['group'])
            for va, vb in zip(a['vertices'], b['vertices']):
                self.assertEqual([round(v, 6) for v in va], [round(v, 6) for v in vb])

    def test_moved_vertex_takes_nearest_owner(self):
        text = self.obj.read_text().splitlines()
        # Fourth exported vertex is limb 1 local (5,0,0) posed at (0,100,-5).
        index = [i for i, l in enumerate(text) if l.startswith('v ')][3]
        text[index] = 'v 0 101 -5'
        self.obj.write_text('\n'.join(text) + '\n')
        out = actor_meshes.load_obj(self.obj, 'link', faces(), POSES)
        self.assertEqual(out[1]['vertex_limbs'][1], 1)
        self.assertEqual(out[1]['local'][1], (5, 1, 0))

    def test_dropped_group_rejected(self):
        text = [l for l in self.obj.read_text().splitlines()]
        cut = next(i for i, l in enumerate(text) if 'left_sword' in l)
        self.obj.write_text('\n'.join(text[:cut]) + '\n')
        with self.assertRaisesRegex(ValueError, 'left_sword'):
            actor_meshes.load_obj(self.obj, 'link', faces(), POSES)

    def test_sidecar_required(self):
        self.obj.with_suffix('.actor.json').unlink()
        with self.assertRaisesRegex(ValueError, 'missing'):
            actor_meshes.load_obj(self.obj, 'link', faces(), POSES)

    def test_override_from_recipe(self):
        game = Path(self.temp.name)
        recipe = actor_meshes.recipe_path('zelda', game)
        recipe.parent.mkdir(parents=True)
        self.assertIsNone(actor_meshes.override('zelda', game))
        recipe.write_text(json.dumps(dict(mesh_override='mesh/zelda.obj')))
        self.assertEqual(actor_meshes.override('zelda', game), recipe.parent / 'mesh/zelda.obj')


if __name__ == '__main__':
    unittest.main()
