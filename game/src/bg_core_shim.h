/*
 * CORE_COLLISION: the C bg_* collision API answered by the core's z_bgcheck
 * (bg_core_shim.c), plus the C Link wrappers over it (bg_core_link.c).
 */
#ifndef BG_CORE_SHIM_H
#define BG_CORE_SHIM_H

#include <stdbool.h>
#include <stdint.h>

#include "kokiri_collision.h"
#include "oot_core_bg.h"

/* Once after the core blob loads (OotCoreEntry.bg_api). */
void bg_core_shim_set_api(const OotCoreBgApi *core);
/* true in the game: the core's Actor_UpdateAll owns the DynaPoly frame
 * boundary; host tests that drive frames themselves pass false. */
void bg_core_shim_frame_owner(bool core_owns);
/* Scene exit, while the old PlayState still exists: proxies, water levels
 * and shim ownership reset together. */
void bg_core_shim_scene_reset(void);
/* The scene's core collision is loaded (queries answer). */
bool bg_core_ready(void);
uint32_t bg_core_shim_busy_hits(void);
/* Speed experiment: scene collision copy in Work RAM (OotCoreBgApi v3). */
int bg_core_fast_data(int mode);
/* Any polygon within radius of pos (feet-free point), C clear_radius. */
bool bg_core_sphere(const bg_vec_t *pos, int32_t radius, uint32_t ignore, bool skip_ceilings);
/* Debug overlay: host queries / proxy rebuilds since the last call. */
void bg_core_shim_counts(uint32_t *queries, uint32_t *rebuilds);
/* Floor-class polys only, highest at y <= pos->y (kokiri_collision_floor). */
int32_t bg_core_floor_class(const bg_vec_t *pos, uint32_t ignore);

#endif
