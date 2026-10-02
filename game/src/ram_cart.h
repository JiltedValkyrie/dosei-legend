#ifndef DOSEI_RAM_CART_H
#define DOSEI_RAM_CART_H
#include <stdbool.h>

/*
** The 4 MB (32 Mbit) RAM expansion cart is a hard requirement, not an optional
** speed-up: the scene, actor and cutscene data for the three areas does not fit
** in the 2 MB of work RAM once SGL's work area and VDP1 staging are subtracted.
**
** Two jobs here:
**
**   1. Refuse to run without the cart, with a message on screen. Silently
**      running with half the memory would fail later as an unexplained
**      allocation failure somewhere far from the cause.
**   2. Claim the SECOND half of the cart. jo_init_memory() in the SDK
**      (joengine/jo_engine/core.c) registers only 0x200000 at 0x22400000 for
**      CART_32MBits and never touches the bank at 0x22600000, so half the cart
**      is invisible to jo_malloc() unless we add it ourselves.
**
** jo_core_init() must have run first: the SDK does its own cart detection and
** A-bus setup there, and this builds on it rather than repeating it.
*/

/* Second 2 MB bank of the 32 Mbit cart, the one the SDK leaves unregistered. */
#define RAM_CART_BANK2_ADDRESS  0x22600000u
#define RAM_CART_BANK2_BYTES    0x200000u

/* The top of bank 2 is kept OUT of jo_malloc for fixed runtime pools (actor
** pool first). A fixed carve keeps these off the 56 KB work-RAM malloc arena,
** which jo_malloc would otherwise fill first. */
#ifdef DOSEI_OOT_CORE
/* oot-core blob (OOTCORE.BIN): decomp code linked at a fixed cart address and
** run from the cart (oot-core/oot-core.ld, makefile OOT_CORE_LOAD_ADDR). It is
** the last carve, so its address is BANK2 end - RAM_CART_OOTCORE_BYTES. */
/* Scene collision blob (<scene>COL.BIN): decomp CollisionHeader + arrays,
** linked at the cached alias OOT_SCENECOL_ADDR (makefile). One scene at a time. */
#define RAM_CART_SCENECOL_OFFSET 0x82400u
#define RAM_CART_SCENECOL_BYTES  0x40000u
#define RAM_CART_OOTCORE_OFFSET 0xC2400u
#define RAM_CART_OOTCORE_BYTES  0x40000u
#define RAM_CART_FIXED_BYTES    0x102400u
#else
#define RAM_CART_FIXED_BYTES    0x82400u
#endif
#define RAM_CART_FIXED_ADDRESS  (RAM_CART_BANK2_ADDRESS + RAM_CART_BANK2_BYTES - RAM_CART_FIXED_BYTES)

/* Fixed carve for the actor pool (actor_sys_bytes() must fit). */
#define RAM_CART_ACTOR_POOL_OFFSET  0u
#define RAM_CART_ACTOR_POOL_BYTES   0x2000u

/* Fixed carve for world copies of actor-owned (DynaPoly) collision:
** 512 triangles x 36 bytes. */
#define RAM_CART_DYNA_OFFSET        0x2000u
#define RAM_CART_DYNA_BYTES         0x4800u

/* Fixed carve for cutscene run text (CUTTEXT.TXT, message.h), in the
** contact colliders' first carve (0x6800..0x8000), outgrown in M2c. */
#define RAM_CART_CUTTEXT_OFFSET     0x6800u
#define RAM_CART_CUTTEXT_BYTES      0x1800u

/* Retained expanded dialogue page, using part of the retired text slot. */
#define RAM_CART_TEXT_LAYOUT_OFFSET 0x8000u
#define RAM_CART_TEXT_LAYOUT_BYTES  0x500u

/* CURSOR.RGB: EnOssan's shop cursor, 4 baked pulse steps x 32x32 RGB555. */
#define RAM_CART_CURSOR_OFFSET      0x8800u
#define RAM_CART_CURSOR_BYTES       0x2000u

/* Expanded coloured cutscene page; disjoint from dialogue and cursor pools. */
#define RAM_CART_MESSAGE_LAYOUT_OFFSET 0xA800u
#define RAM_CART_MESSAGE_LAYOUT_BYTES  0x800u

/* Fixed carve for the sword/grass/nut contact colliders (gameplay_contacts_*).
** Moved here when M2c's three blade capsules and the nutsball outgrew 0x1800. */
#define RAM_CART_CONTACT_OFFSET     0xB000u
#define RAM_CART_CONTACT_BYTES      0x2000u

/* Fixed carve for MINIMAP.BIN (minimap.h): map cells and marker frames. */
#define RAM_CART_MINIMAP_OFFSET     0xD000u
#define RAM_CART_MINIMAP_BYTES      0x1000u

/* Fixed carve for FAIRY.BIN (kokiri_sgl.c): posed En_Elf wing quads. */
#define RAM_CART_FAIRY_OFFSET       0xE000u
#define RAM_CART_FAIRY_BYTES        0x1000u

/* Fixed carve for LINKMESH.BIN (link_scene.h): Link's POLYGON + ATTR
** tables, 791 x 32 B (body + gear + first-person arm), read only on
** equipment change (BUG-039). Moved to the tail 2026-10-01: the arm grew the
** file to 25,312 B and the old 0x4800 carve at 0xF000 let it overwrite Navi's
** glow, the mesh LOD rows and DEKUBABA (Link's ATTR table corrupted).
** 0xF000-0x13800 is now unused.
** 2026-10-02: first-person arm dropped -> Link 704 polygons (22,528 B). */
#define RAM_CART_LINKMESH_OFFSET    0x7C000u
#define RAM_CART_LINKMESH_BYTES     0x6400u

/* Fixed carve for Navi's glow pixels: 3 colours x 3 breath steps x 512 B
** (FAIRY*.RGB). One VRAM slot is refilled from here (kokiri_sgl.c): room
** banks leave no VRAM for nine resident glows. */
#define RAM_CART_NAVIGLOW_OFFSET    0x13800u
#define RAM_CART_NAVIGLOW_BYTES     0x1200u

/* Per-mesh LOD rows from the room bank (KRM1 header[6]): 16 B each, max 96.
** Uses the free gap between Navi's glow (ends 0x14A00) and DEKUBABA. */
#define RAM_CART_MESH_LOD_OFFSET    0x14A00u
#define RAM_CART_MESH_LOD_BYTES     0x600u

/* Fixed carve for DEKUBABA.BIN (karebaba_draw.c) plus its POLYGON/ATTR
** tables: 14.9 KB file + 145 faces x 32 B. */
#define RAM_CART_DEKUBABA_OFFSET    0x15000u
#define RAM_CART_DEKUBABA_BYTES     0x5000u

/* Fixed carve for karebaba.c state (8 x karebaba_t with its colliders). */
#define RAM_CART_KAREBABA_OFFSET    0x1A000u
#define RAM_CART_KAREBABA_BYTES     0x1000u

/* Fixed carve for LINKTEX.BIN: Link's tile descriptors + CLUTs, load only. */
#define RAM_CART_LINKTEX_OFFSET     0x1B000u
#define RAM_CART_LINKTEX_BYTES      0x2000u

/* Fixed carve for dialogue line text (DIALOG.TXT, dialogue_text.h). Moved
** from 0x8000 (0x3000, 704 B left) to the end of the carve for M3 NPC text;
** 0x8000..0xAFFF is now unused. Boot reads it through a temporary heap
** buffer of the file's size, so keep it well below the 51,200 B arena. */
#define RAM_CART_DIALOGUE_OFFSET    0x71000u
#define RAM_CART_DIALOGUE_BYTES     0x6000u

#define RAM_CART_PAUSE_OFFSET 0x1D000u
#define RAM_CART_PAUSE_BYTES  0x26000u
/* RGB page + font, and exact backup of HUD VRAM and the spare bitmap rows
 * temporarily borrowed for pause. Original font and scene bitmap stay live. */
#define RAM_CART_PAUSE_BACKUP_OFFSET 0x43000u
#define RAM_CART_PAUSE_BACKUP_BYTES  0x29880u
#define RAM_CART_SKULL_OFFSET       0x6C900u
#define RAM_CART_SKULL_BYTES        0x900u
#define RAM_CART_WALL_SKULL_OFFSET  0x6D200u
#define RAM_CART_WALL_SKULL_BYTES   0x600u
#define RAM_CART_DEKU_BABA_OFFSET   0x6D800u
#define RAM_CART_DEKU_BABA_BYTES    0x1000u
#define RAM_CART_HINTNUTS_OFFSET    0x6E800u
#define RAM_CART_HINTNUTS_BYTES     0x1000u

/* Cold constant tables moved out of work RAM (BUG-043), from disc at boot:
** title camera paths (TITLEPTH.BIN). MUSICTRG now uses RAM_LOW_MUSICTRG;
** retain its old cart gap so later fixed carves keep their addresses. */
#define RAM_CART_MUSICTRG_OFFSET    0x77000u
#define RAM_CART_MUSICTRG_BYTES     0x5000u
#define RAM_CART_TITLEPTH_OFFSET    0x6F800u
#define RAM_CART_TITLEPTH_BYTES     0x1800u

/* Pointer into the fixed carve, or 0 when no cart / out of range. */
void   *ram_cart_fixed(unsigned int offset, unsigned int bytes);

/* True when a 32 Mbit cart is present. Cheap; reads the cart id byte. */
bool    ram_cart_present(void);

/* Register the second bank with jo_malloc(). Returns false when no 32 Mbit cart
** is fitted, in which case nothing was added and the caller must not continue.
** Safe to call once only; calling twice would double-register the bank. */
bool    ram_cart_claim_second_bank(void);

/* Bytes of cart RAM this build expects to be usable, for diagnostics. */
unsigned int    ram_cart_total_bytes(void);

#endif
