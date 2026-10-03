/*
 * Decomp object data blob (O<id>.OOB): skeletons, limbs, animations cut from
 * the extracted object .c (tools/oot_core_import.py OBJECTS), linked at
 * segment 6 like the N64 objects. The host loads it anywhere and the blob's
 * objectCtx slot holds that address; SEGMENTED_TO_VIRTUAL with gSegments[6]
 * finds the data. Data only.
 */
OUTPUT_ARCH(sh)
SECTIONS
{
    . = 0x06000000;
    .data : { *(.rodata .rodata.* .data .data.*) *(.bss .bss.*) *(COMMON) }
    _oot_object_end = .;
    ASSERT(_oot_object_end <= 0x06000000 + OOT_OBJECT_MAX_BYTES, "object blob exceeds its limit")
    /DISCARD/ : { *(.comment) *(.text .text.*) }
}
