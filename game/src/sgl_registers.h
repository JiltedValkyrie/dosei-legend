#ifndef DOSEI_SGL_REGISTERS_H
#define DOSEI_SGL_REGISTERS_H
/* This project's LIBSGL slInitScroll table starts at GBR+192 (0x060ffcc0).
 * VDP2 control registers are write-only; read SGL's intended state instead.
 * Offsets below are hardware register offsets, not absolute addresses.
 * Recheck this layout when changing SGL. Main SH-2 context only. */
static inline volatile unsigned short *sgl_vdp2_shadow(unsigned int offset)
{
    unsigned int base;
    __asm__ volatile ("stc gbr,%0" : "=r" (base));
    return (volatile unsigned short *)(base + 192u + offset);
}
#endif
