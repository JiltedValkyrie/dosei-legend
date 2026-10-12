/*
 * Decoder for the packed real-Player frame bank. The core includes this file
 * through src/player_frame_decode.cpp; host tests compile the same decoder.
 * tools/player_frame_pack.py documents the block format. Integer only;
 * one 32-bit window read per channel field.
 *
 * One clip block. Kept poses sit in delta blocks of blockK. Decoding kept
 * pose kk reads that block only: one absolute pose plus at most blockK-1
 * deltas. An interpolated frame reads two kept poses.
 */
#include <stdint.h>

#define PFB_CHANNELS 67
#define PFB_HEADER 12
#define PFB_BASES PFB_HEADER
#define PFB_WIDTHS (PFB_HEADER + PFB_CHANNELS * 2)
#define PFB_DWIDTHS (PFB_WIDTHS + PFB_CHANNELS)
#define PFB_SHIFTS (PFB_DWIDTHS + 63)
#define PFB_TABLE (PFB_SHIFTS + 63 + 1)

/* Only source Player animation calls the cached entry. Host C-cutscene poses
 * keep the original stateless entry, so master and slave never mutate this
 * cache concurrently. Four recent kept poses retain lower/upper-body blends
 * and neighbouring interpolation samples. 4 * 140 + 4 = 564 bytes on SH-2.
 * Immutable clip identity + exact kept index is a hit. An earlier pose from
 * the same delta block is also a valid decode prefix; backwards seeks and
 * loop wraps rebuild from the absolute pose when no such prefix survives. */
typedef struct {
    const uint8_t* block;
    uint32_t kept;
    uint32_t next_bit;
    uint16_t q[63];
} PfbRecentPose;

static PfbRecentPose pfb_recent[4];
static uint32_t pfb_replace;

#ifdef PFB_DECODE_WORK_TEST
uint32_t PlayerFrameBank_DecodeFields;
#endif

void PlayerFrameBank_DecodeReset(void) {
    uint32_t slot;
    for (slot = 0; slot < 4; ++slot) pfb_recent[slot].block = 0;
    pfb_replace = 0;
}

static uint32_t be16(const uint8_t* p) { return ((uint32_t)p[0] << 8) | p[1]; }
static uint32_t be32(const uint8_t* p) {
    return ((uint32_t)p[0] << 24) | ((uint32_t)p[1] << 16) | ((uint32_t)p[2] << 8) | p[3];
}

/* w <= 16 bits at bit position pos (MSB first). Blocks carry 4 bytes of
 * tail padding so the window never leaves the allocation. */
static uint32_t pfb_field(const uint8_t* d, uint32_t pos, uint32_t w) {
#ifdef PFB_DECODE_WORK_TEST
    ++PlayerFrameBank_DecodeFields;
#endif
    const uint8_t* p = d + (pos >> 3);
    uint32_t v = ((uint32_t)p[0] << 24) | ((uint32_t)p[1] << 16) | ((uint32_t)p[2] << 8) | p[3];
    return w ? (v << (pos & 7)) >> (32 - w) : 0;
}

/* Decode kept-pose index kk into rotation channels of out. */
static void pfb_kept(const uint8_t* b, uint32_t kk, int16_t* out) {
    uint32_t n = be16(b), block_k = b[5], bits_a = be16(b + 6), nblocks = be16(b + 8);
    uint32_t bi = kk / block_k, within = kk - bi * block_k;
    const uint8_t* widths = b + PFB_WIDTHS;
    const uint8_t* dwidth = b + PFB_DWIDTHS;
    const uint8_t* shifts = b + PFB_SHIFTS;
    uint32_t b_off = PFB_TABLE + nblocks * 4 + (n * bits_a + 7) / 8;
    uint32_t pos = b_off * 8 + be32(b + PFB_TABLE + bi * 4);
    uint16_t q[63];
    int c, step;

    for (c = 0; c < 63; c++) {
        uint32_t ch = (uint32_t)(c + 3);
        uint32_t shift = shifts[c];
        uint32_t mask = (1u << (16 - shift)) - 1;
        uint32_t w = widths[ch];
        q[c] = (uint16_t)((be16(b + PFB_BASES + ch * 2) + pfb_field(b, pos, w)) & mask);
        pos += w;
    }
    for (step = 0; step < (int)within; step++) {
        for (c = 0; c < 63; c++) {
            uint32_t w = dwidth[c];
            uint32_t shift = shifts[c];
            uint32_t mask = (1u << (16 - shift)) - 1;
            int32_t d = 0;
            if (w) {
                d = (int32_t)pfb_field(b, pos, w) - (int32_t)(1u << (w - 1));
                pos += w;
            }
            q[c] = (uint16_t)((q[c] + d) & mask);
        }
    }
    for (c = 0; c < 63; c++) {
        out[c + 3] = (int16_t)(uint16_t)(q[c] << shifts[c]);
    }
}

static void pfb_kept_cached(const uint8_t* b, uint32_t kk, int16_t* out) {
    uint32_t block_k = b[5], bi = kk / block_k;
    uint32_t first = bi * block_k, next, pos, slot;
    const uint8_t* widths = b + PFB_WIDTHS;
    const uint8_t* dwidth = b + PFB_DWIDTHS;
    const uint8_t* shifts = b + PFB_SHIFTS;
    PfbRecentPose* prefix = 0;
    PfbRecentPose* pose;
    int c;

    for (slot = 0; slot < 4; ++slot) {
        PfbRecentPose* candidate = &pfb_recent[slot];
        if (candidate->block != b) continue;
        if (candidate->kept == kk) {
            for (c = 0; c < 63; ++c)
                out[c + 3] = (int16_t)(uint16_t)(candidate->q[c] << shifts[c]);
            return;
        }
        if (candidate->kept >= first && candidate->kept < kk &&
            (!prefix || candidate->kept > prefix->kept)) prefix = candidate;
    }
    pose = &pfb_recent[pfb_replace];
    pfb_replace = (pfb_replace + 1) & 3u;
    if (prefix) {
        pos = prefix->next_bit;
        next = prefix->kept + 1;
        if (pose != prefix)
            for (c = 0; c < 63; ++c) pose->q[c] = prefix->q[c];
    } else {
        uint32_t n = be16(b), bits_a = be16(b + 6), nblocks = be16(b + 8);
        uint32_t b_off = PFB_TABLE + nblocks * 4 + (n * bits_a + 7) / 8;
        pos = b_off * 8 + be32(b + PFB_TABLE + bi * 4);
        for (c = 0; c < 63; ++c) {
            uint32_t ch = (uint32_t)(c + 3), shift = shifts[c];
            uint32_t mask = (1u << (16 - shift)) - 1;
            uint32_t w = widths[ch];
            pose->q[c] = (uint16_t)((be16(b + PFB_BASES + ch * 2) + pfb_field(b, pos, w)) & mask);
            pos += w;
        }
        next = first + 1;
    }
    for (; next <= kk; ++next) {
        for (c = 0; c < 63; ++c) {
            uint32_t w = dwidth[c], shift = shifts[c];
            uint32_t mask = (1u << (16 - shift)) - 1;
            int32_t d = 0;
            if (w) {
                d = (int32_t)pfb_field(b, pos, w) - (int32_t)(1u << (w - 1));
                pos += w;
            }
            pose->q[c] = (uint16_t)((pose->q[c] + d) & mask);
        }
    }
    pose->block = b;
    pose->kept = kk;
    pose->next_bit = pos;
    for (c = 0; c < 63; ++c)
        out[c + 3] = (int16_t)(uint16_t)(pose->q[c] << shifts[c]);
}

/* Decode source frame i of one clip block into 67 s16 (root xyz, 63 rotations,
 * face). Bounded work: stream A once, at most two delta blocks. */
static void pfb_decode(const uint8_t* b, uint32_t i, int16_t* out, int16_t* scratch,
                       void (*kept)(const uint8_t*, uint32_t, int16_t*)) {
    uint32_t n = be16(b), k = be16(b + 2), stride = b[4];
    uint32_t bits_a = be16(b + 6), nblocks = be16(b + 8);
    const uint8_t* widths = b + PFB_WIDTHS;
    uint32_t a = ((PFB_TABLE + nblocks * 4) << 3) + i * bits_a;
    uint32_t lo_k = i / stride, lo = lo_k * stride;
    static const uint8_t exact[4] = { 0, 1, 2, 66 };
    int e, c;

    if (lo_k >= k) {
        lo_k = k - 1;
        lo = lo_k * stride;
    }
    for (e = 0; e < 4; e++) {
        uint32_t ch = exact[e], w = widths[ch];
        out[ch] = (int16_t)(uint16_t)(be16(b + PFB_BASES + ch * 2) + pfb_field(b, a, w));
        a += w;
    }
    if (lo == i || lo_k + 1 >= k) {
        kept(b, lo == i ? lo_k : k - 1, out);
    } else {
        int32_t hi = (int32_t)(lo + stride < n - 1 ? lo + stride : n - 1);
        int32_t t = (int32_t)(i - lo), span = hi - (int32_t)lo;
        kept(b, lo_k, scratch);
        kept(b, lo_k + 1, out);
        for (c = 3; c < 66; c++) {
            int32_t d = (int16_t)(uint16_t)(out[c] - scratch[c]);
            out[c] = (int16_t)(uint16_t)(scratch[c] + (d * t) / span);
        }
    }
}

void PlayerFrameBank_Decode(const uint8_t* b, uint32_t i, int16_t* out, int16_t* scratch) {
    pfb_decode(b, i, out, scratch, pfb_kept);
}

void PlayerFrameBank_DecodeCached(const uint8_t* b, uint32_t i, int16_t* out, int16_t* scratch) {
    pfb_decode(b, i, out, scratch, pfb_kept_cached);
}

#ifdef PFB_HOST_TEST
#include <stdio.h>
#include <stdlib.h>

static uint8_t* slurp(const char* path, long* len) {
    FILE* f = fopen(path, "rb");
    uint8_t* d;
    if (!f) return NULL;
    fseek(f, 0, SEEK_END);
    *len = ftell(f);
    fseek(f, 0, SEEK_SET);
    d = malloc((size_t)*len + 8);
    fread(d, 1, (size_t)*len, f);
    fclose(f);
    return d;
}

/* argv: bank file, expected frames (s16 BE, every frame of every clip in bank
 * order). Exit 0 only when every decoded value matches. */
int main(int argc, char** argv) {
    long bl, el;
    uint8_t* bank = slurp(argv[1], &bl);
    uint8_t* exp = slurp(argv[2], &el);
    uint32_t count, c, i, at = 0, frames = 0;
    int16_t out[PFB_CHANNELS], scratch[PFB_CHANNELS];
    if (!bank || !exp || argc < 3) return 2;
    count = be32(bank + 4);
    for (c = 0; c < count; c++) {
        const uint8_t* o = bank + 8 + c * 4;
        const uint8_t* blk = bank + be32(o);
        uint32_t n = be16(blk);
        for (i = 0; i < n; i++, frames++) {
            int ch;
            PlayerFrameBank_Decode(blk, i, out, scratch);
            for (ch = 0; ch < PFB_CHANNELS; ch++, at += 2) {
                int16_t want = (int16_t)(uint16_t)((exp[at] << 8) | exp[at + 1]);
                if (out[ch] != want) {
                    printf("clip %u frame %u ch %d got %d want %d\n", c, i, ch, out[ch], want);
                    return 1;
                }
            }
        }
    }
    printf("C decoder round trip PASS: %u clips, %u frames\n", count, frames);
    return at == (uint32_t)el ? 0 : 3;
}
#endif
