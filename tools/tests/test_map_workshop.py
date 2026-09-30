import copy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
from PIL import Image

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'mesh-workshop'))
import viewport_scene as scene
from map_render import textured_frame
meshes=scene.map_meshes


class MapTests(unittest.TestCase):
    def test_authored_ground_skips_automatic_refinement(self):
        import build_hybrid_scene as hybrid
        points=[(0,0,0,0,0,255,255,255,255),(1000,0,0,1,0,255,255,255,255),
                (1000,0,1000,1,1,255,255,255,255),(0,0,1000,0,1,255,255,255,255)]
        group=dict(points=points,kind=hybrid.quads.BAKE,size=1000,
                   tri=dict(authored_mesh=True,transparent=False))
        self.assertEqual(hybrid.room_ground(group),[group])
        self.assertEqual(hybrid.refine_room_ground([group],[],dict(polygons=0,vertices=0),100000),[group])

    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.game=Path(self.temp.name)
        source=self.game/'input'; source.mkdir()
        self.obj=source/'mesh.obj'
        self.obj.write_text('mtllib mesh.mtl\nv 0 0 0\nv 10 0 0\nv 0 10 0\nvt 0 0\nvt 1 0\nvt 0 1\nusemtl test\nf 1/1 2/2 3/3\n')
        (source/'mesh.mtl').write_text('newmtl test\nmap_Kd image.png\n')
        Image.new('RGBA',(8,8),(255,20,10,255)).save(source/'image.png')
        self.room='spot04_room_0'; self.raw=b'original source'
        self.entry=dict(sha256=hashlib.sha256(self.raw).hexdigest(),bundle='original',position=[5,5,0],yaw=0,scale=1)
        self.face=dict(vertices=[(0,0,0,0,0,255,255,255,255),(10,0,0,1,0,255,255,255,255),(0,10,0,0,1,255,255,255,255)],
                       texture=None,prim=(255,255,255,255),lighting=False,transparent=False,cull=False,room=self.room,object=2)

    def document(self,entry):
        doc=scene.layouts.empty(); doc['meshes']={self.room+'/object/2':entry}; return doc

    def test_move_preserves_original_uvs_and_other_objects(self):
        other=dict(self.face,object=3)
        entry=dict(self.entry,position=[15,5,0])
        result=meshes.apply_faces([self.face,other],{self.room:self.raw},self.document(entry),self.game)
        moved=next(f for f in result if f['object']==2)
        self.assertEqual(moved['vertices'][0],(10,0,0,0,0,255,255,255,255))
        self.assertIs(next(f for f in result if f['object']==3),other)
        self.assertEqual(self.face['vertices'][0][0],0)

    def test_store_is_immutable_and_detects_changed_dependencies(self):
        identity=meshes.store(self.obj,self.game)
        self.assertEqual(identity,meshes.store(self.obj,self.game))
        folder=meshes.bundle_path(identity,self.game)
        (folder/'mesh.mtl').write_text('changed')
        with self.assertRaises(ValueError): meshes.bundle_path(identity,self.game)

    def test_split_confirmation_can_cancel_without_publishing(self):
        self.obj.write_text('mtllib mesh.mtl\nv 0 0 0\nv 10 0 0\nv 10 10 2\nv 0 10 0\nvt 0 0\nvt 1 0\nvt 1 1\nvt 0 1\nusemtl test\nf 1/1 2/2 3/3 4/4\n')
        seen=[]
        self.assertIsNone(meshes.store(self.obj,self.game,confirm_split=lambda d: seen.append(d) or False))
        self.assertEqual(seen[0]['split_quads'],1)
        self.assertFalse((self.game/'assets/layouts/meshes').exists())
        identity=meshes.store(self.obj,self.game,confirm_split=lambda d: True)
        self.assertTrue(meshes.bundle_path(identity,self.game).is_dir())

    def test_replace_only_selected_mesh_with_local_placement(self):
        identity=meshes.store(self.obj,self.game)
        entry=dict(self.entry,bundle=identity,position=[100,20,30],yaw=90,scale=2)
        doc=self.document(entry); scene.layouts.validate(doc)
        result=meshes.apply_faces([self.face,dict(self.face,object=9)],{self.room:self.raw},doc,self.game)
        new=next(f for f in result if f['object']==2)
        self.assertEqual(new['vertices'][0][:3],(100,20,30))
        self.assertAlmostEqual(new['vertices'][1][2],10)
        self.assertEqual({f['object'] for f in result},{2,9})
        self.assertEqual(new['texture']['colors'][0],(255,20,10,255))

    def test_stale_room_or_missing_object_fails(self):
        with self.assertRaises(ValueError): meshes.apply_faces([self.face],{self.room:b'new'},self.document(self.entry),self.game)
        with self.assertRaises(ValueError): meshes.apply_faces([],{self.room:self.raw},self.document(self.entry),self.game)

    def test_nonfinite_transform_rejected(self):
        for value in (float('nan'),float('inf'),0):
            with self.assertRaises(ValueError): scene.layouts.validate(self.document(dict(self.entry,scale=value)))

    def test_unsupported_build_mode_cannot_ignore_mesh_edits(self):
        with patch.dict('os.environ',{'TEXTURE_PATH':'legacy'},clear=True):
            with self.assertRaises(ValueError): scene.layouts.validate_environment(self.document(self.entry))
        with patch.dict('os.environ',{'STREAM_ROOMS':'0'},clear=True):
            with self.assertRaises(ValueError): scene.layouts.validate_environment(self.document(self.entry))

    def test_export_obj_mtl_texture_roundtrip(self):
        obj=meshes.export_faces([self.face],self.game/'export')
        identity=meshes.store(obj,self.game)
        result=meshes.replacement_faces(dict(self.entry,bundle=identity,position=[0,0,0]),self.room,2,self.game)
        self.assertEqual([v[:3] for v in result[0]['vertices']],[v[:3] for v in self.face['vertices']])
        self.assertEqual(len(list((self.game/'export').glob('mesh_texture_*.png'))),1)
        self.assertFalse((self.game/'export/atlas.png').exists())

    def test_texture_preview_contains_sampled_material(self):
        identity=meshes.store(self.obj,self.game)
        raw=meshes.replacement_faces(dict(self.entry,bundle=identity),self.room,2,self.game)[0]
        image=textured_frame([(10,[(0,0),(100,0),(0,100)],dict(layer='Mesh',source_face=raw,colour=(1,1,1)))],100,100)
        self.assertEqual(image.getpixel((20,20))[:3],(255,20,10))

    def test_named_export_keeps_full_pixels_and_tiled_mirrored_uvs(self):
        tex=dict(width=8,height=4,colors=[(x*30,y*60,17,255) for y in range(4) for x in range(8)],
                 scale=(.5,1),shifts=1,shiftt=0,uls=4,ult=8,cms=1,cmt=0,masks=3,maskt=2,address=0x03000000)
        vertices=[(0,0,0,-20,-6,255,255,255,255),(10,0,0,140,10,255,255,255,255),(0,10,0,20,22,255,255,255,255)]
        face=dict(self.face,texture=tex,vertices=vertices,prim=(180,210,240,255),cull=True)
        obj=meshes.export_faces([face,face],self.game/'Water platform.obj')
        self.assertEqual(obj.name,'Water platform.obj')
        images=list(self.game.glob('Water platform_texture_*.png'))
        self.assertEqual(len(images),1)  # reuse source material, not one image per triangle
        with Image.open(images[0]) as exported:
            self.assertEqual(exported.size,(8,4))
            self.assertEqual(list(exported.getdata()),tex['colors'])
        identity=meshes.store(obj,self.game)
        restored=meshes.replacement_faces(dict(self.entry,bundle=identity,position=[0,0,0]),self.room,2,self.game)[0]
        self.assertEqual(restored['prim'],face['prim'])
        self.assertTrue(restored['cull'])
        def sample(f,weights):
            t=f['texture']; uv=[sum(w*p[3+k] for w,p in zip(weights,f['vertices'])) for k in (0,1)]
            x=meshes.source.coordinate(uv[0],t['scale'][0],t['shifts'],t['uls'],t['cms'],t['masks'],t['width'])
            y=meshes.source.coordinate(uv[1],t['scale'][1],t['shiftt'],t['ult'],t['cmt'],t['maskt'],t['height'])
            return t['colors'][y*t['width']+x]
        for weights in ((1,0,0),(0,1,0),(0,0,1),(.25,.5,.25),(.1,.3,.6)):
            self.assertEqual(sample(face,weights),sample(restored,weights))

    def test_missing_source_sampler_file_fails_instead_of_changing_wrap(self):
        obj=meshes.export_faces([self.face],self.game/'named.obj')
        obj.with_suffix('.materials.json').unlink()
        with self.assertRaises(ValueError): meshes.store(obj,self.game)

    def test_blender_renamed_obj_recovers_from_matching_original_mtl(self):
        original=meshes.export_faces([self.face],self.game/'water.obj')
        changed=self.game/'waterquads.obj'
        changed.write_text(original.read_text().replace('water.mtl','waterquads.mtl'))
        material=original.with_suffix('.mtl').read_text()
        changed.with_suffix('.mtl').write_text('\n'.join(line for line in material.splitlines() if not line.startswith('#')))
        self.assertEqual(meshes.read_material_metadata(changed),meshes.read_material_metadata(original))
        identity=meshes.store(changed,self.game)
        self.assertTrue(meshes.bundle_path(identity,self.game).is_dir())
        # Identical generic material names on a different image must not match.
        changed.with_suffix('.mtl').write_text(material.replace('# dosei_materials: water.materials.json','').replace('map_Kd water_texture_','map_Kd unrelated_texture_'))
        with self.assertRaises(ValueError): meshes.read_material_metadata(changed)

    def test_conflicting_matching_sampler_sources_are_not_guessed(self):
        original=meshes.export_faces([self.face],self.game/'water.obj')
        changed=self.game/'quad.obj'
        changed.write_text(original.read_text().replace('water.mtl','quad.mtl'))
        material=original.with_suffix('.mtl').read_text()
        changed.with_suffix('.mtl').write_text('\n'.join(line for line in material.splitlines() if not line.startswith('#')))
        (self.game/'other.mtl').write_text(material.replace('water.materials.json','other.materials.json'))
        metadata=meshes.read_material_metadata(original)
        metadata['materials']['dosei_000']['cms']=2
        (self.game/'other.materials.json').write_text(json.dumps(metadata))
        with self.assertRaisesRegex(ValueError,'Conflicting'): meshes.read_material_metadata(changed)

    def test_blender_duplicate_material_and_copied_image_keep_sampler(self):
        original=meshes.export_faces([self.face],self.game/'ground.obj')
        changed=self.game/'groundQ.obj'
        changed.write_text(original.read_text().replace('ground.mtl','groundQ.mtl').replace('dosei_000','dosei_000.001'))
        material=original.with_suffix('.mtl').read_text()
        image_name=next(line[7:] for line in material.splitlines() if line.startswith('map_Kd '))
        copied=self.game/'copied.png'
        with Image.open(self.game/image_name) as image: image.save(copied)
        changed.with_suffix('.mtl').write_text('\n'.join(line for line in material.splitlines() if not line.startswith('#')).replace('dosei_000','dosei_000.001').replace(image_name,copied.as_posix()))
        expected=meshes.read_material_metadata(original)['materials']['dosei_000']
        self.assertEqual(meshes.read_material_metadata(changed)['materials']['dosei_000.001'],expected)
        identity=meshes.store(changed,self.game)
        faces=meshes.replacement_faces(dict(self.entry,bundle=identity),self.room,2,self.game)
        self.assertEqual(faces[0]['prim'],tuple(expected['prim']))
        Image.new('RGBA',(1,1),(0,0,0,255)).save(copied)
        with self.assertRaises(ValueError): meshes.read_material_metadata(changed)


if __name__=='__main__': unittest.main()
