/* Host test: demand cache handles (player_anim_cache.cpp) over the real
 * ALL.PFB as the disc archive, asynchronous fake reader. argv: bank dir. */
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

typedef int (*PacReadStart)(uint32_t offset, uint32_t bytes, uint8_t* dst, uint32_t token);
extern "C" int PlayerAnimCache_Init(uint8_t* arena, uint32_t arenaBytes, const uint8_t* manifest,
                                    uint32_t manifestBytes, uint32_t archiveBytes, PacReadStart read);
extern "C" int PlayerAnimCache_Open(const uint16_t* ids, const uint8_t* resident, int count);
extern "C" int PlayerAnimCache_Reserve(int handle);
extern "C" int PlayerAnimCache_Poll(int handle);
extern "C" void PlayerAnimCache_Close(int handle);
extern "C" int PlayerAnimCache_Complete(uint32_t token, int ok);
extern "C" int PlayerAnimCache_State(uint32_t id);
extern "C" uint32_t PlayerAnimCache_Used(uint32_t* pinned);
extern "C" int PlayerFrameBank_Load(uint32_t id, uint32_t frame, int16_t* out);

enum { WAIT = 3, READY = 2, LOADING = 1, UNKNOWN = -1, CORRUPT = -2, IOFAIL = -3, TOOBIG = -4 };

static int sFails;
extern "C" void PlayerFrameBank_Fail(int, uint32_t, uint32_t) { sFails++; }

static uint8_t* sArchive;
static long sArchiveLen;
static uint32_t sHeader;
static uint8_t* sExpect;
static uint32_t sFrames[65536], sExpectAt[65536], sBytes[65536];
struct Pending { uint32_t off, bytes, token; uint8_t* dst; };
static Pending sQueue[256];
static int sQueued, sCorrupt = -1, sFail = -1;

static int read_start(uint32_t off, uint32_t bytes, uint8_t* dst, uint32_t token) {
    sQueue[sQueued++] = { off, bytes, token, dst };
    return 0;
}
/* Complete only reads whose token passes `which` (all when NULL). */
static void pump_some(int (*which)(uint32_t)) {
    int keep = 0;
    for (int i = 0; i < sQueued; i++) {
        Pending p = sQueue[i];
        if (which && !which(p.token)) { sQueue[keep++] = p; continue; }
        memcpy(p.dst, sArchive + p.off, p.bytes);
        if ((int)p.token == sCorrupt) p.dst[4] = 0;
        PlayerAnimCache_Complete(p.token, (int)p.token != sFail);
    }
    sQueued = keep;
}
static void pump() { pump_some(NULL); }
static uint8_t* slurp(const char* path, long* len) {
    FILE* f = fopen(path, "rb");
    if (!f) return NULL;
    fseek(f, 0, SEEK_END); *len = ftell(f); fseek(f, 0, SEEK_SET);
    uint8_t* d = (uint8_t*)malloc(*len + 8);
    if (fread(d, 1, *len, f) != (size_t)*len) return NULL;
    fclose(f);
    return d;
}
static uint32_t be32(const uint8_t* p) { return ((uint32_t)p[0] << 24) | ((uint32_t)p[1] << 16) | ((uint32_t)p[2] << 8) | p[3]; }
static uint32_t be16(const uint8_t* p) { return ((uint32_t)p[0] << 8) | p[1]; }
static int decodes(uint32_t id) {
    int16_t out[67];
    uint32_t at = sExpectAt[id];
    for (uint32_t f = 0; f < sFrames[id]; f++) {
        if (PlayerFrameBank_Load(id, f, out) != 0) return 0;
        for (int c = 0; c < 67; c++, at += 2)
            if (out[c] != (int16_t)(uint16_t)((sExpect[at] << 8) | sExpect[at + 1])) return 0;
    }
    return 1;
}
static int init(uint8_t* arena, uint32_t bytes) {
    return PlayerAnimCache_Init(arena, bytes, sArchive, sHeader, (uint32_t)sArchiveLen, read_start);
}
static uint32_t sFirstId;
static int first_only(uint32_t t) { return t == sFirstId; }
#define CHECK(c, m) do { if (!(c)) { printf("FAIL %s\n", m); return 1; } } while (0)

int main(int argc, char** argv) {
    char path[1024]; long el;
    snprintf(path, sizeof path, "%s/ALL.PFB", argv[1]);
    sArchive = slurp(path, &sArchiveLen);
    snprintf(path, sizeof path, "%s/ALL.EXPECT", argv[1]);
    sExpect = slurp(path, &el);
    if (!sArchive || !sExpect) return 2;
    uint32_t count = be32(sArchive + 4), at = 0;
    sHeader = 8 + 4 * count + ((2 * count + 3) & ~3u);
    uint16_t ids[512];
    for (uint32_t c = 0; c < count; c++) {
        uint32_t id = be16(sArchive + 8 + 4 * count + 2 * c);
        uint32_t off = be32(sArchive + 8 + 4 * c);
        uint32_t end = c + 1 < count ? be32(sArchive + 12 + 4 * c) : (uint32_t)sArchiveLen - 4;
        ids[c] = (uint16_t)id;
        sFrames[id] = be16(sArchive + off);
        sBytes[id] = end - off + 4;
        sExpectAt[id] = at;
        at += 2 * 67 * sFrames[id];
    }
    uint32_t arenaBytes = 64 * 1024;
    uint8_t* arena = (uint8_t*)malloc(arenaBytes);
    uint8_t res0[64] = { 0 };

    /* 3. Manifest validated before any allocation/read. */
    CHECK(PlayerAnimCache_Init(arena, arenaBytes, sArchive, 12, (uint32_t)sArchiveLen, read_start) == -1,
          "short manifest buffer");
    uint8_t* m = (uint8_t*)malloc(sHeader);
    memcpy(m, sArchive, sHeader);
    memcpy(m + 12, m + 8, 4);                       /* clip 0 gets zero length */
    CHECK(PlayerAnimCache_Init(arena, arenaBytes, m, sHeader, (uint32_t)sArchiveLen, read_start) == -1,
          "bad offsets");
    memcpy(m, sArchive, sHeader);
    CHECK(PlayerAnimCache_Init(arena, arenaBytes, m, sHeader, (uint32_t)sHeader + 8, read_start) == -1,
          "offsets past archive");
    CHECK(init(arena, arenaBytes) == (int)count, "init");
    uint16_t unknown = 9999;
    CHECK(PlayerAnimCache_Open(&unknown, res0, 1) == UNKNOWN, "unknown id");

    /* 2. Impossible sets rejected before loading (bytes and entry count). */
    uint16_t big[512]; uint32_t sum = 0; int nb = 0;
    for (uint32_t c = 0; c < count && sum <= arenaBytes; c++) { big[nb++] = ids[c]; sum += sBytes[ids[c]]; }
    uint8_t res512[512] = { 0 };
    CHECK(PlayerAnimCache_Open(big, res512, nb) == TOOBIG, "set larger than arena");
    CHECK(sQueued == 0, "nothing loaded for impossible set");
    uint16_t many[65]; int nm = 0;
    for (uint32_t c = 0; c < count && nm < 65; c++) many[nm++] = ids[c];
    {   /* entry limit: 65 distinct clips in a huge arena */
        uint8_t* huge = (uint8_t*)malloc(4 << 20);
        CHECK(init(huge, 4 << 20) > 0, "init huge");
        CHECK(PlayerAnimCache_Open(many, res512, 65) == TOOBIG, "more than 64 entries");
        CHECK(init(arena, arenaBytes) > 0, "reinit");
    }

    /* 1. Pending set cannot evict itself; polling adds no pins. */
    uint16_t cs[6]; uint32_t csBytes = 0;
    for (int k = 0; k < 6; k++) { cs[k] = ids[40 + k]; csBytes += sBytes[cs[k]]; }
    int h = PlayerAnimCache_Open(cs, res0, 6);
    CHECK(h >= 0, "open cutscene set");
    CHECK(PlayerAnimCache_Poll(h) == WAIT, "not reserved yet");
    CHECK(PlayerAnimCache_Reserve(h) == LOADING, "reserve");
    sFirstId = cs[0];
    pump_some(first_only);                           /* one member done, rest in flight */
    CHECK(PlayerAnimCache_State(cs[0]) == READY, "first member ready");
    for (int r = 0; r < 20; r++) CHECK(PlayerAnimCache_Poll(h) == LOADING, "poll while loading");
    /* Flood with other single-clip handles: must never evict cs members. */
    uint32_t floods = 0;
    for (uint32_t c = 100; c < count && floods < 200; c++) {
        uint16_t one = ids[c];
        int g = PlayerAnimCache_Open(&one, res0, 1);
        if (g < 0) continue;
        int r = PlayerAnimCache_Reserve(g);
        CHECK(r == LOADING || r == WAIT, "flood reserve");
        if (r == LOADING) { sFirstId = one; pump_some(first_only); CHECK(PlayerAnimCache_Poll(g) == READY && decodes(one), "flood clip"); }
        PlayerAnimCache_Close(g);
        CHECK(PlayerAnimCache_State(cs[0]) == READY, "early member kept while set pending");
        floods++;
    }
    pump();
    CHECK(PlayerAnimCache_Poll(h) == READY, "whole set ready");
    for (int k = 0; k < 6; k++) CHECK(decodes(cs[k]), "cutscene member decodes");
    PlayerAnimCache_Close(h);

    /* Contention vs impossible: A pins most of the arena; B fits alone. */
    uint16_t A[64], B[64]; int na = 0, nbb = 0; uint32_t sa = 0, sb = 0;
    uint16_t bySize[512];
    memcpy(bySize, ids, sizeof(uint16_t) * count);
    for (uint32_t i = 0; i < count; i++)            /* largest first */
        for (uint32_t j = i + 1; j < count; j++)
            if (sBytes[bySize[j]] > sBytes[bySize[i]]) { uint16_t t = bySize[i]; bySize[i] = bySize[j]; bySize[j] = t; }
    for (uint32_t c = 0; c < count; c++) {
        uint32_t b = sBytes[bySize[c]];
        if (sa + b <= arenaBytes * 3 / 4 && na < 64) { A[na++] = bySize[c]; sa += b; }
        else if (sa >= arenaBytes * 5 / 8 && sb + b <= arenaBytes / 2 && nbb < 64) { B[nbb++] = bySize[c]; sb += b; }
    }
    CHECK(sa + sb > arenaBytes, "contention fixture");
    CHECK(init(arena, arenaBytes) > 0, "reinit contention");
    int ha = PlayerAnimCache_Open(A, res512, na), hb = PlayerAnimCache_Open(B, res512, nbb);
    CHECK(ha >= 0 && hb >= 0, "open A, B");
    CHECK(PlayerAnimCache_Reserve(ha) == LOADING, "reserve A");
    CHECK(PlayerAnimCache_Reserve(hb) == WAIT, "B waits: temporary contention");
    CHECK(sQueued == na, "B issued no reads");
    pump();
    CHECK(PlayerAnimCache_Poll(ha) == READY, "A ready");
    PlayerAnimCache_Close(ha);
    CHECK(PlayerAnimCache_Reserve(hb) == LOADING, "B proceeds after A closes");
    pump();
    CHECK(PlayerAnimCache_Poll(hb) == READY, "B ready");
    uint32_t pinned;
    PlayerAnimCache_Used(&pinned);
    CHECK(pinned == sb, "pins exactly B (polling added none)");
    PlayerAnimCache_Close(hb);
    PlayerAnimCache_Used(&pinned);
    CHECK(pinned == 0, "no pins after close");

    /* Corrupt and I/O failure: distinct, reported by Poll, never published. */
    CHECK(init(arena, arenaBytes) > 0, "reinit errors");
    uint16_t c1 = ids[5], c2 = ids[6];
    sCorrupt = c1; sFail = c2;
    int h1 = PlayerAnimCache_Open(&c1, res0, 1), h2 = PlayerAnimCache_Open(&c2, res0, 1);
    PlayerAnimCache_Reserve(h1); PlayerAnimCache_Reserve(h2);
    pump();
    CHECK(PlayerAnimCache_Poll(h1) == CORRUPT && PlayerAnimCache_Poll(h2) == IOFAIL, "error states");
    int16_t tmp[67];
    int before = sFails;
    CHECK(PlayerFrameBank_Load(c1, 0, tmp) == -2 && sFails == before + 1, "corrupt never published");
    PlayerAnimCache_Close(h1); PlayerAnimCache_Close(h2);
    CHECK(PlayerAnimCache_Open(&c1, res0, 1) == CORRUPT, "failed clip rejected at open");
    printf("anim cache handles PASS: manifest checks, impossible sets rejected, %u flood handles "
           "never evicted a pending member, contention waits, no extra pins, errors distinct\n", floods);
    return 0;
}
