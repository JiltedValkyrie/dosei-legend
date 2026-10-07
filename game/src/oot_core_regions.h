#ifndef OOT_CORE_REGIONS_H
#define OOT_CORE_REGIONS_H
/* Multi-region oot-core loader (isolated; see oot_core_regions.c). */
#include <stdint.h>

#define OOT_REGION_SPANS 5

#ifdef __cplusplus
extern "C" {
#endif

typedef struct oot_region_span {
    uint32_t address;
    uint32_t bytes;
} oot_region_span_t;

enum {
    OOT_REGIONS_BAD_HEADER = -1,
    OOT_REGIONS_BAD_RANGE = -2,
    OOT_REGIONS_OUTSIDE = -3,
    OOT_REGIONS_OVERLAP = -4,
    OOT_REGIONS_BAD_BSS = -5,
};

extern const oot_region_span_t oot_region_spans[OOT_REGION_SPANS];

/* Region count, or a negative OOT_REGIONS_* error. Nothing is written. */
int oot_core_regions_validate(const uint8_t *file, uint32_t length,
                              const oot_region_span_t *spans, int span_count);

/* Validate everything first, then copy each image and zero BSS.
 * to_pointer maps a design address to a writable pointer (identity on the
 * Saturn; a host buffer in tests). Returns region count or error. */
int oot_core_regions_load(const uint8_t *file, uint32_t length,
                          const oot_region_span_t *spans, int span_count,
                          uint8_t *(*to_pointer)(uint32_t address));
#ifdef __cplusplus
}
#endif
#endif
