#ifndef DOSEI_FIELD_STREAM_H
#define DOSEI_FIELD_STREAM_H
/*
** Hyrule Field distance streaming: KRM2 layout (tools/build_field_chunks.py)
** and the pure selection / slot logic, shared by kokiri_sgl.c and host tests.
**
** KRM2 geometry and pixels occupy separate RAM-cart blocks. Pieces are grouped; members
** of a group (a cell's full/LOD2 pair, an object's LOD0/LOD1 pair) are
** exclusive, so at most one is resident. A resident member stays while Link
** is inside its band widened by the hysteresis; otherwise the first member
** whose exact band holds Link is chosen. Distances are XZ to piece bounds,
** compared squared in 64-bit integers (SH-2 has no FPU).
**
** Owl mode: while the Field owl is out, LOD0 close-ups are refused and their
** LOD1 originals cover the near band too, freeing table space for the owl.
** The bake checks both modes.
*/
#include <stdint.h>

#define FIELD_STREAM_MAGIC   0x4b524d32u  /* 'KRM2' */
#define FIELD_STREAM_VERSION 1u
#define FIELD_KIND_FULL 0u
#define FIELD_KIND_FAR  1u
#define FIELD_KIND_LOD1 2u
#define FIELD_KIND_LOD0 3u
#define FIELD_KIND_LANDMARK 4u
#define FIELD_PIECE_LANDMARK 1u /* piece.pad: retained source cards/buildings */
#define FIELD_FAR_INF   0xFFFFu
#define FIELD_NONE      0xFFFFu
#define FIELD_MAX_BUCKETS 16u

typedef struct {
    uint32_t magic, version, pieces, tiles, pixel_bytes, buckets, slots, total;
    uint32_t max_points, max_polys, max_pieces, hysteresis, pool_offset, groups;
    uint32_t far, reserved;
} field_header_t;

typedef struct { uint32_t size, slots; } field_bucket_t;

typedef struct {
    uint16_t width, height;
    uint32_t offset, length;      /* into the pixel pool */
    uint16_t bucket, pad;
} field_tile_t;

typedef struct {
    int32_t  bounds[6];           /* min xyz, max xyz; source space, Y up */
    uint16_t near, far;           /* XZ band [near, far); far FIELD_FAR_INF */
    uint16_t points, polys, refs, kind, group, pad;
    uint32_t data, pad2;          /* POINT[points] POLYGON[polys] ATTR[polys] u16 refs */
} field_piece_t;

typedef char field_header_size[sizeof(field_header_t) == 64 ? 1 : -1];
typedef char field_bucket_size[sizeof(field_bucket_t) == 8 ? 1 : -1];
typedef char field_tile_size[sizeof(field_tile_t) == 16 ? 1 : -1];
typedef char field_piece_size[sizeof(field_piece_t) == 48 ? 1 : -1];

static inline int64_t field_distance2(const int32_t b[6], int x, int z)
{
    int64_t dx = x < b[0] ? (int64_t)b[0] - x : x > b[3] ? (int64_t)x - b[3] : 0;
    int64_t dz = z < b[2] ? (int64_t)b[2] - z : z > b[5] ? (int64_t)z - b[5] : 0;
    return dx * dx + dz * dz;
}

/* Is distance-squared d2 inside the piece band widened by `widen`? */
static inline int field_in_band(const field_piece_t *p, int64_t d2, int widen, int owl)
{
    int64_t lo, hi;
    if (owl && p->kind == FIELD_KIND_LOD0) return 0;
    lo = (owl && p->kind == FIELD_KIND_LOD1) ? 0 : (int64_t)p->near - widen;
    if (lo > 0 && d2 < lo * lo) return 0;
    if (p->far == FIELD_FAR_INF) return 1;
    hi = (int64_t)p->far + widen;
    return d2 < hi * hi;
}

/* Fill want[groups] for Link at (x, z); returns nonzero when it differs
 * from current[]. Bad group ids are skipped, never written out of range. */
static inline int field_choose(const field_piece_t *pieces, unsigned int count,
                               const uint16_t *current, uint16_t *want,
                               unsigned int groups, int x, int z, int widen, int owl)
{
    unsigned int g, i;
    int changed = 0;
    for (g = 0; g < groups; ++g) {
        unsigned int c = current[g];
        want[g] = FIELD_NONE;
        if (c < count && pieces[c].group == g &&
            field_in_band(&pieces[c], field_distance2(pieces[c].bounds, x, z), widen, owl))
            want[g] = (uint16_t)c;
    }
    for (i = 0; i < count; ++i) {
        g = pieces[i].group;
        if (g >= groups || want[g] != FIELD_NONE) continue;
        if (field_in_band(&pieces[i], field_distance2(pieces[i].bounds, x, z), 0, owl))
            want[g] = (uint16_t)i;
    }
    for (g = 0; g < groups; ++g) changed |= want[g] != current[g];
    return changed;
}

/* Fixed per-bucket VRAM slots: bucket b owns slots [first[b], first[b]+n[b]).
 * stack[] holds free slot ids, one region per bucket; top[b] counts them. */
typedef struct {
    unsigned int buckets;
    uint16_t first[FIELD_MAX_BUCKETS], count[FIELD_MAX_BUCKETS], top[FIELD_MAX_BUCKETS];
    uint16_t *stack;
} field_slots_t;

static inline int field_slots_init(field_slots_t *s, const field_bucket_t *b,
                                   unsigned int buckets, uint16_t *stack, unsigned int capacity)
{
    unsigned int i, j, next = 0;
    if (buckets > FIELD_MAX_BUCKETS) return 0;
    s->buckets = buckets;
    s->stack = stack;
    for (i = 0; i < buckets; ++i) {
        if (b[i].slots > capacity - next) return 0;
        s->first[i] = (uint16_t)next;
        s->count[i] = (uint16_t)b[i].slots;
        s->top[i] = (uint16_t)b[i].slots;
        /* Pop order: lowest slot first. */
        for (j = 0; j < b[i].slots; ++j)
            stack[next + j] = (uint16_t)(next + b[i].slots - 1 - j);
        next += b[i].slots;
    }
    return 1;
}

static inline unsigned int field_slot_alloc(field_slots_t *s, unsigned int bucket)
{
    if (bucket >= s->buckets || !s->top[bucket]) return FIELD_NONE;
    return s->stack[s->first[bucket] + --s->top[bucket]];
}

static inline int field_slot_free(field_slots_t *s, unsigned int bucket, unsigned int slot)
{
    if (bucket >= s->buckets || s->top[bucket] >= s->count[bucket] ||
        slot < s->first[bucket] || slot >= (unsigned int)s->first[bucket] + s->count[bucket])
        return 0;
    s->stack[s->first[bucket] + s->top[bucket]++] = (uint16_t)slot;
    return 1;
}

#endif
