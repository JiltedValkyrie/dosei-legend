/*
 * oot-core blob: decomp code linked to run from a fixed RAM-cart carve.
 * The entry table comes first so the game finds it at the load address.
 * .bss is not in the binary: the loader zeroes the whole carve first.
 * Symbols carry SH-ELF's leading underscore (C oot_core_end = _oot_core_end).
 */
OUTPUT_ARCH(sh)
ENTRY(_oot_core_entry)
/* Fake VROM bases for ROM segments z_message/z_kanfont DMA from
 * (bridge_message.cpp DmaMgr_RequestSync maps them; text comes from the
 * host carve, the rest reads nothing). One 16 MB span each. */
__nes_message_data_staticSegmentRomStart = 0x10000000;
__jpn_message_data_staticSegmentRomStart = 0x11000000;
__staff_message_data_staticSegmentRomStart = 0x12000000;
__message_staticSegmentRomStart = 0x13000000;
__message_texture_staticSegmentRomStart = 0x14000000;
__nes_font_staticSegmentRomStart = 0x15000000;
__kanjiSegmentRomStart = 0x16000000;
__icon_item_staticSegmentRomStart = 0x17000000;
__icon_item_24_staticSegmentRomStart = 0x18000000;
/* Segment (VRAM) starts: message table entries are segment addresses. */
__nes_message_data_staticSegmentStart = 0x07000000;
__jpn_message_data_staticSegmentStart = 0x08000000;
SECTIONS
{
    . = OOT_CORE_LOAD_ADDR;
    .oot_entry : { KEEP(*(.oot_entry)) }
    .text : { _oot_core_text_start = .; *(.text .text.*) _oot_core_text_end = .; }
    .rodata : { *(.rodata .rodata.*) }
    .data : {
        *(.data .data.*)
        . = ALIGN(4);
        _oot_core_ctors_start = .;
        KEEP(*(SORT(.init_array.*))) KEEP(*(.init_array)) KEEP(*(.ctors))
        _oot_core_ctors_end = .;
    }
    .keep_ph : {
        _oot_keep_ph_start = .;
        KEEP(*(.keep_ph))
        _oot_keep_ph_end = .;
    }
    .bss : { *(.bss .bss.*) *(COMMON) }
    _oot_core_end = .;
    ASSERT(_oot_core_end <= OOT_CORE_LOAD_ADDR + OOT_CORE_MAX_BYTES, "oot-core blob exceeds its cart carve")
    /DISCARD/ : { *(.comment) *(.dtors) *(.fini_array) *(.eh_frame) }
}
