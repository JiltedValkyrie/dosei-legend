#include <jo/jo.h>
#include "demo.h"

camera_position_t demo_camera;
uint16_t demo_yaw;
int32_t demo_pitch;
static bool title_visible = true;
static unsigned short *prompt;
static volatile unsigned int ticks;
static unsigned int phase, refresh, previous_tick, previous_frame;
static int last_blink = -1;

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
        if (jo_is_pad1_key_down(JO_KEY_START)) title_visible = !title_visible;
    }
    /* 30 Hz gameplay; preserve baseline per-update movement constants.
     * Cap catch-up so a slow frame cannot create a long input stall. */
    steps = elapsed / 2;
    if (steps > 4) { steps = 4; previous_tick = now - now % 2; }
    else previous_tick += steps * 2;
    while (steps--) kokiri_camera_update(&demo_camera, &demo_yaw, &demo_pitch, buttons, false);
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
