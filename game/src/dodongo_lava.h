#ifndef DODONGO_LAVA_H
#define DODONGO_LAVA_H

/* Room ATTR.gstb carries this source-material tag only until bank upload.
 * The original byte length is dead afterwards. Its spare high bits retain
 * the lava tag and last cooling step without another resident allocation. */
#define DODONGO_LAVA_ATTR 0xDD01u
#define DODONGO_LAVA_TILE 0x80000000u
#define DODONGO_LAVA_LENGTH 0x0000FFFFu

/* Palette cooling is deliberately eight cheap stages. Quantizing the source
 * phase prevents one-bit RGB rounding from swallowing every small step.
 * The endpoint is neutral stone; source owns the timing and room clear flag. */
static inline unsigned dodongo_lava_cool(unsigned short colours[16],
                                         unsigned *tile_length, unsigned phase)
{
    unsigned old, i, step, remaining;
    if (!(*tile_length & DODONGO_LAVA_TILE)) return 0;
    if (phase > 256u) phase = 256u;
    phase &= ~31u;
    old = (*tile_length >> 16) & 0x1FFu;
    if (phase <= old) return 0;
    step = phase - old;
    remaining = 256u - old;
    for (i = 0; i < 16; ++i) {
        unsigned colour = colours[i];
        int r, g, b, grey;
        if (!colour) continue;
        r = colour & 31; g = (colour >> 5) & 31; b = (colour >> 10) & 31;
        grey = (r + g + b) / 3;
        r += (grey - r) * (int)step / (int)remaining;
        g += (grey - g) * (int)step / (int)remaining;
        b += (grey - b) * (int)step / (int)remaining;
        colours[i] = (unsigned short)(0x8000 | r | (g << 5) | (b << 10));
    }
    *tile_length = DODONGO_LAVA_TILE | (phase << 16) |
                   (*tile_length & DODONGO_LAVA_LENGTH);
    return 1;
}
#endif
