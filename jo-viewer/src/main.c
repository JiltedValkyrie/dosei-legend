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
** Its projection is sy = 120 - offset(py), so +Y is up. The SGL target is
** therefore the viewpoint pushed along +Z.
**
** Whether SGL agrees on handedness is NOT assumed -- confirming the view
** matches the baseline, floor included, is what the first Kronos run is for.
*/
#define CAM_X               (-300)
#define CAM_Y               (91)
#define CAM_Z               (0)
#define CAM_TARGET_X        (CAM_X)
#define CAM_TARGET_Y        (CAM_Y)
#define CAM_TARGET_Z        (CAM_Z + 100)

static jo_camera    cam;
static bool         scene_ready;

static void         viewer_draw(void)
{
    if (!scene_ready)
    {
        jo_printf(2, 2, "scene load FAILED");
        return ;
    }

    jo_3d_camera_look_at(&cam);
    kokiri_scene_draw();
}

static void         viewer_hud(void)
{
    jo_printf(0, 0, "Jo/SGL Kokiri viewer");
    jo_printf(0, 1, "verts %d tris %d tiles %d",
              KOKIRI_VERTEX_COUNT, KOKIRI_POLYGON_COUNT, KOKIRI_TILE_COUNT);
    jo_printf(0, 26, "cam %d,%d,%d yaw/pitch 0", CAM_X, CAM_Y, CAM_Z);
    jo_printf(0, 27, "vdp1 %d B  drawn %d  ",
              (int)kokiri_scene_vram_used(), jo_3d_get_polygon_count());
}

void                jo_main(void)
{
    jo_core_init(JO_COLOR_Black);

    jo_3d_camera_init(&cam);
    jo_3d_camera_set_viewpoint(&cam, CAM_X, CAM_Y, CAM_Z);
    jo_3d_camera_set_target(&cam, CAM_TARGET_X, CAM_TARGET_Y, CAM_TARGET_Z);

    scene_ready = kokiri_scene_load();

    jo_core_add_callback(viewer_draw);
    jo_core_add_callback(viewer_hud);
    jo_core_run();
}

/*
** END OF FILE
*/
