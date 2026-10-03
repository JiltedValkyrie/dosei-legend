/*
 * Scene data blob: OotSceneBlob (oot_scene_blob.h) + decomp collision + room actor lists, linked at
 * the cached cart alias of RAM_CART_SCENECOL (makefile OOT_SCENECOL_ADDR).
 * OotSceneBlob comes first so the blob load address is its pointer.
 * Data only: anything needing code or relocations fails the link.
 */
OUTPUT_ARCH(sh)
ENTRY(_oot_scene_blob)
SECTIONS
{
    . = OOT_SCENECOL_ADDR;
    .scene_header : { KEEP(*(.scene_header)) }
    /* Zero-filled arrays (empty BgCam lists) land in .bss: keep them as data. */
    .data : { *(.rodata .rodata.* .data .data.*) *(.bss .bss.*) *(COMMON) }
    _oot_scene_col_end = .;
    ASSERT(SIZEOF(.scene_header) > 0, "scene blob has no header")
    ASSERT(_oot_scene_col_end <= OOT_SCENECOL_ADDR + OOT_SCENECOL_MAX_BYTES, "scene collision exceeds its cart carve")
    /DISCARD/ : { *(.comment) *(.text .text.*) }
}
