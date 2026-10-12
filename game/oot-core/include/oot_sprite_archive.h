/* Pure SPR1/SPR2 parsing, shared by the core loader and non-core C fallback.
 * All accesses are byte based; validate complete input before using a view. */
#ifndef OOT_SPRITE_ARCHIVE_H
#define OOT_SPRITE_ARCHIVE_H

static unsigned int OotSprite_U16(const unsigned char* s, unsigned int at) {
    return (unsigned int)s[at] * 256u + s[at + 1];
}
static unsigned int OotSprite_U32(const unsigned char* s, unsigned int at) {
    return OotSprite_U16(s, at) << 16 | OotSprite_U16(s, at + 2);
}
static int OotSprite_Valid(const unsigned char* s, unsigned int length) {
    unsigned int w, h, poses, ticks, base, i;
    if (!s || length < 52 || s[0]!='S' || s[1]!='P' || s[2]!='R' || s[3]!='1') return 0;
    w=OotSprite_U16(s,4); h=OotSprite_U16(s,6);
    poses=OotSprite_U16(s,10); ticks=OotSprite_U16(s,12);
    if (!w || w>256 || (w&7) || !h || h>255 || !poses || poses>256 ||
        !ticks || OotSprite_U16(s,8)!=5 || !OotSprite_U16(s,16)) return 0;
    base=52+((ticks*2+3)&~3u);
    if (base+w*h/2*poses*5!=length) return 0;
    for (i=0;i<ticks;++i) if (OotSprite_U16(s,52+i*2)>=poses) return 0;
    return 1;
}
static int OotSprite_ArchiveValid(const unsigned char* s, unsigned int bytes, unsigned int skeleton) {
    unsigned int count, end, i, j;
    if (!s || bytes<16 || bytes>0x800000u ||
        s[0]!='S' || s[1]!='P' || s[2]!='R' || s[3]!='2' ||
        OotSprite_U16(s,4)!=2 || OotSprite_U32(s,8)!=skeleton || OotSprite_U32(s,12)!=bytes) return 0;
    count=OotSprite_U16(s,6);
    if (!count || count>256 || count>(bytes-16)/12) return 0;
    end=16+count*12;
    for (i=0;i<count;++i) {
        unsigned int at=16+i*12, off=OotSprite_U32(s,at+4), len=OotSprite_U32(s,at+8);
        if (OotSprite_U32(s,at)>0xffffffu || off<end || off-end>12u || (off&3) || (len&3) ||
            off>bytes || len>bytes-off || !OotSprite_Valid(s+off,len)) return 0;
        /* Legacy clips are contiguous. New archives add only the zero gap
         * needed to align the unchanged SPR1 pixel payload for burst DMA. */
        if (off!=end) {
            unsigned int base=52+((OotSprite_U16(s+off,12)*2+3)&~3u);
            if ((off+base)&15u) return 0;
            for (j=end;j<off;++j) if (s[j]) return 0;
        }
        for (j=0;j<i;++j) if (OotSprite_U32(s,16+j*12)==OotSprite_U32(s,at)) return 0;
        end=off+len;
    }
    return end==bytes;
}
/* UINT_MAX selects the largest cel, otherwise animation is a linked key. */
static const unsigned char* OotSprite_Clip(const unsigned char* s, unsigned int animation) {
    unsigned int i, best=0;
    const unsigned char* result=0;
    if (!s) return 0;
    for (i=0;i<OotSprite_U16(s,6);++i) {
        const unsigned char* clip=s+OotSprite_U32(s,20+i*12);
        if (animation!=~0u) {
            if (OotSprite_U32(s,16+i*12)==(animation&0xffffffu)) return clip;
        } else {
            unsigned int bytes=OotSprite_U16(clip,4)*OotSprite_U16(clip,6);
            if (bytes>best) { best=bytes; result=clip; }
        }
    }
    return result;
}
#endif
