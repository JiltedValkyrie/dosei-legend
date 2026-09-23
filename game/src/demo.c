#include <jo/jo.h>
#include "demo.h"
#include "music.h"
#include "music_banks.h"
#include "texture_probe.h"
#include "title_paths.h"
#include "link_anim_state.h"
#include "action_audio.h"
#include "oot_follow.h"
#include "frame_timer.h"
#include "input_edge.h"
#include "player_input.h"
#include "gameplay.h"
#include "file_select.h"
#include "scene_flow.h"
#include "save_state.h"
#include "save_device.h"
#include "game_mode.h"
#include "cutscene.h"
#include "kokiri_sgl.h"
#include "navi.h"

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

/* Link's follow camera state. Geometry and easing rates come from OoT's
 * Normal1; see shared/lib/camera/oot_follow.c for the derivation. */
static oot_follow_t link_follow;
/* If no walkable floor remains below Link after dropping this far from his
 * last grounded point, collision has let him out of the world. Restore that
 * nearby point rather than relying on one map-wide respawn coordinate. */
#define LINK_VOID_DROP 180
/* Half-fade length for the title->forest switch, in vblanks. */
#define DEMO_MUSIC_FADE_FRAMES 10
/* Which screen we are on now lives in game_mode.c, which also says which screen
 * may follow which. These two read it rather than tracking it a second time:
 * the pair of booleans they replaced could encode a state -- both set -- that
 * nothing prevented and nothing could draw.
 *
 * The file select sits between the title and play: Start leaves the title to
 * it, and only choosing a file there puts Link in the world. It owns the pad
 * while it is up, exactly as the pause menu does. */
#define title_visible       (game_mode() == GAME_MODE_TITLE)
#define file_select_visible (game_mode() == GAME_MODE_FILE_SELECT)
/* Which file the player is playing, so SAVE in the pause menu writes back to
 * the slot they chose rather than to a fixed one. */
static uint8_t active_slot;
/* Last save attempt, for the pause panel. Persistent, not a one-step event:
 * the player needs to still see it after the step that raised it. */
static bool save_reported, save_succeeded;
/* The collision index itself lives in scene_flow.c, which owns the collision
** data and rebuilds the index whenever a scene is loaded. This is only the
** diagnostic mirror the HUD prints. */
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
bool demo_diagnostics_toggled;
static input_edge_t start_edge;
static bool jump_pending;
/* Action intents latched from the sampled input, consumed once per fixed step
 * exactly like jump_pending. A short X tap must survive a slow rendered frame. */
static bool attack_pending;
static bool interact_pending;
static bool cancel_pending;
static bool pause_pending;
static int8_t menu_step;
static bool shield_held;
/* L held. Not an edge: hold targeting needs the button state every step. */
static bool target_held;
static unsigned int cutscene_phase;
/* The vblank the cutscene clock last consumed.
**
** It cannot share previous_tick with the 30 Hz gameplay step: that one only
** ever advances in whole pairs of vblanks (steps * 2), so an odd tick is left
** on the counter and the cutscene, which reads the raw difference, counts it
** a second time on the next frame. The dream ran about half again too fast. */
static unsigned int cutscene_tick;
/* Pending actions whose gameplay systems do not exist yet. Counted rather than
 * dropped so the HUD/tests can show the input arrived, and deliberately not
 * wired to any substitute behavior. */
unsigned int demo_interact_requests;
unsigned int demo_attack_requests;
player_c_button_t demo_last_c_button;

static jo_color sky_color(unsigned int row)
{
    unsigned int r, g, b;
    if (row > 239) row = 239;
    r = 151 + (222 - 151) * row / 239;
    g = 157 + (221 - 157) * row / 239;
    b = 108 + (155 - 108) * row / 239;
    return JO_COLOR_RGB(r, g, b);
}

/* The nightmare's own environment has fog RGB (0,20,35). Until its cloud
 * skybox is imported, use that horizon colour rather than Kokiri daylight. */
static void cutscene_sky_update(void)
{
    static int last_nightmare = -1;
    int nightmare = cutscene_is_playing() && cutscene_id() == CUTSCENE_NIGHTMARE;
    unsigned int row, lines = 240;
    volatile jo_color *sky = (volatile jo_color *)(JO_VDP2_VRAM_B1 + 0x1f000);
#ifdef DOSEI_HIRES
    lines = 480;
#endif
    if (last_nightmare == nightmare) return;
    last_nightmare = nightmare;
    for (row = 0; row < lines - 1; ++row)
        sky[row] = nightmare ? JO_COLOR_RGB(0, 20, 35) : sky_color(row * 240 / lines);
}

/* Authored travelling shots: 10 seconds each, fairy subjects beside logo.
 * Interpolate baked headings, not the rounded path tangent (which wobbled).
 * All runtime math is integer; offline builder checks every flight segment. */
static void title_showcase_camera(unsigned int tick)
{
    unsigned int shot = (tick / TITLE_SHOT_TICKS) % TITLE_SHOT_COUNT;
    unsigned int scaled = (tick % TITLE_SHOT_TICKS) * 64;
    unsigned int index = scaled / TITLE_SHOT_TICKS;
    int fraction = scaled % TITLE_SHOT_TICKS;
    const title_point_t *a = &title_paths[shot][index];
    const title_point_t *b = a + 1;
    demo_camera.x = a->x + (b->x-a->x)*fraction/TITLE_SHOT_TICKS;
    demo_camera.y = a->y + (b->y-a->y)*fraction/TITLE_SHOT_TICKS;
    demo_camera.z = a->z + (b->z-a->z)*fraction/TITLE_SHOT_TICKS;
    demo_yaw = (uint16_t)(a->yaw + (int16_t)(b->yaw-a->yaw)*fraction/TITLE_SHOT_TICKS);
    demo_pitch = a->pitch + (b->pitch-a->pitch)*fraction/TITLE_SHOT_TICKS;
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

/* Put Link in the world. Called when the file select settles on a file, for
 * both a new game and a continue -- the spawn is the same, only the quest
 * state behind it differs.
 *
 * He spawns from the same collision search the free camera used, so he stands
 * on a real floor rather than at an assumed height. */
/* Plant the follow camera behind Link without easing.
 *
 * The ONLY places that advance the camera are this snap and the one call
 * inside the fixed step; tests/test_oot_follow.py checks that, because a
 * second call per draw would double-advance the easing rates. */
static void         snap_camera_to_link(void)
{
    oot_follow_snap(&link_follow, &demo_link, demo_link_yaw);
    oot_follow_update(&link_follow, &demo_link, demo_link_yaw, false,
                      &demo_camera, &demo_yaw, &demo_pitch);
}

/* Put Link at one of a scene's ROM spawn points and make the camera agree.
 * `scene` is a table index; `spawn` indexes that scene's spawn list. */
static void         place_at_spawn(unsigned int scene, unsigned int spawn)
{
    const scene_spawn_t *point = scene_flow_spawn(scene, spawn);

    /* demo_link.y is the collision/eye position; the spawn records his FEET,
     * which is what the original stores. */
    demo_link.x = point->x;
    demo_link.y = point->y + DEMO_LINK_EYE_HEIGHT;
    demo_link.z = point->z;
    demo_link_yaw = point->yaw;
    link_velocity_y_q8 = 0;
    link_fall_remainder_q8 = 0;
    link_fall_peak_y = demo_link.y;
    link_safe_position = demo_link;
    link_safe_position_valid = true;
    demo_link_active = true;
    link_anim_reset();
    link_anim_reset_state();
    kokiri_camera_reset_actor_motion();
    /* Navi belongs to Link, not to a room: every spawn -- a new file, a loaded
     * save, or the far side of a door -- puts her beside him at once, so she
     * is there on the first controllable frame instead of flying in. */
    navi_reset(demo_link.x, demo_link.y - DEMO_LINK_EYE_HEIGHT, demo_link.z);
    snap_camera_to_link();
}

/* A prerendered interior is shown from the one viewpoint its backdrop was
 * rendered from, so the camera is planted rather than eased. Values come from
 * the room's bgCam entry; see tools/build_scene_table.py.
 *
 * The pitch is negated because OoT stores a downward look as a POSITIVE x
 * rotation while this project's demo_pitch is negative for downward (the
 * diagnostic probes use -1820 for a slight downward tilt). */
static void         interior_camera(void)
{
    const scene_entry_t *entry = scene_flow_entry();

    demo_camera.x = entry->cam_x;
    demo_camera.y = entry->cam_y;
    demo_camera.z = entry->cam_z;
    demo_yaw = entry->cam_yaw;
    demo_pitch = -(int32_t)(int16_t)entry->cam_pitch;
}

/* Walk Link through a doorway: load the far scene and stand him on its spawn.
 * Returns true when a transition happened, so the caller can abandon the rest
 * of the step rather than moving him around in a scene that just unloaded. */
static bool         take_door(void)
{
    int                 index;
    const scene_door_t *door;

    index = scene_flow_door_at(demo_link.x, demo_link.y - DEMO_LINK_EYE_HEIGHT,
                               demo_link.z);
    if (index < 0)
        return (false);
    door = &scene_doors[index];
    game_mode_set(GAME_MODE_LOADING);
    if (!scene_flow_load(door->target, door->spawn)) {
        /* Disc read failed: stay where we are, and go back to playing there
         * rather than leaving the mode stuck mid-load. */
        game_mode_set(GAME_MODE_PLAY);
        return (false);
    }
    /* Record where the player now is, so a save made here reloads here. */
    save_state.scene_id = (uint8_t)scene_flow_entry()->save_scene;
    save_state.entrance = (uint8_t)door->spawn;
    place_at_spawn(door->target, door->spawn);
    /* Per-scene state goes; the save (gear, rupees, quest flags) does not. */
    gameplay_reset();
    if (scene_flow_is_interior())
        interior_camera();
    game_mode_set(GAME_MODE_PLAY);
    return (true);
}

static void         enter_world(void)
{
    unsigned int scene = scene_flow_index_for_save(save_state.scene_id);

    /* Follow the transition with the score. music_fade_to() refuses while a
     * switch is running, so a repeated press cannot stack transitions.
     *
     * PENDING: the forest theme plays indoors too. The original has its own
     * interior music and this slice has no bank for it yet. */
    music_fade_to(&music_bank_kokiri, DEMO_MUSIC_FADE_FRAMES);
    /* The file select has already set up the save -- a new file in Link's
     * house, or a loaded one wherever it was saved -- so the scene to enter
     * comes from there rather than being assumed to be the forest. */
    if (scene_flow_load(scene, save_state.entrance)) {
        save_state.scene_id = (uint8_t)scene_flow_entry()->save_scene;
        place_at_spawn(scene, save_state.entrance);
        gameplay_reset();
        if (scene_flow_is_interior())
            interior_camera();
        game_mode_set(GAME_MODE_PLAY);
        return;
    }
    /* Falling back to the old behaviour keeps a disc-read failure playable
     * rather than dropping the player into an empty world. */
    if (!demo_link_active && kokiri_collision_spawn(&demo_link)) {
        demo_link_yaw = demo_yaw;
        link_velocity_y_q8 = 0;
        link_fall_remainder_q8 = 0;
        link_fall_peak_y = demo_link.y;
        link_safe_position = demo_link;
        link_safe_position_valid = true;
        demo_link_active = true;
        /* Spawn standing, not mid-clip from a previous session. Both calls are
         * needed: one clears the cached pose, the other the locomotion state
         * that selects it. */
        link_anim_reset();
        link_anim_reset_state();
        kokiri_camera_reset_actor_motion();
        navi_reset(demo_link.x, demo_link.y - DEMO_LINK_EYE_HEIGHT, demo_link.z);
        /* gameplay_reset() clears per-scene state only. The quest state was
         * set by the file select -- save_new_game() for a new file, or the
         * loaded save for a continue -- so it must NOT be touched here. */
        gameplay_reset();
        player_input_reset();
        kokiri_camera_set_walk(false);
    }
    if (demo_link_active) {
        /* A title shot may be far across the map. Enter gameplay directly
         * behind Link instead of easing there for seconds. */
        snap_camera_to_link();
    }
    /* The scene read failed and the fallback spawn is all we have. Still enter
     * PLAY: leaving the game in LOADING would freeze the pad in a mode with no
     * screen behind it, which is worse than the wrong scene. */
    game_mode_set(GAME_MODE_PLAY);
}

/* One file-select step, driven by the same latched edges the menu uses. While
 * it is up the world does not step at all. */
static void         file_select_tick(void)
{
    file_select_input   pick = {0};
    file_select_result  chosen;

    pick.up = menu_step < 0;
    pick.down = menu_step > 0;
    pick.confirm = interact_pending;
    pick.cancel = cancel_pending;
    menu_step = 0;
    interact_pending = false;
    cancel_pending = false;
    pause_pending = false;
    chosen = file_select_step(&pick);
    if (chosen == FILE_SELECT_BACK) {
        game_mode_set(GAME_MODE_TITLE);
        /* Hand the pad back, or B would keep cancelling instead of toggling
        ** walk/run once play starts. enter_world() does this through
        ** player_input_reset(); the title path has to do it itself. */
        player_input_set_dialogue(false);
        return;
    }
    if (chosen == FILE_SELECT_START_NEW || chosen == FILE_SELECT_START_LOAD) {
        game_mode_set(GAME_MODE_LOADING);
        active_slot = file_select.slot;
        save_reported = false;
        if (chosen == FILE_SELECT_START_NEW) {
            cutscene_phase = 0;
            cutscene_tick = ticks;
            if (!cutscene_start(CUTSCENE_SLEEP))
                enter_world();
            cutscene_tick = ticks;
        } else {
            enter_world();
        }
    }
}

/* Saturn pad -> normalized CAMERA_* bits. Jo's JO_KEY_* values are SGL/CS
 * bitfield positions; the gameplay code works in its own platform-independent
 * bit set so the mapping lives in exactly one place. */
static uint16_t demo_pad_snapshot(void)
{
    uint16_t bits = 0;
#define MAP(key, bit) if (jo_is_pad1_key_pressed(JO_KEY_##key)) bits |= bit
    MAP(A, CAMERA_A); MAP(B, CAMERA_B); MAP(C, CAMERA_C);
    MAP(X, CAMERA_X); MAP(Y, CAMERA_Y); MAP(Z, CAMERA_Z);
    MAP(L, CAMERA_L); MAP(R, CAMERA_R); MAP(START, CAMERA_START);
    MAP(UP, CAMERA_UP); MAP(DOWN, CAMERA_DOWN);
    MAP(LEFT, CAMERA_LEFT); MAP(RIGHT, CAMERA_RIGHT);
#undef MAP
    return bits;
}

static void demo_vblank(void)
{
    /* Jo refreshes held inputs before this callback. Preserve press edges
     * across slow draws instead of relying on its one-VBlank on_keydown. */
    bool connected = jo_is_pad1_available();
    input_edge_sample(&start_edge, connected && jo_is_pad1_key_pressed(JO_KEY_START));
    /* One normalized snapshot per VBlank. All button state -- including every
     * chord -- is read from this single sample, so two consumers can never
     * disagree about which buttons were down on a given frame. */
    player_input_sample(connected ? demo_pad_snapshot() : 0);
    /* BDCLMD=0 keeps the border outside the active picture black. */
    JO_VDP2_TVMD &= (unsigned short)~0x0100;
    phase += 60;
    while (phase >= refresh) { phase -= refresh; ++ticks; }
}

bool demo_init(void)
{
    int length = 0, row;
    jo_file file;
    jo_img strip;
    jo_color *sky;
    unsigned int sky_lines, sky_row;
    /* Zero-filled BSS gives prompt/target index 0, not the no-actor sentinel. */
    gameplay_reset();
    /* Collision belongs to a SCENE now, not to the forest alone, so it is
     * loaded by scene_flow_load() when a scene is entered. The title's attract
     * flight needs the forest's collision under it, so load that one here. */
    if (!scene_flow_load(SCENE_SPOT04, 0)) return false;
    /* The XZ collision index is built by scene_flow_load(), and REBUILT on
     * every scene change -- it describes one scene's triangles, so keeping a
     * stale one after walking into the house made movement fall back to
     * scanning all 1692 triangles per query. */
    demo_collision_indexed = scene_collision_indexed;
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
    if (jo_core_add_vblank_callback(demo_vblank) == 0)
        return false;

    return true;
}

void demo_update(void)
{
#ifdef DOSEI_CUTSCENE_PROBE
    /*
    ** Straight into one cutscene, skipping the title and the file select.
    **
    ** Diagnostic only, never in a player disc: looking at the dream otherwise
    ** means sitting through the narration every time. Build with
    ** CUTSCENE_PROBE=<id>, where the id is a cutscene_id_t -- 1 is the
    ** nightmare.
    */
    static bool probe_started;
    if (!probe_started) {
        probe_started = true;
        save_new_game();
        game_mode_set(GAME_MODE_FILE_SELECT);
        game_mode_set(GAME_MODE_LOADING);
        cutscene_phase = 0;
        cutscene_tick = ticks;
        if (!cutscene_start(DOSEI_CUTSCENE_PROBE))
            enter_world();
        cutscene_tick = ticks;
        jo_clear_screen();
        return;
    }
#endif
    uint16_t buttons = 0;
    bool recenter = false;
    bool start_pressed = input_edge_consume(&start_edge);
    unsigned int now = ticks, elapsed = now - previous_tick, steps;
    jo_img patch;
    /* One consume per rendered frame. The mapping itself lives in
     * player_input.c; this function only applies the decisions. */
    player_input_t input;
    /* The file select needs the pad too, and Link is not active yet while it is
     * up. player_input_step() zeroes every action and returns early when this
     * is false -- AFTER consuming the press edges -- so leaving the file select
     * out of it swallowed A, B and the D-pad entirely and nothing on the screen
     * could be chosen. */
    bool in_gameplay = !title_visible &&
        (demo_link_active || file_select_visible ||
         game_mode() == GAME_MODE_CUTSCENE);

    /* It owns the pad exactly the way a text box does: D-pad moves the cursor,
     * A confirms, B cancels, and B must not also toggle walk/run. Set before
     * the step, because the step is what reads it. */
    if (file_select_visible || game_mode() == GAME_MODE_CUTSCENE)
        player_input_set_dialogue(true);

    player_input_step(in_gameplay, &input);
    /* Preserve a tap until a fixed step runs, but never carry title input
     * into gameplay or queue an airborne press for a later landing. Jump is Y
     * as of the 2026-09-18 layout; A is the interact button. */
    if (in_gameplay && input.jump) jump_pending = true;
    buttons = input.move_buttons;
    /* input.recenter is the raw L press edge and is deliberately NOT used to
     * recentre any more: gameplay.c raises GP_EVENT_RECENTER for a tap that
     * took no lock. Kept sampled so the edge is consumed each frame. */
    (void)input.recenter;
    if (input.diagnostics_toggled) demo_diagnostics_toggled = true;
    if (input.camera_swap_toggled) oot_follow_set_legacy(!oot_follow_legacy());
    /* Walk/run is a persistent mode, so it is pushed even on a frame with no
     * movement: the next step must already run at the selected speed. */
    kokiri_camera_set_walk(input.move_mode == PLAYER_MOVE_WALK);
    /* Keep diagnostics, and latch actions until the next fixed step. */
    if (input.interact_pending) ++demo_interact_requests;
    if (input.attack_pending) ++demo_attack_requests;
    attack_pending = attack_pending || input.attack_pending;
    interact_pending = interact_pending || input.interact_pending;
    cancel_pending = cancel_pending || input.cancel_pending;
    if (input.menu_step) menu_step = input.menu_step;
    shield_held = input.shield_held;
    target_held = input.target_held;
    /* PENDING SYSTEM. There is no item/inventory interface for the C buttons to
     * drive, so the routed direction is recorded for the HUD and tests. The
     * routing, consumption and edges are real; only the target is missing. */
    if (input.c_pressed != PLAYER_C_NONE) demo_last_c_button = input.c_pressed;
    if (input.c_released != PLAYER_C_NONE &&
        demo_last_c_button == input.c_released)
        demo_last_c_button = PLAYER_C_NONE;
    /* Look mode aims the follow camera and translates nothing. Movement bits
     * were already consumed by player_input_step(). */
    if (input.look_mode)
        oot_follow_look(&link_follow, input.look_yaw_delta,
                        input.look_pitch_delta);
    else if (input.look_exited)
        oot_follow_look_exit(&link_follow);
    if (jo_is_pad1_available()) {
#if defined(DOSEI_PERF_PROBE) && (DOSEI_PERF_PROBE == 2 || DOSEI_PERF_PROBE == 3 || DOSEI_PERF_PROBE == 4 || DOSEI_PERF_PROBE == 5)
        /* Diagnostic-only autonomous walk. No OS/controller input injection. */
        {
            static bool entered;
            if (!entered && now > 120) { start_pressed = true; entered = true; }
            buttons = (DOSEI_PERF_PROBE == 3 || DOSEI_PERF_PROBE == 5) ? 0 :
                      (((now / 180) & 1) ? CAMERA_DOWN : CAMERA_UP);
#if DOSEI_PERF_PROBE == 4
            /* Background visual regression: real running/jump physics, no OS
             * input injection. Never enabled in normal player-test discs. */
            if (!title_visible && now / 120 != (now-elapsed) / 120)
                jump_pending = true;
#endif
        }
#endif
        /* Start leaves the title exactly once. After that it belongs to the
         * pause inventory and must never walk back to the title during
         * ordinary play, so the press is forwarded to gameplay instead.
         *
         * Ignore it while a score switch is running: music_fade_to() would
         * refuse it anyway, and toggling regardless would leave the artwork
         * and the music disagreeing about which state we are in. */
        if (start_pressed && !title_visible) {
            pause_pending = true;
            start_pressed = false;
        }
        /* Start on the title hands over to the file select rather than
         * dropping straight into the forest, so a new game and a continue are
         * distinguishable and a save can be chosen. */
        if (start_pressed && title_visible && !music_busy()) {
            game_mode_set(GAME_MODE_FILE_SELECT);
            /* The D-pad's menu edges are consumed AFTER player_input_step()'s
             * not-in-gameplay early return, so they pile up unconsumed while
             * the title is showing. Clear them here or a direction held during
             * the title jumps the cursor on the first frame. */
            player_input_reset();
            file_select_open();
            start_pressed = false;
        }
    }
    /* 30 Hz gameplay; movement uses time-scaled native world units.
     * Cap catch-up so a slow frame cannot create a long input stall. */
    steps = elapsed / 2;
    if (steps > 4) { steps = 4; previous_tick = now - now % 2; }
    else previous_tick += steps * 2;
    if (file_select_visible) {
        /* The screen owns the pad; nothing in the world advances behind it.
         * The title camera keeps drifting so the backdrop is not frozen. */
        jump_pending = false;
        attack_pending = false;
        title_showcase_camera(now);
        file_select_tick();
    } else if (title_visible) {
        jump_pending = false;
        /* This is an authored title shot, so controller movement does not
         * knock it off its route. Start above has already switched state by
         * the time gameplay reaches this branch. */
        title_showcase_camera(now);
    } else if (game_mode() == GAME_MODE_CUTSCENE) {
        jump_pending = false;
        attack_pending = false;
        cancel_pending = false;
        pause_pending = false;
        menu_step = 0;
        player_input_set_dialogue(true);
        cutscene_phase += (now - cutscene_tick) * CUTSCENE_TICK_HZ;
        cutscene_tick = now;
        while (cutscene_phase >= refresh) {
            cutscene_phase -= refresh;
#ifdef DOSEI_CUTSCENE_PROBE_FRAME
            if (cutscene_frame() >= DOSEI_CUTSCENE_PROBE_FRAME) continue;
#endif
            unsigned int previous_cutscene = cutscene_id();
            unsigned int previous_scenery = cutscene_frame() / 100;
#ifdef DOSEI_CUTSCENE_PROBE_AUTO
            /* Full-opening unattended replay, including scene/bank changes.
             * Diagnostic only; never enabled in a player image. */
            interact_pending = true;
#endif
            cutscene_step(interact_pending);
            if (cutscene_id() != previous_cutscene ||
                (previous_cutscene == CUTSCENE_NAVI_FLY &&
                 cutscene_frame() / 100 != previous_scenery) ||
                ticks - now > refresh / 2) {
                /* Synchronous scenery CD loads must not become catch-up
                 * ticks that skip the next shot or consume reading time. */
                cutscene_phase = 0;
                cutscene_tick = ticks;
            }
            interact_pending = false;
        }
        if (cutscene_finished()) {
            cutscene_phase = 0;
            enter_world();
            player_input_reset();
        }
    } else if (demo_link_active) {
        /* Only movement reaches the legacy viewer controller. Its shoulder
         * orbit and raise/lower/pitch controls are not gameplay controls.
         *
         * The yaw handed to kokiri_camera_update is the CAMERA's. Z targets and
         * a tap recentres, L looks, R is shield, D-pad movement is camera-relative. Facing
         * is not steered by the camera -- it follows wherever he actually
         * moved, which is what keeps turning the view from spinning him. */
        uint16_t walk = buttons & (CAMERA_UP | CAMERA_DOWN | CAMERA_LEFT |
                                   CAMERA_RIGHT);
        int32_t unused_pitch = 0;
        bool recovered = false;
        int32_t roll_speed = 0;
        bool roll_pending = false;
        while (steps--) {
            /* Z is both the target button and the recenter tap. Targeting gets
             * the press first: recentring on the same press would swing the view
             * away from the actor just locked, or away from the one just dropped. */
            {
                gameplay_input_t action = {0};
                bool blocked_before = gameplay_blocks_world();
                action.room = (uint8_t)kokiri_scene_room();
                action.x = demo_link.x;
                action.y = demo_link.y - DEMO_LINK_EYE_HEIGHT;
                action.z = demo_link.z;
                action.yaw = demo_link_yaw;
                action.attack = attack_pending;
                action.shield = shield_held;
                action.target_held = target_held;
                action.interact = interact_pending;
                action.cancel = cancel_pending;
                action.pause = pause_pending;
                /* One slot per press: the menu cursor steps on the D-pad's own
                 * press edges, so holding a direction cannot run down the list. */
                action.menu_step = menu_step;
                action.grounded = link_velocity_y_q8 == 0;
                gameplay_step(&action);
                if (gameplay.events & GP_EVENT_SAVE) {
                    /* Record the outcome. A save that quietly failed is the
                     * worst result for the player, so the panel says which
                     * happened rather than assuming success. */
                    save_succeeded = save_device_write(active_slot);
                    save_reported = true;
                    if (!save_succeeded)
                        gameplay.events |= GP_EVENT_SAVE_FAILED;
                }
                /* A is the context button: talk, prompt, pickup and the menu
                 * get it first. Only a press nothing else claimed becomes a
                 * roll, so pressing A at a Kokiri never rolls away from them. */
                roll_pending = interact_pending && !blocked_before &&
                    !gameplay_blocks_world() &&
                    !(gameplay.events & (GP_EVENT_TALK_OPEN | GP_EVENT_TALK_PAGE |
                                         GP_EVENT_TALK_CLOSE | GP_EVENT_PICKUP |
                                         GP_EVENT_MENU_OPEN | GP_EVENT_MENU_CLOSE |
                                         GP_EVENT_EQUIP | GP_EVENT_SAVE));
                action_audio_events(gameplay.events);
                oot_follow_target(&link_follow, gameplay.face_locked);
                attack_pending = false;
                interact_pending = false;
                cancel_pending = false;
                pause_pending = false;
                menu_step = 0;
                /* Tell the mapper who owns B before the next sample. */
                player_input_set_dialogue(gameplay_blocks_world());
                /* gameplay.c decides whether a Z press was a tap or a
                 * hold, because only it knows if the hold became a lock-on.
                 * A press that locked on must never also recentre, or the
                 * view swings away from the actor just acquired. */
                recenter = (gameplay.events & GP_EVENT_RECENTER) != 0;
                if (blocked_before || gameplay_blocks_world()) {
                    /* A box holds the world still: no camera-relative walk, no
                     * jump queued behind the text, no recenter on the close.
                     * Clearing AFTER the event read, or a tap consumed by a
                     * text box would still swing the camera. */
                    walk = 0;
                    jump_pending = false;
                    recenter = false;
                    roll_pending = false;
                    /* A box or the menu holds Link still. A roll already under
                     * way has to END, not merely stop being started, or it
                     * would keep carrying him across the floor behind the
                     * text. */
                    link_anim_cancel_roll();
                }
                /* Pause freezes the world outright. A text box only stops input --
                 * gravity and the camera keep easing under it, which is what OoT
                 * does -- but the inventory stops the fixed step entirely, so a
                 * paused Link cannot fall, slide or drift while the menu is up. */
                if (gameplay_is_paused())
                    break;
                if (gameplay.swing || gameplay.shielding) {
                    walk = 0;
                    jump_pending = false;
                    roll_pending = false;
                    /* Same for combat: swinging or guarding takes movement
                     * away, so it cancels the roll rather than letting the
                     * travel run on underneath the pose. */
                    link_anim_cancel_roll();
                }
            }
            if (recenter) {
                /* Camera_Parallel1's Z-recenter turn: about 0.2 s, eased out,
                 * rather than cutting the view there in one frame. */
                oot_follow_recenter(&link_follow);
            }
            recenter = false;
            {
                bool grounded;
                int32_t step_x = demo_link.x, step_z = demo_link.z;
                int32_t dx, dz, moved, fell;
                if (jump_pending) {
                    if (kokiri_collision_jump(&demo_link, &link_velocity_y_q8,
                                               &link_fall_remainder_q8))
                        action_audio_events(GP_EVENT_JUMP);
                    jump_pending = false;
                }
                /* A roll commits: it owns translation for its whole clip, so
                 * the D-pad cannot steer or stop it part way through. */
                /* OoT's PLAYER_STICK_DIR_FORWARD, on a digital pad: the
                 * direction the D-pad asks to travel in, measured against the
                 * way Link is facing. Sideways or backward input is NOT
                 * forward and drops the roll to the source floor speed, the
                 * same as letting go; pressing forward again brings it back.
                 * The locomotion speed handed over is what walking or running
                 * would give right now, which is what the source scales. */
                {
                    uint16_t heading = demo_link_yaw;
                    bool forward = kokiri_camera_input_heading(demo_yaw, walk,
                                                               &heading);
                    if (forward) {
                        int32_t turn = (int32_t)(int16_t)
                            (uint16_t)(heading - demo_link_yaw);
                        if (turn < 0) turn = -turn;
                        /* Source quadrant: within 45 degrees of his facing. */
                        forward = turn <= 8192;
                    }
                    link_anim_roll_input(kokiri_camera_walking()
                                             ? LINK_WALK_SPEED_Q8
                                             : LINK_RUN_SPEED_Q8,
                                         forward);
                }
                roll_speed = link_anim_roll_speed_q8();
                if (roll_speed > 0)
                    kokiri_camera_move_heading(&demo_link, demo_link_yaw,
                                               roll_speed);
                else
                    kokiri_camera_update(&demo_link, &demo_yaw, &unused_pitch,
                                         walk, false, true);
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
                    if (demo_link.y > link_fall_peak_y)
                        link_fall_peak_y = demo_link.y;
                    if (recover_link_from_void())
                        recovered = true;
                }
                /* En_Elf updates with the world, so she is stepped here and
                 * not per draw: her approach rates are per update. */
                navi_step(demo_link.x, demo_link.y - DEMO_LINK_EYE_HEIGHT,
                          demo_link.z);
                if (navi_dash_started()) action_audio_navi_dash();
                /* NAVY_FLY belongs only to Object_Kankyo's opening layer 7.
                 * En_Elf gameplay uses occasional dash cues, no flying loop. */
                action_audio_navi_flight(0, false);
                link_anim_update(moved, grounded, fell, roll_pending);
                roll_pending = false;
                if (!gameplay_blocks_world() && !gameplay.swing && !gameplay.shielding)
                    action_audio_events(link_anim_motion_events());
                link_anim_combat(gameplay_is_talking() ? 0 : gameplay.swing,
                                 gameplay.shielding);
                /* Follow him while he is on the ground, so the next departure
                 * measures from where he actually left. Left alone while airborne,
                 * which is what makes the landing drop the full fall. */
                if (grounded)
                    link_fall_peak_y = demo_link.y;

                /* The camera advances per FIXED STEP, not per draw.
                 *
                 * Driving it from the draw callback made every easing rate depend
                 * on the frame rate: a 6-step turn takes 0.2 s at 30 Hz but 0.75 s
                 * at 8 FPS, and OoT's rates are defined per update. Facing is
                 * recomputed here so the camera follows the step it just took. */
                if (gameplay.face_locked) {
                    /* Recompute after movement: both Link and camera track the
                     * target from this step's position, not the previous one. */
                    gameplay_update_facing(demo_link.x, demo_link.z);
                    demo_link_yaw = gameplay.face_yaw;
                }
                else if (target_held) {
                    /* Z held with nothing locked: Link holds his heading and
                     * the D-pad strafes and backs up around it, which is the
                     * source behaviour with no target in range. */
                }
                else if (demo_link.x != step_x || demo_link.z != step_z)
                    demo_link_yaw = kokiri_camera_facing(demo_link.x - step_x,
                                                         demo_link.z - step_z);
                if (recovered) {
                    /* Recovery must not ease: a camera left down in the void
                     * would show empty space on the way back. */
                    oot_follow_snap(&link_follow, &demo_link, demo_link_yaw);
                    recovered = false;
                }
                /* A prerendered interior keeps the one viewpoint its
                 * backdrop was drawn from; easing a follow camera around
                 * inside it would slide the room off the picture. */
                if (scene_flow_is_interior())
                    interior_camera();
                else
                    oot_follow_update(&link_follow, &demo_link, demo_link_yaw,
                                      demo_link.x != step_x || demo_link.z != step_z,
                                      &demo_camera, &demo_yaw, &demo_pitch);
                /* Checked after the move, so standing ON the doorway is what
                 * triggers it -- the same collision triangle the original
                 * uses. Abandons the rest of the catch-up: the scene those
                 * remaining steps belonged to is no longer loaded. */
                demo_collision_indexed = scene_collision_indexed;
                if (take_door()) {
                    walk = 0;
                    jump_pending = false;
                    break;
                }
            }
        }
        /* Pose once for the frame, after the catch-up steps have settled on a
         * final state -- not inside the loop, and not in the draw callback.
         * Skinning is the most expensive thing Link costs, so it runs once per
         * frame at most, and only when the clip frame actually changed. */
        frame_timer_begin(FRAME_PHASE_SKINNING);
        link_anim_pose(link_anim_clip(), link_anim_frame(), link_anim_fraction());
        frame_timer_end(FRAME_PHASE_SKINNING);

    } else {
        while (steps--) kokiri_camera_update(&demo_camera, &demo_yaw,
                                             &demo_pitch, buttons, false,
                                             false);
    }
    patch.width = 84; patch.height = 14; patch.data = prompt;
    /* Only upload on a blink transition, not every rendered frame. */
    /* The blinking PRESS START prompt is uploaded into NBG1, the same layer a
     * prerendered interior's backdrop uses. In the forest NBG1 is off so this
     * was invisible; inside a room the layer is on, so the prompt printed over
     * the picture. It belongs to the title and nowhere else. */
    if (title_visible && last_blink != (int)((now / 30) & 1)) {
    last_blink = (now / 30) & 1;
    if (last_blink) {
        unsigned short empty[84] = {0};
        int row;
        patch.height = 1; patch.data = empty;
        for (row = 173; row < 187; ++row) jo_set_background_sprite(&patch, 118, row);
    } else jo_set_background_sprite(&patch, 118, 173);
    }
    /* NBG1 carries the title artwork AND a prerendered interior's backdrop --
     * they are never on screen together. Switching it off whenever the title
     * is hidden is why the backdrop appeared for a frame and then vanished:
     * kokiri_scene_load_backdrop() uploads it, and the very next demo_update()
     * turned the layer off again. */
    cutscene_sky_update();
    slScrAutoDisp(NBG0ON |
                  ((title_visible ||
                    (kokiri_scene_backdrop_active() &&
                     !cutscene_hides_scene())) ? NBG1ON : 0));
}

/* -1 no attempt yet this session, 0 failed, 1 succeeded. */
int demo_save_report(void)
{
    return (!save_reported ? -1 : (save_succeeded ? 1 : 0));
}

bool demo_file_select_is_visible(void)
{
    return (file_select_visible);
}

bool demo_title_is_visible(void)
{
    return title_visible;
}

unsigned int demo_clock(void)
{
    return ticks;
}
