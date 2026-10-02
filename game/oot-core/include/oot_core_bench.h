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

/* The blob entry table is in oot_core_api.h. */

#endif
