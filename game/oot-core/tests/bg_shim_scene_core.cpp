/* Core scene for bg_shim_scenario.c: Kokiri Forest blob in real z_bgcheck,
 * bg_* answered by src/bg_core_shim.c over oot_core_bg.cpp. */
#include "oot_prelude.h"
#include "ultra64.h"
#include "bgcheck.h"
#include "play_state.h"
#include "regs.h"
#include "segmented_address.h"
#include "oot_scene_blob.h"
#include "oot_core_host.h"
#include "oot_core_bg.h"

const OotCoreHost* gOotCoreHost;
PlayState* gOotCorePlay;
extern "C" const OotSceneBlob oot_scene_blob;
static PlayState sPlay;
static RegEditor sRegs;
uintptr_t gSegments[NUM_SEGMENTS];
extern "C" void OotCoreBg_SetPlay(PlayState* play);
extern "C" void bg_core_shim_set_api(const OotCoreBgApi* core);
extern "C" void bg_core_shim_scene_reset(void);

extern "C" void scene_init(const char*) {
    static u64 tha[0x100000 / 8];
    gRegEditor = &sRegs;
    sPlay.sceneId = SCENE_KOKIRI_FOREST;
    THA_Init(&sPlay.state.tha, tha, sizeof tha);
    BgCheck_Allocate(&sPlay.colCtx, &sPlay, (CollisionHeader*)oot_scene_blob.col_header);
    OotCoreBg_SetPlay(&sPlay);
    gOotCorePlay = &sPlay;
    bg_core_shim_set_api(OotCoreBg_Api());
}

extern "C" void scene_reenter(const char* col_file) {
    bg_core_shim_scene_reset();
    scene_init(col_file);
}
