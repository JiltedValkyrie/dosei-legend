/*
 * Target link stubs for symbols the Phase 0 math slice references but the
 * slice never calls (z_lib's Sfx_* helpers, regs). Phase 1 replaces these
 * with real bridges to the Saturn audio/debug backends.
 */
#include "oot_prelude.h"
#include "ultra64.h"
#include "sfx.h"
#include "regs.h"

Vec3f gSfxDefaultPos;
f32 gSfxDefaultFreqAndVolScale;
s8 gSfxDefaultReverb;
RegEditor* gRegEditor;

void Audio_PlaySfxGeneral(u16 sfxId, Vec3f* pos, u8 token, f32* freqScale, f32* vol, s8* reverbAdd) {
}
