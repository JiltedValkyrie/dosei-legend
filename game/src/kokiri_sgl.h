/*
** Mesh loader for the isolated Jo Engine / SGL viewer.
*/

#ifndef __KOKIRI_SGL_H__
# define __KOKIRI_SGL_H__
#include <stdint.h>
#include "asset_names.h"

/** @brief Upload every mesh's textures/CLUTs and bind them to the SGL tables.
 *  @return true on success; on failure jo_core_error() describes the reason. */
bool            kokiri_scene_load(void);
/* Replace Link's own model/skin/clip banks at an age transition. */
bool            kokiri_link_set_age(bool adult);

/* The flat cutscene field's bank number. It is seen end to end, unlike a
** forest room, so the loader gives it a far larger draw distance. */
#define KOKIRI_FIELD_SCENE STORY_BANK_FIELD

/* Load one (scene, room) VDP1 geometry bank: S<scene>R<room>.MSH/.TEX. */
bool            kokiri_scene_load_bank(unsigned int scene, unsigned int room);
/* Source King Dodongo cooling phase; resident room palettes only. */
void            kokiri_scene_dodongo_lava(unsigned phase);

/* Stage a prerendered interior's 320x240 backdrop on VDP2 (S<scene>R<room>.RGB)
** and put the sprite layer IN FRONT of it, so Link draws over the picture
** instead of behind it. Ordinary scenes restore the title-style order, where
** the scroll screen sits in front so the title artwork can overlay the world. */
bool            kokiri_scene_load_backdrop(unsigned int scene, unsigned int room);

/* True while a prerendered backdrop is being shown instead of geometry. */
bool            kokiri_scene_backdrop_active(void);
bool            kokiri_scene_update(void);
/* Preload forest-flight banks into the required RAM cart before playback. */
bool            kokiri_opening_cache_load(void);
void            kokiri_opening_cache_free(void);
bool            kokiri_opening_cache_meshes(unsigned int rooms);

/** @brief VDP1 bytes consumed, valid after kokiri_scene_load(). */
unsigned int    kokiri_scene_vram_used(void);
/* Share of 512 KiB VDP1 VRAM allocated to textures and reserved tables. */
unsigned int    kokiri_scene_vram_percent(void);

/** @brief Submit the forest. Resets the per-frame submission counters, so it
 *  must be called before any actor draw in the same frame. */
void            kokiri_scene_draw(void);
/* Debug: 0 full, 1 in-place, 2 high gather, 3 low gather, 4 fallback, 5 empty. */
unsigned        kokiri_scene_gather_mode(void);

/** @brief Submit Link at a world position, facing @p yaw (binang). */
void            kokiri_link_draw(int x, int y, int z, int yaw);
/* First-person slingshot arm, pinned to the camera focus (see kokiri_sgl.c). */
void            kokiri_link_draw_first_person(int x, int y, int z, int yaw, int pitch);
/* SGL display level: polygons and sprites nearer than screen distance >> level
 * are rejected. OoT's gameplay view near plane is 10 (z_view.c); level 5 gives
 * 240 >> 5 = 7 (play) and 290 >> 5 = 9 (first person, where the child's
 * slingshot arm lies inside the old level-3 cut of 36). */
/* Level 3 everywhere (240 >> 3 = 30). Level 5 let ground corners a few
 * units from the eye project past VDP1's coordinate range and wrap into
 * screen-wide wedges (BUG_FEATURE_LOG, tools/field_walk_probe.py). The
 * first-person arm that wanted it was removed (human, 2026-10-01). */
#define KOKIRI_ZDSP_LEVEL 3
/* Screen-space HUD sprite depth just past the live near rejection, so every
 * visible world polygon sorts behind it. `above` orders HUD layers (1 front). */
int             kokiri_hud_depth(int above);
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
#ifdef DOSEI_WARP_PROBE
/* Warp probe readout, measurement only. 0..5 nearest polygon
** (depth, far, world extent, tile, v0, v1); 6..12 worst projected-span
** candidate (score, depth, far, extent, tile, v0, v1). */
int             kokiri_warp_probe(unsigned int field);
#endif

/** @brief Draw ambient fairies at the original Kokiri NPC homes. */
void            kokiri_fairies_draw(unsigned int tick);
/* Gear pickup billboards, drawn only while the item is still uncollected. */
void            kokiri_items_draw(unsigned int tick);
void kokiri_drop_draw(unsigned int item, int x, int y, int z, unsigned int tick);

void            kokiri_boulder_draw(void);
void            kokiri_nut_draw(void);
/* En_Karebaba (karebaba_draw.c). Load is not fatal: no file, no babas drawn. */
bool            karebaba_draw_load(void);
void            kokiri_babas_draw(void);
/* Resident 8-bit colour-bank texture from memory (minimap markers). */
bool            kokiri_resident_sprite_8bit(const unsigned char *pixels,
                                            unsigned int width, unsigned int height,
                                            unsigned int *slot);
extern unsigned int kokiri_sprite_peak;  /* peak sprite slots used */
/* Link's companion fairy, at the position src/navi.c keeps for her. */
void            kokiri_navi_draw(int x, int y, int z);
void            kokiri_grass_draw(void);
unsigned int    kokiri_scene_room(void);
void            kokiri_seed_draw(int32_t x, int32_t y, int32_t z);
/* Room of the loaded bank (any scene). */
unsigned int    kokiri_bank_room(void);
void            kokiri_rupees_draw(unsigned int tick);
void            kokiri_rupee_hud_draw(void);
/* Pause equipment grid, drawn over the frozen world. */
/* No sprite slot was available. */
#define KOKIRI_TILE_NONE 0xFFFFFFFFu
/* Upload a 4bpp tile into the resident bank's VDP1 space, above the resident
** meshes, and return its sprite slot. Reclaimed by the next bank load. */
unsigned int    kokiri_bank_rgb_upload(const void *pixels, unsigned int width,
                                       unsigned int height);
unsigned int    kokiri_bank_tile_upload(const void *pixels, const void *clut,
                                        unsigned int width,
                                        unsigned int height,
                                        unsigned int *colno);
/* Submit a caller-owned polygon list through the scene's accounting. */
void            kokiri_submit_pdata(PDATA *pdata);

void            kokiri_menu_draw(void);
/* OoT's own message panel, drawn behind cutscene text. Screen-space pixels,
** centred on (x, y). Silently does nothing if the texture failed to load. */
void            kokiri_message_box_draw(int x, int y, int width, int height);
/* The prompt on the box's bottom edge: OoT's continue triangle, or its end
** square on the last page. */
void            kokiri_message_mark_draw(int x, int y, bool last_page);
/* Four flat source-geometry lock corners in the target's source attention
** colour. The aim variant is white and stays at the shot ray centre. */
typedef enum {
    KOKIRI_RETICLE_ENEMY,
    KOKIRI_RETICLE_NPC,
    KOKIRI_RETICLE_POI,
    KOKIRI_RETICLE_AIM,
    KOKIRI_RETICLE_COUNT
} kokiri_reticle_kind_t;
void            kokiri_lock_reticle_draw(int x, int y, unsigned kind);

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

void kokiri_cutscene_effects_draw(void);
void kokiri_flame_draw(int32_t x,int32_t y,int32_t z,unsigned tick);
void kokiri_particle_draw(int x,int y,int z,unsigned radius,unsigned colour,unsigned dither);
void kokiri_score_popup_draw(int x,int y,int z,unsigned score_index,unsigned scale);
void kokiri_minigame_score_draw(unsigned score);
/* Release only transient nightmare textures; resident Link/UI remain. */
void kokiri_cutscene_tiles_reset(void);
/* NPC tiles live after the current room, never over its texture bank. */
unsigned int kokiri_actor_bank_generation(void);
void kokiri_actor_tiles_reset(void);
void kokiri_hit_filter(unsigned level);
unsigned kokiri_hit_gouraud(unsigned level);
/* Dithered ground contact marker: no textures or character meshes. */
void kokiri_actor_shadow(int x, int y, int z, unsigned radius);
/* Slave-SH-2 frame job (2026-10-09): the scene prepare (Link's skin runs
 * at frame start, link_anim_frame_start). */
void kokiri_frame_slave_kick(bool scene);
unsigned int kokiri_frame_slave_us(void);   /* last skin+prepare job, slave FRT */
unsigned int kokiri_sgl_drain_us(void);
/* Slave job order (2026-10-12): scene prepare queued before the core update.
** Mednafen A/B in Kokiri: whole frame 173.6 -> 154.8 ms moving, 133.2 ->
** 125.9 idle, so it is the default. Debug L+R+Left flips it back for A/B. */
extern bool kokiri_prep_first;     /* master wait for SGL's slave queue */
extern bool kokiri_parallel_prepare;
extern volatile unsigned forest_envelope_enabled; /* Debug: zero disables camera-region reuse. */
unsigned kokiri_scene_candidate_reused(void);
unsigned kokiri_scene_candidate_count(void);
unsigned kokiri_scene_envelope_variant(void); /* 1..5, see kokiri_sgl.c */
void kokiri_scene_envelope_cycle(void);       /* Debug L+R+Right */
void kokiri_frame_master_prepare(bool scene);
void kokiri_shadow_resolve(void);           /* deferred shadow floors, after the join */
void kokiri_actor_shadow_floor(int x, int y, int z, unsigned radius, int floor);
void kokiri_navi_draw_colour(int x, int y, int z, unsigned int colour, bool sparkles);
/* Adult hero gear tiles into the actor bank after a bank reset; false =
** not enough room (Link falls back to his flat hand/back variants). */
bool kokiri_link_gear_upload(void);
#endif /* !__KOKIRI_SGL_H__ */

/*
** END OF FILE
*/
