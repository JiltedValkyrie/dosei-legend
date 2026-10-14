"""Execute the source Ranch countdown, Talon win/failure and bottle handshake."""
import os
from pathlib import Path
import re
import sys
import unittest
import test_graphics_backend as graphics
from test_child_route_npcs import function
from test_child_route_shops import enum

GAME = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(GAME / 'tools'))
import ranch_sources as ranch
import build_ranch_sprites
import oot_core_import as imp

OOT = Path(os.environ.get('DOSEI_OOT', 'D:/Workspace-Claude/game-decomps/n64/oot'))


@unittest.skipUnless((OOT / ranch.SOURCES[0]).exists(), 'local decomp required')
class RanchSources(unittest.TestCase):
    run_c = graphics.GraphicsBackend.run_c

    def test_original_actions_and_no_runtime_horse_skin(self):
        for rel in ranch.SOURCES:
            text = (OOT / rel).read_text(encoding='utf-8')
            changed = ranch.adapt(rel, text)
            self.assertNotRegex(changed, r'\b(?:Skin_\w+|SkinMatrix_\w+|Matrix_\w+)\(')
            self.assertIn('RanchSprite_Head', changed)
            for name in re.findall(r'^(?:void|s32) (\w+)\([^;{}]*\) \{', text, re.M):
                if any(x in name for x in ('Init', 'Destroy', 'Update', 'Draw')) or name == 'func_80A6CC88':
                    continue
                self.assertEqual(function(text, name), function(changed, name), name)
            header = ranch.adapt(rel[:-2] + '.h', (OOT / (rel[:-2] + '.h')).read_text())
            self.assertNotIn('Skin skin;', header)
        for rel in ranch.EXISTING_SOURCES:
            text = (OOT / rel).read_text(encoding='utf-8')
            changed = ranch.adapt(rel, text)
            self.assertNotRegex(changed, r'\b(?:Matrix_\w+|SkelAnime_Draw\w*)\(')
            header = ranch.adapt(rel[:-2] + '.h', (OOT / (rel[:-2] + '.h')).read_text())
            self.assertNotRegex(header, r'Vec3s (?:jointTable|morphTable)\[')
        talon = (OOT / ranch.EXISTING_SOURCES[3]).read_text(encoding='utf-8')
        for name in ('EnTa_RunCuccoGame', 'EnTa_StartingCuccoGame3', 'EnTa_GiveItemInLonLonHouse'):
            self.assertEqual(function(talon, name), function(ranch.adapt(ranch.EXISTING_SOURCES[3], talon), name))
        self.assertEqual(build_ranch_sprites.anchors(OOT), (GAME / 'oot-core/include/ranch_horse_anchors.inc').read_text())

    def test_source_timer_cadence_pause_gates_and_snapshot(self):
        timer = (GAME / 'oot-core/src/bridge_ranch.cpp').read_text()
        self.assertEqual(timer, ranch.timer_source(OOT))
        save = (OOT / 'include/save.h').read_text()
        self.run_c(r'''
#include <assert.h>
#include <stdbool.h>
#include <string.h>
typedef short s16;
typedef struct { int msgMode,msgLength; } MessageContext;
typedef struct { unsigned stateFlags2; } Player;
typedef struct PlayState { int pauseCtx; struct { int state; } gameOverCtx;
    MessageContext msgCtx; Player player; int transitionTrigger,transitionMode,shootingGalleryStatus,sceneId;
    void(*damagePlayer)(struct PlayState*,int); } PlayState;
static struct { int timerState,timerSeconds,timerX[2],timerY[2],subTimerState,minigameState;
    struct { struct { struct { int health,healthCapacity; } playerData; } info; } save; } gSaveContext;
enum { GAMEOVER_INACTIVE=0,MSGMODE_NONE=0,TRANS_TRIGGER_OFF=0,TRANS_MODE_OFF=0,
       PLAYER_STATE2_24=1<<24,SCENE_BOMBCHU_BOWLING_ALLEY=75,
       NA_SE_SY_MESSAGE_WOMAN=1,NA_SE_SY_WARNING_COUNT_N,NA_SE_SY_WARNING_COUNT_E };
static int cinematic,switchSet,beeps,lastBeep;
#define GET_PLAYER(p) (&(p)->player)
#define IS_PAUSED(p) (*(p))
#define FALLTHROUGH ((void)0)
#define SFX_PLAY_CENTERED(s) (++beeps,lastBeep=(s))
static int Play_InCsMode(PlayState*p) {return cinematic;}
static int Flags_GetSwitch(PlayState*p,int flag) {return switchSet;}
''' + enum(save, 'TimerState') + enum(save, 'SubTimerState') + enum(save, 'TimerId') + '\n' +
            (GAME / 'oot-core/include/oot_core_timer.h').read_text() +
            timer[timer.index('static s16 sEnvHazardActive;'):] + r'''
int main(void) {
    PlayState p={0}; OotCoreTimerView view; int ticks=0;
    gSaveContext.save.info.playerData.healthCapacity=48;
    Interface_SetTimer(30); assert(gSaveContext.timerState==TIMER_STATE_DOWN_INIT);
    OotCore_TimerView(&view); assert(view.seconds==30 && view.x==140 && view.y==80);
    p.pauseCtx=1; OotCore_UpdateRouteTimer(&p); assert(gSaveContext.timerState==TIMER_STATE_DOWN_INIT);p.pauseCtx=0;
    while(gSaveContext.timerSeconds) {OotCore_UpdateRouteTimer(&p);assert(++ticks<700);}
    assert(ticks==621 && gSaveContext.timerState==TIMER_STATE_STOP && lastBeep==NA_SE_SY_WARNING_COUNT_E);
    OotCore_TimerView(&view);assert(view.seconds==0 && view.x==26 && view.y==46);
    OotCore_UpdateRouteTimer(&p);assert(gSaveContext.timerState==TIMER_STATE_OFF);
    Interface_SetTimer(30);OotCore_UpdateRouteTimer(&p);
    for(int i=0;i<40;i++)OotCore_UpdateRouteTimer(&p);
    assert(gSaveContext.timerSeconds==29);
    p.msgCtx.msgMode=1;for(int i=0;i<80;i++)OotCore_UpdateRouteTimer(&p);assert(gSaveContext.timerSeconds==29);
    p.msgCtx.msgMode=0;cinematic=1;for(int i=0;i<80;i++)OotCore_UpdateRouteTimer(&p);assert(gSaveContext.timerSeconds==29);
    cinematic=0;p.player.stateFlags2=PLAYER_STATE2_24;OotCore_UpdateRouteTimer(&p);assert(sTimerNextSecondTimer==20);
    p.player.stateFlags2=0;p.transitionTrigger=1;OotCore_UpdateRouteTimer(&p);assert(sTimerNextSecondTimer==20);
    p.transitionTrigger=0;gSaveContext.minigameState=1;OotCore_UpdateRouteTimer(&p);assert(sTimerNextSecondTimer==20);
    gSaveContext.minigameState=0;p.msgCtx.msgLength=1;OotCore_UpdateRouteTimer(&p);assert(sTimerNextSecondTimer==20);
    p.msgCtx.msgLength=0;for(int i=0;i<20;i++)OotCore_UpdateRouteTimer(&p);assert(gSaveContext.timerSeconds==28);
    Interface_SetTimer(0);for(int i=0;i<41;i++)OotCore_UpdateRouteTimer(&p);assert(gSaveContext.timerSeconds==1);
    gSaveContext.timerSeconds=3598;sTimerNextSecondTimer=1;OotCore_UpdateRouteTimer(&p);
    assert(gSaveContext.timerSeconds==3599 && gSaveContext.timerState==TIMER_STATE_UP_FREEZE);
    return 0;
}
''')

    def test_talon_source_carry_win_timeout_and_once_only_bottle(self):
        text = (OOT / ranch.EXISTING_SOURCES[3]).read_text(encoding='utf-8')
        flags = '\n'.join(re.findall(r'^#define TALON_STATE_FLAG_.*', text, re.M))
        bodies = '\n'.join(function(text, n) for n in ('EnTa_IsPlayerHoldingSuperCucco', 'EnTa_GetSuperCuccosCount',
                            'EnTa_RunCuccoGame', 'EnTa_GiveItemInLonLonHouse'))
        self.run_c(r'''
#include <assert.h>
#include <stdbool.h>
#include <stddef.h>
#include <string.h>
typedef int s32;
typedef struct Actor {int id,textId,flags;float gravity;void*parent;} Actor;
typedef struct {Actor actor;} EnNiw;
typedef struct {unsigned stateFlags1;Actor*interactRangeActor;} Player;
typedef struct {Player player;} PlayState;
typedef struct EnTa {Actor actor;int skelAnime,stateFlags,superCuccoTimers[3],lastFoundSuperCuccoIdx;
    EnNiw*superCuccos[3];void(*actionFunc)(struct EnTa*,PlayState*);} EnTa;
enum {PLAYER_STATE1_CARRYING_ACTOR=1,ACTOR_EN_NIW=25,TIMER_STATE_OFF=0,PLAYER_CSACTION_1=1,
 ANIMMODE_ONCE,EVENTINF_CUCCO_GAME_WON,SEQ_PLAYER_BGM_MAIN,NA_BGM_SMALL_ITEM_GET,NA_SE_VO_TA_CRY_1,
 NA_SE_VO_TA_SURPRISE,ACTOR_FLAG_TALK_OFFER_AUTO_ACCEPTED=256,NA_SE_SY_FOUND,
 ITEMGETINF_TALON_BOTTLE,GI_MILK=50,GI_BOTTLE_MILK_FULL=51};
static struct {int timerState,timerSeconds;}gSaveContext;
static int won,cinematic,fanfares,textId,cameras,bottleFlag,offers,item,gTalonSitHandsUpAnim;
#define GET_PLAYER(p) (&(p)->player)
#define ARRAY_COUNT(a) (sizeof(a)/sizeof((a)[0]))
#define SET_EVENTINF(x) (won=1)
#define CLEAR_EVENTINF(x) (won=0)
#define SET_ITEMGETINF(x) (bottleFlag=1)
#define SEQCMD_STOP_SEQUENCE(a,b) ((void)0)
#define Animation_Change(...) ((void)0)
#define Player_SetCsActionWithHaltedActors(...) ((void)0)
#define Actor_PlaySfx(...) ((void)0)
#define Actor_OfferTalk(...) ((void)0)
#define Audio_SetFastTempoForTimedMinigame() ((void)0)
#define Sfx_PlaySfxCentered(x) ((void)0)
static void Audio_PlayFanfare(int x){++fanfares;}
static void Message_StartTextbox(PlayState*p,int id,Actor*a){textId=id;}
static int Play_InCsMode(PlayState*p){return cinematic;}
static void EnTa_CreateFloorCamera(EnTa*a,PlayState*p){++cameras;}
static void EnTa_TalkCuccoGameEnd(EnTa*a,PlayState*p){}
static void EnTa_IdleFoundSuperCucco(EnTa*a,PlayState*p){}
static void EnTa_TalkGeneralInLonLonHouse(EnTa*a,PlayState*p){}
static int Actor_HasParent(Actor*a,PlayState*p){return a->parent!=NULL;}
static void Actor_OfferGetItem(Actor*a,PlayState*p,int id,float xz,float y){++offers;item=id;}
''' + flags + '\n' + bodies + r'''
int main(void){
 PlayState p={0};EnTa t={0};EnNiw c[3]={0};for(int i=0;i<3;i++){c[i].actor.id=ACTOR_EN_NIW;t.superCuccos[i]=&c[i];}
 gSaveContext.timerSeconds=20;gSaveContext.timerState=8;
 p.player.stateFlags1=PLAYER_STATE1_CARRYING_ACTOR;p.player.interactRangeActor=&c[0].actor;
 t.superCuccoTimers[0]=1;EnTa_RunCuccoGame(&t,&p);assert(!t.actionFunc && !won);
 EnTa_RunCuccoGame(&t,&p);assert(t.actionFunc==EnTa_IdleFoundSuperCucco && t.actor.textId==0x2082 && !won);
 t.superCuccos[1]=t.superCuccos[2]=NULL;EnTa_RunCuccoGame(&t,&p);
 assert(won && fanfares==1 && textId==0x2084 && gSaveContext.timerState==TIMER_STATE_OFF);
 memset(&t,0,sizeof(t));p.player.stateFlags1=0;gSaveContext.timerSeconds=0;cinematic=1;
 EnTa_RunCuccoGame(&t,&p);assert(!cameras && won);cinematic=0;EnTa_RunCuccoGame(&t,&p);
 assert(cameras==1 && !won && textId==0x2081 && t.actionFunc==EnTa_TalkCuccoGameEnd);
 memset(&t,0,sizeof(t));EnTa_GiveItemInLonLonHouse(&t,&p);assert(offers==1 && item==GI_BOTTLE_MILK_FULL && !bottleFlag);
 t.actor.parent=&p;EnTa_GiveItemInLonLonHouse(&t,&p);assert(offers==1 && bottleFlag && !t.actor.parent);
 bottleFlag=0;t.stateFlags|=TALON_STATE_FLAG_GIVING_MILK_REFILL;EnTa_GiveItemInLonLonHouse(&t,&p);
 assert(offers==2 && item==GI_MILK);t.actor.parent=&p;EnTa_GiveItemInLonLonHouse(&t,&p);
 assert(offers==2 && !bottleFlag && !(t.stateFlags&TALON_STATE_FLAG_GIVING_MILK_REFILL));return 0;
}
''')


if __name__ == '__main__':
    unittest.main()
