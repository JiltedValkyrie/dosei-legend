#ifndef DOSEI_TEXT_POOL_H
#define DOSEI_TEXT_POOL_H
#include <stdbool.h>
#include <stdint.h>

/*
** A pool of NUL-terminated lines kept off work RAM (BUG-033, BUG-037). File
** layout: 4-byte magic, u16 BE line count, u16 BE offsets into the string
** area, then the strings. Loaded once at boot into a fixed cart carve; host
** tests bind the same file.
*/
typedef struct {
    const uint8_t  *blob;
    uint32_t        bytes;
    uint16_t        count;
} text_pool_t;

/* Validate `blob` (magic, exactly `count` lines, at most `max_bytes`, every
** offset inside the string area, final NUL) and use it in place. False
** leaves the pool unbound: every line then reads "". */
bool         text_pool_bind(text_pool_t *pool, const char magic[4],
                            const uint8_t *blob, uint32_t bytes,
                            unsigned int count, uint32_t max_bytes);
const char  *text_pool_line(const text_pool_t *pool, unsigned int index);

#endif
