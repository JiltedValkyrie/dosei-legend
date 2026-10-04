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

Vec3f gSfxDefaultPos;
f32 gSfxDefaultFreqAndVolScale;
s8 gSfxDefaultReverb;
RegEditor* gRegEditor;

void Audio_PlaySfxGeneral(u16 sfxId, Vec3f* pos, u8 token, f32* freqScale, f32* vol, s8* reverbAdd) { /* HOST */
    if (gOotCoreHost != NULL && gOotCoreHost->play_sfx != NULL) {
        gOotCoreHost->play_sfx(sfxId, pos ? (s32)pos->x : 0, pos ? (s32)pos->y : 0, pos ? (s32)pos->z : 0);
    }
}
