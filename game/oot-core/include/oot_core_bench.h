/* oot-core Phase 0 SH-2 benchmark. Shared by C (main.c) and oot-core C++. */
#ifndef OOT_CORE_BENCH_H
#define OOT_CORE_BENCH_H

enum {
    OOT_BENCH_MULADD,
    OOT_BENCH_DIV,
    OOT_BENCH_SMOOTHSTEP,
    OOT_BENCH_DIST,
    OOT_BENCH_SIN,
    OOT_BENCH_ATAN2,
    OOT_BENCH_COUNT
};

typedef struct OotCoreBench {
    /* Nanoseconds per call (microseconds per 1000 calls). */
    unsigned int ns[OOT_BENCH_COUNT];
} OotCoreBench;

typedef void (*OotCoreBenchFn)(OotCoreBench* out, unsigned int (*ticks)(void),
                               unsigned int (*ticks_to_us)(unsigned int));

/*
 * OOTCORE.BIN starts with this table (oot-core/oot-core.ld, section .oot_entry).
 * The blob is linked at OOT_CORE_LOAD_ADDR (cached cart alias) and is
 * self-contained: the game reaches it only through these pointers.
 */
#define OOT_CORE_MAGIC 0x4F4F5443u /* 'OOTC' */
#define OOT_CORE_VERSION 2u
typedef struct OotCoreEntry {
    unsigned int magic;
    unsigned int version;
    const void* end; /* first address past .bss: must fit the cart carve */
    OotCoreBenchFn bench;
    /* Call once after load, before anything else: runs the blob's own static
     * initializers. GCC 9 emits a ctor for a file-scope table whose Fx divide
     * it cannot fold (e.g. z_actor sAttentionRanges). Jo never runs .ctors. */
    void (*init)(void);
} OotCoreEntry;

#endif
