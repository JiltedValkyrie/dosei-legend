/* host shim for tests/test_heap_model_allocator.py (jo/malloc.h subset) */
#define JO_MALLOC_MAX_MEMORY_ZONE (9)
typedef enum { JO_FAST_ALLOCATION, JO_MALLOC_TRY_REUSE_BLOCK, JO_MALLOC_TRY_REUSE_SAME_BLOCK_SIZE } jo_malloc_behaviour;
void *jo_malloc_with_behaviour(unsigned int n, const jo_malloc_behaviour behaviour);
void jo_free(const void * const p);
void jo_add_memory_zone(unsigned char *ptr, const unsigned int size_in_bytes);
void jo_reduce_memory_fragmentation(void);
int jo_memory_usage_percent(void);
