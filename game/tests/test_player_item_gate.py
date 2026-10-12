"""Live Debug item gate reads use the actual Player/Save/Play ABI."""
from pathlib import Path
import subprocess
import tempfile
import unittest

from test_fx32 import ROOT, host_flags, compiler_env
from test_graphics_backend import function


class PlayerItemGate(unittest.TestCase):
    def test_live_gate_truth_and_read_only_formatter(self):
        views = ROOT / 'oot-core/src/oot_core_views.cpp'
        code = r'''
#include "ultra64.h"
#include "play_state.h"
#include "player.h"
#include "save.h"
#include "oot_core_api.h"
extern "C" int printf(const char*, ...);
#define CHECK(c) do { if (!(c)) { printf("line %d: %s\n", __LINE__, #c); return 1; } } while (0)
SaveContext gSaveContext;
PlayState* gOotCorePlay;
unsigned short gOotCoreInputTrace[6];
static const OotCoreDrawItem* sItemsView;
static int sCanUpdate = 1;
int Player_CanUpdateItems(Player*) { return sCanUpdate; }
int Player_HoldsHookshot(Player* p) { return p->heldItemAction == PLAYER_IA_HOOKSHOT; }
unsigned int OotCore_TalkState(void) { return 0; }
int OotCore_DrawItems(const OotCoreDrawItem**) { return 0; }
''' + function(views, 'static u32 OotCore_ItemGateMask(')
        code += '\n' + function(views, 'const char* OotCore_DebugText(')
        code += r'''
static PlayState play;
static Player player;
static void clear_bytes(void* object, unsigned size) {
    unsigned char* p = (unsigned char*)object;
    while (size--) *p++ = 0;
}
static int same_bytes(const void* a, const void* b, unsigned size) {
    const unsigned char* x = (const unsigned char*)a;
    const unsigned char* y = (const unsigned char*)b;
    while (size--) if (*x++ != *y++) return 0;
    return 1;
}
static int same_text(const char* a, const char* b) {
    while (*a && *a == *b) { ++a; ++b; }
    return *a == *b;
}
static void reset() {
    clear_bytes(&play, sizeof(play));
    clear_bytes(&player, sizeof(player));
    clear_bytes(&gSaveContext, sizeof(gSaveContext));
    play.actorCtx.actorLists[ACTORCAT_PLAYER].head = &player.actor;
    player.actor.category = ACTORCAT_PLAYER;
    player.heldItemId = ITEM_NONE;
    player.heldItemAction = player.itemAction = PLAYER_IA_NONE;
    gSaveContext.save.info.playerData.health = 0x30;
    gSaveContext.save.info.equips.buttonItems[1] = ITEM_SLINGSHOT;
    gSaveContext.buttonStatus[1] = BTN_ENABLED;
    gOotCorePlay = &play;
    sCanUpdate = 1;
}
#define GATE(bit, statement) do { reset(); statement; CHECK(OotCore_ItemGateMask(&play, &player) == (1u << (bit))); } while (0)
int main() {
    CHECK(OotCore_DebugText()[0] == 0);
    reset(); CHECK(OotCore_ItemGateMask(&play, &player) == 0);
    GATE(0, sCanUpdate = 0);
    GATE(1, player.actor.category = ACTORCAT_NPC);
    GATE(2, player.stateFlags1 = PLAYER_STATE1_START_CHANGING_HELD_ITEM);
    GATE(3, player.itemAction = PLAYER_IA_SLINGSHOT);
    player.stateFlags1 |= PLAYER_STATE1_SHIELDING;
    CHECK(OotCore_ItemGateMask(&play, &player) == 0);
    player.itemAction = player.heldItemAction;
    CHECK(OotCore_ItemGateMask(&play, &player) == 0);
    GATE(4, gSaveContext.save.info.playerData.health = 0);
    GATE(5, play.csCtx.state = CS_STATE_RUN);
    GATE(6, player.csAction = PLAYER_CSACTION_1);
    GATE(7, play.shootingGalleryStatus = 1);
    GATE(8, play.activeCamId = CAM_ID_SUB_FIRST);
    GATE(9, play.transitionTrigger = TRANS_TRIGGER_START);
    GATE(10, gSaveContext.timerState = TIMER_STATE_STOP);
    GATE(11, player.stateFlags1 = PLAYER_STATE1_CARRYING_ACTOR);
    GATE(11, player.stateFlags1 = PLAYER_STATE1_29);
    GATE(12, player.heldItemAction = player.itemAction = PLAYER_IA_HOOKSHOT);
    player.heldActor = &player.actor;
    CHECK(OotCore_ItemGateMask(&play, &player) == 0);
    GATE(13, gSaveContext.buttonStatus[1] = BTN_DISABLED);
    GATE(13, gSaveContext.save.info.equips.buttonItems[1] = ITEM_NONE);
    GATE(14, player.stateFlags1 = PLAYER_STATE1_DEAD);
    GATE(14, player.stateFlags1 = PLAYER_STATE1_0);
    GATE(15, player.stateFlags1 = PLAYER_STATE1_27);

    reset();
    gOotCoreInputTrace[0] = 0x0002;
    CHECK(same_text(OotCore_DebugText(), "p0002 iFF/00/00 g0000 c06/00 f00000000"));
    // New live item state appears even when there was no subsequent input edge.
    player.heldItemId = ITEM_SLINGSHOT;
    player.heldItemAction = player.itemAction = PLAYER_IA_SLINGSHOT;
    const char* text = OotCore_DebugText();
    CHECK(text[7] == '0' && text[8] == '6');
    CHECK(text[1] == '0' && text[4] == '2');
    // Every field is width bounded, with a terminator inside the old buffer.
    gOotCoreInputTrace[0] = 0xFFFF;
    player.stateFlags1 = 0xFFFFFFFF;
    player.heldItemId = player.heldItemAction = player.itemAction = -1;
    text = OotCore_DebugText();
    unsigned length = 0; while (text[length] && length < 40) ++length;
    CHECK(length == 38);
    // This diagnostic must never change admission, input, or source state.
    static PlayState beforePlay;
    static Player beforePlayer;
    static SaveContext beforeSave;
    beforePlay = play; beforePlayer = player; beforeSave = gSaveContext;
    OotCore_DebugText();
    CHECK(same_bytes(&beforePlay, &play, sizeof(play)));
    CHECK(same_bytes(&beforePlayer, &player, sizeof(player)));
    CHECK(same_bytes(&beforeSave, &gSaveContext, sizeof(gSaveContext)));
    CHECK(gOotCoreInputTrace[0] == 0xFFFF);
    return 0;
}
'''
        compiler, env = compiler_env()
        with tempfile.TemporaryDirectory() as directory:
            cpp, exe = Path(directory) / 'gate.cpp', Path(directory) / 'gate'
            cpp.write_text(code)
            result = subprocess.run([compiler, *host_flags(), '-DPLAYER_SOURCE=1',
                                     str(cpp), '-o', str(exe)], env=env,
                                    capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            result = subprocess.run([str(exe)], capture_output=True, text=True, timeout=30)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == '__main__':
    unittest.main()
