"""Execute real owl talk/departure/transport actions with platform observers."""
import os
from pathlib import Path
import sys
import unittest
import test_graphics_backend as graphics

GAME = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(GAME / 'tools'))
import owl_sources as owl
OOT = Path(os.environ.get('DOSEI_OOT', 'D:/Workspace-Claude/game-decomps/n64/oot'))

@unittest.skipUnless((OOT / owl.SOURCE).exists(), 'local decomp required')
class OwlSource(unittest.TestCase):
    run_c = graphics.GraphicsBackend.run_c

    def test_sprite_adapter_preserves_actions(self):
        original = (OOT / owl.SOURCE).read_text(encoding='utf-8')
        adapted = owl.adapt(owl.SOURCE, original)
        header = owl.adapt(owl.SOURCE[:-2]+'.h', (OOT / (owl.SOURCE[:-2]+'.h')).read_text())
        self.assertNotRegex(header, r'Vec3s (?:jointTable2?|morphTable2?)\[')
        self.assertNotRegex(adapted, r'\b(?:Matrix_\w+|SkelAnime_(?:Init|Draw)\w*)\(')
        self.assertNotIn('this->unk_407 = this->unk_3F2', adapted)
        for name in ('EnOwl_CheckInitTalk','EnOwl_WaitOutsideKokiri','EnOwl_ConfirmKokiriMessage',
                     'func_80ACA76C','EnOwl_WaitDeathMountainShortcut','func_80ACC00C'):
            self.assertEqual(owl.function(original,name),owl.function(adapted,name),name)

    def test_field_choices_departure_and_mountain_transport(self):
        original = (OOT / owl.SOURCE).read_text(encoding='utf-8')
        names = ('EnOwl_LookAtLink','EnOwl_CheckInitTalk','func_80ACA558','func_80ACA62C',
                 'func_80ACA76C','EnOwl_ConfirmKokiriMessage','EnOwl_WaitOutsideKokiri',
                 'func_80ACB22C','func_80ACB274','EnOwl_WaitDeathMountainShortcut','func_80ACC00C')
        bodies = '\n'.join(owl.function(original,name) for name in names)
        self.run_c(r'''
#include <assert.h>
#include <stddef.h>
typedef int s32;typedef short s16;typedef unsigned short u16;typedef float f32;
typedef struct {float x,y,z;} Vec3f;
typedef struct {short x,y,z;} Vec3s;
typedef struct {Vec3f pos;Vec3s rot;} PosRot;
typedef struct {PosRot world;struct {Vec3s rot;} shape;int params,textId,flags;float xzDistToPlayer;void* draw;} Actor;
typedef struct {Actor actor;} Player;
typedef struct {struct {int state,choiceIndex;} msgCtx;struct {void* script;} csCtx;} PlayState;
typedef struct EnOwl {Actor actor;void (*actionFunc)(struct EnOwl*,PlayState*);int actionFlags,subCamId,unk_400,unk_40A,unk_3FE;struct {float curFrame;} skelAnime;} EnOwl;
static Player source_player;static struct {struct {struct {struct {int isMagicAcquired;} playerData;} info;} save;int cutsceneTrigger;} gSaveContext;
static int accepted,offered,advance,closing,seqstop,fanfare,eventflag,switchflag,unfold,csaction,in_cs,sfx,gTimeSpeed=1,camid,camtimer;
static float offered_dist;static char gDMTOwlCs[1],gLakeHyliaOwlCs[1];
#define true 1
#define false 0
#define GET_PLAYER(p) (&source_player)
#define PARAMS_GET_S(v,s,n) (((unsigned)(v)>>(s))&((1u<<(n))-1))
#define ACTOR_FLAG_TALK_OFFER_AUTO_ACCEPTED 1
#define EXCH_ITEM_NONE 0
#define CAM_ID_MAIN 0
#define PLAYER_CSACTION_8 8
#define TEXT_STATE_CHOICE 4
#define OWL_REPEAT 0
#define OWL_OK 1
#define NA_BGM_OWL 12
#define NA_SE_SY_TRE_BOX_APPEAR 13
#define SEQCMD_STOP_SEQUENCE(a,b) (++seqstop)
#define SET_EVENTCHKINF(x) (eventflag=1)
#define PRINTF(...) ((void)0)
#define PRINTF_COLOR_CYAN() ((void)0)
#define PRINTF_RST() ((void)0)
#define ASSERT(c,...) assert(c)
#define SEGMENTED_TO_VIRTUAL(p) (p)
static void EnOwl_WaitDeathMountainShortcut(EnOwl*,PlayState*);
static void EnOwl_WaitDefault(EnOwl* a,PlayState*p) {(void)a;(void)p;}
static void func_80ACC30C(EnOwl*a,PlayState*p) {(void)a;(void)p;}
static void func_80ACBF50(EnOwl*a,PlayState*p) {(void)a;(void)p;}
static short Math_Vec3f_Yaw(Vec3f*a,Vec3f*b) {(void)a;(void)b;return 0x4000;}
static int Actor_TalkOfferAccepted(Actor*a,PlayState*p) {(void)a;(void)p;return accepted;}
static float Rand_ZeroOne(void){return 0.25f;}
static int OnePointCutscene_Init(PlayState*p,int id,int timer,Actor*a,int parent) {(void)p;(void)a;(void)parent;camid=id;camtimer=timer;return 1;}
static void Actor_OfferTalkExchange(Actor*a,PlayState*p,float d,float h,int e){(void)a;(void)p;(void)h;(void)e;++offered;offered_dist=d;}
static void Flags_SetSwitch(PlayState*p,int f){(void)p;switchflag=f;}
static void func_80ACA5C8(EnOwl*a){(void)a;++unfold;}
static void Player_SetCsActionWithHaltedActors(PlayState*p,Actor*a,int action){(void)p;(void)a;csaction=action;}
static int Actor_TextboxIsClosing(Actor*a,PlayState*p){(void)a;(void)p;return closing;}
static int Message_GetState(void*p){return *(int*)p;}
static int Message_ShouldAdvance(PlayState*p){(void)p;return advance;}
static void Message_ContinueTextbox(PlayState*p,int id){p->msgCtx.state=id;}
static void Audio_PlayFanfare(int song){fanfare=song;}
static void Math_SmoothStepToS(short*v,int t,int a,int b,int c){(void)a;(void)b;(void)c;*v=t;}
static int Play_InCsMode(PlayState*p){(void)p;return in_cs;}
static void Sfx_PlaySfxCentered(int id){sfx=id;}
static void func_800F44EC(int a,int b){(void)a;(void)b;}
''' + bodies + r'''
int main(void){
 PlayState play={0};EnOwl o={0};o.actor.params=0x4c;o.actor.xzDistToPlayer=360;
 EnOwl_WaitOutsideKokiri(&o,&play);assert(!offered && o.actor.textId==0x2064);
 o.actor.xzDistToPlayer=359;EnOwl_WaitOutsideKokiri(&o,&play);
 assert(offered==1 && offered_dist==360 && o.actor.shape.rot.y==0x4000);
 assert(o.actor.flags&ACTOR_FLAG_TALK_OFFER_AUTO_ACCEPTED);
 accepted=1;EnOwl_WaitOutsideKokiri(&o,&play);
 assert(camid==8700 && camtimer==-99 && eventflag && fanfare==NA_BGM_OWL);
 assert(o.actionFunc==EnOwl_ConfirmKokiriMessage);
 play.msgCtx.state=TEXT_STATE_CHOICE;advance=1;play.msgCtx.choiceIndex=OWL_REPEAT;
 o.actionFunc(&o,&play);assert(play.msgCtx.state==0x2065 && o.actionFunc==EnOwl_ConfirmKokiriMessage);
 play.msgCtx.state=TEXT_STATE_CHOICE;play.msgCtx.choiceIndex=OWL_OK;
 o.actionFunc(&o,&play);assert(play.msgCtx.state==0x2067 && o.actionFunc==func_80ACA76C);
 o.actionFunc(&o,&play);assert(csaction==8 && !unfold);
 closing=1;o.actionFunc(&o,&play);assert(unfold==1 && switchflag==12 && seqstop==1 && !(o.actor.flags&1));
 accepted=0;closing=0;o.actor.xzDistToPlayer=119;EnOwl_WaitDeathMountainShortcut(&o,&play);
 assert(o.actor.textId==0x3062);accepted=1;EnOwl_WaitDeathMountainShortcut(&o,&play);
 assert(o.actionFunc==func_80ACB274);closing=1;o.actionFunc(&o,&play);
 assert(o.actionFunc==EnOwl_WaitDeathMountainShortcut && unfold==1);
 gSaveContext.save.info.playerData.isMagicAcquired=1;accepted=0;EnOwl_WaitDeathMountainShortcut(&o,&play);
 assert(o.actor.textId==0x3063);accepted=1;EnOwl_WaitDeathMountainShortcut(&o,&play);
 assert(o.actionFunc==func_80ACB22C);o.actionFunc(&o,&play);assert(unfold==2 && o.actionFunc==func_80ACC30C);
 o.actor.params=8<<6;o.actor.xzDistToPlayer=50;o.actor.draw=(void*)1;
 func_80ACC00C(&o,&play);assert(!gSaveContext.cutsceneTrigger);
 o.actor.xzDistToPlayer=49;in_cs=1;func_80ACC00C(&o,&play);assert(!gSaveContext.cutsceneTrigger);
 in_cs=0;func_80ACC00C(&o,&play);
 assert(play.csCtx.script==gDMTOwlCs && !o.actor.draw && gSaveContext.cutsceneTrigger==1);
 assert(o.actionFlags&0x80);assert(o.actionFunc==EnOwl_WaitDefault && !gTimeSpeed && sfx==NA_SE_SY_TRE_BOX_APPEAR);
 return 0;
}
''')

if __name__ == '__main__':unittest.main()
