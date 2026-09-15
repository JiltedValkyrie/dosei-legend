/*
 * Kokiri Forest (spot04) collision mesh as a wireframe panorama behind the
 * title, drawn with VDP1 lines at a lower sprite priority than NBG0 (whose
 * black background is keyed transparent - see main.c). Geometry comes
 * straight from the OoT decomp's collision header (world-space s16 vertices
 * + triangle indices), downsampled and deduped into an edge list host-side -
 * see tools/make_kokiri_wireframe.py.
 *
 * The camera sits at the middle of the mesh looking outward and yaws slowly,
 * so this is a first-person pan around the forest rather than an orbit of it
 * from outside. That means a real perspective divide and near-plane culling:
 * with the camera inside the geometry, a good half of the mesh is behind it
 * on any given frame, and projecting those points would smear lines across
 * the screen.
 */

#include "kokiri_wireframe.h"
#include "kokiri_wireframe_data.h"

#include <string.h>

extern uint8_t asset_kokiri_verts_raw[];
extern uint8_t asset_kokiri_edges_raw[];

#define WIREFRAME_CENTER_X         160
#define WIREFRAME_CENTER_Y         112

/* 65536 angle_t units per revolution; 24/frame at 60fps is ~45s per full
 * turn - a slow drift rather than a spin. */
#define WIREFRAME_ROT_STEP         24

/* Camera sits at the middle of the mesh's bounds, looking outward. */
#define WIREFRAME_CAM_X ((KOKIRI_WIREFRAME_BOUNDS_MIN_X + KOKIRI_WIREFRAME_BOUNDS_MAX_X) / 2)
#define WIREFRAME_CAM_Y ((KOKIRI_WIREFRAME_BOUNDS_MIN_Y + KOKIRI_WIREFRAME_BOUNDS_MAX_Y) / 2)
#define WIREFRAME_CAM_Z ((KOKIRI_WIREFRAME_BOUNDS_MIN_Z + KOKIRI_WIREFRAME_BOUNDS_MAX_Z) / 2)

/* Focal length in pixels: 220 over a 320px-wide screen is roughly a 72
 * degree horizontal field of view. */
#define WIREFRAME_FOCAL            220
#define WIREFRAME_NEAR_Z           40

/* Projected points just past the near plane can land enormously far off
 * screen; VDP1 wants sane coordinates, so clamp to a generous margin. */
#define WIREFRAME_CLAMP_MIN_X      (-320)
#define WIREFRAME_CLAMP_MAX_X      640
#define WIREFRAME_CLAMP_MIN_Y      (-224)
#define WIREFRAME_CLAMP_MAX_Y      448

#define WIREFRAME_SPRITE_PRIO_REG  0
#define WIREFRAME_SPRITE_PRIORITY  3  /* below NBG0's priority (7) - see main.c */
#define WIREFRAME_COLOR            RGB1555(1, 10, 24, 14)

#define WIREFRAME_ORDER_SYSTEM_CLIP 0
#define WIREFRAME_ORDER_LOCAL_COORD 1
#define WIREFRAME_ORDER_FIRST_LINE  2
#define WIREFRAME_ORDER_COUNT       (WIREFRAME_ORDER_FIRST_LINE + KOKIRI_WIREFRAME_EDGE_COUNT + 1)

typedef struct {
        int16_t x;
        int16_t y;
        int16_t z;
} raw_vertex_t;

typedef struct {
        uint16_t a;
        uint16_t b;
} raw_edge_t;

static vdp1_cmdt_list_t *_cmdt_list;
static int16_vec2_t _screen_pts[KOKIRI_WIREFRAME_VERTEX_COUNT];
static bool _pt_visible[KOKIRI_WIREFRAME_VERTEX_COUNT];
static angle_t _angle = 0;

static inline int32_t
_clamp(int32_t v, int32_t lo, int32_t hi)
{
        if (v < lo) {
                return lo;
        }

        if (v > hi) {
                return hi;
        }

        return v;
}

void
kokiri_wireframe_init(void)
{
        vdp2_sprite_priority_set(WIREFRAME_SPRITE_PRIO_REG, WIREFRAME_SPRITE_PRIORITY);

        vdp1_env_t env;
        vdp1_env_default_init(&env);
        env.erase_color = RGB1555(0, 0, 0, 0);
        vdp1_env_set(&env);

        _cmdt_list = vdp1_cmdt_list_alloc(WIREFRAME_ORDER_COUNT);
        (void)memset(&_cmdt_list->cmdts[0], 0x00, sizeof(vdp1_cmdt_t) * WIREFRAME_ORDER_COUNT);
        _cmdt_list->count = WIREFRAME_ORDER_COUNT;

        vdp1_cmdt_t * const cmdts = &_cmdt_list->cmdts[0];

        static const int16_vec2_t system_clip_coord =
            INT16_VEC2_INITIALIZER(320 - 1, 224 - 1);

        vdp1_cmdt_system_clip_coord_set(&cmdts[WIREFRAME_ORDER_SYSTEM_CLIP]);
        vdp1_cmdt_vtx_system_clip_coord_set(&cmdts[WIREFRAME_ORDER_SYSTEM_CLIP], system_clip_coord);

        static const int16_vec2_t no_offset = INT16_VEC2_INITIALIZER(0, 0);

        vdp1_cmdt_local_coord_set(&cmdts[WIREFRAME_ORDER_LOCAL_COORD]);
        vdp1_cmdt_vtx_local_coord_set(&cmdts[WIREFRAME_ORDER_LOCAL_COORD], no_offset);

        const vdp1_cmdt_draw_mode_t draw_mode = {
                .raw = 0x0000
        };

        for (uint32_t i = 0; i < KOKIRI_WIREFRAME_EDGE_COUNT; i++) {
                vdp1_cmdt_t * const cmdt = &cmdts[WIREFRAME_ORDER_FIRST_LINE + i];

                vdp1_cmdt_line_set(cmdt);
                vdp1_cmdt_color_set(cmdt, WIREFRAME_COLOR);
                vdp1_cmdt_draw_mode_set(cmdt, draw_mode);
        }

        vdp1_cmdt_end_set(&cmdts[WIREFRAME_ORDER_COUNT - 1]);
}

void
kokiri_wireframe_update_and_draw(void)
{
        fix16_mat33_t rot;
        fix16_mat33_y_rotation_create(_angle, &rot);

        const raw_vertex_t * const verts = (const raw_vertex_t *)asset_kokiri_verts_raw;

        for (uint32_t i = 0; i < KOKIRI_WIREFRAME_VERTEX_COUNT; i++) {
                fix16_vec3_t v;
                v.x = fix16_int32_from(verts[i].x - WIREFRAME_CAM_X);
                v.y = fix16_int32_from(verts[i].y - WIREFRAME_CAM_Y);
                v.z = fix16_int32_from(verts[i].z - WIREFRAME_CAM_Z);

                fix16_vec3_t rotated;
                fix16_mat33_vec3_mul(&rot, &v, &rotated);

                /* Back to plain ints before the projection: world coords run
                 * to a few thousand units, so scaling them by the focal
                 * length in fix16 would overflow Q16.16. */
                const int32_t rz = fix16_int32_to(rotated.z);

                if (rz < WIREFRAME_NEAR_Z) {
                        _pt_visible[i] = false;
                        continue;
                }

                const int32_t rx = fix16_int32_to(rotated.x);
                const int32_t ry = fix16_int32_to(rotated.y);

                const int32_t px = WIREFRAME_CENTER_X + ((rx * WIREFRAME_FOCAL) / rz);
                const int32_t py = WIREFRAME_CENTER_Y - ((ry * WIREFRAME_FOCAL) / rz);

                _screen_pts[i].x = (int16_t)_clamp(px, WIREFRAME_CLAMP_MIN_X, WIREFRAME_CLAMP_MAX_X);
                _screen_pts[i].y = (int16_t)_clamp(py, WIREFRAME_CLAMP_MIN_Y, WIREFRAME_CLAMP_MAX_Y);
                _pt_visible[i] = true;
        }

        const raw_edge_t * const edges = (const raw_edge_t *)asset_kokiri_edges_raw;
        vdp1_cmdt_t * const cmdts = &_cmdt_list->cmdts[0];

        /* Parked well outside the system clip, so culled edges cost a
         * clipped-away command rather than needing the list resized. */
        static const int16_vec2_t culled = INT16_VEC2_INITIALIZER(-100, -100);

        for (uint32_t i = 0; i < KOKIRI_WIREFRAME_EDGE_COUNT; i++) {
                const uint16_t a = edges[i].a;
                const uint16_t b = edges[i].b;

                int16_vec2_t pts[4];

                if (_pt_visible[a] && _pt_visible[b]) {
                        pts[0] = _screen_pts[a];
                        pts[1] = _screen_pts[b];
                } else {
                        pts[0] = culled;
                        pts[1] = culled;
                }

                pts[2] = pts[1];
                pts[3] = pts[1];

                vdp1_cmdt_vtx_set(&cmdts[WIREFRAME_ORDER_FIRST_LINE + i], pts);
        }

        /* VDP1 double-buffers and erases each frame, so the list has to be
         * resubmitted and rendered every frame to stay on screen. */
        vdp1_sync_cmdt_list_put(_cmdt_list, 0);
        vdp1_sync_render();
        vdp1_sync();

        _angle = (angle_t)(_angle + WIREFRAME_ROT_STEP);
}
