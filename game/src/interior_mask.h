#ifndef DOSEI_INTERIOR_MASK_H
#define DOSEI_INTERIOR_MASK_H
#include <stdbool.h>
/* Prerendered-room occlusion masks (tools/build_interior_masks.py): the
 * N64 room depth mesh as backdrop-pixel tiles depth-sorted with actors.
 * Fixed-camera rooms only; a scene without S<n>R0.MSK simply has none. */
bool interior_mask_load(unsigned int scene_index);
void interior_mask_free(void);
/* After kokiri_actor_tiles_reset(): put the tiles into the actor bank. */
bool interior_mask_upload(void);
void interior_mask_draw(void);
#endif
