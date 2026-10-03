/*
 * NPC batch bridges (Lon Lon Ranch actors and later NPC imports). Tags as
 * bridge_play.cpp: REAL / HOST / STUB.
 */
#include "oot_prelude.h"
#include "ultra64.h"
#include "audio.h"
#include "environment.h"
#include "interface.h"
#include "letterbox.h"
#include "one_point_cutscene.h"
#include "play_state.h"
#include "save.h"
#include "seqcmd.h"
#include "oot_core_host.h"

extern const OotCoreHost* gOotCoreHost;

/* ---- z_parameter.c ---- */
s32 Inventory_HasEmptyBottle(void) { /* REAL */
    s32 slot;

    for (slot = SLOT_BOTTLE_1; slot <= SLOT_BOTTLE_4; slot++) {
        if (gSaveContext.save.info.inventory.items[slot] == ITEM_BOTTLE_EMPTY) {
            return true;
        }
    }
    return false;
}

void Rupees_ChangeBy(s16 rupeeChange) { /* HOST: the C save owns rupees */
    if (gOotCoreHost != NULL && gOotCoreHost->rupees_change != NULL) {
        gOotCoreHost->rupees_change(rupeeChange);
    }
}

void Interface_SetTimer(s16 seconds) { /* STUB: no minigame timer HUD yet */
}

/* ---- audio: music is the C side's; these change sequences ---- */
void Audio_PlaySfxRandom(Vec3f* pos, u16 baseSfxId, u8 randLim) { /* HOST: base sfx */
    if (gOotCoreHost != NULL && gOotCoreHost->play_sfx != NULL) {
        gOotCoreHost->play_sfx(baseSfxId, pos ? (s32)pos->x : 0, pos ? (s32)pos->y : 0, pos ? (s32)pos->z : 0);
    }
}
void Audio_QueueSeqCmd(u32 cmd) { /* STUB: C music owns sequences */
}
void Audio_SetFastTempoForTimedMinigame(void) { /* STUB */
}
void Audio_ToggleMalonSinging(u8 malonSingingDisabled) { /* STUB: no Malon song channel */
}
void Audio_UpdateMalonSinging(f32 dist, u16 seqId) { /* STUB */
}
void func_800F5ACC(u16 seqId) { /* STUB: play sequence (C music) */
}
void func_800F5B58(void) { /* STUB: restore sequence */
}
void Environment_ForcePlaySequence(u16 seqId) { /* STUB */
}

/* ---- camera / letterbox / one-point shots: the C camera owns the view ---- */
void Letterbox_SetSizeTarget(s32 target) { /* STUB */
}
s16 OnePointCutscene_Init(PlayState* play, s16 csId, s16 timer, Actor* actor, s16 parentCamId) { /* STUB */
    return CAM_ID_NONE;
}
s16 Play_CreateSubCamera(PlayState* this) { /* STUB: no sub cameras */
    return CAM_ID_NONE;
}
s16 Play_ChangeCameraStatus(PlayState* this, s16 camId, s16 status) { /* STUB */
    return 0;
}
void Play_ClearCamera(PlayState* this, s16 camId) { /* STUB */
}
s32 Play_SetCameraAtEye(PlayState* this, s16 camId, Vec3f* at, Vec3f* eye) { /* STUB */
    return 0;
}
