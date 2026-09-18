/*
** Isolated Jo Engine / SGL Kokiri Forest viewer.
**
** Title-demo bring-up: textured forest, automatic yaw and baseline SCSP score.
** Title artwork, controls and source-space collision are connected. This is not
** a renderer-only performance comparison with the libyaul baseline.
**
** Resolution is TV_320x240 (jo/conf.h, NTSC non-480i), matching the libyaul
** build's 320x240 viewport, so the comparison needs no video-mode change.
*/

#include <jo/jo.h>

#include "kokiri_scene.h"
#include "kokiri_sgl.h"
#include "music.h"
#include "music_banks.h"
#include "demo.h"
#include "link_anim_state.h"
#include "frame_timer.h"
#include "oot_follow.h"

/*
** Baseline camera, in the scene's native source space.
**
** Position: kokiri_collision_spawn() in the libyaul build searches outward
** from x=-300,z=0 and derives y from the floor plus EYE_HEIGHT (90). Replaying
** that search over FOREST.BIN's 1692 collision triangles lands on ring 0 with
** floor y=1, giving (-300, 91, 0) -- the pose the handoff documents. The
** demo now derives this spawn and raises it 24 units through collision.
**
** Facing: at yaw 0 the baseline's Y-rotation matrix is identity and it uses
** the rotated z as depth (kokiri_scene.c:160-171), so yaw 0 looks along +Z.
** Its projection is sy = 120 - offset(py), so +Y is up. SGL projects +Y
** downward: the fixed view must be (x-CAM_X, CAM_Y-y, z-CAM_Z).
*/
#define SCREEN_DISTANCE     (240)
static bool         scene_ready;
static bool         music_ready;
static bool         debug_visible;
static unsigned int rejected_total;
static void         viewer_hud(void);
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
    demo_link_active = false;
    demo_pitch = 0;
    if (phase < 360) {
        demo_camera.x = PROBE_GROUND_X;
        demo_camera.y = PROBE_GROUND_Y + 110;
        demo_camera.z = PROBE_GROUND_Z - distance;
        demo_yaw = (uint16_t)turn;
    } else {
        distance += 200;
        demo_camera.x = PROBE_TREE_X;
        demo_camera.y = PROBE_TREE_Y;
        demo_camera.z = PROBE_TREE_Z + distance;
        demo_yaw = (uint16_t)(32768 + turn);
    }
    slScrAutoDisp(NBG0ON);
    debug_visible = true;
}
#endif

static void         viewer_draw(void)
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
    ** in baked-Y space; no runtime reflection. The demo's 60 Hz clock keeps
    ** the original 90 angle units/tick pan independent of render rate. */
    /* The gap since the previous callback returned is Jo's slSynch wait plus
    ** whatever the engine does between callbacks: the part of the frame this
    ** file never sees. Measured first so it covers the real idle. */
    frame_timer_end(FRAME_PHASE_SYNC);
    /* Before any CPU work: was VDP1 still drawing when control came back? */
    frame_timer_sample_vdp1();
    frame_timer_frame_begin();
    frame_timer_begin(FRAME_PHASE_MOVEMENT);
    demo_update();
    if (!kokiri_scene_update()) {
        scene_ready = false;
        jo_printf(2, 2, "room load FAILED");
        return;
    }
#if defined(DOSEI_PERF_PROBE) && DOSEI_PERF_PROBE == 1
    /* Repeatable no-input render baseline. Never enabled in normal builds. */
    demo_camera.x = -300; demo_camera.y = 141; demo_camera.z = -260;
    demo_yaw = 0; demo_pitch = 0;
#endif
#if defined(DOSEI_PERF_PROBE) && DOSEI_PERF_PROBE == 3
    /* Actor inspection only: original animations, slowly orbiting camera.
     * No controller injection or focus needed. Never in a normal disc. */
    if (demo_link_active) {
        int32_t sine, cosine;
        unsigned int tick = demo_clock();
        demo_yaw = (uint16_t)(32768u + ((tick / 180) % 4) * 8192u);
        kokiri_camera_sincos(demo_yaw, &sine, &cosine);
        demo_camera.x = demo_link.x - (int32_t)(((int64_t)sine * 155) >> 16);
        demo_camera.z = demo_link.z - (int32_t)(((int64_t)cosine * 155) >> 16);
        demo_camera.y = demo_link.y - DEMO_LINK_EYE_HEIGHT + 77;
        demo_pitch = -1820;
        demo_link_yaw = 0;
        link_anim_pose((tick / 300) % 3, (tick / 3) % 20, 0);
    }
#endif
    frame_timer_end(FRAME_PHASE_MOVEMENT);
    slSetScreenDist(toFIXED(demo_title_is_visible() ? 180 : SCREEN_DISTANCE));
    music_service();
#ifdef DOSEI_TEXTURE_PROBE
    texture_probe();
#endif
#ifdef DOSEI_HIRES
    /* Double only projected Y, keeping the same framing at 320x480i. */
    slScale(toFIXED(1), toFIXED(2), toFIXED(1));
#endif
    slRotX((ANGLE)(0u-demo_pitch));
    slRotY((ANGLE)(0u-demo_yaw));
    jo_3d_translate_matrix(-demo_camera.x, demo_camera.y, -demo_camera.z);
    frame_timer_begin(FRAME_PHASE_SCENE);
#if !defined(DOSEI_PERF_PROBE) || DOSEI_PERF_PROBE != 3
    kokiri_scene_draw();
    kokiri_fairies_draw(demo_clock());
#endif
    frame_timer_end(FRAME_PHASE_SCENE);
    /* Link is submitted after the forest so the per-frame counters, which
    ** kokiri_scene_draw() resets, cover both lists. His model origin is at his
    ** feet, EYE_HEIGHT below the collision position. */
    if (demo_link_active && !demo_title_is_visible()) {
        frame_timer_begin(FRAME_PHASE_LINK);
        kokiri_link_draw(demo_link.x, demo_link.y - DEMO_LINK_EYE_HEIGHT,
                         demo_link.z, demo_link_yaw);
        frame_timer_end(FRAME_PHASE_LINK);
    }
    rejected_total += kokiri_scene_rejected();
    viewer_hud();
    frame_timer_frame_end();
    frame_timer_begin(FRAME_PHASE_SYNC);
}

static void         viewer_hud(void)
{
#ifdef DOSEI_CLEAN_TEST
    /* Player-test disc: no debug text, even if L+R is pressed.
     * Keep JO_DEBUG safety checks and initialization unchanged. */
    return;
#endif
#if defined(DOSEI_PERF_PROBE) && DOSEI_PERF_PROBE == 3
    /* Unobstructed actor inspection on the isolated diagnostic disc. */
    return;
#endif
    static unsigned int last_refresh;
    unsigned int now = demo_clock();
    /* L+R, latched in demo_update() so the chord is read with the rest of the
    ** input and consumes both buttons. A is deliberately not used here: it is
    ** reserved for the action button, and the g/L/d readout below is the only
    ** evidence for the unexplained rolling, so it has to stay reachable. */
    if (demo_diagnostics_toggled) {
        demo_diagnostics_toggled = false;
        debug_visible = !debug_visible;
        jo_clear_screen();
        last_refresh = now - 15;
    }
    /* VDP2 retains the text. Formatting and rewriting every digit every draw
     * costs several milliseconds; four readable updates per second suffice.
     * Input/chord handling above still runs every frame. */
    if (now - last_refresh < 15) return;
    last_refresh = now;
    if (!debug_visible) {
        if (rejected_total || !music_ready)
            jo_printf(0, 0, "music %s refusals %d", music_ready ? "ON" : "FAIL", (int)rejected_total);
        /* Link's pose stays visible without the debug toggle: it is the
        ** quickest way to tell a framing problem from a movement one. */
        /* Switch timing stays visible without the debug toggle: the budget
        ** for title -> forest is two seconds and this is the measurement. */
        /* Kept inside 40 columns: the Saturn screen truncates past that and
        ** the stall figure was being cut off. a=audible f=full s=worst stall. */
        jo_printf(0, 0, "%s n%d a%d f%d s%d%s   ",
                  music_current() == &music_bank_kokiri ? "kokiri" : "title",
                  (int)music_swap_count(),
                  (int)(music_audible_frames() * 1000 / 60),
                  (int)(music_transition_frames() * 1000 / 60),
                  (int)(music_worst_stall() * 1000 / 60),
                  music_failed() ? " FAIL" : "");
        if (demo_link_active)
            jo_printf(0, 1, "L %d,%d,%d yaw %d   ",
                      (int)demo_link.x, (int)demo_link.y, (int)demo_link.z,
                      (int)demo_link_yaw);
        /* Heap headroom and the current locomotion state. The heap figure is
        ** what justifies JO_GLOBAL_MEMORY_SIZE_FOR_MALLOC: the clip tables and
        ** the skinned POINT table compete with it for the RAM below SGL's work
        ** area, so it was trimmed to measured demand rather than guessed. */
        {
            /* Assigned first: casting an enum-returning call directly trips
            ** -Wbad-function-cast, and this build treats warnings as noise to
            ** stay out of. */
            link_state_t pose = link_anim_state();
            jo_printf(0, 2, "heap %d%%  anim %d f%d %s    ",
                      jo_memory_usage_percent(), (int)pose,
                      (int)link_anim_frame(),
                      player_input_move_mode() == PLAYER_MOVE_WALK ? "walk"
                                                                   : "run");
            /* The 2026-09-18 inputs whose gameplay systems do not exist yet.
            ** This is the only evidence that A, X and the routed C buttons
            ** actually arrive, since none of them can do anything yet. */
            jo_printf(0, 4, "pend a%d x%d c%d    ",
                      (int)demo_interact_requests, (int)demo_attack_requests,
                      (int)demo_last_c_button);
            /* One line, because the question is whether the visible rolling
            ** and the state machine agree -- reading that across two rows is
            ** exactly how a wrong answer gets recorded.
            **
            ** s = current state (0 idle, 1 walk, 2 run, 3 fall, 4 landing,
            ** 5 roll), g = grounded now, L = landings seen, d = the fall
            ** distance the last landing decided on.
            **
            ** If Link looks like he is rolling while s is NOT 5, the pose is
            ** wrong and the landing logic is innocent -- that is the corrupted
            ** -frame case, not a state bug. If s is 5 and L is climbing on flat
            ** ground, a real grounded transition is firing and d names the gate
            ** that chose the roll. */
            jo_printf(0, 3, "s%d g%d L%d d%d      ",
                      (int)pose,
                      link_anim_last_grounded() ? 1 : 0,
                      (int)link_anim_landings(),
                      (int)link_anim_last_fall());
        }
        /* Outside the Link guard: the title screen is reported slow too, and
        ** Link is not drawn there. If the forest alone is the cost, these rows
        ** show it with no player on screen. */
        /* Microseconds against a 16700 us frame budget. mv=movement,
        ** sk=skinning, sc=forest submit, lk=Link submit, sy=sync wait,
        ** ot=everything none of those accounted for. */
        jo_printf(0, 4, "mv%u sk%u sc%u lk%u   ",
                  frame_timer_cost(FRAME_PHASE_MOVEMENT),
                  frame_timer_cost(FRAME_PHASE_SKINNING),
                  frame_timer_cost(FRAME_PHASE_SCENE),
                  frame_timer_cost(FRAME_PHASE_LINK));
        jo_printf(0, 5, "sy%u ot%u WORK%u us   ",
                  frame_timer_cost(FRAME_PHASE_SYNC),
                  frame_timer_other(), frame_timer_frame());
        jo_printf(0, 7, "prep%u us %s      ",
                  frame_timer_cost(FRAME_PHASE_PREP),
                  kokiri_scene_reused() ? "CACHED" : "rebuilt");
        /* Marked when stale: on a cache hit these hold the last rebuild's
        ** figures, not this frame's work. */
        jo_printf(0, 8, "%sdp%u po%u fg%u    ",
                  kokiri_scene_reused() ? "~" : " ",
                  frame_timer_cost(FRAME_PHASE_DEPTH),
                  frame_timer_cost(FRAME_PHASE_PARTITION), frame_timer_cost(FRAME_PHASE_FOG));
        /* copr is the share of recent frames where VDP1's command address
        ** moved between two adjacent reads. It is NOT a busy measurement and
        ** no CPU-versus-fill verdict follows from it -- see frame_timer.h. */
        jo_printf(0, 6, "cam %s copr%u%%  ",
                  oot_follow_legacy() ? "LEGACY 260" : "OoT 125-188",
                  frame_timer_copr_changed());
        /* Closest distance-stippled polygon: index, its tile, near..far
        ** extent, and its first two vertex ids. Tiles are shared, so the
        ** polygon and vertex ids are what identify the surface. */
        jo_printf(0, 9, "msh p%d t%d %d..%d v%u,%u  ",
                  kokiri_scene_mesh_near_polygon(),
                  kokiri_scene_mesh_near_tile(),
                  kokiri_scene_mesh_near_depth(),
                  kokiri_scene_mesh_near_far(),
                  (unsigned int)kokiri_scene_mesh_near_vertex(0),
                  (unsigned int)kokiri_scene_mesh_near_vertex(1));
        return;
    }
    jo_printf(0, 0, "Jo/SGL Kokiri viewer");
#ifdef DOSEI_TEXTURE_PROBE
    jo_printf(0, 0, "TEXTURE PROBE stage %d   ", (int)probe_stage);
#endif
    jo_printf(0, 1, "verts %d tris %d tiles %d",
              KOKIRI_VERTEX_COUNT, KOKIRI_POLYGON_COUNT, KOKIRI_TILE_COUNT);
    jo_printf(0, 2, "cam %d,%d,%d pan %d   ", (int)demo_camera.x, (int)demo_camera.y, (int)demo_camera.z,
              (int)demo_yaw);
    if (demo_link_active)
        jo_printf(0, 8, "link %d,%d,%d yaw %d  ", (int)demo_link.x,
                  (int)(demo_link.y - DEMO_LINK_EYE_HEIGHT), (int)demo_link.z,
                  (int)demo_link_yaw);
    else
        jo_printf(0, 8, "link: press START      ");
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
              demo_collision_indexed ? "ON" : "off (full scan)");
}

void                jo_main(void)
{
    jo_core_init(JO_COLOR_Black);
    frame_timer_init();
#ifdef DOSEI_HIRES
    /* VDP2 samples the existing title/font at half rate vertically. */
    jo_vdp2_zoom_nbg0f(1.0f, 0.5f);
    jo_vdp2_zoom_nbg1f(1.0f, 0.5f);
#endif
    jo_core_set_screens_order(JO_NBG0_SCREEN, JO_NBG1_SCREEN, JO_SPRITE_SCREEN,
                             JO_RBG0_SCREEN, JO_NBG2_SCREEN, JO_NBG3_SCREEN);
    slSetScreenDist(toFIXED(SCREEN_DISTANCE));

    scene_ready = kokiri_scene_load();
    scene_ready = scene_ready && demo_init();
    music_ready = scene_ready && music_init(&music_bank_title);

    jo_core_add_callback(viewer_draw);
    jo_core_run();
}

/*
** END OF FILE
*/
