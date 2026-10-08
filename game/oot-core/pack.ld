/* Two-pass fixed top-of-scene-carve link. No runtime relocations. */
OUTPUT_ARCH(sh)
ENTRY(_pack_text)
SECTIONS
{
    . = OOT_PACK_BASE;
    .pack_header : {
        LONG(0x4f415031) LONG(1) LONG(80) LONG(OOT_PACK_CORE_CRC)
        LONG(OOT_PACK_BASE) LONG(_pack_file_end - OOT_PACK_BASE)
        LONG(ALIGN(_pack_memory_end - OOT_PACK_BASE, 16))
        LONG(_pack_file_end - OOT_PACK_BASE) LONG(_pack_memory_end - _pack_file_end)
        LONG(_pack_ctors - OOT_PACK_BASE) LONG((_pack_ctors_end - _pack_ctors) / 4)
        LONG(_pack_actors - OOT_PACK_BASE) LONG((_pack_actors_end - _pack_actors) / 8)
        LONG(_pack_effects - OOT_PACK_BASE) LONG((_pack_effects_end - _pack_effects) / 8)
        LONG(0) LONG(_pack_text - OOT_PACK_BASE) LONG(_pack_text_end - _pack_text)
        LONG(OOT_PACK_SCENE) LONG(OOT_PACK_FLAGS)
    }
    .text : { _pack_text = .; *(.text .text.*) _pack_text_end = .; }
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
    ASSERT(SIZEOF(.pack_header) == 80, "actor pack header ABI mismatch")
    /DISCARD/ : { *(.comment) *(.dtors) *(.fini_array*) *(.eh_frame*) }
}
