"""Source-reachable child camera admission and scene-local recipe closure."""
import os
from pathlib import Path
import re
import sys
import unittest

GAME=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(GAME/'tools'))
import onepoint_sources as cameras
import scene_pack_actors

OOT=Path(os.environ.get('DOSEI_OOT',str(GAME.parents[1]/'game-decomps/n64/oot')))
if not OOT.exists():
    OOT=Path('D:/Workspace-Claude/game-decomps/n64/oot')


@unittest.skipUnless(OOT.exists(),'local source decomp unavailable')
class SourceCameraClosure(unittest.TestCase):
    def test_child_actor_literal_calls_all_have_exact_recipes(self):
        excluded={('Door_Warp1',9704),('Door_Warp1',9705)} # Ruto/adult warp setup
        for name in scene_pack_actors.ALL_ACTORS:
            source=(OOT/scene_pack_actors.source(name)).read_text(encoding='utf-8')
            ids={int(m.group(1),0) for m in re.finditer(
                r'OnePointCutscene_Init\(\s*play\s*,\s*(0x[0-9a-fA-F]+|\d+)',source)}
            for ident in ids:
                self.assertTrue((name,ident) in excluded or ident in cameras.scripts([name],OOT),
                                f'{name} requests unsupported OnePoint {ident}')
            if 'OnePointCutscene_Attention' in source:
                self.assertIn(5010,cameras.scripts([name],OOT),name)

    def test_fixed_shots_do_not_swallow_following_source_case(self):
        source=(OOT/'src/code/z_onepointdemo.c').read_text(encoding='utf-8')
        bomb=cameras.case(source,4180)
        self.assertIn('CAM_SET_FREE2',bomb)
        self.assertIn('-1881.0f',bomb)
        self.assertNotIn('D_8012151C',bomb) # 3040's table follows the unbraced 4180 case
        self.assertIn('case 3065:',cameras.case(source,3380))

    def test_pack_contains_only_reachable_setup_and_required_engines(self):
        owl=cameras.pack_source(OOT,['En_Owl'])
        self.assertIn('case 8700:',owl)
        self.assertNotIn('case 3050:',owl)
        self.assertNotIn('s32 Camera_Demo5(',owl)
        cavern=cameras.pack_source(OOT,['Bg_Ddan_Kd','Obj_Switch','En_Box'])
        for ident in (1020,3050,4500,5010): self.assertIn(f'case {ident}:',cavern)
        for engine in ('Camera_Unique9','Camera_Unique6','Camera_Demo9','Camera_Demo5'):
            self.assertIn('s32 '+engine+'(',cavern)
        self.assertNotIn('case 8700:',cavern)
        self.assertIn('oot_pack_onepoint_step',cavern)


if __name__=='__main__': unittest.main()
