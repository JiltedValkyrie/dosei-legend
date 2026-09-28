/* Compile the SDK allocator in this translation unit without modifying the
 * shared SDK or its snapshot. Calls from every other SDK/game unit enter the
 * wrappers below, so boot and temporary load peaks are included. */
#define jo_malloc_with_behaviour dosei_allocator_malloc
#define jo_free dosei_allocator_free
#define jo_add_memory_zone dosei_allocator_add_zone
#define jo_reduce_memory_fragmentation dosei_allocator_reduce
#include "malloc.c"
#undef jo_malloc_with_behaviour
#undef jo_free
#undef jo_add_memory_zone
#undef jo_reduce_memory_fragmentation
#include "heap_profile.h"

typedef char heap_zone_count_matches[
    HEAP_PROFILE_ZONES == JO_MALLOC_MAX_MEMORY_ZONE ? 1 : -1];
heap_profile_t dosei_heap_profile;

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
    void *result = behaviour == JO_MALLOC_TRY_REUSE_SAME_BLOCK_SIZE
        ? allocate_same_size(n) : dosei_allocator_malloc(n, behaviour);
    if (result) {
        jo_memory_block *block = ((jo_memory_block *)result) - 1;
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
    dosei_allocator_reduce();
    for (zone = 0; zone < dosei_heap_profile.zones; ++zone)
        profile_extent(zone);
}
