#include "gameplay.h"
#include "oot_core_host.h"
#include "player_items.h"
#include "dungeon_puzzles.h"
#include "skulltula.h"
#include "wall_skull.h"
#include "dekubaba.h"
#include "hintnuts.h"
#include "gohma_larva.h"
#include "gohma.h"
#include "kokiri_actors.h"
#include "kokiri_dialogue.h"
#include "dialogue_text.h"
#include "save_state.h"
#include "collide.h"
#include "actor_sys.h"
#include "attention.h"
#include "karebaba.h"
#include "game_over.h"
#include "world_props.h"
#include "world_signs.h"
#include "player_attack.h"
#include "link_clips.h"
#include "cutscene.h"
#include "npc_draw.h"

gameplay_t          gameplay;
/* Contact colliders (run_contacts: sword, grass, Link, boulder), kept off work RAM. */
typedef struct {
    collider_t blade[3], tufts[KOKIRI_GRASS_COUNT], wonders[KOKIRI_WONDER_COUNT];
    collider_t link_body, link_shield, boulder, nut;
    collider_t props[4];
} gp_contacts_t;

/* Tags of the actorless colliders: tufts 0.., wonders 0x100+i. */
#define GP_TAG_LINK_BODY    0x200
#define GP_TAG_LINK_SHIELD  0x201
#define GP_TAG_BOULDER      0x300
#define GP_TAG_BLADE        0x400
#define GP_TAG_NUT          0x500
static bool         blade_live;         /* sword window open this step */
/* Last step's blade tip and midpoint for the swept capsules; valid only
** within one attack instance (swing_count). */
static int32_t      blade_prev_tip[3], blade_prev_mid[3];
static uint16_t     blade_prev_swing;
static bool         blade_prev_valid;
static gp_contacts_t *contacts;

unsigned int        gameplay_contacts_bytes(void) { return sizeof(gp_contacts_t); }
bool                gameplay_contacts_init(void *storage, unsigned int bytes)
{
    unsigned char *p = (unsigned char *)storage;
    unsigned int i;
    contacts = 0;
    if (!storage || bytes < sizeof(gp_contacts_t))
        return false;
    for (i = 0; i < sizeof(gp_contacts_t); ++i)
        p[i] = 0;
    contacts = (gp_contacts_t *)storage;
    return true;
}

#if KOKIRI_GRASS_COUNT > 16 || KOKIRI_RUPEE_COUNT > 16 || KOKIRI_WONDER_COUNT > 16
#error Expand collectible storage before adding actors
#endif

static uint32_t drop_random(void)
{
    gameplay.drop_rng ^= gameplay.drop_rng << 13;
    gameplay.drop_rng ^= gameplay.drop_rng >> 17;
    gameplay.drop_rng ^= gameplay.drop_rng << 5;
    return gameplay.drop_rng;
}

/* Squared planar distance. Coordinates stay inside +/-5000 world units, so the
** products fit a 32-bit int with room to spare and no 64-bit math is needed on
** the SH-2. */
static int32_t      planar_squared(int32_t ax, int32_t az, int32_t bx, int32_t bz)
{
    int32_t dx = ax - bx, dz = az - bz;
    return dx * dx + dz * dz;
}

/* Signed shortest turn between two binang headings, -32768..32767. */
static int32_t      yaw_delta(uint16_t from, uint16_t to)
{
    return (int32_t)(int16_t)(uint16_t)(to - from);
}

static void __attribute__((optimize("Os"))) sync_gear_to_save(void);
static void __attribute__((optimize("Os"))) sync_gear_from_save(void);
static void         grant_rupee(unsigned int value);

/* ---- Mido (EnMd, z_en_md.c) --------------------------------------------- */

/* Path 1 of spot04 (spot04_scenePathList_00030C_020002D4): home, then the
** point he walks to once he stands aside; EnMd_SetMovedPos puts him on its
** last point on later visits. */
#define MIDO_HOME_X     1522
#define MIDO_HOME_Z     105
#define MIDO_MOVED_X    1412
#define MIDO_MOVED_Z    211
#define MIDO_ROOM       0

/* The chest, wonder and Mido tables are Kokiri Forest (spot04) placements. */
static bool         in_forest(void)
{
    return save_state.scene_id == SAVE_SCENE_KOKIRI_FOREST;
}

/* Does placement `npc` exist in the current scene (M3b)? Scene first, then
** the source spawn rule. En_Ko child types are filtered offline
** (EnKo_CanSpawn). EnMd_ShouldSpawn: forest until EVENTCHKINF_1C / Zelda's
** letter, his house after. EnSa_GetType (child): forest until the Emerald;
** her house needs the Fairy Ocarina, which this slice never grants. */
bool                gameplay_npc_present(unsigned int npc)
{
    const kokiri_npc_t *p;
    bool left;
    if (npc >= KOKIRI_NPC_COUNT)
        return false;
    p = &kokiri_npcs[npc];
    if (p->scene != save_state.scene_id ||
        (p->kind != KOKIRI_NPC_SARIA && oot_core_owns_kokiri_npcs()))
        return false;   /* En_Ko / En_Md: the decomp's (npc_draw draws them) */
    left = save_get_event_chk_inf(EVENTCHKINF_MIDO_LEFT_FOR_HIS_HOUSE) ||
           save_get_event_chk_inf(EVENTCHKINF_OBTAINED_ZELDAS_LETTER);
    switch (p->kind) {
    case KOKIRI_NPC_MIDO:
        return p->scene == SAVE_SCENE_KOKIRI_FOREST ? !left :
               p->scene == SAVE_SCENE_MIDOS_HOUSE && left;
    case KOKIRI_NPC_SARIA:
        return p->scene == SAVE_SCENE_KOKIRI_FOREST &&
               !save_check_quest_item(QUEST_KOKIRI_EMERALD);
    default:
        return true;
    }
}

/* Forest Mido runs the Deku Tree gate; his house copy never moves. */
static bool         gate_mido(int npc)
{
    return kokiri_npcs[npc].kind == KOKIRI_NPC_MIDO &&
           kokiri_npcs[npc].scene == SAVE_SCENE_KOKIRI_FOREST;
}

/* Speaker placement with Mido's live position swapped in. */
static kokiri_npc_t mido_live;
static kokiri_npc_t exit_blocker_live;
static bool exit_blocker_valid;
static uint16_t mido_yaw;

static bool exit_blocker(unsigned int npc)
{
    return kokiri_npcs[npc].scene == SAVE_SCENE_KOKIRI_FOREST &&
           kokiri_npcs[npc].kind == KOKIRI_NPC_CHILD &&
           (kokiri_npcs[npc].param & 255) == 3;
}

/* EnKo func_80A995CC: stand on the 80-unit ring around home, facing Link.
 * Its source path is only used after the Emerald (M5/M6). */
static void update_exit_blocker(const gameplay_input_t *in)
{
    unsigned int i;
    if (!in_forest()) return;
    for (i = 0; i < KOKIRI_NPC_COUNT; ++i) if (exit_blocker(i)) {
        int32_t sine, cosine;
        const kokiri_npc_t *home = &kokiri_npcs[i];
        uint16_t yaw = gameplay_facing(in->x - home->x, in->z - home->z);
        gameplay_sincos(yaw, &sine, &cosine);
        exit_blocker_live = *home;
        if (save_check_quest_item(QUEST_KOKIRI_EMERALD)) {
            exit_blocker_live.x = KOKIRI_EXIT_MOVED_X;
            exit_blocker_live.y = KOKIRI_EXIT_MOVED_Y;
            exit_blocker_live.z = KOKIRI_EXIT_MOVED_Z;
            exit_blocker_valid = true;
            return;
        }
        exit_blocker_live.x += (80 * sine) >> 16;
        exit_blocker_live.z += (80 * cosine) >> 16;
        exit_blocker_live.yaw = gameplay_facing(in->x - exit_blocker_live.x,
                                               in->z - exit_blocker_live.z);
        exit_blocker_valid = true;
        return;
    }
}

/*
** Saria's first greeting (En_Sa SARIA_TYPE_GREETING).
**
** EnSa_GetType (z_en_sa.c:430-436) picks the greeting over the standing NPC in
** Kokiri Forest whenever the Kokiri Emerald is not owned and
** INFTABLE_SARIA_GREETED_LINK is clear -- that one bit is the whole latch.
** EnSa_Init then installs gKokiriForestSariaGreetingCs into csCtx.script and
** sets cutsceneTrigger, which is what cutscene_start_in_scene stands in for.
**
** Her position, facing and pose come from actor cue channel 1 for as long as
** it runs, exactly as EnSa_HandleCutscene takes them. When it ends,
** EnSa_BecomeIdle puts her back on home.pos/initRot and sets the flag -- at
** the END of the cutscene, not when its text box closes.
*/
#define GP_SARIA_CS_CHANNEL GAMEPLAY_SARIA_CUE_CHANNEL
static kokiri_npc_t saria_live;
static bool saria_greeting_running;
/* EnSa_GetType runs ONCE, when the actor spawns. Armed on scene entry and
** cleared as soon as the greeting starts or the type turns out not to be
** SARIA_TYPE_GREETING, so a cutscene that cannot start is not retried on
** every step for the rest of the scene. */
static bool saria_greeting_armed;

bool gameplay_saria_cutscene(void)
{
    return saria_greeting_running;
}

void gameplay_saria_greeting_cancel(void)
{
    saria_greeting_armed = false;
}

static bool saria_greeting_due(void)
{
    return in_forest() && !save_check_quest_item(QUEST_KOKIRI_EMERALD) &&
           !save_get_inf_table(INFTABLE_SARIA_GREETED_LINK);
}

static bool forest_saria(int npc)
{
    return kokiri_npcs[npc].kind == KOKIRI_NPC_SARIA &&
           kokiri_npcs[npc].scene == SAVE_SCENE_KOKIRI_FOREST;
}

static const kokiri_npc_t *npc_at(int npc)
{
    if (saria_greeting_running && forest_saria(npc) &&
        cutscene_actor_channel_visible(GP_SARIA_CS_CHANNEL)) {
        saria_live = kokiri_npcs[npc];
        saria_live.x = (int16_t)cutscene_actor_channel_x(GP_SARIA_CS_CHANNEL);
        saria_live.y = (int16_t)cutscene_actor_channel_y(GP_SARIA_CS_CHANNEL);
        saria_live.z = (int16_t)cutscene_actor_channel_z(GP_SARIA_CS_CHANNEL);
        saria_live.yaw = cutscene_actor_channel_yaw(GP_SARIA_CS_CHANNEL);
        return &saria_live;
    }
    if (gate_mido(npc)) {
        mido_live = kokiri_npcs[npc];
        mido_live.x = (int16_t)gameplay.mido_x;
        mido_live.z = (int16_t)gameplay.mido_z;
        mido_live.yaw = mido_yaw;
        return &mido_live;
    }
    if (exit_blocker(npc) && exit_blocker_valid) return &exit_blocker_live;
    return &kokiri_npcs[npc];
}

/* Kokiri NPCs as registry actors, so Link's lock and Navi share one
** identity (M2d). Drawing and talking stay on kokiri_npcs; each step copies
** the live position (Mido's included) onto the actor. Focus: a head-height
** stand-in above the feet; arrow: 0 (no source lockOnArrowOffset; hover adds +17).
** Source per-NPC attentionRangeType is a logged gap (ATTN_RANGE_SLICE_NPC). */
#define GP_NPC_FOCUS_Y  40
#define GP_NPC_ARROW_Y  0       /* En_Ko/Md/Sa set no lockOnArrowOffset */
#define GP_NPC_ACTOR_ID 0xF001
static const actor_profile_t npc_profile = {
    GP_NPC_ACTOR_ID, ACTORCAT_NPC, ACTOR_FLAG_TARGETABLE, 0, 0, 0, 0
};
static actor_handle_t npc_actor[KOKIRI_NPC_COUNT];
/* shape.rot.y after NPC_TRACKING_FULL_BODY turns. Live copies (gate Mido,
** the type-3 exit ring) own their facing and ignore it. */
static uint16_t     npc_turn[KOKIRI_NPC_COUNT];
static uint32_t     npc_turned;


void gameplay_npc_focus(unsigned int npc, const int32_t offset[3])
{
    actor_t *a;
    unsigned int k;
    if (npc >= KOKIRI_NPC_COUNT) return;
    a = actor_resolve(npc_actor[npc]);
    if (a) for (k = 0; k < 3; ++k) a->focus[k] = (int16_t)offset[k];
}

static void         npc_actors_kill(void)
{
    unsigned int i;
    for (i = 0; i < KOKIRI_NPC_COUNT; ++i) {
        actor_kill(actor_resolve(npc_actor[i]));
        npc_actor[i] = ACTOR_HANDLE_NONE;
    }
}

#ifdef DOSEI_OOT_CORE
/* The decomp En_Ko/En_Md standing in for kokiri_npcs[i] (same ENKO_TYPE, or
** Mido), so Navi's hover and Z-target keep working on decomp NPCs. */
static const OotCoreNpcView *core_npc_for(const kokiri_npc_t *npc)
{
    const OotCoreNpcView *v;
    int n, k;
    if (npc->scene != save_state.scene_id || npc->kind == KOKIRI_NPC_SARIA ||
        !oot_core_owns_kokiri_npcs())
        return 0;
    n = oot_core_npcs(&v);
    for (k = 0; k < n; ++k)
        if (npc->kind == KOKIRI_NPC_MIDO ? v[k].id == 0x016D /* ACTOR_EN_MD */ :
            v[k].id == 0x0163 /* ACTOR_EN_KO */ && (v[k].params & 0xFF) == (npc->param & 0xFF))
            return v[k].alpha ? &v[k] : 0;
    return 0;
}
#endif

static void         sync_npc_actors(void)
{
    unsigned int i;
    for (i = 0; i < KOKIRI_NPC_COUNT; ++i) {
        const kokiri_npc_t *npc = npc_at(i);
        actor_t *a = actor_resolve(npc_actor[i]);
#ifdef DOSEI_OOT_CORE
        const OotCoreNpcView *core = core_npc_for(npc);
        if (core) {
            if (!a) {
                a = actor_spawn(&npc_profile, save_state.scene_id, ACTOR_ROOM_NONE,
                                core->x, core->y, core->z, 0, (uint16_t)i);
                if (!a) continue;
                a->attention = ATTN_NPC;
                a->range = ATTN_RANGE_SLICE_NPC;
                a->focus[1] = GP_NPC_FOCUS_Y;
                a->arrow_y = GP_NPC_ARROW_Y;
                npc_actor[i] = actor_handle(a);
            }
            a->x = core->x; a->y = core->y; a->z = core->z;
            continue;
        }
#endif
        if (!gameplay_npc_present(i)) {
            npc_turned &= ~(1u << i);
            if (a) actor_kill(a);
            npc_actor[i] = ACTOR_HANDLE_NONE;
            continue;
        }
        if (!a) {
            a = actor_spawn(&npc_profile, save_state.scene_id, ACTOR_ROOM_NONE,
                            npc->x, npc->y, npc->z, 0, (uint16_t)i);
            if (!a)
                continue;       /* pool full: counted, retried next step */
            a->attention = ATTN_NPC;
            a->range = ATTN_RANGE_SLICE_NPC;
            a->focus[1] = GP_NPC_FOCUS_Y;
            a->arrow_y = GP_NPC_ARROW_Y;
            npc_actor[i] = actor_handle(a);
        }
        a->x = npc->x;
        a->y = npc->y;
        a->z = npc->z;
    }
}

int                 gameplay_target_npc(void)
{
    const actor_t *a = actor_resolve(gameplay.target);
    return a && a->profile == &npc_profile ? (int)a->params : -1;
}

bool                gameplay_npcs_present(void)
{
    unsigned int i;
    for (i = 0; i < KOKIRI_NPC_COUNT; ++i)
        if (gameplay_npc_present(i))
            return true;
    return false;
}

int32_t             gameplay_npc_x(unsigned int npc)
{
    return npc < KOKIRI_NPC_COUNT ? npc_at((int)npc)->x : 0;
}

int32_t             gameplay_npc_y(unsigned int npc)
{
    return npc < KOKIRI_NPC_COUNT ? npc_at((int)npc)->y : 0;
}

int32_t             gameplay_npc_z(unsigned int npc)
{
    return npc < KOKIRI_NPC_COUNT ? npc_at((int)npc)->z : 0;
}

uint16_t gameplay_npc_yaw(unsigned int npc)
{
    const kokiri_npc_t *p;
    if (npc >= KOKIRI_NPC_COUNT) return 0;
    p = npc_at((int)npc);
    return p == &kokiri_npcs[npc] && (npc_turned & (1u << npc)) ? npc_turn[npc] : p->yaw;
}

void                gameplay_npc_turn(unsigned int npc, uint16_t yaw)
{
    if (npc >= KOKIRI_NPC_COUNT || npc_at((int)npc) != &kokiri_npcs[npc]) return;
    npc_turn[npc] = yaw;
    npc_turned |= 1u << npc;
}

void                gameplay_npc_turns_reset(void)
{
    npc_turned = 0;
}

/*
** One step of the greeting, run from the gameplay loop.
**
** Starting it is EnSa_Init's job (cutsceneTrigger); ending it is
** EnSa_BecomeIdle's: put her back on home.pos and initRot -- the cue walks her
** away from both -- and set INFTABLE_SARIA_GREETED_LINK so EnSa_GetType
** returns SARIA_TYPE_STANDING from here on and the greeting never plays twice.
**
** The cutscene clips have to be resident before it starts. If they cannot be
** loaded the greeting does not start at all, and the flag is left clear so it
** is retried rather than silently skipped with Saria frozen in her idle pose.
*/
bool                gameplay_saria_greeting_step(void)
{
    if (saria_greeting_running) {
        unsigned int cue;
        if (cutscene_is_playing() && cutscene_id() == CUTSCENE_SARIA_GREETING) {
            /* EnSa_HandleCutscene's stepTimer: the run cue is the only one
            ** that puts a foot down, every 8 source frames. */
            cue = cutscene_actor_channel_cue(GP_SARIA_CS_CHANNEL);
            if (cue == 3 && (cutscene_frame() % 8) == 0)
                gameplay.events |= GP_EVENT_FOOTSTEP;
            return true;
        }
        /* EnSa_BecomeIdle. npc_at stops swapping as soon as this clears, so
        ** her drawn position returns to the kokiri_npcs entry by itself. */
        saria_greeting_running = false;
        npc_draw_free_saria_cutscene();
        save_set_inf_table(INFTABLE_SARIA_GREETED_LINK);
        return false;
    }
    if (!saria_greeting_armed)
        return false;
    /* The type is decided once, at spawn: a file that already has the flag or
    ** the Emerald gets SARIA_TYPE_STANDING and never asks again. */
    if (!saria_greeting_due()) {
        saria_greeting_armed = false;
        return false;
    }
    /* Wait for a step that can actually hand the scene over, but keep the arm
    ** so entering mid-conversation only delays the greeting. */
    if (cutscene_is_playing() || gameplay.talking || gameplay.paused ||
        gameplay_blocks_world())
        return false;
    saria_greeting_armed = false;
    if (!npc_draw_load_saria_cutscene())
        return false;
    if (!cutscene_start_in_scene(CUTSCENE_SARIA_GREETING)) {
        npc_draw_free_saria_cutscene();
        return false;
    }
    saria_greeting_running = true;
    return true;
}

static void         mido_place(void)
{
    if (save_get_event_chk_inf(EVENTCHKINF_MIDO_STOOD_ASIDE_KOKIRI) &&
        !save_check_quest_item(QUEST_KOKIRI_EMERALD)) {
        gameplay.mido_state = 2;
        gameplay.mido_x = MIDO_MOVED_X;
        gameplay.mido_z = MIDO_MOVED_Z;
    } else {
        gameplay.mido_state = 0;
        gameplay.mido_x = MIDO_HOME_X;
        gameplay.mido_z = MIDO_HOME_Z;
    }
}

/* EnMd_BlockPath while idle: stand 60 units from home toward Link. EnMd_Walk
** afterwards: along path 1 to its last point, then EnMd_Watch there. Not run
** while his box is open (talkState != IDLE freezes the block position). */
static void         update_mido(const gameplay_input_t *in)
{
    if (!gameplay.talking)
        mido_yaw = gameplay_facing(in->x - gameplay.mido_x, in->z - gameplay.mido_z);
    if (gameplay.mido_state == 0) {
        int32_t sine, cosine;
        if (in->room != MIDO_ROOM || gameplay.talking)
            return;
        gameplay_sincos(gameplay_facing(in->x - MIDO_HOME_X, in->z - MIDO_HOME_Z),
                        &sine, &cosine);
        gameplay.mido_x = MIDO_HOME_X + ((GP_MIDO_BLOCK_OFFSET * sine) >> 16);
        gameplay.mido_z = MIDO_HOME_Z + ((GP_MIDO_BLOCK_OFFSET * cosine) >> 16);
    } else if (gameplay.mido_state == 1) {
        int32_t dx = MIDO_MOVED_X - gameplay.mido_x;
        int32_t dz = MIDO_MOVED_Z - gameplay.mido_z;
        int32_t sine, cosine;
        if (dx * dx + dz * dz <= 1) {
            gameplay.mido_x = MIDO_MOVED_X;
            gameplay.mido_z = MIDO_MOVED_Z;
            gameplay.mido_state = 2;
            /* EnMd_Walk commits departure only after the path completes. */
            if (save_check_quest_item(QUEST_KOKIRI_EMERALD))
                save_set_event_chk_inf(EVENTCHKINF_MIDO_LEFT_FOR_HIS_HOUSE);
            return;
        }
        /* Q8 accumulation would be smoother; a unit a step is his speed. */
        gameplay_sincos(gameplay_facing(dx, dz), &sine, &cosine);
        gameplay.mido_x += (sine + (sine >= 0 ? 32768 : -32768)) >> 16;
        gameplay.mido_z += (cosine + (cosine >= 0 ? 32768 : -32768)) >> 16;
    }
}

/* ---- En_Goroiwa: maze boulder --------------------------------------------
** Only the maze shape (build_actors refuses others): one-way loop, the
** bit-10 MoveAndFall variant on a flat path, so the floor is the path height.
** A hit found at the end of one step is acted on the next, as the source's
** AT_HIT is read by the next frame's EnGoroiwa_Roll. */

static int32_t      step_to(int32_t v, int32_t target, int32_t step)
{
    if (step < 0) step = -step;
    if (v < target) return v + step >= target ? target : v + step;
    return v - step <= target ? target : v - step;
}

static void         boulder_face(void)
{
    const int16_t *p = kokiri_boulder_path[gameplay.boulder_next];
    /* gameplay_facing takes world integers; Saturn converts them to Q16.
    ** Q8 deltas overflow that conversion (the first 331-unit leg becomes
    ** 84736), although the host's double atan2 accepts them unchanged. */
    gameplay.boulder_rot = gameplay_facing((int32_t)p[0] - (gameplay.boulder_x >> 16),
                                           (int32_t)p[2] - (gameplay.boulder_z >> 16));
}

static void         boulder_teleport(int i)
{
    gameplay.boulder_x = (int32_t)kokiri_boulder_path[i][0] << 16;
    gameplay.boulder_y = (int32_t)kokiri_boulder_path[i][1] << 16;
    gameplay.boulder_z = (int32_t)kokiri_boulder_path[i][2] << 16;
}

static void         boulder_reset(void)
{
    gameplay.boulder_cur = 0;
    gameplay.boulder_next = 1;
    gameplay.boulder_dir = 1;
    gameplay.boulder_state = 0;
    gameplay.boulder_speed = 0;
    gameplay.boulder_vy = 0;
    gameplay.boulder_nohit = 0;
    gameplay.boulder_hit = false;
    gameplay.boulder_in_way = false;
    boulder_teleport(0);
    boulder_face();
}

/* EnGoroiwa_ReverseDirection + FaceNextWaypoint. */
static void         boulder_reverse(void)
{
    gameplay.boulder_dir = (int8_t)-gameplay.boulder_dir;
    gameplay.boulder_cur = gameplay.boulder_next;
    gameplay.boulder_next = (int8_t)(gameplay.boulder_next + gameplay.boulder_dir);
    boulder_face();
}

/* EnGoroiwa_NextWaypoint, loop mode ONEWAY. */
static void         boulder_next_point(void)
{
    int end = KOKIRI_BOULDER_POINTS - 1;
    gameplay.boulder_cur = gameplay.boulder_next;
    gameplay.boulder_next = (int8_t)(gameplay.boulder_next + gameplay.boulder_dir);
    if (gameplay.boulder_next < 0) {
        gameplay.boulder_cur = (int8_t)end;
        gameplay.boulder_next = (int8_t)(end - 1);
        gameplay.boulder_dir = -1;
    } else if (gameplay.boulder_next > end) {
        gameplay.boulder_cur = 0;
        gameplay.boulder_next = 1;
        gameplay.boulder_dir = 1;
    }
    if (gameplay.boulder_cur == 0 || gameplay.boulder_cur == end)
        boulder_teleport(gameplay.boulder_cur);
    boulder_face();
}

/* EnGoroiwa_MoveAndFall; true when x and z reached the next point. */
static bool         boulder_move(bool accelerate)
{
    const int16_t *p = kokiri_boulder_path[gameplay.boulder_next];
    int32_t sine, cosine, floor = (int32_t)p[1] << 16;
    bool reached;
    if (accelerate)
        gameplay.boulder_speed = step_to(gameplay.boulder_speed, GP_BOULDER_SPEED_Q16,
                                         GP_BOULDER_ACCEL_Q16);
    gameplay_sincos(gameplay.boulder_rot, &sine, &cosine);
    gameplay.boulder_vy += GP_BOULDER_GRAVITY_Q16;
    if (gameplay.boulder_vy < GP_BOULDER_MIN_VY_Q16)
        gameplay.boulder_vy = GP_BOULDER_MIN_VY_Q16;
    gameplay.boulder_x = step_to(gameplay.boulder_x, (int32_t)p[0] << 16,
                                 (int32_t)(((int64_t)gameplay.boulder_speed * sine) >> 16));
    gameplay.boulder_z = step_to(gameplay.boulder_z, (int32_t)p[2] << 16,
                                 (int32_t)(((int64_t)gameplay.boulder_speed * cosine) >> 16));
    reached = gameplay.boulder_x == (int32_t)p[0] << 16 &&
              gameplay.boulder_z == (int32_t)p[2] << 16;
    gameplay.boulder_y += gameplay.boulder_vy;
    if (gameplay.boulder_y <= floor)
        gameplay.boulder_y = floor;             /* flat path: bg check floor */
    return reached;
}

static void         boulder_wait_start(void)
{
    gameplay.boulder_state = 2;
    gameplay.boulder_speed = 0;
    gameplay.boulder_wait = (KOKIRI_BOULDER_ROT_Z & 1) ? 9 : 30;   /* 6 / 20 frames */
}

/* Player_UpdateDamage, AC_HIT branch: the last pass's body hit costs its
** damage, pushes Link 4.0 away from the attacker, 20 frames intangible. */
/* En_Nutsball, the Deku Scrub projectile (z_en_nutsball.c), as M2c's
** labelled reflection test: only a standard-build emitter (demo.c) fires it;
** no Deku Scrub exists in the slice until M5. Source drop audit: Actor_Kill
** with no item drop, so none here. Q16 position; y = cylinder base. */
static bool         nut_bg_hit;

void                gameplay_nut_fire(int32_t x, int32_t y, int32_t z, uint16_t yaw)
{
    gameplay.nut_state = 1;
    gameplay.nut_reflected = 0;
    gameplay.nut_timer = GP_NUT_TIMER_STEPS;    /* EnNutsball_WaitForObject */
    gameplay.nut_yaw = yaw;
    gameplay.nut_x = x * 65536; gameplay.nut_y = y * 65536; gameplay.nut_z = z * 65536;
    gameplay.nut_vy_q8 = 0;
    gameplay.nut_fall_q8 = 0;                   /* gravity 0 until the timer ends */
    nut_bg_hit = false;
    if (contacts) contacts->nut.result = 0;
}

bool                gameplay_nut_body(int32_t *x, int32_t *y, int32_t *z)
{
    if (!gameplay.nut_state)
        return false;
    *x = gameplay.nut_x >> 16; *y = gameplay.nut_y >> 16; *z = gameplay.nut_z >> 16;
    return true;
}

/* EnNutsball_Projectile + Actor_MoveXZGravity, reading the previous pass. */
static void         update_nut(const gameplay_input_t *in)
{
    uint8_t r;
    int32_t sine, cosine, pos[3], dx, dz, dy;
    if (!gameplay.nut_state)
        return;
    if (!in_forest()) {
        gameplay.nut_state = 0;
        return;
    }
    r = contacts ? contacts->nut.result : 0;
    if (--gameplay.nut_timer == 0)
        gameplay.nut_fall_q8 = -171;            /* gravity -1.0 from here on */
    if (nut_bg_hit || (r & (COL_RES_AT_HIT | COL_RES_AC_HIT))) {
        /* Deku Shield reflects: AT_HIT + AT_TYPE_ENEMY + AT_BOUNCED. */
        if ((gameplay.equipped & GP_SHIELD) && !gameplay.nut_reflected &&
            (r & COL_RES_AT_HIT) && (r & COL_RES_AT_BOUNCED)) {
            gameplay.nut_reflected = 1;         /* AT_TYPE_PLAYER, DMG_DEKU_STICK */
            /* shieldRot.y + 0x8000: straight out from the guard's face. */
            gameplay.nut_yaw = in->yaw;
            gameplay.nut_timer = GP_NUT_TIMER_STEPS;
            contacts->nut.result = 0;
            nut_bg_hit = false;
            return;
        }
        gameplay.nut_state = 0;
        gameplay.events |= GP_EVENT_NUT_BREAK;
        return;
    }
    if (gameplay.nut_timer <= -GP_NUT_LIFE_STEPS) {
        gameplay.nut_state = 0;
        return;
    }
    gameplay_sincos(gameplay.nut_yaw, &sine, &cosine);
    gameplay.nut_vy_q8 += gameplay.nut_fall_q8;
    if (gameplay.nut_vy_q8 < -20 * 256)
        gameplay.nut_vy_q8 = -20 * 256;
    dx = (int32_t)(((int64_t)GP_NUT_SPEED_Q16 * sine) >> 16);
    dz = (int32_t)(((int64_t)GP_NUT_SPEED_Q16 * cosine) >> 16);
    dy = gameplay.nut_vy_q8 * 256;
    pos[0] = gameplay.nut_x >> 16; pos[1] = gameplay.nut_y >> 16; pos[2] = gameplay.nut_z >> 16;
    {
        int32_t nx = gameplay.nut_x + dx, ny = gameplay.nut_y + dy, nz = gameplay.nut_z + dz;
        int32_t moved[3] = { pos[0], pos[1], pos[2] };
        nut_bg_hit = gameplay_ball_move(moved, (nx >> 16) - pos[0], (ny >> 16) - pos[1],
                                        (nz >> 16) - pos[2]);
        gameplay.nut_x = nx + (moved[0] - (nx >> 16)) * 65536;
        gameplay.nut_y = ny + (moved[1] - (ny >> 16)) * 65536;
        gameplay.nut_z = nz + (moved[2] - (nz >> 16)) * 65536;
    }
}

/* One cylinder, AT and AC together, as sCylinderInit. */
static void         register_nut(void)
{
    collider_t *c = &contacts->nut;
    if (!gameplay.nut_state)
        return;
    c->shape = COLSHAPE_CYLINDER;
    c->actor = 0;
    c->x = gameplay.nut_x >> 16; c->y = gameplay.nut_y >> 16; c->z = gameplay.nut_z >> 16;
    c->y_shift = 0;
    c->radius = GP_NUT_RADIUS;
    c->height = GP_NUT_HEIGHT;
    c->at_type = gameplay.nut_reflected ? AT_TYPE_PLAYER : AT_TYPE_ENEMY;
    c->at_dmg = gameplay.nut_reflected ? DMG_DEKU_STICK : 0xFFCFFFFFu;
    c->at_damage = GP_NUT_DAMAGE;
    c->ac_type = AC_TYPE_PLAYER;
    c->ac_bumper = 0xFFCFFFFFu;
    c->damage_table = 0;
    c->defense = 0;
    c->ac_flags = COL_OUTSIDE_ACTOR;
    c->attack_id = 0;
    c->tag = GP_TAG_NUT;
    collide_set_at(c);
    collide_set_ac(c);
}

static bool         jump_guard;     /* jump attack still owns its no-hit window */
#define STEPS_OF(frames) (((frames) * 3 + 1) / 2)    /* 20 Hz frames -> steps */

/* The one damage entry: enemy contact, fall and void all come through here
** (Health_ChangeBy via Player_InflictDamage / func_80837B18). */
static void         link_damage(unsigned int units)
{
    save_damage(units);
    if(units){gameplay.hurt_flash_timer=GP_INTANGIBLE_STEPS;gameplay.hurt_flash_phase=0;}
}

/* Player_UpdateDamage -> func_80837C0C, response NONE (grounded): pushed
** away 4.0 a frame; the D_808544B0 hit clip unless running (speedXZ > 4)
** without a hostile lock, which only flinches. Front/back from where the
** hit came from; damage >= 5 picks the heavier "hit" clips. */
static void         consume_link_damage(const gameplay_input_t *in)
{
    const actor_t *lock;
    int16_t side;
    if (!gameplay.hurt_pending)
        return;
    gameplay.hurt_pending = 0;
    /* Invulnerable (dodge): the hit lands, knocks back, but costs nothing,
    ** and Player_SetIntangibility leaves an invulnerable timer alone. */
    if (gameplay.invulnerable) {
        link_damage(0);
    } else {
        link_damage(gameplay.hurt_damage);
        gameplay.intangible = GP_INTANGIBLE_STEPS;
    }
    gameplay.knock_yaw = gameplay.hurt_yaw;
    gameplay.knock_speed = GP_HIT_SPEED_Q16;
    gameplay.knock_down = false;
    gameplay.events |= GP_EVENT_HURT;
    lock = gameplay.face_locked ? actor_resolve(gameplay.target) : (const actor_t *)0;
    if (!(in->moving && !(lock && (lock->flags & ACTOR_FLAG_HOSTILE))))
        gameplay.events2 |= GP2_EVENT_HIT_ANIM;
    /* hurt_yaw points away from the attacker: along Link's facing means the
    ** hit came from behind. */
    side = (int16_t)(gameplay.hurt_yaw - in->yaw);
    if (side > -0x4000 && side < 0x4000)
        gameplay.events2 |= GP2_EVENT_HIT_BACK;
    if (gameplay.hurt_damage >= 5)
        gameplay.events2 |= GP2_EVENT_HIT_HEAVY;
}

void                gameplay_land(int32_t fell, bool rolled)
{
    /* func_80843E64 via the landing branch: a landing roll returns first. */
    if (rolled || fell < 400 || gameplay.dead)
        return;
    link_damage(fell < 800 ? 8 : 16);
    gameplay.hurt_flash_timer=STEPS_OF(40);
    gameplay.intangible = STEPS_OF(40);      /* Player_SetIntangibility(40) */
    gameplay.events2 |= GP2_EVENT_LAND_DAMAGE;
}

void                gameplay_void_out(void)
{
    gameplay.events2 |= GP2_EVENT_ABYSS;
}

void                gameplay_void_respawned(void)
{
    /* unk_A86 -> func_808382DC: Player_InflictDamage(-16), REVENGE. */
    if (gameplay.dead)
        return;
    link_damage(16);
    gameplay.events2 |= GP2_EVENT_VOID_DAMAGE;
}

void                gameplay_death_anim_done(void)
{
    game_over_anim_done();
}

/* Health_IsCritical (z_lifemeter.c): the threshold grows with capacity. */
static bool         health_critical(void)
{
    unsigned int cap = save_state.health_capacity, h = save_state.health;
    unsigned int limit = cap <= 0x50 ? 0x10 : cap <= 0xA0 ? 0x18 : cap <= 0xF0 ? 0x20 : 0x2C;
    return h > 0 && h <= limit;
}

static void         drop_target(void);

/* Lethal exactly once, on the ground (z_player.c: health 0 and ground). */
static void         check_death(const gameplay_input_t *in)
{
    if (gameplay.dead || save_state.health != 0 || !in->grounded)
        return;
    gameplay.dead = true;
    gameplay.hurt_flash_timer=0;gameplay.hurt_flash_phase=0;
    gameplay.world_sfx=0;gameplay.opened_chest=0;
    player_items_reset();
    gameplay.swing = 0;
    gameplay.attack_phase = 0;
    gameplay.shielding = false;
    drop_target();
    game_over_start();
    gameplay.events2 |= GP2_EVENT_DEATH;
}

static void         update_boulder(const gameplay_input_t *in)
{
    int32_t bx, bz;
    if (!in_forest() || in->room != KOKIRI_BOULDER_ROOM) {
        gameplay.boulder_live = false;          /* room unload kills it */
        return;
    }
    if (!gameplay.boulder_live) {
        boulder_reset();                        /* Init: waypoint 0 */
        gameplay.boulder_live = true;
    }
    if (gameplay.boulder_nohit)
        --gameplay.boulder_nohit;
    bx = gameplay.boulder_x >> 16;
    bz = gameplay.boulder_z >> 16;
    if (gameplay.boulder_state == 0) {
        if (gameplay.boulder_hit) {
            uint16_t toward = gameplay_facing(in->x - bx, in->z - bz);
            int16_t diff = (int16_t)(toward - gameplay.boulder_rot);
            gameplay.boulder_hit = false;
            gameplay.boulder_in_way = diff > -0x4000 && diff < 0x4000;
            if (gameplay.boulder_in_way)
                boulder_reverse();              /* bit 10 set: always */
            /* Actor_SetPlayerKnockbackLarge(2.0, yawTowardsPlayer, 0, 0):
            ** no extra damage; the 4 came through Link's cylinder. */
            gameplay.knock_yaw = toward;
            gameplay.knock_speed = GP_KNOCKBACK_SPEED_Q16;
            gameplay.knock_down = true;
            gameplay.events |= GP_EVENT_KNOCKDOWN;
            /* EnGoroiwa_SetupMoveAndFallToGround */
            gameplay.boulder_state = 1;
            gameplay.boulder_speed = (int32_t)(((int64_t)gameplay.boulder_speed * 9830) >> 16);
            gameplay.boulder_vy = GP_BOULDER_HOP_Q16;
            if (KOKIRI_BOULDER_ROT_Z & 1)
                gameplay.boulder_nohit = 75;    /* 50 frames */
        } else if (boulder_move(true)) {
            boulder_next_point();
        }
    } else if (gameplay.boulder_state == 1) {
        boulder_move(false);
        if (gameplay.boulder_vy < 0 &&
            gameplay.boulder_y == (int32_t)kokiri_boulder_path[gameplay.boulder_next][1] << 16) {
            if (gameplay.boulder_in_way && (KOKIRI_BOULDER_ROT_Z & 1))
                boulder_reverse();
            boulder_wait_start();
        }
    } else if (gameplay.boulder_wait) {
        --gameplay.boulder_wait;
    } else {
        gameplay.boulder_hit = false;
        gameplay.boulder_state = 0;
    }
}

/* Boulder AT for the shared pass (roll only, live within 300 of Link). The
** r58 sphere is a cylinder r58 spanning the sphere's height. */
static void         register_boulder(const gameplay_input_t *in)
{
    collider_t *c = &contacts->boulder;
    int32_t dx, dz;
    if (!gameplay.boulder_live || in->room != KOKIRI_BOULDER_ROOM ||
        gameplay.boulder_state != 0 || gameplay.boulder_nohit)
        return;
    dx = in->x - (gameplay.boulder_x >> 16);
    dz = in->z - (gameplay.boulder_z >> 16);
    if (dx * dx + dz * dz >= GP_BOULDER_LIVE_RANGE * GP_BOULDER_LIVE_RANGE)
        return;
    c->shape = COLSHAPE_CYLINDER;
    c->actor = 0;
    c->x = gameplay.boulder_x >> 16;
    c->y = (gameplay.boulder_y >> 16) + GP_BOULDER_CENTER_Y - GP_BOULDER_RADIUS;
    c->z = gameplay.boulder_z >> 16;
    c->y_shift = 0;
    c->radius = GP_BOULDER_RADIUS;
    c->height = 2 * GP_BOULDER_RADIUS;
    c->at_type = AT_TYPE_ENEMY;
    c->at_dmg = DMG_UNBLOCKABLE;            /* 0x20000000 */
    c->at_damage = GP_BOULDER_DAMAGE;
    c->attack_id = 0;
    c->ac_flags = COL_OUTSIDE_ACTOR;
    c->tag = GP_TAG_BOULDER;
    collide_set_at(c);
}

bool                gameplay_boulder_body(unsigned int room, int32_t *x, int32_t *y, int32_t *z)
{
    if (!in_forest() || room != KOKIRI_BOULDER_ROOM || !gameplay.boulder_live)
        return false;
    *x = gameplay.boulder_x >> 16;
    *y = (gameplay.boulder_y >> 16) + GP_BOULDER_CENTER_Y;
    *z = gameplay.boulder_z >> 16;
    return true;
}

bool                gameplay_mido_body(unsigned int room, int32_t *x, int32_t *z)
{
    if (!in_forest() || room != MIDO_ROOM || oot_core_owns_kokiri_npcs() ||
        save_get_event_chk_inf(EVENTCHKINF_MIDO_LEFT_FOR_HIS_HOUSE) ||
        save_get_event_chk_inf(EVENTCHKINF_OBTAINED_ZELDAS_LETTER))
        return false;
    *x = gameplay.mido_x;
    *z = gameplay.mido_z;
    return true;
}

/* EnMd talk-close effects, keyed by the rule's first text id (actor.textId).
** 0x102F: EVENTCHKINF_02 + INFTABLE_0C. 0x1033: NPC_TALK_STATE_ACTION ->
** EnMd_BlockPath sets EVENTCHKINF_04 and starts the walk. */
static void         mido_talk_closed(uint16_t text_id)
{
    if (text_id == 0x102F) {
        save_set_event_chk_inf(EVENTCHKINF_MIDO_DENIED_DEKU_TREE_ACCESS);
        save_set_inf_table(INFTABLE_MIDO_REFUSED_ONCE);
    } else if ((text_id == 0x1033 || (text_id == 0x1045 &&
                save_check_quest_item(QUEST_KOKIRI_EMERALD))) && gameplay.mido_state == 0) {
        save_set_event_chk_inf(EVENTCHKINF_MIDO_STOOD_ASIDE_KOKIRI);
        gameplay.mido_state = 1;
        gameplay.events |= GP_EVENT_MIDO_ASIDE;
    }
}

/* ---- speakerless text (get-item, shop) ------------------------------------ */

static bool         open_system_text(uint16_t text_id)
{
    unsigned int i;
    for (i = 0; i < DIALOGUE_SYSTEM_COUNT; ++i) {
        if (dialogue_system[i].text_id != text_id)
            continue;
        gameplay.rule = (int16_t)dialogue_system[i].rule;
        gameplay.speaker = -1;
        gameplay.prompt = -1;
        gameplay.page = gameplay.page_part = 0;
        gameplay.talking = true;
        gameplay.events |= GP_EVENT_TALK_OPEN;
        return true;
    }
    return false;
}

void gameplay_drop_message(unsigned int item)
{
    if (open_system_text(item == 12 ? 0x0034 : 0x0037)) {
        gameplay.events2 |= GP2_EVENT_ITEM_FANFARE;
        gameplay.get_item = item == 12 ? GP_GET_NUT : GP_GET_STICK;
        gameplay.get_item_age = 0;
        gameplay.events |= GP_EVENT_PICKUP;
    }
}
bool gameplay_token_message(void)
{
    if(gameplay.talking || !open_system_text(0x00B4))return false;
    gameplay.events2|=GP2_EVENT_SMALL_FANFARE;
    gameplay.events|=GP_EVENT_PICKUP;return true;
}
bool gameplay_boss_heart(void)
{
    if (gameplay.talking || gameplay.dead || gameplay.paused ||
        save_state.scene_id != SAVE_SCENE_DEKU_TREE_BOSS || !gohma_defeated() ||
        save_get_collectible(SAVE_SCENE_DEKU_TREE_BOSS, 0x1f) ||
        !open_system_text(0x00c6)) return false;
    save_item_give(SAVE_ITEM_HEART_CONTAINER);
    save_set_collectible(SAVE_SCENE_DEKU_TREE_BOSS, 0x1f);
    gameplay.get_item = GP_GET_CONTAINER;
    gameplay.get_item_age = 0;
    gameplay.events |= GP_EVENT_PICKUP;
    return true;
}
bool gameplay_actor_message(uint16_t text_id)
{
    return !gameplay.talking && open_system_text(text_id);
}

/* ---- En_Box (z_en_box.c) --------------------------------------------------- */

#define CHEST_FLAG(c)   ((c)->param & 0x1F)

bool                gameplay_chest_opened(unsigned int index)
{
    return index < KOKIRI_CHEST_COUNT &&
           save_get_treasure(kokiri_chests[index].scene, CHEST_FLAG(&kokiri_chests[index]));
}

/* EnBox_WaitOpen: Link in the chest's own frame at -50 < z < 0, |x| < 20,
** |y| < 10, and Player_IsFacingActor(0x3000). A then opens it: the treasure
** flag is set during the opening and GI_SWORD_KOKIRI is granted OWNED only
** (Item_Give, z_parameter.c) -- equipping is the pause screen's job. */
static int16_t      chest_in_reach(const gameplay_input_t *in)
{
    unsigned int i;
    for (i = 0; i < KOKIRI_CHEST_COUNT; ++i) {
        const kokiri_chest_t *c = &kokiri_chests[i];
        int32_t dx = in->x - c->x, dy = in->y - c->y, dz = in->z - c->z;
        int32_t sine, cosine, lx, lz, turn;
        if (save_state.scene_id != c->scene || in->room != c->room || gameplay_chest_opened(i))
            continue;
        if (dy <= -10 || dy >= 10)
            continue;
        gameplay_sincos(c->yaw, &sine, &cosine);
        lx = (dx * cosine - dz * sine) >> 16;
        lz = (dx * sine + dz * cosine) >> 16;
        if (lz <= -50 || lz >= 0 || lx <= -20 || lx >= 20)
            continue;
        turn = yaw_delta(in->yaw, gameplay_facing(c->x - in->x, c->z - in->z));
        if (turn < 0) turn = -turn;
        if (turn >= 0x3000)
            continue;
        return (int16_t)i;
    }
    return -1;
}

static bool __attribute__((optimize("Os"))) update_chest(const gameplay_input_t *in)
{
    const kokiri_chest_t *c;
    gameplay.chest_prompt = chest_in_reach(in);
    if (gameplay.chest_prompt < 0 || !in->interact)
        return false;
    c = &kokiri_chests[gameplay.chest_prompt];
    {
        unsigned int reward = (c->param >> 5) & 0x7F;
        save_item_t item;
        unsigned int text;
        switch (reward) {
        case 0x05: item = SAVE_ITEM_SLINGSHOT; text = 0x30; break;
        case 0x40: item = SAVE_ITEM_DEKU_COMPASS; text = 0x67; break;
        case 0x41: item = SAVE_ITEM_DEKU_MAP; text = 0x66; break;
        case 0x27: item = SAVE_ITEM_SWORD_KOKIRI; text = 0xA4; break;
        case 0x48: item = SAVE_ITEM_RECOVERY_HEART; text = 0x55; break;
        case 0x4C: item = SAVE_ITEM_RUPEE_GREEN; text = 0x6F; break;
        case 0x4D: item = SAVE_ITEM_RUPEE_BLUE; text = 0xCC; break;
        default: return false; /* Never consume a chest we cannot grant. */
        }
        /* EnBox opens even when its heart/wallet reward is already full.
         * The shared grant clamps/refuses the excess; this is not a purchase. */
        save_item_give(item);
        gameplay.opened_chest=(uint8_t)(gameplay.chest_prompt+1);
        if((c->param>>12)!=5 && (c->param>>12)!=6 && (c->param>>12)!=7 && (c->param>>12)!=8)
            gameplay.events2|=GP2_EVENT_CHEST_OPEN;
        if(reward==0x05 || reward==0x40 || reward==0x41 || reward==0x27)
            gameplay.events2|=GP2_EVENT_ITEM_FANFARE;
        else gameplay.world_sfx|=1u<<GP_SFX_BOX_ITEM;
        save_set_treasure(c->scene, CHEST_FLAG(c));
        gameplay.rupees = (uint8_t)save_state.rupees;
        if (reward == 0x27) gameplay.owned |= GP_SWORD;
        gameplay.chest_prompt = -1;
        gameplay.get_item_age = 0;
        gameplay.get_item = reward == 0x27 ? GP_SWORD : reward == 0x48 ? GP_GET_HEART : GP_GET_CHEST_ITEM;
        gameplay.events |= GP_EVENT_PICKUP;
        open_system_text(text);
    }
    return true;
}

/* ---- En_Wonder_Item (z_en_wonder_item.c) ---------------------------------- */

#define WONDER_SWITCH(w) ((w)->param & 0x3F)       /* 0x3F = none */
/* Switch flags 0x00-0x1F persist in the save; 0x20-0x3E are the scene's
** temporary half, cleared on scene load. The temporary ones live in
** wonder_done, which only a scene reset clears. */
#define SWITCH_SAVED(f)  ((f) < 0x20)

static bool         wonder_flagged(const kokiri_wonder_t *w)
{
    unsigned int flag = WONDER_SWITCH(w);
    return SWITCH_SAVED(flag) && save_get_switch(save_state.scene_id, flag);
}

/* EnWonderItem_DropCollectible with autoCollect: the rupee is collected at
** once. Its switch flag is set, then the actor is killed. */
static void         wonder_pay(unsigned int i, bool auto_collect)
{
    const kokiri_wonder_t *w = &kokiri_wonders[i];
    unsigned int flag = WONDER_SWITCH(w);
    if (auto_collect)
        grant_rupee(w->value);
    else {
        gameplay.wonder_drop[i] = w->value;
        gameplay.wonder_age[i] = 0;
    }
    if (SWITCH_SAVED(flag))
        save_set_switch(save_state.scene_id, flag);
    gameplay.wonder_done |= (uint16_t)(1u << i);
}

/* Tag point `index` of class `mode` (1 free, 6 ordered) in `room`. */
static const kokiri_wonder_t *wonder_tag(unsigned int mode, unsigned int room,
                                         unsigned int index)
{
    unsigned int i;
    for (i = 0; i < KOKIRI_WONDER_COUNT; ++i) {
        const kokiri_wonder_t *w = &kokiri_wonders[i];
        if (w->mode == mode && w->room == room && (unsigned)(w->rot_z & 0xFF) == index)
            return w;
    }
    return 0;
}

static bool         within(const gameplay_input_t *in, const kokiri_wonder_t *w,
                           int32_t radius)
{
    int32_t dx = in->x - w->x, dy = in->y - w->y, dz = in->z - w->z;
    return dx * dx + dy * dy + dz * dz < radius * radius;
}

/* Multitag: rot.z = count + 10 * seconds; the source timer is timerMod + 81
** frames at 20 Hz, scaled here to 30 Hz steps. */
static void         wonder_multitag(const gameplay_input_t *in, unsigned int i)
{
    const kokiri_wonder_t *w = &kokiri_wonders[i];
    unsigned int tens = w->rot_z >= 10 ? (unsigned)w->rot_z / 10 : 0;
    unsigned int count = (unsigned)w->rot_z - tens * 10, t;
    unsigned int point_mode = w->mode == 0 ? 1 : 6;
    if (gameplay.wonder_timer[i] && --gameplay.wonder_timer[i] == 1) {
        gameplay.wonder_done |= (uint16_t)(1u << i);   /* ran out: killed */
        return;
    }
    for (t = 0; t < count && t < 8; ++t) {
        const kokiri_wonder_t *tag = wonder_tag(point_mode, w->room, t);
        if (!tag || (gameplay.wonder_tags[i] & (1u << t)) || !within(in, tag, 50))
            continue;
        if (w->mode == 5 && t != gameplay.wonder_next[i]) {
            gameplay.wonder_done |= (uint16_t)(1u << i); /* out of order */
            return;
        }
        gameplay.wonder_tags[i] |= (uint8_t)(1u << t);
        ++gameplay.wonder_next[i];
        gameplay.wonder_timer[i] = (uint8_t)(((tens * 20 + 81) * 3) / 2);
        return;
    }
    if (count && gameplay.wonder_next[i] >= count)
        wonder_pay(i, true);
}

/* Room reload: a trigger with no switch flag spawns again, fresh. */
static void         wonder_room_reset(void)
{
    unsigned int i;
    for (i = 0; i < KOKIRI_WONDER_COUNT; ++i) {
        gameplay.wonder_tags[i] = gameplay.wonder_next[i] = 0;
        gameplay.wonder_timer[i] = 0;
        gameplay.wonder_drop[i] = 0;
        if (WONDER_SWITCH(&kokiri_wonders[i]) == 0x3F)
            gameplay.wonder_done &= (uint16_t)~(1u << i);
    }
}

static bool         rupee_near(const gameplay_input_t *in, int x, int y, int z, int room);

static void         update_wonders(const gameplay_input_t *in)
{
    unsigned int i;
    if (in->room != gameplay.room) {
        gameplay.room = in->room;
        wonder_room_reset();
    }
    for (i = 0; i < KOKIRI_WONDER_COUNT; ++i) {
        const kokiri_wonder_t *w = &kokiri_wonders[i];
        int32_t dy = in->y - w->y;
        if (w->room != in->room || w->scene != save_state.scene_id)
            continue;
        if (gameplay.wonder_drop[i]) {
            if (gameplay.wonder_age[i] < GP_DROP_DELAY)
                ++gameplay.wonder_age[i];
            else if (rupee_near(in, w->x, w->y, w->z, w->room)) {
                grant_rupee(gameplay.wonder_drop[i]);
                gameplay.wonder_drop[i] = 0;
            }
        }
        if ((gameplay.wonder_done & (1u << i)) || wonder_flagged(w))
            continue;
        if (w->mode == 2) {
            /* xzDistToPlayer < 50 and |dy| < 30 */
            if (planar_squared(in->x, in->z, w->x, w->z) < 50 * 50 &&
                dy > -30 && dy < 30)
                wonder_pay(i, true);
        } else if (w->mode == 0 || w->mode == 5) {
            wonder_multitag(in, i);
        }
    }
}

bool                gameplay_wonder_drop(unsigned int index)
{
    return index < KOKIRI_WONDER_COUNT && gameplay.wonder_drop[index] &&
           gameplay.wonder_age[index] >= GP_DROP_DELAY;
}

void __attribute__((optimize("Os"))) gameplay_reset(void)
{
    unsigned int i;
    gameplay.hurt_flash_timer=0;gameplay.hurt_flash_phase=0;
    gameplay.world_sfx=0;gameplay.opened_chest=0;
    player_items_reset();
    exit_blocker_valid = false;
    /* A new scene spawns a new En_Sa, so its type is chosen again here. Any
    ** greeting still running belonged to the scene being left. */
    saria_greeting_running = false;
    saria_greeting_armed = true;
    for (i = 0; i < KOKIRI_NPC_COUNT; ++i)
        if (gate_mido(i)) { mido_yaw = kokiri_npcs[i].yaw; break; }
    gameplay.owned = 0;
    gameplay.equipped = 0;
    gameplay.shielding = false;
    npc_actors_kill();
    karebaba_reset();
    gameplay.target = ACTOR_HANDLE_NONE;
    gameplay.arrow = ACTOR_HANDLE_NONE;
    gameplay.target_hold = 0;
    /* A new scene spawns a new En_Elf: fairyFlags clear, and its init resets
    ** a timer outside 3000..25800 (z_en_elf.c EnElf_Init). */
    gameplay.navi_text = 0;
    gameplay.navi_calling = false;
    gameplay.navi_read = false;
    gameplay.navi_phase = 0;
    gameplay.dead = false;
    gameplay.alarm_steps = 0;
    if (save_state.navi_timer >= GP_NAVI_TIMER_MAX || save_state.navi_timer < GP_NAVI_HINT_TO)
        save_state.navi_timer = 0;
    gameplay.swing = 0;
    gameplay.swing_hit = 0;
    gameplay.attack_phase = 0;
    gameplay.attack_thirds = 0;
    gameplay.attack_id = 0;
    gameplay.combo_count = 0;
    gameplay.combo_timer = 0;
    gameplay.lunge_pending = false;
    gameplay.lunge_q16 = 0;
    gameplay.lunge_decel_q16 = 0;
    gameplay.blade_bounced = false;
    gameplay.guard_pending = false;
    gameplay.nut_state = 0;
    blade_prev_valid = false;
    nut_bg_hit = false;
    gameplay.grass_cut = 0;
    world_props_reset();
    /* swing_count restarts below, so old attack ids would read as repeats. */
    for (i = 0; contacts && i < KOKIRI_GRASS_COUNT; ++i)
        collide_forget(&contacts->tufts[i]);
    for (i = 0; contacts && i < KOKIRI_WONDER_COUNT; ++i)
        collide_forget(&contacts->wonders[i]);
    if (contacts) {
        collide_forget(&contacts->link_body);
        collide_forget(&contacts->link_shield);
    }
    gameplay.wonder_done = 0;
    gameplay.room = 0xFF;          /* first step counts as a room load */
    wonder_room_reset();
    gameplay.chest_prompt = -1;
    gameplay.get_item = 0;
    gameplay.shop_state = 0;
    gameplay.shop_cursor = 0;
    gameplay.shop_face = gameplay.shop_target = 0;
    gameplay.shop_accum_x = gameplay.shop_accum_y = 0;
    gameplay.shop_move_x = false;
    gameplay.choice = 0;
    boulder_reset();
    gameplay.boulder_live = false;
    gameplay.intangible = 0;
    gameplay.invulnerable = 0;
    jump_guard = false;
    gameplay.knock_speed = 0;
    gameplay.knock_down = false;
    gameplay.hurt_pending = 0;
    gameplay.shop_prompt = false;
    gameplay.events = 0;
    gameplay.face_yaw = 0;
    gameplay.face_locked = false;
    gameplay.cut_count = 0;
    gameplay.swing_count = 0;
    gameplay.speaker = -1;
    gameplay.prompt = -1;
    gameplay.rule = -1;
    gameplay.page = gameplay.page_part = 0;
    gameplay.talking = false;
    gameplay.paused = false;
    gameplay.cursor = GP_SLOT_SWORD;
    gameplay.pause_window = (pause_window_state_t){ .page = PAUSE_EQUIPMENT, .cursor = {0, 2, 18, 1} };
    gameplay.rupees = 0;
    gameplay.rupee_taken = 0;
    gameplay.drop_rng = 0x12345678u;
    /* owned/equipped/rupees/rupee_taken are restored from the
    ** save by sync_gear_from_save() at the end of this function. */
    for (i = 0; i < 16; ++i) {
        gameplay.grass_rupee[i] = 0;
        gameplay.grass_age[i] = 0;
    }
    /* Reset means "entering a scene", and it runs AFTER the file select has
    ** either started a new game or loaded a save. So gear, rupees and taken
    ** pickups are read FROM the save here. Writing to it instead is what made
    ** loading a file wipe the sword and shield it had just restored. */
    sync_gear_from_save();
    mido_place();
}

bool                gameplay_grass_cut(unsigned int index)
{
    return index < KOKIRI_GRASS_COUNT &&
           (gameplay.grass_cut & (1u << index)) != 0;
}

/* Session-only wallet and collectible flags. Child wallet: z_inventory.c. */
bool gameplay_rupee_taken(unsigned int index)
{
    return index < KOKIRI_RUPEE_COUNT && (gameplay.rupee_taken & (1u << index));
}

static bool rupee_near(const gameplay_input_t *in, int x, int y, int z, int room)
{
    int dy = in->y - y;
    return in->room == room && dy >= -40 && dy <= 40 &&
           planar_squared(in->x, in->z, x, z) <= 30 * 30;
}

static void grant_rupee(unsigned int value)
{
    /* Item_Give via the shared grant path (save_item_give): the wallet is
    ** saved state and clamps there; gameplay.rupees is only its cache. */
    save_state.rupees = gameplay.rupees;
    save_item_give(value >= 20 ? SAVE_ITEM_RUPEE_RED :
                   value >= 5 ? SAVE_ITEM_RUPEE_BLUE : SAVE_ITEM_RUPEE_GREEN);
    gameplay.rupees = (uint8_t)save_state.rupees;
    gameplay.events |= GP_EVENT_RUPEE;
}

static void collect_rupees(const gameplay_input_t *in)
{
    unsigned int i;
    if (!in_forest()) return;
    for (i = 0; i < KOKIRI_RUPEE_COUNT; ++i) {
        const kokiri_rupee_t *r = &kokiri_rupees[i];
        if (!gameplay_rupee_taken(i) && !oot_core_owns_kokiri_props() &&
            rupee_near(in, r->x, r->y, r->z, r->room)) {
            gameplay.rupee_taken |= (uint16_t)(1u << i);
            /* Per-scene collectible flag, where OoT keeps them, so a rupee
            ** already picked up does not reappear after a save and reload. */
            save_set_collectible(save_state.scene_id, (r->param >> 8) & 63);
            grant_rupee(r->value);
        }
    }
    for (i = 0; i < KOKIRI_GRASS_COUNT; ++i) {
        const kokiri_prop_t *g = &kokiri_grass[i];
        if (!gameplay.grass_rupee[i] || in->room != g->room) continue;
        if (gameplay.grass_age[i] < GP_DROP_DELAY) {
            ++gameplay.grass_age[i];
            continue; /* visible pop before Link can collect it */
        }
        if (rupee_near(in, g->x, g->y, g->z, g->room)) {
            grant_rupee(gameplay.grass_rupee[i]);
            gameplay.grass_rupee[i] = 0;
        }
    }
}

/* Gear, rupees and one-off pickups live in the SAVE. gameplay_t holds them as
** GP_* bits and a small wallet only because the per-step actions read them
** constantly and a bitmask is cheaper than four accessor calls.
**
** The save is the owner; these two functions keep the cache agreeing with it.
** Direction matters and getting it wrong is how a loaded file lost its sword
** and shield: gameplay_reset() runs when entering a scene, which is AFTER a
** file has been loaded, so it must read FROM the save. Only the places where
** gear actually changes -- a pickup, or equipping in the menu -- write TO it.
**
** Mido's gate is decided by save_cur_equip_value(), so the two must not drift
** in either direction. */
static void __attribute__((optimize("Os"))) sync_gear_to_save(void)
{
    save_give_equip(EQUIP_TYPE_SWORD,
                    (gameplay.owned & GP_SWORD) ? EQUIP_VALUE_SWORD_KOKIRI : 0);
    save_give_equip(EQUIP_TYPE_SHIELD,
                    (gameplay.owned & GP_SHIELD) ? EQUIP_VALUE_SHIELD_DEKU : 0);
    save_set_equip(EQUIP_TYPE_SWORD,
                   (gameplay.equipped & GP_SWORD) ? EQUIP_VALUE_SWORD_KOKIRI : 0);
    save_set_equip(EQUIP_TYPE_SHIELD,
                   (gameplay.equipped & GP_SHIELD) ? EQUIP_VALUE_SHIELD_DEKU : 0);
    save_state.rupees = gameplay.rupees;
}

static void __attribute__((optimize("Os"))) sync_gear_from_save(void)
{
    unsigned int    i;

    gameplay.owned = 0;
    gameplay.equipped = 0;
    if (save_all_equip_value(EQUIP_TYPE_SWORD) == EQUIP_VALUE_SWORD_KOKIRI)
        gameplay.owned |= GP_SWORD;
    if (save_all_equip_value(EQUIP_TYPE_SHIELD) == EQUIP_VALUE_SHIELD_DEKU)
        gameplay.owned |= GP_SHIELD;
    if (save_cur_equip_value(EQUIP_TYPE_SWORD) == EQUIP_VALUE_SWORD_KOKIRI)
        gameplay.equipped |= GP_SWORD;
    if (save_cur_equip_value(EQUIP_TYPE_SHIELD) == EQUIP_VALUE_SHIELD_DEKU)
        gameplay.equipped |= GP_SHIELD;
    gameplay.rupees = (uint8_t)(save_state.rupees > GP_WALLET_CAPACITY
                                ? GP_WALLET_CAPACITY : save_state.rupees);
    /* The retired ground-pickup ITEMGETINF bits are left as they are and not
    ** read: gear earned that way stays in the equipment words above, and they
    ** are never reinterpreted as chest or shop flags. */
    /* Room rupees are per-scene collectible flags, exactly as OoT stores them,
    ** so a collected rupee stays collected across a save. Cut grass is NOT
    ** persisted: OoT keeps grass in the temp half of the scene flags, which it
    ** deliberately never saves, so regrowing is the original's behaviour. */
    gameplay.rupee_taken = 0;
    for (i = 0; i < KOKIRI_RUPEE_COUNT && i < 16; ++i)
        if (in_forest() && save_get_collectible(save_state.scene_id, (kokiri_rupees[i].param >> 8) & 63))
            gameplay.rupee_taken |= (uint16_t)(1u << i);
}

/* One-handed D_80854190 rows: attack clip, recovery clip (unk_04, the
** non-lock-on end; hostile lock-on unk_08 arrives with enemies). */
static const struct { uint8_t id, clip, end, frames, end_frames; } attack_rows[] = {
    { ATTACK_FORWARD, LINK_CLIP_SLASH, LINK_CLIP_RECOVER,
      LINK_FRAMES_SLASH, LINK_FRAMES_RECOVER },
    { ATTACK_FORWARD_COMBO, LINK_CLIP_SLASH_COMBO, LINK_CLIP_SLASH_COMBO_END,
      LINK_FRAMES_SLASH_COMBO, LINK_FRAMES_SLASH_COMBO_END },
    { ATTACK_RIGHT, LINK_CLIP_RIGHT, LINK_CLIP_RIGHT_END,
      LINK_FRAMES_RIGHT, LINK_FRAMES_RIGHT_END },
    { ATTACK_RIGHT_COMBO, LINK_CLIP_RIGHT_COMBO, LINK_CLIP_RIGHT_COMBO_END,
      LINK_FRAMES_RIGHT_COMBO, LINK_FRAMES_RIGHT_COMBO_END },
    { ATTACK_LEFT, LINK_CLIP_LEFT, LINK_CLIP_LEFT_END,
      LINK_FRAMES_LEFT, LINK_FRAMES_LEFT_END },
    { ATTACK_LEFT_COMBO, LINK_CLIP_LEFT_COMBO, LINK_CLIP_LEFT_COMBO_END,
      LINK_FRAMES_LEFT_COMBO, LINK_FRAMES_LEFT_COMBO_END },
    { ATTACK_STAB, LINK_CLIP_STAB, LINK_CLIP_STAB_END,
      LINK_FRAMES_STAB, LINK_FRAMES_STAB_END },
    { ATTACK_STAB_COMBO, LINK_CLIP_STAB_COMBO, LINK_CLIP_STAB_COMBO_END,
      LINK_FRAMES_STAB_COMBO, LINK_FRAMES_STAB_COMBO_END },
    { ATTACK_JUMP_START, LINK_CLIP_JSLASH, LINK_CLIP_JSLASH,
      LINK_FRAMES_JSLASH, LINK_FRAMES_JSLASH },
    { ATTACK_JUMP_FINISH, LINK_CLIP_JSLASH_HIT, LINK_CLIP_JSLASH_END,
      LINK_FRAMES_JSLASH_HIT, LINK_FRAMES_JSLASH_END },
    { ATTACK_SPIN, LINK_CLIP_SPIN, LINK_CLIP_SPIN_END,
      LINK_FRAMES_SPIN, LINK_FRAMES_SPIN_END },
    { ATTACK_BIG_SPIN, LINK_CLIP_BIG_SPIN, LINK_CLIP_BIG_SPIN_END,
      LINK_FRAMES_BIG_SPIN, LINK_FRAMES_BIG_SPIN_END },
};

static unsigned int attack_row(unsigned int id)
{
    unsigned int i;
    for (i = 0; i < sizeof(attack_rows) / sizeof(attack_rows[0]); ++i)
        if (attack_rows[i].id == id)
            return i;
    return 0;
}

/* func_8084285C: the quads deal damage between unk_0C and unk_0D, read on
** the clip frame BEFORE this step advances it (it runs ahead of
** LinkAnimation_Update). */
static bool         blade_on_frame(void)
{
    if (gameplay.attack_phase == 7)     /* func_80833A20 while curFrame < 2 */
        return gameplay.attack_thirds > 0 && gameplay.attack_thirds < 6u;
    if (gameplay.attack_phase == 6)     /* func_8084285C(6, 7, 99) */
        return player_attack_weapon_state(gameplay.attack_id, gameplay.attack_thirds, 1) > 0;
    return gameplay.attack_phase == 1 &&
           player_attack_weapon_state(gameplay.attack_id, gameplay.attack_thirds, 0) > 0;
}

/* The blade as the last step used it. */
bool                gameplay_sword_active(void)
{
    return blade_live;
}

bool                gameplay_attack_time(unsigned int *clip, unsigned int *thirds)
{
    unsigned int frame;
    /* The crouch stab, rebound and guard recoil play without AnimMovement:
    ** no root motion (their speedXZ comes through lunge_q16). */
    if (gameplay.attack_phase >= 7 || !gameplay_attack_pose(clip, &frame))
        return false;
    *thirds = gameplay.attack_thirds;
    return true;
}

bool                gameplay_attack_pose(unsigned int *clip, unsigned int *frame)
{
    unsigned int r, last;
    if (!gameplay.attack_phase)
        return false;
    r = attack_row(gameplay.attack_id);
    if (gameplay.attack_phase == 3) {
        bool right = gameplay.charge_from == ATTACK_RIGHT ||
                     gameplay.charge_from == ATTACK_RIGHT_COMBO;
        *clip = right ? LINK_CLIP_CHARGE_STARTL : LINK_CLIP_CHARGE_START;
        last = LINK_FRAMES_CHARGE_START - 1u;
    } else if (gameplay.attack_phase == 4) {
        *clip = LINK_CLIP_CHARGE_WAIT;
        *frame = (gameplay.attack_thirds / 3u) % LINK_FRAMES_CHARGE_WAIT;
        return true;
    } else if (gameplay.attack_phase == 5) {
        *clip = LINK_CLIP_CHARGE_END;
        last = LINK_FRAMES_CHARGE_END - 1u;
    } else if (gameplay.attack_phase == 7) {
        *clip = LINK_CLIP_CROUCH_STAB;
        last = LINK_FRAMES_CROUCH_STAB - 1u;
    } else if (gameplay.attack_phase == 8) {
        *clip = LINK_CLIP_REBOUND;
        last = LINK_FRAMES_REBOUND - 1u;
    } else if (gameplay.attack_phase == 9) {
        *clip = LINK_CLIP_GUARD_HIT;
        last = LINK_FRAMES_GUARD_HIT - 1u;
    } else if (gameplay.attack_phase == 1 || gameplay.attack_phase == 6) {
        *clip = attack_rows[r].clip;
        last = attack_rows[r].frames - 1u;
    } else {
        *clip = attack_rows[r].end;
        last = attack_rows[r].end_frames - 1u;
    }
    *frame = gameplay.attack_thirds / 3u;
    if (*frame > last)
        *frame = last;
    return true;
}

void                gameplay_attack_cancel(void)
{
    gameplay.attack_phase = 0;
    gameplay.attack_thirds = 0;
    gameplay.swing = 0;
    gameplay.lunge_pending = false;
    gameplay.lunge_q16 = 0;
    gameplay.charge_q16 = 0;
    gameplay.charge_committed = false;
    gameplay.blade_bounced = false;
    blade_prev_valid = false;
}

/* Acquisition: attention_find (Attention_FindActorInCategory, every filter
** before the winner). Retention: attention_retains. Separate rules. */
static void         feet_of(const gameplay_input_t *in, int32_t feet[3])
{
    feet[0] = in->x;
    feet[1] = in->y;
    feet[2] = in->z;
}

static void         face_actor(int32_t x, int32_t z, const actor_t *a)
{
    int32_t at[3];
    attention_focus(a, at);
    gameplay.face_yaw = gameplay_facing(at[0] - x, at[2] - z);
}

void gameplay_update_facing(int32_t x, int32_t z)
{
    const actor_t *a = actor_resolve(gameplay.target);
    if (gameplay.face_locked && a)
        face_actor(x, z, a);
}

/* L presses toggle the lock. OoT supports Switch and Hold; this slice uses
** a simple Switch-style toggle. L is also the recenter button, and
** demo.c only recenters when no lock was taken or dropped. */
static void         drop_target(void)
{
    if (gameplay.target != ACTOR_HANDLE_NONE)
        gameplay.events |= GP_EVENT_TARGET_OFF;
    gameplay.target = ACTOR_HANDLE_NONE;
    gameplay.face_locked = false;
}

/* HOLD targeting, the setting OoT itself offers as the alternative to Switch.
**
** L held past GP_TARGET_HOLD_STEPS locks onto the nearest actor in front and
** keeps the lock only while it stays held; releasing drops it. A press shorter
** than that is a tap and recentres the camera instead, so brushing L while
** running past a Kokiri no longer grabs them -- which is what made Switch-style
** toggling annoying in the forest.
**
** The lock also drops once the actor is past GP_TARGET_DROP, as before. */
static void         update_target(const gameplay_input_t *in)
{
    int32_t feet[3];
    actor_t *found;
    if (!in->target_held) {
        /* Released. A short press that never became a lock is the recentre
        ** gesture; one that did lock just ends, with no recentre, or the view
        ** would swing away from the actor the player was just looking at. */
        if (gameplay.target_hold > 0 &&
            gameplay.target_hold < GP_TARGET_HOLD_STEPS &&
            gameplay.target == ACTOR_HANDLE_NONE)
            gameplay.events |= GP_EVENT_RECENTER;
        gameplay.target_hold = 0;
        drop_target();
        return;
    }

    if (gameplay.target_hold < GP_TARGET_HOLD_STEPS)
        ++gameplay.target_hold;

    if (gameplay.target_hold < GP_TARGET_HOLD_STEPS) {
        /* Still inside the tap window: nothing is locked yet, so Link keeps
        ** facing wherever he is travelling. */
        gameplay.face_locked = false;
        return;
    }

    feet_of(in, feet);
    if (gameplay.target != ACTOR_HANDLE_NONE) {
        /* A live handle is not enough: the actor must still be targetable
        ** and attention-enabled (a dying Karebaba clears both but lives on
        ** to regrow), and inside its leash. */
        const actor_t *a = actor_resolve(gameplay.target);
        if (!attention_retains(a, feet)) {
            drop_target();
            return;
        }
        face_actor(in->x, in->z, a);
        gameplay.face_locked = true;
        return;
    }

    /* Held long enough and nothing locked yet: try to acquire. Retried every
    ** step while held, so holding L and turning toward an actor picks them up
    ** rather than requiring a fresh press. */
    found = attention_find(feet, in->focus, in->yaw, (const actor_t *)0);
    gameplay.target = actor_handle(found);
    if (found) {
        /* Turn on the acquiring step, not the one after it: a frame of Link
         * still facing his travel heading reads as the lock being ignored. */
        face_actor(in->x, in->z, found);
        if (found->flags & ACTOR_FLAG_HOSTILE)
            gameplay.events2 |= GP2_EVENT_LOCK_HOSTILE;
        gameplay.face_locked = true;
        gameplay.events |= GP_EVENT_TARGET_ON;
    } else {
        gameplay.face_locked = false;
    }
}

/* Cut every uncut tuft inside the live blade's arc. One swing can clear a
** cluster, which is what the original does, but a tuft is only ever cut once
** and a held X cannot re-cut the same one without a new swing. */
/* Sword AT plus the tuft/wonder ACs it can reach, for run_contacts. EnKusa's
** AC cylinder takes the sword's slash bit. Colliders are rebuilt every step,
** so nothing survives to dangle. */
/* The meleeWeaponQuads from the posed blade: capsules along this step's
** blade and along the sweep of its tip and midpoint since the last step.
** All three share the attack id and tag, so a victim still takes one hit. */
static bool         register_blade_quads(void)
{
    int32_t base[3], tip[3], mid[3];
    unsigned int k, n = 1;
    if (!gameplay_blade_points(base, tip))
        return false;
    for (k = 0; k < 3; ++k) mid[k] = (base[k] + tip[k]) / 2;
    if (blade_prev_valid && blade_prev_swing == gameplay.swing_count)
        n = 3;
    for (k = 0; k < n; ++k) {
        collider_t *c = &contacts->blade[k];
        const int32_t *a = k == 0 ? base : k == 1 ? blade_prev_tip : blade_prev_mid;
        const int32_t *b = k == 0 ? tip : k == 1 ? tip : mid;
        c->shape = COLSHAPE_CAPSULE;
        c->actor = 0;
        c->ax = a[0]; c->ay = a[1]; c->az = a[2];
        c->bx = b[0]; c->by = b[1]; c->bz = b[2];
        c->radius = GP_BLADE_RADIUS;
        c->at_type = AT_TYPE_PLAYER;
        c->at_dmg = player_attack_damage_flags(gameplay.attack_id);
        if (player_items_stick()) c->at_dmg = DMG_DEKU_STICK;
        if (!c->at_dmg) c->at_dmg = DMG_SLASH_KOKIRI;
        c->ac_flags = COL_OUTSIDE_ACTOR;        /* Link owns it: AC_HARD bounces */
        c->attack_id = gameplay.swing_count ? gameplay.swing_count : 1;
        c->tag = GP_TAG_BLADE;
        collide_set_at(c);
    }
    for (k = 0; k < 3; ++k) { blade_prev_tip[k] = tip[k]; blade_prev_mid[k] = mid[k]; }
    blade_prev_swing = gameplay.swing_count;
    blade_prev_valid = true;
    return true;
}

static void         register_blade(const gameplay_input_t *in)
{
    unsigned int i;
    collider_t *blade = &contacts->blade[0];
    if (register_blade_quads())
        goto targets;
    blade->shape = COLSHAPE_SECTOR;
    blade->actor = 0;
    blade->x = in->x; blade->y = in->y; blade->z = in->z;
    blade->y_shift = 0;
    blade->radius = GP_SWORD_REACH;
    blade->height = GP_SWORD_HEIGHT;
    blade->yaw = in->yaw;
    /* Spin quads sweep a full turn around Link over the clip; the sector
    ** stand-in for the swept quads covers all 360 degrees. BUG-036. */
    blade->arc = (gameplay.attack_id == ATTACK_SPIN ||
                  gameplay.attack_id == ATTACK_BIG_SPIN) ? 32768 : 16384;
    blade->at_type = AT_TYPE_PLAYER;
    blade->at_dmg = player_attack_damage_flags(gameplay.attack_id);
    if (player_items_stick()) blade->at_dmg = DMG_DEKU_STICK;
    if (!blade->at_dmg) blade->at_dmg = DMG_SLASH_KOKIRI;
    blade->attack_id = gameplay.swing_count ? gameplay.swing_count : 1;
    blade->tag = GP_TAG_BLADE;
    blade->ac_flags = COL_OUTSIDE_ACTOR;
    collide_set_at(blade);
targets:
    for (i = 0; i < KOKIRI_GRASS_COUNT; ++i) {
        const kokiri_prop_t *tuft = &kokiri_grass[i];
        collider_t *c = &contacts->tufts[i];
        if (!in_forest() || in->room != tuft->room || (gameplay.grass_cut & (1u << i)) ||
            oot_core_owns_kokiri_props())
            continue;
        c->shape = COLSHAPE_CYLINDER;
        c->actor = 0;
        c->x = tuft->x; c->y = tuft->y; c->z = tuft->z;
        c->radius = 12; c->height = 44;         /* EnKusa sCylinderInit */
        c->ac_type = AC_TYPE_PLAYER;
        c->ac_bumper = DMG_DEFAULT;
        c->tag = (uint16_t)i;
        collide_set_ac(c);
    }
    /* EnWonderItem_InteractSwitch: radius 20, height 30, rot.z 0 selects
    ** DMG_SLASH | DMG_DEKU_STICK. Tags above the grass range mark them. */
    for (i = 0; i < KOKIRI_WONDER_COUNT; ++i) {
        const kokiri_wonder_t *w = &kokiri_wonders[i];
        collider_t *c = &contacts->wonders[i];
        if (w->mode != 3 || w->room != in->room || w->scene != save_state.scene_id ||
            (gameplay.wonder_done & (1u << i)) || wonder_flagged(w))
            continue;
        c->shape = COLSHAPE_CYLINDER;
        c->actor = 0;
        c->x = w->x; c->y = w->y; c->z = w->z;
        c->radius = 20; c->height = 30;
        c->ac_type = AC_TYPE_PLAYER;
        c->ac_bumper = DMG_SLASH_KOKIRI | DMG_SLASH_MASTER | DMG_SLASH_GIANT |
                       DMG_DEKU_STICK;
        c->tag = (uint16_t)(0x100 + i);
        collide_set_ac(c);
    }
}

/* Link's cylinder (r12, AC 0xFFCFFFFF, AC_TYPE_ENEMY via the player's
** ac type) and, while guarding, the AC_HARD shield (0xDFCFFFFF). The body
** skips hits while intangible, as Player_SetIntangibility does. */
static void         register_link(const gameplay_input_t *in)
{
    collider_t *body = &contacts->link_body, *shield = &contacts->link_shield;
    body->shape = COLSHAPE_CYLINDER;
    body->actor = 0;
    body->x = in->x; body->y = in->y; body->z = in->z;
    body->y_shift = 0;
    body->radius = GP_LINK_BODY_RADIUS;
    body->height = GP_LINK_BODY_HEIGHT;
    body->ac_type = AC_TYPE_ENEMY;
    body->ac_bumper = 0xFFCFFFFFu;
    body->damage_table = 0;
    body->defense = 0;
    body->ac_flags = COL_OUTSIDE_ACTOR;
    body->invincible = gameplay.intangible;
    body->tag = GP_TAG_LINK_BODY;
    collide_set_ac(body);
    if (!gameplay.shielding)
        return;
    {
        int32_t sine, cosine;
        gameplay_sincos(in->yaw, &sine, &cosine);
        shield->shape = COLSHAPE_CYLINDER;
        shield->actor = 0;
        shield->x = in->x + ((GP_SHIELD_FORWARD * sine) >> 16);
        shield->y = in->y;
        shield->z = in->z + ((GP_SHIELD_FORWARD * cosine) >> 16);
        shield->y_shift = 0;
        shield->radius = GP_SHIELD_RADIUS;
        shield->height = GP_SHIELD_HEIGHT;
        shield->ac_type = AC_TYPE_ENEMY;
        shield->ac_bumper = 0xDFCFFFFFu;
        shield->damage_table = 0;
        shield->ac_flags = COL_AC_HARD | COL_OUTSIDE_ACTOR;
        shield->tag = GP_TAG_LINK_SHIELD;
        collide_set_ac(shield);
    }
}

/* The one contact pass per step: begin, register everything, run, consume.
** Runs at the end of gameplay_step, after the boulder moved and before
** demo.c moves Link (pre-movement Link pose, the same step's sword window).
** Consumption: sword results now (grass/wonders are cut on this step, as
** before); Link's body hit and the boulder's AT_HIT next step. */
static void         run_contacts(const gameplay_input_t *in)
{
    unsigned int i;
    collider_t *body, *shield;
    if (!contacts)
        return;
    body = &contacts->link_body;
    shield = &contacts->link_shield;
    /* collide_set_at clears results only when registered. A hopping or
    ** cooling-down boulder skips registration, so its previous AT_HIT must
    ** not be consumed again and restart Link's knockdown indefinitely. The
    ** previous step's hit has already been consumed by update_boulder. */
    contacts->boulder.result = 0;
    collide_begin();
    register_link(in);
    if (blade_live)
        register_blade(in);
    else
        blade_prev_valid = false;
    if (in_forest())
        register_boulder(in);
    register_nut();
    player_items_register();
    dungeon_puzzles_register();
    skulltula_register();
    wall_skull_register();
    dekubaba_register();
    hintnuts_register();
    gohma_larva_register();
    gohma_register();
    karebaba_register();
    world_props_register(contacts->props, 4, in);
    collide_run();
    world_props_collect();
    karebaba_collect();
    skulltula_collect();
    wall_skull_collect();
    dekubaba_collect();
    hintnuts_collect();
    gohma_larva_collect();
    gohma_collect();
    player_items_collect();
    if (blade_live && player_items_stick())
        for (i = 0; i < 3; ++i)
            if (contacts->blade[i].attack_id == gameplay.swing_count &&
                (contacts->blade[i].result & COL_RES_AT_HIT)) {
                player_items_break_stick();
                gameplay_attack_cancel();
                break;
            }
    if (contacts->boulder.result & COL_RES_AT_HIT)
        gameplay.boulder_hit = true;
    if (blade_live)
        for (i = 0; i < 3; ++i)
            if (contacts->blade[i].result & COL_RES_AT_BOUNCED)
                gameplay.blade_bounced = true;
    if (gameplay.shielding && collide_guard_blocked(shield)) {
        gameplay.events |= GP_EVENT_GUARD;      /* the bounce wins */
        gameplay.guard_pending = true;          /* Player_UpdateDamage, next step */
    } else if ((body->result & COL_RES_AC_HIT) && body->ac_hit) {
        int32_t ax = body->ac_hit->x, az = body->ac_hit->z;
        gameplay.hurt_pending = 1;
        gameplay.hurt_damage = body->ac_damage;
        gameplay.hurt_yaw = gameplay_facing(in->x - ax, in->z - az);
    }
    if (!blade_live)
        return;
    for (i = 0; i < collide_event_count(); ++i) {
        unsigned int tuft;
        if (collide_event(i)->at_tag != GP_TAG_BLADE)
            continue;
        tuft = collide_event(i)->ac_tag;
        if (tuft >= 0x100 && tuft - 0x100 < KOKIRI_WONDER_COUNT) {
            if (!(gameplay.wonder_done & (1u << (tuft - 0x100))))
                wonder_pay(tuft - 0x100, false);
            continue;
        }
        if (tuft >= KOKIRI_GRASS_COUNT || (gameplay.grass_cut & (1u << tuft)))
            continue;
        gameplay.grass_cut |= (uint16_t)(1u << tuft);
        /* One source-table roll per tuft, never rerolled by standing/swinging.
         * Tiny slice RNG; source odds, not the original global random stream. */
        world_props_grass_drop(tuft, drop_random());
        gameplay.grass_age[tuft] = 0;
        gameplay.swing_hit = 1;
        ++gameplay.cut_count;
        gameplay.events |= GP_EVENT_CUT;
    }
}

/* func_80837818 + func_80837948: pick the attack from the stick and
** targeting, count repeats of the same one, promote the third to its combo. */
static void         attack_start_id(unsigned int id);
static void         attack_start(const gameplay_input_t *in)
{
    bool targeting = gameplay.face_locked || in->target_held;

    /* Player_Action_80845308 always selects FORWARD_SLASH_1H for a held
     * Deku Stick. It is a one-hand item attack: no directional sword rows,
     * third-hit combo, charge, or spin attack. */
    if (player_items_stick()) {
        attack_start_id(ATTACK_FORWARD);
        gameplay.combo_count = 0;
        gameplay.combo_timer = 0;
        gameplay.charge_ok = false;
        gameplay.lunge_pending = false;
        return;
    }
    attack_start_id(player_attack_select(in->stick_dir, targeting, 0));
    /* D_80854480 forward row is STAB: PLAYER_STATE2_30 even when not
    ** targeting turns it into the forward slash. */
    gameplay.lunge_pending = in->stick_dir == 0;
}

/* func_80837948. */
static void         attack_start_id(unsigned int id)
{
    gameplay.lunge_pending = false;
    if (id != gameplay.attack_id || gameplay.combo_count >= 3)
        gameplay.combo_count = 0;
    ++gameplay.combo_count;
    if (gameplay.combo_count >= 3)
        id += 2;
    gameplay.combo_timer = GP_COMBO_WINDOW_STEPS;
    gameplay.attack_id = (uint8_t)id;
    gameplay.attack_phase = 1;
    gameplay.attack_thirds = 0;
    gameplay.swing = 1;
    gameplay.swing_hit = 0;
    gameplay.charge_ok = true;          /* unk_844 = 8, X held so far */
    ++gameplay.swing_count;
    gameplay.events |= GP_EVENT_SWING;
}

void                gameplay_set_invulnerable(unsigned steps)
{
    if (steps > 255) steps = 255;
    if (gameplay.invulnerable < steps) gameplay.invulnerable = (uint8_t)steps;
}

bool                gameplay_jump_attack_start(void)
{
    if (!(gameplay.equipped & GP_SWORD) || gameplay.shielding)
        return false;
    attack_start_id(ATTACK_JUMP_START);
    gameplay.attack_phase = 6;
    jump_guard = true;
    return true;
}

void                gameplay_jump_attack_land(void)
{
    if (gameplay.attack_phase != 6)
        return;
    gameplay.attack_id = ATTACK_JUMP_START;
    gameplay.combo_count = 0;
    attack_start_id(ATTACK_JUMP_FINISH);
    gameplay.combo_count = 3;
}

/* func_808377DC: start charging off the attack that is ending. */
static void         charge_start(void)
{
    gameplay.charge_from = gameplay.attack_id;
    gameplay.attack_phase = 3;
    gameplay.attack_thirds = GP_CHARGE_START_FRAME * 3u;
    gameplay.charge_q16 = 0;
    gameplay.charge_committed = false;
    gameplay.swing = 1;                 /* holds walk; slow charge walk is TODO */
    gameplay.lunge_q16 = 0;
}

/* Player_Action_80844E68 / func_80844BE4. True when the step is used. */
static bool         update_charge(const gameplay_input_t *in)
{
    if (gameplay.attack_phase == 3) {
        if (gameplay.attack_thirds < (LINK_FRAMES_CHARGE_START - 1u) * 3u)
            gameplay.attack_thirds = (uint16_t)(gameplay.attack_thirds + GP_RECOVER_THIRDS_STEP);
        else {
            gameplay.attack_phase = 4;  /* loop the wait, actionVar2 = -1 */
            gameplay.attack_thirds = 0;
        }
        return true;
    }
    if (gameplay.attack_phase == 4) {
        gameplay.attack_thirds = (uint16_t)(gameplay.attack_thirds + GP_RECOVER_THIRDS_STEP);
        if (!gameplay.charge_committed) {
            gameplay.charge_q16 = (uint16_t)(gameplay.charge_q16 + GP_CHARGE_STEP_Q16);
            if (gameplay.charge_q16 >= GP_CHARGE_COMMIT_Q16) {
                gameplay.charge_committed = true;
                gameplay.combo_count = 0;               /* unk_845 = 0 */
            } else if (!in->attack_held) {
                gameplay.attack_phase = 5;              /* func_80844D68 */
                gameplay.attack_thirds = 0;
                gameplay.swing = 0;
            }
            return true;
        }
        if (!in->attack_held) {
            unsigned int id = gameplay.charge_q16 >= GP_CHARGE_BIG_Q16
                            ? ATTACK_BIG_SPIN : ATTACK_SPIN;
            attack_start_id(id);
            gameplay.lunge_pending = in->stick_dir == 0;
            gameplay.charge_ok = false;
            if (gameplay.intangible < GP_SPIN_INVULN_STEPS)
                gameplay.intangible = GP_SPIN_INVULN_STEPS;
            return true;
        }
        if ((uint32_t)gameplay.charge_q16 + GP_CHARGE_STEP_Q16 < 65536u)
            gameplay.charge_q16 = (uint16_t)(gameplay.charge_q16 + GP_CHARGE_STEP_Q16);
        else
            gameplay.charge_q16 = 65535u;               /* Math_StepToF to 1.0 */
        return true;
    }
    if (gameplay.attack_phase == 5) {
        if (in->moving || in->attack) {
            gameplay_attack_cancel();
            return false;
        }
        if (gameplay.attack_thirds < (LINK_FRAMES_CHARGE_END - 1u) * 3u)
            gameplay.attack_thirds = (uint16_t)(gameplay.attack_thirds + GP_RECOVER_THIRDS_STEP);
        else
            gameplay_attack_cancel();
        return true;
    }
    return false;
}

/* Math_StepToF(&speedXZ, 0, decel): the lunge, wall push and rebounds. */
static void         step_push(void)
{
    int32_t v = gameplay.lunge_q16, d = gameplay.lunge_decel_q16;
    if (!v)
        return;
    if (!d) d = GP_LUNGE_DECEL_Q16;
    if (v > 0) v = v > d ? v - d : 0;
    else       v = -v > d ? v + d : 0;
    gameplay.lunge_q16 = v;
}

/* func_80842DF4, wall half: the blade line from GP_BLADE_BACK behind the
** hilt to the tip, curFrame >= 2, non-spin attacks, speedXZ >= 0. */
static void         blade_wall_check(int32_t decel)
{
    int32_t base[3], tip[3], from[3], len2, len, k;
    unsigned int material;
    if (!blade_live || gameplay.attack_id >= ATTACK_SPIN ||
        gameplay.attack_thirds < 6u || gameplay.lunge_q16 < 0)
        return;
    if (!gameplay_blade_points(base, tip))
        return;
    len2 = 0;
    for (k = 0; k < 3; ++k) len2 += (base[k] - tip[k]) * (base[k] - tip[k]);
    len = (int32_t)collide_isqrt((uint32_t)len2);
    for (k = 0; k < 3; ++k)
        from[k] = len ? tip[k] + (base[k] - tip[k]) * (len + GP_BLADE_BACK) / len : base[k];
    if (!gameplay_blade_wall(from, tip, &material))
        return;
    gameplay.lunge_q16 = GP_WALL_PUSH_Q16;
    gameplay.lunge_decel_q16 = decel;
    gameplay.wall_material = (uint8_t)material;
    gameplay.events |= GP_EVENT_WALL_HIT;
}

/* func_80842D20 (blade AT_BOUNCED) and Player_UpdateDamage's shield bounce
** (Player_Action_808435C4). True while one of them owns the step. */
static bool         update_recoil(const gameplay_input_t *in)
{
    if (gameplay.blade_bounced) {
        gameplay.blade_bounced = false;
        if (gameplay.attack_phase == 7) {
            /* In the guard action: speed only; the stab ends (returns 1). */
            gameplay_attack_cancel();
            gameplay.lunge_q16 = GP_REBOUND_PUSH_Q16;
            gameplay.lunge_decel_q16 = GP_REBOUND_DECEL_Q16;
            gameplay.events |= GP_EVENT_REBOUND;
            return true;
        }
        if ((gameplay.attack_phase == 1 || gameplay.attack_phase == 6) &&
            gameplay.attack_id < ATTACK_SPIN) {
            gameplay.attack_phase = 8;
            gameplay.attack_thirds = 0;
            gameplay.swing = 1;
            gameplay.lunge_pending = false;
            gameplay.lunge_q16 = GP_REBOUND_PUSH_Q16;
            gameplay.lunge_decel_q16 = GP_REBOUND_DECEL_Q16;
            gameplay.events |= GP_EVENT_REBOUND;
            return true;
        }
    }
    if (gameplay.guard_pending) {
        gameplay.guard_pending = false;
        if (gameplay.shielding && gameplay.attack_phase != 8) {
            /* In the guard action: the full-body defense_hit, speedXZ -18. */
            gameplay.attack_phase = 9;
            gameplay.attack_thirds = 0;
            gameplay.swing = 0;                 /* the guard stays up */
            gameplay.lunge_q16 = GP_REBOUND_PUSH_Q16;
            gameplay.lunge_decel_q16 = GP_REBOUND_DECEL_Q16;
            return true;
        }
    }
    if (gameplay.attack_phase == 8) {
        /* Player_Action_808505DC: adjusted speed; idle from curFrame 6. */
        gameplay.attack_thirds = (uint16_t)(gameplay.attack_thirds + GP_ATTACK_THIRDS_STEP);
        if (gameplay.attack_thirds >= GP_REBOUND_END_FRAME * 3u) {
            int32_t keep = gameplay.lunge_q16;
            gameplay_attack_cancel();
            gameplay.lunge_q16 = keep;
        }
        return true;
    }
    if (gameplay.attack_phase == 9) {
        /* Player_Action_808435C4, actionVar1 = 1: speed 1.0; moving after
        ** frame 4 or the clip's end returns to the guard. */
        gameplay.attack_thirds = (uint16_t)(gameplay.attack_thirds + 3u);
        if (!in->shield || (in->moving && gameplay.attack_thirds >= 12u) ||
            gameplay.attack_thirds >= (LINK_FRAMES_GUARD_HIT - 1u) * 3u) {
            int32_t keep = gameplay.lunge_q16;
            gameplay_attack_cancel();
            gameplay.lunge_q16 = keep;
        }
        return true;
    }
    return false;
}

static void         update_sword(const gameplay_input_t *in)
{
    unsigned int r = attack_row(gameplay.attack_id);
    bool can_start = in->attack && !gameplay.shielding;
    /* func_8083C50C: letting go of X while unk_844 > 0 forfeits the charge. */
    if (gameplay.combo_timer && !in->attack_held)
        gameplay.charge_ok = false;
    /* Player_UpdateCommon: unk_844 counts down; at 0 the repeat count clears. */
    if (gameplay.combo_timer && !--gameplay.combo_timer)
        gameplay.combo_count = 0;
    step_push();
    if (update_recoil(in))
        return;
    if (update_charge(in))
        return;
    if (gameplay.attack_phase == 7) {
        /* Player_Action_80843188, actionVar1 = 1: LinkAnimation_Update at
        ** speed 1.0 (one frame a step), the quads on while curFrame < 2; the
        ** clip's end returns to the guard wait. */
        if (gameplay.attack_thirds < (LINK_FRAMES_CROUCH_STAB - 1u) * 3u) {
            gameplay.attack_thirds = (uint16_t)(gameplay.attack_thirds + 3u);
            blade_live = blade_on_frame();
            blade_wall_check(GP_REBOUND_DECEL_Q16);
        } else
            gameplay_attack_cancel();
        return;
    }
    /* func_808428D8: B (X here) while guarding with a sword stabs. */
    if (in->attack && gameplay.shielding && !gameplay.attack_phase &&
        (gameplay.equipped & GP_SWORD)) {
        gameplay.attack_id = ATTACK_STAB;
        gameplay.attack_phase = 7;
        gameplay.attack_thirds = 0;
        gameplay.swing_hit = 0;
        ++gameplay.swing_count;
        gameplay.events |= GP_EVENT_SWING;
        return;
    }
    if (gameplay.attack_phase == 6) {
        /* Player_Action_80844AF4: the clip holds its last frame in the air. */
        blade_live = blade_on_frame();
        blade_wall_check(GP_LUNGE_DECEL_Q16);
        gameplay.attack_thirds = (uint16_t)(gameplay.attack_thirds + GP_ATTACK_THIRDS_STEP);
        return;
    }
    /* The forward lunge belongs to the attack clip only. */
    if (gameplay.lunge_q16 > 0 && gameplay.attack_phase != 1)
        gameplay.lunge_q16 = 0;
    if (gameplay.attack_phase == 1) {
        if (gameplay.lunge_pending && gameplay.attack_thirds == 0) {
            gameplay.lunge_q16 = GP_LUNGE_SPEED_Q16;    /* OnFrame(0) */
            gameplay.lunge_decel_q16 = GP_LUNGE_DECEL_Q16;
            gameplay.lunge_pending = false;
        }
        blade_live = blade_on_frame();
        blade_wall_check(GP_LUNGE_DECEL_Q16);
        /* LinkAnimation_Update reports the end on the clip's last frame. */
        if (gameplay.attack_thirds < (attack_rows[r].frames - 1u) * 3u) {
            gameplay.attack_thirds = (uint16_t)(gameplay.attack_thirds + GP_ATTACK_THIRDS_STEP);
        } else {
            /* Clip done: Player_ActionHandler_7 chains on X, else recovery. */
            if (can_start) {
                attack_start(in);
            } else {
                gameplay.attack_phase = 2;
                gameplay.attack_thirds = 0;
                gameplay.swing = 0;
            }
        }
        return;
    }
    if (gameplay.attack_phase == 2) {
        /* Recovery runs under the idle action: X attacks again, the stick
        ** walks away (both end the recovery clip). */
        /* Player_ActionHandler_8: X still held at unk_844 == 1 charges. */
        if (!player_items_stick() && in->attack_held && gameplay.charge_ok && gameplay.combo_timer == 1 &&
            !gameplay.shielding) {
            charge_start();
            return;
        }
        if (!can_start) {
            if (in->moving) {
                gameplay_attack_cancel();
                return;
            }
            if (gameplay.attack_thirds < (attack_rows[r].end_frames - 1u) * 3u)
                gameplay.attack_thirds = (uint16_t)(gameplay.attack_thirds + GP_RECOVER_THIRDS_STEP);
            else
                gameplay_attack_cancel();
            return;
        }
    } else if (!in->attack) {
        return;
    }
    if (!(gameplay.equipped & GP_SWORD) && !player_items_stick()) {
        /* No sword means no attack, not a substitute action. */
        gameplay.events |= GP_EVENT_DENIED;
        return;
    }
    if (can_start)
        attack_start(in);
}

static void         update_shield(const gameplay_input_t *in)
{
    bool up = in->shield && (gameplay.equipped & GP_SHIELD) != 0 &&
              in->grounded && !gameplay.swing;
    if (in->shield && !(gameplay.equipped & GP_SHIELD))
        gameplay.events |= GP_EVENT_DENIED;
    if (up && !gameplay.shielding)
        gameplay.events |= GP_EVENT_SHIELD_UP;
    gameplay.shielding = up;
}

/* Slot table. Kept beside the menu rather than in the generated actor header:
** these are the slice's two equipment slots, not placement data. */
static const struct { uint8_t item; const char *name; const char *use; }
                    slot_table[GP_SLOT_COUNT] = {
    { GP_SWORD,  "Kokiri Sword", "X: swing" },
    { GP_SHIELD, "Deku Shield",  "Hold R: guard" },
    /* item 0: there is nothing to equip on this row. */
    { 0,         "Save",         "A: save to your file" },
};

uint8_t             gameplay_slot_item(unsigned int slot)
{
    return slot < GP_SLOT_COUNT ? slot_table[slot].item : 0;
}

const char         *gameplay_slot_name(unsigned int slot)
{
    return slot < GP_SLOT_COUNT ? slot_table[slot].name : "";
}

const char         *gameplay_slot_use(unsigned int slot)
{
    return slot < GP_SLOT_COUNT ? slot_table[slot].use : "";
}

bool                gameplay_is_paused(void)
{
    return gameplay.paused;
}

bool                gameplay_blocks_world(void)
{
    return gameplay.paused || gameplay.talking || gohma_cinematic() || gohma_warp_active() ||
           (oot_core_talk() & 1u);
}

/* Four OoT pause pages. Start closes; B opens the save confirmation.
** Only real owned gear can be equipped. Save emits the existing device request. */
static void __attribute__((optimize("Os"))) update_menu(const gameplay_input_t *in)
{
    if (in->pause) {
        gameplay.paused = !gameplay.paused;
        gameplay.pause_window.save_prompt = false;
        gameplay.pause_window.system_confirm = 0;
        gameplay.events |= gameplay.paused ? GP_EVENT_MENU_OPEN
                                           : GP_EVENT_MENU_CLOSE;
        return;
    }
    if (!gameplay.paused)
        return;
    if (in->c_assign && in->c_assign <= 3 && !in->cancel && !in->menu_page &&
        !gameplay.pause_window.save_prompt && !gameplay.pause_window.system_confirm &&
        gameplay.pause_window.page == PAUSE_ITEMS) {
        unsigned cursor = gameplay.pause_window.cursor[PAUSE_ITEMS];
        unsigned item = cursor == 0 && save_state.stick_owned ? 1 :
                        cursor == 6 && save_state.slingshot ? 2 :
                        cursor == 1 && save_state.nut_owned ? 3 : 0;
        if (item) {
            unsigned i;
            for (i = 0; i < 3; ++i)
                if (save_state.c_items[i] == item) save_state.c_items[i] = 0;
            save_state.c_items[in->c_assign - 1] = item;
            gameplay.events |= GP_EVENT_EQUIP;
        } else gameplay.events |= GP_EVENT_DENIED;
        return;
    }
    if (gameplay.pause_window.page == PAUSE_MAP &&
        !gameplay.pause_window.save_prompt && !gameplay.pause_window.system_confirm &&
        !in->menu_page && !in->cancel &&
        (save_state.scene_id == SAVE_SCENE_DEKU_TREE || save_state.scene_id == SAVE_SCENE_DEKU_TREE_BOSS) &&
        (in->menu_dy || in->menu_dx)) {
        int step = in->menu_dy ? in->menu_dy : in->menu_dx;
        gameplay.pause_window.cursor[PAUSE_MAP] =
            (gameplay.pause_window.cursor[PAUSE_MAP] + (step > 0 ? 1 : 4)) % 5;
        gameplay.events |= GP_EVENT_MENU_MOVE;
        return;
    }
    unsigned result = pause_window_step(&gameplay.pause_window,
        in->menu_dx, in->menu_dy, in->menu_page,
        in->cancel, in->interact, gameplay.owned);
    switch (result) {
    case PAUSE_TUNIC_GREEN: case PAUSE_TUNIC_RED: case PAUSE_TUNIC_BLUE:
        gameplay.events |= save_equip_tunic(result==PAUSE_TUNIC_GREEN?0:result==PAUSE_TUNIC_RED?2:1)
            ? GP_EVENT_EQUIP : GP_EVENT_DENIED;
        break;
    case PAUSE_MOVE: gameplay.events |= GP_EVENT_MENU_MOVE; break;
    case PAUSE_WRITE_SAVE: gameplay.events |= GP_EVENT_SAVE; break;
    case PAUSE_LABELS: gameplay.events2 |= GP2_EVENT_LABELS; break;
    case PAUSE_JUMP_BINDING: gameplay.events2 |= GP2_EVENT_JUMP_BINDING; break;
    case PAUSE_RESET_PREFS: gameplay.events2 |= GP2_EVENT_RESET_PREFS; break;
    case PAUSE_LOAD_GAME: gameplay.events2 |= GP2_EVENT_LOAD_MENU; break;
    case PAUSE_RETURN_TITLE: gameplay.events2 |= GP2_EVENT_RETURN_TITLE; break;
    case PAUSE_EQUIP_SWORD:
    case PAUSE_EQUIP_SHIELD:
        gameplay.equipped |= result == PAUSE_EQUIP_SWORD ? GP_SWORD : GP_SHIELD;
        sync_gear_to_save();
        gameplay.events |= GP_EVENT_EQUIP;
        break;
    case PAUSE_DENY: gameplay.events |= GP_EVENT_DENIED; break;
    default: break;
    }

}

bool                gameplay_is_talking(void)
{
    return gameplay.talking;
}

/* Which conversation a speaker owns. Children are matched on ENKO_TYPE -- the
** low 8 bits of the spawn param, exactly as EnKo_GetTextIdChild() reads it --
** so the line each child says is the one the original gives that child. */
static int16_t      convo_for(unsigned int npc)
{
    const kokiri_npc_t *person = &kokiri_npcs[npc];
    unsigned int kind = person->param & 0xFF;
    unsigned int i;
    for (i = 0; i < DIALOGUE_CONVO_COUNT; ++i) {
        if (dialogue_convos[i].speaker != person->kind)
            continue;
        if (person->kind == KOKIRI_NPC_MIDO &&
            dialogue_convos[i].kind != (person->scene == SAVE_SCENE_MIDOS_HOUSE ? 1 : 0)) continue;
        if (person->kind != KOKIRI_NPC_CHILD ||
            dialogue_convos[i].kind == kind)
            return (int16_t)i;
    }
    return -1;
}

/* One extracted guard, evaluated against the save. */
static bool         cond_holds(const dialogue_cond_t *cond)
{
    bool held;

    switch (cond->kind) {
        case DIALOGUE_COND_EVENT:
            held = save_get_event_chk_inf(cond->flag);
            break;
        case DIALOGUE_COND_INFTABLE:
            held = save_get_inf_table(cond->flag);
            break;
        case DIALOGUE_COND_ITEMGET:
            held = save_get_item_get_inf(cond->flag);
            break;
        case DIALOGUE_COND_QUEST:
            held = save_check_quest_item(cond->flag);
            break;
        case DIALOGUE_COND_EQUIP:
            /* CUR_EQUIP_VALUE, not ALL_EQUIP_VALUE: Mido's gate turns on what
            ** is equipped, not what is merely owned. */
            held = (save_cur_equip_value(cond->flag) == cond->value);
            break;
        default:
            return false;
    }
    return (cond->expect ? held : !held);
}

/* The line a speaker actually says right now: the FIRST rule whose conditions
** all hold. That ordering is the whole point -- it is what the original's
** ladder of early returns does, so a later-quest line can never win on a fresh
** file. Returns a dialogue_rules index, or -1 when the speaker has nothing. */
static int16_t      rule_for(unsigned int npc)
{
    int16_t convo = convo_for(npc);
    const dialogue_convo_t *entry;
    unsigned int i, c;

    if (convo < 0)
        return -1;
    entry = &dialogue_convos[convo];
    for (i = 0; i < entry->rules; ++i) {
        const dialogue_rule_t *rule = &dialogue_rules[entry->first_rule + i];
        bool matched = true;
        for (c = 0; c < rule->conds; ++c) {
            if (!cond_holds(&dialogue_conds[rule->first_cond + c])) {
                matched = false;
                break;
            }
        }
        if (matched)
            return (int16_t)(entry->first_rule + i);
    }
    /* Every speaker's list ends in an unconditional rule, so falling out here
    ** means the extracted table is malformed rather than the quest being in an
    ** unexpected state. Say nothing rather than show a wrong line. */
    return -1;
}

static unsigned int source_choice_lines(void);
static unsigned int page_rows(void)
{
    const dialogue_rule_t *rule;
    const dialogue_page_t *page;
    if (!gameplay.talking || gameplay.rule < 0) return 0;
    rule = &dialogue_rules[gameplay.rule];
    if (gameplay.page >= rule->pages) return 0;
    page = &dialogue_pages[rule->first_page + gameplay.page];
    return dialogue_prepare(page->first_line, page->lines, source_choice_lines());
}
bool gameplay_page_more(void)
{
    return page_rows() > (gameplay.page_part + 1u) * DIALOGUE_MAX_LINES;
}
unsigned int gameplay_page_lines(void)
{
    unsigned count = page_rows(), first = gameplay.page_part * DIALOGUE_MAX_LINES;
    if (count <= first) return 0;
    count -= first;
    return count > DIALOGUE_MAX_LINES ? DIALOGUE_MAX_LINES : count;
}
const char *gameplay_page_line(unsigned int line)
{
    if (line >= gameplay_page_lines()) return 0;
    return dialogue_row(gameplay.page_part * DIALOGUE_MAX_LINES + line);
}

const char         *gameplay_speaker_name(void)
{
    if (!gameplay.talking || gameplay.speaker < 0)
        return gameplay.talking ? "" : 0;       /* speakerless text */
    if (kokiri_npcs[gameplay.speaker].kind == KOKIRI_NPC_CHILD) {
        /* OoT's box shows no name. Named cast: Fado (ENKO_TYPE_CHILD_FADO)
        ** and the Know-It-All Brothers (types 7/8/11, their house); the rest
        ** by EnKo sModelInfo body: object_kw1 girls, object_km1 boys. */
        unsigned int type = kokiri_npcs[gameplay.speaker].param & 255;
        if (type == 12) return "Fado";
        if (type == 7 || type == 8 || type == 11) return "Know-It-All Brother";
        return type == 1 || type == 5 || type == 6 || type == 9 || type == 10 ?
               "Kokiri Girl" : "Kokiri Boy";
    }
    return dialogue_speaker_names[kokiri_npcs[gameplay.speaker].kind];
}

/* Who an A press would talk to. A live lock wins, so pressing A while targeted
** always talks to the actor being looked at; otherwise the nearest speaker in
** front within talk range. The OWNER position decides, not the fairy's bob. */
static int16_t      find_speaker(const gameplay_input_t *in)
{
    int32_t best = (int32_t)GP_TALK_RANGE * GP_TALK_RANGE + 1;
    int16_t found = -1;
    unsigned int i;
    /* Only this scene's people (gameplay_npc_present): a Kokiri placed in
    ** another scene must never take A away from a door. */
    if (gameplay_target_npc() >= 0 && gameplay_npc_present((unsigned int)gameplay_target_npc())) {
        const kokiri_npc_t *npc = npc_at(gameplay_target_npc());
        int32_t dy = in->y - npc->y;
        if (dy < 0) dy = -dy;
        if (dy <= GP_TALK_HEIGHT &&
            planar_squared(in->x, in->z, npc->x, npc->z) <=
            (int32_t)GP_TALK_RANGE * GP_TALK_RANGE)
            return (int16_t)gameplay_target_npc();
    }
    for (i = 0; i < KOKIRI_NPC_COUNT; ++i) {
        const kokiri_npc_t *npc;
        int32_t distance, dy, turn;
        if (!gameplay_npc_present(i))
            continue;
        npc = npc_at(i);
        distance = planar_squared(in->x, in->z, npc->x, npc->z);
        dy = in->y - npc->y;
        if (dy < 0) dy = -dy;
        if (dy > GP_TALK_HEIGHT || distance >= best)
            continue;
        turn = yaw_delta(in->yaw, gameplay_facing(npc->x - in->x,
                                                  npc->z - in->z));
        if (turn < 0) turn = -turn;
        if (turn > 16384)
            continue;
        best = distance;
        found = (int16_t)i;
    }
    return found;
}

/* ---- Kokiri Shop (EnOssan / EnGirlA) ---------------------------------------
** Talk: 0x10BA greeting, then the Deku Shield's text 0x009F (the one shelf
** item so far; full eight-item browsing is M3). A there asks 0x0089 with
** TWO_CHOICE. Buy runs EnGirlA_CanBuy_DekuShield in source order: owned ->
** 0x0086; under 40 -> 0x0085; else SUCCESS_FANFARE (not owned, so
** Item_CheckObtainability is ITEM_NONE): debit and grant together, then the
** get-item text 0x004C. Don't buy returns to the item text. */

/* EnOssan Kokiri shopkeeper state machine (z_en_ossan.c) over the shelf of
** sShopkeeperStores[0] and sShopItemEntries (z_en_girla.c). Right shelf is
** slots 0-3, left 4-7; even = bottom row, odd = top. Text is opened by id
** (Message_ContinueTextbox). B ends the exchange wherever the source runs
** EnOssan_TestEndInteraction, and only cancels the buy prompt. */
static const struct {
    uint16_t desc, prompt, get_text, price;
    int8_t   item;          /* save_item_t; -1 = never obtainable here */
} shop_stock[8] = {
    { 0x009F, 0x0089, 0x004C, 40, SAVE_ITEM_SHIELD_DEKU },   /* SI_DEKU_SHIELD */
    { 0x00B2, 0x007F, 0x0034, 15, SAVE_ITEM_DEKU_NUTS_5 },   /* SI_DEKU_NUTS_5 */
    { 0x00A2, 0x0087, 0x0034, 30, SAVE_ITEM_DEKU_NUTS_10 },  /* SI_DEKU_NUTS_10 */
    { 0x00A1, 0x0088, 0x0037, 10, SAVE_ITEM_DEKU_STICK },    /* SI_DEKU_STICK */
    /* No bullet bag / bow yet: EnGirlA_CanBuy_DekuSeeds / _Arrows refuse
    ** (CANT_GET_NOW / CANT_GET_NOW_5), both text 0x86. */
    { 0x00DF, 0x00DE, 0, 30, -1 },                            /* SI_DEKU_SEEDS_30 */
    { 0x00A0, 0x008A, 0, 20, -1 },                            /* SI_ARROWS_10 */
    { 0x00C1, 0x009B, 0, 60, -1 },                            /* SI_ARROWS_30 */
    { 0x00AC, 0x0095, 0, 10, SAVE_ITEM_RECOVERY_HEART },      /* SI_RECOVERY_HEART */
};

static void         shop_text(uint16_t text_id, uint8_t state)
{
    gameplay.shop_state = state;
    gameplay.choice = 0;
    if (!open_system_text(text_id))
        gameplay.talking = false;
}

/* EnOssan_EndInteraction: box closed, locked viewpoint, face angle 0. */
static void         shop_end(void)
{
    gameplay.shop_state = GP_SHOP_NONE;
    gameplay.shop_face = 0;
    gameplay.talking = false;
    gameplay.speaker = -1;
    gameplay.rule = -1;
    gameplay.get_item = 0;
    gameplay.events |= GP_EVENT_TALK_CLOSE;
}

/* EnOssan_StartShopping: facing the shopkeeper, text 0x83. */
static void         shop_facing(void)
{
    shop_text(0x0083, GP_SHOP_FACING);
}

static void         shop_describe(void)
{
    shop_text(shop_stock[gameplay.shop_cursor].desc, GP_SHOP_BROWSE);
}

static void         shop_turn(int8_t target)
{
    gameplay.shop_target = target;
    gameplay.shop_state = GP_SHOP_TURN;
    gameplay.events |= GP_EVENT_MENU_MOVE;          /* NA_SE_SY_CURSOR */
}

/* EnOssan_HandleCanBuyItem, through the shared grant transaction. */
static void __attribute__((optimize("Os"))) shop_buy(void)
{
    unsigned int slot = gameplay.shop_cursor;
    save_canbuy_t result = SAVE_CANBUY_CANT_GET_NOW;
    save_state.rupees = gameplay.rupees;    /* the cache is authoritative here */
    if (shop_stock[slot].item >= 0)
        result = save_item_buy((save_item_t)shop_stock[slot].item, shop_stock[slot].price);
    if (result == SAVE_CANBUY_CANT_GET_NOW || result == SAVE_CANBUY_NEED_RUPEES) {
        shop_text(result == SAVE_CANBUY_CANT_GET_NOW ? 0x0086 : 0x0085, GP_SHOP_RESULT);
        gameplay.events |= GP_EVENT_DENIED;
        return;
    }
    gameplay.rupees = (uint8_t)save_state.rupees;
    if (shop_stock[slot].item == SAVE_ITEM_SHIELD_DEKU)
        gameplay.owned |= GP_SHIELD;
    if (shop_stock[slot].item == SAVE_ITEM_RECOVERY_HEART)
        gameplay.events2 |= GP2_EVENT_HP_RECOVER;
    if (result == SAVE_CANBUY_SUCCESS_FANFARE) {
        /* EnOssan_GiveItemWithFanfare: locked view, Link holds it up. */
        gameplay.events2 |= GP2_EVENT_ITEM_FANFARE;
        shop_text(shop_stock[slot].get_text, GP_SHOP_GET);
        gameplay.get_item_age = 0;
        gameplay.get_item = shop_stock[slot].item == SAVE_ITEM_SHIELD_DEKU ? GP_SHIELD :
            shop_stock[slot].item == SAVE_ITEM_DEKU_STICK ? GP_GET_STICK : GP_GET_NUT;
        gameplay.events |= GP_EVENT_PICKUP;
        return;
    }
    shop_text(0x0084, GP_SHOP_QUICK);               /* quick buy */
}

static void __attribute__((optimize("Os"))) shop_choice(const gameplay_input_t *in)
{
    int next = (int)gameplay.choice + in->menu_dy;
    if (next < 0) next = 0;
    if (next > 1) next = 1;
    if (next == gameplay.choice) return;
    gameplay.choice = (uint8_t)next;
    gameplay.events |= GP_EVENT_MENU_MOVE;
}

/* EnOssan_UpdateJoystickInputState: a push past 30 moves once and starts
** accumulating; the source adds the stick value every 20 Hz frame (x2/3 a
** 30 Hz step), capped at 2000; releasing or reversing resets. */
static void         shop_stick_axis(int value, int16_t *accum, bool *moved)
{
    *moved = false;
    if (*accum == 0) {
        if (value > 30 || value < -30) { *accum = (int16_t)value; *moved = true; }
    } else if (value <= 30 && value >= -30) {
        *accum = 0;
    } else if ((int32_t)*accum * value < 0) {
        *accum = (int16_t)value;
        *moved = true;
    } else {
        int32_t next = *accum + value * 2 / 3;
        if (next > 2000) next = 2000;
        if (next < -2000) next = -2000;
        *accum = (int16_t)next;
    }
}

/* EnOssan_SetCursorIndexFromNeutral, every slot stocked: keep the row. */
static void         shop_enter_shelf(unsigned int offset)
{
    gameplay.shop_cursor = (uint8_t)(offset | (gameplay.shop_cursor & 1));
}

static void __attribute__((optimize("Os"))) shop_browse(const gameplay_input_t *in)
{
    unsigned int cursor = gameplay.shop_cursor, next = cursor;
    bool left_shelf = cursor >= 4;
    unsigned int low = left_shelf ? 4 : 0;
    int ax = gameplay.shop_accum_x, dir = 0;
    if (in->cancel) { shop_end(); return; }
    if (in->interact) {                             /* HasPlayerSelectedItem */
        shop_text(shop_stock[cursor].prompt, GP_SHOP_SELECTED);
        return;
    }
    /* moveHorizontal steps once; a hold past 500 steps every update. */
    if (gameplay.shop_move_x || ax > 500 || ax < -500)
        dir = ax > 0 ? 1 : ax < 0 ? -1 : 0;
    /* Toward the shopkeeper (EnOssan_CursorRight): right on the left shelf,
    ** left on the right one; off the inner edge looks back at him. */
    if ((left_shelf && dir > 0) || (!left_shelf && dir < 0)) {
        if (cursor >= low + 2) next = cursor - 2;
        else { shop_turn(0); return; }
    } else if (dir != 0 && cursor + 2 < low + 4) {
        next = cursor + 2;                          /* EnOssan_CursorLeft */
    }
    /* EnOssan_CursorUpDown: stickAccumY < 0 bottom row, > 0 top row. */
    if (gameplay.shop_accum_y < 0) next &= ~1u;
    else if (gameplay.shop_accum_y > 0) next |= 1u;
    if (next != cursor) {
        gameplay.shop_cursor = (uint8_t)next;
        shop_describe();
        gameplay.events |= GP_EVENT_MENU_MOVE;
    }
}

static void __attribute__((optimize("Os"))) shop_update(const gameplay_input_t *in)
{
    bool moved_y;
    gameplay.prompt = -1;
    shop_stick_axis(in->menu_hold_x, &gameplay.shop_accum_x, &gameplay.shop_move_x);
    shop_stick_axis(in->menu_hold_y, &gameplay.shop_accum_y, &moved_y);
    switch (gameplay.shop_state) {
    case GP_SHOP_HELLO:                             /* 0x9E */
        if (in->cancel) shop_end();
        else if (in->interact) shop_facing();
        break;
    case GP_SHOP_FACING:                            /* 0x83: talk / quit */
        if (in->cancel) { shop_end(); break; }
        shop_choice(in);
        if (in->interact) {
            if (gameplay.choice == 0) shop_text(0x10BA, GP_SHOP_OWNER);
            else shop_end();
        } else if (gameplay.shop_accum_x < 0) {
            shop_enter_shelf(4);                    /* LOOK_SHELF_LEFT: +30 */
            shop_turn(30);
        } else if (gameplay.shop_accum_x > 0) {
            shop_enter_shelf(0);                    /* LOOK_SHELF_RIGHT: -30 */
            shop_turn(-30);
        }
        break;
    case GP_SHOP_OWNER:                             /* EnOssan_TalkKokiriShopkeeper */
        if (in->interact || in->cancel) shop_facing();
        break;
    case GP_SHOP_TURN: {
        /* Math_ApproachF(angle, target, 0.5, 10) at 20 Hz, ~x2/3 a step. */
        int diff = gameplay.shop_target - gameplay.shop_face;
        int step = diff / 2;
        if (step > 7) step = 7;
        if (step < -7) step = -7;
        /* EnOssan_State_LookTo*Shelf zeroes stickAccumX while turning. */
        gameplay.shop_accum_x = 0;
        if (diff >= -1 && diff <= 1) gameplay.shop_face = gameplay.shop_target;
        else gameplay.shop_face = (int8_t)(gameplay.shop_face + step);
        if (gameplay.shop_face == gameplay.shop_target) {
            if (gameplay.shop_target == 0) shop_facing();
            else shop_describe();
        }
        break;
    }
    case GP_SHOP_BROWSE:
        shop_browse(in);
        break;
    case GP_SHOP_SELECTED:                          /* buy / don't buy */
        shop_choice(in);
        if (in->cancel || (in->interact && gameplay.choice == 1)) shop_describe();
        else if (in->interact) shop_buy();
        break;
    case GP_SHOP_RESULT:                            /* EnOssan_State_CantGetItem */
    case GP_SHOP_QUICK:                             /* EnOssan_State_QuickBuyDialog */
        if (in->interact || in->cancel) shop_describe();
        break;
    case GP_SHOP_GET:                               /* EnOssan_State_ItemPurchased */
        if (in->interact || in->cancel) {
            gameplay.get_item = 0;
            shop_text(0x006B, GP_SHOP_CONTINUE);
        }
        break;
    case GP_SHOP_CONTINUE:                          /* 0x6B: continue / quit */
        if (in->cancel) { shop_end(); break; }
        shop_choice(in);
        if (in->interact) {
            if (gameplay.choice == 0) shop_facing();
            else shop_end();
        }
        break;
    default:
        shop_end();
        break;
    }
}

static bool         shop_in_reach(const gameplay_input_t *in)
{
    int32_t dy = in->y - KOKIRI_SHOPKEEPER_Y, turn;
    if (save_state.scene_id != SAVE_SCENE_KOKIRI_SHOP)
        return false;
    if (dy < -GP_TALK_HEIGHT || dy > GP_TALK_HEIGHT)
        return false;
    if (planar_squared(in->x, in->z, KOKIRI_SHOPKEEPER_X, KOKIRI_SHOPKEEPER_Z) >
        (int32_t)GP_SHOP_TALK_RANGE * GP_SHOP_TALK_RANGE)
        return false;
    turn = yaw_delta(in->yaw, gameplay_facing(KOKIRI_SHOPKEEPER_X - in->x,
                                              KOKIRI_SHOPKEEPER_Z - in->z));
    if (turn < 0) turn = -turn;
    return turn <= 16384;
}

static unsigned int source_choice_lines(void)
{
    unsigned int i;
    const dialogue_rule_t *rule;
    if (!gameplay.talking || gameplay.rule < 0)
        return 0;
    rule = &dialogue_rules[gameplay.rule];
    if (gameplay.page + 1u != rule->pages)
        return 0;
    /* By text id: a speaker's own rule for a choice text (En_Ko 0x1038)
    ** shares the count exported with its system entry. */
    for (i = 0; i < DIALOGUE_SYSTEM_COUNT; ++i)
        if (dialogue_system[i].text_id == rule->text_id)
            return dialogue_system[i].choices;
    return 0;
}

unsigned int gameplay_choice_lines(void)
{
    return gameplay_page_more() ? 0 : source_choice_lines();
}

static const dialogue_branch_t *choice_branch(void)
{
    unsigned int i;
    uint16_t text_id = gameplay.rule >= 0 ? dialogue_rules[gameplay.rule].text_id : 0;
    for (i = 0; i < DIALOGUE_BRANCH_COUNT; ++i)
        if (dialogue_branch[i].text_id == text_id)
            return &dialogue_branch[i];
    return 0;
}

/* Message_ContinueTextbox: same box and speaker, next text by id. */
static bool __attribute__((optimize("Os"))) continue_text(uint16_t text_id)
{
    int16_t speaker = gameplay.speaker;
    if (!open_system_text(text_id))
        return false;
    gameplay.speaker = speaker;
    gameplay.events &= ~GP_EVENT_TALK_OPEN;
    gameplay.events |= GP_EVENT_TALK_PAGE;
    gameplay.choice = 0;
    return true;
}

/* End the box. Speaker side effects fire on close, as in the source. */
static void __attribute__((optimize("Os"))) close_talk_as(bool accepted);
static void         close_talk(void)
{
    close_talk_as(true);
}

/* Source EnKo/EnSa TEXT_STATE_CLOSING: remember conversations on close.
 * Only the original actor kind may write a flag; system text cannot. */
static void __attribute__((optimize("Os"))) npc_talk_closed(unsigned int kind, unsigned int text)
{
    static const uint16_t ko[][2] = {
        {0x1005,0x1E},{0x1008,0x22},{0x100A,0x24},{0x100C,0x26},
        {0x100E,0x28},{0x104F,0x59},{0x1053,0x61},{0x1055,0x41},
        {0x1058,0x51},{0x105D,0x47},{0x10D7,0xB7}
    };
    unsigned int i;
    if (kind == KOKIRI_NPC_CHILD) {
        for(i=0;i<sizeof(ko)/sizeof(ko[0]);++i)
            if(ko[i][0]==text) { save_set_inf_table(ko[i][1]); break; }
    } else if(kind == KOKIRI_NPC_SARIA) {
        /* 0x1001 is the greeting cutscene's own text. EnSa_BecomeIdle sets
         * INFTABLE_SARIA_GREETED_LINK when the cutscene ENDS, not when this box
         * closes, so gameplay_saria_greeting_step owns that bit and closing
         * the box here must not set it. */
        if(text==0x1002) save_set_inf_table(INFTABLE_SARIA_NOTICED_FAIRY);
        if(text==0x1031) {
            save_set_event_chk_inf(EVENTCHKINF_SARIA_WAS_TOLD_ABOUT_MIDO);
            save_set_inf_table(INFTABLE_SARIA_WAS_TOLD_ABOUT_MIDO);
        }
        if(text==0x1047) save_set_inf_table(0x05); /* INFTABLE_SARIA_SPOKE_IN_HER_HOUSE */
    }
}

static void __attribute__((optimize("Os"))) close_talk_as(bool accepted)
{
    uint16_t text_id = gameplay.rule >= 0 ? dialogue_rules[gameplay.rule].text_id : 0;
    bool mido = gameplay.speaker >= 0 && gate_mido(gameplay.speaker);
    if (gameplay.speaker >= 0) npc_talk_closed(kokiri_npcs[gameplay.speaker].kind,text_id);
    gameplay.talking = false;
    gameplay.speaker = -1;
    gameplay.rule = -1;
    gameplay.get_item = 0;
    gameplay.events |= GP_EVENT_TALK_CLOSE;
    if (mido)
        mido_talk_closed(text_id);
    (void)accepted;
}

/* One press does one thing. A opens, then advances, then closes on the last
** page; B closes early. The opening press is consumed by the open, so it
** cannot also skip page one, and every transition needs a fresh press edge. */
static void __attribute__((optimize("Os"))) update_talk(const gameplay_input_t *in)
{
    if (gameplay.shop_state) {
        shop_update(in);
        return;
    }
    if (gameplay.talking) {
        const dialogue_rule_t *rule = &dialogue_rules[gameplay.rule];
        gameplay.prompt = -1;
        unsigned int choices = gameplay_choice_lines();
        if (choices) {
            /* Message_HandleChoiceSelection: vertical only, clamped (no wrap);
            ** the cursor sound plays only when it actually moved. */
            const dialogue_branch_t *branch = choice_branch();
            int next = (int)gameplay.choice + in->menu_dy;
            if (next < 0) next = 0;
            if (next > (int)choices - 1) next = (int)choices - 1;
            if (next != gameplay.choice) {
                gameplay.choice = (uint8_t)next;
                gameplay.events |= GP_EVENT_MENU_MOVE;
            }
            if (branch) {
                /* En_Ko: Message_ShouldAdvance (A, B or C-Up) takes the
                ** cursor's choice; there is no cancel option. */
                if ((in->interact || in->cancel || in->c_up) &&
                    branch->next[gameplay.choice] &&
                    !continue_text(branch->next[gameplay.choice]))
                    close_talk();
                return;
            }
            /* A system choice with no branch: A or B closes. */
            if (in->interact || in->cancel)
                close_talk();
            return;
        }
        if (in->cancel) {
            close_talk_as(false);
            return;
        }
        if (!in->interact)
            return;
        if (gameplay_page_more()) {
            ++gameplay.page_part;
            gameplay.events |= GP_EVENT_TALK_PAGE;
            return;
        }
        if (gameplay.page + 1 < rule->pages) {
            gameplay.page_part = 0;
            ++gameplay.page;
            gameplay.events |= GP_EVENT_TALK_PAGE;
            return;
        }
        close_talk();
        return;
    }
    gameplay.shop_prompt = shop_in_reach(in);
    if (gameplay.shop_prompt) {
        gameplay.prompt = -1;
        if (in->interact) {
            /* EnOssan_State_Idle: talk accepted; EnOssan_SetupHelloDialog 0x9E. */
            gameplay.shop_face = 0;
            shop_text(0x009E, GP_SHOP_HELLO);
        }
        return;
    }
    {
        unsigned int sign_text=world_signs_text(in);
        if(sign_text && in->interact) { open_system_text((uint16_t)sign_text);return; }
    }
    gameplay.prompt = find_speaker(in);
    if (!in->interact || gameplay.prompt < 0)
        return;
    gameplay.rule = rule_for((unsigned int)gameplay.prompt);
    if (gameplay.rule < 0)
        return;
    gameplay.speaker = gameplay.prompt;
    gameplay.page = gameplay.page_part = 0;
    gameplay.talking = true;
    gameplay.events |= GP_EVENT_TALK_OPEN;
}

/* Attention_Update: arrow hover (next attention actor, suppressed while
** locked with the stick held back) and Navi's hover, lock first. */
static void         update_attention(const gameplay_input_t *in)
{
    int32_t feet[3];
    actor_t *lock = actor_resolve(gameplay.target), *arrow = (actor_t *)0;
    feet_of(in, feet);
    if (!(lock && in->stick_dir == 2))
        arrow = attention_find(feet, in->focus, in->yaw, lock);
    gameplay.arrow = actor_handle(arrow);
    attention_navi_step(feet, in->focus, lock ? lock : arrow);
}

/* gOverworldNaviQuestHints (elf_message_field.c), the entries the slice
** can reach: !EVENTCHKINF_05 (Deku Tree mouth not opened) -> 0x0140,
** !EVENTCHKINF_09 (Deku Tree not cleared) -> 0x0141. Later entries test
** items, songs and upgrades outside the slice and end at 0x15F, which
** En_Elf treats as no hint. Only Kokiri Forest loads the overworld script
** here (interiors use NAVI_QUEST_HINTS_NONE). */
static uint16_t     navi_quest_hint(void)
{
    if (!in_forest())
        return 0;
    if (!save_get_event_chk_inf(0x05))
        return 0x0140;
    if (!save_get_event_chk_inf(0x09))
        return 0x0141;
    return 0;
}

/* Navi's call and C-Up talk: En_Elf func_80A053F0 (hint pick, naviTimer),
** Player PLAYER_STATE2_21 + Interface_SetNaviCall (0x1D "Hey!" unlocked,
** 0x1E "Hey! Listen!" locked, once per offer), C-Up accepting the talk.
** C-Up with nothing to say is first-person view in the source, not built
** yet (logged), so it does nothing here rather than beep. */
static void         update_navi(const gameplay_input_t *in)
{
    const actor_t *lock = gameplay.face_locked ? actor_resolve(gameplay.target) : (const actor_t *)0;
    uint16_t enemy_text = lock ? lock->navi_text : 0;
    bool offer;
    if (!gameplay.navi_text && !lock &&
        save_state.navi_timer >= GP_NAVI_HINT_FROM &&
        save_state.navi_timer <= GP_NAVI_HINT_TO)
        gameplay.navi_text = navi_quest_hint();
    offer = gameplay.navi_text != 0 || enemy_text != 0;
    if (offer && in->c_up) {
        uint16_t text = enemy_text ? enemy_text : gameplay.navi_text;
        if (open_system_text(text)) {
            gameplay.events2 |= GP2_EVENT_NAVI_TALK;
            if (!enemy_text) {
                /* thisx->textId == QuestHint_GetNaviTextId: read. */
                gameplay.navi_read = true;
                save_state.navi_timer = GP_NAVI_READ;
                gameplay.navi_text = 0;
            }
            offer = false;
        }
    }
    if (offer) {
        if (!gameplay.navi_calling)
            gameplay.events2 |= lock ? GP2_EVENT_NAVI_CALL : GP2_EVENT_NAVI_HELLO;
        gameplay.navi_calling = true;
    } else {
        gameplay.navi_calling = false;          /* Interface_SetNaviCall 0x1F */
    }
    /* EnElf func_80A053F0 increments only in the not-talking branch.
     * Accepting a hint must leave its newly assigned timer at 3001. */
    if (gameplay.talking) return;
    /* naviTimer: one per En_Elf update (20 Hz: two of three steps). */
    gameplay.navi_phase = (uint8_t)(gameplay.navi_phase + 2);
    if (gameplay.navi_phase >= 3) {
        gameplay.navi_phase = (uint8_t)(gameplay.navi_phase - 3);
        if (save_state.navi_timer < GP_NAVI_TIMER_MAX)
            ++save_state.navi_timer;
        else if (!gameplay.navi_read)
            save_state.navi_timer = 0;
    }
}

/* En_Karebaba (karebaba.c): room 1 of the forest. The stick offer needs
** Link free: not charging a spin, not talking, on the ground (Actor_Offer
** GetItem's player-state gate, reduced to the states the slice has). */
static void         update_babas(const gameplay_input_t *in)
{
    uint32_t ev;
    bool free = in->grounded && !gameplay.talking &&
                !(gameplay.attack_phase >= 3 && gameplay.attack_phase <= 5);
    karebaba_sync_scene(save_state.scene_id, in->room);
    skulltula_step(in);
    wall_skull_step(in);
    dekubaba_step(in);
    hintnuts_step(in);
    gohma_larva_step(in);
    gohma_step(in);
    karebaba_update(in->x, in->y, in->z, free);
    ev = karebaba_events();
    gameplay.baba_events = ev;
    /* First stick ever: the get-item show (text 0x0037, GI_DEKU_STICKS_1). */
    if (ev & KAREBABA_EV_STICK_FIRST) gameplay_drop_message(13);
}

void                gameplay_step(const gameplay_input_t *in)
{
    gameplay.events = 0;
    gameplay.events2 = 0;
    gameplay.baba_events = 0;
    /* Dead: the Game Over flow owns the pad (demo.c steps game_over). */
    if (gameplay.dead)
        return;
    /* A lethal landing outranks new conversations, props and pause input. */
    if (!gameplay.paused) check_death(in);
    if (gameplay.dead) return;
    /* Saria's greeting takes the scene before the pad does: while it runs
    ** nothing else in the world steps, the way a cutscene owns the frame in
    ** the source. It starts itself on the first forest step of a fresh file. */
    if (gameplay_saria_greeting_step())
        return;
    if(gohma_cinematic() || gohma_warp_active()) {gohma_step(in);gameplay_attack_cancel();gameplay.shielding=false;return;}
    /* Pause outranks everything, including an open text box: Start freezes the
    ** world wherever it is. Nothing below runs while the menu is up, so no
    ** menu press can reach a swing, a jump, a talk or the walk/run toggle. */
    if (gameplay.paused || in->pause) {
        update_menu(in);
        if (gameplay.paused) {
            gameplay.shielding = false;
            gameplay.prompt = -1;
            return;
        }
        /* Closed this step: the same press must not also act on the world. */
        return;
    }
    /* A conversation owns the input. Nothing else in the world advances from
    ** the pad while a box is open -- no pickup grab, no lock change, no swing,
    ** no guard -- so a held button cannot leak an action through the box. */
    update_exit_blocker(in);
    sync_npc_actors();
    if (gameplay.talking) {
        if (gameplay.get_item && gameplay.get_item_age < 65535) ++gameplay.get_item_age;
        update_talk(in);
        update_attention(in);
        gameplay.shielding = false;
        return;
    }
    world_props_step(in);
    if (gameplay.talking) return;
    collect_rupees(in);
    if (!oot_core_owns_kokiri_npcs()) update_wonders(in);   /* else En_Wonder_Item */
    if(gameplay.hurt_flash_timer){
        unsigned rate=50-gameplay.hurt_flash_timer*2/3;
        if(rate<8)rate=8;if(rate>40)rate=40;
        gameplay.hurt_flash_phase+=(rate*256*2)/3;--gameplay.hurt_flash_timer;
    }
    if (gameplay.intangible)
        --gameplay.intangible;
    if (gameplay.invulnerable)
        --gameplay.invulnerable;
    if (jump_guard) {
        /* Human rule: untouchable through the airborne slash, then one more
         * second once it ends (landing cut, rebound or cancel). */
        if (gameplay.attack_phase == 6) {
            if (gameplay.intangible < 2) gameplay.intangible = 2;
        } else {
            jump_guard = false;
            if (gameplay.intangible < GP_JUMP_ATTACK_GUARD_STEPS)
                gameplay.intangible = GP_JUMP_ATTACK_GUARD_STEPS;
        }
    }
    consume_link_damage(in);
    check_death(in);
    if (gameplay.dead)
        return;
    /* HealthMeter beat: NA_SE_SY_HITPOINT_ALARM each bottom, ~20 frames. */
    if (health_critical()) {
        if (++gameplay.alarm_steps >= 30) {
            gameplay.alarm_steps = 0;
            gameplay.events2 |= GP2_EVENT_ALARM;
        }
    } else {
        gameplay.alarm_steps = 0;
    }
    update_boulder(in);
    update_nut(in);
    if (in_forest())
        update_mido(in);
    update_target(in);
    update_attention(in);
    update_navi(in);
    update_babas(in);
    if (gameplay.talking || gohma_cinematic() || gohma_warp_active()) {
        gameplay.shielding = false;
        return;
    }
    if (!world_props_carrying() && update_chest(in)) {
        gameplay.shielding = false;
        return;
    }
    if (world_props_interact(in)) {
        gameplay_attack_cancel();gameplay.shielding=false;run_contacts(in);return;
    }
    update_talk(in);
    if (gameplay.talking) {
        /* Opened this step: drop anything the same frame would have started. */
        gameplay.shielding = false;
        return;
    }
    (void)drop_random(); /* vary outcomes with play timing, even before a cut */
    player_items_step();
    if (in->c_use && in->c_use <= 3 && in->grounded &&
        !world_props_carrying() && !gameplay.attack_phase && !in->shield) {
        unsigned item = save_state.c_items[in->c_use - 1];
        uint16_t yaw = in->yaw;
        int16_t pitch = in->item_pitch;
        actor_t *target = actor_resolve(gameplay.target);
        if (item == PLAYER_ITEM_SEED && in->target_held && target) {
            int32_t focus[3], dx, dz, distance;
            attention_focus(target, focus);
            dx = focus[0]-in->x; dz = focus[2]-in->z;
            distance = (int32_t)collide_isqrt((uint32_t)(dx*dx+dz*dz));
            yaw = gameplay_facing(dx,dz);
            pitch = (int16_t)gameplay_facing(focus[1]-(in->y+35),distance>12?distance-12:1);
        }
        if (!(in->item_from_eye && item == PLAYER_ITEM_SEED ?
                player_items_use_from(item, in->item_eye, yaw, pitch) :
                player_items_use(item, in->x, in->y, in->z, yaw, pitch)))
            gameplay.events |= GP_EVENT_DENIED;
    }
    /* Player_ProcessItemButtons: B carries the sword, so a B tap while a stick
     * is held lowers the stick and returns to the sword (no stick swing). */
    if (in->cancel && !in->c_use && player_items_stick() && !gameplay.attack_phase)
        player_items_putaway();
    blade_live = false;
    if (in->c_use && in->c_use <= 3 && save_state.c_items[in->c_use - 1] == 1 &&
        player_items_stick() && in->grounded && !world_props_carrying()) {
        /* Player_InitDekuStickIA holds the stick after C use. It does not
         * force a slash: the burning tip can simply touch a torch. */
        update_sword(in);
    } else {
        /* X swings a held stick. A sword attack puts a non-stick item away. */
        if (in->attack && !gameplay.attack_phase && !player_items_stick()) player_items_putaway();
        update_sword(in);
    }
    update_shield(in);
    run_contacts(in);
}
