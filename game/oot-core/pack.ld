/* Two-pass fixed top-of-scene-carve link. No runtime relocations. */
OUTPUT_ARCH(sh)
ENTRY(_pack_text)
SECTIONS
{
    . = OOT_PACK_BASE;
    .pack_header : {
        LONG(0x4f415031) LONG(2) LONG(96) LONG(OOT_PACK_CORE_CRC)
        LONG(OOT_PACK_BASE) LONG(_pack_file_end - OOT_PACK_BASE)
        LONG(ALIGN(_pack_memory_end - OOT_PACK_BASE, 16))
        LONG(_pack_file_end - OOT_PACK_BASE) LONG(_pack_memory_end - _pack_file_end)
        LONG(_pack_ctors - OOT_PACK_BASE) LONG((_pack_ctors_end - _pack_ctors) / 4)
        LONG(_pack_actors - OOT_PACK_BASE) LONG((_pack_actors_end - _pack_actors) / 8)
        LONG(_pack_effects - OOT_PACK_BASE) LONG((_pack_effects_end - _pack_effects) / 8)
        LONG(0) LONG(_pack_text - OOT_PACK_BASE) LONG(_pack_text_end - _pack_text)
        LONG(OOT_PACK_SCENE) LONG(OOT_PACK_FLAGS)
        LONG((DEFINED(_oot_pack_onepoint_setup) || DEFINED(_oot_pack_npc_view)) ? 2 : 0)
        LONG(DEFINED(_oot_pack_onepoint_setup) ? _oot_pack_onepoint_setup : 0)
        LONG(DEFINED(_oot_pack_onepoint_step) ? _oot_pack_onepoint_step : 0)
        LONG(DEFINED(_oot_pack_npc_view) ? _oot_pack_npc_view : 0)
    }
    /* Segment-1 billboard (source D_01000000). The Saturn core keeps
     * play->billboardMtxF identity (z_actor init); alias the same matrix. */
    PROVIDE(_D_01000000 = _gIdentityMtx);
    /* Source D_06000000: segment-6 base; SEGMENTED_TO_VIRTUAL maps it. */
    PROVIDE(_D_06000000 = 0x06000000);
    .text : { _pack_text = .; KEEP(*(.text.oot_pack_onepoint_setup .text.oot_pack_onepoint_step .text.oot_pack_npc_view)) *(.text .text.*) _pack_text_end = .; }
    .rodata : { *(.rodata .rodata.*) }
    .data : { *(.data .data.*) }
    .pack_tables ALIGN(4) : {
        _pack_ctors = .; KEEP(*(SORT(.init_array.*))) KEEP(*(.init_array)) KEEP(*(.ctors))
        _pack_ctors_end = .;
        _pack_actors = .; KEEP(*(.pack_actors)) _pack_actors_end = .;
        _pack_effects = .; KEEP(*(.pack_effects)) _pack_effects_end = .;
        . = ALIGN(4); _pack_file_end = .;
    }
    .bss (NOLOAD) : { *(.bss .bss.*) *(COMMON) _pack_memory_end = .; }
    ASSERT(_pack_memory_end <= OOT_PACK_END, "actor pack exceeds scene carve")
    ASSERT(SIZEOF(.pack_header) == 96, "actor pack header ABI mismatch")
    /DISCARD/ : { *(.comment) *(.dtors) *(.fini_array*) *(.eh_frame*) }
}
