/*
** Kokiri Forest scene loader for the isolated Jo Engine / SGL viewer.
*/

#ifndef __KOKIRI_SGL_H__
# define __KOKIRI_SGL_H__

/** @brief Upload the scene's textures/CLUTs and bind them to the SGL tables.
 *  @return true on success; on failure jo_core_error() describes the reason. */
bool            kokiri_scene_load(void);

/** @brief VDP1 bytes consumed by the scene, valid after kokiri_scene_load(). */
unsigned int    kokiri_scene_vram_used(void);

/** @brief Submit the whole scene as one SGL polygon list. */
void            kokiri_scene_draw(void);

#endif /* !__KOKIRI_SGL_H__ */

/*
** END OF FILE
*/
