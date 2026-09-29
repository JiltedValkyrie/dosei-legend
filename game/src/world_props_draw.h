#ifndef WORLD_PROPS_DRAW_H
#define WORLD_PROPS_DRAW_H
#include <stdbool.h>
bool world_props_draw_load(unsigned int scene);
void world_props_draw_free(void);
bool world_props_draw_upload(void);
void world_props_draw(unsigned int tick);
/* Runtime draw-skip mask for Kronos debugging.  Bit 0=rocks/pots, 1=signs, 2=grass.
 * Default 0.  Toggle in Kronos debugger by symbol name. */
extern volatile int dosei_draw_mask;
#endif
