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
#include "action_audio.h"
#include "demo.h"
#include "navi.h"
#include "gameplay.h"
#include "kokiri_dialogue.h"
#include "link_anim_state.h"
#include "link_clips.h"
#include "frame_timer.h"
#include "oot_follow.h"
#include "ram_cart.h"
#include "actor_sys.h"
#include "save_device.h"
#include "file_select.h"
#include "scene_flow.h"
#include "message.h"
#include "cutscene.h"
#include "cutscene_actor.h"

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
static void         dialogue_box(void);
static void         inventory_menu(void);
static void         action_hint(void);
static void         file_select_screen(void);
static void         cutscene_text(void);
static void         cutscene_fade(void);
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
#if defined(DOSEI_PERF_PROBE) && DOSEI_PERF_PROBE == 5
    /* Warp A/B: one fixed pose facing the long room-0 wall quad
    ** (world corners x -1994..-1634, z -167..1233, y 160..649), so a split-off
    ** and a split-on disc can be compared at the identical camera. Diagnostic
    ** only; never in a normal disc. */
    /* Pin Link where the moving capture showed the offending wall quad
    ** filling the near view and let the real follow camera settle behind him,
    ** so split-off and split-on discs render the same gameplay view. */
    if (demo_link_active && !demo_title_is_visible() && !cutscene_is_playing()) {
        demo_link.x = -43; demo_link.y = 90; demo_link.z = -14;
        demo_link_yaw = 16384;
        /* Astra's settled gap pose, camera included: the follow camera reaches
        ** a different yaw when Link is simply placed here, so the eye is
        ** pinned too rather than approximated. */
        demo_camera.x = -139; demo_camera.y = 71; demo_camera.z = -90;
        demo_yaw = 9356; demo_pitch = 0;
    }
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
    if (cutscene_screen_distance() > 0)
        slSetScreenDist((FIXED)((int32_t)cutscene_screen_distance() << 16));
    else if (kokiri_scene_backdrop_active() && scene_flow_entry()->cam_dist > 0)
        slSetScreenDist((FIXED)((int32_t)scene_flow_entry()->cam_dist << 16));
    else
        slSetScreenDist(toFIXED(demo_title_is_visible() ? 180 : SCREEN_DISTANCE));
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
    slRotX((ANGLE)(0u-demo_pitch));
    slRotY((ANGLE)(0u-demo_yaw));
    jo_3d_translate_matrix(-demo_camera.x, demo_camera.y, -demo_camera.z);
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
        /* The forest's own actors belong to gameplay, not to a cutscene
         * playing in the same scene: Navi's flight must not have Kokiri
         * fairies bobbing along beside it. */
        if (!cutscene_is_playing()) {
            kokiri_grass_draw();
            kokiri_rupees_draw(demo_clock());
            kokiri_fairies_draw(demo_clock());
            kokiri_pickups_draw(demo_clock());
        }
    }
    kokiri_menu_draw();
#endif
    frame_timer_end(FRAME_PHASE_SCENE);
    /* Link is submitted after the forest so the per-frame counters, which
    ** kokiri_scene_draw() resets, cover both lists. His model origin is at his
    ** feet, EYE_HEIGHT below the collision position. */
    if (cutscene_is_playing()) {
        unsigned int channel;

        cutscene_actors_prepare();
        if (cutscene_id() == CUTSCENE_NIGHTMARE && !cutscene_hides_scene()) {
            int32_t sine, cosine;
            int y, z;
            kokiri_camera_sincos((uint16_t)cutscene_bridge_angle(), &sine, &cosine);
            y = -10 + (int)(((int64_t)10 * cosine - (int64_t)400 * sine) >> 16);
            z = 670 + (int)(((int64_t)10 * sine + (int64_t)400 * cosine) >> 16);
            cutscene_actor_draw(CUTSCENE_ACTOR_BRIDGE, 0, -10, 670, 0);
            cutscene_actor_draw(CUTSCENE_ACTOR_CHAINS, 158, y, z, 0);
            cutscene_actor_draw(CUTSCENE_ACTOR_CHAINS, -158, y, z, 0);
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
    } else if (demo_link_active && !demo_title_is_visible()) {
        frame_timer_begin(FRAME_PHASE_LINK);
        kokiri_link_draw(demo_link.x, demo_link.y - DEMO_LINK_EYE_HEIGHT,
                         demo_link.z, demo_link_yaw);
        frame_timer_end(FRAME_PHASE_LINK);
        /* Link's own fairy, drawn with him and only with him: the title
         * shot and the file select are not gameplay. */
        if (navi_active())
            kokiri_navi_draw(navi_x(), navi_y(), navi_z());
    }
    if (!cutscene_is_playing() && (!demo_link_active || demo_title_is_visible()))
        action_audio_navi_flight(0, false);
    if (cutscene_is_playing() && !cutscene_hides_scene())
        kokiri_cutscene_effects_draw();
    rejected_total += kokiri_scene_rejected();
    cutscene_fade();
    cutscene_text();
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
            debug_visible = false;
        }
    }
    dialogue_box();
    inventory_menu();
    file_select_screen();
    if (!gameplay_blocks_world() && !cutscene_is_playing()) viewer_hud();
    action_hint();
    {
        static bool skip_was_visible;
        bool visible = demo_skip_prompt();
        if (visible)
            jo_printf(6, 3, "Skip? Press Start Again");
        else if (skip_was_visible)
            jo_printf(6, 3, "                       ");
        skip_was_visible = visible;
    }
    if (!demo_title_is_visible() && !demo_file_select_is_visible() &&
        !cutscene_is_playing())
        kokiri_rupee_hud_draw();
    {
        /* Callback share of frame time: an estimate of master-CPU work,
         * not total utilization across both SH-2s. Sync includes GPU/VBlank
         * waiting. Existing smoothed timings keep the display readable. */
        unsigned int work = frame_timer_frame();
        unsigned int total = work + frame_timer_cost(FRAME_PHASE_SYNC);
        unsigned int cpu = total ? work * 100u / total : 0;
        jo_printf(1, JO_TV_HEIGHT / 8 - 1, "VRAM %3u%%   CPU~ %3u%%   ",
                  kokiri_scene_vram_percent(), cpu);
    }
    frame_timer_frame_end();
    frame_timer_begin(FRAME_PHASE_SYNC);
}

/*
** The cutscene's screen fill, as a VDP2 colour offset.
**
** OoT fills the screen with a coloured quad and ramps its alpha
** (z_demo.c:1550-1574). VDP2 offers the same effect far more cheaply: a
** negative colour offset darkens every layer it is applied to, so a black fill
** is a ramp from 0 to -255 and needs no polygon at all.
**
** Applied to the scene layers and the sprites, never to NBG0: the text layer
** has to stay legible over a darkened scene, and the narration is drawn while
** the fill is at full strength.
**
** A fully opaque fill is handled earlier by skipping the scene entirely, so
** this only has to cover the partial values.
*/
static void         cutscene_fade(void)
{
    static int last_level = -999;
    static bool last_hidden;
    bool hidden = cutscene_hides_scene();
    unsigned int alpha = cutscene_fade_alpha();
    int flash = cutscene_lightning();
    Sint16 level = (Sint16)(flash - (int)alpha);

    if (alpha && cutscene_fade_colour() != CUTSCENE_FADE_BLACK)
        level = (Sint16)(flash + (int)alpha);
    if (level > 255) level = 255;
    if (level == last_level && hidden == last_hidden) return;
    last_level = level;
    last_hidden = hidden;
    if (!level) {
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
        /* The Blue font palette is bright cyan while cutscene text is active. */
        case CUTSCENE_COLOUR_BLUE: return JO_COLOR_INDEX_Blue;
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

static void         cutscene_text(void)
{
    static bool     was_active;
    static int      last_top, last_rows;
    unsigned int    line, run, lines;
    int             top, rows, text_row, prompt_row;

    if (!message_is_active()) {
        if (was_active) {
            cutscene_box_clear(last_top, last_rows);
            jo_set_printf_palette_color(JO_COLOR_INDEX_Blue, JO_COLOR_Blue);
            was_active = false;
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

    for (line = 0; line < lines; ++line) {
        /* The original's SHIFT, which is what centres the narration, measured
        ** from inside the box rather than from the screen edge. */
        int column = CUTSCENE_BOX_LEFT + 1 + (int)message_line_indent(line);

        /* Wipe the row first. VDP2 retains text, and a page shorter than the
        ** one before it would otherwise leave the tail of the old line on
        ** screen -- which is where "descendingof" came from. */
        jo_printf(0, text_row + (int)line, "%-40s", "");

        for (run = 0; run < message_line_runs(line); ++run) {
            const char  *text = message_run_text(line, run);
            unsigned int shown = message_run_visible(line, run);
            unsigned int length = 0;

            while (text[length])
                ++length;
            if (shown > length)
                shown = length;
            if (shown)
                /* Typed out a character at a time, so only the part of the
                ** run that has appeared so far is drawn. */
                jo_printf_with_color(column, text_row + (int)line,
                                     cutscene_text_colour(
                                         message_run_colour(line, run)),
                                     "%.*s", (int)shown, text);
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
    if (message_waits_for_button())
        kokiri_message_mark_draw(160, prompt_row * 8 + 4,
                                 message_is_last_page());
    /* Restore the default, or every other jo_printf on the screen inherits
    ** whichever colour was used last. */
    jo_set_printf_color_index(JO_COLOR_INDEX_White);
}

/*
** Text box and the A: Talk prompt.
**
** Drawn on the clean player disc as well as the diagnostic one -- this is
** gameplay, not debug text -- so it sits outside viewer_hud()'s early returns.
** VDP2 retains what is printed, so both the box and the prompt clear their own
** rows on the frame they stop being shown, or the last page stays on screen.
*/
#define DIALOGUE_ROW    20
#define DIALOGUE_ROWS   (DIALOGUE_MAX_LINES + 2)
#define PROMPT_ROW      18

static void         dialogue_box(void)
{
    static bool was_talking;
    static int  last_prompt = -1;
    unsigned int i;

    /* Title flythrough and the file select have no interaction. Clear retained
     * VDP2 text too, so returning here cannot leave an old prompt or page on
     * screen -- and so a stale prompt cannot print over the file list. */
    if (demo_title_is_visible() || demo_file_select_is_visible() ||
        cutscene_is_playing()) {
        if (last_prompt != -1)
            jo_printf(1, PROMPT_ROW, "%-38s", "");
        if (was_talking) {
            for (i = 0; i < DIALOGUE_ROWS; ++i)
                jo_printf(0, DIALOGUE_ROW + i, "%-40s", "");
        }
        last_prompt = -1;
        was_talking = false;
        return;
    }
    if (!gameplay_is_talking()) {
        if (was_talking) {
            for (i = 0; i < DIALOGUE_ROWS; ++i)
                jo_printf(0, DIALOGUE_ROW + i, "%-40s", "");
            was_talking = false;
        }
        /* A: Talk, only while a speaker is actually in reach and in front. */
        if (gameplay.prompt != last_prompt) {
            last_prompt = gameplay.prompt;
            if (gameplay.prompt >= 0)
                jo_printf(1, PROMPT_ROW, "%-38s", "A: Talk");
            else
                jo_printf(1, PROMPT_ROW, "%-38s", "");
        }
        return;
    }
    if (last_prompt != -1) {
        last_prompt = -1;
        jo_printf(1, PROMPT_ROW, "%-38s", "");
    }
    was_talking = true;
    jo_printf(1, DIALOGUE_ROW, "%-38s", gameplay_speaker_name());
    for (i = 0; i < DIALOGUE_MAX_LINES; ++i) {
        const char *line = i < gameplay_page_lines() ? gameplay_page_line(i) : "";
        jo_printf(1, DIALOGUE_ROW + 1 + i, "%-38s", line ? line : "");
    }
    jo_printf(1, DIALOGUE_ROW + 1 + DIALOGUE_MAX_LINES, "%-38s",
              "A: next   B: close");
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

static void         inventory_menu(void)
{
    static bool was_paused;
    unsigned int slot;
    int row = MENU_ROW;

    if (!gameplay_is_paused()) {
        if (was_paused) {
            for (slot = 0; slot < MENU_ROWS; ++slot)
                jo_printf(0, MENU_ROW + slot, "%-40s", "");
            was_paused = false;
        }
        return;
    }
    was_paused = true;
    jo_printf(2, row++, "%-36s", "-- ITEMS --");
    row++;
    for (slot = 0; slot < GP_SLOT_COUNT; ++slot) {
        uint8_t item = gameplay_slot_item(slot);
        const char *state;
        if (slot == GP_SLOT_SAVE) {
            /* Not an item row: it reports the last save attempt instead of an
             * owned/equipped state, and says plainly when one failed. */
            int report = demo_save_report();
            state = !save_device_ready() ? "NO BACKUP RAM"
                  : report < 0 ? ""
                  : report ? "SAVED" : "SAVE FAILED";
        } else {
            state = !(gameplay.owned & item) ? "Find in forest"
                  : (gameplay.equipped & item) ? "EQUIPPED" : "Owned";
        }
        jo_printf(2, row++, "%c %-14s %-18s",
                  slot == gameplay.cursor ? '>' : ' ',
                  gameplay_slot_name(slot), state);
        /* Only an owned item gets its use button: printing "X: swing" next to
         * a sword the player has never found would be a lie. The save row
         * always shows its own, because it is always usable. */
        jo_printf(4, row++, "%-34s",
                  (slot == GP_SLOT_SAVE || (gameplay.owned & item))
                      ? gameplay_slot_use(slot) : "");
    }
    row++;
    jo_printf(2, row++, "%-36s", "CONTROLS");
    jo_printf(2, row++, "%-36s", "D-pad move   B walk/run");
    jo_printf(2, row++, "%-36s", "X swing/cut  Hold R shield");
    jo_printf(2, row++, "%-36s", "Y jump       A talk/next page");
    jo_printf(2, row++, "%-36s", "B closes dialogue");
    jo_printf(2, row++, "%-36s", "Hold Z: lock on + strafe");
    jo_printf(2, row++, "%-36s", "Release Z: release lock");
    jo_printf(2, row++, "%-36s", "Tap Z: re-centre camera");
    jo_printf(2, row++, "%-36s", "Hold Z: D-pad strafe/back up");
    jo_printf(2, row++, "%-36s", "Hold L + D-pad: look around");
    jo_printf(2, row++, "%-36s", "Hold C + D-pad: C items (pending)");
    jo_printf(2, row++, "%-36s", "A: roll; also rolls on landing");
    jo_printf(2, row++, "%-36s", "Start opens/closes items");
    jo_printf(2, row++, "%-36s", "MENU: D-pad pick A equip B back");
#ifndef DOSEI_CLEAN_TEST
    jo_printf(2, row++, "%-36s", "L+R+Down debug; +Up camera compare");
#endif
}

/* Persistent state survives fixed-step catch-up; one-step events may not. */
static void action_hint(void)
{
    static unsigned int changed_at;
    static unsigned int last_owned, last_cuts;
    static const char *notice = "";
    unsigned int now = demo_clock();
    if (demo_title_is_visible() || demo_file_select_is_visible() ||
        cutscene_is_playing()) {
        jo_printf(1, 28, "%-38s", "");
        return;
    }
    if (gameplay.owned != last_owned) {
        notice = (gameplay.owned & GP_SWORD) && !(last_owned & GP_SWORD)
            ? "Sword equipped! X: swing" : "Shield equipped! Hold R: guard";
        last_owned = gameplay.owned;
        changed_at = now;
    }
    if (gameplay.cut_count != last_cuts) {
        last_cuts = gameplay.cut_count;
        notice = "Grass cut!";
        changed_at = now;
    }
    if (gameplay_blocks_world()) {
        jo_printf(1, 28, "%-38s", "");
        return;
    }
    /* Only things that just happened. The standing control reminders that used
    ** to sit here ("Find sword west. Start: items/help") were on screen for the
    ** whole game, which the original never does -- and reading one the instant
    ** the opening cutscene handed over to play was the first thing anyone saw.
    ** Transient notices stay: they are feedback, not instructions. */
    jo_printf(1, 28, "%-38s",
        gameplay.swing ? "Sword swing" : gameplay.shielding ? "Shield raised" :
        (*notice && now - changed_at < 180) ? notice : "");
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
            /* Gear/target/sword readout. sw and sh are owned+equipped, tgt is
             * the locked kokiri_npcs index, sg the swing steps left with a '*'
             * while the blade is live, cut the tufts cleared so far. */
            jo_printf(0, 5, "sw%d sh%d tgt%-3d sg%d%c cut%-2d  ",
                      (gameplay.equipped & GP_SWORD) ? 1 : 0,
                      (gameplay.equipped & GP_SHIELD) ? 1 : 0,
                      (int)gameplay.target, (int)gameplay.swing,
                      gameplay_sword_active() ? '*' : (gameplay.shielding ? 'R' : ' '),
                      (int)gameplay.cut_count);
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
#ifdef DOSEI_WARP_PROBE
        /* Probe rows: nearest polygon, then the worst projected-span
        ** candidate. Vertex ids identify the surface through a turn. */
        jo_printf(0, 10, "nr r%d f%d e%d t%d v%d,%d   ",
                  kokiri_warp_probe(0), kokiri_warp_probe(1),
                  kokiri_warp_probe(2), kokiri_warp_probe(3),
                  kokiri_warp_probe(4), kokiri_warp_probe(5));
        jo_printf(0, 11, "sp s%d r%d f%d e%d t%d v%d,%d  ",
                  kokiri_warp_probe(6), kokiri_warp_probe(7),
                  kokiri_warp_probe(8), kokiri_warp_probe(9),
                  kokiri_warp_probe(10), kokiri_warp_probe(11),
                  kokiri_warp_probe(12));
        /* Submission accounting at the probe pose: refusals this frame, the
        ** running total, and how many forest polygons were handed to SGL.
        ** Zero refusals does not prove every face was drawn; a non-zero count
        ** does prove something was dropped. */
        jo_printf(0, 12, "rej%d tot%d sub%d   ",
                  (int)kokiri_scene_rejected(), (int)rejected_total,
                  (int)kokiri_scene_submitted());
#endif
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

static void         file_select_screen(void)
{
    static bool   was_visible;
    /* True while the "Open this file?" panel is up, so the list behind it is
    ** cleared once on entry and redrawn once on the way back out. */
    static bool   was_open;
    unsigned int  row;

    if (!demo_file_select_is_visible()) {
        if (was_visible) {
            for (row = 0; row < FS_ROWS; ++row)
                jo_printf(0, (int)(FS_ROW + row), "                                      ");
            was_visible = false;
            was_open = false;
        }
        return;
    }
    was_visible = true;

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
        for (line = 0; line < FILE_SELECT_OPEN_ROWS; ++line)
            jo_printf(4, (int)(FS_ROW + 5 + line), "%s %-6s",
                      file_select.open_row == line ? ">" : " ",
                      file_select_open_label(line));
        jo_printf(2, FS_ROW + 5 + FILE_SELECT_OPEN_ROWS + 1,
                  "A: DECIDE   B: CANCEL            ");
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
            row == FILE_SELECT_ROW_ERASE)
            here = false;
        jo_printf(2, line, "%s %-12s", here ? ">" : " ",
                  file_select_row_label(row));
        jo_printf(2, line + 1, "     %-32s", file_select_row_detail(row));
    }

    row = FS_ROW + 2 + FILE_SELECT_ROWS * 2;
    switch (file_select.mode) {
        case FILE_SELECT_ERASE_CONFIRM:
            jo_printf(2, (int)row, "ERASE %s? A: YES   B: NO          ",
                      file_select_row_label(file_select.erase_slot));
            break;
        case FILE_SELECT_ERASE_PICK:
            jo_printf(2, (int)row, "PICK A FILE TO ERASE. B: BACK    ");
            break;
        default:
            jo_printf(2, (int)row, "A: PLAY   B: TITLE               ");
            break;
    }
    /* Only ever shown when a device call actually refused. */
    jo_printf(2, (int)row + 2, "%s",
              file_select.device_failed ? "CANNOT USE THAT FILE          "
                                        : "                              ");
    if (!save_device_ready())
        jo_printf(2, (int)row + 3, "NO BACKUP MEMORY: CANNOT SAVE");
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

    /* Actor pool lives in the cart's fixed carve, never in work RAM. */
    if (actor_sys_bytes() > RAM_CART_ACTOR_POOL_BYTES ||
        !actor_sys_init(ram_cart_fixed(RAM_CART_ACTOR_POOL_OFFSET,
                                       RAM_CART_ACTOR_POOL_BYTES),
                        RAM_CART_ACTOR_POOL_BYTES)) {
        jo_core_error("Actor pool does not fit its cart carve");
        return;
    }

    /* Backup RAM is mounted before anything can ask to load a file. A console
    ** with no usable internal memory is still playable, so this is reported
    ** rather than fatal -- unlike the missing cart above. */
    if (!save_device_init())
        jo_printf(2, 26, "no backup memory: cannot save");

    scene_ready = kokiri_scene_load();
    scene_ready = scene_ready && demo_init();
    music_ready = scene_ready && music_init(&music_bank_title);
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
