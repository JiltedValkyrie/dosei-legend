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
#include "oot_core_audio.h"
#include "sprite_actor.h"
#include "segmented_address.h"

/* Q8 frame clocks use 32-bit arithmetic. Fx is only the existing ABI storage.
 * No skeleton reads, limb allocation, frame decoding or morph interpolation. */
static s32 sprite_q8(f32 value) {
#if OOT_CORE_HWFLOAT
    return (s32)(value * 256.0f);
#else
    static_assert(FX_FRAC == 16, "sprite clock ABI expects Q16 Fx storage");
    return value.v / 256;
#endif
}
static f32 sprite_frame(s32 value) {
#if OOT_CORE_HWFLOAT
    return value / 256.0f;
#else
    return Fx::raw(value * 256);
#endif
}

void OotCore_SpriteChange(SkelAnime* s, AnimationHeader* animation,
                         f32 speed, f32 start, f32 end, u8 mode) {
    AnimationHeader* header = (AnimationHeader*)SEGMENTED_TO_VIRTUAL(animation);
    s32 length = header->common.frameCount;
    if (length < 1) length = 1;
    s->animation = animation;
    s->mode = mode;
    s->startFrame = start;
    s->animLength = sprite_frame(length * 256);
    s->endFrame = mode <= ANIMMODE_LOOP_INTERP ? sprite_frame((length - 1) * 256) : end;
    s->curFrame = mode >= ANIMMODE_LOOP_PARTIAL ? sprite_frame(0) : start;
    s->playSpeed = speed;
    s->morphWeight = s->morphRate = sprite_frame(0);
}

void OotCore_SpriteInitFlex(PlayState*, SkelAnime* s, FlexSkeletonHeader* skeleton,
                           AnimationHeader* animation, Vec3s*, Vec3s*, s32 limbCount) {
    s->initFlags = 0x53;
    s->limbCount = limbCount; /* sheet key only; zero means object/clip lookup */
    s->dListCount = 0;
    /* Only the linked symbol identity survives. Its placeholder contains no
     * skeleton data and must never be dereferenced by a sprite path. */
    s->skeleton = (void**)skeleton;
    s->jointTable = s->morphTable = NULL;
    s->update.normal = NULL;
    if (animation != NULL)
        OotCore_SpriteChange(s, animation, sprite_frame(256), sprite_frame(0), sprite_frame(0), ANIMMODE_LOOP);
}

void OotCore_SpriteInit(PlayState* play, SkelAnime* s, SkeletonHeader* skeleton,
                       AnimationHeader* animation, Vec3s* joints, Vec3s* morph, s32 limbCount) {
    OotCore_SpriteInitFlex(play, s, (FlexSkeletonHeader*)skeleton, animation, joints, morph, limbCount);
}

s32 OotCore_SpriteUpdate(SkelAnime* s) {
    s32 frame = sprite_q8(s->curFrame), end = sprite_q8(s->endFrame);
    s32 speed = sprite_q8(s->playSpeed), length = sprite_q8(s->animLength);
    bool once = s->mode == ANIMMODE_ONCE || s->mode == ANIMMODE_ONCE_INTERP;
    if (once && frame == end) return true;
    frame += speed;
    if (once && ((speed > 0 && frame > end) || (speed < 0 && frame < end))) frame = end;
    else if (s->mode >= ANIMMODE_LOOP_PARTIAL) {
        s32 start = sprite_q8(s->startFrame), span = end - start;
        if (span > 0 && (frame < start || frame >= end)) {
            frame = (frame - start) % span;
            if (frame < 0) frame += span;
            frame += start;
        }
    } else if (length > 0 && (frame < 0 || frame >= length)) {
        frame %= length;
        if (frame < 0) frame += length;
    }
    s->curFrame = sprite_frame(frame);
    return false;
}

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
        s32 value = gSaveContext.save.info.playerData.rupees + rupeeChange;
        s32 capacity = CUR_CAPACITY(UPG_WALLET);
        gSaveContext.save.info.playerData.rupees = value < 0 ? 0 : value > capacity ? capacity : value;
    }
}

/* Source Interface_SetTimer and its 20 Hz clock live in bridge_ranch.cpp. */

/* ---- audio: music is the C side's; these change sequences ---- */
void Audio_PlaySfxRandom(Vec3f* pos, u16 baseSfxId, u8 randLim) { /* HOST: base sfx */
    if (gOotCoreHost != NULL && gOotCoreHost->play_sfx != NULL) {
        gOotCoreHost->play_sfx(baseSfxId, pos ? (s32)pos->x : 0, pos ? (s32)pos->y : 0, pos ? (s32)pos->z : 0);
    }
}
void Audio_QueueSeqCmd(u32 cmd) {
    unsigned op = cmd >> 28, player = (cmd >> 24) & 15;
    if (op == SEQCMD_OP_PLAY_SEQUENCE && player <= 1)
        OotCore_AudioRequest(player ? OOT_CORE_AUDIO_FANFARE : OOT_CORE_AUDIO_SEQUENCE, cmd & 0xff);
    else if (op == SEQCMD_OP_STOP_SEQUENCE && player == 0)
        OotCore_AudioRequest(OOT_CORE_AUDIO_STOP, 0);
}
void Audio_SetFastTempoForTimedMinigame(void) {
    OotCore_AudioRequest(OOT_CORE_AUDIO_MINIGAME_TEMPO, 0);
}
/* Malon/ambient channel services are in bridge_route_audio.cpp. */
void func_800F5ACC(u16 seqId) {
    OotCore_AudioRequest(OOT_CORE_AUDIO_PUSH_SEQUENCE, seqId & 0xff);
}
void func_800F5B58(void) {
    OotCore_AudioRequest(OOT_CORE_AUDIO_POP_SEQUENCE, 0);
}
void Environment_ForcePlaySequence(u16 seqId) {
    OotCore_AudioRequest(OOT_CORE_AUDIO_SEQUENCE, seqId & 0xff);
}

/* Subcamera/letterbox services are in bridge_cutscene_camera.cpp. */
/* Source attention camera category services are in bridge_cutscene_camera. */
