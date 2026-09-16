#include <jo/jo.h>
#include "demo.h"
#include "music.h"
#include "music_banks.h"
#include "texture_probe.h"
#include "title_paths.h"
#include "link_anim_state.h"

camera_position_t demo_camera;
uint16_t demo_yaw;
int32_t demo_pitch;
camera_position_t demo_link;
uint16_t demo_link_yaw;
bool demo_link_active;
static int32_t link_velocity_y_q8;
static int32_t link_fall_remainder_q8;
/* Highest point since Link last left the ground, so the drop can be measured
 * at the moment he lands -- that distance is what OoT's landing branch picks
 * the short landing, ordinary landing or roll from. */
static int32_t link_fall_peak_y;
static camera_position_t link_safe_position;
static bool link_safe_position_valid;

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
/* If no walkable floor remains below Link after dropping this far from his
 * last grounded point, collision has let him out of the world. Restore that
 * nearby point rather than relying on one map-wide respawn coordinate. */
#define LINK_VOID_DROP 180
/* Half-fade length for the title->forest switch, in vblanks. */
#define DEMO_MUSIC_FADE_FRAMES 10
static bool title_visible = true;
/* 256 cells of offsets plus one uint16 id per triangle/cell overlap. */
#define COLLISION_INDEX_BYTES (16 * 1024)
static void *collision_index;
bool demo_collision_indexed;
static unsigned short *prompt;
static volatile unsigned int ticks;
static unsigned int phase, refresh, previous_tick;
/* SGL owns the font at B1+0; Jo's allocator does not reserve it. Keep this
 * table at B1+0x1f000, clear of the fixed SGL font and map storage. */
extern void slBackColTable(void *table);
static int last_blink = -1;
/* Diagnostics chord state. demo_diagnostics_toggled is a one-shot the HUD
 * clears, so the chord edge is detected with the rest of the input rather than
 * sampled a second time in main.c. */
static bool diagnostics_chord_held;
bool demo_diagnostics_toggled;

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

static jo_color sky_color(unsigned int row)
{
    unsigned int r, g, b;
    if (row > 239) row = 239;
    r = 151 + (222 - 151) * row / 239;
    g = 157 + (221 - 157) * row / 239;
    b = 108 + (155 - 108) * row / 239;
    return JO_COLOR_RGB(r, g, b);
}

/* Routes are sampled at build time and every interpolated segment is checked
 * against the real collision mesh. Wide framing and roughly 60 units/second
 * replace the old close-up texture probes. */
static void title_showcase_camera(unsigned int tick)
{
    unsigned int shot, total = 0, duration, index, fraction, look;
    unsigned int count;
    const title_point_t *path;
    for (shot = 0; shot < 5; ++shot) total += (title_path_counts[shot]-1)*16;
    tick %= total;
    for (shot = 0; shot < 4; ++shot) {
        duration = (title_path_counts[shot]-1)*16;
        if (tick < duration) break;
        tick -= duration;
    }
    path = title_paths[shot];
    count = title_path_counts[shot];
    index = tick / 16;
    fraction = tick % 16;
    demo_camera.x = path[index].x + (path[index+1].x-path[index].x)*(int)fraction/16;
    demo_camera.y = path[index].y + (path[index+1].y-path[index].y)*(int)fraction/16;
    demo_camera.z = path[index].z + (path[index+1].z-path[index].z)*(int)fraction/16;
    look = index + 8;
    if (look >= count) look = count - 1;
    {
        int lx = path[look].x, lz = path[look].z;
        if (look+1 < count) {
            lx += (path[look+1].x-lx)*(int)fraction/16;
            lz += (path[look+1].z-lz)*(int)fraction/16;
        }
        demo_yaw = kokiri_camera_facing(lx-demo_camera.x, lz-demo_camera.z);
    }
    demo_pitch = 0;
}

static bool recover_link_from_void(void)
{
    int32_t floor;

    if (!link_safe_position_valid ||
        demo_link.y >= link_safe_position.y - LINK_VOID_DROP)
        return false;
    /* A genuine lower landing is still valid. Recovery is only for an open
     * hole with no walkable surface remaining beneath Link's feet. */
    if (kokiri_collision_floor(demo_link.x, demo_link.z,
                               demo_link.y - DEMO_LINK_EYE_HEIGHT, &floor))
        return false;
    demo_link = link_safe_position;
    link_velocity_y_q8 = 0;
    link_fall_remainder_q8 = 0;
    return true;
}

static void demo_vblank(void)
{
    /* BDCLMD=0 keeps the border outside the active picture black. */
    JO_VDP2_TVMD &= (unsigned short)~0x0100;
    phase += 60;
    while (phase >= refresh) { phase -= refresh; ++ticks; }
}

bool demo_init(void)
{
    int length = 0, row;
    collision_triangle_t *collision = (collision_triangle_t *)jo_fs_read_file("FOREST.COL", &length);
    jo_file file;
    jo_img strip;
    jo_color *sky;
    unsigned int sky_lines, sky_row;
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
    /* Olive daylight haze, matched to the forest reference. The back screen
     * leaves NBG1 available for the title without using VDP1 texture space. */
#ifdef DOSEI_HIRES
    sky_lines = 480;
#else
    sky_lines = 240;
#endif
    sky = (jo_color *)(JO_VDP2_VRAM_B1 + 0x1f000);
    /* Some output modes/emulators fetch the full 256/512-line table even
     * with a 240/480-line picture. Unused scanlines are black borders. */
    for (sky_row = 0; sky_row < 512; ++sky_row) sky[sky_row] = JO_COLOR_Black;
    for (sky_row = 0; sky_row < sky_lines; ++sky_row) {
        sky[sky_row] = sky_color(sky_row * 240 / sky_lines);
    }
    /* Kronos extends the last active back colour into its outer viewport.
     * A black final scanline preserves the original black surround there. */
    sky[sky_lines - 1] = JO_COLOR_Black;
    slBackColTable(sky);
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
    bool recenter = false;
    unsigned int now = ticks, elapsed = now - previous_tick, steps;
    jo_img patch;
    if (jo_is_pad1_available()) {
#define MAP(key) if (jo_is_pad1_key_pressed(JO_KEY_##key)) buttons |= CAMERA_##key
        MAP(L); MAP(R); MAP(X); MAP(Y); MAP(Z); MAP(C);
        MAP(UP); MAP(DOWN); MAP(LEFT); MAP(RIGHT);
#undef MAP
        /* L+R held is the diagnostics chord, and it CONSUMES both buttons:
         * the recenter and the R camera bit are cleared, so asking for
         * diagnostics never also recenters the view or triggers whatever R
         * eventually becomes. A is left free for the action button.
         *
         * Held rather than pressed, and edge-detected here, because the pad is
         * sampled once per update and a chord read independently in two files
         * would drift apart on the frame one button arrives before the other. */
        if ((buttons & CAMERA_L) && (buttons & CAMERA_R)) {
            buttons &= (uint16_t)~(CAMERA_L | CAMERA_R);
            if (!diagnostics_chord_held) demo_diagnostics_toggled = true;
            diagnostics_chord_held = true;
        } else {
            diagnostics_chord_held = false;
            recenter = jo_is_pad1_key_down(JO_KEY_L);
        }
        /* Ignore Start while a score switch is running: music_fade_to() would
         * refuse it anyway, and toggling the title regardless would leave the
         * artwork and the music disagreeing about which state we are in. */
        if (jo_is_pad1_key_down(JO_KEY_START) && !music_busy()) {
            title_visible = !title_visible;
            /* Starting the game puts Link in the world. He spawns from the
             * same collision search the free camera used, so he stands on a
             * real floor rather than at an assumed height. */
            /* Follow the title with the score, both ways. music_fade_to()
             * refuses while a switch is running, so held or repeated presses
             * cannot stack transitions. The fade length is the caller's
             * choice, not baked into the player. */
            music_fade_to(title_visible ? &music_bank_title
                                        : &music_bank_kokiri,
                          DEMO_MUSIC_FADE_FRAMES);
            if (!title_visible && !demo_link_active) {
                if (kokiri_collision_spawn(&demo_link)) {
                    demo_link_yaw = demo_yaw;
                    link_velocity_y_q8 = 0;
                    link_fall_remainder_q8 = 0;
                    link_fall_peak_y = demo_link.y;
                    link_safe_position = demo_link;
                    link_safe_position_valid = true;
                    demo_link_active = true;
                    /* Spawn standing, not mid-clip from a previous session.
                     * Both calls are needed: one clears the cached pose, the
                     * other the locomotion state that selects it. */
                    link_anim_reset();
                    link_anim_reset_state();
                    kokiri_camera_reset_actor_motion();
                }
            }
            if (!title_visible && demo_link_active) {
                int32_t sine, cosine;
                /* A title shot may be far across the map. Enter gameplay
                 * directly behind Link instead of easing there for seconds. */
                kokiri_camera_sincos(demo_yaw, &sine, &cosine);
                demo_camera.x = demo_link.x
                    - (int32_t)(((int64_t)sine * FOLLOW_DISTANCE) >> 16);
                demo_camera.z = demo_link.z
                    - (int32_t)(((int64_t)cosine * FOLLOW_DISTANCE) >> 16);
                demo_camera.y = demo_link.y + FOLLOW_HEIGHT;
            }
        }
    }
    /* 30 Hz gameplay; movement uses time-scaled native world units.
     * Cap catch-up so a slow frame cannot create a long input stall. */
    steps = elapsed / 2;
    if (steps > 4) { steps = 4; previous_tick = now - now % 2; }
    else previous_tick += steps * 2;
    if (title_visible) {
        /* This is an authored title shot, so controller movement does not
         * knock it off its route. Start above has already switched state by
         * the time gameplay reaches this branch. */
        title_showcase_camera(now);
    } else if (demo_link_active) {
        /* Drive Link with the baseline movement code, then follow him. Only
         * the walk/turn buttons reach it: the free camera's raise/lower and
         * pitch keys would move a character who must stay on the floor.
         *
         * The yaw handed to kokiri_camera_update is the CAMERA's. R turns
         * the view, L recenters, and the D-pad walks relative to it. Link's facing
         * is not steered by the camera -- it follows wherever he actually
         * moved, which is what keeps turning the view from spinning him. */
        uint16_t walk = buttons & (CAMERA_UP | CAMERA_DOWN | CAMERA_LEFT |
                                   CAMERA_RIGHT | CAMERA_R);
        int32_t unused_pitch = 0, sine, cosine, tx, tz, ty;
        int32_t was_x = demo_link.x, was_z = demo_link.z;
        bool recovered = false;
        if (recenter) {
            demo_yaw = demo_link_yaw;
            demo_pitch = 0;
        }
        while (steps--) {
            bool grounded;
            int32_t step_x = demo_link.x, step_z = demo_link.z;
            int32_t dx, dz, moved, fell;
            kokiri_camera_update(&demo_link, &demo_yaw, &unused_pitch, walk,
                                 false, true);
            grounded = kokiri_collision_fall(&demo_link, &link_velocity_y_q8,
                                              &link_fall_remainder_q8);
            /* Actual travel length, not the largest axis: diagonal running
             * must select the same clip and cadence as straight running. */
            dx = demo_link.x - step_x;
            if (dx < 0) dx = -dx;
            dz = demo_link.z - step_z;
            if (dz < 0) dz = -dz;
            moved = 0;
            while ((moved + 1) * (moved + 1) <= dx * dx + dz * dz)
                ++moved;

            if (grounded) {
                /* The peak still holds the height he left the ground from, so
                 * this is the whole drop. It is only meaningful on the step he
                 * lands; link_anim_update() ignores it otherwise. */
                fell = link_fall_peak_y - demo_link.y;
                if (fell < 0) fell = 0;
                link_safe_position = demo_link;
                link_safe_position_valid = true;
            } else {
                fell = 0;
                if (recover_link_from_void())
                    recovered = true;
            }
            link_anim_update(moved, grounded, fell, false);
            /* Follow him while he is on the ground, so the next departure
             * measures from where he actually left. Left alone while airborne,
             * which is what makes the landing drop the full fall. */
            if (grounded)
                link_fall_peak_y = demo_link.y;
        }
        /* Pose once for the frame, after the catch-up steps have settled on a
         * final state -- not inside the loop, and not in the draw callback.
         * Skinning is the most expensive thing Link costs, so it runs once per
         * frame at most, and only when the clip frame actually changed. */
        link_anim_pose(link_anim_clip(), link_anim_frame(), link_anim_fraction());
        if (demo_link.x != was_x || demo_link.z != was_z)
            demo_link_yaw = kokiri_camera_facing(demo_link.x - was_x,
                                                 demo_link.z - was_z);
        kokiri_camera_sincos(demo_yaw, &sine, &cosine);
        /* Forward is (sin,cos), matching kokiri_camera_update's movement
         * basis, so the view sits directly behind the camera heading. */
        tx = demo_link.x - (int32_t)(((int64_t)sine * FOLLOW_DISTANCE) >> 16);
        tz = demo_link.z - (int32_t)(((int64_t)cosine * FOLLOW_DISTANCE) >> 16);
        ty = demo_link.y + FOLLOW_HEIGHT;
        if (recovered || recenter) {
            /* Keep the recovered player visible immediately; easing from a
             * camera left down in the void would briefly show empty space. */
            demo_camera.x = tx;
            demo_camera.y = ty;
            demo_camera.z = tz;
        } else {
            demo_camera.x = follow_approach(demo_camera.x, tx);
            demo_camera.y = follow_approach(demo_camera.y, ty);
            demo_camera.z = follow_approach(demo_camera.z, tz);
        }
    } else {
        while (steps--) kokiri_camera_update(&demo_camera, &demo_yaw,
                                             &demo_pitch, buttons, false,
                                             false);
    }
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

bool demo_title_is_visible(void)
{
    return title_visible;
}

unsigned int demo_clock(void)
{
    return ticks;
}
