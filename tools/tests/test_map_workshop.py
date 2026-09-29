import copy
import hashlib
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
        self.assertTrue((self.game/'export/atlas.png').is_file())

    def test_texture_preview_contains_sampled_material(self):
        identity=meshes.store(self.obj,self.game)
        raw=meshes.replacement_faces(dict(self.entry,bundle=identity),self.room,2,self.game)[0]
        image=textured_frame([(10,[(0,0),(100,0),(0,100)],dict(layer='Mesh',source_face=raw,colour=(1,1,1)))],100,100)
        self.assertEqual(image.getpixel((20,20))[:3],(255,20,10))


if __name__=='__main__': unittest.main()
