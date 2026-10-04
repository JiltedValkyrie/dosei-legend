"""Base-36 scene/room file names: Python tools and C runtime agree."""
from pathlib import Path
import re
import sys
import unittest
import collections
import json
import os
import shutil
import struct
import subprocess
import tempfile
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import asset_names


class AssetNames(unittest.TestCase):
    def test_single_digit_names_unchanged(self):
        self.assertEqual(asset_names.room_asset(1, 2, 'MSH'), 'S1R2.MSH')
        self.assertEqual(asset_names.scene_asset(0, 'COL'), 'S0.COL')

    def test_ten_plus_rooms_stay_8_3(self):
        self.assertEqual(asset_names.room_asset(3, 11, 'TEX'), 'S3RB.TEX')
        self.assertEqual(asset_names.room_asset(35, 35, 'RGB'), 'SZRZ.RGB')
        self.assertEqual(asset_names.scene_asset(10, 'SUR'), 'SA.SUR')

    def test_out_of_range_rejected(self):
        for bad in (-1, 36):
            with self.assertRaises(ValueError):
                asset_names.digit(bad)

    def test_c_header_matches(self):
        text = (ROOT / 'src/asset_names.h').read_text()
        self.assertIn('#define ASSET_ID_LIMIT 36u', text)
        self.assertIn("'A' + (value - 10u)", text)
        self.assertEqual(asset_names.LIMIT, 36)
        for name,value in vars(asset_names).items():
            if name.startswith('STORY_BANK_'):
                self.assertIn('#define %s %du' % (name,value),text)

    def test_story_names_cannot_overlap_any_gameplay_scene(self):
        gameplay={asset_names.room_asset(scene,room,'MSH') for scene in range(256) for room in range(36)}
        story={asset_names.room_asset(asset_names.STORY_BANK_BASE+scene,room,'MSH') for scene in range(36) for room in range(36)}
        self.assertFalse(gameplay & story)
        self.assertEqual(asset_names.room_asset(asset_names.STORY_BANK_NAVI,9,'MAP'),'C0R9.MAP')
        self.assertEqual(asset_names.room_asset(asset_names.STORY_BANK_PANORAMA,4,'MSH'),'C2R4.MSH')
        self.assertTrue(all(len(name.split('.')[0])<=8 for name in story))

    def test_production_c_names_match_virtual_and_gameplay_ids(self):
        gcc=shutil.which('gcc') or 'C:/msys64/mingw64/bin/gcc.exe'
        if not Path(gcc).exists():self.skipTest('host compiler required')
        rows=[(scene,room) for scene in (0,2,3,4,20,21,28,74,255,1024,1025,1026,1032) for room in (0,9,35)]
        source='#include "asset_names.h"\n#include <string.h>\nint main(void){char name[12];\n'
        for scene,room in rows:
            source+='if(!asset_scene_name(name,%d,%d,"MSH") || strcmp(name,"%s"))return 1;\n' % (scene,room,asset_names.room_asset(scene,room,'MSH'))
        source+='return 0;}\n'
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder);(path/'names.c').write_text(source)
            env=dict(os.environ,PATH=str(Path(gcc).parent)+os.pathsep+os.environ.get('PATH',''))
            subprocess.run([gcc,'-std=c99','-O2','-I'+str(ROOT/'src'),str(path/'names.c'),'-o',str(path/'names.exe')],check=True,env=env)
            subprocess.run([str(path/'names.exe')],check=True,env=env)

    def test_emerald_emitter_preserves_existing_real_scene_banks(self):
        import build_emerald_story as emerald
        with tempfile.TemporaryDirectory() as folder:
            out=Path(folder)
            original={asset_names.room_asset(scene,0,ext):b'gameplay-bank-'+bytes([scene])
                      for scene in (20,21,23,25,26,28) for ext in ('MSH','TEX')}
            for name,data in original.items():(out/name).write_bytes(data)
            def convert(oot,head,actor,folder,**kwargs):
                folder.mkdir(parents=True,exist_ok=True)
                (folder/'texture_manifest.json').write_text(json.dumps(dict(faces=[])))
                return None,[],[],collections.OrderedDict()
            with mock.patch.object(emerald.hybrid,'convert',side_effect=convert), \
                 mock.patch.object(emerald.opening,'forest_bank',return_value=([],[],collections.OrderedDict())), \
                 mock.patch.object(emerald.cs,'read_cutscene',return_value=dict(track=[])), \
                 mock.patch.object(emerald,'static_mesh'):
                rows=emerald.emit(None,None,out,{}, {},[],lambda *args:None)
            self.assertEqual(len(rows),6)
            self.assertTrue(all(row['scene']>=asset_names.STORY_BANK_BASE for row in rows))
            for name,data in original.items():self.assertEqual((out/name).read_bytes(),data,name)
            for row in rows:
                self.assertEqual((out/asset_names.room_asset(row['scene'],0,'MSH')).read_bytes()[:4],b'KRM1')

    def test_runtime_loaders_use_helper(self):
        for name in ('kokiri_sgl.c', 'scene_flow.c'):
            text = (ROOT / 'src' / name).read_text()
            self.assertNotRegex(text, r"(scene|room) > 9")
            self.assertIn('asset_scene_name', text)


if __name__ == '__main__':
    unittest.main()
