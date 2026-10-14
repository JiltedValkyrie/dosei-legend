/*
 * Target link stubs for symbols the Phase 0 math slice references but the
 * slice never calls (z_lib's Sfx_* helpers, regs). Phase 1 replaces these
 * with real bridges to the Saturn audio/debug backends.
 */
#include "oot_prelude.h"
#include "ultra64.h"
#include "sfx.h"
#include "regs.h"
#include "oot_core_host.h"

extern const OotCoreHost* gOotCoreHost;
extern void OotCore_OcarinaSfxStarted(u16 sfxId);
extern void OotCore_AudioSfxPitched(u16 sfxId, Vec3f* pos, f32 frequency);

Vec3f gSfxDefaultPos;
f32 gSfxDefaultFreqAndVolScale=FXL(1.0f);
s8 gSfxDefaultReverb;
RegEditor* gRegEditor;

void Audio_PlaySfxGeneral(u16 sfxId, Vec3f* pos, u8 token, f32* freqScale, f32* vol, s8* reverbAdd) { /* HOST */
    if (gOotCoreHost != NULL && gOotCoreHost->play_sfx != NULL) {
        OotCore_OcarinaSfxStarted(sfxId);
        OotCore_AudioSfxPitched(sfxId,pos,freqScale?*freqScale:FXL(1.0f));
    }
}
