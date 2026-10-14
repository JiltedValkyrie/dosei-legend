#ifndef DOSEI_SAVE_FILE_H
#define DOSEI_SAVE_FILE_H
#include <stdbool.h>
#include <stdint.h>
#include "save_state.h"

/*
** Save-file serialisation: save_state_t <-> a flat byte block.
**
** Platform free on purpose. Backup-RAM device calls live in save_device.c; this
** file only turns quest state into bytes and back, so the host tests can prove
** the round trip, the version check and the checksum without a Saturn or a BUP
** cartridge.
**
** Every field is packed EXPLICITLY, big end first, rather than memcpy'ing the
** struct. A struct blit would bake in whatever padding and field order the
** compiler chose, so adding a field could silently change the layout and make
** old saves decode as garbage while still passing their checksum. Explicit
** packing means a layout change has to go through SAVE_FILE_VERSION.
**
** Three slots, like the N64 file select.
*/

#define SAVE_FILE_SLOTS         3

/* 'DLSV' -- refuse anything that is not ours, including leftover data from
** another game in the same backup device. */
#define SAVE_FILE_MAGIC_0       'D'
#define SAVE_FILE_MAGIC_1       'L'
#define SAVE_FILE_MAGIC_2       'S'
#define SAVE_FILE_MAGIC_3       'V'

/* v8 appends visited Deku rooms; v7 added map/compass. Versions 2-7 migrate;
** v6 introduced source collectible flags without changing the v5 layout. */
#define SAVE_FILE_VERSION       14
/* v2 (M2d): v3 appends Deku Stick slot/ammo/upgrade and naviTimer. A v2
** block still loads; the new fields start at their new-file values. */
#define SAVE_FILE_V2_PAYLOAD_BYTES 290

/* magic(4) + version(2) + reserved(2) + payload + checksum(2). */
#define SAVE_FILE_V3_PAYLOAD_BYTES 295
#define SAVE_FILE_V4_PAYLOAD_BYTES 298
/* v5 (M3a) appends Deku Nut owned/ammo/upgrade. */
#define SAVE_FILE_V6_PAYLOAD_BYTES 301
#define SAVE_FILE_V7_PAYLOAD_BYTES 302
#define SAVE_FILE_V8_PAYLOAD_BYTES 304
#define SAVE_FILE_V9_PAYLOAD_BYTES 336
#define SAVE_FILE_V10_PAYLOAD_BYTES 338 /* cosmetic tunic and Fairy Ocarina */
/* v11 appends original-scene flags, dungeon inventory and age/time/cutscene. */
#define SAVE_FILE_V11_PAYLOAD_BYTES (SAVE_FILE_V10_PAYLOAD_BYTES + SAVE_SOURCE_SCENE_COUNT * 16 + SAVE_DUNGEON_ITEMS_COUNT + SAVE_DUNGEON_KEYS_COUNT + 62)
/* v12 appends the equipped boots. */
#define SAVE_FILE_V12_PAYLOAD_BYTES (SAVE_FILE_V11_PAYLOAD_BYTES + 1)
/* v13 appends source totalDays and bgsDayCount. */
#define SAVE_FILE_V13_PAYLOAD_BYTES (SAVE_FILE_V12_PAYLOAD_BYTES + 8)
/* v14 appends the source Skull Kid memory-game reward tier. */
#define SAVE_FILE_PAYLOAD_BYTES (SAVE_FILE_V13_PAYLOAD_BYTES + 1)
#define SAVE_FILE_BYTES         (8 + SAVE_FILE_PAYLOAD_BYTES + 2)

/* Why a load was refused, so the file select can say something true rather
** than silently showing an empty slot. */
typedef enum
{
    SAVE_FILE_OK = 0,
    SAVE_FILE_EMPTY,            /* nothing stored in that slot */
    SAVE_FILE_BAD_MAGIC,        /* not one of ours */
    SAVE_FILE_BAD_VERSION,      /* ours, but a layout we no longer read */
    SAVE_FILE_BAD_CHECKSUM,     /* ours and current, but corrupt */
    SAVE_FILE_BAD_SIZE,
    SAVE_FILE_DEVICE_ERROR      /* read failed; never offer to overwrite as NEW FILE */
}               save_file_status;

/* What the file select needs to draw one slot without loading it. */
typedef struct
{
    bool        present;
    uint8_t     hearts;         /* whole hearts of capacity */
    uint8_t     hearts_full;    /* whole hearts currently filled */
    uint16_t    rupees;
    bool        has_emerald;
    bool        deku_tree_cleared;
    uint8_t     scene_id;
}               save_file_summary;

/* Pack `state` into exactly SAVE_FILE_BYTES at `out`. */
void                save_file_pack(const save_state_t *state, uint8_t *out);

/* Unpack into `state`. On any failure `state` is left untouched and the reason
** is returned, so a rejected load cannot half-overwrite live quest state. */
save_file_status    save_file_unpack(save_state_t *state, const uint8_t *in,
                                     unsigned int bytes);

/* Summary from a stored block, without disturbing the live save. */
save_file_status    save_file_read_summary(save_file_summary *summary,
                                           const uint8_t *in,
                                           unsigned int bytes);

/* The checksum the format uses, exposed for the tests. */
uint16_t            save_file_checksum(const uint8_t *payload,
                                       unsigned int bytes);

/* Human-readable reason, for the file select. Never NULL. */
const char         *save_file_status_text(save_file_status status);

#endif
