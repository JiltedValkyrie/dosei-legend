#include <assert.h>
#include <stdio.h>
#include <string.h>
#include "../../src/dodongo_lava.h"

int main(void)
{
    unsigned short original[16] = {0, 0x801f, 0x83ff, 0xfc00, 0xa94a};
    unsigned short colours[16], other[16];
    unsigned length = DODONGO_LAVA_TILE | 768, unmarked = 768;
    unsigned phase, i;
    memcpy(colours, original, sizeof colours);
    memcpy(other, original, sizeof other);
    assert(!dodongo_lava_cool(other, &unmarked, 256));
    assert(!memcmp(other, original, sizeof other));
    assert(!dodongo_lava_cool(colours, &length, 31));
    for (phase = 32; phase <= 256; phase += 32) {
        unsigned short snapshot[16];
        assert(dodongo_lava_cool(colours, &length, phase));
        assert(colours[0] == 0);
        assert((length & DODONGO_LAVA_LENGTH) == 768);
        memcpy(snapshot, colours, sizeof colours);
        assert(!dodongo_lava_cool(colours, &length, phase));
        assert(!memcmp(snapshot, colours, sizeof colours));
    }
    for (i = 1; i < 5; ++i) {
        unsigned c = colours[i];
        assert((c & 31) == ((c >> 5) & 31));
        assert((c & 31) == ((c >> 10) & 31));
    }
    /* Completed room: one source clear snapshot reaches the same endpoint
     * class. Loading a fresh bank restores its original palette/phase. */
    length = DODONGO_LAVA_TILE | 768;
    memcpy(colours, original, sizeof colours);
    assert(dodongo_lava_cool(colours, &length, 256));
    assert(!dodongo_lava_cool(colours, &length, 0));
    assert(!dodongo_lava_cool(colours, &length, 300));
    puts("Dodongo lava: source phase, transparent entry, repeated view, clear reload pass");
    return 0;
}
