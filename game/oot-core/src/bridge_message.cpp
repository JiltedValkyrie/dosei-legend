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
#include "player.h"
#include "save.h"
#include "item.h"
#include "controller.h"
#include "environment.h"

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

/* ---- z_parameter.c: Saturn HUD draws the A/B labels; Player picks A ---- */
void Interface_ChangeHudVisibilityMode(u16 hudVisibilityMode) { /* STUB */
}
u8 gOotCoreDoAction = DO_ACTION_NONE;
void Interface_SetDoAction(PlayState* play, u16 action) { /* HOST: player_view -> Saturn HUD */
    gOotCoreDoAction = (u8)action;
}
void Interface_LoadActionLabelB(PlayState* play, u16 action) { /* STUB */
}

/* ---- audio: message SFX and Ocarina notes to the host PCM bank ---- */
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

static OcarinaStaff sOcarinaStaff, sPlaybackStaff;
static u16 sSongMask;
static u8 sNotes[8], sNoteCount, sPlaybackSong, sPlaybackTick, sSoundedNote;
static u8 sInstrument, sOcarinaActive, sCompletedSong, sListening;
OcarinaNote* gScarecrowLongSongPtr;
u8* gScarecrowSpawnSongPtr;
/* src/audio/game/general.c gOcarinaSongButtons. Button order is A, down,
 * right, left, up. Timing/bend/vibrato remain a Saturn approximation. */
OcarinaSongButtons gOcarinaSongButtons[OCARINA_SONG_MAX] = {
    {6,{0,4,3,2,3,2}}, {8,{1,0,1,0,2,1,2,1}}, {5,{0,1,2,2,3}},
    {6,{0,1,0,2,1,0}}, {7,{3,2,2,0,3,2,1}}, {6,{4,2,4,2,3,4}},
    {6,{1,2,3,1,2,3}}, {6,{4,3,2,4,3,2}}, {6,{3,4,2,3,4,2}},
    {6,{2,1,4,2,1,4}}, {6,{2,0,1,2,0,1}}, {6,{0,1,4,0,1,4}},
    {8,{0}}, {0,{0}}
};

void AudioOcarina_Start(u16 ocarinaFlags) {
    sSongMask = ocarinaFlags & 0x0fff;
    sListening = 1;
    sNoteCount = 0;
    sOcarinaStaff.buttonIndex = OCARINA_BTN_INVALID;
    sOcarinaStaff.state = 0xfe;
    sOcarinaStaff.pos = 0;
}
void AudioOcarina_SetInstrument(u8 ocarinaInstrumentId) {
    sInstrument = ocarinaInstrumentId;
    if (!sInstrument) { sSongMask = 0; sListening = 0; }
}
void AudioOcarina_SetPlaybackSong(s8 songIndexPlusOne, s8 playbackState) {
    sPlaybackSong = songIndexPlusOne > 0 && songIndexPlusOne <= 12 ? songIndexPlusOne - 1 : 0xff;
    sPlaybackTick = 0;
    sPlaybackStaff.pos = 0;
    sPlaybackStaff.state = sPlaybackSong < 12 && playbackState ? 1 : 0;
}
void AudioOcarina_SetRecordingState(u8 recordingState) {
    /* Scarecrow recording/storage is not yet imported. Reject explicitly. */
    sOcarinaStaff.state = recordingState ? OCARINA_RECORD_REJECTED : OCARINA_RECORD_OFF;
}
OcarinaStaff* AudioOcarina_GetRecordingStaff(void) {
    return &sOcarinaStaff;
}
OcarinaStaff* AudioOcarina_GetPlayingStaff(void) {
    return &sOcarinaStaff;
}
OcarinaStaff* AudioOcarina_GetPlaybackStaff(void) {
    return &sPlaybackStaff;
}
void AudioOcarina_MemoryGameInit(u8 minigameRound) {
}
s32 AudioOcarina_MemoryGameNextNote(void) {
    return 1; /* no generated next note: memory game remains unsupported */
}

extern PlayState* gOotCorePlay;
void OotCore_SunSongStart(PlayState* play);
void OotCore_OcarinaScene(PlayState* play) {
    static const u8 restrictions[][3] = {
#include "../../build/oot-core/ocarina_restrictions.inc"
    };
    for (unsigned i=0;restrictions[i][0]!=0xff;++i) if (restrictions[i][0]==play->sceneId) {
        play->interfaceCtx.restrictions.ocarina = (restrictions[i][1] >> 2) & 3;
        play->interfaceCtx.restrictions.warpSongs = restrictions[i][1] & 3;
        play->interfaceCtx.restrictions.sunsSong = restrictions[i][2] >> 6;
        break;
    }
}
/* C NPC placement/quest callbacks use the source text/page engine. */
static unsigned int sNpcText;
unsigned int OotCore_NpcText(unsigned int command) {
    PlayState* play = gOotCorePlay;
    if (!play) return 0;
    if (command & 0x10000u) {
        if (!sNpcText && play->msgCtx.msgMode != MSGMODE_NONE) return 0;
        if (sNpcText && play->msgCtx.msgMode != MSGMODE_NONE)
            Message_ContinueTextbox(play, command & 0xffffu);
        else Message_StartTextbox(play, command & 0xffffu, NULL);
        sNpcText = 1;
    } else if (command & 0x20000u) {
        if (sNpcText && play->msgCtx.msgMode != MSGMODE_NONE) Message_CloseTextbox(play);
        sNpcText = 0;
    }
    return sNpcText;
}
void OotCore_NpcTextStep(PlayState* play) {
    unsigned state;
    if (sNpcText != 1) return;
    state = Message_GetState(&play->msgCtx);
    if (state == TEXT_STATE_CHOICE && Message_ShouldAdvance(play)) {
        sNpcText = 4u | ((unsigned)play->msgCtx.choiceIndex << 8);
    } else if (state == TEXT_STATE_EVENT && Message_ShouldAdvance(play)) {
        Message_CloseTextbox(play);
    } else if (state == TEXT_STATE_CLOSING || play->msgCtx.msgMode == MSGMODE_NONE) {
        sNpcText = 2;
    }
}

void OotCore_OcarinaReset(void) {
    sNpcText = 0;
    sOcarinaActive = sSongMask = sInstrument = sCompletedSong = sSoundedNote = sListening = 0;
    sPlaybackStaff.state = 0;
}

/* command 0 state, 1 start, 2 consume note (1..5), 3 completed song (1..12).
 * State bit 0 owns Link; bit 1 accepts notes; bits 8..15 = last song + 1. */
unsigned int OotCore_Ocarina(unsigned int command) {
    PlayState* play = gOotCorePlay;
    Player* player = play ? GET_PLAYER(play) : NULL;
    if (command == 2 || command == 3) {
        u8 result = command == 2 ? sSoundedNote : sCompletedSong;
        if (command == 2) sSoundedNote = 0; else sCompletedSong = 0;
        return result;
    }
    if (!play || !player) return 0;
    if (command == 4) {
        return gTimeSpeed != 400 && !play->msgCtx.disableSunsSong &&
            GET_EVENTINF_INGO_RACE_STATE() != INGO_RACE_STATE_HORSE_RENTAL_PERIOD;
    }
    if (command == 5) {
        OotCore_SunSongStart(play);
        return gSaveContext.sunsSongState != SUNSSONG_INACTIVE;
    }
    if (command == 1) {
        if (sOcarinaActive || play->msgCtx.msgMode != MSGMODE_NONE ||
            play->interfaceCtx.restrictions.ocarina ||
            (INV_CONTENT(ITEM_OCARINA_FAIRY) != ITEM_OCARINA_FAIRY &&
             INV_CONTENT(ITEM_OCARINA_FAIRY) != ITEM_OCARINA_OF_TIME)) return 0;
        OotCore_OcarinaReset();
        sOcarinaActive = 1;
        player->stateFlags2 |= PLAYER_STATE2_USING_OCARINA;
        /* Source song-check actors observe 24 after the start animation. */
        player->stateFlags2 |= PLAYER_STATE2_24;
        Message_StartOcarina(play, OCARINA_ACTION_FREE_PLAY);
    }
    return sOcarinaActive ? 1u | (sListening ? 2u : 0u) |
        (play->msgCtx.lastPlayedSong < 12 ? (play->msgCtx.lastPlayedSong + 1u) << 8 : 0u) : 0;
}

void OotCore_OcarinaStep(PlayState* play) {
    Player* player = GET_PLAYER(play);
    unsigned i, j, note = 5;
    u16 press = play->state.input[0].press.button;
    if (!player) return;
    if (sOcarinaActive) {
        /* The C player owns free play, including cancellation during the
         * result/playback phases where z_message does not check B. */
        if ((press & BTN_B) &&
            (play->msgCtx.ocarinaAction == OCARINA_ACTION_FREE_PLAY ||
             play->msgCtx.ocarinaAction == OCARINA_ACTION_FREE_PLAY_DONE)) {
            OotCore_OcarinaReset();
            player->stateFlags2 &= ~(PLAYER_STATE2_USING_OCARINA | PLAYER_STATE2_23 | PLAYER_STATE2_24 | PLAYER_STATE2_25);
            play->msgCtx.ocarinaMode = OCARINA_MODE_04;
            Message_CloseTextbox(play);
            return;
        }
        if (play->msgCtx.ocarinaMode == OCARINA_MODE_02 && play->msgCtx.lastPlayedSong < 6) {
            /* z_player.c sWarpSongEntrances / Environment_WarpSongLeave.
             * The common transition loader preserves destination spawn/yaw.
             * Warp particles/camera choreography remain unimported. */
            static const u16 entrance[6] = {0x0600,0x04f6,0x0604,0x01f1,0x0568,0x05f4};
            play->nextEntranceIndex = entrance[play->msgCtx.lastPlayedSong];
            play->transitionTrigger = TRANS_TRIGGER_START;
            play->msgCtx.ocarinaMode = OCARINA_MODE_04;
        }
        if (play->msgCtx.msgMode == MSGMODE_NONE &&
            (play->msgCtx.ocarinaMode == OCARINA_MODE_04 ||
             play->msgCtx.ocarinaAction == OCARINA_ACTION_FREE_PLAY_DONE)) {
            if (play->msgCtx.ocarinaAction == OCARINA_ACTION_FREE_PLAY_DONE && play->msgCtx.lastPlayedSong < 12)
                sCompletedSong = play->msgCtx.lastPlayedSong + 1;
            sOcarinaActive = sListening = sInstrument = sSoundedNote = 0;
            sPlaybackStaff.state = 0;
            player->stateFlags2 &= ~(PLAYER_STATE2_USING_OCARINA | PLAYER_STATE2_23 | PLAYER_STATE2_24 | PLAYER_STATE2_25);
            play->msgCtx.ocarinaMode = OCARINA_MODE_04;
        }
    }
    if (sPlaybackStaff.state && sPlaybackSong < 12 && ++sPlaybackTick >= 8) {
        sPlaybackTick = 0;
        if (sPlaybackStaff.pos >= gOcarinaSongButtons[sPlaybackSong].numButtons) sPlaybackStaff.state = 0;
        else {
            sPlaybackStaff.buttonIndex = gOcarinaSongButtons[sPlaybackSong].buttonsIndex[sPlaybackStaff.pos++];
            sSoundedNote = sPlaybackStaff.buttonIndex + 1;
        }
    }
    if (!sListening || !sInstrument || sOcarinaStaff.state < 12) return;
    if (press & BTN_A) note = 0;
    else if (press & BTN_CDOWN) note = 1;
    else if (press & BTN_CRIGHT) note = 2;
    else if (press & BTN_CLEFT) note = 3;
    else if (press & BTN_CUP) note = 4;
    if (note == 5) return;
    if (sNoteCount == 8) { for (i=1;i<8;++i) sNotes[i-1]=sNotes[i]; --sNoteCount; }
    sNotes[sNoteCount++] = note;
    sSoundedNote = note + 1;
    sOcarinaStaff.buttonIndex = note;
    sOcarinaStaff.pos = sNoteCount;
    for (i=0;i<12;++i) if (sSongMask & (1u<<i)) {
        unsigned n = gOcarinaSongButtons[i].numButtons;
        if (n > sNoteCount) continue;
        for (j=0;j<n && sNotes[sNoteCount-n+j] == gOcarinaSongButtons[i].buttonsIndex[j];++j) {}
        if (j == n) { sOcarinaStaff.state = i; sSongMask = 0; sListening = 0; break; }
    }
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
