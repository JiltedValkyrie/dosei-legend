"""Source song gate, fairy rewards and refill are preserved by sprite import."""
import os
from pathlib import Path
import sys
import unittest
GAME=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(GAME/'tools'))
import child_fairy_sources as fairy
from child_route_effects import functions
OOT=Path(os.environ.get('DOSEI_OOT','D:/Workspace-Claude/game-decomps/n64/oot'))

@unittest.skipUnless((OOT/fairy.SOURCES[0]).exists(),'local decomp required')
class FairySource(unittest.TestCase):
    def test_source_reward_gate_and_refill(self):
        before=(OOT/fairy.SOURCES[0]).read_text(encoding='utf-8')
        after=fairy.adapt(fairy.SOURCES[0],before)
        old,new=functions(before),functions(after)
        for name in ('BgDyYoseizo_WaitSong','BgDyYoseizo_SetupCutscene','BgDyYoseizo_Reward_GiveReward',
                     'BgDyYoseizo_Revisit_RefillPlayerEnergy','BgDyYoseizo_Reward_WaitCutscene'):
            expected=old[name]
            import re
            expected=re.sub(r'this->skelAnime.curFrame \* (\d+)\.0f',r'(s32)this->skelAnime.curFrame * \1',expected)
            expected=re.sub(r'this->curAnimLastFrame \* (\d+)\.0f',r'(s32)this->curAnimLastFrame * \1',expected)
            self.assertEqual(expected,new[name],name)
        header=fairy.adapt(fairy.SOURCES[0][:-2]+'.h',(OOT/(fairy.SOURCES[0][:-2]+'.h')).read_text())
        self.assertIn('Vec3s* jointTable',header)
        self.assertNotIn('SkelAnime_InitFlex(',after)
        self.assertNotIn('SkelAnime_Draw',after)
        self.assertNotIn('Actor_TrackPlayer(',after)
    def test_beam_source_motion_and_no_vertex_writes(self):
        before=(OOT/fairy.SOURCES[1]).read_text(encoding='utf-8')
        after=fairy.adapt(fairy.SOURCES[1],before)
        old,new=functions(before),functions(after)
        for name in ('EnDyExtra_Init','EnDyExtra_Wait','EnDyExtra_Disappear','EnDyExtra_Update'):
            self.assertEqual(old[name],new[name])
        self.assertNotIn('vertices[',new['EnDyExtra_Draw'])
        self.assertIn('this->alphaFac * 255.0f',new['EnDyExtra_Draw'])

if __name__=='__main__':unittest.main()
