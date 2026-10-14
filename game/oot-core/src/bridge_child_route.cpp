/* Small source services needed by child-route NPCs. The original actions,
 * camera state and saved Biggoron clock remain authoritative in the core. */
#include "oot_prelude.h"
#include "camera.h"
#include "environment.h"
#include "save.h"
#include "oot_core_audio.h"

/* z_camera.c: these are state operations, independent of camera rendering. */
s16 Camera_SetStateFlag(Camera* camera, s16 stateFlag) {
    camera->stateFlags |= stateFlag;
    return camera->stateFlags;
}

s16 Camera_UnsetStateFlag(Camera* camera, s16 stateFlag) {
    camera->stateFlags &= ~stateFlag;
    return camera->stateFlags;
}

/* z_kankyo.c: preserve the original save field and reset semantics. */
s32 Environment_GetBgsDayCount(void) {
    return gSaveContext.save.bgsDayCount;
}

void Environment_ClearBgsDayCount(void) {
    gSaveContext.save.bgsDayCount = 0;
}

/* z_parameter.c: the beggar checks the four source bottle slots. */
s32 Inventory_HasSpecificBottle(u8 bottleItem) {
    s32 slot;
    for (slot = SLOT_BOTTLE_1; slot <= SLOT_BOTTLE_4; slot++) {
        if (gSaveContext.save.info.inventory.items[slot] == bottleItem) {
            return true;
        }
    }
    return false;
}

/* audio/game/general.c forwards this volume/fade pair to the main BGM
 * player. Saturn's backend receives the same pair at the frame boundary. */
void Audio_SetMainBgmVolume(u8 targetVol, u8 volFadeTimer) {
    OotCore_AudioRequest(OOT_CORE_AUDIO_MAIN_VOLUME,
                        (unsigned)targetVol | ((unsigned)volFadeTimer << 8));
}
