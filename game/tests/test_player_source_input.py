"""Run live Player input/camera adapters with the actual decomp ABI."""
from pathlib import Path
import subprocess
import tempfile
import unittest

from test_fx32 import ROOT, host_flags, compiler_env
from test_graphics_backend import function


class PlayerSourceInput(unittest.TestCase):
    def test_source_tick_taps_release_rearm_cancel_and_camera(self):
        api = ROOT / 'oot-core/src/oot_core_api.cpp'
        bridge = ROOT / 'oot-core/src/bridge_player_source.cpp'
        code = r'''
#include "ultra64.h"
#include "play_state.h"
#include "player.h"
#include "save.h"
#include "camera.h"
#include "message.h"
#include "libu64/pad.h"
#include "controller.h"
#include "player_tap_aim.h"
extern "C" int printf(const char*, ...);
#define CHECK(c) do { if (!(c)) { printf("line %d: %s\n", __LINE__, #c); return 1; } } while (0)
SaveContext gSaveContext;
static Input sHostInput;
unsigned short gOotCoreInputTrace[6];
static s8 sPendingStickY, sHeldStickY;
static PlayerTapAim sTapAim;
int Player_InCsMode(PlayState*) { return 0; }
int Player_HoldsHookshot(Player* p) { return p->heldItemAction == PLAYER_IA_HOOKSHOT; }
/* Carry adapter is exercised separately with the source pickup action. */
void OotCore_CarryReset() {}
void OotCore_CarryOffer(PlayState*) {}
''' + '\n'.join(function(bridge, name) for name in (
            'void OotCore_PlayerInputReset(', 'void OotCore_PlayerInput('))
        code += '\n' + '\n'.join(function(api, name) for name in (
            'static void reset_input(void) {', 'static void oot_core_set_input(',
            'static void consume_input('))
        code += '\n' + function(ROOT / 'oot-core/src/bridge_play.cpp', 's32 Camera_RequestMode(')
        code += r'''
int main() {
    static PlayState play;
    static Player player;
    play.actorCtx.actorLists[ACTORCAT_PLAYER].head = &player.actor;
    Input* input = &play.state.input[0];
    /* A survives a skipped tick and cannot become an item-button press.
     * Keep evidence through the following release tick. */
    reset_input(); OotCore_PlayerInputReset();
    player.heldItemId = ITEM_NONE;
    player.heldItemAction = PLAYER_IA_NONE;
    player.actor.bgCheckFlags = BGCHECKFLAG_GROUND;
    oot_core_set_input(BTN_A, BTN_A, 0, 0);
    oot_core_set_input(0, 0, 0, 0);
    consume_input(&play);
    CHECK(input->press.button == BTN_A && input->cur.button == BTN_A);
    CHECK(gOotCoreInputTrace[0] == BTN_A && gOotCoreInputTrace[2] == ITEM_NONE);
    CHECK(gOotCoreInputTrace[4] == 0xFFFF && gOotCoreInputTrace[5] == 1);
    consume_input(&play);
    CHECK(input->press.button == 0 && gOotCoreInputTrace[0] == BTN_A);
    gSaveContext.save.info.equips.buttonItems[1] = ITEM_HOOKSHOT;
    gSaveContext.save.info.equips.buttonItems[2] = ITEM_BOW;
    gSaveContext.save.info.equips.buttonItems[3] = ITEM_SLINGSHOT;
    reset_input(); OotCore_PlayerInputReset();
    /* A press on the skipped 30 Hz tick survives until the 20 Hz update.
     * Tap is held for source ready animation despite physical release. */
    oot_core_set_input(BTN_CDOWN, BTN_CDOWN, 0, 0);
    oot_core_set_input(0, 0, 0, 0);
    consume_input(&play);
    CHECK(input->cur.button & BTN_CDOWN);
    CHECK(input->press.button == BTN_CDOWN);
    CHECK(sTapAim.button == BTN_CDOWN);
    player.stateFlags1 = PLAYER_STATE1_20 | PLAYER_STATE1_9;
    for (int i=0; i<20; ++i) {
        consume_input(&play);
        CHECK(input->cur.button & BTN_CDOWN);
        CHECK(input->press.button == 0);
    }
    /* Next tap releases once; second source update must not replay it. */
    oot_core_set_input(BTN_CDOWN, BTN_CDOWN, 0, 0);
    consume_input(&play);
    CHECK(!(input->cur.button & BTN_CDOWN));
    CHECK(!(input->press.button & BTN_CDOWN));
    CHECK(input->rel.button & BTN_CDOWN);
    player.stateFlags1 = PLAYER_STATE1_20; /* source shot consumed readiness */
    consume_input(&play);
    CHECK(input->cur.button & BTN_CDOWN);
    CHECK(input->press.button & BTN_CDOWN); /* request source rearm */
    player.stateFlags1 |= PLAYER_STATE1_9;
    oot_core_set_input(0, 0, 0, 0);
    consume_input(&play);
    CHECK(sTapAim.release == 0 && input->press.button == 0);
    CHECK(input->cur.button & BTN_CDOWN);
    /* B exits; Z-targeted shots keep ordinary source hold/release. */
    oot_core_set_input(BTN_B, BTN_B, 0, 0); consume_input(&play);
    CHECK(sTapAim.button == 0 && input->cur.button == BTN_B);
    oot_core_set_input(BTN_Z | BTN_CLEFT, BTN_CLEFT, 0, 0); consume_input(&play);
    CHECK(sTapAim.button == 0 && (input->cur.button & BTN_CLEFT));
    /* R press/release is source input too, and edges clear after consume. */
    oot_core_set_input(BTN_R, 0, 0, 0); consume_input(&play);
    CHECK(input->press.button & BTN_R);
    oot_core_set_input(0, 0, 0, 0); consume_input(&play);
    CHECK(input->rel.button & BTN_R);
    consume_input(&play); CHECK(input->rel.button == 0);
    /* Hook waiting for return: no C press can retract it prematurely. */
    OotCore_PlayerInputReset(); player.stateFlags1 = 0;
    player.heldItemAction = PLAYER_IA_HOOKSHOT;
    oot_core_set_input(BTN_CLEFT, BTN_CLEFT, 0, 0); consume_input(&play);
    player.stateFlags1 = PLAYER_STATE1_20 | PLAYER_STATE1_9;
    oot_core_set_input(0, 0, 0, 0); consume_input(&play);
    oot_core_set_input(BTN_CLEFT, BTN_CLEFT, 0, 0); consume_input(&play);
    CHECK(!(input->cur.button & BTN_CLEFT));
    player.stateFlags1 = PLAYER_STATE1_20;
    oot_core_set_input(0, 0, 0, 0);
    for (int i=0; i<20; ++i) {
        consume_input(&play); CHECK(!(input->press.button & BTN_CLEFT));
    }
    player.actor.child = &player.actor; /* returned by ArmsHook_AttachToPlayer */
    consume_input(&play); CHECK(input->press.button & BTN_CLEFT);
    player.stateFlags1 |= PLAYER_STATE1_9; consume_input(&play);
    CHECK(input->press.button == 0 && sTapAim.release == 0);
    /* Leaving first person/dying/dialogue cannot retain an item hold. */
    player.stateFlags1 = 0; consume_input(&play); CHECK(sTapAim.button == 0);
    oot_core_set_input(BTN_CRIGHT, BTN_CRIGHT, 0, 0); consume_input(&play);
    CHECK(sTapAim.button == BTN_CRIGHT);
    play.msgCtx.msgMode = MSGMODE_TEXT_DISPLAYING;
    oot_core_set_input(0, 0, 0, 0); consume_input(&play); CHECK(sTapAim.button == 0);
    reset_input(); OotCore_PlayerInputReset();
    CHECK(sHostInput.cur.button == 0 && sHostInput.prev.button == 0);
    /* Aim sensitivity changes only source first-person input. Repeated
     * source ticks use the original held sample, never halve it again. */
    play.msgCtx.msgMode = MSGMODE_NONE;
    player.stateFlags1 = PLAYER_STATE1_20;
    oot_core_set_input(0, 0, 80, -80);
    for (int i = 0; i < 4; ++i) {
        consume_input(&play);
        CHECK(input->rel.stick_x == 40 && input->rel.stick_y == -40);
    }
    oot_core_set_input(0, 0, -20, 10); consume_input(&play);
    CHECK(input->rel.stick_x == -10 && input->rel.stick_y == 5);
    player.stateFlags1 = 0;
    oot_core_set_input(0, 0, 80, -80); consume_input(&play);
    CHECK(input->rel.stick_x == 80 && input->rel.stick_y == -80);
    Camera camera = {};
    CHECK(Camera_RequestMode(&camera, CAM_MODE_AIM_ADULT) != CAM_MODE_NORMAL);
    CHECK(camera.mode == CAM_MODE_AIM_ADULT);
    CHECK(Camera_RequestMode(&camera, CAM_MODE_AIM_CHILD) != CAM_MODE_NORMAL);
    CHECK(Camera_RequestMode(&camera, CAM_MODE_FIRST_PERSON) != CAM_MODE_NORMAL);
    CHECK(Camera_RequestMode(&camera, CAM_MODE_NORMAL) == CAM_MODE_NORMAL);
    return 0;
}
'''
        compiler, env = compiler_env()
        with tempfile.TemporaryDirectory() as directory:
            cpp, exe = Path(directory) / 'input.cpp', Path(directory) / 'input'
            cpp.write_text(code)
            result = subprocess.run([compiler, *host_flags(), '-DPLAYER_SOURCE=1',
                                     str(cpp), '-o', str(exe)], env=env,
                                    capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            result = subprocess.run([str(exe)], capture_output=True, text=True, timeout=30)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == '__main__':
    unittest.main()
