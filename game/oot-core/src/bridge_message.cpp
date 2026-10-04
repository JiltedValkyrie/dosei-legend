/*
 * Route step 4 bridges: z_message runs for real in the blob; its Gfx goes to
 * a scratch display list (never executed) and the C side draws the text box
 * on VDP2 from msgCtx (oot_core_api.cpp message_view). Tags as bridge_play.cpp:
 * REAL / HOST / STUB.
 *
 * ROM: message text comes from the ROM's nes_message_data_static, loaded by
 * the host into a cart carve (set_text). The entry table offsets come from
 * the ROM's own sNesMessageEntryTable (tools/oot_core_import.py writes
 * build/oot-core/msg_syms.ld). Segment ROM starts are fake absolute VROM
 * bases (oot-core.ld); DmaMgr_RequestSync maps them back.
 */
#include "oot_prelude.h"
#include "ultra64.h"
#include "dma.h"
#include "gfx.h"
#include "kanji_tex.h"
#include "n64dd.h"
#include "message.h"
#include "ocarina.h"
#include "play_state.h"
#include "regs.h"
#include "segment_symbols.h"
#include "sfx.h"
#include "audio.h"
#include "view.h"
#include "interface.h"
#include "oot_core_host.h"

extern const OotCoreHost* gOotCoreHost;

/* ---- ROM text (host carve) ---- */
static const u8* sTextData;
static u32 sTextBytes;

void OotCore_SetText(const void* data, u32 bytes) {
    sTextData = (const u8*)data;
    sTextBytes = bytes;
}

/* VROM base of each fake segment (oot-core.ld OOT_VROM_*). */
#define VROM_NES_MESSAGE ((uintptr_t)_nes_message_data_staticSegmentRomStart)
#define VROM_SPAN 0x01000000u

s32 DmaMgr_RequestSync(void* ram, uintptr_t vrom, size_t size) { /* HOST: ROM text only */
    if (vrom >= VROM_NES_MESSAGE && vrom - VROM_NES_MESSAGE < VROM_SPAN) {
        u32 off = vrom - VROM_NES_MESSAGE;
        if (sTextData != NULL && off < sTextBytes) {
            if (size > sTextBytes - off) {
                size = sTextBytes - off;
            }
            for (u32 i = 0; i < size; i++) {
                ((u8*)ram)[i] = sTextData[off + i];
            }
            return 0;
        }
    }
    /* Font glyphs, icons, kanji: the VDP2 text box has its own font. */
    return 0;
}

s32 osRecvMesg(OSMesgQueue* mq, OSMesg* msg, s32 flag) { /* STUB: DMA is synchronous */
    return 0;
}

s32 KanjiTex_CodepointToOffset(s32 codepoint) { /* STUB: no kanji (English text) */
    return 0;
}

/* ---- code_n64dd / debug globals ---- */
n64ddStruct_80121220* B_80121220; /* NULL: no 64DD */
s32 gDebugCamEnabled;

/* ---- z_view.c: the message view only sets an ortho overlay ---- */
void View_Init(View* view, GraphicsContext* gfxCtx) { /* STUB */
}
void View_SetViewport(View* view, Viewport* viewport) { /* STUB */
}
s32 View_ApplyOrthoToOverlay(View* view) { /* STUB */
    return 1;
}

/* ---- z_parameter.c: the C HUD owns the A/B labels until z_parameter ---- */
void Interface_ChangeHudVisibilityMode(u16 hudVisibilityMode) { /* STUB */
}
void Interface_SetDoAction(PlayState* play, u16 action) { /* STUB */
}
void Interface_LoadActionLabelB(PlayState* play, u16 action) { /* STUB */
}

/* ---- audio: message sfx to the host PCM bank, ocarina absent ---- */
void Audio_PlaySfxIfNotInCutscene(u16 sfxId) { /* HOST */
    if (gOotCoreHost != NULL && gOotCoreHost->play_sfx != NULL) {
        gOotCoreHost->play_sfx(sfxId, 0, 0, 0);
    }
}
u8 Audio_IsSfxPlaying(u32 sfxId) { /* STUB: host one-shots are not tracked */
    return false;
}
void Audio_PlayFanfare(u16 seqId) { /* STUB: C music owns fanfares */
}
void Audio_SetSfxBanksMute(u16 muteMask) { /* STUB */
}

static OcarinaStaff sOcarinaStaff;
OcarinaNote* gScarecrowLongSongPtr;
u8* gScarecrowSpawnSongPtr;
OcarinaSongButtons gOcarinaSongButtons[OCARINA_SONG_MAX];

/* STUB (all): ocarina playing is not on Saturn yet (audio/game/ocarina.c). */
void AudioOcarina_Start(u16 ocarinaFlags) {
}
void AudioOcarina_SetInstrument(u8 ocarinaInstrumentId) {
}
void AudioOcarina_SetPlaybackSong(s8 songIndexPlusOne, s8 playbackState) {
}
void AudioOcarina_SetRecordingState(u8 recordingState) {
}
OcarinaStaff* AudioOcarina_GetRecordingStaff(void) {
    return &sOcarinaStaff;
}
OcarinaStaff* AudioOcarina_GetPlayingStaff(void) {
    return &sOcarinaStaff;
}
OcarinaStaff* AudioOcarina_GetPlaybackStaff(void) {
    return &sOcarinaStaff;
}
void AudioOcarina_MemoryGameInit(u8 minigameRound) {
}
s32 AudioOcarina_MemoryGameNextNote(void) {
    return 0;
}

/* ---- graph.c: scratch display lists for Message_Draw (never executed) ---- */
#define OVERLAY_GFX 256
#define POLY_OPA_GFX 8192
#define POLY_XLU_GFX 1024
/* In the host's play block (low work RAM), not the blob's cart carve. */
static Gfx* sOverlayGfx;
static Gfx* sPolyOpaGfx;
static Gfx* sPolyXluGfx;
#define OVERLAY_BYTES (OVERLAY_GFX * sizeof(Gfx))
#define POLY_OPA_BYTES (POLY_OPA_GFX * sizeof(Gfx))
#define POLY_XLU_BYTES (POLY_XLU_GFX * sizeof(Gfx))

u32 OotCore_GfxBytes(void) {
    return OVERLAY_BYTES + POLY_OPA_BYTES + POLY_XLU_BYTES;
}

void OotCore_GfxInit(void* mem) {
    sOverlayGfx = (Gfx*)mem;
    sPolyOpaGfx = (Gfx*)((u8*)mem + OVERLAY_BYTES);
    sPolyXluGfx = (Gfx*)((u8*)mem + OVERLAY_BYTES + POLY_OPA_BYTES);
}
static GraphicsContext sGfxCtx;

GraphicsContext* OotCore_GfxCtx(void) {
    return &sGfxCtx;
}

/* Graph_Update order: a fresh frame for each draw. */
void OotCore_GfxReset(void) {
    sGfxCtx.overlay.size = OVERLAY_BYTES;
    sGfxCtx.overlay.start = sOverlayGfx;
    sGfxCtx.overlay.p = sOverlayGfx;
    sGfxCtx.overlay.d = (u8*)sOverlayGfx + OVERLAY_BYTES;
    sGfxCtx.polyOpa.size = POLY_OPA_BYTES;
    sGfxCtx.polyOpa.start = sPolyOpaGfx;
    sGfxCtx.polyOpa.p = sPolyOpaGfx;
    sGfxCtx.polyOpa.d = (u8*)sPolyOpaGfx + POLY_OPA_BYTES;
    sGfxCtx.polyXlu.size = POLY_XLU_BYTES;
    sGfxCtx.polyXlu.start = sPolyXluGfx;
    sGfxCtx.polyXlu.p = sPolyXluGfx;
    sGfxCtx.polyXlu.d = (u8*)sPolyXluGfx + POLY_XLU_BYTES;
    sGfxCtx.polyXluBuffer = sPolyXluGfx;
    sGfxCtx.overlayBuffer = sOverlayGfx;
    sGfxCtx.polyOpaBuffer = sPolyOpaGfx;
}
