/*
** Isolated Jo Engine / SGL Kokiri Forest viewer.
**
** Title-recomp bring-up: textured forest, automatic yaw and baseline SCSP score.
** Title artwork, controls and source-space collision are connected. This is not
** a renderer-only performance comparison with the libyaul baseline.
**
** Resolution is TV_320x240 (jo/conf.h, NTSC non-480i), matching the libyaul
** build's 320x240 viewport, so the comparison needs no video-mode change.
*/

#include <jo/jo.h>
#include <string.h>

#include "kokiri_scene.h"
#include "kokiri_sgl.h"
#include "music.h"
#include "cdda.h"
#include "music_songs.h"
#include "music_banks.h"
#include "field_music.h"
#include "story_route.h"
#include "emerald_story.h"
#include "action_audio.h"
#include "recomp.h"
#include "karebaba.h"
#include "skulltula.h"
#include "wall_skull.h"
#include "dekubaba.h"
#include "hintnuts.h"
#include "gohma_larva.h"
#include "gohma.h"
#include "game_over.h"
#include "navi.h"
#include "gameplay.h"
#include "player_items.h"
#include "dialogue_text.h"
#include "minimap.h"
#include "pause_windows.h"
#include "ui_preferences.h"
#include "minimap_data.h"
#include "kokiri_dialogue.h"
#include "link_anim_state.h"
#include "link_clips.h"
#include "frame_timer.h"
#include "perf_sub.h"
#include "oot_follow.h"
#include "ram_cart.h"
#include "ram_low.h"
#include "heap_profile.h"
#include "sgl_registers.h"
#include "actor_sys.h"
#include "npc_draw.h"
#include "save_device.h"
#include "file_select.h"
#include "level_select.h"
#include "scene_flow.h"
#include "message.h"
#include "cutscene.h"
#include "cutscene_actor.h"
#include "game_mode.h"

/*
** Baseline camera, in the scene's native source space.
**
** Position: kokiri_collision_spawn() in the libyaul build searches outward
** from x=-300,z=0 and derives y from the floor plus EYE_HEIGHT (90). Replaying
** that search over FOREST.BIN's 1692 collision triangles lands on ring 0 with
** floor y=1, giving (-300, 91, 0) -- the pose the handoff documents. The
** recomp now derives this spawn and raises it 24 units through collision.
**
** Facing: at yaw 0 the baseline's Y-rotation matrix is identity and it uses
** the rotated z as depth (kokiri_scene.c:160-171), so yaw 0 looks along +Z.
** Its projection is sy = 120 - offset(py), so +Y is up. SGL projects +Y
** downward: the fixed view must be (x-CAM_X, CAM_Y-y, z-CAM_Z).
*/
#define SCREEN_DISTANCE     (240)
static bool aim_dot_shown;  /* VDP2 slingshot crosshair on screen */
static bool         scene_ready;
static bool         music_ready;
static bool         debug_visible;
static unsigned int rejected_total;
static void __attribute__((optimize("Os"))) viewer_hud(void);
static void __attribute__((optimize("Os"))) dialogue_box(void);
static void __attribute__((optimize("Os"))) inventory_menu(void);
static void __attribute__((optimize("Os"))) game_over_screen(void);
static void __attribute__((optimize("Os"))) file_select_screen(void);
static void __attribute__((optimize("Os"))) cutscene_text(void);
static void         cutscene_fade(void);
static void         play_test_room(void);

/* Read DIALOG.TXT into its cart carve and bind it. jo_fs_read_file holds a
** transient work-RAM copy; only the cart copy stays. */
typedef char dialogue_text_fits[DIALOGUE_TEXT_BYTES <= RAM_CART_DIALOGUE_BYTES ? 1 : -1];
typedef char cutscene_text_fits[CUTSCENE_TEXT_BYTES <= RAM_CART_CUTTEXT_BYTES ? 1 : -1];
static bool __attribute__((optimize("Os"))) table_file_load(const char *name, void *destination, unsigned int bytes,
                               bool (*bind)(const uint8_t *, uint32_t))
{
    uint8_t    *carve = (uint8_t *)destination;
    void       *data;
    int         length = 0;
    bool        ok;

    if (!carve) {
        jo_core_error("%s: no cart carve", name);
        return (false);
    }
    data = jo_fs_read_file(name, &length);
    if (!data) {
        jo_core_error("%s: read failed", name);
        return (false);
    }
    ok = length > 0 && length <= (int)bytes;
    if (ok) {
        memcpy(carve, data, (unsigned int)length);
        ok = bind(carve, (uint32_t)length);
    }
    jo_free(data);
    if (!ok) jo_core_error("%s: size/header mismatch", name);
    return (ok);
}

typedef char actor_pool_fits[ACTOR_POOL_MAX * sizeof(actor_t) <= RAM_CART_ACTOR_POOL_BYTES ? 1 : -1];
/* Master-owned legacy actor pool: hot scans/handles belong in high WRAM.
 * Core has its own actor world; no slave or DMA writes this pool. Retain
 * the reserved cart carve and DOSEI_CART_ACTOR_POOL build fallback. */
#ifndef DOSEI_CART_ACTOR_POOL
static actor_t fast_actor_pool[ACTOR_POOL_MAX];
#endif
static bool text_file_load(const char *name, unsigned int offset, unsigned int bytes,
                           bool (*bind)(const uint8_t *, uint32_t))
{
    return table_file_load(name, ram_cart_fixed(offset, bytes), bytes, bind);
}
typedef char minimap_file_fits[MINIMAP_FILE_BYTES <= RAM_CART_MINIMAP_BYTES ? 1 : -1];
static bool __attribute__((optimize("Os"))) dialogue_text_load(void)
{
    return (text_file_load("DIALOG.TXT", RAM_CART_DIALOGUE_OFFSET,
                           RAM_CART_DIALOGUE_BYTES, dialogue_text_bind) &&
            text_file_load("CUTTEXT.TXT", RAM_CART_CUTTEXT_OFFSET,
                           RAM_CART_CUTTEXT_BYTES, cutscene_text_bind) &&
            text_file_load("MINIMAP.BIN", RAM_CART_MINIMAP_OFFSET,
                           RAM_CART_MINIMAP_BYTES, minimap_bind) &&
            table_file_load("MUSICTRG.BIN", jo_malloc(MUSICTRG_BYTES),
                           MUSICTRG_BYTES, music_banks_bind) &&
            table_file_load("GOHMAPOS.BIN", RAM_LOW(RAM_LOW_GOHMA_POSES_OFFSET),
                           RAM_LOW_GOHMA_POSES_BYTES, gohma_bind) &&
            text_file_load("TITLEPTH.BIN", RAM_CART_TITLEPTH_OFFSET,
                           RAM_CART_TITLEPTH_BYTES, recomp_title_paths_bind));
}

/* oot-core: decomp code in OOTCORE.BIN (oot_core_host.c); the header gives
** inline no-op stubs when DOSEI_OOT_CORE is off. */
#include "oot_core_host.h"
#ifdef CORE_COLLISION
#include "bg_core_shim.h"
#endif

#ifdef DOSEI_TEXTURE_PROBE
#include "texture_probe.h"
static unsigned int probe_frame;
static unsigned int probe_stage;
static void texture_probe(void)
{
    unsigned int phase = probe_frame++ % 720;
    unsigned int step = phase % 360;
    int distance = step < 180 ? 500 - (int)step * 2 : 140;
    int turn = step < 180 ? 0 : ((int)step - 270) * 20;
    probe_stage = phase / 120;
    recomp_link_active = false;
    recomp_pitch = 0;
    if (phase < 360) {
        recomp_camera.x = PROBE_GROUND_X;
        recomp_camera.y = PROBE_GROUND_Y + 110;
        recomp_camera.z = PROBE_GROUND_Z - distance;
        recomp_yaw = (uint16_t)turn;
    } else {
        distance += 200;
        recomp_camera.x = PROBE_TREE_X;
        recomp_camera.y = PROBE_TREE_Y;
        recomp_camera.z = PROBE_TREE_Z + distance;
        recomp_yaw = (uint16_t)(32768 + turn);
    }
    slScrAutoDisp(NBG0ON);
    debug_visible = true;
}
#endif

/* The live projection's screen distance (pixels), one choice for the
** renderer and attention's on-screen test. */
int32_t             recomp_screen_distance(void)
{
    int core_distance = oot_core_cutscene_screen_distance();
    if (core_distance > 0) return core_distance;
    if(story_owl_talking())return story_owl_screen_distance();
    if (cutscene_screen_distance() > 0)
        return (int32_t)cutscene_screen_distance();
    if (kokiri_scene_backdrop_active() && scene_flow_entry()->cam_dist > 0)
        return (int32_t)scene_flow_entry()->cam_dist;
    if (recomp_view_first_person()) return 290; /* Subj3: 45 degree FOV. */
    if (scene_flow_pivot()) return 208; /* Camera_Unique7: 60 degree FOV. */
    return recomp_title_is_visible() ? 180 : SCREEN_DISTANCE;
}

/* Text diagnostics are cold glue, not geometry. Keep their code compact. */
#pragma GCC push_options
#pragma GCC optimize("Os")
unsigned int perf_sub[PS_COUNT];
#ifdef __sh__
#define perf_sub_sum (perf_sub_avg + PS_COUNT)
#else
unsigned int perf_sub_avg[PS_COUNT];
static unsigned int perf_sub_sum[PS_COUNT];
#endif
static unsigned int perf_frames, perf_sum_frames;   /* frame callbacks */
static void perf_sub_init(void)
{
    unsigned int i;
    for (i = 0; i < PS_COUNT; ++i)
        perf_sub[i] = perf_sub_avg[i] = perf_sub_sum[i] = 0;
    perf_frames = perf_sum_frames = 0;
}

void perf_sub_latch(void)
{
    unsigned int i;
    ++perf_frames;
    ++perf_sum_frames;
    for (i = 0; i < PS_COUNT; ++i) {
        perf_sub_sum[i] += perf_sub[i];
        perf_sub[i] = 0;
    }
}

/* Overlay refresh: per-frame averages over the window, then restart it.
 * One frame is too noisy to compare runs (Astra review 2026-10-12). */
static void perf_sub_average(void)
{
    unsigned int i;
    for (i = 0; i < PS_COUNT; ++i) {
        perf_sub_avg[i] = perf_sum_frames ? perf_sub_sum[i] / perf_sum_frames : 0;
        perf_sub_sum[i] = 0;
    }
    perf_sum_frames = 0;
}
#pragma GCC pop_options

static void __attribute__((optimize("Os"))) diagnostic_overlay(void)
{
    {
        /* Callback share of frame time: an estimate of master-CPU work,
         * not total utilization across both SH-2s. Sync includes GPU/VBlank
         * waiting. Existing smoothed timings keep the display readable. */
        unsigned int work = frame_timer_frame();
        unsigned int total = work + frame_timer_cost(FRAME_PHASE_SYNC);
        unsigned int cpu = total ? work * 100u / total : 0;
        /* Per SH-2 (2026-10-09): M = master frame-callback share; S = the
         * slave's jobs (Link skin + scene prepare + decomp core update); its
         * SGL polygon work is not counted. */
        static unsigned int slave_smooth;
#ifdef DOSEI_OOT_CORE
        unsigned int slave = total ? (oot_core_slave_job_us() + kokiri_frame_slave_us()) * 100u / total : 0;
#else
        unsigned int slave = total ? kokiri_frame_slave_us() * 100u / total : 0;
#endif
        if (slave > 100u) slave = 100u;
        slave_smooth += (int)(slave - slave_smooth) >> 2;
        jo_printf(1, JO_TV_HEIGHT / 8 - 1, "VRAM %3u%%  M %3u%%  S %3u%%  ",
                  kokiri_scene_vram_percent(), cpu, slave_smooth);
    }
    /* Last text writer: available on Clean, title, menus and cutscenes too.
     * recomp_clock is normalized to 60 Hz, independent of rendering rate/PAL.
     * Require release after firing so a long hold cannot toggle repeatedly. */
    {
        static unsigned int hold_start;
        static bool holding, latched, visible;
        unsigned int now = recomp_clock();
        bool chord = jo_is_pad1_available() &&
            jo_is_pad1_key_pressed(JO_KEY_L) && jo_is_pad1_key_pressed(JO_KEY_R) &&
            !jo_is_pad1_key_pressed(JO_KEY_B);
        if (!chord) holding = latched = false;
        else if (!holding) { holding = true; hold_start = now; }
        else if (!latched && now - hold_start >= 60u) {
            latched = true;
            visible = !visible;
            if (!visible) {
                jo_printf(0, 2, "                                        ");
                jo_printf(0, 3, "                                        ");
                jo_printf(0, 4, "                                        ");
            }
        }
        if (visible) {
            /* SPCTL/PRISA are write-only. Read this SDK's SGL shadow instead:
             * slInitScroll copies its register table to GBR+192;
             * slSpriteColMode accesses SPCTL at GBR+416. These are intended
             * settings, not proof of the hardware's latched register state. */
            jo_printf(0, 2, "SGL SP %04X PR %04X END %X ",
                      *sgl_vdp2_shadow(0xe0),
                      *sgl_vdp2_shadow(0xf0), JO_VDP1_EDSR);
            jo_printf(0, 3, "MS %u M%u G%u L%u OC%u         ",
                      (frame_timer_frame() + frame_timer_cost(FRAME_PHASE_SYNC)) / 1000,
                      frame_timer_cost(FRAME_PHASE_MOVEMENT) / 1000,
                      frame_timer_cost(FRAME_PHASE_SCENE) / 1000,
                      frame_timer_cost(FRAME_PHASE_LINK) / 1000,
                      oot_core_update_us() / 1000);
#ifdef DOSEI_OOT_CORE
            {
                const oot_core_sprite_stats_t *s = oot_core_sprite_stats();
                jo_printf(0, 4, "NPC %u MISS %u POSE %u SLOT %u       ",
                          s->actors, s->missing, s->fallback, s->slots);
            }
#endif
        }
    }
}

static void __attribute__((optimize("Os"))) viewer_draw(void)
{
    if (!scene_ready)
    {
        jo_printf(2, 2, "scene load FAILED");
        return ;
    }

    /* The Y negation that SGL's Y-down projection needs is
    ** baked into the POINT table by the converter, so slScale(1,-1,1) is gone.
    ** eye.y - y is exactly (-y) + eye.y, so this translation is unchanged.
    ** Keeping the matrix free of reflections is what lets the generated face
    ** normals stay meaningful, which Single_Plane culling depends on. */
    /* Source yaw rotates (x,z) to (cx-sz,sx+cz). Use a proper rotation
    ** in baked-Y space; no runtime reflection. The recomp's 60 Hz clock keeps
    ** the original 90 angle units/tick pan independent of render rate. */
    /* The gap since the previous callback returned is Jo's slSynch wait plus
    ** whatever the engine does between callbacks: the part of the frame this
    ** file never sees. Measured first so it covers the real idle. */
    frame_timer_end(FRAME_PHASE_SYNC);
    /* Before any CPU work: was VDP1 still drawing when control came back? */
    frame_timer_sample_vdp1();
    frame_timer_frame_begin();
    frame_timer_begin(FRAME_PHASE_MOVEMENT);
    PS_T0();
    recomp_update();
    PS_ADD(PS_RU);
    if (!recomp_code_fanfare_active() && !kokiri_scene_update()) {
        scene_ready = false;
        jo_printf(2, 2, "room load FAILED");
        return;
    }
    PS_ADD(PS_KS);
#if defined(DOSEI_PERF_PROBE) && DOSEI_PERF_PROBE == 1
    /* Repeatable no-input render baseline. Never enabled in normal builds. */
    recomp_camera.x = -300; recomp_camera.y = 141; recomp_camera.z = -260;
    recomp_yaw = 0; recomp_pitch = 0;
#endif
#if defined(DOSEI_PERF_PROBE) && DOSEI_PERF_PROBE == 5
    /* Warp A/B: one fixed pose facing the long room-0 wall quad
    ** (world corners x -1994..-1634, z -167..1233, y 160..649), so a split-off
    ** and a split-on disc can be compared at the identical camera. Diagnostic
    ** only; never in a normal disc. */
    /* Pin Link where the moving capture showed the offending wall quad
    ** filling the near view and let the real follow camera settle behind him,
    ** so split-off and split-on discs render the same gameplay view. */
    if (recomp_link_active && !recomp_title_is_visible() && !cutscene_is_playing()) {
        recomp_link.x = -43; recomp_link.y = 90; recomp_link.z = -14;
        recomp_link_yaw = 16384;
        /* Astra's settled gap pose, camera included: the follow camera reaches
        ** a different yaw when Link is simply placed here, so the eye is
        ** pinned too rather than approximated. */
        recomp_camera.x = -139; recomp_camera.y = 71; recomp_camera.z = -90;
        recomp_yaw = 9356; recomp_pitch = 0;
    }
#endif
#if defined(DOSEI_PERF_PROBE) && DOSEI_PERF_PROBE == 3
    /* Actor inspection only: original animations, slowly orbiting camera.
     * No controller injection or focus needed. Never in a normal disc. */
    if (recomp_link_active) {
        int32_t sine, cosine;
        unsigned int tick = recomp_clock();
        recomp_yaw = (uint16_t)(32768u + ((tick / 180) % 4) * 8192u);
        kokiri_camera_sincos(recomp_yaw, &sine, &cosine);
        recomp_camera.x = recomp_link.x - (int32_t)(((int64_t)sine * 155) >> 16);
        recomp_camera.z = recomp_link.z - (int32_t)(((int64_t)cosine * 155) >> 16);
        recomp_camera.y = recomp_link.y - RECOMP_LINK_EYE_HEIGHT + 77;
        recomp_pitch = -1820;
        recomp_link_yaw = 0;
        {
            unsigned int gear = (tick / 180) % 4;
            unsigned int clip = !(gear & GP_SWORD) ? LINK_CLIP_IDLE : LINK_CLIP_SLASH;
            if ((gear & GP_SHIELD) && (tick / 90) % 2) clip = LINK_CLIP_GUARD_WAIT;
            gameplay.owned = gameplay.equipped = gear;
            link_anim_pose(clip, (tick / 3) % link_clips[clip].count, 0);
        }
    }
#endif
    frame_timer_end(FRAME_PHASE_MOVEMENT);
    /* A prerendered interior must be drawn at the SAME field of view the
     * backdrop was rendered with, or the 3D and the picture disagree about
     * scale and Link drifts away from the room as he crosses it. The distance
     * is computed offline from the room's own bgCam fov; see
     * tools/build_scene_table.py.
     *
     * Shifted by hand rather than through toFIXED(): that macro multiplies by
     * a double, and on an FPU-less SH-2 a non-constant argument pulls in the
     * software-float helpers (DOSEI-LEGEND-BIBLE.md). The constants below are
     * folded at compile time and stay safe. */
    /* A cutscene shot has its own field of view, baked to a screen distance
     * because the SH-2 has no tangent. Holding the gameplay 240 for every shot
     * framed the whole dream far too wide. */
    slSetScreenDist((FIXED)(recomp_screen_distance() << 16));
    /* Near rejection at screen distance >> level; see KOKIRI_ZDSP_LEVEL. */
    slZdspLevel(KOKIRI_ZDSP_LEVEL);
    music_menu_duck(gameplay_is_paused());
    cdda_service();
    music_service();
#ifdef DOSEI_TEXTURE_PROBE
    texture_probe();
#endif
    /*
    ** Screen-space X flip: the world was rendered MIRRORED until this existed.
    **
    ** The converter bakes vertices as (x, -y, z) so SGL's Y-down projection
    ** comes out upright. Negating one axis flips handedness, and the camera
    ** maths never compensated: working it through, the projection's effective
    ** screen-right is (cos yaw, 0, -sin yaw), which is the exact NEGATION of
    ** the true right-handed right vector (f x up) = (-cos yaw, 0, sin yaw).
    ** So every scene -- Kokiri Forest included -- was a mirror image of the
    ** original, and nothing could reveal it until Link's house arrived with a
    ** prerendered backdrop to compare against. Projecting the house's real
    ** collision onto its own backdrop put the door on the wrong side; with the
    ** sign corrected, the exit polygons land exactly on the doorway.
    **
    ** Applied FIRST so it multiplies in outermost and negates the projected X
    ** of everything at once -- geometry, Link and the billboards -- rather
    ** than needing every world coordinate, facing and model negated
    ** separately. Depth and the yaw sense are untouched, because only the
    ** screen X is wrong.
    **
    ** Y is doubled in the same call for the hi-res variant.
    */
#ifdef DOSEI_HIRES
    slScale(toFIXED(-1), toFIXED(2), toFIXED(1));
#else
    slScale(toFIXED(-1), toFIXED(1), toFIXED(1));
#endif
    slRotZ((ANGLE)(0u - cutscene_camera_roll()));
    slRotX((ANGLE)(0u-recomp_pitch));
    slRotY((ANGLE)(0u-recomp_yaw));
    jo_3d_translate_matrix(-recomp_camera.x, recomp_camera.y, -recomp_camera.z);
    /* 2026-10-09 scheduling. SGL hands a PDATA to the slave only when the
     * slave command queue is empty (sglC08.o); otherwise the master
     * transforms it itself. So the slave runs our jobs while the master does
     * work SGL barely needs the slave for:
     *   frame start (recomp_update): Link's skin, during the game steps;
     *   here: the queued decomp core update (the actors below draw from a
     *   snapshot of its views), then the scene prepare, while the master
     *   submits the small actor meshes and sprites;
     *   kokiri_scene_draw waits for the prepare and an empty queue, so the
     *   slave transforms the forest while the master transforms Link.
     * Joined before text/HUD. Depth sorting, not submission order, decides
     * occlusion. */
    if (kokiri_parallel_prepare) {
        oot_core_async_kick();
        kokiri_frame_master_prepare(!kokiri_scene_backdrop_active() && !cutscene_hides_scene());
    } else if (kokiri_prep_first) {   /* Debug L+R+Left cycles M/P/C */
        kokiri_frame_slave_kick(!kokiri_scene_backdrop_active() && !cutscene_hides_scene());
        oot_core_async_kick();
    } else {
        oot_core_async_kick();
        kokiri_frame_slave_kick(!kokiri_scene_backdrop_active() && !cutscene_hides_scene());
    }
#if !defined(DOSEI_PERF_PROBE) || DOSEI_PERF_PROBE != 3
    /* Link has priority over optional actors in SGL's finite work area.
     * Depth sorting still controls occlusion, independent of submission order. */
    /* The opening cutscenes play in scenes the gameplay actors do not belong
     * to, so they suppress them. An in-scene cutscene is the opposite case:
     * it plays inside a live room, and the grass, NPCs and items standing in
     * that room must keep being drawn or the shot cuts to an empty forest. */
    if (!kokiri_scene_backdrop_active() && !cutscene_hides_scene() &&
        (!cutscene_is_playing() || cutscene_is_in_scene()) &&
        (save_state.scene_id == SAVE_SCENE_KOKIRI_FOREST || oot_core_owns_kokiri_props())) {
        PS_RESET();
        /* With the decomp playing, these draw its En_Kusa/En_Item00 in any scene. */
        kokiri_grass_draw();
        kokiri_rupees_draw(recomp_world_clock());
        if (save_state.scene_id == SAVE_SCENE_KOKIRI_FOREST) kokiri_boulder_draw();
        PS_ADD(PS_DGR);
    }
    if (recomp_link_active && !recomp_title_is_visible() &&
          (!cutscene_is_playing() || cutscene_is_in_scene())) {
        unsigned int da0 = frame_timer_ticks();
        PS_RESET();
        kokiri_nut_draw();
        kokiri_babas_draw();
        PS_ADD(PS_DNB);
        npc_draw(recomp_world_clock());
        PS_ADD(PS_DNPC);
        story_route_draw(recomp_world_clock());
        kokiri_items_draw(recomp_world_clock());
        PS_RESET();
        kokiri_fairies_draw(recomp_world_clock());
        PS_ADD(PS_DFY);
        perf_sub[PS_DAC] += frame_timer_ticks_to_us(ps_t0 - da0);
    }
#endif
    frame_timer_begin(FRAME_PHASE_SCENE);
#if !defined(DOSEI_PERF_PROBE) || DOSEI_PERF_PROBE != 3
    /* A prerendered interior IS its backdrop: it has no geometry, and the
     * resident VDP1 bank still holds whichever forest room was loaded last, so
     * drawing the world here would paint the forest over the room.
     *
     * The forest's actors go with it. They filter by ROOM, and an interior is
     * a different SCENE whose room 0 would otherwise match -- a Kokiri fairy
     * would bob around inside Link's house. */
    /* A cutscene's screen fill covers the world completely at full strength,
     * so there is nothing to submit -- and while a cutscene's scene is one we
     * have not extracted, drawing would show whichever scene is still resident
     * instead. Either way the polygons are skipped rather than drawn and
     * hidden. */
    if (!kokiri_scene_backdrop_active() && !cutscene_hides_scene()) {
        kokiri_scene_draw();
    }
    /* Equipment now belongs to the VDP2 pause window. */
#endif
    frame_timer_end(FRAME_PHASE_SCENE);
    /* Link is submitted after the forest so the per-frame counters, which
    ** kokiri_scene_draw() resets, cover both lists. His model origin is at his
    ** feet, EYE_HEIGHT below the collision position. */
    if (cutscene_is_playing()) {
        unsigned int channel;

        cutscene_actors_prepare();
        if (cutscene_id() == CUTSCENE_NAVI_FLY && !cutscene_hides_scene())
            npc_draw_navi(cutscene_frame());
        if (cutscene_id() == CUTSCENE_NIGHTMARE && !cutscene_hides_scene()) {
            int32_t sine, cosine;
            int y, z;
            kokiri_camera_sincos((uint16_t)cutscene_bridge_angle(), &sine, &cosine);
            y = -10 + (int)(((int64_t)10 * cosine - (int64_t)400 * sine) >> 16);
            z = 670 + (int)(((int64_t)10 * sine + (int64_t)400 * cosine) >> 16);
            cutscene_actor_draw(CUTSCENE_ACTOR_BRIDGE, 0, -10, 670, 0);
            cutscene_actor_draw(CUTSCENE_ACTOR_CHAINS, 158, y, z, 0);
            cutscene_actor_draw(CUTSCENE_ACTOR_CHAINS, -158, y, z, 0);
            cutscene_gate_fire_draw();
        }
        /* All five En_Viewer actors share their channel's world origin.
         * Riding offsets belong to the original animation, not the mount. */
        for (channel = 0; channel < 2; ++channel) {
            int32_t x, y, z;
            if (!cutscene_actor_channel_visible(channel) || cutscene_hides_scene())
                continue;
            x = cutscene_actor_channel_x(channel);
            y = cutscene_actor_channel_y(channel);
            z = cutscene_actor_channel_z(channel);
            cutscene_actor_draw(channel == 0 ? CUTSCENE_ACTOR_HORSE_ZELDA
                                            : CUTSCENE_ACTOR_HORSE_GANON,
                                x, y, z, 0);
            if (channel == 0) {
                cutscene_actor_draw(CUTSCENE_ACTOR_ZELDA, x, y, z, 0);
                cutscene_actor_draw(CUTSCENE_ACTOR_IMPA, x, y, z, 0);
            } else {
                cutscene_actor_draw(CUTSCENE_ACTOR_GANON, x, y - 6, z, 0);
            }
        }
    }

    if (!recomp_slingshot_aiming()) link_anim_first_person(false);
    if (cutscene_is_playing()) {
        /* A cutscene places and poses Link itself, from its own player cues:
         * asleep in bed for the narration, sitting up when Navi wakes him.
         * Shots with no cue do not contain him, so nothing is drawn. */
        if (cutscene_link_visible() && !cutscene_hides_scene()) {
            frame_timer_begin(FRAME_PHASE_LINK);
            link_anim_pose(cutscene_link_clip(), cutscene_link_frame(), cutscene_link_fraction());
            kokiri_link_draw(cutscene_link_x(), cutscene_link_y(),
                             cutscene_link_z(), cutscene_link_yaw());
            frame_timer_end(FRAME_PHASE_LINK);
        }
    } else if (recomp_link_active && !recomp_title_is_visible() && !recomp_first_person() &&
               !recomp_shop_browsing()
#ifdef PLAYER_SOURCE
               && !(oot_core_player_valid && oot_core_player.hidden)
#endif
               ) {
        frame_timer_begin(FRAME_PHASE_LINK);
        /* shape.yOffset: a ledge step-up draws him from where he stood
         * while the actor is already on the ledge. */
        if(recomp_chest_opening()) {
            link_anim_pose(LINK_CLIP_CHEST_OPEN,recomp_chest_frame(),0);
        } else if (gameplay.get_item) {
            unsigned int frame = gameplay.get_item_age * 2u / 3u;
            if (frame >= LINK_FRAMES_GET_ITEM) frame = LINK_FRAMES_GET_ITEM - 1;
            link_anim_pose(LINK_CLIP_GET_ITEM, frame, 0);
        }
        kokiri_link_draw(recomp_link.x, recomp_link.y - RECOMP_LINK_EYE_HEIGHT +
                         link_anim_y_offset_q8() / 256,
                         recomp_link.z, recomp_link_yaw);
        link_anim_trail_draw();
        frame_timer_end(FRAME_PHASE_LINK);
        /* Link's own fairy, drawn with him and only with him: the title
         * shot and the file select are not gameplay. */
#ifdef PLAYER_SOURCE
        if (oot_core_player_valid && oot_core_player.navi_shown)
            kokiri_navi_draw_colour(oot_core_player.navi[0], oot_core_player.navi[1],
                                    oot_core_player.navi[2], oot_core_player.navi_colour, false);
#else
        if (navi_active())
            kokiri_navi_draw(navi_x(), navi_y(), navi_z());
#endif
    }
    if (!cutscene_is_playing() && (!recomp_link_active || recomp_title_is_visible()))
        action_audio_navi_flight(0, false);
    if (cutscene_is_playing() && !cutscene_hides_scene())
        kokiri_cutscene_effects_draw();
    if(!cutscene_hides_scene())emerald_story_draw();
    /* Use the same joined snapshot/FOV as this frame's world before join
     * publishes the next source camera sample. */
    oot_core_cutscene_letterbox_draw();
    oot_core_async_join();
    kokiri_shadow_resolve();
    rejected_total += kokiri_scene_rejected();
    PS_RESET();
    cutscene_fade();
    dialogue_box(); /* Clear outgoing dialogue before cutscene writes its rows. */
    cutscene_text();
    { static bool field_card;
      bool show=cutscene_is_playing() && cutscene_id()==CUTSCENE_FIELD_INTRO && cutscene_frame()>=40 && cutscene_frame()<160;
      if(show)jo_printf(13,19,"HYRULE FIELD");
      else if(field_card)jo_printf(13,19,"            ");
      field_card=show;
    }
    /* Persistent development readout, independent of auto-start probes. */
    {
        static bool debug_visible;
        if (cutscene_is_playing()) {
            jo_printf(0, 0, "SCENE %d FRAME %d FADE %d   ",
                      cutscene_id(), cutscene_frame(), cutscene_fade_alpha());
            jo_printf(0, 1, "ACT %d X %d Z %d REJ %d   ", cutscene_actors_ready(),
                      cutscene_actor_channel_x(1), cutscene_actor_channel_z(1),
                      kokiri_scene_rejected());
#ifdef DOSEI_CUTSCENE_PROBE
            jo_printf(0, 2, "MUS %d BUSY %d FAIL %d T %d   ",
                      music_current() == &music_bank_nightmare,
                      music_busy(), music_failed(), (int)music_ticks());
#ifdef DOSEI_CUTSCENE_PROBE_FRAME
            jo_printf(0, 3, "CAMERA TEST HOLD AT %d", DOSEI_CUTSCENE_PROBE_FRAME);
#elif defined(DOSEI_CUTSCENE_PROBE_AUTO)
            jo_printf(0, 3, "AUTOMATIC OPENING TEST");
#endif
#endif
            debug_visible = true;
        } else if (debug_visible) {
            jo_printf(0, 0, "                                        ");
            jo_printf(0, 1, "                                        ");
            jo_printf(0, 2, "                                        ");
            debug_visible = false;
        }
    }
    inventory_menu();
#ifdef DOSEI_OOT_CORE
    {
        static bool ocarina_hint;
        bool active=(oot_core_ocarina_state()&1u) && !gameplay.paused && !recomp_title_is_visible();
        if (active && !ocarina_hint) jo_printf(4,27,"A + D-Pad: Notes   B: Stop");
        else if (!active && ocarina_hint) jo_printf(4,27,"                          ");
        ocarina_hint=active;
    }
#endif
    play_test_room();
    oot_core_timer_draw(!gameplay_is_paused() && !recomp_title_is_visible() &&
                        !recomp_file_select_is_visible() && !cutscene_is_playing());
    game_over_screen();
    file_select_screen();
    if (!gameplay_blocks_world() && !cutscene_is_playing()) viewer_hud();
    {
        static bool skip_was_visible;
        bool visible = recomp_skip_prompt();
        if (visible)
            jo_printf(6, 3, "Skip? Press %s Again", ui_button_label(UI_KEY_START, false));
        else if (skip_was_visible)
            jo_printf(6, 3, "                       ");
        skip_was_visible = visible;
    }
    if (!recomp_title_is_visible() && !recomp_file_select_is_visible() &&
        !cutscene_is_playing())
    {
        if (!gameplay_blocks_world() && !gameplay.dead) {
            int32_t x,y; bool locked; unsigned kind;
            if (recomp_slingshot_aiming()) {
                /* VDP2 text-layer crosshair: cell (20,15) covers pixels
                 * 160-167 x 120-127, glyph centre ~3 px off screen centre. */
                jo_printf(20, 15, "+");
                aim_dot_shown = true;
            } else if (recomp_target_marker(&x,&y,&locked,&kind))
                kokiri_lock_reticle_draw(x,y,kind);
        }
        if (aim_dot_shown && !recomp_slingshot_aiming()) {
            jo_printf(20, 15, " ");
            aim_dot_shown = false;
        }
        kokiri_rupee_hud_draw();
        minimap_draw(recomp_link.x, recomp_link.z, recomp_link_yaw);
    }
    PS_ADD(PS_DUI);
    diagnostic_overlay();
    perf_sub_latch();
    frame_timer_frame_end();
    frame_timer_begin(FRAME_PHASE_SYNC);
}

/*
** The cutscene's screen fill, as a VDP2 colour offset.
**
** OoT fills the screen with a coloured quad and ramps its alpha
** (z_demo.c:1550-1574). VDP2 offers the same effect far more cheaply: a
** black line-colour screen supplies the second colour for VDP2 alpha blending.
** Subtracting alpha as a colour offset clips dark pixels to black instead of
** fading them (60% of the house panorama was clipped at alpha 100).
**
** Applied to the scene layers and the sprites, never to NBG0: the text layer
** has to stay legible over a darkened scene, and the narration is drawn while
** the fill is at full strength.
**
** A fully opaque fill is handled earlier by skipping the scene entirely, so
** this only has to cover the partial values.
*/
static void __attribute__((optimize("Os"))) cutscene_fade(void)
{
    static int last_key = -1;
    bool hidden = cutscene_hides_scene();
    unsigned int alpha = cutscene_fade_alpha();
    int flash = cutscene_lightning();
    if (!cutscene_is_playing() && player_items_flash()) flash = (int)player_items_flash() * 255 / 6;
    bool black = cutscene_fade_colour() == CUTSCENE_FADE_BLACK;
    int16_t tint[3];
    bool tinted = oot_core_hit_tint(tint);
    int key = (int)alpha | (flash << 8) | (black << 16) | (hidden << 17) |
              (tinted ? ((tint[0] & 0xFF) << 18 ^ (tint[1] & 0xFF) << 10 ^ (tint[2] & 0xFF) << 24) : 0);
    Sint16 level = (Sint16)(flash + (black ? 0 : (int)alpha));
    if (level > 255) level = 255;
    if (key == last_key) return;
    last_key = key;
    if (black && alpha && !hidden) {
        unsigned rate = alpha >> 3; /* VDP2's 32-step second-image weight. */
        /* Reserved word beyond the 512-entry back-colour table; CRAM 2047
         * is outside the font/HUD/marker palettes. slLine1ColSet takes a
         * VRAM-relative byte offset, unlike slLineColTable. */
        ((volatile unsigned short *)JO_VDP2_CRAM)[2047] = 0;
        slLine1ColSet((void *)0x7f400u, 2047);
        slLineColDisp(NBG1ON | RBG0ON | SPRON);
        slColRateNbg1(rate); slColRateRbg0(rate); slColRateSpr0(rate);
        slSpriteCCalcCond(CC_pr_CN); slSpriteCCalcNum(7);
        slColorCalc(CC_RATE | CC_TOP | NBG1ON | RBG0ON | SPRON);
    } else {
        slLineColDisp(0);
        slColorCalc(0);
    }
    if (!level) {
        if (tinted) {
            /* Arrow*_Draw hit fill: offset A on the 3D scene, HUD untouched. */
            slColOffsetA(tint[0], tint[1], tint[2]);
            slColOffsetBUse(0);
            slColOffsetOn(NBG1ON | RBG0ON | SPRON | BACKON);
            return;
        }
        slColOffsetOff(NBG1ON | RBG0ON | SPRON | BACKON);
        return;
    }
    slColOffsetB(level, level, level);
    slColOffsetBUse(NBG1ON | RBG0ON | SPRON | BACKON);
    slColOffsetOn(NBG1ON | RBG0ON | SPRON | BACKON);
    /* At full cover the world is not submitted. The only sprites left are
     * the text panel and its notice; keep them visible during narration. */
    if (hidden) slColOffsetOff(SPRON);
}

/*
** Cutscene text: the opening's narration and speeches.
**
** Separate from dialogue_box() below, which draws NPC conversations. This one
** has no speaker name and no "A: next" footer on a timed page, it is centred
** or placed per the original's TEXTBOX_POS_*, and a line is drawn as a series
** of coloured runs -- COLOR() changes colour partway through a line, so
** "I'm Navi the fairy!" is one line in three colours.
**
** Colour works through SGL's slCurColor, which Jo's jo_printf_with_color sets:
** the index is written into each character cell's pattern name as the cell is
** printed, so it stays per character rather than recolouring the layer.
*/
static unsigned int cutscene_text_colour(unsigned int colour)
{
    switch (colour) {
        /* Blue source emphasis becomes readable yellow on the dark panel. */
        case CUTSCENE_COLOUR_BLUE: return JO_COLOR_INDEX_Yellow;
        case CUTSCENE_COLOUR_RED:  return JO_COLOR_INDEX_Red;
        default:                   return JO_COLOR_INDEX_White;
    }
}

/*
** The box the text sits in.
**
** The panel itself is OoT's own gDefaultMessageBackgroundTex, drawn on VDP1
** behind the text; the VDP2 text layer sits above the sprite layer, so the
** words land on it without any ordering work. These constants only say where
** it goes, in character cells, which the box draw converts to pixels.
**
** A dithered fill of '#' glyphs on the text layer was tried first, because
** that layer has no solid cell to fill a rectangle with. It looked like a row
** of hashes, which is what it was.
*/
/* One padding row above and below the text, and the box only as tall as the
** page needs. Two rows each way made it swallow half the screen. */
#define CUTSCENE_BOX_PAD    1
#define CUTSCENE_BOX_LEFT   0
#define CUTSCENE_BOX_RIGHT  39
#define CUTSCENE_BOX_WIDTH  (CUTSCENE_BOX_RIGHT - CUTSCENE_BOX_LEFT + 1)

/* Row the box starts on, for a message of `lines` lines.
**
** Bottom is the default and the common case, and the box grows upwards from a
** fixed bottom edge so a three-line page and a one-line page share an edge
** instead of drifting. Only a message the original places elsewhere moves. */
static int          cutscene_box_top(unsigned int lines)
{
    int height = (int)lines + CUTSCENE_BOX_PAD * 2;

    switch (message_position()) {
        case CUTSCENE_POS_TOP:    return 2;
        case CUTSCENE_POS_MIDDLE: return 13 - height / 2;
        default:                  return 25 - height;
    }
}

/* Wipe a box drawn earlier. VDP2 retains text, so every row it covered has to
** be cleared or the last page stays on screen behind the next one. */
static void         cutscene_box_clear(int top, int rows)
{
    int row;

    for (row = 0; row < rows; ++row)
        jo_printf(0, top + row, "%-40s", "");
}

static void __attribute__((optimize("Os"))) cutscene_text(void)
{
    static bool     was_active;
    static int      last_top, last_rows;
    static uint32_t last_text_hash;
    unsigned int    line, run, lines;
    int             top, rows, text_row, prompt_row;

    if (!message_is_active()) {
        if (was_active) {
            cutscene_box_clear(last_top, last_rows);
            jo_set_printf_palette_color(JO_COLOR_INDEX_Blue, JO_COLOR_Blue);
            was_active = false;
            last_text_hash = 0;
        }
        return;
    }

    lines = message_lines();
    top = cutscene_box_top(lines);
    rows = (int)lines + CUTSCENE_BOX_PAD * 2;
    text_row = top + 1;
    prompt_row = top + rows - 1;

    /* A box that moved or changed size must wipe where it was first. */
    if (was_active && (top != last_top || rows != last_rows))
        cutscene_box_clear(last_top, last_rows);
    if (!was_active)
        jo_set_printf_palette_color(JO_COLOR_INDEX_Blue, C_RGB(18, 28, 31));
    was_active = true;
    last_top = top;
    last_rows = rows;

    /* OoT's own message panel, on VDP1 behind the text. A character cell is
    ** 8x8, so the box's rows and columns convert straight to pixels, and the
    ** sprite is centred on that rectangle. */
    kokiri_message_box_draw(
        (CUTSCENE_BOX_LEFT * 8 + (CUTSCENE_BOX_RIGHT + 1) * 8) / 2,
        (top * 8 + (top + rows) * 8) / 2,
        CUTSCENE_BOX_WIDTH * 8, rows * 8);

    /* Retained VDP2 rows: avoid blanking/repainting every active scanout.
     * The panel still submits each frame, but unchanged text stays in place. */
    uint32_t hash = 2166136261u;
    hash = (hash ^ message_state.message) * 16777619u;
    hash = (hash ^ message_state.page) * 16777619u;
    hash = (hash ^ message_state.revealed) * 16777619u;
    hash = (hash ^ message_choice()) * 16777619u;
    hash = (hash ^ ui_text_revision()) * 16777619u;
    bool repaint = hash != last_text_hash;
    last_text_hash = hash;

    for (line = 0; repaint && line < lines; ++line) {
        /* The original's SHIFT, which is what centres the narration, measured
        ** from inside the box rather than from the screen edge. */
        int column = CUTSCENE_BOX_LEFT + 1 + (int)message_line_indent(line);

        /* Wipe the row first. VDP2 retains text, and a page shorter than the
        ** one before it would otherwise leave the tail of the old line on
        ** screen -- which is where "descendingof" came from. */
        jo_printf(0, text_row + (int)line, "%-40s", "");

        for (run = 0; run < message_line_runs(line); ++run) {
            unsigned int shown = message_run_visible(line, run);
            const char  *text = message_run_text(line, run);
            unsigned int length = 0;

            while (text[length])
                ++length;
            if (shown > length)
                shown = length;
            if (shown)
                /* Typed out a character at a time, so only the part of the
                ** run that has appeared so far is drawn. */
            {
                jo_printf_with_color(column, text_row + (int)line,
                                     cutscene_text_colour(
                                         message_run_colour(line, run)),
                                     "%.*s", (int)shown, text);
                if (cutscene_text_colour(message_run_colour(line, run)) != JO_COLOR_INDEX_White)
                    recomp_text_embolden(column, text_row + (int)line, text, shown);
            }
            column += (int)length;
            if (shown < length)
                break;          /* nothing later on this line is visible yet */
        }
    }

    /* The prompt appears only when the page is genuinely waiting for it.
    ** Anything else invites a press that would be ignored. */
    /* OoT's own prompt, on the box's bottom edge: the continue triangle, or
    ** the end square on the last page. Drawn only when the page is genuinely
    ** waiting -- never while it is still typing itself out. */
    if (message_choices())
        jo_printf(1,text_row+(int)lines-(int)message_choices()+(int)message_choice(),">");
    if (message_waits_for_button())
        kokiri_message_mark_draw(160, prompt_row * 8 + 4,
                                 message_is_last_page());
    /* Restore the default, or every other jo_printf on the screen inherits
    ** whichever colour was used last. */
    jo_set_printf_color_index(JO_COLOR_INDEX_White);
}

/*
** Dialogue text box. Context action graphics live on the NBG2 button HUD.
**
** Drawn on the clean player disc as well as the diagnostic one -- this is
** gameplay, not debug text -- so it sits outside viewer_hud()'s early returns.
** VDP2 retains what is printed, so both the box and the prompt clear their own
** rows on the frame they stop being shown, or the last page stays on screen.
*/
#define DIALOGUE_ROW    20
#define DIALOGUE_BODY_ROW (DIALOGUE_ROW + 2) /* Name extends 4 pixels into the intervening row. */
#define DIALOGUE_ROWS   (DIALOGUE_MAX_LINES + 3)
#define DIALOGUE_PAD_PX 4
#define DIALOGUE_NAME_OFFSET_PX 4

/* All dialogue uses the retained SGL font. Thicken ASCII once at boot;
 * palette variants share these glyphs, and pause restores the same font VRAM. */
/* Human rule 2026-10-08: only emphasised (coloured) text is bold. Regular
 * glyphs stay as SGL loaded them; widened copies of glyphs 33-126 sit in
 * order in free text-layer cells after the font (same 32 KB B1 window, 10-bit
 * cell numbers, two units per 256-colour cell), at bold_base + 2*(ch - 33).
 * recomp_text_embolden swaps a coloured run's map entries; 0 = no bold. */
static uint16_t bold_base;
static void __attribute__((optimize("Os"))) dialogue_font_init(void)
{
    unsigned ch, y, x, top = 0;
    uint16_t regular[127];
    for (ch=33;ch<127;++ch) {
        char text[2]={(char)ch,0};
        jo_printf(0,31,"%s",text);
        regular[ch] = *(volatile uint16_t *)slLocate(0,31) & 0x3ffu;
        if (regular[ch] > top) top = regular[ch];
    }
    jo_printf(0,31," ");
    top = (top + 2u) & ~1u;
    if (top + 2u * (127u - 33u) > 1024u) return;   /* no room: emphasis stays regular */
    for (ch=33;ch<127;++ch) {
        volatile uint8_t *from = (volatile uint8_t *)0x25E60000u + regular[ch]*32u;
        volatile uint8_t *cell = (volatile uint8_t *)0x25E60000u + (top + 2u*(ch-33u))*32u;
        for (x = 0; x < 64; ++x) cell[x] = from[x];
        for (y=0;y<8;++y)
            for (x=7;x>0;--x)
                if (!cell[y*8+x]) cell[y*8+x]=cell[y*8+x-1];
    }
    bold_base = (uint16_t)top;
}

void __attribute__((optimize("Os"))) recomp_text_embolden(int x, int y, const char *text, unsigned length)
{
    volatile uint16_t *map = (volatile uint16_t *)slLocate(x, y);
    unsigned i;
    for (i = 0; bold_base && i < length && text[i]; ++i) {
        unsigned ch = (unsigned char)text[i];
        if (ch > 32 && ch < 127) map[i] = (uint16_t)((map[i] & ~0x3ffu) | (bold_base + 2u*(ch-33u)));
    }
}

/* Debug Play Test (Level Select): current source room on the bottom row.
 * Pause owns the text layer; its close restores these rows. */
static void __attribute__((optimize("Os"))) play_test_room(void)
{
    static int room_shown = -1;
    int room = recomp_play_test() && game_mode() == GAME_MODE_PLAY &&
               !recomp_title_is_visible() && !cutscene_is_playing()
               ? (int)kokiri_scene_room() : -1;
    if (gameplay_is_paused() || room == room_shown) return;
    if (room >= 0) jo_printf(1, 29, "Room %-3d", room);
    else jo_printf(1, 29, "        ");
    room_shown = room;
}


static uint32_t dialogue_row_hash(const char *text, unsigned marker)
{
    uint32_t hash = 2166136261u ^ marker;
    if (text) while (*text) hash = (hash ^ (unsigned char)*text++) * 16777619u;
    return hash;
}

static void __attribute__((optimize("Os"))) dialogue_box(void)
{
    static bool was_talking;
    static uint32_t row_hash[DIALOGUE_MAX_LINES + 1];
    unsigned int i;
    bool repaint = !was_talking;

    /* Title flythrough and the file select have no interaction. Clear retained
     * VDP2 text too, so returning here cannot leave an old prompt or page on
     * screen -- and so a stale prompt cannot print over the file list. */
    if (gameplay_is_paused() || recomp_title_is_visible() || recomp_file_select_is_visible() ||
        cutscene_is_playing() || recomp_chest_opening()) {
        if (was_talking) {
            for (i = 0; i < DIALOGUE_ROWS; ++i)
                jo_printf(0, DIALOGUE_ROW + i, "%-40s", "");
        }
        was_talking = false;
        return;
    }
    if (oot_core_message_box()) {
        was_talking = false;   /* the decomp box owns the rows now */
        return;
    }
    if (oot_core_npc_text(0)) { was_talking=false; return; }
    if (!gameplay_is_talking()) {
        if (was_talking) {
            for (i = 0; i < DIALOGUE_ROWS; ++i)
                jo_printf(0, DIALOGUE_ROW + i, "%-40s", "");
            was_talking = false;
        }
        /* Context actions now live in the VDP2 gameplay button HUD. */
        return;
    }
    was_talking = true;
    /* VDP2 retains rows. Do not blank a visible page before repainting it:
     * scanout can expose the empty lower rows. Padded line writes below
     * replace previous content; close/ownership transitions clear once. */
    kokiri_message_box_draw(160, DIALOGUE_ROW * 8 + DIALOGUE_ROWS * 4 + DIALOGUE_NAME_OFFSET_PX / 2,
                            320, DIALOGUE_ROWS * 8 + DIALOGUE_PAD_PX * 2 - DIALOGUE_NAME_OFFSET_PX);
    if (repaint) jo_printf(0, DIALOGUE_ROW + 1, "%-40s", "");
    const char *speaker = gameplay_speaker_name();
    uint32_t hash = dialogue_row_hash(speaker, 0);
    if (repaint || row_hash[0] != hash) {
        jo_printf(1, DIALOGUE_ROW, "%-38s", speaker);
        row_hash[0] = hash;
    }
    {
        /* TWO_CHOICE rows (the shop's Buy / Don't buy) carry a cursor. */
        unsigned int lines = gameplay_page_lines();
        unsigned int choices = gameplay_choice_lines();
        for (i = 0; i < DIALOGUE_MAX_LINES; ++i) {
            const char *line = i < lines ? gameplay_page_line(i) : "";
            char cursor = choices && i < lines && i >= lines - choices &&
                i - (lines - choices) == gameplay.choice ? '>' : ' ';
            hash = dialogue_row_hash(line, choices ? cursor : 0);
            if (!repaint && row_hash[i + 1] == hash) continue;
            row_hash[i + 1] = hash;
            if (choices && i < lines && i >= lines - choices)
                jo_printf(1, DIALOGUE_BODY_ROW + i, "%c %-36s",
                          i - (lines - choices) == gameplay.choice ? '>' : ' ',
                          line ? line : "");
            else
                jo_printf(1, DIALOGUE_BODY_ROW + i, "%-38s", line ? line : "");
        }
        if (!choices) {
            bool last = !gameplay_page_more() && (gameplay.rule < 0 ||
                gameplay.page + 1u >= dialogue_rules[gameplay.rule].pages);
            kokiri_message_mark_draw(160,
                (DIALOGUE_BODY_ROW + DIALOGUE_MAX_LINES) * 8 + 4, last);
        }
    }
}

/*
** Pause inventory. Player-facing, so it draws on the clean disc too.
**
** VDP2 retains printed text, so the whole panel is cleared on the frame it
** closes -- otherwise the menu stays burned over the world. Every slot is
** listed whether owned or not: a missing item has to be readable, and say
** where to get it, or the player has no way to learn the sword exists.
*/
#define MENU_ROW    4
/* Rows the panel occupies and therefore must clear on close. Three item rows
** now, each with its own use line, so this grew by two with the save row. */
#define MENU_ROWS   23

/* Kaleido's Game Over prompts, as VDP2 text (menus are VDP2, never VDP1
** sprites). The source's rotating prompt windows and fades are not drawn. */
static void __attribute__((optimize("Os"))) game_over_screen(void)
{
    static game_over_state_t shown = GAME_OVER_OFF;
    game_over_state_t st = game_over_state();
    bool yes = game_over_cursor() == 0;
    if (st != shown) {
        jo_clear_screen();
        shown = st;
    }
    switch (st) {
    case GAME_OVER_MESSAGE:
        jo_printf(15, 13, "GAME OVER");
        break;
    case GAME_OVER_SAVE:
    case GAME_OVER_SAVING:
        jo_printf(15, 10, "GAME OVER");
        jo_printf(10, 13, "Save game?");
        jo_printf(12, 15, "%c Yes    %c No", yes ? '>' : ' ', yes ? ' ' : '>');
        if (game_over_save_failed())
            jo_printf(10, 18, "SAVE FAILED - TRY AGAIN");
        break;
    case GAME_OVER_SAVED:
        jo_printf(15, 10, "GAME OVER");
        jo_printf(10, 13, "Game saved.");
        break;
    case GAME_OVER_CONTINUE:
        jo_printf(15, 10, "GAME OVER");
        jo_printf(10, 13, "Continue playing?");
        jo_printf(12, 15, "%c Yes    %c No", yes ? '>' : ' ', yes ? ' ' : '>');
        break;
    default:
        break;
    }
}

static void __attribute__((optimize("Os"))) inventory_menu(void)
{
    static bool was_paused;
    static int last_window = -1;
    const pause_window_state_t *state = &gameplay.pause_window;
    bool paused = gameplay_is_paused();
    if (paused != was_paused) {
        if (!paused) jo_clear_screen();
        was_paused = paused;
    }
    if (!paused) { last_window = -1; return; }
    {
        int window = state->system_confirm ? 10 + state->system_confirm :
            state->save_prompt ? PAUSE_SAVE : state->page;
        if (window != last_window) last_window = window;
    }
    if (pause_windows_failed()) { jo_printf(5,12,"PAUSE ART LOAD FAILED"); return; }
    if (!pause_windows_text_ready()) return;
    if (!state->save_prompt) {
        bool analog = jo_is_pad1_available() && jo_is_input_analog(0);
        pause_windows_printf(2, 14, "%-2s", ui_button_label(UI_KEY_L, analog));
        pause_windows_printf(35, 14, "%-2s", ui_button_label(UI_KEY_R, analog));
    }
    if (state->system_confirm || (state->page == PAUSE_EXTRA && !state->save_prompt)) {
        const char *pad;
        switch (jo_get_input_type(0)) {
        case JoNotConnectedGamepad: pad = "Not connected"; break;
        case JoRegularGamepad: pad = "Digital pad"; break;
        case JoNightsPad: pad = "3D pad (analog)"; break;
        default: pad = "Unsupported device"; break;
        }
        bool analog = jo_is_pad1_available() && jo_is_input_analog(0);
        pause_windows_printf(16, 6, "SYSTEM");
        if (state->system_confirm) {
            pause_windows_printf(8, 10, "%-25s", state->system_confirm == 1 ? "Open load menu?" : "Return to title?");
            pause_windows_printf(6, 13, "Unsaved progress will be lost.");
            pause_windows_printf(12, 16, "%c YES     %c NO", state->save_choice == 0 ? '>' : ' ',
                      state->save_choice == 1 ? '>' : ' ');
        } else {
            static const char *const options[3] = {"Save game", "Load game", "Return to title"};
            unsigned i, selected = state->cursor[PAUSE_EXTRA];
            const char *jump = ui_button_label(ui_jump_key(), analog);
            int report = save_device_preferences_report();
            for (i = 0; i < 3; ++i)
                pause_windows_printf(8, 8 + 2 * i, "%c %-25s", selected == i ? '>' : ' ', options[i]);
            pause_windows_printf(8, 14, "%c Labels: %-17s", selected == 3 ? '>' : ' ', ui_label_name());
            pause_windows_printf(8, 16, "%c Jump: %-10s (%c)  ", selected == 4 ? '>' : ' ',
                      *jump ? jump : "Unmapped", "YABXCZLR"[ui_jump_binding()]);
            pause_windows_printf(8, 18, "%c Core: %-18s", selected == 5 ? '>' : ' ',
                      ui_core_responsive() ? "Responsive" : "Fast (2 CPUs)");
            pause_windows_printf(8, 20, "%c Reset defaults          ", selected == 6 ? '>' : ' ');
            pause_windows_printf(7, 22, "Pad 1: %-23s", pad);
            pause_windows_printf(7, 24, "%s: OK  %s: Close     ",
                      ui_button_label(UI_KEY_A, analog), ui_button_label(UI_KEY_START, analog));
            pause_windows_printf(8, 25, "%-24s", minimap_enemy_dots() ? "Enemy map: ON" : "");
            pause_windows_printf(7, 27, "%-27s", report == 0 ? "Settings NOT saved" :
                      selected == 4 ? "Replaces old button action" :
                      selected == 5 ? (ui_core_responsive() ? "Less lag, lower FPS" : "More FPS, 1 frame lag") :
                      report == 1 ? "Settings saved" : "");
        }
        return;
    }
    {
        const pause_window_state_t *p = &gameplay.pause_window;
        const char *name = "";
        bool floor_hint = p->page == PAUSE_MAP && !p->save_prompt &&
            (save_state.scene_id == SAVE_SCENE_DEKU_TREE || save_state.scene_id == SAVE_SCENE_DEKU_TREE_BOSS);
        if (!p->save_prompt) name=pause_windows_selection_name();
        /* Centre in the baked info panel: y 196..219, map page 204..227. */
        pause_windows_print_centered(p->page == PAUSE_MAP ? (floor_hint ? 206 : 212) : 204, name);
        if (floor_hint) {
            pause_windows_printf(4,27,"[%s]: Floor  Blue: visited",ui_button_label(UI_KEY_DPAD,false));
        }
        if (p->page == PAUSE_ITEMS && !p->save_prompt) {
            if (save_state.stick_owned) pause_windows_printf(9, 10, "%2u", (unsigned)save_state.stick_ammo);
            if (save_state.nut_owned) pause_windows_printf(13, 10, "%2u", (unsigned)save_state.nut_ammo);
            if (save_state.slingshot) pause_windows_printf(9, 14, "%2u", (unsigned)save_state.ammo_seeds);
            if (save_inventory_item(2)!=255) pause_windows_printf(17,10,"%2u",(unsigned)save_state.source_ammo[2]);
            if (save_inventory_item(3)!=255) pause_windows_printf(21,10,"%2u",(unsigned)save_state.source_ammo[3]);
            if (save_inventory_item(8)!=255) pause_windows_printf(17,14,"%2u",(unsigned)save_state.source_ammo[8]);
            if (save_inventory_item(14)!=255) pause_windows_printf(17,18,"%2u",(unsigned)save_state.source_ammo[14]);
            pause_windows_printf(5, 27, "Hold [%s]+[%s]: Assign", ui_assign_modifier_label(),
                                 ui_button_label(UI_KEY_DPAD, false));
        }
        if (p->page==PAUSE_QUEST && !p->save_prompt)
            pause_windows_printf(10,12,"%3u",save_skull_count());
    }
    /* Backup writes remain the real recomp/save-device path. */
    if (gameplay.pause_window.save_prompt) {
        pause_windows_printf(6,20,"%-28s",save_scene_name(save_state.scene_id));
        int report = recomp_save_report();
        pause_windows_printf(6, 22, "%-28s", !save_device_ready() ? save_device_error() :
            report < 0 ? "" : report ? "SAVED" : save_device_error());
    }

}

static unsigned int pace_fps10, pace_vbl10;
static void __attribute__((optimize("Os"))) viewer_hud(void)
{
#ifdef DOSEI_CLEAN_TEST
    /* Player-test disc: no debug text, even if L+R is pressed.
     * Keep JO_DEBUG safety checks and initialization unchanged.
     * TEMPORARY (2026-10-04 tool bring-up): one bottom line while a decomp
     * tool is live or was just used (bridge_items.cpp OotCore_ToolDebug). */
#ifdef DOSEI_OOT_CORE
    {
        static bool shown;
        const char *t = oot_core_debug_text2();
        if (t[0] == 'T') { jo_printf(0, JO_TV_HEIGHT / 8 - 2, "%-39.39s", t); shown = true; }
        else if (shown) { jo_printf(0, JO_TV_HEIGHT / 8 - 2, "%39s", ""); shown = false; }
    }
#endif
    return;
#endif
#if defined(DOSEI_PERF_PROBE) && DOSEI_PERF_PROBE == 3
    /* Unobstructed actor inspection on the isolated diagnostic disc. */
    return;
#endif
    static unsigned int last_refresh;
    unsigned int now = recomp_clock();
    /* L+R, latched in recomp_update() so the chord is read with the rest of the
    ** input and consumes both buttons. A is deliberately not used here: it is
    ** reserved for the action button, and the g/L/d readout below is the only
    ** evidence for the unexplained rolling, so it has to stay reachable. */
    if (recomp_diagnostics_toggled) {
        recomp_diagnostics_toggled = false;
        debug_visible = !debug_visible;
        jo_clear_screen();
        last_refresh = now - 15;
    }
    /* VDP2 retains the text. Formatting and rewriting every digit every draw
     * costs several milliseconds; four readable updates per second suffice.
     * Input/chord handling above still runs every frame. */
    if (now - last_refresh < 15) return;
    {
        /* Row 16 pacing from the VBlank clock alone (60 Hz, FRT-free):
         * displayed frames per second and VBlanks per frame since the last
         * refresh. Compare with Mednafen's Shift+F1 virtual FPS. */
        static unsigned int last_frames;
        unsigned int frames = perf_frames - last_frames, vbl = now - last_refresh;
        last_frames = perf_frames;
        pace_fps10 = frames ? frames * 600u / vbl : 0;
        pace_vbl10 = frames ? vbl * 10u / frames : 0;
        perf_sub_average();
    }
    last_refresh = now;
    /* M2a heap reading, always on in the standard build (bottom row 27):
    ** work-RAM zone 0 live/peak bytes, cart zones' summed peak KB, failed
    ** allocations. Exact dosei_heap_profile, not the SDK's mixed percent. */
    {
        unsigned int z, cart = 0;
        for (z = 1; z < dosei_heap_profile.zones && z < HEAP_PROFILE_ZONES; ++z)
            cart += dosei_heap_profile.zone[z].peak_live;
        jo_printf(0, 27, "heap w%u/%u c%uK f%u sp%u  ",
                  (unsigned int)dosei_heap_profile.zone[0].live,
                  (unsigned int)dosei_heap_profile.zone[0].peak_live,
                  (cart + 1023) / 1024,
                  (unsigned int)dosei_heap_profile.failed_allocations,
                  kokiri_sprite_peak);
    }
    if (!debug_visible) {
        /* Performance overlay (2026-10-09, real Player). 0.1 ms units.
        ** Row 0: whole frame, CPU work, wait for VDP1/VBlank.
        ** Row 1: host phases: mv = gameplay step incl. the core update and
        **   camera, sk = Link skinning, sc = scene submit, lk = Link submit,
        **   ot = everything not named (NPC sprites, HUD, text, audio...).
        ** Row 2: core update per 20 Hz step: total, then collision checks /
        **   actor updates / messages+env / draw shim, pd = Player anchor draw.
        ** Row 3: top 3 actor ids by update cost (id x 0.1 ms; Player is 0).
        ** Row 4: host collision queries and proxy rebuilds this refresh,
        **   core actors player/npc/enemy/prop/misc, scene index. */
        unsigned int work = frame_timer_frame();
        unsigned int sync = frame_timer_cost(FRAME_PHASE_SYNC);
        jo_printf(0, 0, "fr%-4u wk%-4u sy%-4u          ",
                  (work + sync) / 100, work / 100, sync / 100);
        jo_printf(0, 1, "mv%-3u sk%-3u sc%-3u lk%-3u ot%-3u   ",
                  frame_timer_cost(FRAME_PHASE_MOVEMENT) / 100,
                  frame_timer_cost(FRAME_PHASE_SKINNING) / 100,
                  frame_timer_cost(FRAME_PHASE_SCENE) / 100,
                  frame_timer_cost(FRAME_PHASE_LINK) / 100,
                  frame_timer_other() / 100);
#ifdef DOSEI_OOT_CORE
        if (oot_core_is_loaded()) {
            const char *t = oot_core_debug_text2();
            char phases[24];
            unsigned int i = 0;
            /* debug_text2: "col/act/msg/drw <top3 or tool text>" */
            while (t[i] && t[i] != ' ' && i < sizeof phases - 1) { phases[i] = t[i]; ++i; }
            phases[i] = 0;
            jo_printf(0, 2, "cu%-4u %-15s pd%-3u      ", oot_core_update_us() / 100, phases,
                      oot_core_player_draw_us() / 100);
            jo_printf(0, 7, "top %-34s", t[i] ? t + i + 1 : "");
            jo_printf(0, 21, "%-39s", oot_core_debug_text());
            {
                uint32_t q = 0, r = 0;
#ifdef CORE_COLLISION
                bg_core_shim_counts(&q, &r);
#endif
                int fd = 0;
#ifdef CORE_COLLISION
                fd = bg_core_fast_data(-1);
#endif
                jo_printf(0, 8, "bgq%-4u rb%-2u a%d/%d/%d/%d/%d s%u fd%d   ", (unsigned)q, (unsigned)r,
                          oot_core_actors(2), oot_core_actors(4), oot_core_actors(5),
                          oot_core_actors(6), oot_core_actors(8), scene_flow_scene(), fd);
            }
#ifdef PLAYER_SOURCE
            {
                unsigned int h[5];
                recomp_step_perf(h);
                jo_printf(0, 9, "gs%-4u co%-4u cm%-4u st%-4u n%u   ",
                          h[0] / 100, h[1] / 100, h[2] / 100, h[3] / 100, h[4]);
            }
#endif
            {
                const unsigned int *p = perf_sub_avg;   /* refresh-window mean */
                jo_printf(0, 10, "nc%u wp%u en%u at%u bb%u tk%u it%u rc%u     ",
                          p[PS_NC] / 100, p[PS_WP] / 100, p[PS_EN] / 100, p[PS_AT] / 100,
                          p[PS_BB] / 100, p[PS_TK] / 100, p[PS_IT] / 100, p[PS_RC] / 100);
                jo_printf(0, 11, "pr%u po%u ac%u dp%u nv%u     ",
                          p[PS_PRE] / 100, p[PS_POST] / 100, p[PS_AC] / 100, p[PS_DP] / 100,
                          p[PS_NV] / 100);
                jo_printf(0, 12, "ks%u dg%u da%u ui%u ru%u     ",
                          p[PS_KS] / 100, p[PS_DGR] / 100, p[PS_DAC] / 100, p[PS_DUI] / 100,
                          p[PS_RU] / 100);
                jo_printf(0, 13, "%40s", "");
                jo_printf(0, 13, "nb%u np%u wc%u wp%u wr%u pl%u fy%u",
                          p[PS_DNB] / 100, p[PS_DNPC] / 100, p[PS_DWC] / 100, p[PS_DWP] / 100,
                          p[PS_DWR] / 100, p[PS_DPPL] / 100, p[PS_DFY] / 100);
                jo_printf(0, 14, "r0%u r1%u pd%u dw%u     ",
                          p[PS_R0] / 100, p[PS_R1] / 100, p[PS_PRD] / 100, p[PS_DPW] / 100);
                {
                    unsigned int a[5];
                    unsigned int site = oot_core_async_violation_line();
                    oot_core_async_stats(a);
                    jo_printf(0, 15, "as k%u ov%u jw%u cv%u@%u bv%u dr%u    ",
                              a[0], a[1] / 100, a[2] / 100, a[3], site, a[4], kokiri_sgl_drain_us() / 100);
                }
                {
                    /* Rows 16-17: who waits for whom (last frame, 0.1 ms).
                     * 16: pacing, then master waits on the slave: scene
                     *     prepare, Link skin, core join, SGL queue drain.
                     * 17: slave job times: prepare, core update, skin, and
                     *     their share of the frame (SGL polygons excluded). */
                    unsigned int frame = frame_timer_frame() + frame_timer_cost(FRAME_PHASE_SYNC);
                    unsigned int busy = p[PS_SPREP] + p[PS_SCORE] + p[PS_SSKIN];
                    jo_printf(0, 16, "%40s", "");
                    jo_printf(0, 17, "%40s", "");
                    jo_printf(0, 18, "%40s", "");
                    jo_printf(0, 16, "fps%u.%u vb%u.%u W pr%u sk%u jn%u dr%u %c   ",
                              pace_fps10 / 10, pace_fps10 % 10, pace_vbl10 / 10, pace_vbl10 % 10,
                              p[PS_WPREP] / 100, p[PS_WSKIN] / 100, p[PS_WJOIN] / 100,
                              p[PS_WDRAIN] / 100, kokiri_parallel_prepare ? 'M' : kokiri_prep_first ? 'P' : 'C');
                    jo_printf(0, 17, "S pr%u cu%u sk%u %u%%      ",
                              p[PS_SPREP] / 100, p[PS_SCORE] / 100, p[PS_SSKIN] / 100,
                              frame ? (busy > frame ? 100u : busy * 100u / frame) : 0u);
                    /* Row 18: prepare depth/partition/fog, fog tiles
                     * rewritten, cel upload time and KB to VDP1 VRAM. */
                    jo_printf(0, 18, "pd%u pp%u pf%u ft%u cel%u %uK sb%u   ",
                              p[PS_PDEPTH] / 100, p[PS_PPART] / 100, p[PS_PFOG] / 100,
                              p[PS_FOGN], p[PS_CEL] / 100, (p[PS_CELB] + 1023) / 1024,
                              p[PS_SUBMIT] / 100);
                    /* Row 19: sprite actors: shadow lookup+submit, slPutSprite,
                     * sprites drawn, shadow floor queries after the join. */
                    jo_printf(0, 19, "%40s", "");
                    jo_printf(0, 19, "spr n%u sh%u put%u rs%u nd%u sg%u ch%u",
                              p[PS_SCOUNT], p[PS_SSHADOW] / 100, p[PS_SPUT] / 100,
                              p[PS_SRESOLVE] / 100, p[PS_NDRAW] / 100,
                              p[PS_DSIGN] / 100, p[PS_DCHEST] / 100);
                    jo_printf(0, 20, "geo v%u/%u pk%u mp%u g%u ec%u r%u  ",
                              p[PS_VUSED], p[PS_VTOTAL], p[PS_VPACK] / 100, p[PS_MPREP] / 100,
                              kokiri_scene_gather_mode(), kokiri_scene_candidate_count(),
                              kokiri_scene_candidate_reused());
                    jo_printf(0, 22, "hud q%u hp%u vis%u a%u b%u v%u    ",
                              p[PS_HQUERY] / 100, p[PS_HHEALTH] / 100, p[PS_HVIS] / 100,
#ifdef PLAYER_SOURCE
                              (unsigned int)oot_core_player.aim_mode,
                              (unsigned int)oot_core_player.item_button,
#else
                              0u, 0u,
#endif
                              (unsigned int)recomp_view_first_person());
                    /* Row 23: candidate envelope variant (L+R+Right cycles),
                     * build %, build pass time, exit reasons % (docs). */
                    jo_printf(0, 23, "%40s", "");
                    jo_printf(0, 23, "env v%u b%u bt%u xp%u xa%u xo%u",
                              kokiri_scene_envelope_variant(), p[PS_EBUILD],
                              p[PS_EBTIME] / 100, p[PS_EXPOS], p[PS_EXANG], p[PS_EXOTH]);
                }
            }
        }
#endif
        return;
    }
    jo_printf(0, 0, "Jo/SGL Kokiri viewer");
#ifdef DOSEI_TEXTURE_PROBE
    jo_printf(0, 0, "TEXTURE PROBE stage %d   ", (int)probe_stage);
#endif
    jo_printf(0, 1, "verts %d tris %d tiles %d",
              KOKIRI_VERTEX_COUNT, KOKIRI_POLYGON_COUNT, KOKIRI_TILE_COUNT);
    jo_printf(0, 2, "cam %d,%d,%d pan %d   ", (int)recomp_camera.x, (int)recomp_camera.y, (int)recomp_camera.z,
              (int)recomp_yaw);
    if (recomp_link_active)
        jo_printf(0, 8, "link %d,%d,%d yaw %d  ", (int)recomp_link.x,
                  (int)(recomp_link.y - RECOMP_LINK_EYE_HEIGHT), (int)recomp_link.z,
                  (int)recomp_link_yaw);
    else
        jo_printf(0, 8, "link: press %-10s", ui_button_label(UI_KEY_START, false));
    /* jo_3d_get_polygon_count() reports SGL's TotalPolygons, i.e. polygons
    ** submitted this frame, not DispPolygons actually drawn -- so it is a
    ** submission count, not a coverage measurement. "rej" is the number of
    ** slPutPolygon calls SGL refused; it must stay 0 for the view to be
    ** complete. */
    jo_printf(0, 3, "subm %d rej %d    ", jo_3d_get_polygon_count(),
              (int)kokiri_scene_rejected());
    jo_printf(0, 4, "verts %d shown %d    ", jo_3d_get_vertices_count(),
              jo_3d_get_displayed_polygon_count());
    jo_printf(0, 5, "ok mask %d max P%d V%d  ",
              (int)kokiri_scene_accepted_mask(), MaxPolygons, MaxVertices);
    jo_printf(0, 6, "music %s %s tick %d  ", music_ready ? "ON" : "FAIL",
              music_current() == &music_bank_kokiri ? "kokiri" : "title",
              (int)music_ticks());
    jo_printf(0, 10, "swap %d vbl (%d ms)%s  ",
              (int)music_transition_frames(),
              (int)(music_transition_frames() * 1000 / 60),
              music_failed() ? " FAILED" : "");
    jo_printf(0, 7, "total refusals %d    ", (int)rejected_total);
    jo_printf(0, 9, "collision index %s   ",
              recomp_collision_indexed ? "ON" : "off (full scan)");
}

/*
** File select.
**
** Gameplay text, not debug text, so it is drawn on the clean player disc too.
** VDP2 retains what is printed, so the screen clears its own rows on the frame
** it stops being shown -- otherwise the file list would sit on top of the
** forest after a file is chosen.
*/
#define FS_ROW      6
#define FS_ROWS     (FILE_SELECT_ROWS * 2 + 6)

static void __attribute__((optimize("Os"))) file_select_screen(void)
{
    static bool   was_visible;
    /* True while the "Open this file?" panel is up, so the list behind it is
    ** cleared once on entry and redrawn once on the way back out. */
    static bool   was_open;
    unsigned int  row;

    if (!recomp_file_select_is_visible()) {
        if (was_visible) {
            for (row = 0; row < FS_ROWS; ++row)
                jo_printf(0, (int)(FS_ROW + row), "                                      ");
            was_visible = false;
            was_open = false;
        }
        return;
    }
    was_visible = true;
    if(level_select.visible) {
        for(row=0;row<FS_ROWS;++row)jo_printf(0,FS_ROW+row,"                                      ");
        jo_printf(4,FS_ROW,"LEVEL SELECT - DEBUG MODE");
        if(level_select.page==LEVEL_OPTIONS) {
            jo_printf(2,FS_ROW+2,"%.35s",scene_name(level_select.scene));
            for(row=0;row<5;++row)jo_printf(2,FS_ROW+4+row*2,"%s",level_select.cursor==row?">":" ");
            jo_printf(4,FS_ROW+4,"Room: %u / %u",level_select.room,scene_entries[level_select.scene].rooms-1);
            jo_printf(4,FS_ROW+6,"Link: %s",level_select.adult?"Adult":"Child");
            jo_printf(4,FS_ROW+8,"All Items? %s",level_select.max_gear?"On":"Off");
            jo_printf(4,FS_ROW+10,"Begin Play Test");
            jo_printf(4,FS_ROW+12,"Go Back");
            if(level_select.failed)jo_printf(2,FS_ROW+13,"ROOM ENTRY UNAVAILABLE");
        } else {
            unsigned count=level_select_count();
            unsigned first=level_select.cursor>=8?level_select.cursor-7:0;
            jo_printf(2,FS_ROW+2,"%s",level_select.page==LEVEL_REGIONS?"Choose Region":level_select_region(level_select.region));
            for(row=first;row<count && row<first+8;++row)
                jo_printf(2,FS_ROW+4+row-first,"%s %.33s",row==level_select.cursor?">":" ",
                    level_select.page==LEVEL_REGIONS?level_select_region(row):scene_name(level_select_map(level_select.region,row)));
            jo_printf(2,FS_ROW+13,"%u / %u",level_select.cursor+1,count);
        }
        jo_printf(2,FS_ROW+14,"A: SELECT / TOGGLE  B: BACK");
        jo_printf(2,FS_ROW+15,"TEST RUN - NO SAVE SLOT");
        was_open=true;return;
    }

    /* "Open this file?" takes over the whole panel, as it does on N64: the
    ** list is not left visible behind it, so the file being opened is the only
    ** thing on screen and there is no second cursor to misread. */
    if (file_select.mode == FILE_SELECT_OPEN_CONFIRM) {
        unsigned int slot = file_select_open_slot();
        unsigned int line;

        /* Clear the list once on the way in. VDP2 retains text, so redoing it
        ** every frame would only cost time and flicker the panel. */
        if (!was_open) {
            for (line = 0; line < FS_ROWS; ++line)
                jo_printf(0, (int)(FS_ROW + line),
                          "                                      ");
            was_open = true;
        }
        jo_printf(4, FS_ROW, "OPEN THIS FILE?");
        jo_printf(4, FS_ROW + 2, "%-12s", file_select_row_label(slot));
        jo_printf(4, FS_ROW + 3, "%-32s", file_select_row_detail(slot));
        jo_printf(4, FS_ROW + 4, "%-32s", file_select_row_location(slot));
        for (line = 0; line < FILE_SELECT_OPEN_ROWS; ++line)
            jo_printf(4, (int)(FS_ROW + 5 + line), "%s %-6s",
                      file_select.open_row == line ? ">" : " ",
                      file_select_open_label(line));
        jo_printf(2, FS_ROW + 5 + FILE_SELECT_OPEN_ROWS + 1,
                  "%s: DECIDE  %s%s              ", ui_button_label(UI_KEY_A, false),
                  ui_button_label(UI_KEY_B, false), *ui_button_label(UI_KEY_B, false) ? ": CANCEL" : "");
        return;
    }
    /* Back from the panel: wipe it before the list is drawn over it, or its
    ** longer lines stay behind the shorter ones. */
    if (was_open) {
        for (row = 0; row < FS_ROWS; ++row)
            jo_printf(0, (int)(FS_ROW + row), "                                      ");
        was_open = false;
    }

    jo_printf(4, FS_ROW, "SELECT A FILE");
    for (row = 0; row < FILE_SELECT_ROWS; ++row) {
        int line = (int)(FS_ROW + 2 + row * 2);
        bool here = (file_select.cursor == row);
        /* In erase mode the erase row itself is not selectable, so it is drawn
        ** without a cursor rather than left looking chosen. */
        if (file_select.mode == FILE_SELECT_ERASE_PICK &&
            row >= SAVE_FILE_SLOTS)
            here = false;
        if(row==FILE_SELECT_ROW_DEBUG)
            jo_printf(2,line,"%s %-34s",here?">":" ",file_select_row_label(row));
        else jo_printf(2, line, "%s %-7s %-24s", here ? ">" : " ",
                  file_select_row_label(row),file_select_row_location(row));
        jo_printf(2, line + 1, "     %-32s", file_select_row_detail(row));
    }

    row = FS_ROW + 2 + FILE_SELECT_ROWS * 2;
    {
        const char *a = ui_button_label(UI_KEY_A, false);
        const char *b = ui_button_label(UI_KEY_B, false);
        jo_printf(2, (int)row + 1, "%-36s", "");
        switch (file_select.mode) {
        case FILE_SELECT_ERASE_CONFIRM:
            jo_printf(2, (int)row, "ERASE %-12s?                 ",
                      file_select_row_label(file_select.erase_slot));
            jo_printf(2, (int)row+1, "%s: YES  %s%s              ", a, b, *b ? ": NO" : "");
            break;
        case FILE_SELECT_ERASE_PICK:
            jo_printf(2, (int)row, "PICK A FILE TO ERASE.            ");
            jo_printf(2, (int)row+1, "%s%s                         ", b, *b ? ": BACK" : "");
            break;
        default:
            jo_printf(2, (int)row, "%s: PLAY  %s%s             ", a, b, *b ? ": TITLE" : "");
            break;
        }
    }
    /* Only ever shown when a device call actually refused. */
    jo_printf(2, (int)row + 2, "%s",
              file_select.device_failed ? "CANNOT USE THAT FILE          "
                                        : "                              ");
    if (!save_device_ready())
        jo_printf(2, (int)row + 3, "%-32s", save_device_error());
}

/* Boot setup is cold; retain the full heap and SGL pools. */
void __attribute__((optimize("Os"))) jo_main(void)
{
    extern void sprites_low_init(void);
    extern void fs_low_init(void);
    extern void core_low_init(void);
    core_low_init();
    fs_low_init();
    sprites_low_init();
    /* Low RAM is not boot-cleared. Initialize before any scene/actor reads. */
    save_new_game();
    jo_core_init(JO_COLOR_Black);
    dialogue_font_init();
    frame_timer_init();
    perf_sub_init();
#ifdef DOSEI_HIRES
    /* VDP2 samples the existing title/font at half rate vertically. */
    jo_vdp2_zoom_nbg0f(1.0f, 0.5f);
    jo_vdp2_zoom_nbg1f(1.0f, 0.5f);
#endif
    /* NBG2 (minimap) second: above the world, below the text. */
    jo_core_set_screens_order(JO_NBG0_SCREEN, JO_NBG2_SCREEN, JO_NBG1_SCREEN,
                             JO_SPRITE_SCREEN, JO_RBG0_SCREEN, JO_NBG3_SCREEN);
    minimap_priorities();
    slSetScreenDist(toFIXED(SCREEN_DISTANCE));

    /* The 4 MB cart is required. Stop here rather than loading and failing an
    ** allocation later, where the real cause would be invisible. The second
    ** bank must be claimed before anything allocates, or the early allocations
    ** crowd the first bank while half the cart sits unused. */
    if (!ram_cart_claim_second_bank()) {
        jo_printf(2, 10, "4 MB RAM EXPANSION CART REQUIRED");
        jo_printf(2, 12, "This game needs the 4 MB (32 Mbit)");
        jo_printf(2, 13, "Saturn RAM expansion cartridge.");
        jo_printf(2, 15, "In Kronos: set Cartridge/Type to");
        jo_printf(2, 16, "the 32 Mbit DRAM cart (type 7).");
        jo_core_run();
        return;
    }
    /* Cold const tables (host_cold.h) are read only after this load. */
    if (!ram_cart_load_host_cold()) {
        jo_printf(2, 10, "HOSTCOLD.BIN MISSING OR MISMATCHED");
        jo_printf(2, 12, "Rebuild: it must come from the");
        jo_printf(2, 13, "same link as 0.BIN.");
        jo_core_run();
        return;
    }
#ifdef DOSEI_OOT_CORE
    oot_core_boot();
#endif

    /* High-WRAM pool by default; preserve cart carve for diagnostic builds. */
    if (actor_sys_bytes() > RAM_CART_ACTOR_POOL_BYTES ||
        !actor_sys_init(
#ifdef DOSEI_CART_ACTOR_POOL
                        ram_cart_fixed(RAM_CART_ACTOR_POOL_OFFSET, RAM_CART_ACTOR_POOL_BYTES),
#else
                        fast_actor_pool,
#endif
                        RAM_CART_ACTOR_POOL_BYTES)) {
        jo_core_error("Actor pool does not fit its cart carve");
        return;
    }
    if(!skulltula_init(ram_cart_fixed(RAM_CART_SKULL_OFFSET,RAM_CART_SKULL_BYTES),RAM_CART_SKULL_BYTES))
        jo_core_error("Skulltula state exceeds cart carve");
    if(!wall_skull_init(ram_cart_fixed(RAM_CART_WALL_SKULL_OFFSET,RAM_CART_WALL_SKULL_BYTES),RAM_CART_WALL_SKULL_BYTES))
        jo_core_error("Wall Skulltula state exceeds cart carve");
    if(!dekubaba_init(ram_cart_fixed(RAM_CART_DEKU_BABA_OFFSET,RAM_CART_DEKU_BABA_BYTES),RAM_CART_DEKU_BABA_BYTES))
        jo_core_error("Deku Baba state exceeds cart carve");
    if(!hintnuts_init(ram_cart_fixed(RAM_CART_HINTNUTS_OFFSET,RAM_CART_HINTNUTS_BYTES),RAM_CART_HINTNUTS_BYTES))
        jo_core_error("Hint Scrub state exceeds cart carve");
    if(!gohma_larva_init(RAM_LOW(RAM_LOW_GOMA_OFFSET),RAM_LOW_GOMA_BYTES))
        jo_core_error("Gohma larva state exceeds low RAM carve");
    if(!gohma_init(RAM_LOW(RAM_LOW_GOHMA_OFFSET),RAM_LOW_GOHMA_BYTES))
        jo_core_error("Gohma state exceeds low RAM carve");
    if (!karebaba_init(ram_cart_fixed(RAM_CART_KAREBABA_OFFSET, RAM_CART_KAREBABA_BYTES),
                       RAM_CART_KAREBABA_BYTES)) {
        jo_core_error("Karebaba state does not fit its cart carve");
        return;
    }

    /* Sword/grass contact colliders: fixed cart carve too. */
    if (!gameplay_contacts_init(ram_cart_fixed(RAM_CART_CONTACT_OFFSET,
                                               RAM_CART_CONTACT_BYTES),
                                RAM_CART_CONTACT_BYTES)) {
        jo_core_error("Contact colliders do not fit their cart carve");
        return;
    }

    /* Dialogue line text: disc file into a fixed cart carve (BUG-033). */
    if (!dialogue_text_load()) {
        return;
    }
    /* Scene spawns and doors (all scenes) from disc into the jo heap. */
    if (!scene_table_load()) {
        jo_core_error("SCENETAB.BIN failed to load");
        return;
    }

    /* Link's clip frames live in the cart; posing without them is impossible. */
    if (!link_anim_load()) {
        jo_core_error("LINKANIM.BIN missing or does not match this build");
        return;
    }

    /* Backup RAM is mounted before anything can ask to load a file. A console
    ** with no usable internal memory is still playable, so this is reported
    ** rather than fatal -- unlike the missing cart above. */
    if (!save_device_init())
        jo_printf(2, 26, "no backup memory: cannot save");

    scene_ready = kokiri_scene_load();
    scene_ready = scene_ready && recomp_init();
    field_music_init();
    music_ready = scene_ready && music_init_with_scratch(music_song_bank(NA_BGM_TITLE),
        ram_cart_fixed(RAM_CART_LOAD_SCRATCH_OFFSET, RAM_CART_LOAD_SCRATCH_BYTES),
        RAM_CART_LOAD_SCRATCH_BYTES);
    if (scene_ready && !music_ready)
        jo_printf(2, 3, "music load FAILED");
    if (music_ready && !action_audio_init()) {
        scene_ready = false;
        jo_printf(2, 3, "action audio load FAILED");
    }

    jo_core_add_callback(viewer_draw);
    jo_core_run();
}

/*
** END OF FILE
*/
