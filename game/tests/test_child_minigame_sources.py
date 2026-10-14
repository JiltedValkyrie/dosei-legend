"""Execute original child minigame fees/rewards and exported presentation gates."""
import os
from pathlib import Path
import sys
import unittest
import test_graphics_backend as graphics
from test_child_route_npcs import function

GAME = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(GAME / 'tools'))
import child_minigame_sources as games
OOT = Path(os.environ.get('DOSEI_OOT', 'D:/Workspace-Claude/game-decomps/n64/oot'))


@unittest.skipUnless((OOT / games.SOURCES[0]).exists(), 'local decomp required')
class ChildMinigames(unittest.TestCase):
    run_c = graphics.GraphicsBackend.run_c

    def source(self, actor):
        return (OOT / games.SOURCES[games.ACTORS.index(actor)]).read_text(encoding='utf8')

    def test_source_actions_and_contact_managers_preserved(self):
        for name, rel in zip(games.ACTORS, games.SOURCES):
            original = self.source(name)
            adapted = games.adapt(rel, original)
            # Only presentation has changed. Every source action survives byte for byte.
            import re
            for fn in re.findall(r'^void (\w+)\([^;{}]*\) \{', original, re.M):
                if 'Draw' in fn or fn.endswith('_Init') or fn.endswith('_Update'):
                    continue
                self.assertEqual(function(original, fn), function(adapted, fn), fn)
            if name in games.NPC_ACTORS:
                header = games.adapt(rel[:-2] + '.h', (OOT / (rel[:-2] + '.h')).read_text())
                self.assertNotRegex(header, r'Vec3s (?:jointTable|morphTable)\[')
                self.assertNotRegex(adapted, r'\b(?:SkelAnime_Init\w*|SkelAnime_Draw\w*|Actor_TrackPlayer)\(')

    def test_original_fees_reject_poor_or_declining_players(self):
        bodies = ''.join(function(self.source(a), fn) for a, fn in (
            ('En_Syateki_Man', 'EnSyatekiMan_Talk'),
            ('En_Bom_Bowl_Man', 'EnBomBowlMan_WaitPlayAnswer'),
            ('En_Takara_Man', 'func_80B17934')))
        self.run_c(r'''
#include <assert.h>
#include <stddef.h>
typedef short s16;
typedef struct { int textId; void* parent; } Actor;
typedef struct { struct {int state,choiceIndex;} msgCtx; int shootingGalleryStatus,bombchuBowlingStatus; } PlayState;
typedef struct EnSyatekiMan { Actor actor; int skelAnime,cameraHold,numTextBox,textIdx;
 void(*actionFunc)(struct EnSyatekiMan*,PlayState*); } EnSyatekiMan;
typedef struct EnBomBowlMan { Actor actor; int skelAnime,waitMessageState,gameStartStatus,wallsState[2],hasPlayedBefore,isAskingToPlayAgain;
 void(*actionFunc)(struct EnBomBowlMan*,PlayState*); } EnBomBowlMan;
typedef struct EnTakaraMan { Actor actor; int dialogState,unk_214;
 void(*actionFunc)(struct EnTakaraMan*,PlayState*); } EnTakaraMan;
enum { SYATEKI_TEXT_CHOICE,SYATEKI_TEXT_START_GAME,SYATEKI_TEXT_NO_RUPEES,SYATEKI_TEXT_REFUSE,
 TEXT_STATE_EVENT=7, EN_BOM_BOWL_MAN_GAME_START_STATUS_PAID=1,EN_BOM_BOWL_MAN_WALL_STATE_STANDING=0,
 CAM_ID_MAIN=0,PLAYER_CSACTION_8=8,GI_DOOR_KEY=0x71 };
static int sTextIds[]={0x2b,0x2e,0xc8,0x2d},sTextBoxCount[]={4,7,7,7};
static struct { struct { struct { struct {int rupees;}playerData;}info;}save;}gSaveContext;
static int advance,charges,offers,offered,switches,cameras;
#define Message_GetState(c) ((c)->state)
#define false 0
static int Message_ShouldAdvance(PlayState*p){return advance;}
static void SkelAnime_Update(int*a){}
static void Rupees_ChangeBy(int n){gSaveContext.save.info.playerData.rupees+=n;charges++;}
static void Message_CloseTextbox(PlayState*p){}
static void Message_ContinueTextbox(PlayState*p,int id){}
static void Flags_SetSwitch(PlayState*p,int id){assert(id==0x38);switches++;}
static void OnePointCutscene_Init(PlayState*p,int id,int duration,void*a,int cam){assert(id==8010);cameras++;}
static void Player_SetCsActionWithHaltedActors(PlayState*p,void*a,int action){}
static void Actor_OfferGetItem(Actor*a,PlayState*p,int item,float x,float y){offers++;offered=item;}
static void EnSyatekiMan_SetupIdle(EnSyatekiMan*a,PlayState*p){}
static void EnSyatekiMan_StartGame(EnSyatekiMan*a,PlayState*p){}
static void EnSyatekiMan_StopTalk(EnSyatekiMan*a,PlayState*p){}
static void EnBomBowlMan_Talking(EnBomBowlMan*a,PlayState*p){}
static void EnBomBowlMan_WaitToShowReward(EnBomBowlMan*a,PlayState*p){}
static void func_80B17A6C(EnTakaraMan*a,PlayState*p){}
static void func_80B17B14(EnTakaraMan*a,PlayState*p){}
''' + bodies + r'''
int main(void){ PlayState p={{4,0}};EnSyatekiMan s={0};EnBomBowlMan b={0};EnTakaraMan t={0};
s.numTextBox=4;gSaveContext.save.info.playerData.rupees=20;
EnSyatekiMan_Talk(&s,&p);assert(!charges);advance=1;gSaveContext.save.info.playerData.rupees=19;
EnSyatekiMan_Talk(&s,&p);assert(!charges&&s.actionFunc==EnSyatekiMan_StopTalk);
s.textIdx=0;s.numTextBox=4;gSaveContext.save.info.playerData.rupees=20;
EnSyatekiMan_Talk(&s,&p);assert(charges==1&&!gSaveContext.save.info.playerData.rupees&&s.actionFunc==EnSyatekiMan_StartGame);
s.textIdx=0;s.numTextBox=4;p.msgCtx.choiceIndex=1;gSaveContext.save.info.playerData.rupees=99;
EnSyatekiMan_Talk(&s,&p);assert(charges==1&&gSaveContext.save.info.playerData.rupees==99);
p.msgCtx.choiceIndex=0;b.waitMessageState=4;gSaveContext.save.info.playerData.rupees=29;
EnBomBowlMan_WaitPlayAnswer(&b,&p);assert(charges==1&&!p.bombchuBowlingStatus&&!switches);
b.waitMessageState=4;gSaveContext.save.info.playerData.rupees=30;
EnBomBowlMan_WaitPlayAnswer(&b,&p);assert(charges==2&&!gSaveContext.save.info.playerData.rupees);
assert(p.bombchuBowlingStatus==10&&switches==1&&b.gameStartStatus==1&&b.actionFunc==EnBomBowlMan_Talking);
b.waitMessageState=4;b.hasPlayedBefore=1;gSaveContext.save.info.playerData.rupees=40;
EnBomBowlMan_WaitPlayAnswer(&b,&p);assert(charges==3&&cameras==1&&b.actionFunc==EnBomBowlMan_WaitToShowReward);
t.dialogState=4;gSaveContext.save.info.playerData.rupees=9;func_80B17934(&t,&p);assert(!offers&&charges==3);
t.dialogState=4;gSaveContext.save.info.playerData.rupees=10;func_80B17934(&t,&p);
assert(offers==1&&offered==0x71&&charges==4&&t.unk_214&&t.actionFunc==func_80B17A6C);
return 0;}
''')

    def test_bowling_bag_capacity_and_parent_reward_handshake(self):
        source = self.source('En_Bom_Bowl_Pit')
        self.run_c(r'''
#include <assert.h>
#include <stddef.h>
typedef struct {void*parent;}Actor;typedef struct {int stateFlags1;}Player;
typedef struct {struct{int state;}msgCtx;Player player;}PlayState;
typedef struct EnBomBowlPit {Actor actor;int rewardGetItemId,reward,hasRewardFinishedAppearing,rewardState;
 void(*actionFunc)(struct EnBomBowlPit*,PlayState*);}EnBomBowlPit;
enum{GI_BOMB_BAG_30=1,GI_BOMB_BAG_40,GI_HEART_PIECE,UPG_BOMB_BAG,PLAYER_STATE1_29=1,
 PLAYER_CSACTION_7=7,TEXT_STATE_DONE=6,EN_BOM_BOWL_PIT_REWARD_STATE_REWARD_GIVEN=2};
static int sGetItemIdRewards[]={GI_BOMB_BAG_30,GI_HEART_PIECE};
static struct{int healthAccumulator;}gSaveContext;static int cap,offers,offered,advance;
#define GET_PLAYER(p) (&(p)->player)
#define CUR_CAPACITY(u) cap
#define Message_GetState(c) ((c)->state)
#define PRINTF(...) ((void)0)
#define false 0
static int Message_ShouldAdvance(PlayState*p){return advance;}
static void Player_SetCsActionWithHaltedActors(PlayState*p,void*a,int act){}
static int Actor_HasParent(Actor*a,PlayState*p){return a->parent!=NULL;}
static void Actor_OfferGetItem(Actor*a,PlayState*p,int item,float x,float y){assert(!(p->player.stateFlags1&1));offers++;offered=item;}
static void EnBomBowlPit_WaitGameStarted(EnBomBowlPit*a,PlayState*p){}
void EnBomBowlPit_WaitRewardGiven(EnBomBowlPit*a,PlayState*p);
void EnBomBowlPit_WaitRewardText(EnBomBowlPit*a,PlayState*p);
''' + ''.join(function(source, fn) for fn in ('EnBomBowlPit_GiveReward', 'EnBomBowlPit_WaitRewardGiven', 'EnBomBowlPit_WaitRewardText')) + r'''
int main(void){PlayState p={{6},{0}};EnBomBowlPit a={0};cap=20;
EnBomBowlPit_GiveReward(&a,&p);assert(offered==GI_BOMB_BAG_30&&offers==1&&p.player.stateFlags1==1);
cap=30;EnBomBowlPit_GiveReward(&a,&p);assert(offered==GI_BOMB_BAG_40&&offers==2);
a.actor.parent=&p;EnBomBowlPit_WaitRewardGiven(&a,&p);assert(offers==2&&a.actionFunc==EnBomBowlPit_WaitRewardText);
a.rewardGetItemId=GI_HEART_PIECE;a.hasRewardFinishedAppearing=1;
EnBomBowlPit_WaitRewardText(&a,&p);assert(!a.rewardState&&!gSaveContext.healthAccumulator);
advance=1;EnBomBowlPit_WaitRewardText(&a,&p);assert(a.rewardState==2&&!a.hasRewardFinishedAppearing);
assert(gSaveContext.healthAccumulator==0x140&&a.actionFunc==EnBomBowlPit_WaitGameStarted);return 0;}
''')

    def test_item_atlas_gates_source_visibility_lens_and_reward_identity(self):
        view=(GAME/'oot-core/include/child_minigame_views.inc').read_text().replace('*v = {};','*v = (OotCoreNpcView){0};')
        self.run_c(r'''
#include <assert.h>
#include <stddef.h>
typedef unsigned char u8;typedef unsigned short u16;typedef unsigned u32;typedef int s32;
typedef struct {float x,y,z;}Vec;
typedef struct {int id,params;void*draw;Vec scale;struct{Vec pos;}world;struct{float yOffset;struct{int y;}rot;}shape;}Actor;
typedef struct {struct{int lensActive;}actorCtx;}PlayState;
typedef struct {Actor actor;int giDrawId,type;}EnExItem;
typedef struct {Actor actor;int giDrawId;}ItemEtcetera;
typedef struct {Actor actor;int invisible,colorIdx;}EnExRuppy;
typedef struct {Actor actor;int type,broken,colorIdx;}EnGSwitch;
typedef struct {int id,params,object,anim,alpha,flags,x,y,z,yaw,scale_x,scale_y;}OotCoreNpcView;
enum {ACTOR_EN_EX_ITEM=1,ACTOR_ITEM_ETCETERA,ACTOR_EN_EX_RUPPY,ACTOR_EN_G_SWITCH,
 ENGSWITCH_ARCHERY_POT=2,ENGSWITCH_SILVER_TRACKER=0,
 EXITEM_HEART_PIECE_BOWLING=1,EXITEM_HEART_PIECE_COUNTER=8,EXITEM_SMALL_KEY_CHEST=12,
 EXITEM_MAGIC_FIRE=15,EXITEM_MAGIC_WIND,EXITEM_MAGIC_DARK,
 GID_HEART_PIECE=18,GID_SMALL_KEY=1,GID_DINS_FIRE=21,GID_FARORES_WIND,GID_NAYRUS_LOVE,
 GID_RUPEE_GREEN=40,GID_RUPEE_BLUE,GID_RUPEE_RED,GID_RUPEE_PURPLE,GID_RUPEE_GOLD,
 ITEM_ETC_RUPEE_GREEN_CHEST_GAME=8,OOT_CORE_VIEW_DRAWN=1};
#define ARRAY_COUNT(a) (sizeof(a)/sizeof((a)[0]))
''' + view + r'''
int main(void){PlayState p={0};OotCoreNpcView v={0};EnExItem item={0};item.actor.id=1;item.actor.draw=&p;
item.actor.scale.x=.2f;item.actor.scale.y=.2f;item.actor.world.pos.y=100;item.actor.shape.yOffset=10;
assert(ChildMinigame_ItemView(&item.actor,&p,&v)==1&&v.anim==1&&v.object==0xfff&&v.scale_x==256&&v.y==102);
item.type=EXITEM_HEART_PIECE_COUNTER;assert(ChildMinigame_ItemView(&item.actor,&p,&v)==1&&v.anim==GID_HEART_PIECE+1);
item.type=EXITEM_SMALL_KEY_CHEST;item.actor.scale.x=.05f;
assert(ChildMinigame_ItemView(&item.actor,&p,&v)==1&&v.anim==GID_SMALL_KEY+1&&v.scale_x==256);
item.type=EXITEM_MAGIC_WIND;assert(ChildMinigame_ItemView(&item.actor,&p,&v)==1&&v.anim==GID_FARORES_WIND+1);
item.actor.draw=NULL;assert(ChildMinigame_ItemView(&item.actor,&p,&v)==-1);
ItemEtcetera lens={0};lens.actor.id=2;lens.actor.draw=&p;lens.actor.params=8;lens.giDrawId=GID_RUPEE_GREEN;
assert(ChildMinigame_ItemView(&lens.actor,&p,&v)==-1);p.actorCtx.lensActive=1;
assert(ChildMinigame_ItemView(&lens.actor,&p,&v)==1&&v.anim==GID_RUPEE_GREEN+1);
EnGSwitch target={0};target.actor.id=4;target.actor.draw=&p;target.type=3;target.colorIdx=2;target.actor.scale.x=.01f;
assert(ChildMinigame_ItemView(&target.actor,&p,&v)==1&&v.anim==GID_RUPEE_RED+1&&v.scale_x==412);
target.broken=1;assert(ChildMinigame_ItemView(&target.actor,&p,&v)==-1);target.type=2;
assert(ChildMinigame_ItemView(&target.actor,&p,&v)==0);
EnExRuppy mark={0};mark.actor.id=3;mark.actor.draw=&p;mark.invisible=1;
assert(ChildMinigame_ItemView(&mark.actor,&p,&v)==-1);mark.invisible=0;
assert(ChildMinigame_ItemView(&mark.actor,&p,&v)==1);return 0;}
''')


if __name__ == '__main__':
    unittest.main()
