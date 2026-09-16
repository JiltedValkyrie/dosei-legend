#include <jo/jo.h>
#include "demo.h"

camera_position_t demo_camera;
uint16_t demo_yaw;
int32_t demo_pitch;
camera_position_t demo_link;
uint16_t demo_link_yaw;
bool demo_link_active;

/* Third-person follow: how far behind and above Link the view sits, and how
 * hard it chases him. FOLLOW_LAG is a shift: the camera closes 1/(1<<LAG) of
 * the remaining distance per update, which trails him slightly instead of
 * moving rigidly. */
#define FOLLOW_DISTANCE 260
/* Relative to Link's collision position, which is his eye at floor+90. A level
 * camera frames him only if it sits near his mid-body: at 260 behind, the view
 * puts screen y at 120 + 240*(camera_y - point_y)/260, so -40 lands his feet
 * near y=166 and his head near y=109 -- centred, with no pitch needed. Pitching
 * a higher camera down would frame him too, but the sign of demo_pitch is not
 * established here, and a wrong guess loses him off-screen entirely. */
#define FOLLOW_HEIGHT   (-40)
#define FOLLOW_LAG      2
static bool title_visible = true;
/* 256 cells of offsets plus one uint16 id per triangle/cell overlap. */
#define COLLISION_INDEX_BYTES (16 * 1024)
static void *collision_index;
bool demo_collision_indexed;
static unsigned short *prompt;
static volatile unsigned int ticks;
static unsigned int phase, refresh, previous_tick, previous_frame;
static int last_blink = -1;

/* Move one axis a fraction of the way to its target. The >> alone stalls a few
 * units short, because a difference under (1<<FOLLOW_LAG) shifts to zero and
 * the camera never finishes closing; step at least one unit while any gap
 * remains. */
static int32_t follow_approach(int32_t current, int32_t target)
{
    int32_t delta = target - current;
    int32_t step = delta >> FOLLOW_LAG;
    if (step == 0 && delta != 0) step = delta > 0 ? 1 : -1;
    return current + step;
}

static void demo_vblank(void)
{
    phase += 60;
    while (phase >= refresh) { phase -= refresh; ++ticks; }
}

bool demo_init(void)
{
    int length = 0, row;
    collision_triangle_t *collision = (collision_triangle_t *)jo_fs_read_file("FOREST.COL", &length);
    jo_file file;
    jo_img strip;
    if (!collision || length <= 0 || length % sizeof(*collision)) return false;
    kokiri_collision_init(collision, length / sizeof(*collision));
    /* Bucket the 1692 collision triangles by XZ so walking does not rescan all
     * of them. Movement runs up to 8 swept queries per update (two axes x four
     * 4-unit steps) and each query previously touched every triangle, which is
     * why moving cost far more frame time than turning. Failure is survivable:
     * the queries fall back to the original full scan. */
    collision_index = jo_malloc(COLLISION_INDEX_BYTES);
    if (collision_index)
        demo_collision_indexed = kokiri_collision_index(collision_index,
                                                   COLLISION_INDEX_BYTES);
    if (!kokiri_collision_spawn(&demo_camera)) return false;
    /* Raise the starting eye without bypassing walls/ceilings. */
    kokiri_collision_move(&demo_camera, 0, 24, 0);
    if (!jo_fs_open(&file, "TITLE.RGB")) return false;
    if (file.size != 512 * 256 * 2) { jo_fs_close(&file); return false; }
    strip.width = 512; strip.height = 1;
    strip.data = jo_malloc(1024);
    if (!strip.data) { jo_fs_close(&file); return false; }
    jo_clear_background(0);
    for (row = 0; row < 256; ++row) {
        if (jo_fs_read_next_bytes(&file, (char *)strip.data, 1024) != 1024) {
            jo_fs_close(&file); jo_free(strip.data); return false;
        }
        jo_set_background_sprite(&strip, 0, row);
    }
    jo_fs_close(&file);
    jo_free(strip.data);
    prompt = (unsigned short *)jo_fs_read_file("START.RGB", &length);
    if (!prompt || length != 84 * 14 * 2) return false;
    refresh = (JO_VDP2_TVSTAT & 1) ? 50 : 60;
    return jo_core_add_vblank_callback(demo_vblank) != 0;
}

void demo_update(void)
{
    uint16_t buttons = 0;
    unsigned int now = ticks, elapsed = now - previous_tick, steps;
    jo_img patch;
    if (jo_is_pad1_available()) {
#define MAP(key) if (jo_is_pad1_key_pressed(JO_KEY_##key)) buttons |= CAMERA_##key
        MAP(L); MAP(R); MAP(X); MAP(Y); MAP(Z); MAP(C);
        MAP(UP); MAP(DOWN); MAP(LEFT); MAP(RIGHT);
#undef MAP
        if (jo_is_pad1_key_down(JO_KEY_START)) {
            title_visible = !title_visible;
            /* Starting the game puts Link in the world. He spawns from the
             * same collision search the free camera used, so he stands on a
             * real floor rather than at an assumed height. */
            if (!title_visible && !demo_link_active) {
                if (kokiri_collision_spawn(&demo_link)) {
                    int32_t sine, cosine;
                    demo_link_yaw = demo_yaw;
                    /* Snap the view behind him on the first frame; the lag
                     * below should trail his movement, not the spawn jump. */
                    kokiri_camera_sincos(demo_yaw, &sine, &cosine);
                    demo_camera.x = demo_link.x
                        - (int32_t)(((int64_t)sine * FOLLOW_DISTANCE) >> 16);
                    demo_camera.z = demo_link.z
                        - (int32_t)(((int64_t)cosine * FOLLOW_DISTANCE) >> 16);
                    demo_camera.y = demo_link.y + FOLLOW_HEIGHT;
                    demo_link_active = true;
                }
            }
        }
    }
    /* 30 Hz gameplay; preserve baseline per-update movement constants.
     * Cap catch-up so a slow frame cannot create a long input stall. */
    steps = elapsed / 2;
    if (steps > 4) { steps = 4; previous_tick = now - now % 2; }
    else previous_tick += steps * 2;
    if (demo_link_active) {
        /* Drive Link with the baseline movement code, then follow him. Only
         * the walk/turn buttons reach it: the free camera's raise/lower and
         * pitch keys would move a character who must stay on the floor.
         *
         * The yaw handed to kokiri_camera_update is the CAMERA's, so L/R turn
         * the view and the D-pad walks him relative to it. Link's own facing
         * is not steered by the camera -- it follows wherever he actually
         * moved, which is what keeps turning the view from spinning him. */
        uint16_t walk = buttons & (CAMERA_UP | CAMERA_DOWN | CAMERA_LEFT |
                                   CAMERA_RIGHT | CAMERA_L | CAMERA_R);
        int32_t unused_pitch = 0, sine, cosine, tx, tz, ty;
        int32_t was_x = demo_link.x, was_z = demo_link.z;
        while (steps--)
            kokiri_camera_update(&demo_link, &demo_yaw, &unused_pitch, walk, false);
        if (demo_link.x != was_x || demo_link.z != was_z)
            demo_link_yaw = kokiri_camera_facing(demo_link.x - was_x,
                                                 demo_link.z - was_z);
        kokiri_camera_sincos(demo_yaw, &sine, &cosine);
        /* Forward is (sin,cos), matching kokiri_camera_update's movement
         * basis, so the view sits directly behind the camera heading. */
        tx = demo_link.x - (int32_t)(((int64_t)sine * FOLLOW_DISTANCE) >> 16);
        tz = demo_link.z - (int32_t)(((int64_t)cosine * FOLLOW_DISTANCE) >> 16);
        ty = demo_link.y + FOLLOW_HEIGHT;
        demo_camera.x = follow_approach(demo_camera.x, tx);
        demo_camera.y = follow_approach(demo_camera.y, ty);
        demo_camera.z = follow_approach(demo_camera.z, tz);
    } else {
        while (steps--) kokiri_camera_update(&demo_camera, &demo_yaw, &demo_pitch, buttons, false);
    }
    if (title_visible && !buttons) demo_yaw += (uint16_t)((now - previous_frame) * CAMERA_AUTO_TURN_SPEED);
    previous_frame = now;
    patch.width = 84; patch.height = 14; patch.data = prompt;
    /* Only upload on a blink transition, not every rendered frame. */
    if (last_blink != (int)((now / 30) & 1)) {
    last_blink = (now / 30) & 1;
    if (last_blink) {
        unsigned short empty[84] = {0};
        int row;
        patch.height = 1; patch.data = empty;
        for (row = 173; row < 187; ++row) jo_set_background_sprite(&patch, 118, row);
    } else jo_set_background_sprite(&patch, 118, 173);
    }
    slScrAutoDisp(NBG0ON | (title_visible ? NBG1ON : 0));
}
