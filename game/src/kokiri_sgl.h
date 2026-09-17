/*
** Mesh loader for the isolated Jo Engine / SGL viewer.
*/

#ifndef __KOKIRI_SGL_H__
# define __KOKIRI_SGL_H__

/** @brief Upload every mesh's textures/CLUTs and bind them to the SGL tables.
 *  @return true on success; on failure jo_core_error() describes the reason. */
bool            kokiri_scene_load(void);

/** @brief VDP1 bytes consumed, valid after kokiri_scene_load(). */
unsigned int    kokiri_scene_vram_used(void);

/** @brief Submit the forest. Resets the per-frame submission counters, so it
 *  must be called before any actor draw in the same frame. */
void            kokiri_scene_draw(void);

/** @brief Submit Link at a world position, facing @p yaw (binang). */
void            kokiri_link_draw(int x, int y, int z, int yaw);
/* Diagnostics for the giant near checkerboard: the closest polygon that was
** still stippled, its tile, and whether that stipple came from the authored
** flag or from the distance test. -1 tile means none was seen. */
int             kokiri_scene_mesh_near_depth(void);
int             kokiri_scene_mesh_near_tile(void);
bool            kokiri_scene_mesh_near_authored(void);

/** @brief Draw ambient fairies at the original Kokiri NPC homes. */
void            kokiri_fairies_draw(unsigned int tick);

/** @brief Submissions SGL refused this frame. Non-zero means some faces never
 *  reached VDP1, so the picture is incomplete. */
unsigned int    kokiri_scene_rejected(void);

/** @brief Bit per accepted list: 1 = forest, 2 = Link. */
unsigned int    kokiri_scene_accepted_mask(void);

/** @brief Polygons in the lists SGL accepted this frame. */
unsigned int    kokiri_scene_submitted(void);

#endif /* !__KOKIRI_SGL_H__ */

/*
** END OF FILE
*/
