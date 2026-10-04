#ifndef DOSEI_SCENE_FLOW_H
#define DOSEI_SCENE_FLOW_H
#include <stdbool.h>
#include <stdint.h>
#include "scene_table.h"

/*
** Which scene is loaded, and the doors between scenes.
**
** Two kinds of scene, because OoT has two (decomp include/room.h):
**
**   ordinary  ROOM_SHAPE_TYPE_NORMAL. Real geometry in VDP1 banks, drawn with
**             the follow camera. Kokiri Forest.
**   interior  ROOM_SHAPE_TYPE_IMAGE. One prerendered 320x240 backdrop on VDP2
**             and a fixed camera, which is how the original draws Link's house
**             and the other Kokiri buildings. Costs no VDP1 texture space --
**             which matters, because the tightest forest bank leaves under
**             5 KB of it spare.
**
** A door is a real collision triangle carrying SurfaceType.exitIndex; see
** tools/build_scene_table.py for how it resolves to a scene and a spawn. Link
** walks onto the triangle, exactly as in the original, rather than through an
** invented trigger volume.
*/

/* Load a scene: its collision, and either its room bank or its backdrop.
** False if a load fails. Collision, textures and actor storage may already be
** replaced; callers must reload a valid scene before resuming gameplay.
**
** Deliberately does NOT touch the save. demo_init() stages the forest here
** just to give the title's attract flight some collision to fly over, which
** is not "the player is in the forest"; recording the player's position is
** the caller's job, at the point they actually arrive somewhere. */
bool            scene_flow_load(unsigned int scene, unsigned int spawn);

/* True when the loaded scene's collision has a working XZ index. Rebuilt on
** every scene load; false means the slower full-scan fallback is in use. */
extern bool     scene_collision_indexed;

/* The scene currently loaded, and whether it is a prerendered interior. */
unsigned int    scene_flow_scene(void);
/* SAVE_SCENE_* -> table index, so a saved file resumes in the right scene. */
unsigned int    scene_flow_index_for_save(unsigned int save_scene);
bool            scene_flow_is_interior(void);
bool scene_flow_pivot(void);
/* Kokiri Shop browsing view on/off (true when it switched). */
bool scene_flow_shop_browse(bool on);
bool scene_flow_toggle_view(void);

/* The loaded scene's table entry, for the fixed camera and room count. */
const scene_entry_t *scene_flow_entry(void);

/* Which door Link is standing on, or -1. Only doors belonging to the loaded
** scene are considered, and his feet must be near the doorway's floor so a
** doorway cannot fire from a different storey. */
int             scene_flow_door_at(int32_t x, int32_t y, int32_t z);

/* Where a spawn puts Link. Safe for any index; out of range gives spawn 0. */
const scene_spawn_t *scene_flow_spawn(unsigned int scene, unsigned int spawn);

/* Vertical tolerance for standing on a door triangle, world units. A doorway
** is flat, and Link's feet sit on it, so this only has to absorb the
** difference between the triangle's averaged height and the floor he is
** actually standing on. */
#define SCENE_DOOR_HEIGHT   60

#endif
