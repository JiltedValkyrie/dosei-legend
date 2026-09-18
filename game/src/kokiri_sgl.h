/*
** Mesh loader for the isolated Jo Engine / SGL viewer.
*/

#ifndef __KOKIRI_SGL_H__
# define __KOKIRI_SGL_H__

/** @brief Upload every mesh's textures/CLUTs and bind them to the SGL tables.
 *  @return true on success; on failure jo_core_error() describes the reason. */
bool            kokiri_scene_load(void);
bool            kokiri_scene_update(void);

/** @brief VDP1 bytes consumed, valid after kokiri_scene_load(). */
unsigned int    kokiri_scene_vram_used(void);

/** @brief Submit the forest. Resets the per-frame submission counters, so it
 *  must be called before any actor draw in the same frame. */
void            kokiri_scene_draw(void);

/** @brief Submit Link at a world position, facing @p yaw (binang). */
void            kokiri_link_draw(int x, int y, int z, int yaw);
/* Identity of the closest DISTANCE-stippled polygon this prep, for the near
** checkerboard. Facts only: authored stipple is excluded because it is
** legitimate at any depth, and near/far together distinguish a small close
** polygon from a large one reaching away. Tiles are shared, so the polygon
** index and vertex ids are what actually identify the surface. -1 means none
** was seen this frame. */
int             kokiri_scene_mesh_near_depth(void);
int             kokiri_scene_mesh_near_far(void);
int             kokiri_scene_mesh_near_tile(void);
int             kokiri_scene_mesh_near_polygon(void);
unsigned short  kokiri_scene_mesh_near_vertex(unsigned int corner);
bool            kokiri_scene_mesh_near_authored(void);

/** @brief Draw ambient fairies at the original Kokiri NPC homes. */
void            kokiri_fairies_draw(unsigned int tick);

/** @brief Submissions SGL refused this frame. Non-zero means some faces never
 *  reached VDP1, so the picture is incomplete. */
unsigned int    kokiri_scene_rejected(void);
/* True when the prepared list was reused this frame, which makes the
** depth/partition/fog timers stale rather than current. */
bool            kokiri_scene_reused(void);

/** @brief Bit per accepted list: 1 = forest, 2 = Link. */
unsigned int    kokiri_scene_accepted_mask(void);

/** @brief Polygons in the lists SGL accepted this frame. */
unsigned int    kokiri_scene_submitted(void);
#ifdef DOSEI_ACTOR_ORDER_PROBE
unsigned int    kokiri_order_changed(void);
unsigned int    kokiri_order_conflicts(void);
unsigned int    kokiri_order_frames(void);
unsigned int    kokiri_order_error(void);
#endif

#endif /* !__KOKIRI_SGL_H__ */

/*
** END OF FILE
*/
