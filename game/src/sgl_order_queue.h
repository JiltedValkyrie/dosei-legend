/*
 * SGL 3.02j sort-queue adapter. Run ONLY in an slSlaveFunc callback queued
 * after every drawable for this frame, before slSynch queues its DMA table.
 *
 * Verified against the project's read-only LIBSGL.A:
 *   sglJ05.o / _sbSortEntry: command +30 is a 16-bit depth key; +32 is next.
 *   sglJ03.o / _sbMakeDMATable: two descending radix passes, high then low.
 *   sglJ01.o / _sbUseOperation: slSlaveFunc is an ordered queue callback.
 *
 * There are 128 high-byte heads per window, followed by 256 temporary heads.
 * SGL prepends in BOTH radix passes. Thus equal-key hardware order is the
 * REVERSE of their order in the current high-byte linked list.
 *
 * Access queue memory through the SAME aliases SGL uses on the slave (the
 * exported Zbuffer and SpriteBuf values), not new uncached aliases: otherwise
 * SGL may retain stale cached links. Only context/data written by the master
 * should be passed/read cache-through. Do not call this from the master while
 * SGL is still producing commands. No SDK files or live VDP1 RAM are patched.
 */
#ifndef DOSEI_SGL_ORDER_QUEUE_H
#define DOSEI_SGL_ORDER_QUEUE_H

#include <stddef.h>
#include <stdint.h>

typedef struct sgl_order_command {
    uint16_t ctrl, link, pmod, colr, srca, size;
    int16_t xa, ya, xb, yb, xc, yc, xd, yd;
    uint16_t grda, key;
    uint32_t next;
} sgl_order_command;

typedef char sgl_order_size_is_36[(sizeof(sgl_order_command) == 36) ? 1 : -1];
typedef char sgl_order_grda_is_28[(offsetof(sgl_order_command, grda) == 28) ? 1 : -1];
typedef char sgl_order_key_is_30[(offsetof(sgl_order_command, key) == 30) ? 1 : -1];
typedef char sgl_order_next_is_32[(offsetof(sgl_order_command, next) == 32) ? 1 : -1];

/* Separate the 32-bit emulated addresses from host pointers. On the Saturn,
 * sprite_memory == (void *)sprite_address. Host tests can instead supply an
 * ordinary byte array and a synthetic 32-bit Saturn base address. */
typedef struct sgl_order_queue {
    volatile uint32_t *heads;       /* 128 + 128 heads; scratch is untouched */
    volatile unsigned char *sprite_memory;
    uint32_t sprite_address;
    uint32_t sprite_bytes;
} sgl_order_queue;

typedef enum sgl_order_result {
    SGL_ORDER_OK = 0,
    SGL_ORDER_BAD_LAYOUT,
    SGL_ORDER_BAD_ADDRESS,
    SGL_ORDER_BAD_KEY,
    SGL_ORDER_CAPACITY,
    SGL_ORDER_BAD_MEMBERSHIP,
    SGL_ORDER_NOT_FOUND,
    SGL_ORDER_MULTIPLE_WINDOWS
} sgl_order_result;

/* Context helper, NOT the alias to use for the slave-owned sort queue. */
static inline void *sgl_order_cache_through(void *pointer)
{
#if UINTPTR_MAX == UINT32_MAX
    return (void *)((uintptr_t)pointer | UINT32_C(0x20000000));
#else
    return pointer;
#endif
}

static inline uint32_t sgl_order_physical(uint32_t address)
{
    return address & ~UINT32_C(0x20000000);
}

static inline int sgl_order_layout_valid(const sgl_order_queue *queue)
{
    return queue && queue->heads && queue->sprite_memory &&
           queue->sprite_bytes >= 72 && queue->sprite_bytes % 72 == 0 &&
           (queue->sprite_address & 3u) == 0;
}

static inline volatile sgl_order_command *
sgl_order_resolve(const sgl_order_queue *queue, uint32_t address)
{
    uint32_t physical = sgl_order_physical(address);
    uint32_t base = sgl_order_physical(queue->sprite_address);
    uint32_t offset;
    if (!address || physical < base) return NULL;
    offset = physical - base;
    if (queue->sprite_bytes < sizeof(sgl_order_command) ||
        offset > queue->sprite_bytes - sizeof(sgl_order_command) ||
        offset % sizeof(sgl_order_command) != 0)
        return NULL;
    return (volatile sgl_order_command *)(queue->sprite_memory + offset);
}

/* Returns the window containing a tag family, e.g. mask/value 0x8000 for
 * Link. No command is changed. A duplicate/cyclic list fails at max_commands.
 * Reject a key in the wrong bucket, including keys outside 0..32767. */
static inline sgl_order_result
sgl_order_find_window(const sgl_order_queue *queue, uint16_t mask,
                      uint16_t value, unsigned int max_commands,
                      unsigned int *found_window)
{
    unsigned int window, total = 0, found = 2;
    if (!sgl_order_layout_valid(queue) || !found_window)
        return SGL_ORDER_BAD_LAYOUT;
    for (window = 0; window < 2; ++window) {
        unsigned int high;
        for (high = 0; high < 128; ++high) {
            uint32_t address = queue->heads[window * 128 + high];
            while (address) {
                volatile sgl_order_command *command = sgl_order_resolve(queue, address);
                if (!command) return SGL_ORDER_BAD_ADDRESS;
                if ((command->key >> 8) != high) return SGL_ORDER_BAD_KEY;
                if (total++ >= max_commands) return SGL_ORDER_CAPACITY;
                if ((command->grda & mask) == value) {
                    if (found != 2 && found != window)
                        return SGL_ORDER_MULTIPLE_WINDOWS;
                    found = window;
                }
                address = command->next;
            }
        }
    }
    if (found == 2) return SGL_ORDER_NOT_FOUND;
    *found_window = found;
    return SGL_ORDER_OK;
}

/* Collect EXACT final hardware draw order, including ties, without mutation.
 * Caller supplies capacity pointers (32-bit addresses) and 256 uint16 slots.
 * All commands in one window belong to one current SpriteBuf half. */
static inline sgl_order_result
sgl_order_collect(const sgl_order_queue *queue, unsigned int window,
                  uint32_t *order, unsigned int capacity, uint16_t ends[256],
                  unsigned int *count)
{
    int high;
    unsigned int total = 0, bank = 2;
    if (count) *count = 0;
    if (!sgl_order_layout_valid(queue) || window > 1 || !order || !ends ||
        !count || capacity > 32767)
        return SGL_ORDER_BAD_LAYOUT;
    for (high = 127; high >= 0; --high) {
        uint32_t address = queue->heads[window * 128 + (unsigned int)high];
        uint32_t head = address;
        unsigned int entries = 0, end, low;
        if (!head) continue;
        for (low = 0; low < 256; ++low) ends[low] = 0;
        while (address) {
            volatile sgl_order_command *command = sgl_order_resolve(queue, address);
            unsigned int current_bank;
            if (!command) return SGL_ORDER_BAD_ADDRESS;
            if ((command->key >> 8) != (unsigned int)high) return SGL_ORDER_BAD_KEY;
            if (total + entries >= capacity) return SGL_ORDER_CAPACITY;
            current_bank = (sgl_order_physical(address) -
                            sgl_order_physical(queue->sprite_address)) /
                           (queue->sprite_bytes / 2);
            if (bank != 2 && bank != current_bank) return SGL_ORDER_BAD_MEMBERSHIP;
            bank = current_bank;
            ++ends[command->key & 255u];
            ++entries;
            address = command->next;
        }
        end = total;
        for (low = 256; low-- > 0;) {
            end += ends[low];
            ends[low] = (uint16_t)end;
        }
        address = head;
        while (address) {
            volatile sgl_order_command *command = sgl_order_resolve(queue, address);
            /* The first pass validated this whole list; it cannot change
             * while this callback owns the slave queue. */
            order[--ends[command->key & 255u]] = address;
            address = command->next;
        }
        total += entries;
    }
    *count = total;
    return SGL_ORDER_OK;
}

static inline unsigned int sgl_order_seen_bytes(const sgl_order_queue *queue)
{
    return (queue->sprite_bytes / sizeof(sgl_order_command) + 7u) / 8u;
}

/* Rebuild one window in precisely the requested order, using unique keys
 * count..1. All original commands must occur exactly once. Validation is
 * complete BEFORE any command/head write, so failure leaves the queue alone.
 *
 * This changes the meaning of its depth keys: no further drawable may be
 * inserted into this window for this frame. Queue this hook LAST. The other
 * window and SGL's low-byte scratch heads are untouched. Caller may reuse
 * the collection histogram for seen, if it has enough bytes; current 2600
 * polygon SGLAREA requires 652 bytes for both SpriteBuf halves. */
static inline sgl_order_result
sgl_order_rebuild(const sgl_order_queue *queue, unsigned int window,
                  const uint32_t *order, unsigned int count,
                  unsigned char *seen, unsigned int seen_capacity)
{
    unsigned int i, old_count = 0, needed, bank = 2;
    if (!sgl_order_layout_valid(queue) || window > 1 || !order || !seen ||
        !count || count > 32767)
        return SGL_ORDER_BAD_LAYOUT;
    needed = sgl_order_seen_bytes(queue);
    if (seen_capacity < needed) return SGL_ORDER_CAPACITY;
    for (i = 0; i < needed; ++i) seen[i] = 0;
    for (i = 0; i < count; ++i) {
        volatile sgl_order_command *command = sgl_order_resolve(queue, order[i]);
        uint32_t offset;
        unsigned int slot, current_bank;
        unsigned char bit;
        if (!command) return SGL_ORDER_BAD_ADDRESS;
        offset = sgl_order_physical(order[i]) - sgl_order_physical(queue->sprite_address);
        slot = offset / sizeof(sgl_order_command);
        current_bank = offset / (queue->sprite_bytes / 2);
        if (bank != 2 && bank != current_bank) return SGL_ORDER_BAD_MEMBERSHIP;
        bank = current_bank;
        bit = (unsigned char)(1u << (slot & 7u));
        if (seen[slot >> 3] & bit) return SGL_ORDER_BAD_MEMBERSHIP;
        seen[slot >> 3] |= bit;
    }
    for (i = 0; i < 128; ++i) {
        uint32_t address = queue->heads[window * 128 + i];
        while (address) {
            volatile sgl_order_command *command = sgl_order_resolve(queue, address);
            unsigned int slot;
            unsigned char bit;
            if (!command) return SGL_ORDER_BAD_ADDRESS;
            if ((command->key >> 8) != i) return SGL_ORDER_BAD_KEY;
            if (old_count++ >= count) return SGL_ORDER_BAD_MEMBERSHIP;
            slot = (sgl_order_physical(address) - sgl_order_physical(queue->sprite_address)) /
                   sizeof(sgl_order_command);
            bit = (unsigned char)(1u << (slot & 7u));
            if (!(seen[slot >> 3] & bit)) return SGL_ORDER_BAD_MEMBERSHIP;
            seen[slot >> 3] &= (unsigned char)~bit;
            address = command->next;
        }
    }
    if (old_count != count) return SGL_ORDER_BAD_MEMBERSHIP;
    for (i = 0; i < 128; ++i) queue->heads[window * 128 + i] = 0;
    for (i = 0; i < count; ++i) {
        volatile sgl_order_command *command = sgl_order_resolve(queue, order[i]);
        unsigned int key = count - i;
        unsigned int head_index = window * 128 + (key >> 8);
        command->key = (uint16_t)key;
        command->next = queue->heads[head_index];
        queue->heads[head_index] = order[i];
    }
    return SGL_ORDER_OK;
}

#endif
