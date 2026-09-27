#include "text_pool.h"

static unsigned int     be16(const uint8_t *p)
{
    return ((unsigned int)p[0] << 8) | p[1];
}

bool            text_pool_bind(text_pool_t *pool, const char magic[4],
                               const uint8_t *blob, uint32_t bytes,
                               unsigned int count, uint32_t max_bytes)
{
    uint32_t    head = 6u + 2u * count, i;

    pool->blob = 0;
    pool->bytes = 0;
    pool->count = 0;
    if (!blob || bytes <= head || bytes > max_bytes ||
        blob[0] != (uint8_t)magic[0] || blob[1] != (uint8_t)magic[1] ||
        blob[2] != (uint8_t)magic[2] || blob[3] != (uint8_t)magic[3] ||
        be16(blob + 4) != count || blob[bytes - 1] != 0)
        return (false);
    /* A stale file from another build would show the wrong lines; refuse any
    ** offset past the string area. The final NUL bounds every string. */
    for (i = 0; i < count; ++i)
        if (be16(blob + 6 + 2 * i) >= bytes - head)
            return (false);
    pool->blob = blob;
    pool->bytes = bytes;
    pool->count = (uint16_t)count;
    return (true);
}

const char     *text_pool_line(const text_pool_t *pool, unsigned int index)
{
    if (!pool->blob || index >= pool->count)
        return ("");
    return ((const char *)pool->blob + 6u + 2u * pool->count +
            be16(pool->blob + 6 + 2 * index));
}
