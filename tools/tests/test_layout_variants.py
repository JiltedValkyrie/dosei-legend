import copy
import hashlib
import json
import os
from pathlib import Path
import struct
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'game/tools'))
import layout_variants as layouts
import room_imports


class LayoutTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.game = Path(self.temp.name)
        self.raw = struct.pack('>BBHI',1,1,0,0x03000010)+bytes([0x14])+bytes(7)
        self.raw += struct.pack('>H6hH',0xA141,1,2,3,4,5,6,0xBEEF)
        self.doc = layouts.empty()
        self.doc['rooms']['spot04_room_0'] = {
            'sha256':hashlib.sha256(self.raw).hexdigest(),
            'actors':{'0':{'actor_id':0x141,'position':[101,102,103],'yaw':-200}}}

    def test_patch_preserves_original_identity_flags_other_rotations_params(self):
        source = {'spot04_room_0':self.raw,'spot04_scene':b'scene'}
        modified = layouts.apply(source,self.doc)
        self.assertEqual(source['spot04_room_0'],self.raw)
        self.assertEqual(struct.unpack_from('>H6hH',modified['spot04_room_0'],16),
                         (0xA141,101,102,103,4,-200,6,0xBEEF))
        self.assertEqual(modified['spot04_scene'],b'scene')
        self.assertEqual(layouts.apply(source,layouts.empty()),source)

    def test_stale_source_and_wrong_identity_fail(self):
        with self.assertRaises(ValueError): layouts.apply({'spot04_room_0':self.raw+b'x'},self.doc)
        self.doc['rooms']['spot04_room_0']['actors']['0']['actor_id'] = 0x125
        with self.assertRaises(ValueError): layouts.apply({'spot04_room_0':self.raw},self.doc)

    def test_grass_facing_cannot_be_silently_ignored_by_bake(self):
        raw = self.raw[:16]+struct.pack('>H',0xA125)+self.raw[18:]
        record = self.doc['rooms']['spot04_room_0']
        record['sha256'] = hashlib.sha256(raw).hexdigest()
        record['actors']['0']['actor_id'] = 0x125
        with self.assertRaises(ValueError): layouts.apply({'spot04_room_0':raw},self.doc)
        record['actors']['0']['yaw'] = 5
        self.assertNotEqual(layouts.apply({'spot04_room_0':raw},self.doc)['spot04_room_0'],raw)

    def test_ranges_and_unsupported_actor_fields_fail(self):
        for field,value in (('position',[32768,0,0]),('yaw',1.5),('actor_id',0x146),('params',3)):
            doc = copy.deepcopy(self.doc)
            doc['rooms']['spot04_room_0']['actors']['0'][field] = value
            with self.assertRaises(ValueError): layouts.validate(doc)

    def test_original_is_immutable_and_names_cannot_escape(self):
        for name in ('original','../escape','A name',''):
            with self.assertRaises(ValueError): layouts.save(name,self.doc,self.game)
        self.assertEqual(list(self.game.iterdir()),[])

    def test_save_select_reset_keeps_saved_alternates(self):
        layouts.save('garden',self.doc,self.game)
        self.assertIsNone(layouts.selection(self.game))
        layouts.choose('garden',self.game)
        self.assertEqual(layouts.selection(self.game),'garden')
        layouts.choose('original',self.game)
        self.assertEqual(layouts.load('original',self.game),layouts.empty())
        self.assertEqual(layouts.load('garden',self.game),self.doc)
        self.assertEqual(layouts.names(self.game),['garden'])

    def test_missing_selection_does_not_replace_previous(self):
        layouts.choose('original',self.game)
        with self.assertRaises(FileNotFoundError): layouts.choose('missing',self.game)
        self.assertEqual(layouts.selection(self.game),'original')

    def test_snapshot_does_not_follow_later_gui_selection(self):
        snapshot = self.game/'snapshot.json'
        layouts.atomic_json(snapshot,{'layout':'garden','document':self.doc})
        layouts.choose('original',self.game)
        with patch.dict(os.environ,{'DOSEI_LAYOUT_SNAPSHOT':str(snapshot)}):
            self.assertEqual(layouts.build_document(self.game),self.doc)

    def test_original_build_ignores_legacy_mesh_selection(self):
        with patch.object(layouts,'build_document',return_value=layouts.empty()):
            with patch.dict(os.environ,{'ROOM_IMPORTS':str(self.game/'does-not-exist.json')}):
                self.assertIsNone(room_imports.selected('spot04',0))

    def test_atomic_save_failure_retains_previous_variant(self):
        layouts.save('garden',self.doc,self.game)
        with patch.object(layouts.os,'replace',side_effect=OSError('locked')):
            with self.assertRaises(OSError): layouts.save('garden',layouts.empty(),self.game)
        self.assertEqual(layouts.load('garden',self.game),self.doc)
        self.assertEqual(len(list((layouts.directory(self.game)/'variants').iterdir())),1)


if __name__=='__main__': unittest.main()
