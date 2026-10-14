#ifndef DOSEI_OOT_CORE_HOST_H
#define DOSEI_OOT_CORE_HOST_H
/*
** C side of the oot-core blob (oot-core/include/oot_core_api.h). Boot loads
** OOTCORE.BIN and the scene collision blobs into their cart carves; each
** 30 Hz gameplay step drives the decomp play state at the decomp's 20 Hz.
** Built only with OOT_CORE=1; the calls compile to nothing otherwise.
*/
#include <stdbool.h>
#include <stdint.h>
#include "../oot-core/include/oot_cutscene_camera.h"
#include "../oot-core/include/oot_core_shop.h"
#ifndef OOT_CORE_TRANSITION_RELOAD
#define OOT_CORE_TRANSITION_RELOAD 0x10000
#endif
typedef struct {
    unsigned int actors, missing, fallback, slots;
} oot_core_sprite_stats_t;

#ifdef DOSEI_OOT_CORE
#include "oot_core_api.h"

/* Boot: load + init the blob and run the gate bench. False if not loaded. */
bool oot_core_boot(void);
/* Joined snapshot only: safe during the slave's next update. */
const OotCoreCutsceneCameraView* oot_core_cutscene_camera(void);
const OotCoreShopView* oot_core_shop_view(void);
void oot_core_timer_draw(bool visible);
int oot_core_cutscene_screen_distance(void);
void oot_core_cutscene_camera_apply(void);
void oot_core_cutscene_letterbox_draw(void);
/* Second-CPU core update (2026-10-09, PLAYER_SOURCE; stubs otherwise). The
 * host steps queue core updates; main.c kicks them onto the slave SH-2 at
 * the start of the draw and joins before the HUD. Between kick and join the
 * master must not enter the core (counted: oot_core_async_stats). */
void oot_core_async_kick(void);
void oot_core_async_join(void);
bool oot_core_async_busy(void);
void oot_core_async_stats(unsigned int out[5]); /* updates, overlap us, join wait us, core / bg violations */
unsigned int oot_core_async_violation_line(void); /* Debug: last ENTRY line; read before stats */
unsigned int oot_core_slave_job_us(void);        /* last slave core job, its own FRT */
#ifdef PLAYER_SOURCE
/* The real decomp Player, read after every core update (recomp_link and
** recomp_link_yaw follow it). Valid once a scene's Player exists. */
extern OotCorePlayerView oot_core_player;
extern bool oot_core_player_valid;
/* Source Player's A label (OOT_CORE_DO_*), from its last update. */
unsigned int oot_core_player_do_action(void);
/* Door Room_RequestNewRoom since the last core update, -1 none. */
int oot_core_player_room_request(void);
/* A C-side enemy's hit (1/16 hearts) on the real Player. */
void oot_core_player_damage(int damage);
/* Saturn Y jump extension; true when the Player jumped. */
bool oot_core_player_jump(void);
void oot_core_carry_cancel(void);
/* After the host places Link at a spawn: take the Player's own position
** (a void-out/respawn spawns him at the respawn point, not the entrance). */
void oot_core_player_resync(void);
/* Debug overlay: the real Player's anchor draw pass, us. */
unsigned int oot_core_player_draw_us(void);
/* Pause menu close: load the clip groups of the C items now equipped,
** behind the menu. False = wait (a CD-DA fanfare owns the drive). */
bool oot_core_player_groups_prepare(void);
/* scene_flow_load, after the old scene is gone: common clips (PLAYRES.PFB). */
bool oot_core_player_resident(void);
#else
static inline unsigned int oot_core_player_draw_us(void) { return 0; }
#define oot_core_player_groups_prepare() true
#define oot_core_player_resident() true
#endif
/* Failed code-pack admission blocks gameplay until explicit scene restart. */
bool oot_core_scene_failed(void);
#include "gameplay.h"
/* After gameplay_step (fixed 30 Hz). Starts/stops the decomp play state
** with the scene and steps it 2 of every 3 calls. `in` = that step's input. */
void oot_core_frame(const gameplay_input_t *in);
unsigned int oot_core_skybox_time(void);
unsigned int oot_core_skybox_settings(void);
/* Explicit source/probe sky assignment; does not clear pending song state. */
void oot_core_clock_reset(unsigned int skybox_time);
/* Source frontend reset: file choose 0; level select dayTime. */
void oot_core_session_reset(unsigned int skybox_time);
/* Bit 0: a decomp conversation or text box is up (C Link and C A/B
** actions wait). Bit 1: a decomp actor offers talk (A goes to it). */
unsigned int oot_core_talk(void);
/* Decomp NPCs the C npc_draw renderer draws (OotCoreNpcView). */
int oot_core_npcs(const OotCoreNpcView **out);
/* Draw the decomp text box (VDP2 text + VDP1 panel); true while it is up. */
bool oot_core_message_box(void);
unsigned int oot_core_npc_text(unsigned int command);
/* prop_query: decomp state word of actor `id` near (x, z), -1 if none. */
int oot_core_prop(short id, int x, int z);
const char *oot_core_debug_text(void);
const char *oot_core_debug_text2(void);
const oot_core_sprite_stats_t *oot_core_sprite_stats(void);
int oot_core_door_action(unsigned int kind, unsigned int flag, int front_side, bool commit);
unsigned int oot_core_scene_layer(void);
unsigned int oot_core_destination_layer(unsigned int original_base_scene);
void oot_core_cancel_transition_time(void);
int oot_core_transition_request(bool consume);
bool oot_core_ocarina_start(void);
unsigned int oot_core_ocarina_state(void);
unsigned int oot_core_ocarina_note(void); /* 0 none, 1 A, 2 down, 3 right, 4 left, 5 up */
unsigned int oot_core_ocarina_song(void); /* completed source song + 1; consume */
bool oot_core_ocarina_sun_allowed(void);
bool oot_core_ocarina_sun_start(void);
void oot_core_scene_restart(void); /* after a successful full scene reload */
/* Release old scene resources before loading the next scene's native assets.
 * Destructors run while their OOC/OOB/code pack is still resident. */
void oot_core_scene_unload(void);
#ifdef CORE_COLLISION
/* Load the scene's core PlayState now (its collision is the only world). */
bool oot_core_scene_enter(unsigned int scene, unsigned int spawn);
#endif
/* Link's C-button tools on the decomp actors (bridge_items.cpp). Slot is the
** inventory slot; false = refused (no ammo/magic, one already out, no play). */
bool oot_core_tool_use(unsigned int slot, const int32_t origin[3], uint16_t yaw, int16_t pitch);
bool oot_core_tool_holding(void);
/* Arrow*_Hit screen tint as a VDP2 colour offset; false when none. */
bool oot_core_hit_tint(int16_t rgb[3]);   /* bomb/Bombchu over Link's head */
bool oot_core_tool_throw(void);
bool oot_core_tool_pull(int32_t step_q8[3]); /* hookshot flight this step */
void oot_core_tool_register(void);  /* C contact AT mirrors of live tools */
/* Phase 2 draw shim meshes: upload after a bank reset, draw the items. */
void oot_core_meshes_upload(void);
void oot_core_meshes_draw(void);

bool oot_core_is_loaded(void);
/* Play state active for the current scene. */
bool oot_core_is_playing(void);
bool oot_core_owns_owl(void); /* cached cold scene admission, safe during slave update */
const OotCoreBench *oot_core_bench_result(void);
/* Time of the last decomp update step (Actor_UpdateAll, collision, effects), us. */
unsigned int oot_core_update_us(void);
int oot_core_actors(int category);
/* Live actors of a category, for C drawing (see OotCoreActorView). */
int oot_core_view(int category, OotCoreActorView *out, int max);
/* Kokiri Forest grass (En_Kusa) and floor rupees (En_Item00) belong to the
** decomp while it plays: the C copies stop drawing, cutting and collecting. */
static inline bool oot_core_owns_kokiri_props(void) { return oot_core_is_playing(); }
/* Kokiri children (En_Ko), Mido (En_Md) and the wonder spots (En_Wonder_
** Item/Talk2) belong to the decomp while it plays. Saria stays C (her
** greeting is a C cutscene until z_demo). */
/* 2026-10-03: off. Decomp NPC logic in 64-bit Fx cost 11.5 ms per step;
** C keeps them (fast) until the 32-bit Fx conversion lands. */
static inline bool oot_core_owns_kokiri_npcs(void) { return false; }
#else
static inline const OotCoreCutsceneCameraView* oot_core_cutscene_camera(void) { return 0; }
static inline const OotCoreShopView* oot_core_shop_view(void) { return 0; }
static inline void oot_core_timer_draw(bool visible) { (void)visible; }
static inline int oot_core_cutscene_screen_distance(void) { return 0; }
static inline void oot_core_cutscene_camera_apply(void) {}
static inline void oot_core_cutscene_letterbox_draw(void) {}
static inline void oot_core_async_kick(void) {}
static inline void oot_core_async_join(void) {}
static inline bool oot_core_async_busy(void) { return false; }
static inline unsigned int oot_core_async_violation_line(void) { return 0; }
static inline bool oot_core_is_playing(void) { return false; }
#define oot_core_player_groups_prepare() true
#define oot_core_player_resident() true
static inline bool oot_core_scene_failed(void) { return false; }
#define oot_core_frame(in) ((void)0)
#define oot_core_skybox_time() 0x8000u
#define oot_core_skybox_settings() 1u
static inline void oot_core_clock_reset(unsigned int skybox_time) { (void)skybox_time; }
static inline void oot_core_session_reset(unsigned int skybox_time) { (void)skybox_time; }
static inline bool oot_core_owns_kokiri_props(void) { return false; }
static inline bool oot_core_owns_owl(void) { return false; }
static inline bool oot_core_owns_kokiri_npcs(void) { return false; }
static inline unsigned int oot_core_talk(void) { return 0; }
static inline unsigned int oot_core_update_us(void) { return 0; }
static inline bool oot_core_message_box(void) { return false; }
static inline unsigned int oot_core_npc_text(unsigned int command) { (void)command;return 0; }
static inline int oot_core_door_action(unsigned int kind, unsigned int flag, int front_side, bool commit)
{ (void)kind; (void)flag; (void)front_side; (void)commit; return 0xFF00; }
static inline unsigned int oot_core_scene_layer(void) { return 0; }
static inline unsigned int oot_core_destination_layer(unsigned int scene) { (void)scene; return 0; }
static inline void oot_core_cancel_transition_time(void) {}
static inline int oot_core_transition_request(bool consume) { (void)consume; return -1; }
static inline bool oot_core_ocarina_start(void) { return false; }
static inline bool oot_core_tool_use(unsigned int slot, const int32_t origin[3], uint16_t yaw, int16_t pitch)
{ (void)slot; (void)origin; (void)yaw; (void)pitch; return false; }
static inline bool oot_core_tool_holding(void) { return false; }
static inline bool oot_core_tool_throw(void) { return false; }
static inline bool oot_core_tool_pull(int32_t step_q8[3]) { (void)step_q8; return false; }
static inline void oot_core_tool_register(void) {}
static inline unsigned int oot_core_ocarina_state(void) { return 0; }
static inline unsigned int oot_core_ocarina_note(void) { return 0; }
static inline unsigned int oot_core_ocarina_song(void) { return 0; }
static inline bool oot_core_ocarina_sun_allowed(void) { return false; }
static inline bool oot_core_ocarina_sun_start(void) { return false; }
static inline void oot_core_scene_restart(void) {}
static inline void oot_core_scene_unload(void) {}
static inline int oot_core_prop(short id, int x, int z) { (void)id; (void)x; (void)z; return -1; }
#endif

#endif
