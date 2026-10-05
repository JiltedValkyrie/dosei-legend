#pragma GCC optimize("Os") /* actor/state logic, not draw loops: size over speed (work RAM) */
/* En_Karebaba: see karebaba.h. Source: ovl_En_Karebaba/z_en_karebaba.c. */
#include "karebaba.h"
#include "gameplay.h"           /* gameplay_sincos, gameplay_facing */
#include "save_state.h"
#include "kokiri_actors.h"

#define Q8(v)           ((int32_t)((v) * 256))
#define SCALE_IDLE      100     /* 0.005 */
#define SCALE_UP        200     /* 0.01 */
#define SCALE_DROP      600     /* 0.03 */
#define SCALE_STEP      10      /* 0.0005 */
#define ANIM_FRAMES     24      /* gDekuBabaFastChompAnim */
#define NAVI_TEXT       0x0609  /* NAVI_ENEMY_WITHERED_DEKU_BABA + 0x600 */
#define KAREBABA_ID     KAREBABA_ACTOR_ID

static karebaba_t  *babas;             /* KAREBABA_MAX, cart */
static unsigned int count;
static uint32_t     events;
static unsigned live_scene=255,live_room=255;
/* US 1.2 ydan child-day En_Karebaba params 1, same source drop/regrowth. */
static const kokiri_prop_t dungeon_babas[]={
    {-546,-820,392,3},{-2038,-760,1252,6},{-1674,-760,1248,6},
    {-2174,-760,295,7},{-1472,840,-157,10}
};

/* DamageTable_Get(1) is not consulted: any accepted AC hit kills (health 1,
** the action checks AC_HIT). DMG_SWORD = SLASH (8-10) | SPIN (22-24) |
** JUMP (25-27); a child masks DMG_JUMP_MASTER (27). */
#define DMG_SWORD_CHILD (DMG_SLASH_KOKIRI | DMG_SLASH_MASTER | DMG_SLASH_GIANT | \
                         DMG_SPIN_KOKIRI | (1u << 23) | (1u << 24) | \
                         DMG_JUMP_KOKIRI | (1u << 26))
#define DMG_UPRIGHT     (DMG_SWORD_CHILD | DMG_BOOMERANG)

static const actor_profile_t profile = {
    KAREBABA_ID, ACTORCAT_ENEMY, ACTOR_FLAG_TARGETABLE | ACTOR_FLAG_HOSTILE, 0, 0, 0, 0
};

static int32_t  sin_q16(uint16_t a) { int32_t s, c; gameplay_sincos(a, &s, &c); return s; }
static int32_t  cos_q16(uint16_t a) { int32_t s, c; gameplay_sincos(a, &s, &c); return c; }

static bool     step_to(int32_t *v, int32_t target, int32_t rate)
{
    if (*v < target) { *v += rate; if (*v > target) *v = target; }
    else if (*v > target) { *v -= rate; if (*v < target) *v = target; }
    return *v == target;
}

static void     reset_collider(karebaba_t *b)
{
    /* EnKarebaba_ResetCollider */
    b->body.radius = 7;
    b->body.height = 25;
    b->body.ac_flags |= COL_AC_HARD;
    b->body.ac_bumper = DMG_DEFAULT;
    b->head.height = 25;
}

static void     setup_idle(karebaba_t *b)
{
    b->scale = SCALE_IDLE;
    b->rot_x = 0xC000;                  /* -0x4000 */
    b->action = KAREBABA_IDLE;
    b->pos_q8[1] = (b->home[1] + 14) * 256;
}

static void     setup_upright(karebaba_t *b)
{
    if (b->action != KAREBABA_SPIN) {
        b->scale = SCALE_UP;
        b->body.ac_flags &= ~COL_AC_HARD;       /* COL_MATERIAL_HIT6 */
        b->body.ac_bumper = DMG_UPRIGHT;
        b->body.radius = 15;
        b->body.height = 80;
        b->head.height = 80;
    }
    b->timer = 40;
    b->action = KAREBABA_UPRIGHT;
}

static void     setup_dying(karebaba_t *b)
{
    b->timer = 0;
    b->vel_y_q8 = Q8(4);
    b->move_yaw = (uint16_t)(b->rot_y + 0x8000);
    b->speed_q8 = Q8(3);
    b->action = KAREBABA_DYING;
    events |= KAREBABA_EV_DEAD | KAREBABA_EV_LAST_DAMAGE;
}

static void     setup_dead(karebaba_t *b)
{
    b->frame_q8 = 0;
    b->frame_speed_q8 = 0;
    reset_collider(b);
    b->rot_x = 0xC000;
    b->timer = 200;
    b->picked = 0;
    b->pos_q8[0] = b->home[0] * 256;
    b->pos_q8[1] = b->home[1] * 256;
    b->pos_q8[2] = b->home[2] * 256;
    b->action = KAREBABA_DEAD;
}

static void     grow_step(karebaba_t *b)
{
    /* Grow / Regrow: params++, scale 0.005 * params * 0.05, y home + 14 x. */
    ++b->timer;
    b->scale = (int16_t)(5 * b->timer);
    b->pos_q8[1] = b->home[1] * 256 + 14 * 256 * b->timer / 20;
}

/* SkelAnime_Update for the loop (Awaken/Upright/Spin) and once (Retract). */
static void     anim_update(karebaba_t *b, bool loop)
{
    int32_t f = b->frame_q8 + b->frame_speed_q8;
    if (loop) {
        while (f >= ANIM_FRAMES * 256) f -= ANIM_FRAMES * 256;
        while (f < 0) f += ANIM_FRAMES * 256;
    } else if (f < 0) {
        f = 0;
    } else if (f > (ANIM_FRAMES - 1) * 256) {
        f = (ANIM_FRAMES - 1) * 256;
    }
    b->frame_q8 = (int16_t)f;
}

/* Animation_OnFrame(0) || OnFrame(12): the 4.0 speed lands on them exactly. */
static void     mouth_sound(const karebaba_t *b)
{
    if (b->frame_q8 == 0 || b->frame_q8 == 12 * 256)
        events |= KAREBABA_EV_MOUTH;
}

static bool     body_hit(const karebaba_t *b)
{
    return b->hit;
}

static void     item_give_stick(void)
{
    save_item_give(SAVE_ITEM_DEKU_STICK);   /* Item_Give(ITEM_DEKU_STICK) */
}

static void     tick(karebaba_t *b, actor_t *a, const int32_t link[3], bool can_take)
{
    int32_t x = b->pos_q8[0] / 256, y = b->pos_q8[1] / 256, z = b->pos_q8[2] / 256;
    int32_t dx = link[0] - x, dz = link[2] - z, dy = link[1] - y;
    int32_t hx = link[0] - b->home[0], hz = link[2] - b->home[2];
    switch (b->action) {
    case KAREBABA_GROW:
        grow_step(b);
        if (b->timer == 20)
            setup_idle(b);
        break;
    case KAREBABA_IDLE:
        if (dx > -200 && dx < 200 && dz > -200 && dz < 200 &&
            dx * dx + dz * dz < 200 * 200 && dy > -30 && dy < 30) {
            b->frame_q8 = 0;
            b->frame_speed_q8 = Q8(4);
            events |= KAREBABA_EV_AWAKEN;
            b->action = KAREBABA_AWAKEN;
        }
        break;
    case KAREBABA_AWAKEN: {
        int32_t s = b->scale;
        anim_update(b, true);
        step_to(&s, SCALE_UP, SCALE_STEP);
        b->scale = (int16_t)s;
        if (step_to(&b->pos_q8[1], (b->home[1] + 60) * 256, Q8(5)))
            setup_upright(b);
        b->rot_y = (uint16_t)(b->rot_y + 0x1999);
        break;
    }
    case KAREBABA_UPRIGHT:
        anim_update(b, true);
        if (b->timer) --b->timer;
        mouth_sound(b);
        if (body_hit(b)) {
            setup_dying(b);
        } else if (hx < -240 || hx > 240 || hz < -240 || hz > 240 ||
                   hx * hx + hz * hz > 240 * 240) {
            /* SetupRetract: reverse at -3, once, from the last frame. */
            b->frame_q8 = (ANIM_FRAMES - 1) * 256;
            b->frame_speed_q8 = -Q8(3);
            reset_collider(b);
            b->action = KAREBABA_RETRACT;
        } else if (!b->timer) {
            b->timer = 40;
            b->action = KAREBABA_SPIN;
        }
        break;
    case KAREBABA_SPIN: {
        int32_t value, c60;
        if (b->timer) --b->timer;
        anim_update(b, true);
        mouth_sound(b);
        value = 20 - b->timer;
        value = 20 - (value < 0 ? -value : value);
        if (value > 10) value = 10;
        b->head.radius = (int16_t)(4 + value * 2);
        b->rot_x = (uint16_t)(0xC000 - value * 0x100);
        b->rot_y = (uint16_t)(b->rot_y + value * 0x2C0);
        b->pos_q8[1] = b->home[1] * 256 - (int32_t)(((int64_t)sin_q16(b->rot_x) * 60 * 256) >> 16);
        c60 = (int32_t)(((int64_t)cos_q16(b->rot_x) * 60) >> 8);        /* Q8 */
        b->pos_q8[0] = b->home[0] * 256 + (int32_t)(((int64_t)sin_q16(b->rot_y) * c60) >> 16);
        b->pos_q8[2] = b->home[2] * 256 + (int32_t)(((int64_t)cos_q16(b->rot_y) * c60) >> 16);
        if (body_hit(b))
            setup_dying(b);
        else if (!b->timer)
            setup_upright(b);
        break;
    }
    case KAREBABA_DYING:
        step_to(&b->speed_q8, 0, 26);                       /* 0.1 */
        if (b->timer == 0) {
            /* Math_ScaledStepToS(rot.x, 0x4800, 0x71C) */
            int16_t d = (int16_t)(0x4800 - b->rot_x);
            if (d > 0x71C) d = 0x71C;
            if (d < -0x71C) d = -0x71C;
            b->rot_x = (uint16_t)(b->rot_x + d);
            if (b->scale > SCALE_IDLE && (b->ground || b->wall)) {
                b->scale = 0;
                b->speed_q8 = 0;
                a->flags &= (uint8_t)~(ACTOR_FLAG_TARGETABLE | ACTOR_FLAG_HOSTILE);
            }
            if (b->ground) {
                events |= KAREBABA_EV_GROUND;
                b->timer = 1;
            }
        } else if (b->timer == 1) {
            /* SetupDeadItemDrop; the 4 + 1 dust puffs are not drawn (logged). */
            b->scale = SCALE_DROP;
            b->rot_x = (uint16_t)(b->rot_x - 0x4000);
            b->vel_y_q8 = 0;
            b->timer = 200;
            b->action = KAREBABA_DROP;
        }
        break;
    case KAREBABA_DROP:
        if (b->timer) --b->timer;
        if (b->picked || !b->timer) {
            setup_dead(b);
            break;
        }
        /* Actor_OfferGetItemNearby: xz < 50, |y| < 10. Player_ActionHandler_2
        ** accepts a positive getItemId with no button. */
        if (can_take && dx > -50 && dx < 50 && dz > -50 && dz < 50 &&
            dx * dx + dz * dz < 50 * 50 && dy > -10 && dy < 10) {
            events |= save_state.stick_owned ? KAREBABA_EV_STICK : KAREBABA_EV_STICK_FIRST;
            item_give_stick();
            b->picked = 1;                  /* actor.parent = player */
        }
        break;
    case KAREBABA_RETRACT: {
        int32_t s = b->scale;
        anim_update(b, false);
        step_to(&s, SCALE_IDLE, SCALE_STEP);
        b->scale = (int16_t)s;
        if (step_to(&b->pos_q8[1], (b->home[1] + 14) * 256, Q8(5)))
            setup_idle(b);
        b->rot_y = (uint16_t)(b->rot_y + 0x1999);
        break;
    }
    case KAREBABA_DEAD:
        if (b->timer) --b->timer;
        if (!b->timer) {
            b->head.radius = 4;
            b->scale = 0;
            b->timer = 0;
            b->action = KAREBABA_REGROW;
        }
        break;
    case KAREBABA_REGROW:
        grow_step(b);
        if (b->timer == 20) {
            a->flags |= ACTOR_FLAG_TARGETABLE | ACTOR_FLAG_HOSTILE;
            setup_idle(b);
        }
        break;
    }
    if (b->action == KAREBABA_DYING) {
        /* Actor_MoveXZGravity (gravity -0.8, min -20) + bg check. */
        int32_t d[3], feet[3];
        b->vel_y_q8 -= 205;
        if (b->vel_y_q8 < -Q8(20)) b->vel_y_q8 = -Q8(20);
        d[0] = (int32_t)(((int64_t)b->speed_q8 * sin_q16(b->move_yaw)) >> 16);
        d[2] = (int32_t)(((int64_t)b->speed_q8 * cos_q16(b->move_yaw)) >> 16);
        d[1] = b->vel_y_q8;
        feet[0] = b->pos_q8[0]; feet[1] = b->pos_q8[1]; feet[2] = b->pos_q8[2];
        karebaba_bg_move(feet, d, &b->ground, &b->wall);
        b->pos_q8[0] = feet[0]; b->pos_q8[1] = feet[1]; b->pos_q8[2] = feet[2];
    } else {
        b->ground = b->wall = false;
    }
}

/* Actor side: position, focus (x/z at home, y capped at home + 40), arrow.
** Collider base points are offsets from the owning actor (collide.c base()),
** so the fixed spawn-point cylinders are re-expressed against its new place
** every step. */
static void     sync_actor(karebaba_t *b, actor_t *a)
{
    int32_t fy;
    a->x = b->pos_q8[0] / 256;
    a->y = b->pos_q8[1] / 256;
    a->z = b->pos_q8[2] / 256;
    /* Actor_SetFocus(scale x 10 / 0.01): scale / 20 units above world.pos. */
    fy = a->y + b->scale / 20;
    if (fy > b->home[1] + 40) fy = b->home[1] + 40;
    a->focus[0] = (int16_t)(b->home[0] - a->x);
    a->focus[1] = (int16_t)(fy - a->y);
    a->focus[2] = (int16_t)(b->home[2] - a->z);
    a->arrow_y = (int16_t)(b->scale / 8);          /* 2500 x scale.y */
    b->head.x = b->body.x = b->home[0] - a->x;
    b->head.y = b->body.y = b->home[1] - a->y;
    b->head.z = b->body.z = b->home[2] - a->z;
}

static void     spawn(karebaba_t *b, unsigned int i, const kokiri_prop_t *p, unsigned scene)
{
    actor_t *a = actor_spawn(&profile, scene, ACTOR_ROOM_NONE,
                             p->x, p->y, p->z, 0, 1);
    unsigned int k;
    if (!a) { b->handle = 0; return; }  /* retried by karebaba_sync */
    for (k = 0; k < sizeof(*b); ++k) ((unsigned char *)b)[k] = 0;
    b->handle = actor_handle(a);
    b->spawn = (uint8_t)i;
    b->home[0] = p->x; b->home[1] = p->y; b->home[2] = p->z;
    b->pos_q8[0] = p->x * 256; b->pos_q8[1] = p->y * 256; b->pos_q8[2] = p->z * 256;
    a->attention = ATTN_ENEMY;
    a->range = ATTN_RANGE_1;
    a->navi_text = NAVI_TEXT;
    /* sBodyColliderInit / sHeadColliderInit, fixed at the spawn point. */
    b->body.actor = a;
    b->body.shape = COLSHAPE_CYLINDER;
    b->body.ac_type = AC_TYPE_PLAYER;
    b->body.oc_flags2 = OC2_TYPE_1;
    b->head.actor = a;
    b->head.shape = COLSHAPE_CYLINDER;
    b->head.at_type = AT_TYPE_ENEMY;
    b->head.at_dmg = 0xFFCFFFFFu;
    b->head.at_damage = 8;
    b->head.oc_flags1 = OC1_ON | OC1_TYPE_ALL;
    b->head.oc_flags2 = OC2_TYPE_1;
    b->head.mass = MASS_HEAVY;
    b->head.radius = 4;
    reset_collider(b);
    if (scene==SAVE_SCENE_KOKIRI_FOREST && (KOKIRI_BABA_GROW & (1u << i))) {
        b->scale = 0;
        b->rot_x = 0xC000;
        b->pos_q8[1] = (p->y + 14) * 256;
        b->action = KAREBABA_GROW;
    } else {
        setup_idle(b);
    }
    sync_actor(b, a);
}

unsigned int    karebaba_bytes(void) { return (unsigned int)(KAREBABA_MAX * sizeof(karebaba_t)); }

bool            karebaba_init(void *storage, unsigned int bytes)
{
    babas = storage && bytes >= karebaba_bytes() ? (karebaba_t *)storage : (karebaba_t *)0;
    count = 0;
    return babas != 0;
}

void            karebaba_reset(void)
{
    unsigned int i;
    for (i = 0; i < count; ++i)
        actor_kill(actor_resolve(babas[i].handle));
    count = 0;
    events = 0;
}

void            karebaba_sync(bool in_scene, unsigned int room)
{
    karebaba_sync_scene(in_scene?SAVE_SCENE_KOKIRI_FOREST:255,room);
}
void            karebaba_sync_scene(unsigned int scene, unsigned int room)
{
    unsigned int i;
    const kokiri_prop_t *placements=scene==SAVE_SCENE_DEKU_TREE?dungeon_babas:kokiri_babas;
    unsigned total=scene==SAVE_SCENE_DEKU_TREE?sizeof(dungeon_babas)/sizeof(dungeon_babas[0]):KOKIRI_BABA_COUNT;
    bool live = babas && (scene==SAVE_SCENE_DEKU_TREE || scene==SAVE_SCENE_KOKIRI_FOREST);
    if(live_scene!=scene || live_room!=room) {
        karebaba_reset();live_scene=scene;live_room=room;
    }
    if (!live) {
        if (count) karebaba_reset();
        return;
    }
    if (count) {
        for (i = 0; i < count; ++i)
            if (!actor_resolve(babas[i].handle)) break;
        if (i < count)
            karebaba_reset();           /* unloaded under us: respawn fresh */
    }
    /* Required placements: a spawn refused by a full pool (counted by
    ** actor_sys) is retried every sync until it lands, never dropped. */
    for (i = 0; i < total && count < KAREBABA_MAX; ++i) {
        unsigned int k;
        if(placements[i].room!=room)continue;
        for (k = 0; k < count; ++k)
            if (babas[k].spawn == i) break;
        if (k < count)
            continue;
        spawn(&babas[count], i,&placements[i],scene);
        if (babas[count].handle) ++count;
    }
}

void            karebaba_update(int32_t link_x, int32_t link_y, int32_t link_z, bool can_take)
{
    int32_t link[3] = { link_x, link_y, link_z };
    unsigned int i;
    events = 0;
    for (i = 0; i < count; ++i) {
        karebaba_t *b = &babas[i];
        actor_t *a = actor_resolve(b->handle);
        if (!a) continue;
        /* Source 20 Hz on the 30 Hz step. */
        b->phase = (uint8_t)(b->phase + 2);
        if (b->phase >= 3) {
            b->phase = (uint8_t)(b->phase - 3);
            tick(b, a, link, can_take);
            b->hit = false;
        }
        sync_actor(b, a);
    }
}

void            karebaba_register(void)
{
    unsigned int i;
    for (i = 0; i < count; ++i) {
        karebaba_t *b = &babas[i];
        if (!actor_resolve(b->handle) || b->action == KAREBABA_DEAD ||
            b->action == KAREBABA_DYING || b->action == KAREBABA_DROP)
            continue;
        if (b->action != KAREBABA_REGROW && b->action != KAREBABA_GROW) {
            collide_set_at(&b->head);
            collide_set_ac(&b->body);
        }
        collide_set_oc(&b->head);
    }
}

void            karebaba_collect(void)
{
    unsigned int i;
    for (i = 0; i < count; ++i)
        if (babas[i].body.result & COL_RES_AC_HIT)
            babas[i].hit = true;
}

unsigned int        karebaba_count(void) { return count; }
const karebaba_t   *karebaba_at(unsigned int i) { return i < count ? &babas[i] : 0; }
uint32_t            karebaba_events(void) { return events; }
