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
#define RAM_LOW_MUSICTRG_OFFSET     0x17800u
#define RAM_LOW_MUSICTRG_BYTES      0x10000u
#define RAM_LOW_USED_BYTES          0x27800u

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
                             <= RAM_LOW_MUSICTRG_OFFSET &&
                             RAM_LOW_MUSICTRG_OFFSET + RAM_LOW_MUSICTRG_BYTES
                             <= RAM_LOW_USED_BYTES ? 1 : -1];
#endif
