/* Host driver for tests/test_heap_model_allocator.py: the game's real
 * allocator (src/heap_profile.c wrapping joengine malloc.c, both copied next
 * to the jo_shim headers) replays an op trace and prints every zone layout.
 *
 *   z <bytes>            add a zone
 *   m <key> <n> <beh>    allocate (beh 0 fast, 1 reuse, 2 same size)
 *   f <key>              free
 * After each m/f: "R <zone>|-1" then "L <zone> <off>:<size>:<free> ..." per zone.
 */
#include <stdio.h>
#include <stdlib.h>
#include "heap_profile.c"

#define KEYS 4096
static void *ptrs[KEYS];
static unsigned char *bases[JO_MALLOC_MAX_MEMORY_ZONE];

static void dump(void)
{
    int z;
    for (z = 0; z < __jo_memory_zone_index; ++z) {
        unsigned char *p = memory_zones[z].begin;
        printf("L %d", z);
        while (p < memory_zones[z].high) {
            jo_memory_block *b = (jo_memory_block *)p;
            printf(" %u:%u:%d", (unsigned)(p - bases[z]), b->size, b->zone == (short)JO_BLOCK_FREE);
            p += b->size;
        }
        printf("\n");
    }
}

int main(void)
{
    char op;
    while (scanf(" %c", &op) == 1) {
        if (op == 'z') {
            unsigned bytes;
            if (scanf("%u", &bytes) != 1) return 2;
            bases[__jo_memory_zone_index] = (unsigned char *)calloc(1, bytes + 16);
            jo_add_memory_zone(bases[__jo_memory_zone_index], bytes);
        } else if (op == 'm') {
            unsigned key, n, beh;
            if (scanf("%u %u %u", &key, &n, &beh) != 3 || key >= KEYS) return 2;
            ptrs[key] = jo_malloc_with_behaviour(n, (jo_malloc_behaviour)(beh == 0 ? JO_FAST_ALLOCATION :
                                                beh == 1 ? JO_MALLOC_TRY_REUSE_BLOCK :
                                                JO_MALLOC_TRY_REUSE_SAME_BLOCK_SIZE));
            printf("R %d\n", ptrs[key] ? ((jo_memory_block *)ptrs[key] - 1)->zone : -1);
            dump();
        } else if (op == 'f') {
            unsigned key;
            if (scanf("%u", &key) != 1 || key >= KEYS) return 2;
            jo_free(ptrs[key]);
            ptrs[key] = 0;
            printf("R 0\n");
            dump();
        }
    }
    return 0;
}
