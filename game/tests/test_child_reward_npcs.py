"""Execute source reward handshakes and deterministic prize bag boundaries."""
import os
from pathlib import Path
import re
import sys
import unittest
import test_graphics_backend as graphics
from test_child_route_npcs import function
GAME=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(GAME/'tools'))
import child_reward_npcs as reward
import build_child_reward_sprites as baker
OOT=Path(os.environ.get('DOSEI_OOT','D:/Workspace-Claude/game-decomps/n64/oot'))

@unittest.skipUnless((OOT/reward.SOURCES[0]).exists(),'local decomp required')
class ChildRewardNpcs(unittest.TestCase):
    run_c=graphics.GraphicsBackend.run_c

    def test_original_rewards_and_no_runtime_pose(self):
        unchanged={'En_Dog':('EnDog_Init','EnDog_FollowPlayer','EnDog_FaceLink'),
            'En_Gm':('EnGm_ProcessChoiceIndex','func_80A3DF00','func_80A3DF60'),
            'En_Ssh':('EnSsh_CheckHitFront','EnSsh_CheckHitBack','EnSsh_CollisionCheck','EnSsh_Talk'),
            'En_Sth':('EnSth_GivePlayerItem','EnSth_GiveReward','EnSth_RewardUnobtainedTalk'),
            'En_Tk':('EnTk_ChooseReward','EnTk_UpdateTalkState')}
        for name,rel in zip(reward.ACTORS,reward.SOURCES):
            src=(OOT/rel).read_text(encoding='utf8');changed=reward.adapt(rel,src)
            self.assertNotRegex(changed,r'\b(?:SkelAnime_Draw\w*|SkelAnime_Init\w*|Collider_UpdateSpheres|Actor_TrackPlayer)\(')
            head=reward.adapt(rel[:-2]+'.h',(OOT/(rel[:-2]+'.h')).read_text())
            self.assertNotRegex(head,r'Vec3s (?:jointTable|morphTable)\[')
            for fn in unchanged[name]:
                original=function(src,fn).replace('SkelAnime_InitFlex(', 'OotCore_SpriteInitFlex(')
                self.assertEqual(original,function(changed,fn),fn)
        self.assertEqual(baker.anchors(OOT),(GAME/'oot-core/include/child_reward_anchors.inc').read_text())

    def test_token_wallet_choice_and_parent_acknowledgement(self):
        text=(OOT/reward.SOURCES[3]).read_text(encoding='utf8')
        self.run_c(r'''
#include <assert.h>
#include <stddef.h>
typedef unsigned short u16;
typedef struct{int params;void*parent;} Actor;typedef struct{int unused;} PlayState;
typedef struct EnSth{Actor actor;int eventFlag;void(*action)(struct EnSth*,PlayState*);}EnSth;
enum{GI_WALLET_ADULT=56,GI_WALLET_GIANT=57,UPG_WALLET=0,EVENTCHKINF_INDEX_SKULLTULA_REWARD=13};
static int wallet,offered,offers;static u16 sGetItemIds[]={42,56,55,57,64,62};
static struct{struct{struct{unsigned eventChkInf[14];}info;}save;}gSaveContext;
#define CUR_UPG_VALUE(x) wallet
static int Actor_HasParent(Actor*a,PlayState*p){return a->parent!=NULL;}
static void Actor_OfferGetItem(Actor*a,PlayState*p,int item,float xz,float y){offered=item;++offers;}
static void EnSth_RewardObtainedTalk(EnSth*a,PlayState*p){}
static void EnSth_SetupAction(EnSth*a,void(*f)(EnSth*,PlayState*)){a->action=f;}
static void EnSth_FacePlayer(EnSth*a,PlayState*p){}
'''+function(text,'EnSth_GivePlayerItem')+function(text,'EnSth_GiveReward')+r'''
int main(void){PlayState p={0};EnSth a={0};a.eventFlag=4;
for(int param=1;param<=3;param+=2){a.actor.params=param;wallet=0;EnSth_GivePlayerItem(&a,&p);assert(offered==56);
wallet=1;EnSth_GivePlayerItem(&a,&p);assert(offered==57);}
a.actor.params=5;EnSth_GiveReward(&a,&p);assert(offered==62&&!gSaveContext.save.info.eventChkInf[13]);
int before=offers;a.actor.parent=&p;EnSth_GiveReward(&a,&p);assert(offers==before&&a.actor.parent==NULL);
assert(gSaveContext.save.info.eventChkInf[13]==4&&a.action==EnSth_RewardObtainedTalk);return 0;}
''')

    def test_dampe_prize_distribution_exhaustion_and_reset(self):
        text=(OOT/reward.SOURCES[4]).read_text(encoding='utf8')
        self.run_c(r'''
#include <assert.h>
typedef int s32;typedef float f32;typedef struct{int rewardCount[4];}EnTk;
static float luck;static float Rand_ZeroOne(void){return luck;}
'''+function(text,'EnTk_ChooseReward')+r'''
int main(void){EnTk a={0};luck=.95f;assert(EnTk_ChooseReward(&a)==3);
for(int i=0;i<8;i++)assert(EnTk_ChooseReward(&a)==0);
for(int i=0;i<4;i++)assert(EnTk_ChooseReward(&a)==1);
for(int i=0;i<2;i++)assert(EnTk_ChooseReward(&a)==2);
assert(EnTk_ChooseReward(&a)==0&&a.rewardCount[0]==1&&!a.rewardCount[3]);
EnTk b={0};luck=.399f;assert(EnTk_ChooseReward(&b)==0);luck=.4f;assert(EnTk_ChooseReward(&b)==1);
luck=.7f;assert(EnTk_ChooseReward(&b)==1);luck=.7001f;assert(EnTk_ChooseReward(&b)==2);luck=.9f;assert(EnTk_ChooseReward(&b)==2);
luck=.9001f;assert(EnTk_ChooseReward(&b)==3);return 0;}
''')

if __name__=='__main__':unittest.main()
