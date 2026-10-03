#ifndef DOSEI_RAM_LOW_H
#define DOSEI_RAM_LOW_H
/*
** Fixed carves in the 1 MB Low Work RAM (0x00200000..0x002FFFFF).
**
** Nothing else in this build touches it: jo_malloc zones are the work-RAM
** arena and the expansion cart (core.c), SGL's work area is high work RAM,
** GFS/backup take jo_malloc or static buffers. It is SH-2 bus DRAM: slower
** than high work RAM, much faster than the A-bus cart, and it is NOT
** zero-filled at boot like .bss, so users initialise what they read.
** Moved here to free high work RAM below the SGL area (BUG-043).
*/
#define RAM_LOW_ADDRESS             0x00200000u
#define RAM_LOW_BYTES               0x00100000u

/* Link's equipped POLYGON + ATTR copy (kokiri_sgl.c), rebuilt on change. */
#define RAM_LOW_EQUIP_POLY_OFFSET   0x0000u
#define RAM_LOW_EQUIP_POLY_BYTES    0x3000u
#define RAM_LOW_EQUIP_ATTR_OFFSET   0x3000u
#define RAM_LOW_EQUIP_ATTR_BYTES    0x2000u
/* Renderer scratch; each used entry is filled on bank load or before prep.
 * Keep the heap, polygon budget and sprite limit unchanged. */
#define RAM_LOW_FOREST_DEPTH_OFFSET 0x5000u
#define RAM_LOW_FOREST_DEPTH_BYTES  0x2000u
#define RAM_LOW_TILE_DEPTH_OFFSET   0x7000u
#define RAM_LOW_TILE_DEPTH_BYTES    0x1000u
#define RAM_LOW_TILE_FOG_OFFSET     0x8000u
#define RAM_LOW_TILE_FOG_BYTES      0x0800u
#define RAM_LOW_FOREST_MESH_OFFSET  0x8800u
#define RAM_LOW_FOREST_MESH_BYTES   0x1000u
/* Streamed room metadata. Every used byte is filled by room_load_bank before
 * drawing; no boot-zero assumption. Separate from depth/material scratch. */
#define RAM_LOW_ROOM_OBJECTS_OFFSET 0x9800u
#define RAM_LOW_ROOM_OBJECTS_BYTES  0x1000u
#define RAM_LOW_ROOM_BOUNDS_OFFSET  0xA800u
#define RAM_LOW_ROOM_BOUNDS_BYTES   0x1000u
#define RAM_LOW_SPRITES_OFFSET      0xB800u
#define RAM_LOW_SPRITES_BYTES       0xC000u
/* MUSICTRG.BIN is ~90 KB (2026-10-02); the carve shrank to grow the CD directory. */
#define RAM_LOW_MUSICTRG_OFFSET     0x59500u
#define RAM_LOW_MUSICTRG_BYTES      0x18000u
/* Old 0x27800..0x2B800 directory carve is reserved, now unused. */
#define RAM_LOW_FS_DIRECTORY_OFFSET 0x49500u
#define RAM_LOW_FS_DIRECTORY_BYTES  0x10000u
#define RAM_LOW_GOMA_OFFSET         0x2B800u
#define RAM_LOW_GOMA_BYTES          0x1000u
#define RAM_LOW_QUADS_OFFSET        0x2C800u
#define RAM_LOW_QUADS_BYTES         0x2800u
#define RAM_LOW_GOHMA_POSES_OFFSET  0x2F000u
#define RAM_LOW_GOHMA_POSES_BYTES   0xB000u
#define RAM_LOW_GOHMA_OFFSET        0x3A000u
#define RAM_LOW_GOHMA_BYTES         0x2000u
/* Immutable fog channel lookup, fully filled before any scene draw. */
#define RAM_LOW_FOG_CHANNEL_OFFSET  0x3C000u
#define RAM_LOW_FOG_CHANNEL_BYTES   0x0500u
#define RAM_LOW_CORE_OFFSET         0x3C500u
#define RAM_LOW_CORE_BYTES          0xD000u
#ifdef DOSEI_OOT_CORE
/* oot-core play block (oot_core_host.c): PlayState + TwoHeadArena + ZeldaArena,
** OotCoreEntry.play_bytes() must fit (checked at boot). Faster than the cart. */
#define RAM_LOW_OOTPLAY_OFFSET      0x71500u
#define RAM_LOW_OOTPLAY_BYTES       0x80000u   /* play_bytes() 0x7F440 measured on target 2026-10-03 */
#define RAM_LOW_USED_BYTES          0xF1500u
#else
#define RAM_LOW_USED_BYTES          0x71500u
#endif

#define RAM_LOW(offset)             ((void *)(RAM_LOW_ADDRESS + (offset)))

typedef char ram_low_fits[RAM_LOW_USED_BYTES <= RAM_LOW_BYTES ? 1 : -1];
typedef char ram_low_ordered[RAM_LOW_EQUIP_POLY_OFFSET + RAM_LOW_EQUIP_POLY_BYTES
                             <= RAM_LOW_EQUIP_ATTR_OFFSET &&
                             RAM_LOW_EQUIP_ATTR_OFFSET + RAM_LOW_EQUIP_ATTR_BYTES
                             <= RAM_LOW_FOREST_DEPTH_OFFSET &&
                             RAM_LOW_FOREST_DEPTH_OFFSET + RAM_LOW_FOREST_DEPTH_BYTES
                             <= RAM_LOW_TILE_DEPTH_OFFSET &&
                             RAM_LOW_TILE_DEPTH_OFFSET + RAM_LOW_TILE_DEPTH_BYTES
                             <= RAM_LOW_TILE_FOG_OFFSET &&
                             RAM_LOW_TILE_FOG_OFFSET + RAM_LOW_TILE_FOG_BYTES
                             <= RAM_LOW_FOREST_MESH_OFFSET &&
                             RAM_LOW_FOREST_MESH_OFFSET + RAM_LOW_FOREST_MESH_BYTES
                             <= RAM_LOW_ROOM_OBJECTS_OFFSET &&
                             RAM_LOW_ROOM_OBJECTS_OFFSET + RAM_LOW_ROOM_OBJECTS_BYTES
                             <= RAM_LOW_ROOM_BOUNDS_OFFSET &&
                             RAM_LOW_ROOM_BOUNDS_OFFSET + RAM_LOW_ROOM_BOUNDS_BYTES
                             <= RAM_LOW_SPRITES_OFFSET &&
                             RAM_LOW_SPRITES_OFFSET + RAM_LOW_SPRITES_BYTES
                             <= RAM_LOW_GOMA_OFFSET &&
                             RAM_LOW_GOMA_OFFSET + RAM_LOW_GOMA_BYTES
                             <= RAM_LOW_QUADS_OFFSET &&
                             RAM_LOW_QUADS_OFFSET + RAM_LOW_QUADS_BYTES
                             <= RAM_LOW_GOHMA_POSES_OFFSET &&
                             RAM_LOW_GOHMA_POSES_OFFSET + RAM_LOW_GOHMA_POSES_BYTES
                             <= RAM_LOW_GOHMA_OFFSET &&
                             RAM_LOW_GOHMA_OFFSET + RAM_LOW_GOHMA_BYTES
                             <= RAM_LOW_FOG_CHANNEL_OFFSET &&
                             RAM_LOW_FOG_CHANNEL_OFFSET + RAM_LOW_FOG_CHANNEL_BYTES
                             <= RAM_LOW_CORE_OFFSET &&
                             RAM_LOW_CORE_OFFSET + RAM_LOW_CORE_BYTES
                             <= RAM_LOW_FS_DIRECTORY_OFFSET &&
                             RAM_LOW_FS_DIRECTORY_OFFSET + RAM_LOW_FS_DIRECTORY_BYTES
                             <= RAM_LOW_MUSICTRG_OFFSET &&
                             RAM_LOW_MUSICTRG_OFFSET + RAM_LOW_MUSICTRG_BYTES
                             <= RAM_LOW_USED_BYTES ? 1 : -1];
#endif
