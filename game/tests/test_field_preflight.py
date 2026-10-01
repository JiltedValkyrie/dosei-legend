"""M7 source assets: correct skeletons, bounded texture reads and story tracks."""
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import build_field_owl as owl
import build_field_story_preflight as story
import build_kokiri_scene as source
import build_cutscenes as cs
import build_cutscene_audio as music

OOT=Path('D:/Workspace-Claude/game-decomps/n64/oot')


class TextureBounds(unittest.TestCase):
    def test_explicit_source_image_bounds_do_not_read_large_clamp_rectangle(self):
        dl=source.DisplayLists(b'',b'')
        dl.segments={6: bytes.fromhex('ffff')*256}
        dl.texture_on=True;dl.texture_tile=0
        dl.tiles[0]=dict(fmt=0,size=2,line=4,tmem=0,palette=0,
            cmt=2,maskt=4,shiftt=0,cms=2,masks=4,shifts=0,
            uls=0,ult=0,lrs=2556,lrt=764)
        dl.images[0]=(0x06000000,1,0,2)
        with self.assertRaises(AssertionError):dl.texture()
        dl.texture_dimensions={0x06000000:(16,16)}
        tex=dl.texture()
        self.assertEqual((tex['width'],tex['height']),(16,16))
        self.assertEqual(tex['colors'],[(255,255,255,255)]*256)
        self.assertEqual(dl.tiles[0]['lrs'],2556) # original clamp state retained


@unittest.skipUnless(OOT.is_dir(),'original source required')
class OriginalAssets(unittest.TestCase):
    def test_perch_and_flight_use_different_original_skeletons(self):
        with tempfile.TemporaryDirectory() as folder:
            result=owl.build(OOT,None,Path(folder))
            perch,flight=result['models']
            self.assertEqual((perch['vertices'],perch['polygons']),(240,400))
            self.assertEqual((flight['vertices'],flight['polygons']),(301,520))
            self.assertEqual(perch['clips'],{'gOwlPerchAnim':(0,20)})
            self.assertEqual(flight['clips']['gOwlTakeoffAnim'],(15,60))
            self.assertEqual(flight['clips']['gOwlGlideAnim'],(90,2))
            self.assertEqual(sum(m['texture_bytes'] for m in result['models']),30920)
            self.assertFalse(result['runtime_registered'])

    def test_story_tracks_keep_source_handoff_and_expose_missing_cues(self):
        with tempfile.TemporaryDirectory() as folder:
            result=story.build(OOT,Path(folder))
            bridge,field=result['tracks']
            self.assertEqual(bridge['destination']['dest'],'CS_DEST_HYRULE_FIELD_FROM_FAIRY_OCARINA')
            self.assertEqual(bridge['destination']['start'],1130)
            self.assertEqual(field['stop_frame'],330)
            self.assertEqual(field['scene'],'FIELD_GAMEPLAY') # never nightmare clearance
            self.assertEqual(bridge['unmapped_player_cues'],[])
            self.assertEqual(bridge['unmapped_music'],[])
            self.assertEqual((Path(folder)/'FIELDCS.BIN').stat().st_size,331*14)
            self.assertFalse(result['runtime_registered'])
            live=cs.read_cutscene(dict(key='FIELD',scene='FIELD_GAMEPLAY',scene_bgm=None,
                path=OOT/'extracted/ntsc-1.2/assets/scenes/overworld/spot00/gHyruleFieldIntroCs.csdata.inc.c'))
            self.assertTrue(any(e['kind']=='CS_MISC_SHOW_TITLE_CARD' for e in live['misc']))

    def test_owl_neutral_bend_and_non_neutral_rejection(self):
        path=OOT/'extracted/ntsc-1.2/assets/audio/sequences/seq_90.seq'
        label=music.loop_label_of(path)
        notes,*_=music.audio.interpret(path,label or 'SEQ_0000',stop_at_loop=label is not None)
        self.assertTrue(notes)
        with tempfile.TemporaryDirectory() as folder:
            altered=Path(folder)/'bend.seq'
            text=path.read_text()
            self.assertIn('bend        0',text)
            altered.write_text(text.replace('bend        0','bend        1'))
            with self.assertRaisesRegex(ValueError,'pitch automation'):
                music.audio.interpret(altered,label or 'SEQ_0000',stop_at_loop=label is not None)


if __name__=='__main__':unittest.main()
