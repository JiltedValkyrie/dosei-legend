#pragma GCC optimize("Os") /* cold menu/save/script code: size over speed (work RAM) */
/* Compile the SDK allocator in this translation unit without modifying the
 * shared SDK or its snapshot. Calls from every other SDK/game unit enter the
 * wrappers below, so boot and temporary load peaks are included. */
#define jo_malloc_with_behaviour dosei_allocator_malloc
#define jo_free dosei_allocator_free
#define jo_add_memory_zone dosei_allocator_add_zone
#define jo_reduce_memory_fragmentation dosei_allocator_reduce
/* The SDK percent uses JO_PERCENT_USED (soft-float); replaced below. */
#define jo_memory_usage_percent dosei_allocator_usage_percent_float
#include "malloc.c"
#undef jo_memory_usage_percent
#undef jo_malloc_with_behaviour
#undef jo_free
#undef jo_add_memory_zone
#undef jo_reduce_memory_fragmentation
#include "heap_profile.h"

typedef char heap_zone_count_matches[
    HEAP_PROFILE_ZONES == JO_MALLOC_MAX_MEMORY_ZONE ? 1 : -1];
heap_profile_t dosei_heap_profile;

/* Same walk as the SDK, integer percent (human rule: no soft-float). */
int jo_memory_usage_percent(void)
{
    int zone;
    unsigned int total = 0, free_bytes = 0;
    for (zone = 0; zone < __jo_memory_zone_index; ++zone) {
        jo_memory_block *block = (jo_memory_block *)memory_zones[zone].begin;
        total += memory_zones[zone].end - memory_zones[zone].begin;
        if (memory_zones[zone].high < memory_zones[zone].end)
            free_bytes += memory_zones[zone].end - memory_zones[zone].high;
        while ((unsigned char *)block < memory_zones[zone].high) {
            if (block->zone == JO_BLOCK_FREE) free_bytes += block->size;
            block = (jo_memory_block *)(((unsigned char *)block) + block->size);
        }
    }
    /* total < 8 MB: (used / 64) * 100 fits 32 bits. */
    return total ? (int)(((total - free_bytes) / 64u) * 100u / (total / 64u ? total / 64u : 1u)) : 0;
}
void jo_reduce_memory_fragmentation(void);

static void profile_extent(unsigned int zone)
{
    heap_zone_profile_t *p = &dosei_heap_profile.zone[zone];
    p->extent = memory_zones[zone].high - memory_zones[zone].begin;
    if (p->extent > p->peak_extent) p->peak_extent = p->extent;
}

void jo_add_memory_zone(unsigned char *ptr, const unsigned int size)
{
    int before = __jo_memory_zone_index;
    dosei_allocator_add_zone(ptr, size);
    if (__jo_memory_zone_index != before) {
        heap_zone_profile_t *p = &dosei_heap_profile.zone[before];
        p->base = (uintptr_t)ptr;
        p->capacity = size;
        dosei_heap_profile.zones = __jo_memory_zone_index;
    }
}

/* The SDK's SAME_BLOCK_SIZE path retries a full zone forever instead of
 * advancing to the next zone. Lists use that mode, including boot callbacks.
 * Preserve exact-size reuse, but bound each scan and spill into cart RAM. */
static void *allocate_same_size(unsigned int n)
{
    int zone;
    unsigned int size;
    if (!n || n > ~0u - sizeof(jo_memory_block) - 3u) return JO_NULL;
    size = (n + sizeof(jo_memory_block) + 3u) & ~3u;
    for (zone = 0; zone < __jo_memory_zone_index; ++zone) {
        unsigned char *ptr = memory_zones[zone].begin;
        while (ptr < memory_zones[zone].high) {
            jo_memory_block *block = (jo_memory_block *)ptr;
            unsigned int remaining = memory_zones[zone].high - ptr;
            if (remaining < sizeof(*block) || block->size < sizeof(*block) ||
                (block->size & 3u) || block->size > remaining) return JO_NULL;
            if (block->zone == JO_BLOCK_FREE && block->size == size) {
                block->zone = zone;
                return block + 1;
            }
            ptr += block->size;
        }
        if (size <= (unsigned int)(memory_zones[zone].end - ptr)) {
            jo_memory_block *block = (jo_memory_block *)ptr;
            block->zone = zone;
            block->size = size;
            memory_zones[zone].high += size;
            return block + 1;
        }
    }
    return JO_NULL;
}

void *jo_malloc_with_behaviour(unsigned int n, const jo_malloc_behaviour behaviour)
{
    unsigned int needed;
    if (!n || n > ~0u - sizeof(jo_memory_block) - 3u) return JO_NULL;
    needed = (n + sizeof(jo_memory_block) + 3u) & ~3u;
    void *result = behaviour == JO_MALLOC_TRY_REUSE_SAME_BLOCK_SIZE
        ? allocate_same_size(n) : dosei_allocator_malloc(n, behaviour);
    if (!result) {
        /* Scene/clip teardown leaves adjacent holes. Merge before declaring
         * OOM, without moving live allocations or changing their pointers. */
        jo_reduce_memory_fragmentation();
        result = behaviour == JO_MALLOC_TRY_REUSE_SAME_BLOCK_SIZE
            ? allocate_same_size(n) : dosei_allocator_malloc(n, behaviour);
    }
    if (result) {
        jo_memory_block *block = ((jo_memory_block *)result) - 1;
        /* SDK reuse consumes the ENTIRE free block. A tiny file probe could
         * otherwise pin a freed 224 KB animation until the next scene. */
        if (block->size - needed >= sizeof(*block) + 4u) {
            jo_memory_block *tail = (jo_memory_block *)((unsigned char *)block + needed);
            tail->size = block->size - needed;
            tail->zone = JO_BLOCK_FREE;
            block->size = needed;
        }
        heap_zone_profile_t *p = &dosei_heap_profile.zone[block->zone];
        p->live += block->size;
        if (p->live > p->peak_live) p->peak_live = p->live;
        profile_extent(block->zone);
    } else {
        ++dosei_heap_profile.failed_allocations;
    }
    return result;
}

void jo_free(const void * const ptr)
{
    if (ptr) {
        const jo_memory_block *block = ((const jo_memory_block *)ptr) - 1;
        unsigned int zone = block->zone;
        unsigned int size = block->size;
#ifdef JO_DEBUG
        if (size == 0 || JO_MOD_POW2(size, 4) != 0) {
            dosei_allocator_free(ptr); /* preserve SDK error handling */
            return;
        }
#endif
        dosei_allocator_free(ptr);
        dosei_heap_profile.zone[zone].live -= size;
        profile_extent(zone);
    } else {
        dosei_allocator_free(ptr);
    }
}

void jo_reduce_memory_fragmentation(void)
{
    unsigned int zone;
    /* The SDK only retracts the free tail; it never combines interior holes. */
    for (zone = 0; zone < (unsigned int)__jo_memory_zone_index; ++zone) {
        unsigned char *ptr = memory_zones[zone].begin;
        jo_memory_block *previous = JO_NULL;
        while (ptr < memory_zones[zone].high) {
            jo_memory_block *block = (jo_memory_block *)ptr;
            unsigned int remaining = memory_zones[zone].high - ptr;
            if (remaining < sizeof(*block) || block->size < sizeof(*block) ||
                (block->size & 3u) || block->size > remaining) return;
            ptr += block->size;
            if (block->zone != JO_BLOCK_FREE) previous = JO_NULL;
            else if (previous) previous->size += block->size;
            else previous = block;
        }
    }
    dosei_allocator_reduce();
    for (zone = 0; zone < dosei_heap_profile.zones; ++zone)
        profile_extent(zone);
}
