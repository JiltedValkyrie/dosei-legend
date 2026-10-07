/*
 * Demand-loaded real-Player animation cache (human directive 2026-10-06,
 * PLAYER_MIGRATION.md "Demand-loaded Player animation"). Isolated: not in the
 * live OOT_CORE_SRCS list until Player cutover.
 *
 * The common gameplay set is registered resident (PlayerFrameBank_Register).
 * Every other supported clip lives in an indexed archive on disc (ALL.PFB;
 * its 'PFB2' header is the manifest id -> byte range). This layer sits ABOVE
 * the decoder and works in request handles, one per action or cutscene:
 *
 *   h = Open(ids, resident, n)  validate the WHOLE set: unknown id, failed
 *                               clip or a set that can never fit (bytes or
 *                               entries) is rejected before anything loads.
 *   Reserve(h)                  all-or-nothing: allocates every missing member
 *                               at once (evicting only unpinned warm clips),
 *                               pins every member, issues the reads. A set
 *                               that fits but is blocked by other handles'
 *                               pins returns WAIT (temporary contention).
 *   Poll(h)                     READY when every member is published, else
 *                               LOADING or a hard error. Never adds pins.
 *   Close(h)                    release or cancel: unpins; loaded clips stay
 *                               warm, in-flight reads finish and stay warm.
 *
 * A cutscene opens one handle for all its shots and branches and keeps it
 * until the cutscene ends: no per-shot loads, no load pauses in playback.
 * Reads are serviced by the host (CD/audio ownership stays host side), which
 * calls Complete(); each block is fully validated before the decoder sees it.
 * Evicted clips are withdrawn from the decoder before their bytes are reused.
 */
#include <stdint.h>

extern "C" int PlayerFrameBank_PublishBlock(uint32_t id, const uint8_t* block, uint32_t bytes,
                                            uint32_t slack);
extern "C" void PlayerFrameBank_Retract(uint32_t id, const uint8_t* block);

#define PAC_MAX_IDS 512
#define PAC_MAX_ENTRIES 64
#define PAC_MAX_HANDLES 8
#define PAC_SLACK 4            /* 32-bit decode window past the stream */
#define PAC_TABLE 340          /* smallest valid clip block (descriptor) */

enum PacState {
    PAC_ABSENT = 0,
    PAC_LOADING = 1,
    PAC_READY = 2,
    PAC_WAIT = 3,              /* fits, but other handles' pins block it now */
    PAC_UNKNOWN = -1,          /* id not in the disc manifest */
    PAC_CORRUPT = -2,          /* read finished, block failed validation */
    PAC_IO_FAIL = -3,          /* host read failed */
    PAC_TOO_BIG = -4,          /* set can never fit: fix the budget */
    PAC_BAD_HANDLE = -5,
};

typedef int (*PacReadStart)(uint32_t offset, uint32_t bytes, uint8_t* dst, uint32_t token);

typedef struct PacEntry {
    uint16_t id;
    uint16_t pins;
    int8_t state;
    uint32_t start, bytes;      /* arena range incl. PAC_SLACK */
    uint32_t lastUse;
} PacEntry;

typedef struct PacHandle {
    const uint16_t* ids;
    const uint8_t* resident;
    uint16_t count;
    uint8_t open, reserved;
} PacHandle;

static uint8_t* sArena;
static uint32_t sArenaBytes, sClock, sArchiveBytes;
static const uint8_t* sManifest;
static uint32_t sManifestCount;
static int16_t sById[PAC_MAX_IDS];
static int8_t sFailed[PAC_MAX_IDS];
static PacEntry sEntries[PAC_MAX_ENTRIES];
static int sEntryCount;
static PacHandle sHandles[PAC_MAX_HANDLES];
static PacReadStart sRead;

static uint32_t be32(const uint8_t* p) {
    return ((uint32_t)p[0] << 24) | ((uint32_t)p[1] << 16) | ((uint32_t)p[2] << 8) | p[3];
}
static uint32_t be16(const uint8_t* p) { return ((uint32_t)p[0] << 8) | p[1]; }

/* manifest: the first manifestBytes of ALL.PFB (must hold count, offsets and
 * ids). archiveBytes: whole file size. Offsets must start after the header,
 * strictly increase, give every clip at least a descriptor and stay inside
 * the archive before its 4-byte tail pad. Nothing is published on failure. */
extern "C" int PlayerAnimCache_Init(uint8_t* arena, uint32_t arenaBytes, const uint8_t* manifest,
                                    uint32_t manifestBytes, uint32_t archiveBytes,
                                    PacReadStart read) {
    uint32_t i, count, header;

    sManifest = 0;
    if (manifestBytes < 8 || manifest[0] != 'P' || manifest[1] != 'F' || manifest[2] != 'B' ||
        manifest[3] != '2') {
        return -1;
    }
    count = be32(manifest + 4);
    if (count == 0 || count > PAC_MAX_IDS) {
        return -1;
    }
    header = 8 + 4 * count + ((2 * count + 3) & ~3u);
    if (manifestBytes < header || archiveBytes < header + 4) {
        return -1;
    }
    for (i = 0; i < PAC_MAX_IDS; i++) {
        sById[i] = -1;
        sFailed[i] = 0;
    }
    for (i = 0; i < count; i++) {
        uint32_t id = be16(manifest + 8 + 4 * count + 2 * i);
        uint32_t start = be32(manifest + 8 + 4 * i);
        uint32_t end = i + 1 < count ? be32(manifest + 12 + 4 * i) : archiveBytes - 4;
        if (id >= PAC_MAX_IDS || sById[id] >= 0 || start < header || end > archiveBytes - 4 ||
            end < start || end - start < PAC_TABLE) {
            return -1;
        }
        sById[id] = (int16_t)i;
    }
    sArena = arena;
    sArenaBytes = arenaBytes;
    sManifest = manifest;
    sManifestCount = count;
    sArchiveBytes = archiveBytes;
    sEntryCount = 0;
    sClock = 0;
    sRead = read;
    for (i = 0; i < PAC_MAX_HANDLES; i++) {
        sHandles[i].open = 0;
    }
    return (int)count;
}

static uint32_t clip_bytes(uint32_t id, uint32_t* offset) {
    uint32_t i = (uint32_t)sById[id];
    uint32_t start = be32(sManifest + 8 + 4 * i);
    uint32_t end = i + 1 < sManifestCount ? be32(sManifest + 12 + 4 * i) : sArchiveBytes - 4;
    if (offset) *offset = start;
    return end - start;
}

static PacEntry* find(uint32_t id) {
    for (int i = 0; i < sEntryCount; i++) {
        if (sEntries[i].id == id) return &sEntries[i];
    }
    return 0;
}

static void drop(int index) {
    PacEntry* e = &sEntries[index];
    if (e->state == PAC_READY) {
        PlayerFrameBank_Retract(e->id, sArena + e->start);
    }
    sEntries[index] = sEntries[--sEntryCount];
}

static int evict_one(void) {
    int victim = -1;
    for (int i = 0; i < sEntryCount; i++) {
        PacEntry* e = &sEntries[i];
        if (e->state == PAC_READY && e->pins == 0 &&
            (victim < 0 || e->lastUse < sEntries[victim].lastUse)) {
            victim = i;
        }
    }
    if (victim < 0) return 0;
    drop(victim);
    return 1;
}

static int first_fit(uint32_t bytes, uint32_t* start) {
    uint32_t cursor = 0;
    for (;;) {
        int next = -1;
        for (int i = 0; i < sEntryCount; i++) {
            if (sEntries[i].start >= cursor && (next < 0 || sEntries[i].start < sEntries[next].start)) {
                next = i;
            }
        }
        uint32_t gapEnd = next < 0 ? sArenaBytes : sEntries[next].start;
        if (gapEnd - cursor >= bytes) {
            *start = cursor;
            return 1;
        }
        if (next < 0) return 0;
        cursor = sEntries[next].start + sEntries[next].bytes;
    }
}

static int member_needed(const PacHandle* h, int i) {
    if (h->resident[i]) return 0;
    for (int j = 0; j < i; j++) {
        if (h->ids[j] == h->ids[i]) return 0;          /* listed twice */
    }
    return 1;
}

/* Validate a whole set; returns a handle (>= 0) or an error. Impossible sets
 * (more bytes or entries than the arena can ever hold) fail here, before any
 * load. Unknown or already-failed clips fail here too. */
extern "C" int PlayerAnimCache_Open(const uint16_t* ids, const uint8_t* resident, int count) {
    PacHandle probe = { ids, resident, (uint16_t)count, 0, 0 };
    uint32_t bytes = 0;
    int entries = 0, slot = -1;

    if (!sManifest || count <= 0) return PAC_BAD_HANDLE;
    for (int i = 0; i < count; i++) {
        if (ids[i] >= PAC_MAX_IDS || sById[ids[i]] < 0) return PAC_UNKNOWN;
        if (sFailed[ids[i]]) return sFailed[ids[i]];
        if (member_needed(&probe, i)) {
            bytes += clip_bytes(ids[i], 0) + PAC_SLACK;
            entries++;
        }
    }
    if (bytes > sArenaBytes || entries > PAC_MAX_ENTRIES) return PAC_TOO_BIG;
    for (int i = 0; i < PAC_MAX_HANDLES; i++) {
        if (!sHandles[i].open) { slot = i; break; }
    }
    if (slot < 0) return PAC_BAD_HANDLE;
    sHandles[slot] = probe;
    sHandles[slot].open = 1;
    return slot;
}

/* All-or-nothing: every missing member gets its arena range in this call, or
 * none does. Members are pinned from here on, so an early-finished clip can
 * never be evicted while later ones load. Idempotent once reserved. */
extern "C" int PlayerAnimCache_Reserve(int handle) {
    if (handle < 0 || handle >= PAC_MAX_HANDLES || !sHandles[handle].open) return PAC_BAD_HANDLE;
    PacHandle* h = &sHandles[handle];
    if (h->reserved) return PAC_LOADING;

    /* Pin warm/in-flight members first so making room cannot evict them. */
    for (int i = 0; i < h->count; i++) {
        PacEntry* e = member_needed(h, i) ? find(h->ids[i]) : 0;
        if (e) e->pins++;
    }
    int added[PAC_MAX_ENTRIES], nadded = 0, ok = 1;
    uint32_t offsets[PAC_MAX_ENTRIES];
    for (int i = 0; i < h->count && ok; i++) {
        if (!member_needed(h, i) || find(h->ids[i])) continue;
        uint32_t offset, bytes = clip_bytes(h->ids[i], &offset) + PAC_SLACK, start;
        while (sEntryCount == PAC_MAX_ENTRIES || !first_fit(bytes, &start)) {
            if (!evict_one()) { ok = 0; break; }
        }
        if (!ok) break;
        PacEntry* e = &sEntries[sEntryCount++];
        e->id = h->ids[i];
        e->pins = 1;
        e->state = PAC_ABSENT;          /* allocated, read not issued yet */
        e->start = start;
        e->bytes = bytes;
        e->lastUse = ++sClock;
        offsets[nadded] = offset;
        added[nadded++] = e->id;
    }
    if (!ok) {
        /* Undo: drop this call's allocations, unpin the warm members. */
        for (int k = 0; k < nadded; k++) {
            PacEntry* e = find((uint32_t)added[k]);
            if (e) drop((int)(e - sEntries));
        }
        for (int i = 0; i < h->count; i++) {
            PacEntry* e = member_needed(h, i) ? find(h->ids[i]) : 0;
            if (e && e->pins) e->pins--;
        }
        return PAC_WAIT;
    }
    h->reserved = 1;
    for (int k = 0; k < nadded; k++) {
        PacEntry* e = find((uint32_t)added[k]);
        for (uint32_t s = 0; s < PAC_SLACK; s++) sArena[e->start + e->bytes - PAC_SLACK + s] = 0;
        e->state = PAC_LOADING;
        if (sRead(offsets[k], e->bytes - PAC_SLACK, sArena + e->start, e->id) != 0) {
            e->state = PAC_IO_FAIL;     /* reported by Poll; freed on Close */
        }
    }
    return PAC_LOADING;
}

/* Host: a read finished. Validate before publishing. */
extern "C" int PlayerAnimCache_Complete(uint32_t token, int ok) {
    PacEntry* e = find(token);
    if (e == 0 || e->state != PAC_LOADING) return -1;
    if (!ok) {
        e->state = PAC_IO_FAIL;
        sFailed[e->id] = PAC_IO_FAIL;
        return PAC_IO_FAIL;
    }
    if (PlayerFrameBank_PublishBlock(e->id, sArena + e->start, e->bytes - PAC_SLACK, PAC_SLACK) != 0) {
        e->state = PAC_CORRUPT;
        sFailed[e->id] = PAC_CORRUPT;
        return PAC_CORRUPT;
    }
    e->state = PAC_READY;
    return PAC_READY;
}

/* READY / LOADING / WAIT (not reserved yet) / hard error. No pins added. */
extern "C" int PlayerAnimCache_Poll(int handle) {
    if (handle < 0 || handle >= PAC_MAX_HANDLES || !sHandles[handle].open) return PAC_BAD_HANDLE;
    PacHandle* h = &sHandles[handle];
    if (!h->reserved) return PAC_WAIT;
    int all = 1;
    for (int i = 0; i < h->count; i++) {
        if (!member_needed(h, i)) continue;
        PacEntry* e = find(h->ids[i]);
        if (!e) return PAC_BAD_HANDLE;
        if (e->state == PAC_CORRUPT || e->state == PAC_IO_FAIL) return e->state;
        if (e->state != PAC_READY) all = 0;
        e->lastUse = ++sClock;
    }
    return all ? PAC_READY : PAC_LOADING;
}

/* Release (finished) or cancel (abandoned): unpins members. Ready clips stay
 * warm; failed members are freed; in-flight reads finish and stay warm. */
extern "C" void PlayerAnimCache_Close(int handle) {
    if (handle < 0 || handle >= PAC_MAX_HANDLES || !sHandles[handle].open) return;
    PacHandle* h = &sHandles[handle];
    if (h->reserved) {
        for (int i = 0; i < h->count; i++) {
            PacEntry* e = member_needed(h, i) ? find(h->ids[i]) : 0;
            if (!e) continue;
            if (e->pins) e->pins--;
            if (e->pins == 0 && (e->state == PAC_CORRUPT || e->state == PAC_IO_FAIL)) {
                drop((int)(e - sEntries));
            }
        }
    }
    h->open = 0;
    h->reserved = 0;
}

extern "C" int PlayerAnimCache_State(uint32_t id) {
    if (id >= PAC_MAX_IDS || sById[id] < 0) return PAC_UNKNOWN;
    PacEntry* e = find(id);
    if (e) return e->state;
    return sFailed[id] ? sFailed[id] : PAC_ABSENT;
}

extern "C" uint32_t PlayerAnimCache_Used(uint32_t* pinned) {
    uint32_t used = 0, pin = 0;
    for (int i = 0; i < sEntryCount; i++) {
        used += sEntries[i].bytes;
        if (sEntries[i].pins || sEntries[i].state == PAC_LOADING) pin += sEntries[i].bytes;
    }
    if (pinned) *pinned = pin;
    return used;
}
