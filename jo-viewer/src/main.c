/*
** Isolated Jo Engine / SGL Kokiri Forest viewer.
**
** Step 3 of docs/JOENGINE_PORT.md: render one fixed, textured Kokiri view
** through SGL so its output and cost can be compared against the unchanged
** libyaul baseline. No controls, no collision, no audio yet -- those only come
** across once this view is confirmed correct (step 5).
**
** Resolution is TV_320x240 (jo/conf.h, NTSC non-480i), matching the libyaul
** build's 320x240 viewport, so the comparison needs no video-mode change.
*/

#include <jo/jo.h>

#include "kokiri_scene.h"
#include "kokiri_sgl.h"

/*
** Baseline camera, in the scene's native source space.
**
** Position: kokiri_collision_spawn() in the libyaul build searches outward
** from x=-300,z=0 and derives y from the floor plus EYE_HEIGHT (90). Replaying
** that search over FOREST.BIN's 1692 collision triangles lands on ring 0 with
** floor y=1, giving (-300, 91, 0) -- the pose the handoff documents. The
** viewer has no collision yet (step 5), so the result is pinned here.
**
** Facing: at yaw 0 the baseline's Y-rotation matrix is identity and it uses
** the rotated z as depth (kokiri_scene.c:160-171), so yaw 0 looks along +Z.
** Its projection is sy = 120 - offset(py), so +Y is up. SGL projects +Y
** downward: the fixed view must be (x-CAM_X, CAM_Y-y, z-CAM_Z).
*/
#define CAM_X               (-300)
#define CAM_Y               (91)
#define CAM_Z               (0)
#define SCREEN_DISTANCE     (240)
static bool         scene_ready;
static void         viewer_hud(void);

static void         viewer_draw(void)
{
    if (!scene_ready)
    {
        jo_printf(2, 2, "scene load FAILED");
        return ;
    }

    /* Pure translation: the Y negation that SGL's Y-down projection needs is
    ** baked into the POINT table by the converter, so slScale(1,-1,1) is gone.
    ** eye.y - y is exactly (-y) + eye.y, so this translation is unchanged.
    ** Keeping the matrix free of reflections is what lets the generated face
    ** normals stay meaningful, which Single_Plane culling depends on. */
    jo_3d_translate_matrix(-CAM_X, CAM_Y, -CAM_Z);
    kokiri_scene_draw();
    viewer_hud();
}

static void         viewer_hud(void)
{
    jo_printf(0, 0, "Jo/SGL Kokiri viewer");
    jo_printf(0, 1, "verts %d tris %d tiles %d",
              KOKIRI_VERTEX_COUNT, KOKIRI_POLYGON_COUNT, KOKIRI_TILE_COUNT);
    jo_printf(0, 2, "cam %d,%d,%d yaw/pitch 0", CAM_X, CAM_Y, CAM_Z);
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
}

void                jo_main(void)
{
    jo_core_init(JO_COLOR_Black);
    jo_core_set_screens_order(JO_NBG0_SCREEN, JO_NBG2_SCREEN, JO_SPRITE_SCREEN,
                             JO_RBG0_SCREEN, JO_NBG1_SCREEN, JO_NBG3_SCREEN);
    slSetScreenDist(toFIXED(SCREEN_DISTANCE));

    scene_ready = kokiri_scene_load();

    jo_core_add_callback(viewer_draw);
    jo_core_run();
}

/*
** END OF FILE
*/
