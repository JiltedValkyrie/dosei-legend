"""Host prop identity through the real Player pickup action and detach."""
from pathlib import Path
import subprocess
import tempfile
import unittest
from test_fx32 import ROOT, host_flags, compiler_env
from test_graphics_backend import function


class PlayerHostCarry(unittest.TestCase):
    def test_pickup_attach_release_and_cancel(self):
        source = ROOT / 'build/oot-core/decomp/src/overlays/actors/ovl_player_actor/z_player.cpp'
        code = r'''
#include "ultra64.h"
#include "play_state.h"
#include "player.h"
#include "oot_core_api.h"
#include "z_lib.h"
#include "item.h"
#include "player_host_carry.h"
extern "C" int printf(const char*, ...);
#define CHECK(x) do { if (!(x)) { printf("line %d: %s\n", __LINE__, #x); return 1; } } while(0)
static int frame;
f32 Actor_WorldDistXZToActor(Actor*, Actor*) { return FXL(20.0f); }
s16 Actor_WorldYawTowardActor(Actor*, Actor*) { return -0x8000; }
static int offers;
static f32 offerXz, offerY;
s32 Actor_OfferGetItem(Actor* a, PlayState* play, s32, f32 xz, f32 y) {
    ++offers; offerXz = xz; offerY = y;
    GET_PLAYER(play)->interactRangeActor = a; return 1;
}
s32 Player_DecelerateToZero(Player*) { return 1; }
s32 LinkAnimation_Update(PlayState*, SkelAnime*) { return 0; }
s32 LinkAnimation_OnFrame(SkelAnime*, f32 f) { return frame == (int)f; }
s32 Math_ScaledStepToS(s16*, s16, s16) { return 0; }
void func_80839F90(Player*, PlayState*) {}
void func_80835688(Player*, PlayState*) {}
s32 func_80835644(PlayState*, Player*, Actor* a) { return !a; }
int Player_HoldsHookshot(Player*) { return 0; }
s32 Player_GetExplosiveHeld(Player*) { return -1; }
void Player_InitItemAction(PlayState*, Player*, s32) {}
''' + function(source, 'void Player_Action_80846050(Player* this, PlayState* play) {') + '\n' + function(source, 'void Player_DetachHeldActor(PlayState* play, Player* this) {')
        code += r'''
int main() {
    static Player p;
    static PlayState play;
    play.actorCtx.actorLists[ACTORCAT_PLAYER].head = &p.actor;
    int io[7] = {123, ACTOR_EN_ISHI, 10, 0, 20, 200, 0};
    CHECK(OotCore_CarryCommand(&play, OOT_CORE_TOOL_CARRY_OFFER, io));
    OotCore_CarryOffer(&play);
    CHECK(p.interactRangeActor && p.interactRangeActor->update);
    /* EnIshi_Wait small-rock offer range, not a host guess. */
    CHECK(offers == 1 && offerXz == FXL(50.0f) && offerY == FXL(10.0f));
    CHECK(!OotCore_CarryCommand(&play, OOT_CORE_TOOL_CARRY_READ, io));
    /* Source admission sets this before its put-away/pickup animation. */
    p.stateFlags1 = PLAYER_STATE1_CARRYING_ACTOR;
    CHECK(OotCore_CarryCommand(&play, OOT_CORE_TOOL_CARRY_READ, io) == 1);
    io[0] = 999;
    CHECK(!OotCore_CarryCommand(&play, OOT_CORE_TOOL_CARRY_OFFER, io));
    frame = 3; Player_Action_80846050(&p, &play);
    CHECK(!p.heldActor);
    frame = 4; Player_Action_80846050(&p, &play);
    CHECK(p.heldActor && p.heldActor->parent == &p.actor);
    OotCore_CarryAfter(&play);
    CHECK(OotCore_CarryCommand(&play, OOT_CORE_TOOL_CARRY_READ, io) == 2);
    CHECK(io[0] == 123);
    p.heldActor->world.pos.x = 30;
    p.heldActor->speed = FXL(10.0f);
    p.heldActor->velocity.y = FXL(20.0f);
    Player_DetachHeldActor(&play, &p);
    CHECK(OotCore_CarryCommand(&play, OOT_CORE_TOOL_CARRY_READ, io) == 3);
    CHECK(io[1] == 30 && io[5] == 2560 && io[6] == 5120);
    CHECK(!OotCore_CarryCommand(&play, OOT_CORE_TOOL_CARRY_READ, io));
    /* ObjTsubo_Idle: own +/-60 deg gate on Player's movement yaw, 30/30. */
    io[0] = 456; io[1] = ACTOR_OBJ_TSUBO;
    OotCore_CarryCommand(&play, OOT_CORE_TOOL_CARRY_OFFER, io);
    p.actor.world.rot.y = 0x3000;
    offers = 0; OotCore_CarryOffer(&play);
    CHECK(!offers && !p.interactRangeActor);
    p.actor.world.rot.y = 0x2000;
    OotCore_CarryOffer(&play);
    CHECK(offers == 1 && offerXz == FXL(30.0f) && offerY == FXL(30.0f));
    p.stateFlags1 = PLAYER_STATE1_CARRYING_ACTOR;
    frame = 4; Player_Action_80846050(&p, &play);
    OotCore_CarryCommand(&play, OOT_CORE_TOOL_CARRY_CANCEL, 0);
    CHECK(!p.heldActor && !p.actor.child && !p.interactRangeActor);
    CHECK(!(p.stateFlags1 & PLAYER_STATE1_CARRYING_ACTOR));
    /* Large rock: 80/20; Player's lift handler gates strength. */
    io[0] = 789; io[1] = ACTOR_EN_ISHI; io[6] = 1;
    OotCore_CarryCommand(&play, OOT_CORE_TOOL_CARRY_OFFER, io);
    offers = 0; OotCore_CarryOffer(&play);
    CHECK(offers == 1 && offerXz == FXL(80.0f) && offerY == FXL(20.0f));
    return 0;
}
'''
        compiler, env = compiler_env()
        with tempfile.TemporaryDirectory() as directory:
            cpp, exe = Path(directory) / 'carry.cpp', Path(directory) / 'carry'
            cpp.write_text(code)
            result = subprocess.run([compiler, *host_flags(), str(cpp), '-o', str(exe)],
                                    env=env, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            result = subprocess.run([str(exe)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
