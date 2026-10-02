/*
 * Scene collision data blob: decomp CollisionHeader + its arrays, linked at
 * the cached cart alias of RAM_CART_SCENECOL (makefile OOT_SCENECOL_ADDR).
 * The header comes first so the blob's load address is the header pointer.
 * Data only: anything needing code or relocations fails the link.
 */
OUTPUT_ARCH(sh)
ENTRY(_oot_scene_col)
SECTIONS
{
    . = OOT_SCENECOL_ADDR;
    .col_header : { KEEP(*(.col_header)) }
    .data : { *(.rodata .rodata.* .data .data.*) }
    _oot_scene_col_end = .;
    ASSERT(SIZEOF(.col_header) > 0, "scene collision blob has no header")
    ASSERT(_oot_scene_col_end <= OOT_SCENECOL_ADDR + OOT_SCENECOL_MAX_BYTES, "scene collision exceeds its cart carve")
    /DISCARD/ : { *(.comment) *(.text .text.*) *(.bss .bss.*) *(COMMON) }
}
