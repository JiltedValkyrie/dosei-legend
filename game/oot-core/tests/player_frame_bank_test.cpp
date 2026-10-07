/* Host test of oot-core/src/player_frame_bank.cpp with real emitted banks.
 * argv: bank dir, then scene pack files. Lifecycle as in the game: resident
 * registered once; each scene pack registered, checked, unregistered. Every
 * registered frame must match ALL.EXPECT; untriggered ids, frame overrun,
 * unloaded packs and every corrupted/duplicate bank must fail loud and
 * publish nothing. */
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

extern "C" int PlayerFrameBank_Register(const uint8_t* bank, uint32_t bytes);
extern "C" void PlayerFrameBank_Unregister(const uint8_t* bank, uint32_t bytes);
extern "C" int PlayerFrameBank_Load(uint32_t id, uint32_t frame, int16_t* out);
typedef int (*PfbRead)(void* ctx, uint8_t* dst, uint32_t capacity);
extern "C" int PlayerFrameBank_ChangeScenePack(uint8_t* home, uint32_t capacity, uint32_t* homeBytes,
                                               PfbRead readNew, void* newCtx, PfbRead readOld, void* oldCtx);

struct Src { const uint8_t* data; long len; int corrupt; int fail; };
static int read_src(void* ctx, uint8_t* dst, uint32_t cap) {
    Src* s = (Src*)ctx;
    if (s->fail) return -1;
    if ((uint32_t)s->len > cap) return -1;
    memcpy(dst, s->data, s->len);
    if (s->corrupt) dst[(((uint32_t)dst[8] << 24) | ((uint32_t)dst[9] << 16) | ((uint32_t)dst[10] << 8) | dst[11]) + 4] = 0;
    return (int)s->len;
}

static int sFails, sLastCode;
extern "C" void PlayerFrameBank_Fail(int code, uint32_t, uint32_t) {
    sFails++;
    sLastCode = code;
}

static uint8_t* slurp(const char* path, long* len) {
    FILE* f = fopen(path, "rb");
    if (!f) return NULL;
    fseek(f, 0, SEEK_END);
    *len = ftell(f);
    fseek(f, 0, SEEK_SET);
    uint8_t* d = (uint8_t*)malloc(*len + 8);
    if (fread(d, 1, *len, f) != (size_t)*len) return NULL;
    fclose(f);
    return d;
}

static uint32_t be32(const uint8_t* p) { return ((uint32_t)p[0] << 24) | ((uint32_t)p[1] << 16) | ((uint32_t)p[2] << 8) | p[3]; }
static uint32_t be16(const uint8_t* p) { return ((uint32_t)p[0] << 8) | p[1]; }
static void put16(uint8_t* p, uint32_t v) { p[0] = (uint8_t)(v >> 8); p[1] = (uint8_t)v; }

/* id -> (frame count, first EXPECT byte) from ALL.PFB order. */
static uint32_t sFrames[65536], sExpectAt[65536];
static uint8_t* sExpect;

static int check_file(const uint8_t* file, uint32_t* framesOut) {
    uint32_t count = be32(file + 4), idTable = 8 + 4 * count;
    int16_t out[67];
    for (uint32_t c = 0; c < count; c++) {
        uint32_t id = be16(file + idTable + 2 * c), at = sExpectAt[id];
        for (uint32_t f = 0; f < sFrames[id]; f++, (*framesOut)++) {
            if (PlayerFrameBank_Load(id, f, out) != 0) { printf("load id %u frame %u\n", id, f); return 1; }
            for (int ch = 0; ch < 67; ch++, at += 2) {
                if (out[ch] != (int16_t)(uint16_t)((sExpect[at] << 8) | sExpect[at + 1])) {
                    printf("id %u frame %u ch %d\n", id, f, ch);
                    return 1;
                }
            }
        }
    }
    return 0;
}

/* Corrupt one byte/field of a copy; Register must refuse it and publish nothing. */
static int expect_reject(const uint8_t* good, long len, const char* what, uint32_t at, int bytes,
                         uint32_t value, long cut, uint32_t probeId) {
    uint8_t* bad = (uint8_t*)malloc(len + 8);
    int16_t out[67];
    memcpy(bad, good, len);
    if (bytes == 1) bad[at] = (uint8_t)value;
    if (bytes == 2) put16(bad + at, value);
    int r = PlayerFrameBank_Register(bad, (uint32_t)(len - cut));
    int before = sFails;
    int published = PlayerFrameBank_Load(probeId, 0, out) == 0;
    sFails = before;
    free(bad);
    if (r >= 0 || published) { printf("corrupt %s accepted (r=%d published=%d)\n", what, r, published); return 1; }
    return 0;
}

int main(int argc, char** argv) {
    char path[1024];
    long allLen, expLen, len;
    snprintf(path, sizeof path, "%s/ALL.PFB", argv[1]);
    uint8_t* all = slurp(path, &allLen);
    snprintf(path, sizeof path, "%s/ALL.EXPECT", argv[1]);
    sExpect = slurp(path, &expLen);
    if (!all || !sExpect) return 2;
    uint32_t count = be32(all + 4), idTable = 8 + 4 * count, at = 0;
    for (uint32_t c = 0; c < count; c++) {
        uint32_t id = be16(all + idTable + 2 * c);
        sFrames[id] = be16(all + be32(all + 8 + 4 * c));
        sExpectAt[id] = at;
        at += 2 * 67 * sFrames[id];
    }
    if (at != (uint32_t)expLen) { puts("expect length"); return 1; }

    /* Corruption cases on the first scene pack (nothing registered yet). */
    long pl;
    uint8_t* pack = argc > 2 ? slurp(argv[2], &pl) : NULL;
    if (pack) {
        uint32_t pc = be32(pack + 4), pid = be16(pack + 8 + 4 * pc);
        uint32_t blk = be32(pack + 8);                 /* first block */
        int bad = 0;
        bad |= expect_reject(pack, pl, "magic", 3, 1, '1', 0, pid);
        bad |= expect_reject(pack, pl, "stride 0", blk + 4, 1, 0, 0, pid);
        bad |= expect_reject(pack, pl, "blockK 0", blk + 5, 1, 0, 0, pid);
        bad |= expect_reject(pack, pl, "frames 0", blk + 0, 2, 0, 0, pid);
        bad |= expect_reject(pack, pl, "kept", blk + 2, 2, be16(pack + blk + 2) + 1, 0, pid);
        bad |= expect_reject(pack, pl, "odd shift", blk + 12 + 134 + 67 + 63, 1, 3, 0, pid);
        bad |= expect_reject(pack, pl, "shift 10", blk + 12 + 134 + 67 + 63, 1, 10, 0, pid);
        bad |= expect_reject(pack, pl, "width 17", blk + 12 + 134 + 3, 1, 17, 0, pid);
        bad |= expect_reject(pack, pl, "bits_a", blk + 6, 2, be16(pack + blk + 6) + 1, 0, pid);
        bad |= expect_reject(pack, pl, "block table", blk + 340 + 3, 1, 1, 0, pid);
        bad |= expect_reject(pack, pl, "truncated", 0, 0, 0, 40, pid);
        bad |= expect_reject(pack, pl, "id range", 8 + 4 * pc, 2, 0xFFFF, 0, pid);
        if (pc > 1) bad |= expect_reject(pack, pl, "duplicate id", 8 + 4 * pc + 2, 2, pid, 0, pid);
        if (bad) return 1;
    }

    snprintf(path, sizeof path, "%s/RESIDENT.PFB", argv[1]);
    uint8_t* resident = slurp(path, &len);
    uint32_t frames = 0;
    if (!resident || PlayerFrameBank_Register(resident, (uint32_t)len) <= 0) { puts("resident"); return 1; }
    if (PlayerFrameBank_Register(resident, (uint32_t)len) != -4) { puts("resident twice accepted"); return 1; }
    if (check_file(resident, &frames)) return 1;

    static uint8_t covered[65536];
    uint32_t rc = be32(resident + 4);
    for (uint32_t i = 0; i < rc; i++) covered[be16(resident + 8 + 4 * rc + 2 * i)] = 1;
    int npacks = 0;
    for (int a = 2; a < argc; a++, npacks++) {
        uint8_t* p = slurp(argv[a], &len);
        if (!p || PlayerFrameBank_Register(p, (uint32_t)len) <= 0) { printf("pack %s\n", argv[a]); return 1; }
        if (check_file(p, &frames)) return 1;
        uint32_t c = be32(p + 4), id0 = be16(p + 8 + 4 * c);
        for (uint32_t i = 0; i < c; i++) covered[be16(p + 8 + 4 * c + 2 * i)] = 1;
        PlayerFrameBank_Unregister(p, (uint32_t)len);
        int16_t out[67];
        int before = sFails;
        if (PlayerFrameBank_Load(id0, 0, out) != -2 || sFails != before + 1) { puts("unloaded pack not loud"); return 1; }
        free(p);
    }
    /* Untriggered ids (in no file) and frame overrun fail loud. */
    int16_t out[67];
    uint32_t orphans = 0;
    for (uint32_t c = 0; c < count; c++) {
        uint32_t id = be16(all + idTable + 2 * c);
        if (covered[id]) continue;
        int before = sFails;
        if (PlayerFrameBank_Load(id, 0, out) != -2 || sFails != before + 1) { puts("orphan silent"); return 1; }
        orphans++;
    }
    uint32_t rid = be16(resident + 8 + 4 * rc);
    if (PlayerFrameBank_Load(rid, 60000, out) != -3 || sLastCode != -3) { puts("frame range not loud"); return 1; }
    /* Approved scene-pack change + rollback with real packs A and B. */
    if (argc > 3) {
        long la, lb;
        uint8_t* A = slurp(argv[2], &la);
        uint8_t* B = slurp(argv[3], &lb);
        uint32_t cap = (uint32_t)(la > lb ? la : lb) + 64, home = 0;
        uint8_t* buf = (uint8_t*)malloc(cap);
        Src sa = { A, la, 0, 0 }, sb = { B, lb, 0, 0 }, bad = { B, lb, 1, 0 }, dead = { A, la, 0, 1 };
        uint32_t idA = be16(A + 8 + 4 * be32(A + 4)), idB = be16(B + 8 + 4 * be32(B + 4));
        int16_t o[67];
        if (PlayerFrameBank_ChangeScenePack(buf, cap, &home, read_src, &sa, NULL, NULL) != 0 ||
            PlayerFrameBank_Load(idA, 0, o) != 0) { puts("swap none->A"); return 1; }
        if (PlayerFrameBank_ChangeScenePack(buf, cap, &home, read_src, &sb, read_src, &sa) != 0 ||
            PlayerFrameBank_Load(idB, 0, o) != 0) { puts("swap A->B"); return 1; }
        int before = sFails;
        if (PlayerFrameBank_ChangeScenePack(buf, cap, &home, read_src, &bad, read_src, &sb) != 1 ||
            PlayerFrameBank_Load(idB, 0, o) != 0 || sFails != before) { puts("rollback to B"); return 1; }
        if (PlayerFrameBank_ChangeScenePack(buf, cap, &home, read_src, &bad, read_src, &dead) != -1 ||
            PlayerFrameBank_Load(rid, 0, o) != -2) { puts("double failure resumed"); return 1; }
        puts("scene-pack change: commit, rollback by reload, double failure stays stopped PASS");
    }
    printf("frame bank adapter PASS: %u frames, %d packs one at a time, %u untriggered ids loud, "
           "13 corrupt/duplicate banks refused\n", frames, npacks, orphans);
    return 0;
}
