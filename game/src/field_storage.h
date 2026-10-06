#ifndef DOSEI_FIELD_STORAGE_H
#define DOSEI_FIELD_STORAGE_H
#include "field_stream.h"
#include "fs_range.h"

/* The disk format keeps pixels after geometry. Separate allocations avoid
 * requiring one file-sized hole in the cart heap. Read the overlapping sector
 * twice so the pixel allocation need not start at an aligned file offset.
 * The caller supplies Jo allocation declarations. All math stays 32-bit. */
static bool field_storage_load(const char *name, unsigned char **geometry,
                               unsigned char **pixels, unsigned int *length)
{
    field_header_t h;
    unsigned int tables, start;
    int size = fs_file_size(name);
    *geometry = 0; *pixels = 0; *length = 0;
    if (size < (int)sizeof(h) || !fs_read_sectors(name, 0, &h, sizeof(h)))
        return false;
    if (h.magic != FIELD_STREAM_MAGIC || h.version != FIELD_STREAM_VERSION ||
        h.total != (unsigned int)size || !h.pieces || h.pieces > 255 ||
        !h.groups || h.groups > h.pieces || h.buckets > FIELD_MAX_BUCKETS ||
        h.tiles > 0xFFFE || !h.pixel_bytes || h.pool_offset > h.total ||
        h.pixel_bytes != h.total - h.pool_offset)
        return false;
    tables = sizeof(h) + h.buckets * sizeof(field_bucket_t) +
             h.tiles * (sizeof(field_tile_t) + 32u) + h.pieces * sizeof(field_piece_t);
    if (tables > h.pool_offset) return false;
    start = h.pool_offset & ~2047u;
    *pixels = jo_malloc_with_behaviour(h.total - start, JO_MALLOC_TRY_REUSE_BLOCK);
    if (!*pixels) return false;
    *geometry = jo_malloc_with_behaviour(h.pool_offset, JO_MALLOC_TRY_REUSE_BLOCK);
    if (!*geometry || !fs_read_sectors(name, 0, *geometry, h.pool_offset) ||
        !fs_read_sectors(name, start / 2048u, *pixels, h.total - start)) {
        if (*geometry) jo_free(*geometry);
        jo_free(*pixels);
        *geometry = 0; *pixels = 0;
        return false;
    }
    *length = h.total;
    return true;
}
#endif
