/* host shim for tests/test_heap_model_allocator.py */
#include <string.h>
#define JO_NULL ((void *)0)
#define JO_ZERO(x) ((x) = 0)
#define JO_MOD_POW2(n, p) ((n) & ((p) - 1))
#define jo_memset memset
#define JO_PERCENT_USED(total, free_bytes) ((int)(((total) - (free_bytes)) * 100.0 / (total)))
static inline void jo_core_error(const char *f, ...) { (void)f; }
