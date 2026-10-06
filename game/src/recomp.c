#include <jo/jo.h>
#include "../../shared/lib/collision/div32.h"   /* 32-bit divides, no ___divdi3 */
#include "ram_cart.h"
#include "sgl_registers.h"
#include "recomp.h"
#include "oot_core_host.h"
#include "environment_sky.h"
#include "pause_windows.h"
#include "music.h"
#include "music_banks.h"
#include "field_music.h"
#include "story_route.h"
#include "music_songs.h"
#include "cdda.h"
#include "gohma.h"
#include "tree_mouth.h"
#include "texture_probe.h"
#pragma GCC diagnostic push
#pragma GCC diagnostic ignored "-Wunused-const-variable"
#include "title_paths.h"                /* layout/counts; points on the cart */
#pragma GCC diagnostic pop
#include "link_anim_state.h"
#include "link_clips.h"
#include "action_audio.h"
#include "oot_follow.h"
#include "frame_timer.h"
#include "input_edge.h"
#include "skip_input.h"
#include "player_input.h"
#include "gameplay.h"
#include "message.h"
#include "player_items.h"
#include "dungeon_doors.h"
#include "dungeon_webs.h"
#include "dungeon_torches.h"
#include "dungeon_puzzles.h"
#include "file_select.h"
#include "level_select.h"
#include "music_area.h"
#include "kokiri_scene.h"
#include "scene_flow.h"
#include "save_state.h"
#include "save_device.h"
#include "ui_preferences.h"
#include "game_mode.h"
#include "cutscene.h"
#include "kokiri_sgl.h"
#include "navi.h"
#include "player_air.h"
#include "player_bg.h"
#include "player_climb.h"
#include "player_crawl.h"
#include "player_push.h"
#include "actor_sys.h"
#include "attention.h"
#include "karebaba.h"
#include "game_over.h"
#include "player_lift.h"
#include "world_props.h"
#include "player_slope.h"
#include "player_water.h"
#include "player_camera.h"
#include "combat_input.h"
#include "kokiri_actors.h"
#include "minimap.h"
#include "scene_room_type.h"

static void link_focus(int32_t out[3]);

camera_position_t recomp_camera;
uint16_t recomp_yaw;
int32_t recomp_pitch;
camera_position_t recomp_link;
uint16_t recomp_link_yaw;
bool recomp_link_active;
static int32_t link_velocity_y_q8;
static uint8_t link_hover_steps;
static int32_t link_fall_remainder_q8;
/* Height Link last left the ground from (OoT fallStartHeight: set while
 * grounded, NOT raised by a jump), so the drop measured at landing is
 * departure minus landing -- what the landing branch picks short landing,
 * ordinary landing or roll from. Eye-anchor units, like recomp_link.y. */
static int32_t link_fall_peak_y;
/* Grounded on the previous step, and that floor's SurfaceType floorProperty
 * (sPrevFloorProperty): func_8083AA10 decides a departure from these. */
static bool link_on_ground;
static uint8_t link_floor_property;
static camera_position_t link_safe_position;
static bool link_safe_position_valid;
/* Wall contact and ledge probe (Player_ProcessSceneCollision), and the
** yDistToLedge a 250 jump launches from on its frame 8. */
static player_bg_t link_bg;
static int32_t link_jump250_dist;
/* speedXZ an action set that no input is steering (250 jump 1.0, hop 2.5,
** let go of a ledge -0.8 away from it). The air steering func_8083DFE0
** takes it toward zero by 0.1 a frame (17 Q8 a step) with the stick
** centred; input replaces it, as for every jump in this port. */
static int32_t link_air_speed_q8;
static uint16_t link_air_yaw;
/* Jump slash / sidehop / backflip: launch speed carries the whole jump,
** stick does not replace it. evade_launch skips the launch-step clear. */
static bool link_air_evade, link_air_evade_launch;
/* The hang began by walking off (func_8083A6AC) rather than grabbing. */
static bool link_hang_walk_off;
/* Ladder / vine climbing (player_climb.c). */
static player_climb_t link_climb;
static player_push_t link_push;
static player_lift_t link_lift;
/* Bomb/Bombchu over Link's head (decomp tool actor): the carry pose and the
 * throw clip come from the same lift states as pots. */
static bool lift_bomb, bomb_throw;
/* Sword/shield in hand (z_player heldItemAction >= SWORD) vs sheathed. */
static bool link_sword_out;
static uint8_t putaway_wait;
bool recomp_sword_out(void) { return link_sword_out; }
static player_slope_t link_slope;
static player_water_t link_water;
static player_camera_t link_camera;

/* Existing scene bushes: child-without-strength attempts do not detach or
 * destroy the prop, so no collectible/drop path runs. Successful actor carry
 * needs the prop owner to consume player_lift's events (M3 integration). */
static int lift_bush_candidate(void)
{
    int found=-1;
    int32_t best=50*50;
    unsigned i;
    if (save_state.scene_id!=SAVE_SCENE_KOKIRI_FOREST) return -1;
    for (i=0;i<KOKIRI_GRASS_COUNT;i++) {
        const kokiri_prop_t *g=&kokiri_grass[i];
        int32_t dx=g->x-recomp_link.x,dz=g->z-recomp_link.z;
        int32_t dy=g->y-(recomp_link.y-RECOMP_LINK_EYE_HEIGHT);
        int32_t dist=dx*dx+dz*dz;
        int32_t turn=(int16_t)(uint16_t)(kokiri_camera_facing(dx,dz)-recomp_link_yaw);
        if (g->room==kokiri_scene_room() && !gameplay_grass_cut(i) &&
            dy>=-10 && dy<=10 && dist<best && turn>-0x3000 && turn<0x3000) {
            bg_vec_t from={recomp_link.x,recomp_link.y-RECOMP_LINK_EYE_HEIGHT+26,recomp_link.z};
            bg_vec_t to={g->x,g->y+26,g->z},at;
            bg_hit_t hit;
            if (!bg_line(&from,&to,&at,BG_CHECK_WALL,BG_IGNORE_ENTITY,&hit)) {
                found=(int)i; best=dist;
            }
        }
    }
    return found;
}
/* Crawlspaces (player_crawl.c), and last step's sphere wall: the crawl exit
** acts on the previous update's collision, as the source does. */
static player_crawl_t link_crawl;
static bool link_last_wall;
static bg_hit_t link_last_wall_hit;
/* PLAYER_STATE2_DO_ACTION_ENTER this step (the HUD's "A: Enter"). */
static bool link_enter_prompt;

bool recomp_enter_prompt(void) { return link_enter_prompt; }

/* Last intent_speed passed to player_lift_update, cached for query functions. */
static int32_t lift_last_speed_q8;

bool recomp_lift_hold_actionable(void) { return link_lift.phase == LIFT_HOLD; }

bool recomp_lift_throw_ready(void)
{
    return link_lift.phase == LIFT_HOLD &&
           (link_lift.throw_only || lift_last_speed_q8 >= 282);
}

/* Camera_Subj4 (CAM_SET_CRAWLSPACE): first person on the crawlspace's bgCam
** line -- points [1] and [n-2] -- at the point nearest Link, looking down
** the tunnel, bobbing toward (r 5, pitch 50 deg) as he moves. */
static bool crawl_cam_valid;
static bool view_first_person;
static bool c_up_pending;
bool recomp_view_first_person(void) { return view_first_person; }
static bg_vec_t crawl_cam_point;
static int32_t crawl_cam_dir[3];
static uint16_t crawl_cam_yaw, crawl_cam_phase;

/* EnOssan: PLAYER_STATE2_29 hides Link while the shop is browsed. */
static bool shop_browsing;
bool recomp_shop_browsing(void) { return shop_browsing; }

bool recomp_first_person(void)
{
    return view_first_person || (crawl_cam_valid && link_crawl.phase == PLAYER_CRAWL_IN);
}

static void __attribute__((optimize("Os"), noinline)) crawl_camera_begin(void)
{
    bg_vec_t feet = { recomp_link.x, recomp_link.y - RECOMP_LINK_EYE_HEIGHT + 1, recomp_link.z };
    const bg_mesh_t *mesh = bg_scene_mesh();
    bg_hit_t floor;
    uint32_t index;
    crawl_cam_valid = false;
    if (bg_floor(&feet, BG_IGNORE_ENTITY, &floor) == BG_Y_MIN || !mesh)
        return;
    index = bg_bgcam(&floor);
    if (!player_camera_crawl_line(mesh, index, &crawl_cam_point, crawl_cam_dir))
        return;
    /* He faces into the tunnel on entering: that is the forward yaw. */
    crawl_cam_yaw = recomp_link_yaw;
    crawl_cam_phase = 0;
    crawl_cam_valid = true;
}

static void __attribute__((optimize("Os"), noinline)) crawl_camera(bool moving)
{
    int64_t len = (int64_t)crawl_cam_dir[0] * crawl_cam_dir[0] +
                  (int64_t)crawl_cam_dir[1] * crawl_cam_dir[1] +
                  (int64_t)crawl_cam_dir[2] * crawl_cam_dir[2];
    int64_t along = (int64_t)(recomp_link.x - crawl_cam_point.x) * crawl_cam_dir[0] +
                    (int64_t)(recomp_link.y - RECOMP_LINK_EYE_HEIGHT - crawl_cam_point.y) * crawl_cam_dir[1] +
                    (int64_t)(recomp_link.z - crawl_cam_point.z) * crawl_cam_dir[2];
    int32_t sine, cosine, bob, ex, ey, ez;
    if (!len) return;
    /* Math3D_LineClosestToPoint (32-bit divides, no ___divdi3). */
    ex = crawl_cam_point.x + muldiv64_s32(crawl_cam_dir[0], along, len);
    ey = crawl_cam_point.y + muldiv64_s32(crawl_cam_dir[1], along, len);
    ez = crawl_cam_point.z + muldiv64_s32(crawl_cam_dir[2], along, len);
    /* eyeLerpPhase += 0xBB8 an update (0x7D0 a 30 Hz step) while moving;
    ** the eye leans |cos| of the way to (r 5, pitch 0x238C, forward). */
    if (moving) crawl_cam_phase = (uint16_t)(crawl_cam_phase + 0x7D0);
    kokiri_camera_sincos(crawl_cam_phase, &sine, &cosine);
    bob = cosine < 0 ? -cosine : cosine;            /* Q16 */
    kokiri_camera_sincos(crawl_cam_yaw, &sine, &cosine);
    recomp_camera.x = ex + (int32_t)((int64_t)3 * sine / 65536 * bob / 65536);
    recomp_camera.y = ey + (int32_t)((int64_t)4 * bob / 65536);
    recomp_camera.z = ez + (int32_t)((int64_t)3 * cosine / 65536 * bob / 65536);
    recomp_yaw = crawl_cam_yaw;
    recomp_pitch = 0;
}

/* Link's follow camera state. Geometry and easing rates come from OoT's
 * Normal1; see shared/lib/camera/oot_follow.c for the derivation. */
static oot_follow_t link_follow;
/* If no walkable floor remains below Link after dropping this far from his
 * last grounded point, collision has let him out of the world. Restore that
 * nearby point rather than relying on one map-wide respawn coordinate. */
#define LINK_VOID_DROP 180
/* Half-fade length for the title->forest switch, in vblanks. */
#define RECOMP_MUSIC_FADE_FRAMES 10
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
static bool frozen_fanfare, item_fanfare_pending;
static unsigned chest_start, fanfare_start;
static unsigned level_select_open_tick;
static uint8_t chest_scene;
static void chest_scene_begin(void);
static void chest_scene_step(void);
static void snap_camera_to_link(void);
static void interior_camera(void);
bool recomp_code_fanfare_active(void) {return frozen_fanfare;}
/* Last save attempt, for the pause panel. Persistent, not a one-step event:
 * the player needs to still see it after the step that raised it. */
static bool save_reported, save_succeeded;
/* The collision index itself lives in scene_flow.c, which owns the collision
** data and rebuilds the index whenever a scene is loaded. This is only the
** diagnostic mirror the HUD prints. */
bool recomp_collision_indexed;
static unsigned short *prompt;
static volatile unsigned int ticks;
static unsigned int phase, refresh, previous_tick;
/* SGL owns the font at B1+0; Jo's allocator does not reserve it. Keep this
 * table at B1+0x1f000, clear of the fixed SGL font and map storage. */
extern void slBackColTable(void *table);
static int last_blink = -1;
/* Diagnostics chord state. recomp_diagnostics_toggled is a one-shot the HUD
 * clears, so the chord edge is detected with the rest of the input rather than
 * sampled a second time in main.c. */
bool recomp_diagnostics_toggled;
static input_edge_t start_edge;
static skip_input_t skip_input;
static bool jump_pending;
/* Action intents latched from the sampled input, consumed once per fixed step
 * exactly like jump_pending. A short X tap must survive a slow rendered frame. */
static combat_input_t combat_input;
static bool interact_pending;
static bool cancel_pending;
static bool pause_pending;
static int8_t menu_step, menu_dx, menu_dy, menu_page;
static uint8_t c_assign, c_use, item_aim;

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
unsigned int recomp_interact_requests;
unsigned int recomp_attack_requests;
player_c_button_t recomp_last_c_button;

static jo_color __attribute__((optimize("Os"))) sky_color(unsigned int row)
{
    return environment_field_horizon(row,
        environment_map_top(scene_flow_scene(), oot_core_skybox_time(), oot_core_skybox_settings()),
        environment_map_floor(scene_flow_scene(),oot_core_skybox_time()));
}

/* The nightmare's own environment has fog RGB (0,20,35). Until its cloud
 * skybox is imported, use that horizon colour rather than Kokiri daylight. */
static void __attribute__((optimize("Os"), noinline)) cutscene_sky_update(void)
{
    static int last_key = -1;
    static unsigned short last_top, last_floor;
    int nightmare = cutscene_is_playing() && cutscene_id() == CUTSCENE_NIGHTMARE;
    if(cutscene_is_playing() && (cutscene_id()==CUTSCENE_EMERALD2 ||
       cutscene_id()==CUTSCENE_EMERALD3 || cutscene_id()==CUTSCENE_EMERALD8))nightmare=2;
    unsigned int row, lines = 240;
    volatile jo_color *sky = (volatile jo_color *)(JO_VDP2_VRAM_B1 + 0x1f000);
#ifdef DOSEI_HIRES
    lines = 480;
#endif
    unsigned alpha = cutscene_fade_colour() == CUTSCENE_FADE_BLACK ? cutscene_fade_alpha() : 0;
    int field = scene_flow_scene() == SCENE_SPOT00;
    int key = nightmare | (alpha << 2) | (field << 10);
    unsigned short top = environment_map_top(scene_flow_scene(), oot_core_skybox_time(), oot_core_skybox_settings());
    unsigned short floor = environment_map_floor(scene_flow_scene(),oot_core_skybox_time());
    if (last_key == key && last_top == top && last_floor == floor) return;
    last_key = key;
    last_top = top; last_floor = floor;
    for (row = 0; row < lines - 1; ++row) {
        unsigned c = nightmare==2 ? JO_COLOR_RGB(0,0,0) : nightmare ? JO_COLOR_RGB(0, 20, 35) :
            environment_field_horizon(row * 240 / lines, top, floor);
        unsigned scale = 255 - alpha;
        sky[row] = 0x8000u | (((c & 31u) * scale / 255u)) |
            ((((c >> 5) & 31u) * scale / 255u) << 5) |
            ((((c >> 10) & 31u) * scale / 255u) << 10);
    }
}

/* TITLEPTH.BIN (tools/build_cart_tables.py), bound into the cart carve at
 * boot (BUG-043): 'KTPT', u16 shots, u16 points per shot, title_point_t. */
static const title_point_t *title_points;
static unsigned int title_shot_points;
typedef char title_point_is_10_bytes[sizeof(title_point_t) == 10 ? 1 : -1];
bool __attribute__((optimize("Os"), noinline)) recomp_title_paths_bind(const uint8_t *blob, uint32_t bytes)
{
    unsigned int points;
    title_points = 0;
    if (!blob || bytes < 8 || blob[0] != 'K' || blob[1] != 'T' ||
        blob[2] != 'P' || blob[3] != 'T' ||
        ((blob[4] << 8) | blob[5]) != TITLE_SHOT_COUNT)
        return false;
    points = (unsigned int)(blob[6] << 8) | blob[7];
    /* index + 1 reaches 64 (scaled / TICKS < 64): need 65 per shot. */
    if (points < 65 || bytes != 8 + TITLE_SHOT_COUNT * points * 10)
        return false;
    title_shot_points = points;
    title_points = (const title_point_t *)(blob + 8);
    return true;
}

/* Authored travelling shots: 10 seconds each, fairy subjects beside logo.
 * Interpolate baked headings, not the rounded path tangent (which wobbled).
 * All runtime math is integer; offline builder checks every flight segment. */
static void __attribute__((optimize("Os"), noinline)) title_showcase_camera(unsigned int tick)
{
    unsigned int shot = (tick / TITLE_SHOT_TICKS) % TITLE_SHOT_COUNT;
    unsigned int scaled = (tick % TITLE_SHOT_TICKS) * 64;
    unsigned int index = scaled / TITLE_SHOT_TICKS;
    int fraction = scaled % TITLE_SHOT_TICKS;
    const title_point_t *a;
    if (!title_points)
        return;                         /* TITLEPTH.BIN missing: hold the view */
    a = &title_points[shot * title_shot_points + index];
    const title_point_t *b = a + 1;
    recomp_camera.x = a->x + (b->x-a->x)*fraction/TITLE_SHOT_TICKS;
    recomp_camera.y = a->y + (b->y-a->y)*fraction/TITLE_SHOT_TICKS;
    recomp_camera.z = a->z + (b->z-a->z)*fraction/TITLE_SHOT_TICKS;
    recomp_yaw = (uint16_t)(a->yaw + (int16_t)(b->yaw-a->yaw)*fraction/TITLE_SHOT_TICKS);
    recomp_pitch = a->pitch + (b->pitch-a->pitch)*fraction/TITLE_SHOT_TICKS;
}

/* Standing exactly on a floor, the test kokiri_collision_fall uses. */
static bool link_standing(void)
{
    int32_t floor;
    return kokiri_collision_floor(recomp_link.x, recomp_link.z,
                                  recomp_link.y - RECOMP_LINK_EYE_HEIGHT + 4, &floor) &&
           recomp_link.y == floor + RECOMP_LINK_EYE_HEIGHT;
}

/* Model-local (x, z) -> world, as SkelAnime_UpdateTranslation turns root
** motion by the facing: x cos + z sin, z cos - x sin. Q8 in, whole units out. */
static void link_local_move(int32_t local_x_q8, int32_t local_z_q8, uint16_t yaw)
{
    int32_t sine, cosine;
    kokiri_camera_sincos(yaw, &sine, &cosine);
    recomp_link.x += (local_x_q8 * (cosine / 256) + local_z_q8 * (sine / 256)) / 65536;
    recomp_link.z += (local_z_q8 * (cosine / 256) - local_x_q8 * (sine / 256)) / 65536;
}

/* func_8083A5C4, then the source's next floor ray from +50, which stands the
** actor on the ledge top while the clip hangs the body below it. */
static bool link_start_hang(const bg_hit_t *wall, int32_t dist, bg_vec_t feet,
                            bool walk_off)
{
    int32_t floor;
    uint16_t facing;
    player_hang_place(wall, dist, &feet, &facing, !walk_off);
    if (!kokiri_collision_floor(feet.x, feet.z, feet.y + 49, &floor) ||
        floor < feet.y)
        return false;
    recomp_link.x = feet.x;
    recomp_link.y = floor + RECOMP_LINK_EYE_HEIGHT;
    recomp_link.z = feet.z;
    recomp_link_yaw = facing;
    link_velocity_y_q8 = 0;
    link_fall_remainder_q8 = 0;
    link_fall_peak_y = recomp_link.y;
    link_air_speed_q8 = 0; link_air_evade = false;
    link_hang_walk_off = walk_off;
    link_anim_hang(walk_off);
    /* NA_SE_VO_LI_HANG (and SLIPDOWN walking off): no resident sample
    ** (BUG-007). */
    return true;
}

/* func_8083AA10 on the step Link walks or rolls off an edge: revert, fall,
** jump automatically (player_air.c), or hang (func_8083A6AC). */
static void link_leave_ground(int32_t from_x, int32_t from_z,
                              int32_t speed_q8, uint16_t heading)
{
    player_leave_t leave;
    int32_t floor, launch = 0;
    int32_t feet = recomp_link.y - RECOMP_LINK_EYE_HEIGHT;
    player_leave_action_t act;

    leave.ground_leave = true;
    leave.swinging = gameplay.swing != 0;
    leave.prev_floor_property = link_floor_property;
    leave.y_dist_to_floor = kokiri_collision_floor(recomp_link.x, recomp_link.z,
                                                   feet, &floor)
                          ? feet - floor : 32000;
    leave.speed_q8 = speed_q8;
    leave.yaw_diff = (int16_t)(uint16_t)(heading - recomp_link_yaw);
    act = player_leave_ground(&leave, &launch);
    if (act == PLAYER_LEAVE_REVERT_XZ || act == PLAYER_LEAVE_REVERT_STOP) {
        recomp_link.x = from_x;
        recomp_link.z = from_z;
        if (act == PLAYER_LEAVE_REVERT_STOP)
            link_anim_cancel_roll();
    } else if (act == PLAYER_LEAVE_JUMP || act == PLAYER_LEAVE_RUN_JUMP) {
        link_velocity_y_q8 = launch;
        link_fall_remainder_q8 = 0;
        link_anim_auto_jump(act == PLAYER_LEAVE_RUN_JUMP);
        /* NA_SE_VO_LI_AUTO_JUMP + jumping sfx: the Y jump's cue already. */
        action_audio_events(GP_EVENT_JUMP);
    } else if (act == PLAYER_LEAVE_HANG) {
        /* The line test runs after this step's first fall (PLAYER_HANG_LINE_DROP). */
        bg_vec_t pos = { recomp_link.x, feet - PLAYER_HANG_LINE_DROP, recomp_link.z };
        bg_vec_t prev = { from_x, feet, from_z };
        bg_hit_t wall;
        const bg_waterbox_t *box;
        int32_t dist = 0, surface, depth = BG_Y_MIN;
        if (bg_water_surface(pos.x, pos.z, kokiri_scene_room(), &surface, &box))
            depth = surface - pos.y;
        player_hang_t hang = player_hang_walk_off(&pos, &prev, depth,
                                                  link_floor_property, &wall, &dist);
        if (hang == PLAYER_HANG_LEDGE)
            link_start_hang(&wall, dist, pos, true);
        else if (hang == PLAYER_HANG_CLIMB) {
            /* func_8083A5C4 with Fclimb_startB, then onto the vine. */
            uint16_t facing;
            player_hang_place(&wall, dist, &pos, &facing, false);
            recomp_link.x = pos.x;
            recomp_link.y = pos.y + RECOMP_LINK_EYE_HEIGHT;
            recomp_link.z = pos.z;
            recomp_link_yaw = facing;
            link_velocity_y_q8 = 0;
            link_fall_remainder_q8 = 0;
            link_air_speed_q8 = 0; link_air_evade = false;
            player_climb_start_walk_off(&link_climb, &wall, &recomp_link_yaw);
        }
    }
}

/* M2e: Link's damage reactions (func_80837C0C), the death clip
 * (func_80836448) and the Game Over flow (game_over.c). Called once per
 * gameplay step after gameplay_step(). */
static bool death_reported;
static void enter_world(void);
static void __attribute__((optimize("Os"))) scene_music(void);
static void __attribute__((optimize("Os"))) respawn_after_game_over(void);

/* Source list8: Player_ActionHandler_12 precedes TALK. Probe without moving
 * Link; the existing traversal block still performs the selected action.
 * Open messages/menus retain A, including their final advance press. */
static bool ledge_claims_interact(const gameplay_input_t *action)
{
    link_state_t state = link_anim_state();
    int32_t velocity = 0;
    if (!action->interact || !action->moving || action->pause ||
        action->attack || action->shield || gameplay_blocks_world() ||
        gameplay.dead || gameplay.swing || gameplay.shielding ||
        link_water.phase || link_lift.phase || !link_on_ground || link_velocity_y_q8 ||
        (state != LINK_STATE_IDLE && state != LINK_STATE_WALK && state != LINK_STATE_RUN))
        return false;
    return player_ledge_action(&link_bg, true, true, &velocity) != PLAYER_LEDGE_ACT_NONE;
}
/* Subj3 first-person look for this step. Called once per step: before a
 * shot when one fires (so the seed uses this frame's look), otherwise by the
 * camera pass. */
static bool fp_camera_done;
/* Debug readout: last Z+A refusal bits (see the evade block) and Link pose. */
unsigned recomp_evade_gates, recomp_evade_pose;
static void __attribute__((optimize("Os"), noinline)) first_person_camera_step(const player_input_t *in)
{
    int32_t focus[3];
    bg_vec_t at;
    link_focus(focus);
    at = (bg_vec_t){focus[0], focus[1], focus[2]};
    player_camera_first_person(&link_follow, &at, recomp_link_yaw,
        in->look_yaw_delta, in->look_pitch_delta,
        &recomp_camera, &recomp_yaw, &recomp_pitch, item_aim != 0);
}

/* Returns true when Continue respawned Link: the caller abandons the step. */
static bool __attribute__((optimize("Os"))) m2e_reactions(void)
{
    uint32_t e = gameplay.events, e2 = gameplay.events2;
    if (e2 & GP2_EVENT_DEATH) {
        /* NA_BGM_GAME_OVER: Red Book is allowed here -- the world is frozen
         * and nothing streams until Continue reloads the scene. */
        /* Keep the bank resident: CD-DA mutes it and restores it afterward. */
        music_play(NA_BGM_GAME_OVER);
        link_anim_react(LINK_CLIP_DEATH, LINK_REACT_NONE, true);
        death_reported = false;
        game_mode_set(GAME_MODE_GAME_OVER);
        player_input_set_dialogue(true);    /* D-pad drives the Yes/No cursor */
    } else if (e & GP_EVENT_KNOCKDOWN) {
        /* Knockback LARGE: front_downA when |yRot| > 0x4000, else back. */
        int16_t d = (int16_t)(gameplay.knock_yaw - recomp_link_yaw);
        bool front = d > 0x4000 || d < -0x4000;
        link_anim_react(front ? LINK_CLIP_DOWN_FRONT : LINK_CLIP_DOWN_BACK,
                        front ? LINK_CLIP_WAKE_FRONT : LINK_CLIP_WAKE_BACK, false);
    } else if ((e & GP_EVENT_HURT) && (e2 & GP2_EVENT_HIT_ANIM)) {
        bool back = (e2 & GP2_EVENT_HIT_BACK) != 0;
        unsigned int clip = (e2 & GP2_EVENT_HIT_HEAVY) ?
            (back ? LINK_CLIP_HIT_BACK : LINK_CLIP_HIT_FRONT) :
            (back ? LINK_CLIP_SHIT_BACK : LINK_CLIP_SHIT_FRONT);
        link_anim_react(clip, LINK_REACT_NONE, false);
    }
    /* EnSi token fanfare; first sticks/nuts use Player ITEM_GET below. */
    if ((e2 & GP2_EVENT_SMALL_FANFARE) && gameplay_is_talking())
        {fanfare_start=ticks;frozen_fanfare = music_play(NA_BGM_SMALL_ITEM_GET);}
    if ((gameplay.events & GP_EVENT_PICKUP) && gameplay.get_item == GP_GET_CONTAINER && gameplay_is_talking())
        {fanfare_start=ticks;frozen_fanfare = music_play(NA_BGM_HEART_GET);}
    if(gameplay_is_talking() && (e2 & (GP2_EVENT_CHEST_OPEN|GP2_EVENT_ITEM_FANFARE))){
        fanfare_start=ticks;
        if(scene_flow_is_interior()){shop_browsing=false;interior_camera();}
        if(e2 & GP2_EVENT_CHEST_OPEN)chest_scene_begin();
        item_fanfare_pending=(e2 & GP2_EVENT_CHEST_OPEN) && (e2 & GP2_EVENT_ITEM_FANFARE);
        frozen_fanfare=music_play((e2 & GP2_EVENT_CHEST_OPEN)?NA_BGM_OPEN_TRE_BOX:NA_BGM_ITEM_GET) || chest_scene;
    }
    if (!gameplay.dead)
        return false;
    if (!death_reported && link_anim_react_done()) {
        death_reported = true;
        gameplay_death_anim_done();
    }
    switch (game_over_step(menu_step, interact_pending || pause_pending)) {
    case GAME_OVER_RESULT_CONTINUE:
        /* Kaleido FINISH Yes: Play_TriggerRespawn at the last entrance,
         * health 3 hearts (game_over.c); scene state resets, the quest and
         * the save keep. */
        link_anim_react_cancel();
        player_input_set_dialogue(false);
        respawn_after_game_over();
        (void)game_over_events();
        return true;
    case GAME_OVER_RESULT_TITLE:
        minimap_session_reset();
        link_anim_react_cancel();
        gameplay_reset();
        recomp_link_active = false;
        game_mode_set(GAME_MODE_TITLE);
        player_input_set_dialogue(false);
        break;
    default:
        break;
    }
    {
        uint32_t go = game_over_events();
        action_audio_game_over(go);
        if (!(go & GAME_OVER_EV_SAVE))
            return false;
    }
    {
        /* Kaleido SAVE_PROMPT Yes: savedSceneId = this scene, Sram_WriteSave. */
        save_succeeded = active_slot<SAVE_FILE_SLOTS && save_device_write(active_slot);
        save_reported = true;
        game_over_save_done(save_succeeded);
    }
    return false;
}

static bool __attribute__((optimize("Os"))) recover_link_from_void(void)
{
    int32_t floor;

    if (!link_safe_position_valid ||
        recomp_link.y >= link_safe_position.y - LINK_VOID_DROP)
        return false;
    /* A genuine lower landing is still valid. Recovery is only for an open
     * hole with no walkable surface remaining beneath Link's feet. */
    if (kokiri_collision_floor(recomp_link.x, recomp_link.z,
                               recomp_link.y - RECOMP_LINK_EYE_HEIGHT, &floor))
        return false;
    recomp_link = link_safe_position;
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
bool recomp_chest_opening(void) {return chest_scene!=0;}
unsigned recomp_chest_frame(void) {unsigned f=(ticks-chest_start)/3;return f<133?f:132;}
int recomp_chest_index(void) {return (int)chest_scene-1;}
static void __attribute__((optimize("Os"))) chest_scene_step(void)
{
    /* Camera_Demo3 source opening orbit: first two spherical keyframes.
     * Fixed point adaptation, child eye target; collision clips the shot. */
    unsigned f=recomp_chest_frame();
    int32_t sn,cs,dx,dz;
    unsigned t=f>132?132:f;
    int radius=50+25*(int)t/146;
    uint16_t angle=recomp_link_yaw+0xD558-(0x5550*(int)t/146);
    bg_vec_t at={recomp_link.x,recomp_link.y-RECOMP_LINK_EYE_HEIGHT+40,recomp_link.z},hit;
    bg_vec_t eye;
    kokiri_camera_sincos(recomp_link_yaw,&sn,&cs);
    at.x+=sn*(20-20*(int)t/146)/65536;
    at.z+=cs*(20-20*(int)t/146)/65536;
    kokiri_camera_sincos(angle,&sn,&cs);
    eye.x=at.x+sn*radius/65536;eye.z=at.z+cs*radius/65536;
    eye.y=at.y+21-21*(int)t/146;
    if(bg_line(&at,&eye,&hit,BG_CHECK_ALL,BG_IGNORE_CAMERA,0))eye=hit;
    recomp_camera.x=eye.x;recomp_camera.y=eye.y;recomp_camera.z=eye.z;
    dx=at.x-eye.x;dz=at.z-eye.z;
    recomp_yaw=collide_heading(dx,dz);
    recomp_pitch=-(int16_t)collide_heading(at.y-eye.y,collide_isqrt((uint32_t)((int64_t)dx*dx+(int64_t)dz*dz)));
}
static void __attribute__((optimize("Os"))) chest_scene_begin(void)
{
    const kokiri_chest_t *c;
    int32_t sn,cs;
    chest_scene=gameplay.opened_chest;chest_start=ticks;
    if(!chest_scene)return;
    c=&kokiri_chests[chest_scene-1];
    kokiri_camera_sincos(c->yaw,&sn,&cs);
    recomp_link.x=c->x-sn*29/65536;recomp_link.z=c->z-cs*29/65536;
    recomp_link.y=c->y+RECOMP_LINK_EYE_HEIGHT;recomp_link_yaw=c->yaw;
    view_first_person=false;chest_scene_step();
}

static void __attribute__((optimize("Os"), noinline)) snap_camera_to_link(void)
{
    player_camera_reset(&link_camera);
    oot_follow_snap(&link_follow, &recomp_link, recomp_link_yaw);
    oot_follow_update(&link_follow, &recomp_link, recomp_link_yaw, false,
                      &recomp_camera, &recomp_yaw, &recomp_pitch);
    player_camera_constrain(&link_follow,&recomp_link,
        recomp_link.y-RECOMP_LINK_EYE_HEIGHT+oot_follow_scale.height+oot_follow_scale.y_offset,
        &recomp_camera,&recomp_pitch);
}

/* Put Link at one of a scene's ROM spawn points and make the camera agree.
 * `scene` is a table index; `spawn` indexes that scene's spawn list. */
static void __attribute__((optimize("Os"))) place_at_spawn(unsigned int scene, unsigned int spawn)
{
    player_camera_scene_default(scene == SCENE_SPOT00);
    if(save_state.source_scene!=scene_entries[scene].oot_scene)save_state.source_entrance=0xFFFF;
    save_state.source_scene=scene_entries[scene].oot_scene;
    combat_input_cancel(&combat_input);
    shop_browsing = false;   /* a scene load restores the fixed view */
    const scene_spawn_t *point = scene_flow_spawn(scene, spawn);

    /* recomp_link.y is the collision/eye position; the spawn records his FEET,
     * which is what the original stores. */
    view_first_person = c_up_pending = false;
    item_aim = 0;
    recomp_link.x = point->x;
    recomp_link.y = point->y + RECOMP_LINK_EYE_HEIGHT;
    recomp_link.z = point->z;
    recomp_link_yaw = point->yaw;
    link_velocity_y_q8 = 0;
    link_fall_remainder_q8 = 0;
    link_fall_peak_y = recomp_link.y;
    link_on_ground = false;
    link_floor_property = 0;
    player_water_reset(&link_water);
    player_bg_reset(&link_bg);
    player_push_cancel(&link_push);
    player_lift_cancel(&link_lift); world_props_drop_carried();
    link_sword_out = false; /* scenes start with the sword sheathed */
    link_slope=(player_slope_t){0};
    link_crawl.phase = PLAYER_CRAWL_NONE;
    kokiri_collision_actor_set_crawl(false);
    link_air_speed_q8 = 0; link_air_evade = false;
    link_safe_position = recomp_link;
    link_safe_position_valid = true;
    recomp_link_active = true;
    link_anim_reset();
    link_anim_trail_reset();
    link_anim_reset_state();
    kokiri_camera_reset_actor_motion();
    /* Navi belongs to Link, not to a room: every spawn -- a new file, a loaded
     * save, or the far side of a door -- puts her beside him at once, so she
     * is there on the first controllable frame instead of flying in. */
    { int32_t focus[3]; link_focus(focus); navi_reset(focus[0], focus[1], focus[2]); attention_navi_reset(focus); }
    snap_camera_to_link();
}

/* A prerendered interior is shown from the one viewpoint its backdrop was
 * rendered from, so the camera is planted rather than eased. Values come from
 * the room's bgCam entry; see tools/build_scene_table.py.
 *
 * The pitch is negated because OoT stores a downward look as a POSITIVE x
 * rotation while this project's recomp_pitch is negative for downward (the
 * diagnostic probes use -1820 for a slight downward tilt). */
static void __attribute__((optimize("Os"))) interior_camera(void)
{
    const scene_entry_t *entry = scene_flow_entry();

    recomp_camera.x = entry->cam_x;
    recomp_camera.y = entry->cam_y;
    recomp_camera.z = entry->cam_z;
    recomp_yaw = entry->cam_yaw;
    recomp_pitch = -(int32_t)(int16_t)entry->cam_pitch;
    if (scene_flow_pivot() && shop_browsing) {
        /* Camera_Data4 (CAM_SET_PIVOT_SHOP_BROWSING, bgCam 1): eye (0,60,40),
         * bgCam flags -1 so yaw = rot.y + data2 and pitch = rot.x + data3.
         * data2 is EnOssan's cameraFaceAngle: 0 at the counter, +-30 deg at
         * a shelf (shelf cursor, M3d). fov 60 (recomp_screen_distance 208). */
        recomp_camera = (camera_position_t){0, 60, 40};
        recomp_yaw = (uint16_t)(0x8000 + gameplay.shop_face * 65536 / 360);
        recomp_pitch = 0;
        return;
    }
    if (scene_flow_pivot()) {
        const bg_mesh_t *mesh = bg_scene_mesh();
        const int16_t *cam;
        int32_t sine, cosine;
        if (!mesh || mesh->camera_count < 2 || mesh->cameras[1].count < 3) return;
        cam = mesh->camera_vectors + mesh->cameras[1].first * 3;
        recomp_camera = (camera_position_t){cam[0], cam[1], cam[2]};
        recomp_yaw = kokiri_camera_facing(recomp_link.x - cam[0], recomp_link.z - cam[2]);
        kokiri_camera_sincos((uint16_t)(recomp_yaw - cam[4]), &sine, &cosine);
        /* Camera_Unique7: fixed eye, yaw tracks feet, pitch follows bg rotation. */
        recomp_pitch = -(int32_t)cam[3] * cosine / 65536;
    }
}

/* Walk Link through a doorway: load the far scene and stand him on its spawn.
 * Returns true when a transition or recovery happened, so the caller abandons
 * the rest of the step whose collision and actor pointers just unloaded. */
static bool __attribute__((optimize("Os"))) take_door(void)
{
    static unsigned notice_scene = ~0u;
    static int32_t notice_x, notice_z;
    int                 index;
    int scripted=oot_core_transition_request(false);
    unsigned target,spawn,keep_music,entrance,variant,layer;
    unsigned resident=scene_flow_scene(),resident_spawn=save_state.entrance;
    /* A missing destination must not reopen its box every movement step.
     * Rearm only after leaving its neighbourhood (or changing scenes). */
    if (notice_scene != resident || recomp_link.x < notice_x-600 ||
        recomp_link.x > notice_x+600 || recomp_link.z < notice_z-600 ||
        recomp_link.z > notice_z+600) notice_scene=~0u;

    index = scene_flow_door_at(recomp_link.x, recomp_link.y - RECOMP_LINK_EYE_HEIGHT,
                               recomp_link.z);
    if (index < 0 && scripted < 0)
        return (false);
    if(scripted == OOT_CORE_TRANSITION_RELOAD) {
        /* Level Select has no original entrance group. A frozen-room Sun's
         * Song still reloads the current scene; retain the unknown marker. */
        entrance = 0xFFFFu;
    } else if(scripted>=0) {
        if((unsigned)scripted>=SCENE_ENTRANCE_COUNT) {
            oot_core_transition_request(true);oot_core_cancel_transition_time();
            goto unavailable;
        }
        entrance=(unsigned)scripted;
    } else {
        entrance=scene_doors[index].entrance;
    }
    /* Play_Init indexes each entrance group with the current age/time/setup.
     * Non-cutscene BGM ownership comes from the group's child-day entry. */
    if(scripted == OOT_CORE_TRANSITION_RELOAD) {
        target=resident;spawn=resident_spawn;keep_music=1;
    } else {
        unsigned base_target=entrance<SCENE_ENTRANCE_COUNT ? scene_entrances[entrance].target : SCENE_COUNT;
        layer=base_target<SCENE_COUNT ?
            oot_core_destination_layer(scene_entries[base_target].oot_scene) : 0;
        variant=entrance+layer;
        target=variant<SCENE_ENTRANCE_COUNT ? scene_entrances[variant].target : SCENE_COUNT;
        spawn=variant<SCENE_ENTRANCE_COUNT ? scene_entrances[variant].spawn : 0;
        keep_music=entrance<SCENE_ENTRANCE_COUNT ? scene_entrances[entrance].keep_music : 0;
        if(layer>=4 && variant<SCENE_ENTRANCE_COUNT)keep_music=scene_entrances[variant].keep_music;
    }
    if(target>=SCENE_COUNT || spawn>=scene_entries[target].spawns) {
        if(scripted>=0) {
            oot_core_transition_request(true);oot_core_cancel_transition_time();
        }
        goto unavailable;
    }
    /* Consume before loading: scene_flow_load may destroy the requesting play
     * state even when a later asset read fails. Never retry its warp each step. */
    if(scripted>=0)oot_core_transition_request(true);
    game_mode_set(GAME_MODE_LOADING);
    if (!scene_flow_load(target, spawn)) {
        oot_core_cancel_transition_time();
        /* A failed load can already have replaced collision, pixels and NPCs.
         * Rebuild the source scene before resuming, at its saved entrance so
         * Link and the restored room bank agree even after room crossings. */
        if (!scene_flow_load(resident, resident_spawn))
            jo_core_error("Door scene recovery load failed");
        place_at_spawn(resident, resident_spawn);
        gameplay_reset();
        if (scene_flow_is_interior()) interior_camera();
        game_mode_set(GAME_MODE_PLAY);
        gameplay_actor_message(0xFF00);
        return (true);
    }
    /* Record where the player now is, so a save made here reloads here. */
    save_state.scene_id = (uint8_t)scene_flow_entry()->save_scene;
    save_state.entrance = (uint8_t)spawn;
    if(!keep_music)scene_music();
    place_at_spawn(target, spawn);
    save_state.source_entrance=(uint16_t)entrance;
    /* Per-scene state goes; the save (gear, rupees, quest flags) does not. */
    gameplay_reset();
    if (scene_flow_is_interior())
        interior_camera();
    game_mode_set(GAME_MODE_PLAY);
    story_route_arrive(spawn);
    return (true);
unavailable:
    if (notice_scene == resident) return false;
    notice_scene=resident;notice_x=recomp_link.x;notice_z=recomp_link.z;
    gameplay_actor_message(0xFF00);
    return true;
}

/* Area themes follow the scene actually loaded, including Continue. */
static void __attribute__((optimize("Os"))) scene_music(void)
{
    oot_song_t song = scene_flow_entry()->save_scene == SAVE_SCENE_KOKIRI_SHOP
        ? NA_BGM_SHOP : scene_flow_entry()->save_scene == SAVE_SCENE_DEKU_TREE_BOSS
        ? (gohma_defeated() ? NA_BGM_BOSS_CLEAR : save_get_event_chk_inf(EVENTCHKINF_BEGAN_GOHMA_BATTLE) ? NA_BGM_BOSS : NA_BGM_DUNGEON)
        : scene_flow_entry()->save_scene == SAVE_SCENE_DEKU_TREE
        ? NA_BGM_DUNGEON : scene_flow_entry()->save_scene == SAVE_SCENE_LOST_WOODS
        ? NA_BGM_SARIA_THEME : scene_flow_entry()->save_scene == SAVE_SCENE_HYRULE_FIELD
        ? NA_BGM_FIELD_LOGIC : scene_flow_is_interior() ? NA_BGM_LINK_HOUSE : NA_BGM_KOKIRI;
    if(story_owl_talking()) song=NA_BGM_OWL;
    /* All-scenes entries play their own scene header seqId: a built-in
    ** route if songs.json has one, else the disc-baked area bank. */
    if (scene_flow_scene() >= SCENE_GENERIC_FIRST && !story_owl_talking()) {
        unsigned int seq = scene_flow_entry()->seq;
        if (seq == 0x7F || seq == 0x01) { music_silence(RECOMP_MUSIC_FADE_FRAMES); return; }
        if (music_song_routed((oot_song_t)seq)) {
            music_play_fade((oot_song_t)seq, RECOMP_MUSIC_FADE_FRAMES);
            return;
        }
        if (!music_area_play(seq, RECOMP_MUSIC_FADE_FRAMES))
            music_silence(RECOMP_MUSIC_FADE_FRAMES); /* sequence not baked */
        return;
    }
    music_play_fade(song, RECOMP_MUSIC_FADE_FRAMES);
}

/* Let z_parameter's source state machine accelerate the clock, reload frozen
 * rooms, or enter dungeon-special mode. Song of Time retains the human's
 * explicitly requested reversible age shortcut. */
static bool __attribute__((optimize("Os"))) finish_ocarina_song(void)
{
    unsigned song=oot_core_ocarina_song();
    unsigned scene,spawn,old_age=save_state.link_age,new_age=old_age ? 0 : 1;
    /* Requested shortcut: Song of Time toggles age. Reload at the
     * saved entrance so collision, actor layer and the new model agree. */
    if(song==11) {
        scene=scene_flow_scene();spawn=save_state.entrance;
        save_state.link_age=new_age;
        game_mode_set(GAME_MODE_LOADING);
        if(!scene_flow_load(scene,spawn)) {
            save_state.link_age=old_age;
            if(!scene_flow_load(scene,spawn))jo_core_error("Time song scene recovery load failed");
        } else save_set_link_age(new_age);
        place_at_spawn(scene,spawn);
        gameplay_reset();
        if(scene_flow_is_interior())interior_camera();
        scene_music();
        game_mode_set(GAME_MODE_PLAY);
        return true;
    }
    return song==10 && oot_core_ocarina_sun_start();
}

/* Menu open, navigation and the press that closes it all belong to pause.
 * In particular B must not cancel the song and arrows must not sound notes. */
static bool step_core_gameplay(const gameplay_input_t *action, bool was_paused)
{
    unsigned note;
    if (was_paused || gameplay_is_paused()) return false;
    oot_core_frame(action);
    note = oot_core_ocarina_note();
    if (note) action_audio_ocarina(note - 1);
    return finish_ocarina_song();
}

static bool __attribute__((optimize("Os"), noinline)) finish_boss_warp(void)
{
    unsigned scene,spawn;
    bool first=!save_get_event_chk_inf(EVENTCHKINF_ENTERED_BLUE_WARP);
    if(!gohma_warp_ready())return false;
    scene=scene_flow_index_for_save(SAVE_SCENE_KOKIRI_FOREST);
    spawn=save_get_event_chk_inf(EVENTCHKINF_ENTERED_BLUE_WARP)?11:0;
    game_mode_set(GAME_MODE_LOADING);
    if(!scene_flow_load(scene,spawn)) {
        scene=scene_flow_index_for_save(SAVE_SCENE_DEKU_TREE_BOSS);spawn=0;
        if(!scene_flow_load(scene,spawn))jo_core_error("Boss warp recovery load failed");
    } else {
        /* Commit only after successful destination load; source save scene is
         * still the boss. Heart collectible 0x1f is deliberately independent. */
        save_finish_deku_warp();
    }
    save_state.scene_id=(uint8_t)scene_flow_entry()->save_scene;
    save_state.entrance=(uint8_t)spawn;
    place_at_spawn(scene,spawn);gameplay_reset();scene_music();
    game_mode_set(GAME_MODE_PLAY);
    if(first && save_check_quest_item(QUEST_KOKIRI_EMERALD)) {
        save_state.entrance=11;
        if(!cutscene_start(CUTSCENE_EMERALD1))jo_core_error("Tree aftermath load failed");
    }
    return true;
}

/* BUG-049/070: Kaleido Continue Yes. Link respawns at the last entrance.
 * Tree rooms share one scene id but use separate streamed banks.  Reload even
 * when the scene is resident: otherwise an entrance in (for example) room 8
 * can put Link at that room's coordinates over the old room 0 bank/collision.
 * That was the sky fall and crash after Continue.  A failed destination load
 * retries the resident scene at spawn 0, so LOADING never resumes over a
 * partial collision or room bank. */
static void __attribute__((optimize("Os"))) respawn_after_game_over(void)
{
    unsigned int scene = scene_flow_index_for_save(save_state.scene_id);
    unsigned int spawn = save_state.entrance;
    unsigned int resident = scene_flow_scene();

    /* Kaleido FINISH sets this before Play_TriggerRespawn. Keep the same
     * minimum here too: a failed/old Game Over path must never re-enter the
     * newly loaded room at zero health. */
    if (save_state.health < GAME_OVER_CONTINUE_HEALTH)
        save_state.health = GAME_OVER_CONTINUE_HEALTH;
    if (spawn >= scene_entries[scene].spawns)
        spawn = 0;
    game_mode_set(GAME_MODE_LOADING);
    if (!scene_flow_load(scene, spawn)) {
        /* A partial load may already have replaced the collision (BUG-002):
         * reload the resident scene so its ground matches, spawn 0. */
        scene = resident;
        spawn = 0;
        if (!scene_flow_load(scene, spawn)) {
            jo_core_error("Continue recovery load failed");
            return;
        }
    }
    save_state.scene_id = (uint8_t)scene_flow_entry()->save_scene;
    save_state.entrance = (uint8_t)spawn;
    scene_music();
    place_at_spawn(scene, spawn);
    gameplay_reset();
    if (scene_flow_is_interior())
        interior_camera();
    game_mode_set(GAME_MODE_PLAY);
}

static void __attribute__((optimize("Os"))) enter_world(void)
{
    unsigned int scene = scene_flow_index_for_save(save_state.scene_id);

    /* The file select has already set up the save -- a new file in Link's
     * house, or a loaded one wherever it was saved -- so the scene to enter
     * comes from there rather than being assumed to be the forest. */
    if (scene_flow_load(scene, save_state.entrance)) {
        scene_music();
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
    if (!recomp_link_active && kokiri_collision_spawn(&recomp_link)) {
        recomp_link_yaw = recomp_yaw;
        link_velocity_y_q8 = 0;
        link_fall_remainder_q8 = 0;
        link_fall_peak_y = recomp_link.y;
        link_on_ground = false;
        link_floor_property = 0;
        player_water_reset(&link_water);
        player_bg_reset(&link_bg);
        player_push_cancel(&link_push);
        player_lift_cancel(&link_lift); world_props_drop_carried();
        link_slope=(player_slope_t){0};
        link_crawl.phase = PLAYER_CRAWL_NONE;
        kokiri_collision_actor_set_crawl(false);
        link_air_speed_q8 = 0; link_air_evade = false;
        link_safe_position = recomp_link;
        link_safe_position_valid = true;
        recomp_link_active = true;
        /* Spawn standing, not mid-clip from a previous session. Both calls are
         * needed: one clears the cached pose, the other the locomotion state
         * that selects it. */
        link_anim_reset();
        link_anim_trail_reset();
        link_anim_reset_state();
        kokiri_camera_reset_actor_motion();
        { int32_t focus[3]; link_focus(focus); navi_reset(focus[0], focus[1], focus[2]); attention_navi_reset(focus); }
        /* gameplay_reset() clears per-scene state only. The quest state was
         * set by the file select -- save_new_game() for a new file, or the
         * loaded save for a continue -- so it must NOT be touched here. */
        gameplay_reset();
        player_input_reset();
        kokiri_camera_set_walk(false);
    }
    if (recomp_link_active) {
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
static void __attribute__((optimize("Os"))) level_select_enter(void)
{
    unsigned scene=level_select.scene,room=level_select.room,spawn=0,i;
    const scene_entry_t *entry=&scene_entries[scene];
    bool exact=false;
    camera_position_t position={0};uint16_t yaw=0;
    for(i=0;i<entry->spawns;++i) {
        const scene_spawn_t *p=scene_flow_spawn(scene,i);
        if(p->room==room){spawn=i;exact=true;break;}
    }
    if(!exact) {
        for(i=0;i<KOKIRI_PORTAL_COUNT;++i) {
            const kokiri_portal *p=&kokiri_portals[i];int32_t sn,cs,distance;
            if(p->scene!=scene || (p->front!=(int)room && p->back!=(int)room) || p->kind==2)continue;
            distance=p->front==(int)room?-110:110;
            kokiri_camera_sincos(p->yaw,&sn,&cs);
            position=(camera_position_t){p->x+distance*sn/65536,p->y+RECOMP_LINK_EYE_HEIGHT,p->z+distance*cs/65536};
            yaw=p->yaw+(distance<0?0x8000:0);break;
        }
        if(i==KOKIRI_PORTAL_COUNT){level_select.failed=true;return;}
    }
    level_select_prepare();save_state.entrance=spawn;active_slot=SAVE_FILE_SLOTS;
    /* z_select: starting a map explicitly initializes its sky clock. */
    oot_core_session_reset(save_state.day_time);
    minimap_session_reset();game_mode_set(GAME_MODE_LOADING);
    if(!scene_flow_load(scene,spawn) || (!exact && !kokiri_scene_load_bank(scene,room))) {
        level_select.failed=true;game_mode_set(GAME_MODE_FILE_SELECT);return;
    }
    place_at_spawn(scene,spawn);
    if(!exact) {
        bg_vec_t probe={position.x,position.y,position.z};int32_t floor=bg_floor(&probe,BG_IGNORE_ENTITY,0);
        if(floor!=BG_Y_MIN && floor>position.y-RECOMP_LINK_EYE_HEIGHT-200)position.y=floor+RECOMP_LINK_EYE_HEIGHT;
        recomp_link=position;recomp_link_yaw=yaw;link_safe_position=position;link_fall_peak_y=position.y;
        snap_camera_to_link();
    }
    gameplay_reset();scene_music();level_select.visible=false;save_reported=false;
    game_mode_set(GAME_MODE_PLAY);
}
static void __attribute__((optimize("Os"))) file_select_tick(void)
{
    file_select_input   pick = {0};
    file_select_result  chosen;

    pick.up = menu_step < 0;
    pick.down = menu_step > 0;
    pick.confirm = interact_pending;
    pick.cancel = cancel_pending;
    if(level_select.visible) {
        /* ticks is normalized to 60 Hz on both PAL and NTSC. Do not queue
         * inputs during the title cheat's 2.5-second opening delay. */
        if ((unsigned)(ticks-level_select_open_tick)<150u) {
            menu_step=menu_dx=menu_dy=menu_page=0;c_assign=c_use=0;
            interact_pending=cancel_pending=pause_pending=false;
            return;
        }
        level_select_move(menu_dy,menu_dx);
        if(menu_page<0)level_select_toggle_max_gear();
        if(menu_page>0)level_select_toggle_era();
        menu_step=menu_dx=menu_dy=menu_page=0;c_assign=c_use=0;
        interact_pending=cancel_pending=pause_pending=false;
        if(pick.cancel){level_select.visible=false;game_mode_set(GAME_MODE_TITLE);player_input_reset();player_input_set_dialogue(false);music_play(NA_BGM_TITLE);}
        else if(pick.confirm)level_select_enter();
        return;
    }
    menu_step = menu_dx = menu_dy = menu_page = 0;
    c_assign = c_use = 0;
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
        /* FileSelect_LoadGame resets skyboxTime, not the loaded dayTime. */
        oot_core_session_reset(0);
        minimap_session_reset();
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
            /* Sram_OpenSave: an overworld/house save resumes in Link's
             * house; the Deku Tree at its entrance. */
            save_resume_remap();
            enter_world();
        }
    }
}

/* Saturn pad -> normalized CAMERA_* bits. Jo's JO_KEY_* values are SGL/CS
 * bitfield positions; the gameplay code works in its own platform-independent
 * bit set so the mapping lives in exactly one place. */
static uint16_t recomp_pad_snapshot(void)
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

static void recomp_vblank(void)
{
    /* Jo refreshes held inputs before this callback. Preserve press edges
     * across slow draws instead of relying on its one-VBlank on_keydown. */
    static bool cheat_start_held;
    bool connected = jo_is_pad1_available();
    uint16_t snapshot = connected ? recomp_pad_snapshot() : 0;
    if (!(snapshot & CAMERA_START)) cheat_start_held = false;
    if (minimap_cheat_sample(snapshot)) cheat_start_held = true;
    input_edge_sample(&start_edge, (snapshot & CAMERA_START) && !cheat_start_held);
    skip_input_sample(&skip_input, (game_mode() == GAME_MODE_CUTSCENE &&
                      cutscene_is_playing()) || gohma_cinematic(),
                      connected && jo_is_pad1_key_pressed(JO_KEY_START),
                      ticks, gohma_cinematic()?gohma_shot_key():cutscene_shot_key());
    /* One normalized snapshot per VBlank. All button state -- including every
     * chord -- is read from this single sample, so two consumers can never
     * disagree about which buttons were down on a given frame. */
    player_input_sample_3d(snapshot,
        connected && jo_is_input_analog(0),
        connected ? jo_get_input_axis(0, JoAxis1) : 128,
        connected ? jo_get_input_axis(0, JoAxis2) : 128,
        connected ? jo_get_input_axis(0, JoAxis3) : 0,
        connected ? jo_get_input_axis(0, JoAxis4) : 0);
    /* BDCLMD=0 keeps the border outside the active picture black. */
    *sgl_vdp2_shadow(0) &= (unsigned short)~0x0100;
    JO_VDP2_TVMD = *sgl_vdp2_shadow(0);
    phase += 60;
    while (phase >= refresh) { phase -= refresh; ++ticks; }
}

bool __attribute__((optimize("Os"))) recomp_init(void)
{
    player_camera_experiment_reset();
    int length = 0;
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
    recomp_collision_indexed = scene_collision_indexed;
    if (!kokiri_collision_spawn(&recomp_camera)) return false;
    /* Raise the starting eye without bypassing walls/ceilings. */
    kokiri_collision_move(&recomp_camera, 0, 24, 0);
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
    /* Whole image in one CD read, one VDP2 upload (row reads drew visibly). */
    strip.data = (jo_color *)ram_cart_load_scratch("TITLE.RGB", &length);
    if (!strip.data || length != 512 * 256 * 2) return false;
    strip.width = 512; strip.height = 256;
    jo_clear_background(0);
    jo_set_background_sprite(&strip, 0, 0);
    prompt = (unsigned short *)jo_fs_read_file("START.RGB", &length);
    if (!prompt || length != 84 * 14 * 2) return false;
    refresh = (JO_VDP2_TVSTAT & 1) ? 50 : 60;
    if (jo_core_add_vblank_callback(recomp_vblank) == 0)
        return false;

    return true;
}

/* Mido's OC cylinder (EnMd: radius 36, MASS_IMMOVABLE) against Link's 12:
 * Link takes the whole push, applied through the actor wall checks so it can
 * never shove him through scenery. Runs after the step's own movement. */
/* Player_Action_8084377C carries Link away at the knockback speed while the
 * knock-down animation plays. Stand-in: no knock-down animation yet, so input
 * is held for RECOMP_KNOCKDOWN_STEPS and the speed eases out (BUG-031). */
#define RECOMP_KNOCKDOWN_STEPS 45
static unsigned int knock_steps;
static int32_t      knock_rx, knock_rz;     /* Q16 remainders */

static void link_knockback(void)
{
    int32_t sine, cosine, dx, dz;
    if (gameplay_blocks_world() || gameplay.knock_speed <= 0)
        return;
    kokiri_camera_sincos(gameplay.knock_yaw, &sine, &cosine);
    knock_rx += (int32_t)(((int64_t)gameplay.knock_speed * sine) >> 16);
    knock_rz += (int32_t)(((int64_t)gameplay.knock_speed * cosine) >> 16);
    dx = knock_rx >> 16;
    dz = knock_rz >> 16;
    knock_rx -= dx << 16;
    knock_rz -= dz << 16;
    if (dx || dz)
        kokiri_collision_move_actor(&recomp_link, dx, 0, dz);
    gameplay.knock_speed -= gameplay.knock_speed >> 4;
    if (gameplay.knock_speed < 0x1000)
        gameplay.knock_speed = 0;
}

/* En_Goroiwa OC (MASS_HEAVY): Link is pushed out of the sphere's footprint
 * when their heights overlap. */
static void boulder_push_link(void)
{
    int32_t bx, by, bz, dx, dz, dist2, dist, push, feet;
    const int32_t reach = GP_BOULDER_RADIUS + GP_LINK_BODY_RADIUS;
    if (!gameplay_boulder_body(kokiri_scene_room(), &bx, &by, &bz))
        return;
    feet = recomp_link.y - RECOMP_LINK_EYE_HEIGHT;
    if (feet > by + GP_BOULDER_RADIUS || feet + GP_LINK_BODY_HEIGHT < by - GP_BOULDER_RADIUS)
        return;
    dx = recomp_link.x - bx;
    dz = recomp_link.z - bz;
    if (dx > reach || dx < -reach || dz > reach || dz < -reach)
        return;
    dist2 = dx * dx + dz * dz;
    if (dist2 >= reach * reach)
        return;
    dist = 1;
    while ((dist + 1) * (dist + 1) <= dist2)
        ++dist;
    if (!dist2) { dx = 0; dz = -1; dist = 1; }
    push = reach - dist;
    kokiri_collision_move_actor(&recomp_link, dx * push / dist, 0, dz * push / dist);
}

/* ANIM_FLAG_UPDATE_XZ for sword clips: the clip root's step-to-step motion
 * carries Link (Player_StartAnimMovement resets prevTransl when an attack
 * or its recovery starts), plus the forward lunge. Through wall checks. */
static unsigned int attack_root_clip = 0xFFFF, attack_root_swing;
static int32_t      attack_root_prev[3], attack_carry_x_q8, attack_carry_z_q8;

static void attack_root_motion(void)
{
    unsigned int clip, thirds, k;
    int32_t now[3], d[3] = { 0, 0, 0 }, sine, cosine, dx, dz;
    if (gameplay_blocks_world()) return;
    /* The wall push and rebounds outlive their clips (speedXZ decays under
     * the idle action), so the speed applies without a rooted clip too. */
    if (!gameplay_attack_time(&clip, &thirds)) {
        attack_root_clip = 0xFFFF;
        if (!gameplay.lunge_q16)
            return;
    } else {
        link_anim_clip_root(clip, thirds, now);
        if (clip != attack_root_clip || gameplay.swing_count != attack_root_swing) {
            attack_root_clip = clip;
            attack_root_swing = gameplay.swing_count;
            for (k = 0; k < 3; ++k) attack_root_prev[k] = now[k];
        }
        for (k = 0; k < 3; ++k) {
            d[k] = now[k] - attack_root_prev[k];
            attack_root_prev[k] = now[k];
        }
    }
    kokiri_camera_sincos(recomp_link_yaw, &sine, &cosine);
    /* Same model->world mapping as player_crawl.c apply_xz (x0.01). */
    attack_carry_x_q8 += (d[0] * (cosine / 256) + d[2] * (sine / 256)) / 100;
    attack_carry_z_q8 += (d[2] * (cosine / 256) - d[0] * (sine / 256)) / 100;
    if (gameplay.lunge_q16) {
        attack_carry_x_q8 += (int32_t)(((int64_t)gameplay.lunge_q16 * sine) >> 24);
        attack_carry_z_q8 += (int32_t)(((int64_t)gameplay.lunge_q16 * cosine) >> 24);
    }
    dx = attack_carry_x_q8 / 256; attack_carry_x_q8 %= 256;
    dz = attack_carry_z_q8 / 256; attack_carry_z_q8 %= 256;
    if (dx || dz)
        kokiri_collision_move_actor(&recomp_link, dx, 0, dz);
}

/* Player_Action_80845000 / 80845308: walking while the spin charges.
 * Facing stays; speed Math_AsymStepToF toward 0.2 of the stick's speed,
 * +1.0 / -0.5 a frame (114 / 57 Q8 a step); turning more than 90 degrees
 * first steps the speed to 0 (1.0 a frame) and then takes the new heading;
 * smaller turns ease 0.1 a frame (about 1/15 a step). Sideways travel plays
 * the side-walk clip. Clip speed clamp(speed * 0.5, 0.5, 1.0). */
static int32_t  charge_walk_q8;
static uint16_t charge_walk_heading, charge_walk_thirds;
static bool     charge_walk_side;

static void charge_walk(const player_input_t *pad, bool allowed)
{
    uint16_t heading = recomp_link_yaw;
    int32_t speed = 0, target, turn, step;
    bool moving;
    if (!allowed || gameplay.attack_phase != 4) {
        charge_walk_q8 = 0;
        charge_walk_thirds = 0;
        return;
    }
    moving = player_input_motion(pad, recomp_yaw, &heading, &speed);
    target = moving ? speed / 5 : 0;
    if (!charge_walk_q8)
        charge_walk_heading = heading;
    turn = (int32_t)(int16_t)(uint16_t)(heading - charge_walk_heading);
    if (moving && (turn > 0x4000 || turn < -0x4000)) {
        charge_walk_q8 -= 114;
        if (charge_walk_q8 <= 0) {
            charge_walk_q8 = 0;
            charge_walk_heading = heading;
        }
    } else {
        if (charge_walk_q8 < target) {
            charge_walk_q8 += 114;
            if (charge_walk_q8 > target) charge_walk_q8 = target;
        } else if (charge_walk_q8 > target) {
            charge_walk_q8 -= 57;
            if (charge_walk_q8 < target) charge_walk_q8 = target;
        }
        if (moving)
            charge_walk_heading = (uint16_t)(charge_walk_heading + turn / 15);
    }
    if (!charge_walk_q8)
        return;
    kokiri_camera_move_heading(&recomp_link, charge_walk_heading, charge_walk_q8);
    turn = (int32_t)(int16_t)(uint16_t)(charge_walk_heading - recomp_link_yaw);
    if (turn < 0) turn = -turn;
    charge_walk_side = turn > 0x2000 && turn < 0x6000;
    /* speed a frame = q8 x 1.5 / 256; clip thirds = 3 x clamp(speed/2). */
    step = charge_walk_q8 * 9 / 1024;
    if (step < 2) step = 2;
    if (step > 3) step = 3;
    charge_walk_thirds = (uint16_t)(charge_walk_thirds + step);
}

/* Player focus.pos in world units: the posed head point (link_anim_focus),
 * placed like the blade. Navi's anchor. */
static void link_focus(int32_t out[3])
{
    int32_t local[3], sine, cosine;
    link_anim_focus(local);
    kokiri_camera_sincos(recomp_link_yaw, &sine, &cosine);
    out[0] = recomp_link.x + (int32_t)((((int64_t)cosine * local[0]) + ((int64_t)sine * local[2])) >> 32);
    out[1] = recomp_link.y - RECOMP_LINK_EYE_HEIGHT + link_anim_y_offset_q8() / 256 + local[1] / 65536;
    out[2] = recomp_link.z + (int32_t)((((int64_t)cosine * local[2]) - ((int64_t)sine * local[0])) >> 32);
}

/* gameplay.c's weapon hooks.  Sword uses the Kokiri sword line; a held Deku
 * Stick uses the source L_HAND attachment line.  Both are Link-local Q16,
 * y up from drawn feet, then placed like link_anim_trail_update. */
bool gameplay_blade_points(int32_t base[3], int32_t tip[3])
{
    int32_t blade[2][3], sine, cosine, feet;
    unsigned int end;
    if (!recomp_link_active)
        return false;
    if (player_items_stick()) link_anim_stick(blade);
    else link_anim_blade(blade);
    kokiri_camera_sincos(recomp_link_yaw, &sine, &cosine);
    feet = recomp_link.y - RECOMP_LINK_EYE_HEIGHT + link_anim_y_offset_q8() / 256;
    for (end = 0; end < 2; ++end) {
        int32_t *out = end ? tip : base;
        const int32_t *l = blade[end];
        out[0] = recomp_link.x + (int32_t)((((int64_t)cosine * l[0]) + ((int64_t)sine * l[2])) >> 32);
        out[1] = feet + l[1] / 65536;
        out[2] = recomp_link.z + (int32_t)((((int64_t)cosine * l[2]) - ((int64_t)sine * l[0])) >> 32);
    }
    return true;
}

bool __attribute__((noinline)) gameplay_link_point(unsigned int limb, int32_t out[3])
{
    int32_t l[3], sine, cosine;
    if (!recomp_link_active)
        return false;
    link_anim_limb(limb, l);
    kokiri_camera_sincos(recomp_link_yaw, &sine, &cosine);
    /* Q16 x Q16 in 32 bits: 1/16-unit local, 1/4096 trig; ample for a hand. */
    l[0] >>= 12; l[2] >>= 12; sine >>= 4; cosine >>= 4;
    out[0] = recomp_link.x + ((cosine * l[0] + sine * l[2]) >> 16);
    out[1] = recomp_link.y - RECOMP_LINK_EYE_HEIGHT + link_anim_y_offset_q8() / 256 + l[1] / 65536;
    out[2] = recomp_link.z + ((cosine * l[2] - sine * l[0]) >> 16);
    return true;
}

/* BgCheck_EntityLineTest1 (walls, one face), not an entity-ignored poly,
 * not floor type 6. Dyna attachment (func_8002F9EC) is not modelled. */
bool gameplay_blade_wall(const int32_t from[3], const int32_t to[3], unsigned int *material)
{
    bg_vec_t a = { from[0], from[1], from[2] }, b = { to[0], to[1], to[2] }, at;
    bg_hit_t hit;
    if (!bg_line(&a, &b, &at, BG_CHECK_WALL | BG_CHECK_ONE_FACE, BG_IGNORE_ENTITY, &hit))
        return false;
    if (bg_floor_type(&hit) == 6)
        return false;
    *material = bg_material(&hit);
    return true;
}

/* BgCheck_CameraLineTest1 (walls, floors, ceilings, one face; camera-
 * ignored polys skipped) from Link's focus to the actor's; a nearest hit
 * that SurfaceType_IsIgnoredByProjectiles does not block. */
bool attention_sight_blocked(const int32_t from[3], const int32_t to[3])
{
    bg_vec_t a = { from[0], from[1], from[2] }, b = { to[0], to[1], to[2] }, at;
    bg_hit_t hit;
    if (!bg_line(&a, &b, &at, BG_CHECK_ALL | BG_CHECK_ONE_FACE, BG_IGNORE_CAMERA, &hit))
        return false;
    return !(hit.ignore & BG_IGNORE_PROJECTILES);
}

/* Attention_ActorOnScreen: Actor_GetScreenPos of the focus through the live
 * camera (recomp_camera, recomp_yaw/pitch, screen distance). x in (-20, 340),
 * y in (-160, 400) of a 320x240 frame, i.e. |right| * dist < 180 * depth and
 * |up| * dist < 280 * depth. Actor_ProjectPos caps 1/w at 1, so a point at
 * or behind the eye is divided by 1: depth is clamped to 1 the same way. */
static int project_attention(const int32_t p[3], int32_t *screen_x, int32_t *screen_y)
{
    int32_t x = p[0] - recomp_camera.x, y = recomp_camera.y - p[1], z = p[2] - recomp_camera.z;
    int32_t sy, cy, sp, cp, horizontal, depth, right, up;
    int32_t dist = (int32_t)recomp_screen_distance();
    kokiri_camera_sincos(recomp_yaw, &sy, &cy);
    kokiri_camera_sincos((uint16_t)recomp_pitch, &sp, &cp);
    horizontal = (int32_t)(((int64_t)x * sy + (int64_t)z * cy) / 65536);
    right = (int32_t)((-(int64_t)x * cy + (int64_t)z * sy) / 65536);
    /* recomp_pitch is positive looking UP (oot_follow_update_profile), while
     * y here is camera-relative Y DOWN. Match main.c's slRotX(-recomp_pitch). */
    depth = (int32_t)(((int64_t)horizontal * cp - (int64_t)y * sp) / 65536);
    up = (int32_t)(((int64_t)y * cp + (int64_t)horizontal * sp) / 65536);
    int32_t divisor = depth < 1 ? 1 : depth;
    *screen_x = 160 + muldiv_s32(right, dist, divisor);   /* no ___divdi3 */
    *screen_y = 120 + muldiv_s32(up, dist, divisor);
    return depth;
}

bool attention_on_screen(const int32_t p[3])
{
    int32_t x,y;
    project_attention(p,&x,&y);
    return x > -20 && x < 340 && y > -160 && y < 400;
}

bool recomp_target_marker(int32_t *x, int32_t *y, bool *locked, unsigned *kind)
{
    actor_t *a = actor_resolve(gameplay.target ? gameplay.target : gameplay.arrow);
    int32_t focus[3];
    if (!a || a->kill || !(a->flags & ACTOR_FLAG_TARGETABLE)) return false;
    *locked = gameplay.target != 0;
    *kind = a->profile->category == ACTORCAT_ENEMY || a->profile->category == ACTORCAT_BOSS ?
        KOKIRI_RETICLE_ENEMY : a->profile->category == ACTORCAT_NPC ?
        KOKIRI_RETICLE_NPC : KOKIRI_RETICLE_POI;
    attention_focus(a,focus);
    /* Attention_Draw hover arrow: focus.y + lockOnArrowOffset * scale + 17. */
    if (!*locked) focus[1] += a->arrow_y + 17;
    return project_attention(focus,x,y) > 0 && *x >= 12 && *x < 308 && *y >= 12 && *y < 228;
}

bool recomp_push_prompt(void)
{
    return link_on_ground && !gameplay_blocks_world() && !gameplay.swing &&
           !gameplay.shielding && !link_lift.phase && !link_push.phase &&
           player_push_prompt(&link_bg);
}

/* En_Karebaba dying fall: Actor_MoveXZGravity + UpdateBgCheckInfo(10, 15,
 * 10). pos/d Q8 world. Wall: the move line 10 up hits a wall (x/z stop).
 * Ground: a floor between 10 above and the new feet (feet snap to it). */
bool karebaba_bg_move(int32_t pos[3], const int32_t d[3], bool *ground, bool *wall)
{
    bg_vec_t a = { pos[0] >> 8, (pos[1] >> 8) + 10, pos[2] >> 8 }, b, at;
    bg_hit_t hit;
    int32_t n[3] = { pos[0] + d[0], pos[1] + d[1], pos[2] + d[2] };
    b.x = n[0] >> 8; b.y = (n[1] >> 8) + 10; b.z = n[2] >> 8;
    *wall = bg_line(&a, &b, &at, BG_CHECK_WALL, BG_IGNORE_ENTITY, &hit);
    if (*wall) { n[0] = pos[0]; n[2] = pos[2]; }
    a.x = n[0] >> 8; a.y = (pos[1] >> 8) + 10; a.z = n[2] >> 8;
    b.x = a.x; b.y = n[1] >> 8; b.z = a.z;
    *ground = d[1] <= 0 && bg_line(&a, &b, &at, BG_CHECK_FLOOR, BG_IGNORE_ENTITY, &hit);
    if (*ground) n[1] = at.y * 256;
    pos[0] = n[0]; pos[1] = n[1]; pos[2] = n[2];
    return *ground || *wall;
}

/* Actor_UpdateBgCheckInfo(10, 13, 13) stand-in for the nutsball: a wall or
 * floor crossing on the move from the ball's centre stops it there. */
bool gameplay_ball_move(int32_t pos[3], int32_t dx, int32_t dy, int32_t dz)
{
    bg_vec_t a = { pos[0], pos[1] + GP_NUT_HEIGHT / 2, pos[2] };
    bg_vec_t b = { pos[0] + dx, pos[1] + dy + GP_NUT_HEIGHT / 2, pos[2] + dz }, at;
    bg_hit_t hit;
    if (bg_line(&a, &b, &at, BG_CHECK_WALL | BG_CHECK_FLOOR, BG_IGNORE_ENTITY, &hit)) {
        pos[0] = at.x; pos[1] = at.y - GP_NUT_HEIGHT / 2; pos[2] = at.z;
        return true;
    }
    pos[0] += dx; pos[1] += dy; pos[2] += dz;
    return false;
}



/* Player_ActionHandler_10: no Z-targeted A moves indoors (scene_room_type.h),
 * on floor type 7 or floor
 * effect 1 (sFloorType / SurfaceType_GetFloorEffect of Link's floor). */
static bool evade_floor_ok(void)
{
    bg_vec_t feet = { recomp_link.x, recomp_link.y - RECOMP_LINK_EYE_HEIGHT + 1, recomp_link.z };
    bg_hit_t floor;
    if (bg_floor(&feet, BG_IGNORE_ENTITY, &floor) == BG_Y_MIN)
        return true;
    return bg_floor_type(&floor) != 7 && bg_floor_effect(&floor) != 1;
}

static void mido_push_link(void)
{
    int32_t mx, mz, dx, dz, dist2, dist, push;
    if (save_state.scene_id != SAVE_SCENE_KOKIRI_FOREST ||
        !gameplay_mido_body(kokiri_scene_room(), &mx, &mz))
        return;
    dx = recomp_link.x - mx;
    dz = recomp_link.z - mz;
    if (dx > GP_MIDO_PUSH_RADIUS || dx < -GP_MIDO_PUSH_RADIUS ||
        dz > GP_MIDO_PUSH_RADIUS || dz < -GP_MIDO_PUSH_RADIUS)
        return;
    dist2 = dx * dx + dz * dz;
    if (dist2 >= GP_MIDO_PUSH_RADIUS * GP_MIDO_PUSH_RADIUS)
        return;
    dist = 1;
    while ((dist + 1) * (dist + 1) <= dist2)
        ++dist;
    if (!dist2) { dx = 0; dz = -1; dist = 1; }
    push = GP_MIDO_PUSH_RADIUS - dist;
    kokiri_collision_move_actor(&recomp_link, dx * push / dist, 0,
                                dz * push / dist);
}

void recomp_update(void)
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
    if(gohma_cinematic()) {
        if(input_edge_consume(&skip_input.request)&&skip_input.request_shot==gohma_shot_key())gohma_skip_shot();
        start_pressed=false;
    } else if (game_mode() != GAME_MODE_CUTSCENE)
        input_edge_consume(&skip_input.request);
    unsigned int now = ticks, elapsed = now - previous_tick, steps;
    /* Playtest refill cheat: only live, unpaused, living gameplay may consume
     * it. Anywhere else the sequence is reset and a stale trigger discarded. */
    if(game_mode()==GAME_MODE_PLAY && !gameplay_blocks_world() && !frozen_fanfare &&
       !game_over_active() && save_state.health) {
        if(minimap_cheat_refill_take()) {
            save_cheat_refill();
            action_audio_events(GP_EVENT_RUPEE);   /* existing SFX, no music */
        }
    } else minimap_cheat_refill_reset();
    if(minimap_cheat_chime()) {
        if(title_visible) {
            level_select_open();game_mode_set(GAME_MODE_FILE_SELECT);
            level_select_open_tick=now;
            slScrAutoDisp(NBG0ON);
            /* Keep the resident title score. CD startup plus another bank
             * upload must not determine when this menu accepts controls. */
            action_audio_events(GP_EVENT_RUPEE);
        } else frozen_fanfare=music_play(NA_BGM_SMALL_ITEM_GET);
        player_input_reset();interact_pending=cancel_pending=pause_pending=false;
        menu_step=menu_dx=menu_dy=menu_page=0;
    }
    if(frozen_fanfare) {
        previous_tick=now;
        player_input_reset();combat_input_cancel(&combat_input);
        if(chest_scene)chest_scene_step();
        else if(gameplay.get_item)gameplay.get_item_age=(uint16_t)((now-fanfare_start)/2);
        if(cdda_busy() || (chest_scene && recomp_chest_frame()<132))return;
        if(chest_scene){chest_scene=0;gameplay.get_item_age=0;snap_camera_to_link();}
        if(item_fanfare_pending){
            item_fanfare_pending=false;fanfare_start=now;
            if(music_play(NA_BGM_ITEM_GET))return;
        }
        frozen_fanfare=false;
    }
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
        (recomp_link_active || file_select_visible ||
         game_mode() == GAME_MODE_CUTSCENE);

    /* It owns the pad exactly the way a text box does: D-pad moves the cursor,
     * A confirms, B cancels, and B must not also toggle walk/run. Set before
     * the step, because the step is what reads it. */
    if (file_select_visible || game_mode() == GAME_MODE_CUTSCENE)
        player_input_set_dialogue(true);

    if (view_first_person && (game_mode() != GAME_MODE_PLAY || gameplay_blocks_world() ||
        gameplay.dead || scene_flow_is_interior() || link_crawl.phase != PLAYER_CRAWL_NONE)) {
        view_first_person = false;
        if (scene_flow_is_interior()) interior_camera();
        else snap_camera_to_link();
    }
    player_input_set_view_look(view_first_person);
    player_input_set_orbit(player_camera_orbit_active() &&
        game_mode()==GAME_MODE_PLAY && !gameplay_blocks_world() &&
        !gameplay.dead && !scene_flow_is_interior() && !view_first_person &&
        !gohma_cinematic());
    player_input_set_jump_button(ui_jump_mask());
    player_input_step(in_gameplay, &input);
    if (input.camera_orbit_turn) {
        player_camera_orbit_turn(input.camera_orbit_turn);
        action_audio_decomp_sfx(0x4809); /* NA_SE_SY_CURSOR: resident UI tick. */
    }
    if (input.camera_experiment_toggled && game_mode()==GAME_MODE_PLAY &&
        !gameplay_blocks_world() && !gameplay.dead && !scene_flow_is_interior() &&
        !view_first_person && !gohma_cinematic()) {
        player_camera_experiment_cycle();
        snap_camera_to_link();
    }
    ui_text_set_analog(input.analog);
    if (input.c_pressed == PLAYER_C_UP) c_up_pending = true;
    if (!in_gameplay || gameplay.dead) c_up_pending = false;
    if (input.map_toggled) minimap_toggle();
    /* Preserve a tap until a fixed step runs, but never carry title input
     * into gameplay or queue an airborne press for a later landing. Jump is Y
     * as of the 2026-09-18 layout; A is the interact button. */
    if (in_gameplay && input.jump) jump_pending = true;
    buttons = input.move_buttons;
    /* input.recenter is the raw L press edge and is deliberately NOT used to
     * recentre any more: gameplay.c raises GP_EVENT_RECENTER for a tap that
     * took no lock. Kept sampled so the edge is consumed each frame. */
    (void)input.recenter;
    if (input.diagnostics_toggled) recomp_diagnostics_toggled = true;
    if (input.camera_swap_toggled) oot_follow_set_legacy(!oot_follow_legacy());
    /* Walk/run is a persistent mode, so it is pushed even on a frame with no
     * movement: the next step must already run at the selected speed. */
    kokiri_camera_set_walk(input.move_mode == PLAYER_MOVE_WALK);
    /* Keep diagnostics, and latch actions until the next fixed step. */
    if (input.interact_pending) ++recomp_interact_requests;
    if (input.attack_pending) ++recomp_attack_requests;
    combat_input_feed(&combat_input, input.attack_pending, input.attack_held,
        input.attack_released, game_mode() != GAME_MODE_PLAY ||
        gameplay_blocks_world() || input.look_mode);
    interact_pending = interact_pending || input.interact_pending;
    cancel_pending = cancel_pending || input.cancel_pending ||
        (input.look_mode && input.look_exited &&
         !(item_aim && input.c_pressed == (player_c_button_t)(PLAYER_C_DOWN + item_aim - 1)));
    if (input.menu_step) menu_step = input.menu_step;
    if (input.menu_dx) menu_dx = input.menu_dx;
    if (input.menu_dy) menu_dy = input.menu_dy;
    if (input.menu_page) menu_page = input.menu_page;
    if (gameplay_is_paused() && input.c_pressed >= PLAYER_C_DOWN)
        c_assign = input.c_pressed - PLAYER_C_DOWN + 1;
    if ((!gameplay_blocks_world() || (oot_core_ocarina_state() & 2u)) && input.c_pressed >= PLAYER_C_DOWN)
        c_use = input.c_pressed - PLAYER_C_DOWN + 1;
    shield_held = input.shield_held;
    target_held = input.target_held;
    /* Pause assigns inventory slots. Live stick/slingshot actions remain
     * pending; retain the routed direction for the HUD and input tests. */
    if (input.c_pressed != PLAYER_C_NONE) recomp_last_c_button = input.c_pressed;
    if (input.c_released != PLAYER_C_NONE &&
        recomp_last_c_button == input.c_released)
        recomp_last_c_button = PLAYER_C_NONE;
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
            level_select.visible=false;
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
        combat_input_cancel(&combat_input);
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
        combat_input_cancel(&combat_input);
        cancel_pending = false;
        pause_pending = false;
        menu_step = menu_dx = menu_dy = menu_page = 0;
        c_assign = c_use = 0;
        player_input_set_dialogue(true);
        if (input_edge_consume(&skip_input.request) &&
            skip_input.request_shot == cutscene_shot_key()) {
            cutscene_skip_shot();
            interact_pending = false;
            cutscene_phase = 0;
            cutscene_tick = ticks;
            now = ticks;
        }
        cutscene_phase += (now - cutscene_tick) * CUTSCENE_TICK_HZ;
        cutscene_tick = now;
        while (cutscene_phase >= refresh && cutscene_is_playing()) {
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
            message_choose(menu_dy);menu_dy=0;
            cutscene_step(interact_pending);
            tree_mouth_step();
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
            /* An in-scene cutscene never unloaded the room it played in, so
             * re-entering the world would reload the scene and respawn Link at
             * an entrance in the middle of gameplay. Just take the pad back. */
            if (!cutscene_is_in_scene()) enter_world();
            else {
                /* The scene is still standing behind it, so only the pad and
                 * the camera come back. The owner of an in-scene cutscene
                 * closes its own state out here -- gameplay_step does not run
                 * in CUTSCENE mode, so it cannot do it from there. */
                bool bridge=cutscene_id()==CUTSCENE_SARIA_BRIDGE;
                story_route_finish();
                if(bridge) {
                    unsigned field=scene_flow_index_for_save(SAVE_SCENE_HYRULE_FIELD);
                    game_mode_set(GAME_MODE_LOADING);
                    if(!scene_flow_load(field,3))jo_core_error("Saria farewell Field load failed");
                    save_state.scene_id=SAVE_SCENE_HYRULE_FIELD;save_state.entrance=3;
                    place_at_spawn(field,3);gameplay_reset();scene_music();
                    game_mode_set(GAME_MODE_PLAY);story_route_arrive(3);
                }
                gameplay_saria_greeting_step();
                if(!cutscene_is_playing())snap_camera_to_link();
            }
            player_input_reset();
        }
    } else if (recomp_link_active) {
        /* A fast door crossing can finish during the preceding music fade.
         * Retry the current area's request until the player accepts it. */
        if (!music_busy()) scene_music();
        /* Only movement reaches the legacy viewer controller. Its shoulder
         * orbit and raise/lower/pitch controls are not gameplay controls.
         *
         * The yaw handed to kokiri_camera_update is the CAMERA's. Z targets and
         * a tap recentres, L toggles the map, R is shield, D-pad movement is camera-relative. Facing
         * is not steered by the camera -- it follows wherever he actually
         * moved, which is what keeps turning the view from spinning him. */
        uint16_t walk = buttons & (CAMERA_UP | CAMERA_DOWN | CAMERA_LEFT |
                                   CAMERA_RIGHT);
        int32_t unused_pitch = 0;
        bool recovered = false;
        int32_t roll_speed = 0;
        bool roll_pending = false, evade_a_unclaimed = false;
        bool interact_pending_step = interact_pending;
        int step_stick_dir = -1;
        while (steps--) {
            interact_pending_step = interact_pending; evade_a_unclaimed = false;
            bool land_combat = combat_input_land_allowed(link_anim_state());
            combat_buttons_t combat_buttons;
            if (!land_combat && !link_water.phase)
                combat_input_cancel(&combat_input);
            combat_buttons = combat_input_take(&combat_input);
            bool water_stroke = combat_buttons.pressed;
            /* DynaPoly_UpdateBgActorTransforms: last step's mesh placement
             * becomes "previous", so riders carry by this step's motion. */
            bg_dyna_step();
            /* Z is both the target button and the recenter tap. Targeting gets
             * the press first: recentring on the same press would swing the view
             * away from the actor just locked, or away from the one just dropped. */
            {
                gameplay_input_t action = {0};
                bool blocked_before = gameplay_blocks_world();
                bool paused_before = gameplay_is_paused();
                action.room = scene_flow_is_interior() ? 0 : (uint8_t)kokiri_scene_room();
                action.climbing = link_climb.phase == PLAYER_CLIMB_ON;
                action.x = recomp_link.x;
                action.y = recomp_link.y - RECOMP_LINK_EYE_HEIGHT;
                action.z = recomp_link.z;
                action.yaw = recomp_link_yaw;
                link_focus(action.focus);
                action.c_up = c_up_pending;
                action.attack = combat_buttons.pressed && land_combat && !link_water.phase;
                action.attack_held = combat_buttons.held && land_combat && !link_water.phase;
                /* Biggoron's Sword is two-handed: no shield guard. */
                action.shield = shield_held && land_combat && !link_water.phase &&
                                (save_state.link_age || save_state.equip_sword != EQUIP_VALUE_SWORD_BIGGORON);
                action.target_held = target_held && !link_water.phase;
                action.interact = interact_pending &&
                                  (!link_water.phase || gameplay_blocks_world());
                action.cancel = cancel_pending;
                action.pause = pause_pending;
                /* One slot per press: the menu cursor steps on the D-pad's own
                 * press edges, so holding a direction cannot run down the list. */
                action.menu_step = menu_step;
                action.menu_dx = menu_dx;
                action.menu_hold_x = input.menu_hold_x;
                action.menu_hold_y = input.menu_hold_y;
                action.menu_dy = menu_dy;
                action.menu_page = menu_page;
                action.c_assign = c_assign;
                action.c_use = land_combat && !link_water.phase ? c_use : 0;
                action.item_pitch = 0;
                action.item_from_eye = false;
                action.grounded = link_on_ground && !link_water.phase && link_velocity_y_q8 == 0;
                {
                    /* controlStickDirections: the stick's heading against
                     * Link's facing, in quadrants (+turn is his left). */
                    uint16_t heading = recomp_link_yaw;
                    int32_t speed = 0;
                    /* 3D pad analog mode moves by the stick, not D-pad bits. */
                    action.moving = (input.analog || walk) &&
                                    player_input_motion(&input, recomp_yaw, &heading, &speed) &&
                                    (!input.analog || speed > 0);
                    action.stick_dir = -1;
                    if (action.moving) {
                        int32_t turn = (int32_t)(int16_t)(uint16_t)(heading - recomp_link_yaw);
                        action.stick_dir = turn >= -0x2000 && turn <= 0x2000 ? 0 :
                                           turn > 0x2000 && turn <= 0x6000 ? 1 :
                                           turn < -0x2000 && turn >= -0x6000 ? 3 : 2;
                    }
                    step_stick_dir = action.stick_dir;
                }
                if (input.look_mode) {
                    /* Exit actions are consumed by the view, never a roll,
                     * sword swing, menu cancel or Navi call behind it. */
                    action.interact = action.cancel = action.attack = false;
                    action.attack_held = action.shield = action.target_held = false;
                    action.c_up = false;
                    action.c_use = 0;
                    bool exit_view = cancel_pending || (!item_aim && input.look_exited) || pause_pending;
                    interact_pending = cancel_pending = false;
                    if (exit_view && view_first_person) {
                        view_first_person = false;
                        item_aim = 0;
                        recomp_link_yaw += link_follow.look_yaw;
                        snap_camera_to_link();
                    }
                }
                /* Tap enters aim; release does nothing. Further slot taps fire
                 * without dropping the view. The ordinary cancel exits it. */
                if (item_aim && !view_first_person) item_aim = 0;
                fp_camera_done = false;
                if (item_aim && c_use == item_aim && !cancel_pending &&
                    !action.pause && !gameplay_blocks_world()) {
                    /* Apply this step's look BEFORE the shot, so the seed
                     * leaves along the ray the cursor shows this frame. The
                     * later camera pass skips its own update this step. */
                    first_person_camera_step(&input);
                    fp_camera_done = true;
                    action.c_use = item_aim;
                    /* look_pitch is positive UP, as is player_items_use's
                     * seed pitch (+sin = up; the quick-shot uses the same). */
                    action.item_pitch = (int16_t)link_follow.look_pitch;
                    action.yaw = (uint16_t)(recomp_link_yaw + link_follow.look_yaw);
                    action.item_from_eye = true;
                    action.item_eye[0] = recomp_camera.x;
                    action.item_eye[1] = recomp_camera.y;
                    action.item_eye[2] = recomp_camera.z;
                } else if (!item_aim && action.c_use && action.c_use <= 3 &&
                           (save_state.c_items[action.c_use - 1] == 2 ?
                                save_state.slingshot && save_state.ammo_seeds :
                                gameplay_item_aimable(save_state.c_items[action.c_use - 1])) &&
                           !gameplay_blocks_world() && action.grounded &&
                           !gameplay.attack_phase && !action.shield && !action.pause &&
                           !view_first_person && !input.look_mode && !action.target_held) {
                    item_aim = action.c_use;
                    action.c_use = 0; view_first_person = true;
                    oot_follow_look_exit(&link_follow);
                    oot_follow_look(&link_follow, 0, 0);
                }
                if (!gameplay_blocks_world() && !action.pause &&
                    (!dungeon_webs_step(save_state.scene_id,action.room) ||
                     !dungeon_puzzles_sync(save_state.scene_id,action.room)))
                    jo_core_error("Dungeon web collision pool exhausted");
                if (ledge_claims_interact(&action)) action.interact = false;
                if (save_state.scene_id == SAVE_SCENE_DEKU_TREE && kokiri_scene_room() < 12)
                    save_state.deku_visited_rooms |= (uint16_t)(1u << kokiri_scene_room());
                if (!gameplay_blocks_world() && !action.pause) {
                    unsigned door_action=dungeon_doors_step(&action);
                    if (door_action) {
                        action.interact = false;
                        /* Door ownership also consumes the later roll fallback.
                         * gameplay_step clears events, so play refusal here. */
                        interact_pending = false;
                        if (door_action==2) action_audio_events(GP_EVENT_DENIED);
                    }
                }
                gohma_notice(recomp_camera.x,recomp_camera.y,recomp_camera.z,recomp_yaw,recomp_pitch);
                field_music_motion(action.moving);
                if(story_owl_talking()) action.cancel=false;
                {
                    /* A decomp talk offer or conversation owns A/B: the C
                     * game must not open its own prompt with the same press. */
                    bool a, b;
                    unsigned int talk = oot_core_talk();
                    /* Holding a bomb: A or the C button throws it (func_8084409C). */
                    if (lift_bomb && link_lift.phase == LIFT_HOLD && (action.interact || action.c_use)) {
                        bomb_throw = true;
                        action.interact = false; action.c_use = 0; interact_pending = false;
                    }
                    a = action.interact; b = action.cancel;
                    if (talk) action.interact = false;
                    if (talk & 1u) action.cancel = false;
                    gameplay_step(&action);
                    action.interact = a; action.cancel = b;
                }
                if (step_core_gameplay(&action, paused_before)) {
                    interact_pending=cancel_pending=pause_pending=jump_pending=false;
                    c_assign=c_use=0;menu_step=menu_dx=menu_dy=menu_page=0;
                    walk=0;break;
                }
                story_route_step();
                tree_mouth_step();
                if (finish_boss_warp()) { walk=0; jump_pending=false; break; }
                if (!gameplay_blocks_world() && !action.pause && !cutscene_is_playing()) {
                    int32_t hand[3],tip[3],surface;
                    bool have_tip=player_items_stick() && gameplay_blade_points(hand,tip);
                    if(have_tip && bg_water_surface(tip[0],tip[2],action.room,&surface,0) && tip[1]<surface)
                        player_items_extinguish();
                    dungeon_torches_step(save_state.scene_id,action.room,have_tip?tip:0);
                    if(have_tip && player_items_burning())dungeon_webs_burn(tip);
                }
                /* The greeting can take ownership inside gameplay_step.
                 * Do not run movement/doors or more catch-up steps afterward. */
                if (cutscene_is_playing()) {
                    interact_pending = cancel_pending = pause_pending = false;
                    jump_pending = false;
                    break;
                }
                if (action.c_up && !blocked_before && !gameplay_blocks_world() &&
                    !gameplay.dead && !gameplay.face_locked && action.grounded && link_on_ground &&
                    (link_anim_state() == LINK_STATE_IDLE ||
                     link_anim_state() == LINK_STATE_WALK ||
                     link_anim_state() == LINK_STATE_RUN ||
                     link_anim_state() == LINK_STATE_TURN) &&
                    link_crawl.phase == PLAYER_CRAWL_NONE && !input.look_mode &&
                    !gameplay_sword_active() && !gameplay.knock_speed) {
                    if (scene_flow_is_interior()) {
                        scene_flow_toggle_view();
                        interior_camera();
                    } else {
                        view_first_person = true;
                        oot_follow_look_exit(&link_follow);
                        oot_follow_look(&link_follow, 0, 0);
                    }
                }
                if (view_first_person && (gameplay_blocks_world() || gameplay.dead || gameplay.knock_speed)) {
                    view_first_person = false;
                    snap_camera_to_link();
                }
                c_up_pending = false;
                input.c_pressed = input.c_released = PLAYER_C_NONE;
                if (view_first_person || input.look_mode) {
                    walk = 0;
                    input.move_buttons = 0;
                    input.stick_x = input.stick_y = 0;
                    jump_pending = false;
                    combat_input_cancel(&combat_input);
                }
                if (gameplay.events2 & (GP2_EVENT_LABELS | GP2_EVENT_JUMP_BINDING | GP2_EVENT_RESET_PREFS)) {
                    if (gameplay.events2 & GP2_EVENT_RESET_PREFS) ui_preferences_reset();
                    else ui_preferences_cycle((gameplay.events2 & GP2_EVENT_JUMP_BINDING) != 0);
                    save_device_write_preferences();
                    player_input_set_jump_button(ui_jump_mask());
                }
                if (gameplay.events2 & (GP2_EVENT_LOAD_MENU | GP2_EVENT_RETURN_TITLE)) {
                    bool load = (gameplay.events2 & GP2_EVENT_LOAD_MENU) != 0;
                    /* The pause confirmation is the only emitter. Never write
                     * or load a save until the player chooses a file. */
                    if (game_mode() == GAME_MODE_PLAY) game_mode_set(GAME_MODE_PAUSE);
                    if (game_mode_set(load ? GAME_MODE_FILE_SELECT : GAME_MODE_TITLE)) {
                        minimap_session_reset();
                        gameplay_reset();
                        recomp_link_active = false;
                        link_anim_react_cancel();
                        combat_input_cancel(&combat_input);
                        player_input_reset();
                        player_input_set_dialogue(load);
                        interact_pending = cancel_pending = pause_pending = jump_pending = false;
                        menu_step = menu_dx = menu_dy = menu_page = 0;
                        c_assign = c_use = 0;
                        if (load) file_select_open();
                        break; /* no catch-up world step after leaving play */
                    }
                }
                if (gameplay.events & GP_EVENT_SAVE) {
                    /* Record the outcome. A save that quietly failed is the
                     * worst result for the player, so the panel says which
                     * happened rather than assuming success. */
                    save_succeeded = active_slot<SAVE_FILE_SLOTS && save_device_write(active_slot);
                    save_reported = true;
                    if (!save_succeeded)
                        gameplay.events |= GP_EVENT_SAVE_FAILED;
                }
                if (m2e_reactions()) {
                    /* Continue respawned Link: this step's state is stale. */
                    knock_steps = 0;
                    walk = 0;
                    jump_pending = false;
                    roll_pending = false;
                    interact_pending = cancel_pending = pause_pending = false;
                    menu_step = menu_dx = menu_dy = menu_page = 0;
                    c_assign = c_use = 0;
                    player_input_set_dialogue(false);
                    break;
                }
                if(frozen_fanfare) {
                    previous_tick=now;
                    interact_pending=cancel_pending=pause_pending=jump_pending=false;
                    c_assign=c_use=0;
                    combat_input_cancel(&combat_input);player_input_reset();
                    return; /* no streaming or catch-up after CD playback starts */
                }
                /* A is the context button: talk, prompt, pickup and the menu
                 * get it first. Only a press nothing else claimed becomes a
                 * roll, so pressing A at a Kokiri never rolls away from them. */
                if (world_props_carrying() && !link_lift.phase)
                    player_lift_begin(&link_lift,false,0,false);
                if (lift_bomb && !link_lift.phase && !oot_core_tool_holding()) lift_bomb = false;
                if (oot_core_tool_holding() && !link_lift.phase && !world_props_carrying()) {
                    player_lift_begin(&link_lift,false,0,true);
                    lift_bomb = true;
                }
                roll_pending = interact_pending && !blocked_before &&
                    !gameplay_blocks_world() && !oot_core_talk() &&
                    !(gameplay.events & (GP_EVENT_TALK_OPEN | GP_EVENT_TALK_PAGE |
                                         GP_EVENT_TALK_CLOSE | GP_EVENT_PICKUP |
                                         GP_EVENT_MENU_OPEN | GP_EVENT_MENU_CLOSE |
                                         GP_EVENT_EQUIP | GP_EVENT_SAVE));
                evade_a_unclaimed = roll_pending;
                /* DO_ACTION_PUTAWAY: a swing or guard draws the sword; an
                 * unclaimed A while standing puts it back once the 20-frame
                 * putAwayCooldownTimer (30 steps) has run. Crawl, climb, swim
                 * and carrying stow it, as Player_PutAwayHeldItem does. */
                if (gameplay.attack_phase || gameplay.shielding) link_sword_out = true;
                {
                    link_state_t st = link_anim_state();
                    if (st == LINK_STATE_CRAWL || st == LINK_STATE_CLIMB || st == LINK_STATE_SWIM ||
                        st == LINK_STATE_HANG || link_lift.phase || link_water.phase)
                        link_sword_out = false;
                }
                if (link_sword_out && !action.moving && !gameplay.attack_phase) {
                    if (putaway_wait < 30) ++putaway_wait;
                } else putaway_wait = 0;
                if (roll_pending && link_sword_out && putaway_wait >= 30) {
                    link_sword_out = false;
                    roll_pending = evade_a_unclaimed = false;
                }
                action_audio_events(gameplay.events);
                if (GP_SHOP_BROWSING(gameplay.shop_state) != shop_browsing &&
                    scene_flow_entry()->save_scene == SAVE_SCENE_KOKIRI_SHOP) {
                    bool on = GP_SHOP_BROWSING(gameplay.shop_state);
                    if (scene_flow_shop_browse(on) || scene_flow_pivot() == on) {
                        shop_browsing = on;
                        interior_camera();
                    }
                }
                oot_follow_target(&link_follow, gameplay.face_locked);
                {
                    /* CAM_MODE_Z_TARGET_UNFRIENDLY (Battle1) for a hostile
                     * lock, FRIENDLY (KeepOn1) otherwise: aim at its focus. */
                    const actor_t *lock = actor_resolve(gameplay.target);
                    int32_t focus[3];
                    if (lock && gameplay.face_locked) {
                        attention_focus(lock, focus);
                        oot_follow_aim(&link_follow, focus,
                                       lock->profile->category == ACTORCAT_ENEMY ||
                                       lock->profile->category == ACTORCAT_BOSS ?
                                       OOT_CAM_LOCK_DIST_UNFRIENDLY : OOT_CAM_LOCK_DIST_FRIENDLY,
                                       !link_on_ground);
                    } else {
                        oot_follow_aim(&link_follow, (const int32_t *)0, 0, false);
                    }
                }
                interact_pending = false;
                cancel_pending = false;
                pause_pending = false;
                menu_step = menu_dx = menu_dy = menu_page = 0;
                c_assign = c_use = 0;
                /* Tell the mapper who owns B before the next sample. */
                player_input_set_dialogue(gameplay_blocks_world() || gameplay.dead);
                /* gameplay.c decides whether a Z press was a tap or a
                 * hold, because only it knows if the hold became a lock-on.
                 * A press that locked on must never also recentre, or the
                 * view swings away from the actor just acquired. */
                recenter = (gameplay.events & GP_EVENT_RECENTER) != 0;
                if (blocked_before || gameplay_blocks_world()) {
                    combat_input_cancel(&combat_input);
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
                    player_push_cancel(&link_push);
                    player_lift_cancel(&link_lift); world_props_drop_carried();
                    gameplay.knock_speed = gameplay.lunge_q16 = 0;
                    attack_carry_x_q8 = attack_carry_z_q8 = 0;
                    knock_rx = knock_rz = 0;
                }
                /* Pause freezes the world outright. A text box only stops input --
                 * gravity and the camera keep easing under it, which is what OoT
                 * does -- but the inventory stops the fixed step entirely, so a
                 * paused Link cannot fall, slide or drift while the menu is up. */
                if (gameplay_is_paused())
                    break;
                if (gameplay.events & GP_EVENT_KNOCKDOWN) {
                    knock_steps = RECOMP_KNOCKDOWN_STEPS;
                    link_anim_cancel_roll();
                    player_push_cancel(&link_push);
                    player_lift_cancel(&link_lift); world_props_drop_carried();
                }
                if (gameplay.dead) {
                    /* Dead: the Game Over flow owns the pad. */
                    walk = 0;
                    jump_pending = false;
                    roll_pending = false;
                }
                if (knock_steps) {
                    /* Knocked down: no control until he is back up. */
                    --knock_steps;
                    walk = 0;
                    jump_pending = false;
                    roll_pending = false;
                }
                link_knockback();
                attack_root_motion();
                charge_walk(&input, !gameplay_blocks_world() && !knock_steps);
                if (gameplay.swing || gameplay.shielding) {
                    walk = 0;
                    jump_pending = false;
                    roll_pending = false;
                    /* Same for combat: swinging or guarding takes movement
                     * away, so it cancels the roll rather than letting the
                     * travel run on underneath the pose. */
                    link_anim_cancel_roll();
                    player_push_cancel(&link_push);
                    player_lift_cancel(&link_lift); world_props_drop_carried();
                }
            }
            if (recenter) {
                /* Camera_Parallel1's Z-recenter turn: about 0.2 s, eased out,
                 * rather than cutting the view there in one frame. */
                oot_follow_recenter(&link_follow);
            }
            recenter = false;
            {
                bg_vec_t feet={recomp_link.x,recomp_link.y-RECOMP_LINK_EYE_HEIGHT+1,recomp_link.z};
                bg_hit_t floor;
                unsigned rider=BG_NONE;
                if (link_on_ground && bg_floor(&feet,BG_IGNORE_ENTITY,&floor)!=BG_Y_MIN)
                    rider=floor.bg_id;
                {
                    gameplay_input_t puzzle_input={0};
                    puzzle_input.x=feet.x;puzzle_input.y=feet.y-1;puzzle_input.z=feet.z;
                    puzzle_input.grounded=link_on_ground;
                    dungeon_puzzles_step(&puzzle_input);
                }
                actor_sys_update();
                feet.y--;
                if (rider<BG_DYNA_MAX && !link_push.phase &&
                    bg_dyna_carry(rider,&feet,&recomp_link_yaw)) {
                    recomp_link.x=feet.x;
                    recomp_link.y=feet.y+RECOMP_LINK_EYE_HEIGHT;
                    recomp_link.z=feet.z;
                }
            }
            {
                /* Player_Action_HookshotFly: Arms_Hook's velocity carries Link
                 * to the hook point; no gravity, walking or water this step. */
                int32_t pull[3];
                if (oot_core_tool_pull(pull)) {
                    if (view_first_person) { view_first_person = false; item_aim = 0; snap_camera_to_link(); }
                    recomp_link.x += pull[0] / 256;
                    recomp_link.y += pull[1] / 256;
                    recomp_link.z += pull[2] / 256;
                    link_velocity_y_q8 = 0;
                    link_fall_remainder_q8 = 0;
                    link_fall_peak_y = recomp_link.y;
                    link_on_ground = false;
                    jump_pending = roll_pending = false;
                    gameplay_attack_cancel();
                    if (scene_flow_is_interior()) interior_camera();
                    else player_camera_update(&link_camera, &link_follow, PLAYER_CAMERA_NORMAL, &recomp_link,
                                              recomp_link_yaw, true, &recomp_camera, &recomp_yaw, &recomp_pitch);
                    continue;
                }
            }
            /* Water owns a full fixed step: no land gravity, auto-jump, roll,
             * or falling animation can run a second time underneath it. */
            {
                link_state_t st = link_anim_state();
                /* Iron Boots: Link sinks and walks the bottom instead of swimming. */
                bool iron = !save_state.link_age && save_state.boots == SAVE_BOOTS_IRON;
                bool was_water = link_water.phase != PLAYER_WATER_DRY;
                if (iron && was_water) { player_water_reset(&link_water); was_water = false; }
                bool eligible = !iron && (was_water || st == LINK_STATE_IDLE ||
                    st == LINK_STATE_WALK || st == LINK_STATE_RUN ||
                    st == LINK_STATE_FALL || st == LINK_STATE_JUMP ||
                    st == LINK_STATE_LANDING || st == LINK_STATE_JUMP_LANDING ||
                    st == LINK_STATE_ROLL || st == LINK_STATE_BONK ||
                    st == LINK_STATE_TURN || st == LINK_STATE_SLIDE ||
                    st == LINK_STATE_SLIDE_END);
                if (eligible) {
                    player_water_input_t wi = {0};
                    bg_vec_t feet = {recomp_link.x, recomp_link.y-RECOMP_LINK_EYE_HEIGHT, recomp_link.z};
                    int32_t old_x = feet.x, old_z = feet.z;
                    wi.yaw = recomp_link_yaw;
                    if (!player_input_motion(&input, recomp_yaw, &wi.yaw, &wi.speed_q8))
                        wi.speed_q8 = 0;
                    wi.room = kokiri_scene_room();
                    wi.dive_pressed = roll_pending;
                    wi.dive_held = input.interact_held;
                    wi.stroke_pressed = water_stroke;
                    wi.blocked = gameplay_blocks_world();
                    /* Child has no scale upgrade in the current inventory. */
                    wi.scale = 0;
                    if (player_water_step(&link_water, &wi, &feet, &recomp_link_yaw,
                                          link_velocity_y_q8, link_on_ground)) {
                        recomp_link.x = feet.x;
                        recomp_link.y = feet.y + RECOMP_LINK_EYE_HEIGHT;
                        recomp_link.z = feet.z;
                        link_velocity_y_q8 = link_water.velocity_q8;
                        link_fall_remainder_q8 = 0;
                        link_air_speed_q8 = 0; link_air_evade = false;
                        link_on_ground = link_water.grounded;
                        link_fall_peak_y = recomp_link.y;
                        link_slope = (player_slope_t){0};
                        jump_pending = roll_pending = false;
                        link_enter_prompt = false;
                        player_bg_reset(&link_bg);
                        gameplay_attack_cancel();
                        gameplay.shielding = false;
                        link_anim_combat(false, 0, 0, false);
                        { int32_t focus[3]; link_focus(focus); navi_step(focus[0], focus[1], focus[2]); }
                        if (navi_dash_started()) action_audio_navi_dash();
                        action_audio_navi_flight(0, false);
                        if (scene_flow_is_interior()) interior_camera();
                        else player_camera_update(&link_camera, &link_follow,
                                PLAYER_CAMERA_NORMAL, &recomp_link, recomp_link_yaw,
                                feet.x != old_x || feet.z != old_z,
                                &recomp_camera, &recomp_yaw, &recomp_pitch);
                        if (take_door()) break;
                        continue;
                    }
                    if (was_water) {
                        link_velocity_y_q8 = 0;
                        link_fall_remainder_q8 = 0;
                        link_fall_peak_y = recomp_link.y;
                    }
                }
            }
            {
                bool grounded;
                int32_t step_x = recomp_link.x, step_z = recomp_link.z;
                int32_t intent_speed = 0;
                uint16_t intent_heading = recomp_link_yaw;
                int32_t dx, dz, moved, fell;
                /* Player_Action_80845668 owns Link while he climbs: no walk,
                 * jump or roll input reaches him (the last frames of a step
                 * up still yield to movement, in link_anim_update). */
                bool climbing = link_anim_state() == LINK_STATE_STEP_UP ||
                                link_anim_state() == LINK_STATE_JUMP_START ||
                                link_anim_state() == LINK_STATE_HANG ||
                                link_anim_state() == LINK_STATE_PULL_UP ||
                                link_anim_state() == LINK_STATE_CLIMB ||
                                link_anim_state() == LINK_STATE_CRAWL ||
                                (link_anim_state() == LINK_STATE_PUSH && link_lift.phase != LIFT_HOLD);
                bool ledge_started = false;
                bool bonking = link_anim_state() == LINK_STATE_BONK;
                bool sloping = false;
                uint16_t step_walk = climbing ? 0 : walk;
                bg_hit_t wall_hit;
                bool wall, stepped;
                /* An A press nothing else claimed: a climbing Link lets go. */
                bool interact_seen = roll_pending;
                kokiri_collision_actor_begin_step();
                if (climbing || bonking) {
                    jump_pending = false;
                    roll_pending = false;
                }
                /* Player_Action_8084BBE4, once the grab frame has passed: a
                 * pushed stick pulls up, else A held lets go. */
                if (link_anim_hang_ready() && !gameplay_blocks_world()) {
                    if (player_input_stick_pushed(&input)) {
                        link_anim_pull_up();
                    } else if (input.interact_held) {
                        int32_t lx, ly, lz, floor;
                        uint16_t away = link_hang_walk_off ? recomp_link_yaw
                                        : (uint16_t)(recomp_link_yaw + 0x8000);
                        /* func_80837B60: the actor goes to the hanging pelvis. */
                        link_anim_let_go(&lx, &ly, &lz);
                        link_local_move(lx, lz, recomp_link_yaw);
                        recomp_link.y += ly / 256;
                        if (kokiri_collision_floor(recomp_link.x, recomp_link.z,
                                                   recomp_link.y - RECOMP_LINK_EYE_HEIGHT + 49,
                                                   &floor) &&
                            recomp_link.y - RECOMP_LINK_EYE_HEIGHT < floor)
                            recomp_link.y = floor + RECOMP_LINK_EYE_HEIGHT;
                        link_velocity_y_q8 = 0;
                        link_fall_remainder_q8 = 0;
                        /* speedXZ +-0.8: away from the wall either way. */
                        link_air_speed_q8 = 205;
                        link_air_yaw = away;
                        /* Already airborne: not a departure from the ledge. */
                        link_on_ground = false;
                    }
                }
                if (jump_pending) {
                    if (kokiri_collision_jump(&recomp_link, &link_velocity_y_q8,
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
                    uint16_t heading = recomp_link_yaw;
                    int32_t speed = 0;
                    bool moving = player_input_motion(&input, recomp_yaw,
                                                      &heading, &speed);
                    bool forward = moving && step_walk;
                    /* speedXZ and this->yaw for a departure this step. */
                    intent_speed = forward ? speed : 0;
                    intent_heading = heading;
                    link_anim_turn(input.analog && moving && speed == 0 &&
                        step_walk && link_on_ground && link_velocity_y_q8 == 0 &&
                        !gameplay_blocks_world() && !gameplay.swing &&
                        !gameplay.shielding && !target_held && !gameplay.face_locked,
                        heading, &recomp_link_yaw);
                    if (input.analog && speed == 0) step_walk = 0;
                    if (forward) {
                        int32_t turn = (int32_t)(int16_t)
                            (uint16_t)(heading - recomp_link_yaw);
                        if (turn < 0) turn = -turn;
                        /* Source quadrant: within 45 degrees of his facing. */
                        forward = turn <= 8192;
                    }
                    /* A released digital pad still reports its base speed;
                     * only a held direction is input (BUG-011). */
                    link_anim_roll_input(moving ? speed : 0, forward);
                }
                roll_speed = link_anim_roll_speed_q8();
                if (!gameplay_blocks_world() &&
                    link_anim_bonk(link_bg.interact, link_bg.world_yaw_to_wall)) {
                    bonking = true;
                    roll_speed = 0;
                    action_audio_events(GP_EVENT_CLIMB_END);
                }
                if (bonking) {
                    step_walk = 0;
                    intent_speed = 0;
                    roll_pending = false;
                }
                {
                    link_state_t st=link_anim_state();
                    bool eligible=link_on_ground && !link_velocity_y_q8 &&
                        !gameplay_blocks_world() && !gameplay.swing && !gameplay.shielding &&
                        (st==LINK_STATE_IDLE || st==LINK_STATE_WALK || st==LINK_STATE_RUN ||
                         st==LINK_STATE_TURN || st==LINK_STATE_SLIDE);
                    if (eligible) {
                        bg_vec_t feet={recomp_link.x,recomp_link.y-RECOMP_LINK_EYE_HEIGHT+1,recomp_link.z};
                        bg_hit_t floor;
                        bool was_sliding=link_slope.active;
                        bool hit=bg_floor(&feet,BG_IGNORE_ENTITY,&floor)!=BG_Y_MIN;
                        player_slope_update(&link_slope,hit?&floor:0,intent_heading,
                                            intent_speed,&recomp_link_yaw);
                        if (link_slope.active) link_anim_slide(link_slope.face_up);
                        else if (was_sliding && hit) link_anim_slide_end(link_slope.face_up);
                    } else {
                        link_slope=(player_slope_t){0};
                        if (gameplay_blocks_world() || gameplay.swing || gameplay.shielding ||
                            link_velocity_y_q8) link_anim_slide_cancel();
                    }
                    sloping=link_anim_state()==LINK_STATE_SLIDE ||
                            link_anim_state()==LINK_STATE_SLIDE_END;
                    if (sloping) { step_walk=0; roll_pending=false; intent_speed=0; }
                }
                if (roll_speed > 0) {
                    intent_speed = roll_speed;
                    intent_heading = recomp_link_yaw;
                }
                /* Player_ActionHandler_12, in the walk/run action lists: the
                 * probe from the end of the last step, before this step's
                 * move. An A press nothing else claimed counts, ahead of the
                 * roll (list order). */
                if (!climbing && roll_speed <= 0 && intent_speed > 0 &&
                    link_on_ground && link_velocity_y_q8 == 0 &&
                    (link_anim_state() == LINK_STATE_IDLE ||
                     link_anim_state() == LINK_STATE_WALK ||
                     link_anim_state() == LINK_STATE_RUN)) {
                    int32_t hop = 0;
                    player_ledge_act_t act = player_ledge_action(&link_bg, true,
                                                                 roll_pending, &hop);
                    if (act == PLAYER_LEDGE_ACT_STEP100 || act == PLAYER_LEDGE_ACT_STEP150) {
                        bg_vec_t feet = { recomp_link.x, recomp_link.y - RECOMP_LINK_EYE_HEIGHT,
                                          recomp_link.z };
                        player_ledge_step_target(&link_bg, &feet, &recomp_link_yaw);
                        recomp_link.x = feet.x;
                        recomp_link.y = feet.y + RECOMP_LINK_EYE_HEIGHT;
                        recomp_link.z = feet.z;
                        link_velocity_y_q8 = 0;
                        link_fall_remainder_q8 = 0;
                        link_fall_peak_y = recomp_link.y;
                        link_anim_step_up(act == PLAYER_LEDGE_ACT_STEP150,
                                          link_bg.y_dist_to_ledge);
                        ledge_started = true;
                    } else if (act == PLAYER_LEDGE_ACT_JUMP250) {
                        recomp_link_yaw = (uint16_t)(link_bg.wall_yaw + 0x8000);
                        link_air_speed_q8 = 256;
                        link_air_yaw = recomp_link_yaw;
                        link_jump250_dist = link_bg.y_dist_to_ledge;
                        link_anim_jump_start();
                        ledge_started = true;
                    } else if (act == PLAYER_LEDGE_ACT_HOP) {
                        /* func_808389E8: jump clip, SWORD_N voice. Air X/Z stay
                         * input-driven, as for the automatic jump. */
                        link_velocity_y_q8 = hop;
                        link_fall_remainder_q8 = 0;
                        link_air_speed_q8 = 640;      /* speedXZ 2.5 */
                        link_air_yaw = recomp_link_yaw;
                        link_anim_hop();
                        action_audio_events(GP_EVENT_HOP_VOICE);
                    }
                    /* Player_ActionHandler_5, after 12 in the list: a ladder or
                     * vine wall (func_8083EC18). */
                    if (act == PLAYER_LEDGE_ACT_NONE && link_bg.interact &&
                        link_bg.shape_yaw_to_wall < 0x3000) {
                        bg_vec_t feet = { recomp_link.x, recomp_link.y - RECOMP_LINK_EYE_HEIGHT,
                                          recomp_link.z };
                        if (player_climb_start(&link_climb, &link_bg, &feet,
                                               &recomp_link_yaw, true)) {
                            recomp_link.x = feet.x;
                            recomp_link.y = feet.y + RECOMP_LINK_EYE_HEIGHT;
                            recomp_link.z = feet.z;
                            link_velocity_y_q8 = 0;
                            link_fall_remainder_q8 = 0;
                            ledge_started = true;
                        }
                    }
                    if (act != PLAYER_LEDGE_ACT_NONE)
                        roll_pending = false;
                }
                /* Player_ActionHandler_5 -> Player_TryEnteringCrawlspace: in
                 * the idle list too, so no speed is needed, only A. */
                if (!climbing && !ledge_started && roll_pending && roll_speed <= 0 &&
                    link_on_ground && link_velocity_y_q8 == 0 &&
                    link_bg.interact && link_bg.shape_yaw_to_wall < 0x3000 &&
                    (link_anim_state() == LINK_STATE_IDLE ||
                     link_anim_state() == LINK_STATE_WALK ||
                     link_anim_state() == LINK_STATE_RUN)) {
                    bg_vec_t feet = { recomp_link.x, recomp_link.y - RECOMP_LINK_EYE_HEIGHT,
                                      recomp_link.z };
                    if (player_crawl_enter(&link_crawl, &link_bg, true, &feet,
                                           &recomp_link_yaw)) {
                        recomp_link.x = feet.x;
                        recomp_link.z = feet.z;
                        roll_pending = false;
                        ledge_started = true;
                    }
                }
                if (!climbing && !ledge_started && !bonking && link_on_ground &&
                    link_velocity_y_q8==0 && !gameplay_blocks_world() &&
                    !gameplay.swing && !gameplay.shielding &&
                    (link_anim_state()==LINK_STATE_IDLE || link_anim_state()==LINK_STATE_WALK ||
                     link_anim_state()==LINK_STATE_RUN)) {
                    if (player_push_start(&link_push,&link_bg,input.interact_held,&recomp_link_yaw)) {
                        ledge_started=true;
                        roll_pending=false;
                    }
                }
                if (!climbing && !ledge_started && !bonking && roll_pending &&
                    link_on_ground && !link_velocity_y_q8 && !gameplay_blocks_world() &&
                    !gameplay.swing && !gameplay.shielding &&
                    (link_anim_state()==LINK_STATE_IDLE || link_anim_state()==LINK_STATE_WALK ||
                     link_anim_state()==LINK_STATE_RUN)) {
                    int bush=lift_bush_candidate();
                    if (bush>=0) {
                        const kokiri_prop_t *g=&kokiri_grass[bush];
                        int32_t sn,cs;
                        recomp_link_yaw=kokiri_camera_facing(g->x-recomp_link.x,g->z-recomp_link.z);
                        kokiri_camera_sincos(recomp_link_yaw,&sn,&cs);
                        recomp_link.x=g->x-20*sn/65536;
                        recomp_link.z=g->z-20*cs/65536;
                        player_lift_begin(&link_lift,true,0,false);
                        roll_pending=false; ledge_started=true;
                    }
                }
                /* Diagnostic latch (debug readout only): which evade gate
                 * refused the last Z+A press. Does not change behaviour. */
                if (interact_pending_step && (target_held || gameplay.face_locked)) {
                    recomp_evade_gates =
                        (!evade_a_unclaimed ? 1u : 0) |
                        (evade_a_unclaimed && !roll_pending ? 2u : 0) |
                        (climbing || ledge_started || bonking ? 4u : 0) |
                        (!link_on_ground || link_velocity_y_q8 ? 8u : 0) |
                        (gameplay_blocks_world() ? 16u : 0) |
                        (gameplay.swing ? 32u : 0) | (gameplay.shielding ? 64u : 0) |
                        (scene_room_indoors(save_state.scene_id) ? 128u : 0) |
                        (!evade_floor_ok() ? 256u : 0) |
                        (link_anim_state()!=LINK_STATE_IDLE && link_anim_state()!=LINK_STATE_WALK &&
                         link_anim_state()!=LINK_STATE_RUN ? 512u : 0);
                    recomp_evade_pose = (unsigned)link_anim_state();
                }
                /* Player_ActionHandler_10: Z-targeted unclaimed A outdoors.
                 * None/forward: jump slash with a sword, else the roll below.
                 * Side: sidehop; back: backflip (func_8083BCD0). */
                if (!climbing && !ledge_started && !bonking && roll_pending &&
                    link_on_ground && !link_velocity_y_q8 && !gameplay_blocks_world() &&
                    !gameplay.swing && !gameplay.shielding &&
                    (target_held || gameplay.face_locked) &&
                    !scene_room_indoors(save_state.scene_id) && evade_floor_ok() &&
                    (link_anim_state()==LINK_STATE_IDLE || link_anim_state()==LINK_STATE_WALK ||
                     link_anim_state()==LINK_STATE_RUN)) {
                    static const uint16_t evade_clip[4][2] = {
                        { 0, 0 },
                        { LINK_CLIP_HOP_LEFT, LINK_CLIP_HOP_LEFT_END },
                        { LINK_CLIP_BACKFLIP, LINK_CLIP_BACKFLIP_END },
                        { LINK_CLIP_HOP_RIGHT, LINK_CLIP_HOP_RIGHT_END },
                    };
                    int dir = step_stick_dir;
                    bool launched = false;
                    if (dir <= 0) {
                        if (gameplay_jump_attack_start()) {
                            link_velocity_y_q8 = GP_JUMP_SLASH_VY_Q8;
                            link_air_speed_q8 = GP_JUMP_SLASH_SPEED_Q8;
                            link_air_yaw = recomp_link_yaw;
                            link_anim_hop();
                            launched = true;
                        } else {
                            /* No usable melee weapon: Player_SetupRoll, even
                             * standing still (the plain roll needs motion). */
                            link_anim_roll_start();
                            roll_pending = false;
                        }
                    } else {
                        link_velocity_y_q8 = (dir & 1) ? GP_SIDEHOP_VY_Q8 : GP_BACKFLIP_VY_Q8;
                        link_air_speed_q8 = (dir & 1) ? GP_SIDEHOP_SPEED_Q8 : GP_BACKFLIP_SPEED_Q8;
                        link_air_yaw = (uint16_t)(recomp_link_yaw + (dir << 14));
                        link_anim_evade(evade_clip[dir][0], evade_clip[dir][1]);
                        launched = true;
                    }
                    if (launched) {
                        link_air_evade = link_air_evade_launch = true;
                        link_fall_remainder_q8 = 0;
                        roll_pending = false;
                        step_walk = 0;
                        intent_speed = 0;
                        action_audio_events(GP_EVENT_JUMP);
                    }
                }
                if (link_lift.phase && !gameplay_blocks_world()) {
                    int32_t hand[3],tip[3];
                    lift_last_speed_q8 = intent_speed;
                    player_lift_update(&link_lift,lift_bomb ? bomb_throw : world_props_lift_action(),intent_speed);
                    bomb_throw = false;
                    if (lift_bomb && (link_lift.events & LIFT_RELEASE)) { oot_core_tool_throw(); lift_bomb = false; }
                    else if (lift_bomb && !oot_core_tool_holding() && link_lift.phase != LIFT_THROW) {
                        player_lift_cancel(&link_lift); lift_bomb = false;   /* exploded in his hands */
                    }
                    bool have_hand=gameplay_blade_points(hand,tip);
                    world_props_lift_sync(link_lift.events,link_lift.release_speed_q8,
                                         link_lift.release_y_q8,recomp_link_yaw,have_hand ? hand : 0);
                }
                if (ledge_started || climbing) {
                    step_walk = 0;
                    roll_speed = 0;
                    intent_speed = 0;
                    if (climbing && link_push.phase) {
                        bg_vec_t feet={recomp_link.x,recomp_link.y-RECOMP_LINK_EYE_HEIGHT,recomp_link.z};
                        uint16_t heading=recomp_link_yaw;
                        int32_t speed=0;
                        if (!player_input_motion(&input,recomp_yaw,&heading,&speed)) speed=0;
                        player_push_update(&link_push,input.interact_held,speed,heading,
                                           &feet,recomp_link_yaw);
                        recomp_link.x=feet.x; recomp_link.z=feet.z;
                    }
                    /* The 250 jump start walks into the wall at speedXZ 1.0. */
                    if (link_anim_state() == LINK_STATE_JUMP_START)
                        kokiri_camera_move_heading(&recomp_link, recomp_link_yaw, 256);
                    /* Player_Action_8084C760 / 8084C81C: the crawlspace. */
                    if (climbing && link_crawl.phase != PLAYER_CRAWL_NONE) {
                        bg_vec_t feet = { recomp_link.x, recomp_link.y - RECOMP_LINK_EYE_HEIGHT,
                                          recomp_link.z };
                        int32_t stick_y = input.analog ? input.stick_y * 80 / 127 :
                            (input.move_buttons & CAMERA_UP ? 80 : 0) -
                            (input.move_buttons & CAMERA_DOWN ? 80 : 0);
                        player_crawl_update(&link_crawl, stick_y, link_last_wall,
                                            &link_last_wall_hit, &feet, &recomp_link_yaw);
                        recomp_link.x = feet.x;
                        recomp_link.z = feet.z;
                        if (link_crawl.phase == PLAYER_CRAWL_IN && link_crawl.speed_q8)
                            kokiri_camera_move_heading(&recomp_link,
                                link_crawl.speed_q8 > 0 ? recomp_link_yaw
                                                        : (uint16_t)(recomp_link_yaw + 0x8000),
                                link_crawl.speed_q8 > 0 ? link_crawl.speed_q8
                                                        : -link_crawl.speed_q8);
                        if (link_crawl.phase == PLAYER_CRAWL_DONE)
                            link_crawl.phase = PLAYER_CRAWL_NONE;
                    }
                    /* Player_Action_8084BF1C / 8084C5F8, from the step after
                     * the start (the action runs on the next update). */
                    if (climbing && link_anim_state() == LINK_STATE_CLIMB &&
                        (link_climb.phase == PLAYER_CLIMB_ON ||
                         link_climb.phase == PLAYER_CLIMB_ENDING)) {
                        player_climb_input_t cin;
                        bg_vec_t feet = { recomp_link.x, recomp_link.y - RECOMP_LINK_EYE_HEIGHT,
                                          recomp_link.z };
                        /* rel.stick, raw N64 scale: a digital direction is
                         * a full push (80). Not camera-relative. */
                        if (input.analog) {
                            cin.stick_x = input.stick_x * 80 / 127;
                            cin.stick_y = input.stick_y * 80 / 127;
                        } else {
                            cin.stick_x = (input.move_buttons & CAMERA_RIGHT ? 80 : 0) -
                                          (input.move_buttons & CAMERA_LEFT ? 80 : 0);
                            cin.stick_y = (input.move_buttons & CAMERA_UP ? 80 : 0) -
                                          (input.move_buttons & CAMERA_DOWN ? 80 : 0);
                        }
                        cin.a_pressed = interact_seen;
                        cin.stick_pushed = player_input_stick_pushed(&input);
                        player_climb_update(&link_climb, &cin, &feet, &recomp_link_yaw);
                        recomp_link.x = feet.x;
                        recomp_link.y = feet.y + RECOMP_LINK_EYE_HEIGHT;
                        recomp_link.z = feet.z;
                        if (link_climb.events)
                            action_audio_events(link_climb.events);
                        if (link_climb.phase == PLAYER_CLIMB_DONE)
                            link_climb.phase = PLAYER_CLIMB_NONE;
                        else if (link_climb.phase == PLAYER_CLIMB_VINE_TOP) {
                            /* func_8083A5C4(wall, unk_3C, ...), facing the
                             * wall, then func_8083A9B8(jump_climb_up_free). */
                            uint16_t facing;
                            link_anim_move_end();
                            player_hang_place(&link_climb.wall, 12, &feet, &facing, true);
                            recomp_link.x = feet.x;
                            recomp_link.z = feet.z;
                            recomp_link_yaw = facing;
                            link_anim_pull_up_clip(LINK_CLIP_CLIMB_UP_FREE);
                            link_climb.phase = PLAYER_CLIMB_NONE;
                        } else if (link_climb.phase == PLAYER_CLIMB_LET_GO) {
                            /* func_8083FB7C: fall, speedXZ -0.4. */
                            link_anim_move_end();
                            link_anim_fall();
                            link_air_speed_q8 = 102;
                            link_air_yaw = (uint16_t)(recomp_link_yaw + 0x8000);
                            link_on_ground = false;
                            link_climb.phase = PLAYER_CLIMB_NONE;
                        }
                    }
                }
                else if (sloping) {
                    if (link_slope.active)
                        kokiri_camera_move_heading(&recomp_link,link_slope.yaw,link_slope.speed_q8);
                }
                else if (bonking) {
                    int32_t recoil = link_anim_bonk_speed_q8();
                    if (recoil < 0)
                        kokiri_camera_move_heading(&recomp_link,
                            (uint16_t)(recomp_link_yaw + 0x8000), -recoil);
                }
                else if (link_air_speed_q8 > 0 && !link_on_ground &&
                         (intent_speed == 0 || link_air_evade) && roll_speed <= 0) {
                    kokiri_camera_move_heading(&recomp_link, link_air_yaw,
                                               link_air_speed_q8);
                    link_air_speed_q8 -= 17;
                    if (link_air_speed_q8 < 0) link_air_speed_q8 = 0;
                }
                else if (roll_speed > 0)
                    kokiri_camera_move_heading(&recomp_link, recomp_link_yaw,
                                               roll_speed);
                else if (input.analog)
                {
                    uint16_t heading;
                    int32_t speed;
                    if (step_walk && player_input_motion(&input, recomp_yaw, &heading, &speed))
                        kokiri_camera_move_heading(&recomp_link, heading, speed);
                }
                else
                    kokiri_camera_update(&recomp_link, &recomp_yaw, &unused_pitch,
                                         step_walk, false, true);
                if (!climbing && !bonking && !sloping && link_slope.push_q8)
                    kokiri_camera_move_heading(&recomp_link,link_slope.push_yaw,link_slope.push_q8);
                if (link_slope.active && link_on_ground && !link_velocity_y_q8) {
                    bg_vec_t feet={recomp_link.x,recomp_link.y-RECOMP_LINK_EYE_HEIGHT,recomp_link.z};
                    if (player_slope_ground(&feet)) recomp_link.y=feet.y+RECOMP_LINK_EYE_HEIGHT;
                }
                if (!sloping && link_on_ground && link_velocity_y_q8 == 0 && !link_standing())
                    link_leave_ground(step_x, step_z, intent_speed, intent_heading);
                /* ANIM_FLAG_OVERRIDE_MOVEMENT: no gravity while the climb's
                 * root motion owns him; fallStartHeight follows him. */
                if (link_anim_state() == LINK_STATE_CLIMB) {
                    link_velocity_y_q8 = 0;
                    link_fall_remainder_q8 = 0;
                    grounded = true;
                } else {
                    /* Player_Action_80844AF4: jump slash gravity -1.2, not -1.0. The
                     * fall adds -171 (x2/3 of -1.0); the extra -0.2 is -34. */
                    if (gameplay.attack_phase == 6)
                        link_velocity_y_q8 -= 34;
                    /* Hover Boots: hoverBootsTimer 19 source frames (28 steps)
                     * of level flight after leaving the ground. */
                    if (save_state.link_age || save_state.boots != SAVE_BOOTS_HOVER || link_on_ground)
                        link_hover_steps = 28;
                    else if (link_hover_steps) {
                        --link_hover_steps;
                        if (link_velocity_y_q8 < 0) link_velocity_y_q8 = 0;
                    }
                    grounded = kokiri_collision_fall(&recomp_link, &link_velocity_y_q8,
                                                      &link_fall_remainder_q8);
                }
                if (!grounded && link_push.phase) player_push_cancel(&link_push);
                if (!grounded && link_lift.phase) { player_lift_cancel(&link_lift); world_props_drop_carried(); }
                /* Actual travel length, not the largest axis: diagonal running
                 * must select the same clip and cadence as straight running. */
                dx = recomp_link.x - step_x;
                if (dx < 0) dx = -dx;
                dz = recomp_link.z - step_z;
                if (dz < 0) dz = -dz;
                moved = 0;
                while ((moved + 1) * (moved + 1) <= dx * dx + dz * dz)
                    ++moved;

                if (grounded) {
                    /* The peak still holds the height he left the ground from, so
                     * this is the whole drop. It is only meaningful on the step he
                     * lands; link_anim_update() ignores it otherwise. */
                    fell = link_fall_peak_y - recomp_link.y;
                    if (dungeon_webs_land(recomp_link.x,recomp_link.y-RECOMP_LINK_EYE_HEIGHT,recomp_link.z,fell))
                        fell=0; /* source web catches the impact before breaking */
                    if (fell < 0) fell = 0;
                    link_safe_position = recomp_link;
                    link_safe_position_valid = true;
                } else {
                    fell = 0;
                    if (recover_link_from_void()) {
                        recovered = true;
                        gameplay_void_out();
                        gameplay_void_respawned();
                    }
                }
                link_anim_set_air(link_velocity_y_q8 < 0 &&
                                  recomp_link.y < link_fall_peak_y);
                /* En_Elf updates with the world, so she is stepped here and
                 * not per draw: her approach rates are per update. */
                {
                    /* Navi hovers attention's naviHoverPos (the lock, else
                     * the arrow actor, else Link), set by gameplay_step. */
                    int32_t focus[3], hover[3];
                    attention_colour_t colour = attention_navi_colour();
                    link_focus(focus);
                    attention_navi_hover(hover);
                    navi_step_hover(hover, focus, attention_navi_has_actor(),
                                    attention_navi_moving(),
                                    (unsigned int)colour);
                }
                if (navi_dash_started()) action_audio_navi_dash();
                /* NAVY_FLY belongs only to Object_Kankyo's opening layer 7.
                 * En_Elf gameplay uses occasional dash cues, no flying loop. */
                action_audio_navi_flight(0, false);
                /* Player_Action_80844AF4: touching down ends the jump slash
                 * with its finishing cut. */
                if (grounded && gameplay.attack_phase == 6)
                    gameplay_jump_attack_land();
                link_anim_update(moved, grounded, fell, roll_pending);
                roll_pending = false;
                {
                    /* Player_Action_Roll: invulnerable from anim frame 8. */
                    static bool roll_guarded;
                    if (link_anim_state() != LINK_STATE_ROLL) roll_guarded = false;
                    else if (!roll_guarded && link_anim_frame() >= GP_ROLL_INVULN_FRAME) {
                        gameplay_set_invulnerable(GP_ROLL_INVULN_STEPS);
                        roll_guarded = true;
                    }
                }
                /* func_80843E64: the landing's fall damage (not on a roll). */
                if (grounded && fell > 0)
                    gameplay_land(fell, link_anim_roll_speed_q8() > 0);
                {
                    int32_t lx, lz;
                    uint16_t turn;
                    /* Player_Action_8084BDFC's end: the clip's root x/z moves
                     * the actor, then its root yaw turns him. */
                    if (link_anim_pull_up_done(&lx, &lz, &turn)) {
                        link_local_move(lx, lz, recomp_link_yaw);
                        recomp_link_yaw = (uint16_t)(recomp_link_yaw + turn);
                    }
                }
                bool launched = link_anim_jump250_launch();
                if (launched) {
                    /* Frame 8 of the 250 jump start: func_80838940 with
                     * NA_SE_VO_LI_AUTO_JUMP. No mid-air ledge grab yet (M1d):
                     * he comes back down. */
                    link_velocity_y_q8 = player_ledge_jump250_velocity_q8(link_jump250_dist);
                    link_fall_remainder_q8 = 0;
                    /* speedXZ 1.0 carries into the jump (BUG-012: the
                     * grounded start steps cleared it). */
                    link_air_speed_q8 = 256;
                    link_air_yaw = recomp_link_yaw;
                    action_audio_events(GP_EVENT_JUMP);
                }
                if (!gameplay_blocks_world() && !gameplay.swing && !gameplay.shielding)
                    action_audio_events(link_anim_motion_events());
                {
                    unsigned int clip = 0, frame = 0;
                    bool attacking = !gameplay_is_talking() &&
                                     gameplay_attack_pose(&clip, &frame);
                    if (attacking && gameplay.attack_phase == 4 && charge_walk_q8) {
                        clip = charge_walk_side ? LINK_CLIP_CHARGE_SIDE : LINK_CLIP_CHARGE_WALK;
                        frame = (charge_walk_thirds / 3u) %
                                (charge_walk_side ? LINK_FRAMES_CHARGE_SIDE : LINK_FRAMES_CHARGE_WALK);
                    }
                    link_anim_combat(attacking, clip, frame, gameplay.shielding);
                }
                /* Follow him while he is on the ground, so the next departure
                 * measures from where he actually left. Left alone while airborne,
                 * which is what makes the landing drop the full fall. */
                if (grounded) {
                    bg_vec_t feet;
                    bg_hit_t floor_hit;
                    link_fall_peak_y = recomp_link.y;
                    feet.x = recomp_link.x;
                    feet.y = recomp_link.y - RECOMP_LINK_EYE_HEIGHT + 1;
                    feet.z = recomp_link.z;
                    link_floor_property = bg_floor(&feet, BG_IGNORE_ENTITY,
                                                   &floor_hit) != BG_Y_MIN
                        ? (uint8_t)bg_floor_property(&floor_hit) : 0;
                }
                link_on_ground = grounded;

                /* The camera advances per FIXED STEP, not per draw.
                 *
                 * Driving it from the draw callback made every easing rate depend
                 * on the frame rate: a 6-step turn takes 0.2 s at 30 Hz but 0.75 s
                 * at 8 FPS, and OoT's rates are defined per update. Facing is
                 * recomputed here so the camera follows the step it just took. */
                if (sloping) {
                    /* Slope action owns facing, including its uphill pose. */
                } else if (gameplay.face_locked) {
                    /* Recompute after movement: both Link and camera track the
                     * target from this step's position, not the previous one. */
                    gameplay_update_facing(recomp_link.x, recomp_link.z);
                    recomp_link_yaw = gameplay.face_yaw;
                }
                else if (target_held) {
                    /* Z held with nothing locked: Link holds his heading and
                     * the D-pad strafes and backs up around it, which is the
                     * source behaviour with no target in range. */
                }
                else if (step_walk && roll_speed <= 0 &&
                         (recomp_link.x != step_x || recomp_link.z != step_z)) {
                    int32_t unused_speed;
                    /* Whole-unit collision positions form a staircase at low
                     * speed. Facing that rounded delta makes Link alternate
                     * headings and feeds the error back into camera-relative
                     * movement. Face the requested direction instead. Actual
                     * travel still drives animation and the moving-camera flag.
                     * Rolls retain their heading; lock/strafe take priority. */
                    player_input_motion(&input, recomp_yaw, &recomp_link_yaw,
                                        &unused_speed);
                }
                /* Player_ProcessSceneCollision's wall block, on this step's
                 * wall contact and final facing. A step whose integer travel
                 * came to nothing keeps the last probe rather than dropping
                 * the contact the source would still report. */
                kokiri_collision_actor_probe_still(&recomp_link);
                wall = kokiri_collision_actor_wall(&stepped, &wall_hit);
                link_last_wall = wall;
                if (wall)
                    link_last_wall_hit = wall_hit;
                /* Handler 5's crawlspace test, short of the press. */
                {
                    bg_vec_t feet = { recomp_link.x, recomp_link.y - RECOMP_LINK_EYE_HEIGHT,
                                      recomp_link.z };
                    link_enter_prompt = grounded && !gameplay_blocks_world() &&
                        link_crawl.phase == PLAYER_CRAWL_NONE &&
                        (link_anim_state() == LINK_STATE_IDLE ||
                         link_anim_state() == LINK_STATE_WALK ||
                         link_anim_state() == LINK_STATE_RUN) &&
                        link_bg.interact && link_bg.shape_yaw_to_wall < 0x3000 &&
                        player_crawl_prompt(&link_bg, &feet);
                }
                if (stepped || intent_speed == 0) {
                    bg_vec_t feet = { recomp_link.x, recomp_link.y - RECOMP_LINK_EYE_HEIGHT,
                                      recomp_link.z };
                    int32_t air_speed = intent_speed ? intent_speed : link_air_speed_q8;
                    player_bg_update(&link_bg, wall, &wall_hit, &feet, recomp_link_yaw,
                                     intent_heading, air_speed);
                    /* Player_Action_8084411C, descending: grab a ledge ahead. */
                    if (!grounded && link_velocity_y_q8 < 0 && !climbing) {
                        int32_t floor;
                        uint16_t off = (uint16_t)(intent_heading - recomp_link_yaw);
                        if (!kokiri_collision_floor(feet.x, feet.z, feet.y, &floor))
                            floor = BG_Y_MIN;
                        /* yDistToLedge >= 150 with the stick forward: grab the
                         * wall itself if it is a ladder or vines. */
                        if (link_bg.interact && air_speed > 0 &&
                            link_bg.y_dist_to_ledge >= PLAYER_CLIMB_AIR_WALL &&
                            player_input_stick_pushed(&input) &&
                            (off < 0x2000 || off > 0xE000)) {
                            if (player_climb_start(&link_climb, &link_bg, &feet,
                                                   &recomp_link_yaw, false)) {
                                recomp_link.x = feet.x;
                                recomp_link.y = feet.y + RECOMP_LINK_EYE_HEIGHT;
                                recomp_link.z = feet.z;
                                link_velocity_y_q8 = 0;
                                link_fall_remainder_q8 = 0;
                                link_air_speed_q8 = 0; link_air_evade = false;
                            }
                        } else if (player_hang_grab(&link_bg, air_speed, feet.y, floor)) {
                            feet.y += link_bg.y_dist_to_ledge;
                            link_start_hang(&link_bg.wall_hit, link_bg.dist_to_wall,
                                            feet, false);
                        }
                    }
                }
                /* Not on the launch step: that step still reads grounded,
                 * and would drop the 250 jump's speedXZ 1.0 (BUG-012). */
                if (link_air_evade) {
                    if (grounded && !link_air_evade_launch) {
                        link_air_evade = false;
                        link_air_speed_q8 = 0;
                    }
                    link_air_evade_launch = false;
                } else if ((grounded && !launched) || intent_speed)
                    link_air_speed_q8 = 0;
                {
                    int32_t push[2];
                    world_props_displace(recomp_link.x,recomp_link.y-RECOMP_LINK_EYE_HEIGHT,recomp_link.z,
                                         scene_flow_is_interior()?0:kokiri_scene_room(),push);
                    if(push[0] || push[1]) kokiri_collision_move_actor(&recomp_link,push[0],0,push[1]);
                }
                dungeon_doors_constrain(&recomp_link.x,&recomp_link.z,recomp_link.y-RECOMP_LINK_EYE_HEIGHT);
                mido_push_link();
                boulder_push_link();
                if (recovered) {
                    /* Recovery must not ease: a camera left down in the void
                     * would show empty space on the way back. */
                    oot_follow_snap(&link_follow, &recomp_link, recomp_link_yaw);
                    recovered = false;
                    player_camera_reset(&link_camera);
                }
                /* A prerendered interior keeps the one viewpoint its
                 * backdrop was drawn from; easing a follow camera around
                 * inside it would slide the room off the picture. */
                if (link_crawl.phase == PLAYER_CRAWL_IN) {
                    if (!crawl_cam_valid) crawl_camera_begin();
                    if (crawl_cam_valid) crawl_camera(link_crawl.speed_q8 != 0);
                } else if (crawl_cam_valid) {
                    /* Out of Subj4: the follow camera starts behind him. */
                    crawl_cam_valid = false;
                    oot_follow_snap(&link_follow, &recomp_link, recomp_link_yaw);
                    player_camera_reset(&link_camera);
                }
                if (view_first_person) {
                    if (!fp_camera_done) first_person_camera_step(&input);
                } else if (recomp_first_person())
                    ;
                else if (scene_flow_is_interior())
                    interior_camera();
                else {
                    link_state_t pose = link_anim_state();
                    unsigned mode = pose == LINK_STATE_CLIMB ? PLAYER_CAMERA_CLIMB :
                        (pose == LINK_STATE_HANG || pose == LINK_STATE_PULL_UP) ?
                            PLAYER_CAMERA_HANG : PLAYER_CAMERA_NORMAL;
                    player_camera_update(&link_camera, &link_follow, mode,
                                      &recomp_link, recomp_link_yaw,
                                      recomp_link.x != step_x || recomp_link.z != step_z,
                                      &recomp_camera, &recomp_yaw, &recomp_pitch);
                }
                /* Checked after the move, so standing ON the doorway is what
                 * triggers it -- the same collision triangle the original
                 * uses. Abandons the rest of the catch-up: the scene those
                 * remaining steps belonged to is no longer loaded. */
                {int32_t eye[3],at[3];if(gohma_camera(eye,at)){
                    int dx=at[0]-eye[0],dz=at[2]-eye[2];
                    recomp_camera.x=eye[0];recomp_camera.y=eye[1];recomp_camera.z=eye[2];
                    recomp_yaw=collide_heading(dx,dz);
                    recomp_pitch=-(int16_t)collide_heading(at[1]-eye[1],collide_isqrt((uint32_t)((int64_t)dx*dx+(int64_t)dz*dz)));
                }}
                recomp_collision_indexed = scene_collision_indexed;
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
        if (oot_core_ocarina_state() & 1u)
            link_anim_pose(LINK_CLIP_OCARINA_HOLD, (now / 3) % LINK_FRAMES_OCARINA_HOLD, 0);
        else link_anim_pose(link_anim_clip(), link_anim_frame(), link_anim_fraction());
        {
            static unsigned int trail_tick;
            if (!gameplay_is_paused() && trail_tick != now / 2) {
                trail_tick = now / 2;
                link_anim_trail_update(recomp_link.x,
                    recomp_link.y - RECOMP_LINK_EYE_HEIGHT + link_anim_y_offset_q8() / 256,
                    recomp_link.z, recomp_link_yaw, gameplay_sword_active());
            }
        }
        frame_timer_end(FRAME_PHASE_SKINNING);

    } else {
        while (steps--) kokiri_camera_update(&recomp_camera, &recomp_yaw,
                                             &recomp_pitch, buttons, false,
                                             false);
    }
    story_owl_camera();
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
     * kokiri_scene_load_backdrop() uploads it, and the very next recomp_update()
     * turned the layer off again. */
    cutscene_sky_update();
    unsigned layers = NBG0ON | minimap_layer_flags() |
                  ((title_visible ||
                    (kokiri_scene_backdrop_active() &&
                     !cutscene_hides_scene())) ? NBG1ON : 0);
    if (gameplay_is_paused() && recomp_link_active && !pause_windows_failed()) {
        /* RGB page on NBG0; preserve NBG1's frozen interior underneath.
         * RGB carousel uses enlargement, with explicit fetch scheduling. */
        slScrDisp(layers & ~NBG2ON);
        slScrCycleSet(0x5555FEEEu,0x05555EEEu,0x4444EEEEu,0x4444EEEEu);
    } else slScrAutoDisp(layers);
}

/* -1 no attempt yet this session, 0 failed, 1 succeeded. */
int recomp_save_report(void)
{
    return (!save_reported ? -1 : (save_succeeded ? 1 : 0));
}

bool recomp_file_select_is_visible(void)
{
    return (file_select_visible);
}

bool recomp_title_is_visible(void)
{
    return title_visible;
}

bool recomp_skip_prompt(void)
{
    return ((game_mode() == GAME_MODE_CUTSCENE && cutscene_is_playing()) || gohma_cinematic()) &&
           skip_input.armed;
}

/* Render-only animation clock: wall/UI/audio clocks must keep running. */
unsigned int recomp_world_clock(void)
{
    static unsigned int previous, animation;
    static bool was_paused;
    unsigned int now = recomp_clock();
    bool paused = gameplay_is_paused();
    if (!paused && !was_paused) animation += now - previous;
    previous = now;
    was_paused = paused;
    return animation;
}

unsigned int recomp_clock(void)
{
    return ticks;
}

/* En_Arrow uses projectile-ignored surfaces, including floor/ceiling sweeps. */
bool player_items_wall(const int32_t from[3], int32_t to[3], unsigned item)
{
    bg_vec_t a = {from[0], from[1], from[2]}, b = {to[0], to[1], to[2]}, at;
    bg_hit_t hit;
    bool wall=bg_line(&a, &b, &at, BG_CHECK_ALL | BG_CHECK_ONE_FACE, BG_IGNORE_PROJECTILES, &hit);
    if(wall){to[0] = at.x; to[1] = at.y; to[2] = at.z;}
    if(item==PLAYER_ITEM_SEED && dungeon_puzzles_shot(from,to))return true;
    return wall;
}

bool recomp_slingshot_aiming(void) { return item_aim && view_first_person; }
