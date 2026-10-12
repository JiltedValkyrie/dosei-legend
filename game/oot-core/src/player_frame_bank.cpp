/*
 * Real-Player frame bank adapter (Player migration phase 4: live with PLAYER_SOURCE=1
 * OOT_CORE_SRCS list until Player cutover).
 *
 * Bank files (tools/build_player_frame_bank.py, format in player_frame_pack.py):
 *   'PFB2', u32 count, u32 offset[count], u16 id[count] (pad 4), clip blocks,
 *   4 bytes tail pad. RESIDENT.PFB is registered at boot; one S_<scene>.PFB is
 *   registered per scene load (behind the loading screen, never mid-action).
 * The importer writes each LinkAnimationHeader.segment as PFB_SEGMENT | id.
 *
 * AnimTaskQueue_AddLoadPlayerFrame decodes the frame synchronously into the
 * caller's frameTable (22 Vec3s + face word = 67 s16), replacing the ROM DMA.
 * A missing id or out-of-range frame is a hard failure through
 * PlayerFrameBank_Fail: never a silent pose.
 */
#include <stdint.h>
#ifdef PFB_CORE
/* The decomp's libc stdint.h has no fixed-width types. */
typedef unsigned char uint8_t;
typedef signed short int16_t;
typedef unsigned short uint16_t;
typedef unsigned int uint32_t;
typedef signed int int32_t;
#endif

#define PFB_CHANNELS 67
#define PFB_MAX_IDS 640  /* bank_full: 521 clips */
#define PFB_SEGMENT 0x0B000000u
#define PFB_HEADER 12
#define PFB_BASES PFB_HEADER
#define PFB_WIDTHS (PFB_BASES + PFB_CHANNELS * 2)
#define PFB_DWIDTHS (PFB_WIDTHS + PFB_CHANNELS)
#define PFB_SHIFTS (PFB_DWIDTHS + 63)
#define PFB_TABLE (PFB_SHIFTS + 63 + 1)

enum {
    PFB_OK = 0,
    PFB_ERR_FORMAT = -1,
    PFB_ERR_MISSING = -2,
    PFB_ERR_FRAME = -3,
    PFB_ERR_DUPLICATE = -4,
};

extern "C" void PlayerFrameBank_Decode(const uint8_t* block, uint32_t frame, int16_t* out,
                                       int16_t* scratch);
extern "C" void PlayerFrameBank_DecodeCached(const uint8_t* block, uint32_t frame, int16_t* out,
                                             int16_t* scratch);
extern "C" void PlayerFrameBank_DecodeReset(void);
/* Fatal hook: the game build routes this to its error screen. */
extern "C" void PlayerFrameBank_Fail(int code, uint32_t id, uint32_t frame);

static const uint8_t* sSlots[PFB_MAX_IDS];
static int16_t sScratch[PFB_CHANNELS];
static int16_t sCachedScratch[PFB_CHANNELS]; /* source-only, independent of host pose queries */
static int sSwapping;   /* scene-pack change in progress: Load fails loud */

static uint32_t be32(const uint8_t* p) {
    return ((uint32_t)p[0] << 24) | ((uint32_t)p[1] << 16) | ((uint32_t)p[2] << 8) | p[3];
}
static uint32_t be16(const uint8_t* p) { return ((uint32_t)p[0] << 8) | p[1]; }

/* Whole decoder-input check for one clip block occupying [b, b + len).
 * `slack` = readable bytes after the block inside the bank (32-bit window).
 * Everything PlayerFrameBank_Decode trusts is proved here: header counts,
 * stride/blockK, per-channel shift and widths, exact block-table offsets and
 * both stream sizes. */
static bool pfb_block_ok(const uint8_t* b, uint32_t len, uint32_t slack) {
    if (len < PFB_TABLE) {
        return false;
    }
    uint32_t n = be16(b), k = be16(b + 2), stride = b[4], blockK = b[5];
    uint32_t bitsA = be16(b + 6), nblocks = be16(b + 8);
    const uint8_t* widths = b + PFB_WIDTHS;
    const uint8_t* dwidth = b + PFB_DWIDTHS;
    const uint8_t* shifts = b + PFB_SHIFTS;

    if (n == 0 || stride == 0 || blockK == 0) {
        return false;
    }
    /* kept = 0, s, 2s, ... plus the last frame when it is off the grid. */
    uint32_t grid = (n + stride - 1) / stride;
    if (k != grid + ((n - 1) % stride != 0 ? 1u : 0u) || nblocks != (k + blockK - 1) / blockK) {
        return false;
    }
    if (be16(b + 10) != 0 || b[PFB_TABLE - 1] != 0) {
        return false;
    }
    static const uint8_t exact[4] = { 0, 1, 2, 66 };
    uint32_t sumA = 0, absBits = 0, deltaBits = 0;
    for (int e = 0; e < 4; e++) {
        if (widths[exact[e]] > 16) {
            return false;
        }
        sumA += widths[exact[e]];
    }
    if (sumA != bitsA) {
        return false;
    }
    for (int c = 0; c < 63; c++) {
        uint32_t s = shifts[c];
        if (s > 8 || (s & 1) || widths[c + 3] > 16 - s || dwidth[c] > 17 - s) {
            return false;
        }
        absBits += widths[c + 3];
        deltaBits += dwidth[c];
    }
    /* Block table must hold the exact running bit offsets. */
    uint32_t tableEnd = PFB_TABLE + 4 * nblocks;
    if (tableEnd > len) {
        return false;
    }
    uint32_t bitsB = 0;
    for (uint32_t g = 0; g < nblocks; g++) {
        uint32_t poses = k - g * blockK < blockK ? k - g * blockK : blockK;
        if (be32(b + PFB_TABLE + 4 * g) != bitsB) {
            return false;
        }
        bitsB += absBits + (poses - 1) * deltaBits;
    }
    uint32_t streamA = (n * bitsA + 7) / 8, streamB = (bitsB + 7) / 8;
    uint32_t need = tableEnd + streamA + streamB;
    /* The last field's 32-bit window may read 3 bytes past its stream. */
    return need <= len && need + 3 <= len + slack;
}

/* Validate a whole bank file before publishing any slot. Rejects a bad block,
 * duplicate ids inside the file and ids another registered bank already owns
 * (no silent resident/pack replacement: unregister first). Returns the clip
 * count or a negative error; a failed register changes nothing. */
extern "C" int PlayerFrameBank_Register(const uint8_t* bank, uint32_t bytes) {
    static uint8_t sSeen[PFB_MAX_IDS];
    uint32_t count, idTable, dataStart, i;

    if (bytes < 12 || bank[0] != 'P' || bank[1] != 'F' || bank[2] != 'B' || bank[3] != '2') {
        return PFB_ERR_FORMAT;
    }
    count = be32(bank + 4);
    if (count == 0 || count > PFB_MAX_IDS) {
        return PFB_ERR_FORMAT;
    }
    idTable = 8 + 4 * count;
    dataStart = idTable + ((2 * count + 3) & ~3u);
    if (dataStart + 4 > bytes) {
        return PFB_ERR_FORMAT;
    }
    for (i = 0; i < PFB_MAX_IDS; i++) {
        sSeen[i] = 0;
    }
    for (i = 0; i < count; i++) {
        uint32_t off = be32(bank + 8 + 4 * i), id = be16(bank + idTable + 2 * i);
        uint32_t end = i + 1 < count ? be32(bank + 12 + 4 * i) : bytes - 4;
        if (id >= PFB_MAX_IDS || off < dataStart || end <= off || end > bytes - 4 ||
            !pfb_block_ok(bank + off, end - off, bytes - end)) {
            return PFB_ERR_FORMAT;
        }
        if (sSeen[id] || sSlots[id] != 0) {
            return PFB_ERR_DUPLICATE;
        }
        sSeen[id] = 1;
    }
    for (i = 0; i < count; i++) {
        sSlots[be16(bank + idTable + 2 * i)] = bank + be32(bank + 8 + 4 * i);
    }
    PlayerFrameBank_DecodeReset();
    return (int)count;
}

/* Demand cache (player_anim_cache.cpp): publish one validated clip block that
 * was read on its own. Fails without publishing if the block is malformed or
 * the id is already owned (resident set or another cached copy). */
extern "C" int PlayerFrameBank_PublishBlock(uint32_t id, const uint8_t* block, uint32_t bytes,
                                            uint32_t slack) {
    if (id >= PFB_MAX_IDS || bytes == 0 || !pfb_block_ok(block, bytes, slack)) {
        return PFB_ERR_FORMAT;
    }
    if (sSlots[id] != 0) {
        return PFB_ERR_DUPLICATE;
    }
    sSlots[id] = block;
    PlayerFrameBank_DecodeReset();
    return PFB_OK;
}

/* Withdraw one cached clip before its memory is reused. */
extern "C" void PlayerFrameBank_Retract(uint32_t id, const uint8_t* block) {
    if (id < PFB_MAX_IDS && sSlots[id] == block) {
        sSlots[id] = 0;
        PlayerFrameBank_DecodeReset();
    }
}

/* Drop every slot that points into this bank (scene pack unload). */
extern "C" void PlayerFrameBank_Unregister(const uint8_t* bank, uint32_t bytes) {
    PlayerFrameBank_DecodeReset(); /* pointers may be reused by the next pack */
    for (uint32_t id = 0; id < PFB_MAX_IDS; id++) {
        if (sSlots[id] >= bank && sSlots[id] < bank + bytes) {
            sSlots[id] = 0;
        }
    }
}

/* Frames in clip `id`, 0 when it is not registered (no failure). */
extern "C" uint32_t PlayerFrameBank_Count(uint32_t id) {
    const uint8_t* block = id < PFB_MAX_IDS && !sSwapping ? sSlots[id] : 0;
    return block ? be16(block) : 0;
}

static int pfb_load(uint32_t id, uint32_t frame, int16_t* out, bool cached) {
    const uint8_t* block = id < PFB_MAX_IDS && !sSwapping ? sSlots[id] : 0;

    if (block == 0) {
        PlayerFrameBank_Fail(PFB_ERR_MISSING, id, frame);
        return PFB_ERR_MISSING;
    }
    if (frame >= be16(block)) {
        PlayerFrameBank_Fail(PFB_ERR_FRAME, id, frame);
        return PFB_ERR_FRAME;
    }
    if (cached) PlayerFrameBank_DecodeCached(block, frame, out, sCachedScratch);
    else PlayerFrameBank_Decode(block, frame, out, sScratch);
    return PFB_OK;
}

extern "C" int PlayerFrameBank_Load(uint32_t id, uint32_t frame, int16_t* out) {
    return pfb_load(id, frame, out, false);
}

/* Source Player only. C cutscene/render callers keep the stateless Load path. */
extern "C" int PlayerFrameBank_LoadCached(uint32_t id, uint32_t frame, int16_t* out) {
    return pfb_load(id, frame, out, true);
}

/* Scene-pack change, approved rollback rules (human/Astra 2026-10-06). Runs
 * behind the loading screen; the caller has already paused every animation
 * consumer (no Player/actor update), and Load fails loud while a swap is in
 * progress. The new pack is read into the same home buffer as the old one:
 *   1. unregister the old pack's slots BEFORE its bytes are overwritten;
 *   2. read + fully validate the new pack, register it -> 0, commit scene;
 *   3. else reload the old pack from disc into the buffer and re-register it
 *      -> 1: caller aborts the scene change and restores the matching state;
 *   4. if that also fails -> -1: caller stays on the error/loading screen and
 *      never resumes gameplay. */
typedef int (*PfbRead)(void* ctx, uint8_t* dst, uint32_t capacity);

extern "C" int PlayerFrameBank_ChangeScenePack(uint8_t* home, uint32_t capacity,
                                               uint32_t* homeBytes,
                                               PfbRead readNew, void* newCtx,
                                               PfbRead readOld, void* oldCtx) {
    int got;

    sSwapping = 1;
    if (*homeBytes) {
        PlayerFrameBank_Unregister(home, *homeBytes);
    }
    got = readNew ? readNew(newCtx, home, capacity) : 0;
    if (got == 0) {                         /* scene without a pack */
        *homeBytes = 0;
        sSwapping = 0;
        return 0;
    }
    if (got > 0 && (uint32_t)got <= capacity && PlayerFrameBank_Register(home, (uint32_t)got) > 0) {
        *homeBytes = (uint32_t)got;
        sSwapping = 0;
        return 0;
    }
    got = readOld ? readOld(oldCtx, home, capacity) : 0;
    if (got == 0 || (got > 0 && (uint32_t)got <= capacity &&
                     PlayerFrameBank_Register(home, (uint32_t)got) > 0)) {
        *homeBytes = got > 0 ? (uint32_t)got : 0;
        sSwapping = 0;
        return 1;
    }
    *homeBytes = 0;
    PlayerFrameBank_Fail(PFB_ERR_FORMAT, 0xFFFFu, 0);
    return -1;                              /* stays swapping: Load keeps failing loud */
}

#ifdef PFB_CORE
/* Source z_skelanime.c replacement, compiled only into the cutover core. */
#include "ultra64.h"
#include "animation.h"
#include "segmented_address.h"

void AnimTaskQueue_AddLoadPlayerFrame(PlayState* play, LinkAnimationHeader* animation, s32 frame,
                                      s32 limbCount, Vec3s* frameTable) {
    LinkAnimationHeader* header = (LinkAnimationHeader*)SEGMENTED_TO_VIRTUAL(animation);
    uint32_t segment = (uint32_t)(uintptr_t)header->segment;

    if ((segment & 0xFF000000u) != PFB_SEGMENT || limbCount * 3 + 1 != PFB_CHANNELS) {
        PlayerFrameBank_Fail(PFB_ERR_FORMAT, segment, (uint32_t)frame);
        return;
    }
    PlayerFrameBank_LoadCached(segment & 0xFFFFu, (uint32_t)frame, (int16_t*)frameTable);
}
#endif
