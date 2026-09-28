#ifndef DOSEI_HEAP_PROFILE_H
#define DOSEI_HEAP_PROFILE_H
#include <stdint.h>

/* Per allocator zone, including block headers/alignment and reused-block slack.
 * Extent includes holes below the allocator's high pointer. Live excludes them.
 * Peaks survive frees and scene transitions. No allocation is made by profiling.
 * Zone 0 is work RAM; cartridge zones must not dilute its usage percentage. */
#define HEAP_PROFILE_ZONES 9
typedef struct {
    uintptr_t base;
    uint32_t capacity, live, peak_live, extent, peak_extent;
} heap_zone_profile_t;
typedef struct {
    uint32_t zones, failed_allocations;
    heap_zone_profile_t zone[HEAP_PROFILE_ZONES];
} heap_profile_t;

/* Retained in Clean builds for emulator/debugger inspection. Read on the main
 * CPU between allocations; this is not a concurrently synchronized snapshot. */
extern heap_profile_t dosei_heap_profile;
#endif
