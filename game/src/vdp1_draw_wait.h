#ifndef DOSEI_VDP1_DRAW_WAIT_H
#define DOSEI_VDP1_DRAW_WAIT_H
#include <jo/jo.h>
#include "demo.h"

/* slSynch starts the next VDP1 draw before returning to the game callback.
 * Sampling CEF once here can therefore reject every bank change forever.
 * Give the in-flight draw time to finish without submitting it again. Never
 * overwrite its textures while busy, and bound the wait even if ticks stop.
 */
static inline bool vdp1_wait_for_draw_end(void)
{
    unsigned int start = demo_clock();
    unsigned int polls = 1048576;
    do {
        if (JO_VDP1_EDSR & 2) return true;
        if (demo_clock() - start >= 2) return false;
    } while (--polls);
    return false;
}
#endif
