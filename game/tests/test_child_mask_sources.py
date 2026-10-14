"""Original mask-customer transactions and offline attachment coverage."""
import os
from pathlib import Path
import re
import sys
import unittest
import test_graphics_backend as graphics
from test_child_route_npcs import function
GAME=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(GAME/'tools'))
import child_mask_sources as masks
import build_child_mask_sprites as bake
import build_link_model as link
OOT=Path(os.environ.get('DOSEI_OOT','D:/Workspace-Claude/game-decomps/n64/oot'))

@unittest.skipUnless((OOT/masks.SOURCES[0]).exists(),'local decomp required')
class ChildMaskSources(unittest.TestCase):
    run_c=graphics.GraphicsBackend.run_c
    def test_source_transactions_and_no_runtime_character_pose(self):
        original_functions={'En_Cs':('EnCs_GetTalkState','EnCs_GetTextId'),
            'En_Mm':('func_80AADAA0','EnMm_GetTextId'),
            'En_Skj':('EnSkj_TakeMask','EnSkj_AskForMask','EnSkj_SariasSongShortStumpUpdate'),
            'En_Skjneedle':('EnSkjneedle_Update',)}
        for name,rel in zip(masks.ACTORS,masks.SOURCES):
            src=(OOT/rel).read_text(encoding='utf8');adapted=masks.adapt(rel,src)
            self.assertNotRegex(adapted,r'\b(?:SkelAnime_Init\w*|SkelAnime_Draw\w*|Actor_TrackPlayer|Npc_TrackPoint)\(')
            for fn in original_functions[name]:self.assertEqual(function(src,fn),function(adapted,fn))
            header=masks.adapt(rel[:-2]+'.h',(OOT/(rel[:-2]+'.h')).read_text())
            self.assertNotRegex(header,r'Vec3s (?:jointTable|morphTable)\[')
            self.assertNotRegex(header,r'MtxF (?:spookyMaskMtx|unk_208);')

    def test_all_four_sold_masks_have_source_attached_geometry(self):
        keep=link.read_object(OOT,'gameplay_keep')
        for obj,limb in (('object_sd',15),('object_cs',14),('object_mm',14),('object_skj',10)):
            faces=bake.attachment(OOT,None,obj,limb,keep)
            self.assertGreater(len(faces),8,obj)
            self.assertTrue(all(set(f['vertex_limbs'])=={limb} for f in faces),obj)
            self.assertFalse(bake.attachment(OOT,None,obj,0,keep))

    def test_spooky_and_skull_sales_require_message_advance(self):
        cs=(OOT/masks.SOURCES[0]).read_text(encoding='utf8');skj=(OOT/masks.SOURCES[2]).read_text(encoding='utf8')
        self.run_c(r'''
#include <assert.h>
typedef int s32;typedef struct{int textId;}Actor;
typedef struct{struct{int state,choiceIndex;}msgCtx;}PlayState;
typedef struct{Actor actor;int currentAnimIndex;}EnCs;
typedef struct{Actor actor;int done;}EnSkj;
enum{TEXT_STATE_CHOICE,TEXT_STATE_DONE,TEXT_STATE_NONE,TEXT_STATE_DONE_HAS_NEXT,TEXT_STATE_CLOSING,
TEXT_STATE_DONE_FADING,TEXT_STATE_EVENT,ENCS_ANIM_3=3,ENCS_ANIM_1=1,ITEMGETINF_3A=58,ITEMGETINF_39=57,ITEM_SOLD_OUT=44};
static int advance,rupees,grants,unsets;static unsigned long long flags;
#define SET_ITEMGETINF(x) (flags|=1ull<<(x))
#define Message_GetState(c) ((c)->state)
static int Message_ShouldAdvance(PlayState*p){return advance;}
static void EnCs_ChangeAnim(EnCs*a,int anim,int*out){*out=anim;}
static void Player_UnsetMask(PlayState*p){unsets++;}
static void Item_Give(PlayState*p,int id){assert(id==44);grants++;}
static void Rupees_ChangeBy(int n){rupees+=n;}
static void EnSkj_SetNaviId(EnSkj*a){}
static void Message_ContinueTextbox(PlayState*p,int id){p->msgCtx.state=TEXT_STATE_NONE;}
static void EnSkj_SetupWaitForMaskTextClear(EnSkj*a){a->done=1;}
'''+function(cs,'EnCs_GetTalkState')+function(skj,'EnSkj_TakeMask')+r'''
int main(void){PlayState p={{TEXT_STATE_DONE,0}};EnCs child={{0x2026},0};EnSkj skull={0};
assert(EnCs_GetTalkState(&child,&p)==1&&!grants);advance=1;
assert(EnCs_GetTalkState(&child,&p)==2&&rupees==30&&grants==1&&unsets==1);
assert(flags&(1ull<<58));assert(EnCs_GetTalkState(&child,&p)==0&&grants==1);
advance=0;EnSkj_TakeMask(&skull,&p);assert(!skull.done);advance=1;EnSkj_TakeMask(&skull,&p);
assert(skull.done&&rupees==40&&grants==2&&unsets==2&&(flags&(1ull<<57)));
EnSkj_TakeMask(&skull,&p);assert(grants==2);return 0;}
''')

if __name__=='__main__':unittest.main()
