#ifndef DOSEI_RAM_LOW_H
#define DOSEI_RAM_LOW_H
/*
** Fixed carves in the 1 MB Low Work RAM (0x00200000..0x002FFFFF).
**
** Nothing else in this build touches it: jo_malloc zones are the work-RAM
** arena and the expansion cart (core.c), SGL's work area is high work RAM,
** GFS and backup use the reserved ranges below. It is SH-2 bus DRAM: slower
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
/* Shared child/adult Link pose and alternate skin metadata. The age switch
 * overwrites these only between scenes; both are filled before use. */
#define RAM_LOW_LINK_POINTS_OFFSET  0x17800u
#define RAM_LOW_LINK_POINTS_BYTES   0x1400u
/* Link's 21 joint matrices: rebuilt by pose_skeleton, cleared on reset.
 * Use existing pose carve slack; keep the alternate skin's address fixed. */
#define RAM_LOW_LINK_MATRICES_OFFSET 0x18C00u
#define RAM_LOW_LINK_MATRICES_BYTES  0x0400u
/* Shared 24-row actor-view query scratch; each query fills returned rows. */
#define RAM_LOW_CORE_VIEW_OFFSET     0x19000u
#define RAM_LOW_CORE_VIEW_BYTES      0x0200u
#define RAM_LOW_LINK_SKIN_OFFSET    0x19800u
#define RAM_LOW_LINK_SKIN_BYTES     0x2000u
/* Adult hero gear pose points (kokiri_sgl.c gear_draw), filled each draw
** before submission; in the free span between LINK_SKIN and SAVE. */
#define RAM_LOW_LINK_GEAR_POINTS_OFFSET 0x1B800u
#define RAM_LOW_LINK_GEAR_POINTS_BYTES  0x2000u
/* MUSICTRG.BIN is ~90 KB (2026-10-02); the carve shrank to grow the CD directory. */
#define RAM_LOW_MUSICTRG_OFFSET     0x59500u
#define RAM_LOW_MUSICTRG_BYTES      0x18000u
/* Persistent save state uses the start of the retired directory carve.
 * Explicitly initialized before boot scene setup; never assumes zeroed RAM. */
#define RAM_LOW_SAVE_OFFSET         0x27800u
#define RAM_LOW_SAVE_BYTES          0x1000u
/* Separate synchronous save-write and summary decode workspaces. Neither
 * buffer belongs on SGL's 1 KiB master stack; live save data stays separate. */
#define RAM_LOW_SAVE_IO_OFFSET       0x28800u
#define RAM_LOW_SAVE_IO_BYTES        0x1000u
#define RAM_LOW_SAVE_SUMMARY_OFFSET  0x29800u
#define RAM_LOW_SAVE_SUMMARY_BYTES   0x1000u
/* oot-core draw-cache ownership; explicitly cleared once before core boot. */
#define RAM_LOW_OOTDRAW_OFFSET       0x2A800u
#define RAM_LOW_OOTDRAW_BYTES        0x1000u
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
#define RAM_LOW_GAME_END            0xF1500u
#else
#define RAM_LOW_GAME_END            0x71500u
#endif

/* BIOS backup executable and STN-52 workspace: never placed in expansion RAM. */
#define RAM_LOW_BACKUP_LIB_OFFSET   0xF1600u
#define RAM_LOW_BACKUP_LIB_BYTES    0x4000u
#define RAM_LOW_BACKUP_WORK_OFFSET  0xF5600u
#define RAM_LOW_BACKUP_WORK_BYTES   8312u
/* 8 KB of jo_malloc moved out of high work RAM (makefile 48128 -> 39936):
** a heap zone after the backup workspace. Zeroed by jo_add_memory_zone. */
#define RAM_LOW_HEAP_OFFSET         0xF8000u
#define RAM_LOW_HEAP_BYTES          0x2000u
#define RAM_LOW_USED_BYTES          (RAM_LOW_HEAP_OFFSET + RAM_LOW_HEAP_BYTES)
typedef char ram_low_heap_after_backup[RAM_LOW_BACKUP_WORK_OFFSET + RAM_LOW_BACKUP_WORK_BYTES
                                       <= RAM_LOW_HEAP_OFFSET ? 1 : -1];
typedef char ram_low_backup_fits[RAM_LOW_GAME_END <= RAM_LOW_BACKUP_LIB_OFFSET &&
    RAM_LOW_BACKUP_LIB_OFFSET + RAM_LOW_BACKUP_LIB_BYTES <= RAM_LOW_BACKUP_WORK_OFFSET ? 1 : -1];

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
                             <= RAM_LOW_LINK_POINTS_OFFSET &&
                             RAM_LOW_LINK_POINTS_OFFSET + RAM_LOW_LINK_POINTS_BYTES
                             <= RAM_LOW_LINK_MATRICES_OFFSET &&
                             RAM_LOW_LINK_MATRICES_OFFSET + RAM_LOW_LINK_MATRICES_BYTES
                             <= RAM_LOW_CORE_VIEW_OFFSET &&
                             RAM_LOW_CORE_VIEW_OFFSET + RAM_LOW_CORE_VIEW_BYTES
                             <= RAM_LOW_LINK_SKIN_OFFSET &&
                             RAM_LOW_LINK_SKIN_OFFSET + RAM_LOW_LINK_SKIN_BYTES
                             <= RAM_LOW_SAVE_OFFSET &&
                             RAM_LOW_SAVE_OFFSET + RAM_LOW_SAVE_BYTES
                             <= RAM_LOW_SAVE_IO_OFFSET &&
                             RAM_LOW_SAVE_IO_OFFSET + RAM_LOW_SAVE_IO_BYTES
                             <= RAM_LOW_SAVE_SUMMARY_OFFSET &&
                             RAM_LOW_SAVE_SUMMARY_OFFSET + RAM_LOW_SAVE_SUMMARY_BYTES
                             <= RAM_LOW_OOTDRAW_OFFSET &&
                             RAM_LOW_OOTDRAW_OFFSET + RAM_LOW_OOTDRAW_BYTES
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
typedef char ram_low_gear_points_fit[RAM_LOW_LINK_SKIN_OFFSET + RAM_LOW_LINK_SKIN_BYTES <=
    RAM_LOW_LINK_GEAR_POINTS_OFFSET && RAM_LOW_LINK_GEAR_POINTS_OFFSET +
    RAM_LOW_LINK_GEAR_POINTS_BYTES <= RAM_LOW_SAVE_OFFSET ? 1 : -1];
#endif
