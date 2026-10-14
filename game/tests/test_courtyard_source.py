"""Execute original Zelda reward and Impa Lullaby/exit gates."""
import os
from pathlib import Path
import re
import sys
import unittest
import test_graphics_backend as graphics
GAME=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(GAME/'tools'))
import courtyard_sources as courtyard
from owl_sources import function
OOT=Path(os.environ.get('DOSEI_OOT','D:/Workspace-Claude/game-decomps/n64/oot'))

@unittest.skipUnless((OOT/courtyard.SOURCES[0]).exists(),'local source required')
class CourtyardSource(unittest.TestCase):
    run_c=graphics.GraphicsBackend.run_c

    def test_sprite_only_and_original_reward_actions(self):
        for path in courtyard.SOURCES:
            original=(OOT/path).read_text(encoding='utf-8')
            adapted=courtyard.adapt(path,original)
            header=courtyard.adapt(path[:-2]+'.h',(OOT/(path[:-2]+'.h')).read_text())
            self.assertNotRegex(adapted,r'\b(?:Matrix_\w+|SkelAnime_(?:Init|Draw)\w*|Skin_\w+|Npc_TrackPoint)\(')
            self.assertNotRegex(header,r'Vec3s (?:jointTable|morphTable)\[')
            names=('EnZl4_CsMakePlan','EnZl4_CsAskName') if path==courtyard.SOURCES[0] else (
                ('func_80986C30','func_80986B2C','func_80986BF8') if path==courtyard.SOURCES[1] else ())
            for name in names:self.assertEqual(function(original,name),function(adapted,name),name)

    def test_source_letter_offer_waits_for_player_acceptance(self):
        source=(OOT/courtyard.SOURCES[0]).read_text(encoding='utf-8')
        body=function(source,'EnZl4_CsMakePlan')
        constants=sorted(set(re.findall(r'\b(?:ZL4_\w+|TEXT_STATE_\w+|MSGMODE_\w+|CAM_SET_\w+|GI_\w+)\b',body)))
        self.run_c(r'''
#include <assert.h>
#include <math.h>
typedef int s32;
typedef struct Actor {float xzDistToPlayer,yDistToPlayer;} Actor;
typedef struct PlayState {struct {int state,msgMode,stateTimer;} msgCtx;void(*talkWithPlayer)(struct PlayState*,Actor*);} PlayState;
typedef struct {Actor actor;int skelAnime,talkState,blinkTimer,eyeExpression,mouthExpression,talkTimer2,unk_20F,cueId;} EnZl4;
static int sAnimationInfo,advance,parent,offered,item,talk_calls,setting;
#define GET_ACTIVE_CAM(p) (p)
#define FALLTHROUGH ((void)0)
'''+'enum {'+','.join(constants)+'};\n'+r'''
static void Animation_ChangeByInfo(int*a,int b,int c){(void)a;(void)b;(void)c;}
static void EnZl4_SetActiveCamMove(PlayState*p,int i){(void)p;(void)i;}
static void EnZl4_SetActiveCamDir(PlayState*p,int i){(void)p;(void)i;}
static void Message_StartTextbox(PlayState*p,int id,void*a){(void)p;(void)id;(void)a;}
static int Message_GetState(void*p){return *(int*)p;}
static int Message_ShouldAdvance(PlayState*p){(void)p;return advance;}
static int EnZl4_SetNextAnim(EnZl4*a,int n){(void)a;(void)n;return 1;}
static void Camera_RequestSetting(PlayState*p,int s){(void)p;setting=s;}
static void Actor_OfferGetItem(Actor*a,PlayState*p,int id,float d,float h){(void)a;(void)p;assert(d>0 && h>0);++offered;item=id;}
static int Actor_HasParent(Actor*a,PlayState*p){(void)a;(void)p;return parent;}
static void talk(PlayState*p,Actor*a){(void)p;(void)a;++talk_calls;}
'''+body+r'''
int main(void){
 PlayState p={0};EnZl4 z={0};p.talkWithPlayer=talk;z.talkState=6;z.actor.xzDistToPlayer=-34;z.actor.yDistToPlayer=-2;
 p.msgCtx.state=TEXT_STATE_EVENT;assert(!EnZl4_CsMakePlan(&z,&p) && !offered);
 advance=1;assert(!EnZl4_CsMakePlan(&z,&p));assert(z.talkState==7 && offered==1 && item==GI_ZELDAS_LETTER);
 assert(talk_calls==1 && setting==CAM_SET_NORMAL0 && p.msgCtx.msgMode==MSGMODE_TEXT_CLOSING);
 assert(!EnZl4_CsMakePlan(&z,&p) && offered==2 && z.talkState==7);
 parent=1;assert(EnZl4_CsMakePlan(&z,&p) && z.talkState==8 && offered==2);
 return 0;
}
''')

    def test_source_impa_letter_gate_song_grant_and_field_exit(self):
        source=(OOT/courtyard.SOURCES[1]).read_text(encoding='utf-8')
        bodies='\n'.join(function(source,n) for n in ('func_80986A5C','func_80986BF8','func_80986C30','func_80986B2C'))
        self.run_c(r'''
#include <assert.h>
typedef int s32;typedef float f32;
typedef struct {struct {struct {float x,y,z;} pos;} world;struct {int shadowAlpha;} shape;} Actor;
typedef struct {Actor actor;} Player;
typedef struct {int state;} Message;
typedef struct {Message msgCtx;struct {void*script;} csCtx;int nextEntranceIndex,transitionType,transitionTrigger;} PlayState;
typedef struct {Actor actor;int action,drawConfig,unk_280;} DemoIm;
static Player source_player;static struct {int cutsceneTrigger;} gSaveContext;
static int letter,flag59,in_cs,item,grants,actions,csaction;static char gZeldasCourtyardLullabyCs[1];
#define true 1
#define false 0
#define GET_PLAYER(p) (&source_player)
#define kREG(n) 0
#define GET_EVENTCHKINF(f) (letter)
#define SET_EVENTCHKINF(f) (flag59=1)
#define SEGMENTED_TO_VIRTUAL(p) (p)
#define ITEM_SONG_LULLABY 7
#define TEXT_STATE_CLOSING 3
#define ENTR_HYRULE_FIELD_0 99
#define TRANS_TYPE_CIRCLE(a,b,c) 100
#define TRANS_TRIGGER_START 1
#define PLAYER_CSACTION_8 8
static int Play_InCsMode(PlayState*p){(void)p;return in_cs;}
static void Item_Give(PlayState*p,int id){(void)p;item=id;++grants;}
static void func_80985F54(DemoIm*a){(void)a;++actions;}
static int Message_GetState(Message*m){return m->state;}
static void Player_SetCsActionWithHaltedActors(PlayState*p,Actor*a,int s){(void)p;(void)a;csaction=s;}
'''+bodies+r'''
int main(void){
 PlayState p={0};DemoIm impa={0};impa.actor.world.pos.x=336;
 func_80986BF8(&impa,&p);assert(!impa.action && !impa.drawConfig);
 letter=1;func_80986BF8(&impa,&p);assert(impa.action==24 && impa.drawConfig==1);
 source_player.actor.world.pos.x=206;func_80986C30(&impa,&p);assert(!grants);
 source_player.actor.world.pos.x=207;in_cs=1;func_80986C30(&impa,&p);assert(!grants);
 in_cs=0;func_80986C30(&impa,&p);assert(grants==1 && item==ITEM_SONG_LULLABY && flag59);
 assert(p.csCtx.script==gZeldasCourtyardLullabyCs && gSaveContext.cutsceneTrigger && actions==1);
 func_80986B2C(&p);assert(!p.transitionTrigger);
 p.msgCtx.state=TEXT_STATE_CLOSING;func_80986B2C(&p);
 assert(p.transitionTrigger==1 && p.nextEntranceIndex==ENTR_HYRULE_FIELD_0 && csaction==8);
 return 0;
}
''')

    def test_root_anchors_current_and_move_actor_without_joints(self):
        generated=courtyard.anchor_source(OOT)
        self.assertEqual((GAME/'oot-core/include/courtyard_root.inc').read_text(),generated)
        rows=courtyard.root_anchors(OOT)
        name,_,points=next(r for r in rows if len(r[2])>20)
        declarations='\n'.join('static char '+n+';' for n,_,_ in rows)
        self.run_c(r'''
#include <assert.h>
#include <stddef.h>
#include <math.h>
typedef short s16;typedef float f32;
typedef struct CourtyardRootPoint CourtyardRootPoint;
typedef struct {struct {struct {float x,y,z;} pos;} world;struct {struct {short y;} rot;} shape;struct {float x,y,z;} scale;} Actor;
typedef struct {void*animation;float curFrame;struct {short x,y,z;} prevTransl;short prevRot;int movementFlags;} SkelAnime;
#define ANIM_FLAG_ADJUST_STARTING_POS 1
static float Math_SinS(short a){return sinf(a*6.283185307179586/65536.0);}
static float Math_CosS(short a){return cosf(a*6.283185307179586/65536.0);}
'''+declarations+'\n'+generated+f'''
int main(void){{
 Actor a={{0}};SkelAnime s={{0}};a.scale.x=a.scale.z=.01f;s.animation=&{name};
 s.movementFlags=1;Courtyard_ZeldaMove(&a,&s);assert(!a.world.pos.x && !a.world.pos.z);
 s.curFrame={points[-1][0]};Courtyard_ZeldaMove(&a,&s);
 assert(fabsf(a.world.pos.x-({points[-1][1]-points[0][1]})*.01f)<.001f);
 assert(fabsf(a.world.pos.z-({points[-1][2]-points[0][2]})*.01f)<.001f);
 float x=a.world.pos.x,z=a.world.pos.z;Courtyard_ZeldaMove(&a,&s);
 assert(a.world.pos.x==x && a.world.pos.z==z);return 0;
}}
''')

if __name__=='__main__':unittest.main()
