/*
 * oot-core blob: decomp code linked to run from a fixed RAM-cart carve.
 * The entry table comes first so the game finds it at the load address.
 * .bss is not in the binary: the loader zeroes the whole carve first.
 * Symbols carry SH-ELF's leading underscore (C oot_core_end = _oot_core_end).
 */
OUTPUT_ARCH(sh)
ENTRY(_oot_core_entry)
SECTIONS
{
    . = OOT_CORE_LOAD_ADDR;
    .oot_entry : { KEEP(*(.oot_entry)) KEEP(*(.oot_entry.roots)) }
    .text : { *(.text .text.*) }
    .rodata : { *(.rodata .rodata.*) }
    .data : {
        *(.data .data.*)
        . = ALIGN(4);
        _oot_core_ctors_start = .;
        KEEP(*(SORT(.init_array.*))) KEEP(*(.init_array)) KEEP(*(.ctors))
        _oot_core_ctors_end = .;
    }
    .bss : { *(.bss .bss.*) *(COMMON) }
    _oot_core_end = .;
    ASSERT(_oot_core_end <= OOT_CORE_LOAD_ADDR + OOT_CORE_MAX_BYTES, "oot-core blob exceeds its cart carve")
    /DISCARD/ : { *(.comment) *(.dtors) *(.fini_array) *(.eh_frame) }
}
