#include "gameplay.h"
#include "kokiri_actors.h"
#include "kokiri_dialogue.h"
#include "dialogue_text.h"
#include "save_state.h"
#include "collide.h"
#include "actor_sys.h"
#include "attention.h"
#include "karebaba.h"
#include "game_over.h"
#include "player_attack.h"
#include "link_clips.h"

gameplay_t          gameplay;
/* Contact colliders (run_contacts: sword, grass, Link, boulder), kept off work RAM. */
typedef struct {
    collider_t blade[3], tufts[KOKIRI_GRASS_COUNT], wonders[KOKIRI_WONDER_COUNT];
    collider_t link_body, link_shield, boulder, nut;
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

static void         sync_gear_to_save(void);
static void         sync_gear_from_save(void);
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

/* Speaker placement with Mido's live position swapped in. */
static kokiri_npc_t mido_live;

static const kokiri_npc_t *npc_at(int npc)
{
    if (kokiri_npcs[npc].kind == KOKIRI_NPC_MIDO) {
        mido_live = kokiri_npcs[npc];
        mido_live.x = (int16_t)gameplay.mido_x;
        mido_live.z = (int16_t)gameplay.mido_z;
        return &mido_live;
    }
    return &kokiri_npcs[npc];
}

/* Kokiri NPCs as registry actors, so Link's lock and Navi share one
** identity (M2d). Drawing and talking stay on kokiri_npcs; each step copies
** the live position (Mido's included) onto the actor. Focus: a head-height
** stand-in above the feet; arrow: Actor_Init lockOnArrowOffset 2000 x 0.01.
** Source per-NPC attentionRangeType is a logged gap (ATTN_RANGE_SLICE_NPC). */
#define GP_NPC_FOCUS_Y  40
#define GP_NPC_ARROW_Y  20
#define GP_NPC_ACTOR_ID 0xF001
static const actor_profile_t npc_profile = {
    GP_NPC_ACTOR_ID, ACTORCAT_NPC, ACTOR_FLAG_TARGETABLE, 0, 0, 0, 0
};
static actor_handle_t npc_actor[KOKIRI_NPC_COUNT];

static void         npc_actors_kill(void)
{
    unsigned int i;
    for (i = 0; i < KOKIRI_NPC_COUNT; ++i) {
        actor_kill(actor_resolve(npc_actor[i]));
        npc_actor[i] = ACTOR_HANDLE_NONE;
    }
}

static void         sync_npc_actors(void)
{
    unsigned int i;
    if (!in_forest()) {
        npc_actors_kill();
        return;
    }
    for (i = 0; i < KOKIRI_NPC_COUNT; ++i) {
        const kokiri_npc_t *npc = npc_at(i);
        actor_t *a = actor_resolve(npc_actor[i]);
        if (!a) {
            a = actor_spawn(&npc_profile, save_state.scene_id, ACTOR_ROOM_NONE,
                            npc->x, npc->y, npc->z, 0, (uint16_t)i);
            if (!a)
                continue;                   /* pool full: this one untargetable */
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
    return in_forest();
}

int32_t             gameplay_npc_x(unsigned int npc)
{
    return npc < KOKIRI_NPC_COUNT ? npc_at((int)npc)->x : 0;
}

int32_t             gameplay_npc_z(unsigned int npc)
{
    return npc < KOKIRI_NPC_COUNT ? npc_at((int)npc)->z : 0;
}

static void         mido_place(void)
{
    if (save_get_event_chk_inf(EVENTCHKINF_MIDO_STOOD_ASIDE_KOKIRI)) {
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

#define STEPS_OF(frames) (((frames) * 3 + 1) / 2)    /* 20 Hz frames -> steps */

/* The one damage entry: enemy contact, fall and void all come through here
** (Health_ChangeBy via Player_InflictDamage / func_80837B18). */
static void         link_damage(unsigned int units)
{
    save_damage(units);
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
    link_damage(gameplay.hurt_damage);
    gameplay.intangible = GP_INTANGIBLE_STEPS;
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
    if (!in_forest() || room != MIDO_ROOM)
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
    } else if (text_id == 0x1033 && gameplay.mido_state == 0) {
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
        gameplay.page = 0;
        gameplay.talking = true;
        gameplay.events |= GP_EVENT_TALK_OPEN;
        return true;
    }
    return false;
}

/* ---- En_Box (z_en_box.c) --------------------------------------------------- */

#define CHEST_FLAG(c)   ((c)->param & 0x1F)

bool                gameplay_chest_opened(unsigned int index)
{
    return index < KOKIRI_CHEST_COUNT &&
           save_get_treasure(save_state.scene_id, CHEST_FLAG(&kokiri_chests[index]));
}

/* EnBox_WaitOpen: Link in the chest's own frame at -50 < z < 0, |x| < 20,
** |y| < 10, and Player_IsFacingActor(0x3000). A then opens it: the treasure
** flag is set during the opening and GI_SWORD_KOKIRI is granted OWNED only
** (Item_Give, z_parameter.c) -- equipping is the pause screen's job. */
static int16_t      chest_in_reach(const gameplay_input_t *in)
{
    unsigned int i;
    if (!in_forest())
        return -1;
    for (i = 0; i < KOKIRI_CHEST_COUNT; ++i) {
        const kokiri_chest_t *c = &kokiri_chests[i];
        int32_t dx = in->x - c->x, dy = in->y - c->y, dz = in->z - c->z;
        int32_t sine, cosine, lx, lz, turn;
        if (in->room != c->room || gameplay_chest_opened(i))
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

static bool         update_chest(const gameplay_input_t *in)
{
    const kokiri_chest_t *c;
    gameplay.chest_prompt = chest_in_reach(in);
    if (gameplay.chest_prompt < 0 || !in->interact)
        return false;
    c = &kokiri_chests[gameplay.chest_prompt];
    save_set_treasure(save_state.scene_id, CHEST_FLAG(c));
    gameplay.owned |= GP_SWORD;
    sync_gear_to_save();
    gameplay.chest_prompt = -1;
    gameplay.get_item = GP_SWORD;
    gameplay.events |= GP_EVENT_PICKUP;
    open_system_text(0x00A4);
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

void                gameplay_reset(void)
{
    unsigned int i;
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
    gameplay.choice = 0;
    boulder_reset();
    gameplay.boulder_live = false;
    gameplay.intangible = 0;
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
    gameplay.page = 0;
    gameplay.talking = false;
    gameplay.paused = false;
    gameplay.cursor = GP_SLOT_SWORD;
    gameplay.pause_window = (pause_window_state_t){ .page = PAUSE_EQUIPMENT, .cursor = {0, 0, 18, 1} };
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
    unsigned int total = gameplay.rupees + value;
    gameplay.rupees = total > GP_WALLET_CAPACITY ? GP_WALLET_CAPACITY : total;
    /* The wallet is saved state: the Deku Shield costs 40 rupees, so losing
    ** the count on a reload would undo real progress. */
    save_state.rupees = gameplay.rupees;
    gameplay.events |= GP_EVENT_RUPEE;
}

static void collect_rupees(const gameplay_input_t *in)
{
    unsigned int i;
    for (i = 0; i < KOKIRI_RUPEE_COUNT; ++i) {
        const kokiri_rupee_t *r = &kokiri_rupees[i];
        if (!gameplay_rupee_taken(i) && rupee_near(in, r->x, r->y, r->z, r->room)) {
            gameplay.rupee_taken |= (uint16_t)(1u << i);
            /* Per-scene collectible flag, where OoT keeps them, so a rupee
            ** already picked up does not reappear after a save and reload. */
            save_set_collectible(save_state.scene_id, i);
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
static void         sync_gear_to_save(void)
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

static void         sync_gear_from_save(void)
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
        if (save_get_collectible(save_state.scene_id, i))
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
    if (!blade->at_dmg) blade->at_dmg = DMG_SLASH_KOKIRI;
    blade->attack_id = gameplay.swing_count ? gameplay.swing_count : 1;
    blade->tag = GP_TAG_BLADE;
    blade->ac_flags = COL_OUTSIDE_ACTOR;
    collide_set_at(blade);
targets:
    for (i = 0; i < KOKIRI_GRASS_COUNT; ++i) {
        const kokiri_prop_t *tuft = &kokiri_grass[i];
        collider_t *c = &contacts->tufts[i];
        if (in->room != tuft->room || (gameplay.grass_cut & (1u << i)))
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
    karebaba_register();
    collide_run();
    karebaba_collect();
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
        gameplay.grass_rupee[tuft] =
            kokiri_grass_rupees[tuft][drop_random() & 15];
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

bool                gameplay_jump_attack_start(void)
{
    if (!(gameplay.equipped & GP_SWORD) || gameplay.shielding)
        return false;
    attack_start_id(ATTACK_JUMP_START);
    gameplay.attack_phase = 6;
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
        if (in->attack_held && gameplay.charge_ok && gameplay.combo_timer == 1 &&
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
    if (!(gameplay.equipped & GP_SWORD)) {
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
    return gameplay.paused || gameplay.talking;
}

/* Four OoT pause pages. Start closes; B opens the save confirmation.
** Only real owned gear can be equipped. Save emits the existing device request. */
static void         update_menu(const gameplay_input_t *in)
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
    unsigned result = pause_window_step(&gameplay.pause_window,
        in->menu_dx, in->menu_dy, in->menu_page,
        in->cancel, in->interact, gameplay.owned);
    switch (result) {
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

unsigned int        gameplay_page_lines(void)
{
    const dialogue_rule_t *rule;
    if (!gameplay.talking || gameplay.rule < 0)
        return 0;
    rule = &dialogue_rules[gameplay.rule];
    if (gameplay.page >= rule->pages)
        return 0;
    return dialogue_pages[rule->first_page + gameplay.page].lines;
}

const char         *gameplay_page_line(unsigned int line)
{
    const dialogue_rule_t *rule;
    const dialogue_page_t *page;
    if (line >= gameplay_page_lines())
        return 0;
    rule = &dialogue_rules[gameplay.rule];
    page = &dialogue_pages[rule->first_page + gameplay.page];
    return dialogue_line(page->first_line + line);
}

const char         *gameplay_speaker_name(void)
{
    if (!gameplay.talking || gameplay.speaker < 0)
        return gameplay.talking ? "" : 0;       /* speakerless text */
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
    /* Forest actors only: inside Link's house a Kokiri standing outside the
    ** wall must not take A away from the door. */
    if (!in_forest())
        return -1;
    if (gameplay_target_npc() >= 0) {
        const kokiri_npc_t *npc = npc_at(gameplay_target_npc());
        int32_t dy = in->y - npc->y;
        if (dy < 0) dy = -dy;
        if (dy <= GP_TALK_HEIGHT &&
            planar_squared(in->x, in->z, npc->x, npc->z) <=
            (int32_t)GP_TALK_RANGE * GP_TALK_RANGE)
            return (int16_t)gameplay_target_npc();
    }
    for (i = 0; i < KOKIRI_NPC_COUNT; ++i) {
        const kokiri_npc_t *npc = npc_at(i);
        int32_t distance = planar_squared(in->x, in->z, npc->x, npc->z);
        int32_t dy = in->y - npc->y, turn;
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

static bool         shop_open(uint16_t text_id, uint8_t state)
{
    if (!open_system_text(text_id))
        return false;
    gameplay.shop_state = state;
    gameplay.choice = 0;
    return true;
}

static void         shop_buy(void)
{
    if (gameplay.owned & GP_SHIELD) {
        shop_open(0x0086, 4);
        gameplay.events |= GP_EVENT_DENIED;
        return;
    }
    if (gameplay.rupees < GP_SHIELD_PRICE) {
        shop_open(0x0085, 4);
        gameplay.events |= GP_EVENT_DENIED;
        return;
    }
    gameplay.rupees = (uint8_t)(gameplay.rupees - GP_SHIELD_PRICE);
    gameplay.owned |= GP_SHIELD;
    sync_gear_to_save();                /* wallet and shield in one write */
    shop_open(0x004C, 4);
    gameplay.get_item = GP_SHIELD;
    gameplay.events |= GP_EVENT_PICKUP;
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

unsigned int        gameplay_choice_lines(void)
{
    unsigned int i;
    const dialogue_rule_t *rule;
    if (!gameplay.talking || gameplay.rule < 0)
        return 0;
    rule = &dialogue_rules[gameplay.rule];
    if (gameplay.page + 1u != rule->pages)
        return 0;
    for (i = 0; i < DIALOGUE_SYSTEM_COUNT; ++i)
        if (dialogue_system[i].rule == (uint16_t)gameplay.rule)
            return dialogue_system[i].choices;
    return 0;
}

/* After a shop box closes: what the exchange opens next. */
static void         shop_next(bool accepted)
{
    uint8_t state = gameplay.shop_state;
    gameplay.shop_state = 0;
    if (state == 1 && accepted)
        shop_open(0x009F, 2);
    else if (state == 2 && accepted)
        shop_open(0x0089, 3);
}

/* End the box. Speaker side effects fire on close, as in the source. */
static void         close_talk_as(bool accepted);
static void         close_talk(void)
{
    close_talk_as(true);
}

static void         close_talk_as(bool accepted)
{
    uint16_t text_id = gameplay.rule >= 0 ? dialogue_rules[gameplay.rule].text_id : 0;
    bool mido = gameplay.speaker >= 0 &&
                kokiri_npcs[gameplay.speaker].kind == KOKIRI_NPC_MIDO;
    gameplay.talking = false;
    gameplay.speaker = -1;
    gameplay.rule = -1;
    gameplay.get_item = 0;
    gameplay.events |= GP_EVENT_TALK_CLOSE;
    if (mido)
        mido_talk_closed(text_id);
    if (gameplay.shop_state)
        shop_next(accepted);
}

/* One press does one thing. A opens, then advances, then closes on the last
** page; B closes early. The opening press is consumed by the open, so it
** cannot also skip page one, and every transition needs a fresh press edge. */
static void         update_talk(const gameplay_input_t *in)
{
    if (gameplay.talking) {
        const dialogue_rule_t *rule = &dialogue_rules[gameplay.rule];
        gameplay.prompt = -1;
        if (gameplay_choice_lines()) {
            /* TWO_CHOICE: D-pad moves, A picks, B is the second option. */
            if (in->menu_step) {
                gameplay.choice ^= 1;
                gameplay.events |= GP_EVENT_MENU_MOVE;
            }
            if (in->interact || in->cancel) {
                bool buy = in->interact && gameplay.choice == 0;
                gameplay.shop_state = 0;
                close_talk();
                if (buy)
                    shop_buy();
                else
                    shop_open(0x009F, 2);   /* back to the item text */
            }
            return;
        }
        if (in->cancel) {
            close_talk_as(false);
            return;
        }
        if (!in->interact)
            return;
        if (gameplay.page + 1 < rule->pages) {
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
        if (in->interact)
            shop_open(0x10BA, 1);
        return;
    }
    gameplay.prompt = find_speaker(in);
    if (!in->interact || gameplay.prompt < 0)
        return;
    gameplay.rule = rule_for((unsigned int)gameplay.prompt);
    if (gameplay.rule < 0)
        return;
    gameplay.speaker = gameplay.prompt;
    gameplay.page = 0;
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
    karebaba_sync(in_forest(), in->room);
    karebaba_update(in->x, in->y, in->z, free);
    ev = karebaba_events();
    /* First stick ever: the get-item show (text 0x0037, GI_DEKU_STICKS_1). */
    if ((ev & KAREBABA_EV_STICK_FIRST) && open_system_text(0x0037))
        gameplay.events |= GP_EVENT_PICKUP;
}

void                gameplay_step(const gameplay_input_t *in)
{
    gameplay.events = 0;
    gameplay.events2 = 0;
    /* Dead: the Game Over flow owns the pad (demo.c steps game_over). */
    if (gameplay.dead)
        return;
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
    sync_npc_actors();
    if (gameplay.talking) {
        update_talk(in);
        update_attention(in);
        gameplay.shielding = false;
        return;
    }
    collect_rupees(in);
    update_wonders(in);
    if (gameplay.intangible)
        --gameplay.intangible;
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
    if (gameplay.talking) {
        gameplay.shielding = false;
        return;
    }
    if (update_chest(in)) {
        gameplay.shielding = false;
        return;
    }
    update_talk(in);
    if (gameplay.talking) {
        /* Opened this step: drop anything the same frame would have started. */
        gameplay.shielding = false;
        return;
    }
    (void)drop_random(); /* vary outcomes with play timing, even before a cut */
    blade_live = false;
    update_sword(in);
    update_shield(in);
    run_contacts(in);
}
