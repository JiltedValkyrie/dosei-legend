"""Route source reward/turning behavior and sprite-adaptation regressions."""
import os
from pathlib import Path
import re
import sys
import unittest

import test_graphics_backend as graphics

GAME = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(GAME / 'tools'))
import child_route_npcs as route

OOT = Path(os.environ.get('DOSEI_OOT', 'D:/Workspace-Claude/game-decomps/n64/oot'))


def function(text, name):
    match = re.search(r'^(?:static inline )?(?:void|s16|u16|s32) ' + name + r'\([^;{}]*\) \{', text, re.M)
    if match is None:
        raise AssertionError('source function missing: ' + name)
    end = text.index('\n}', match.end()) + 2
    return text[match.start():end]


@unittest.skipUnless((OOT / 'src/code/z_actor.c').exists(), 'local OoT decomp required')
class ChildRouteNpcs(unittest.TestCase):
    run_c = graphics.GraphicsBackend.run_c

    def source(self, name):
        rel = route.SOURCES[route.ACTORS.index(name)]
        return rel, (OOT / rel).read_text(encoding='utf-8')

    def test_runtime_characters_have_no_pose_or_matrix_work(self):
        for name in route.ACTORS:
            rel, original = self.source(name)
            with self.subTest(actor=name):
                source = route.adapt(rel, original)
                header_rel = rel[:-2] + '.h'
                header = route.adapt(header_rel, (OOT / header_rel).read_text(encoding='utf-8'))
                self.assertNotRegex(header, r'Vec3s (?:jointTable|morphTable)\[')
                self.assertNotRegex(source, r'\b(?:Matrix_\w+|SkelAnime_Init\w*|SkelAnime_Draw\w*|Npc_TrackPoint|Actor_TrackPlayer)\(')
                self.assertIn('OotCore_SpriteInit', source)

    def test_reward_and_gate_actions_remain_original_source(self):
        rewards = {
            'En_Go2': ('EnGo2_GetTextIdGoronCityRollingBig', 'EnGo2_UpdateTalkStateGoronCityRollingBig', 'EnGo2_GetItem'),
            'En_Du': ('func_809FEC14', 'func_809FEC70', 'func_809FECE4'),
            'En_Niw_Lady': ('func_80ABA654', 'func_80ABAC00', 'func_80ABA244'),
            'En_Heishi2': ('func_80A53908', 'func_80A53C0C', 'func_80A53D0C'),
            'En_Sa': ('EnSa_AwaitTeachingSariasSong', 'EnSa_HandleCutscene'),
        }
        for actor, names in rewards.items():
            rel, source = self.source(actor)
            adapted = route.adapt(rel, source)
            for name in names:
                with self.subTest(actor=actor, function=name):
                    self.assertEqual(function(source, name), function(adapted, name))

    def test_rolling_goron_eligibility_and_one_time_bag_upgrade(self):
        _, source = self.source('En_Go2')
        bodies = '\n'.join(function(source, name) for name in (
            'EnGo2_GetTextIdGoronCityRollingBig', 'EnGo2_UpdateTalkStateGoronCityRollingBig'))
        self.run_c(r'''
#include <assert.h>
typedef short s16; typedef unsigned short u16; typedef int s32;
typedef struct { int msgCtx; } PlayState;
typedef struct { struct { int textId; } actor; int waypoint; void (*actionFunc)(void); } EnGo2;
enum { TEXT_STATE_CLOSING, TEXT_STATE_EVENT, NPC_TALK_STATE_ACTION, NPC_TALK_STATE_TALKING,
       GI_BOMB_BAG_30, GI_BOMB_BAG_40, UPG_BOMB_BAG, INFTABLE_11E };
static int awarded, capacity, item, offers, advance;
#define GET_INFTABLE(x) (awarded)
#define SET_INFTABLE(x) (awarded=1)
#define CUR_CAPACITY(x) (capacity)
#define FALLTHROUGH ((void)0)
static int Message_GetState(int* ctx) { return *ctx; }
static int Message_ShouldAdvance(PlayState* play) { return advance; }
static void Message_CloseTextbox(PlayState* play) { play->msgCtx=TEXT_STATE_CLOSING; }
static void EnGo2_SetupGetItem(void) {}
static void EnGo2_GetItem(EnGo2* actor, PlayState* play, int id) { item=id; ++offers; }
''' + bodies + r'''
int main(void) {
    PlayState play={TEXT_STATE_EVENT}; EnGo2 goron={{0},8,0};
    capacity=0; assert(EnGo2_GetTextIdGoronCityRollingBig(&play,&goron)==0x3011);
    capacity=20; goron.waypoint=7; assert(EnGo2_GetTextIdGoronCityRollingBig(&play,&goron)==0x3011);
    goron.waypoint=12; assert(EnGo2_GetTextIdGoronCityRollingBig(&play,&goron)==0x3011);
    goron.waypoint=8; goron.actor.textId=EnGo2_GetTextIdGoronCityRollingBig(&play,&goron);
    assert(goron.actor.textId==0x3012);
    advance=0; EnGo2_UpdateTalkStateGoronCityRollingBig(&play,&goron); assert(!offers && !awarded);
    advance=1; EnGo2_UpdateTalkStateGoronCityRollingBig(&play,&goron);
    assert(offers==1 && item==GI_BOMB_BAG_30 && awarded);
    assert(EnGo2_GetTextIdGoronCityRollingBig(&play,&goron)==0x3013);
    EnGo2_UpdateTalkStateGoronCityRollingBig(&play,&goron); assert(offers==1);
    awarded=0; capacity=30; play.msgCtx=TEXT_STATE_EVENT;
    EnGo2_UpdateTalkStateGoronCityRollingBig(&play,&goron); assert(item==GI_BOMB_BAG_40 && offers==2);
    return 0;
}
''')

    def test_darunia_bracelet_waits_for_parent_handshake(self):
        _, source = self.source('En_Du')
        self.run_c(r'''
#include <assert.h>
#include <math.h>
#include <stddef.h>
typedef float f32;
typedef struct { void* parent; float xzDistToPlayer, yDistToPlayer; } Actor;
typedef struct { int unused; } PlayState;
typedef struct { Actor actor; int next; } EnDu;
enum { GI_GORONS_BRACELET=0x50 };
static int offers; static float offered_xz, offered_y;
static int Actor_HasParent(Actor* actor, PlayState* play) { return actor->parent!=NULL; }
static void Actor_OfferGetItem(Actor* actor, PlayState* play,int item,float xz,float y) {
    assert(item==GI_GORONS_BRACELET); ++offers; offered_xz=xz; offered_y=y;
}
static void func_809FECE4(EnDu* actor, PlayState* play) {}
static void EnDu_SetupAction(EnDu* actor, void(*action)(EnDu*,PlayState*)) {
    assert(action==func_809FECE4); actor->next=1;
}
''' + function(source, 'func_809FEC70') + r'''
int main(void) {
    PlayState play={0}; EnDu actor={{NULL,42,-9},0};
    func_809FEC70(&actor,&play); assert(offers==1 && !actor.next && offered_xz==43 && offered_y==10);
    actor.actor.parent=&play; func_809FEC70(&actor,&play);
    assert(offers==1 && actor.next && actor.actor.parent==NULL);
    return 0;
}
''')

    def test_body_turn_preserves_source_autoturn_delays_without_pose(self):
        original = (OOT / 'src/code/z_actor.c').read_text(encoding='utf-8')
        helper = (GAME / 'oot-core/include/child_route_npc_sprite.h').read_text()
        self.run_c(r'''
#include <assert.h>
#include <stdlib.h>
typedef short s16; typedef int s32; typedef float f32;
typedef struct { float x,y,z; } Vec3f;
typedef struct { struct { Vec3f pos; } world; struct { struct { s16 y; } rot; } shape; } Actor;
typedef struct { Vec3f trackPos; int talkState, autoTurnTimer, autoTurnState, trackingMode; } NpcInteractInfo;
enum { NPC_TRACKING_PLAYER_AUTO_TURN, NPC_TRACKING_NONE, NPC_TRACKING_HEAD_AND_TORSO,
       NPC_TRACKING_HEAD, NPC_TRACKING_FULL_BODY, NPC_TALK_STATE_IDLE=0 };
static int random_calls, turns;
#define ABS(x) abs(x)
#define DECR(x) ((x)>0?--(x):0)
static float Math_Vec3f_DistXYZ(Vec3f* a,Vec3f* b) { return b->z; }
static s16 Math_Vec3f_Yaw(Vec3f* a,Vec3f* b) { return (s16)b->x; }
static int Rand_S16Offset(int base,int range) { ++random_calls; return base; }
static void Math_SmoothStepToS(s16* value,s16 target,int scale,int max,int min) { *value=target; ++turns; }
''' + function(original, 'Npc_UpdateAutoTurn') + '\n' + function(helper, 'ChildRouteSprite_TrackBody') + r'''
int main(void) {
    Actor actor={0}; NpcInteractInfo info={{20000,0,10},0,0,0,0};
    ChildRouteSprite_TrackBody(&actor,&info,3,NPC_TRACKING_PLAYER_AUTO_TURN);
    assert(random_calls==1 && info.autoTurnTimer==30 && !turns);
    for(int i=0;i<70;i++) ChildRouteSprite_TrackBody(&actor,&info,3,NPC_TRACKING_PLAYER_AUTO_TURN);
    assert(random_calls==3 && turns==1 && actor.shape.rot.y==20000);
    info.talkState=1; actor.shape.rot.y=0;
    ChildRouteSprite_TrackBody(&actor,&info,3,NPC_TRACKING_PLAYER_AUTO_TURN);
    assert(turns==2 && actor.shape.rot.y==20000);
    info.talkState=0; info.trackPos.z=200;
    ChildRouteSprite_TrackBody(&actor,&info,3,NPC_TRACKING_PLAYER_AUTO_TURN);
    assert(info.autoTurnTimer==0 && info.autoTurnState==0 && turns==2);
    return 0;
}
''')

    def test_changed_source_hook_is_rejected(self):
        rel, source = self.source('En_Go2')
        with self.assertRaises(ValueError):
            route.adapt(rel, source.replace('Actor_UpdateFidgetTables(', 'Changed_FidgetTables('))

    def test_kakariko_gate_preserves_open_wait_and_close_handshake(self):
        source = (OOT / route.GATE_SOURCES[0]).read_text(encoding='utf-8')
        names = ('func_8087828C', 'func_80878300', 'func_808783AC', 'func_808783D4', 'BgGateShutter_Update')
        self.run_c(r'''
#include <assert.h>
typedef struct { struct { struct { float x,y,z; } pos; } world; } Actor;
typedef struct { int unused; } PlayState;
typedef struct BgGateShutter {
    struct { Actor actor; } dyna; int openingState, unk_178;
    void (*actionFunc)(struct BgGateShutter*,PlayState*);
} BgGateShutter;
enum { INFTABLE_76, NA_SE_EV_METALGATE_OPEN, NA_SE_EV_BRIDGE_OPEN_STOP, SFX_FLAG=0 };
static int letter_flag, stops;
#define GET_INFTABLE(x) (letter_flag)
static void Actor_PlaySfx(Actor* actor,int id) { if(id==NA_SE_EV_BRIDGE_OPEN_STOP) ++stops; }
static void Math_ApproachF(float* value,float target,float fraction,float max) {
    float step=(target-*value)*fraction; if(step>max) step=max; if(step< -max) step=-max; *value+=step;
}
void func_8087828C(BgGateShutter*,PlayState*);
void func_80878300(BgGateShutter*,PlayState*);
void func_808783AC(BgGateShutter*,PlayState*);
void func_808783D4(BgGateShutter*,PlayState*);
''' + '\n'.join(function(source, name) for name in names) + r'''
int main(void) {
    PlayState play={0}; BgGateShutter gate={0}; gate.dyna.actor.world.pos.x=91;
    gate.actionFunc=func_8087828C; gate.openingState=1;
    BgGateShutter_Update((Actor*)&gate,&play);
    assert(gate.unk_178==2 && gate.dyna.actor.world.pos.x==91);
    BgGateShutter_Update((Actor*)&gate,&play); assert(gate.dyna.actor.world.pos.x==91);
    for(int i=0;i<125;i++) BgGateShutter_Update((Actor*)&gate,&play);
    assert(gate.dyna.actor.world.pos.x< -89 && gate.openingState==0 && stops==1);
    letter_flag=1; gate.openingState=1;
    BgGateShutter_Update((Actor*)&gate,&play); assert(gate.actionFunc==func_8087828C);
    gate.openingState= -1;
    for(int i=0;i<125;i++) BgGateShutter_Update((Actor*)&gate,&play);
    assert(gate.dyna.actor.world.pos.x==91 && gate.openingState==0 && stops==2);
    return 0;
}
''')


if __name__ == '__main__':
    unittest.main()
