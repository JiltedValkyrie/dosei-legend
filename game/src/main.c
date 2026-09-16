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
    demo_update();
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
    kokiri_scene_draw();
    kokiri_fairies_draw(demo_clock());
    /* Link is submitted after the forest so the per-frame counters, which
    ** kokiri_scene_draw() resets, cover both lists. His model origin is at his
    ** feet, EYE_HEIGHT below the collision position. */
    if (demo_link_active && !demo_title_is_visible())
        kokiri_link_draw(demo_link.x, demo_link.y - DEMO_LINK_EYE_HEIGHT,
                         demo_link.z, demo_link_yaw);
    rejected_total += kokiri_scene_rejected();
    viewer_hud();
}

static void         viewer_hud(void)
{
    if (jo_is_pad1_available() && jo_is_pad1_key_down(JO_KEY_A)) {
        debug_visible = !debug_visible;
        jo_clear_screen();
    }
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
            jo_printf(0, 1, "L %d,%d yaw %d  C %d,%d pan %d   ",
                      (int)demo_link.x, (int)demo_link.z, (int)demo_link_yaw,
                      (int)demo_camera.x, (int)demo_camera.z, (int)demo_yaw);
        /* Heap headroom and the current locomotion state. The heap figure is
        ** what justifies JO_GLOBAL_MEMORY_SIZE_FOR_MALLOC: the clip tables and
        ** the skinned POINT table compete with it for the RAM below SGL's work
        ** area, so it was trimmed to measured demand rather than guessed. */
        {
            /* Assigned first: casting an enum-returning call directly trips
            ** -Wbad-function-cast, and this build treats warnings as noise to
            ** stay out of. */
            link_state_t pose = link_anim_state();
            jo_printf(0, 2, "heap %d%%  anim %d f%d    ",
                      jo_memory_usage_percent(), (int)pose,
                      (int)link_anim_frame());
            /* g=grounded now, L=landings seen, d=the fall distance the last
            ** landing decided on. If Link rolls without input, L climbing on
            ** flat ground is the evidence, and d says which gate selected it. */
            jo_printf(0, 3, "g%d L%d d%d        ",
                      link_anim_last_grounded() ? 1 : 0,
                      (int)link_anim_landings(),
                      (int)link_anim_last_fall());
        }
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
