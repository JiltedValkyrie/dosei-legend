"""Outliner exchange must protect Original and refresh the selected alternate."""
import copy
from pathlib import Path
import sys
import time
import tkinter as tk
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'mesh-workshop'))
from level_viewport import RoomViewport
from map_inspector import ObjectInspector


class OutlinerTests(unittest.TestCase):
    def setUp(self):
        self.root=tk.Tk(); self.root.withdraw()
        self.view=RoomViewport(self.root,autoload=False)
        self.view.withdraw()
        self.eid='spot04/room/0/mesh/2'
        self.key='spot04_room_0/object/2'
        self.scene=dict(prefix='spot04',room=0,source_sha256='a'*64,warnings=[],bounds=((0,0,0),(10,10,10)),
            entities=[dict(id=self.eid,label='Mesh object 2',kind='Mesh',bounds=((0,0,0),(10,10,10)),details=dict(mesh_key=self.key))],
            faces=[dict(entity=self.eid,layer='Mesh',points=[(0,0,0),(10,0,0),(0,10,0)],colour=(255,255,255),
                        source_face=dict(texture=None,vertices=[(0,0,0),(10,0,0),(0,10,0)]))])
        self.view.set_scene(self.scene); self.view.select(self.eid)

    def tearDown(self):
        self.view.unsaved=False; self.view.close(); self.root.destroy()

    def test_right_click_selects_mesh_and_original_disables_import(self):
        self.view.selected=None
        with patch.object(self.view.outliner,'identify_row',return_value=self.eid),patch.object(self.view.mesh_menu,'tk_popup'):
            self.view.outliner_menu(SimpleNamespace(y=10,x_root=10,y_root=10))
        self.assertEqual(self.view.selected,self.eid)
        self.assertEqual(self.view.mesh_menu.entrycget(0,'state'),'normal')
        self.assertEqual(self.view.mesh_menu.entrycget(1,'state'),'disabled')

    def test_original_guard_blocks_import_before_any_asset_write(self):
        inspector=ObjectInspector(self.view,show=False)
        try:
            with patch('map_inspector.scene.map_meshes.store') as store:
                with self.assertRaises(ValueError): inspector.replace('not-read.obj')
                store.assert_not_called()
        finally: inspector.destroy()

    def test_undo_redo_and_new_edit_clear_redo(self):
        self.view.layout_name='test-alternate'
        original=copy.deepcopy(self.view.document)
        edit=copy.deepcopy(original)
        edit['meshes']={self.key:dict(sha256='a'*64,bundle='original',position=[5,5,5],yaw=45,scale=1)}
        self.view.apply_document(edit)
        self.assertTrue(self.view.unsaved)
        with patch.object(self.view,'load') as load:
            self.view.undo()
            self.assertEqual(self.view.document,original)
            self.assertFalse(self.view.unsaved)
            self.view.redo()
            self.assertEqual(self.view.document,edit)
            self.assertTrue(self.view.unsaved)
            self.view.undo()
            edit['meshes'][self.key]['yaw']=90
            self.view.apply_document(edit)
            self.assertEqual(self.view.redo_stack,[])
            self.assertTrue(load.called)

    def test_undo_after_save_marks_draft_dirty_again(self):
        self.view.layout_name='test-alternate'
        edit=copy.deepcopy(self.view.document)
        edit['meshes']={self.key:dict(sha256='a'*64,bundle='original',position=[5,5,5],yaw=45,scale=1)}
        self.view.apply_document(edit)
        with patch('level_viewport.scene_data.layouts.save'):
            self.assertTrue(self.view.save_layout())
        self.assertFalse(self.view.unsaved)
        with patch.object(self.view,'load'):
            self.view.undo(); self.assertTrue(self.view.unsaved)
            self.view.redo(); self.assertFalse(self.view.unsaved)

    def test_rename_uses_stable_id_and_history(self):
        self.view.layout_name='test-alternate'
        with patch('level_viewport.simpledialog.askstring',return_value='Water platform'),patch.object(self.view,'load'):
            self.view.rename_selected()
            self.assertEqual(self.view.document['labels'][self.eid],'Water platform')
            self.view.undo(); self.assertNotIn('labels',self.view.document)
            self.view.redo(); self.assertEqual(self.view.document['labels'][self.eid],'Water platform')

    def test_build_saves_and_selects_visible_alternate_before_launch(self):
        self.view.layout_name='water'
        self.view.unsaved=True
        calls=[]
        with patch('level_viewport.scene_data.layouts.save',side_effect=lambda *args:calls.append('save')), \
             patch('level_viewport.scene_data.layouts.choose',side_effect=lambda *args:calls.append('choose')), \
             patch('subprocess.Popen',side_effect=lambda *args,**kwargs:calls.append('build')):
            self.view.build_clean()
        self.assertEqual(calls,['save','choose','build'])
        self.assertFalse(self.view.unsaved)

    def test_cancel_save_prevents_build(self):
        self.view.unsaved=True
        with patch.object(self.view,'save_layout',return_value=False),patch('subprocess.Popen') as launch:
            self.view.build_clean()
            launch.assert_not_called()

    def test_alternate_import_refreshes_world_preserving_camera_and_selection(self):
        self.view.layout_name='test-alternate'
        self.view.camera.position=(123,456,789)
        changed=copy.deepcopy(self.scene)
        changed['faces'][0]['points'][1]=(25,0,0)
        with patch('map_inspector.filedialog.askopenfilename',return_value='replacement.obj'), \
             patch('map_inspector.scene.map_meshes.store',return_value='b'*64), \
             patch('map_inspector.scene.map_meshes.replacement_faces',return_value=[]), \
             patch('level_viewport.scene_data.load_room',side_effect=lambda *args,document: changed if document.get('meshes') else self.scene) as load:
            self.view.mesh_exchange('replace')
            deadline=time.monotonic()+2
            while self.view.scene is None and time.monotonic()<deadline:
                self.root.update(); time.sleep(.01)
            self.assertIsNotNone(self.view.scene)
            self.assertEqual(self.view.scene['faces'][0]['points'][1],(25,0,0))
            self.assertEqual(self.view.camera.position,(123,456,789))
            self.assertEqual(self.view.selected,self.eid)
            self.assertTrue(self.view.unsaved)
            self.assertEqual(self.view.document['meshes'][self.key]['bundle'],'b'*64)
            self.assertEqual(load.call_args.kwargs['document'],self.view.document)
            for action,expected in ((self.view.undo,(10,0,0)),(self.view.redo,(25,0,0))):
                action()
                deadline=time.monotonic()+2
                while self.view.scene is None and time.monotonic()<deadline:
                    self.root.update(); time.sleep(.01)
                self.assertEqual(self.view.scene['faces'][0]['points'][1],expected)
                self.assertEqual(self.view.selected,self.eid)



if __name__=='__main__': unittest.main()
