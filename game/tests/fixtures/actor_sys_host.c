/* Host adapter for actor_sys.c and collide.c: small scenarios the Python test
** drives through ctypes. Everything is platform free; no Saturn stand-ins. */
#include <stdint.h>
#include "../../src/actor_sys.h"
#include "../../src/collide.h"
#include "../../src/save_state.h"

static unsigned char    storage[ACTOR_POOL_MAX * sizeof(actor_t)];
static int              inits, updates, draws, destroys;
static int              order[ACTOR_POOL_MAX * 2], order_len;

static void t_init(actor_t *a)      { ++inits; a->data[0] = 7; }
static void t_update(actor_t *a)
{
    ++updates;
    if (order_len < (int)(sizeof(order) / sizeof(order[0])))
        order[order_len++] = a->profile->category;
    if (a->params == 1)
        actor_kill(a);                  /* self kill during update */
}
static void t_draw(const actor_t *a){ (void)a; ++draws; }
static void t_destroy(actor_t *a)   { (void)a; ++destroys; }
static void t_init_fail(actor_t *a) { actor_kill(a); }

static const actor_profile_t npc   = { 1, ACTORCAT_NPC,   ACTOR_FLAG_TARGETABLE, t_init, t_update, t_draw, t_destroy };
static const actor_profile_t enemy = { 2, ACTORCAT_ENEMY, ACTOR_FLAG_TARGETABLE, t_init, t_update, t_draw, t_destroy };
static const actor_profile_t sw    = { 3, ACTORCAT_SWITCH, 0, t_init, t_update, t_draw, t_destroy };
static const actor_profile_t keep  = { 4, ACTORCAT_MISC, ACTOR_FLAG_PERSISTENT, t_init, t_update, t_draw, t_destroy };
static const actor_profile_t fail  = { 5, ACTORCAT_PROP, 0, t_init_fail, 0, 0, t_destroy };

static const actor_profile_t *profiles[] = { &npc, &enemy, &sw, &keep, &fail };

int     as_reset(void)
{
    inits = updates = draws = destroys = order_len = 0;
    return (int)actor_sys_init(storage, sizeof(storage));
}

int     as_init_small(void)     { return (int)actor_sys_init(storage, actor_sys_bytes() - 1); }
int     as_inits(void)          { return inits; }
int     as_updates(void)        { return updates; }
int     as_draws(void)          { return draws; }
int     as_destroys(void)       { return destroys; }
int     as_order(int i)         { return i < order_len ? order[i] : -1; }
int     as_order_len(void)      { return order_len; }

int     as_spawn(int kind, int scene, int room, int x, int z, int params,
                 int attention)
{
    actor_t *a = actor_spawn(profiles[kind], (unsigned)scene, room, x, 0, z,
                             0, (uint16_t)params);
    if (!a)
        return (-1);
    a->attention = (uint8_t)attention;
    return (int)(a - (actor_t *)storage);
}

int     as_data0(int slot)
{
    actor_t *a = actor_sys_slot((unsigned)slot);
    return a ? a->data[0] : -1;
}

void    as_kill(int slot)       { actor_kill(actor_sys_slot((unsigned)slot)); }

int     as_nearest(int x, int z, int range, unsigned mask)
{
    actor_t *a = actor_sys_nearest_attention(x, 0, z, range, mask);
    return a ? (int)(a - (actor_t *)storage) : -1;
}

int     as_find_count(int id)
{
    int n = 0;
    actor_t *a = 0;
    while ((a = actor_sys_find((uint16_t)id, a)) != 0)
        ++n;
    return n;
}

int     as_flag_round_trip(int slot, int flag)
{
    actor_t *a = actor_sys_slot((unsigned)slot);
    int before = actor_get_chest(a, (unsigned)flag) | actor_get_switch(a, (unsigned)flag) << 1 |
                 actor_get_clear(a, (unsigned)flag) << 2 | actor_get_collect(a, (unsigned)flag) << 3;
    actor_set_chest(a, (unsigned)flag);
    actor_set_switch(a, (unsigned)flag);
    actor_set_clear(a, (unsigned)flag);
    actor_set_collect(a, (unsigned)flag);
    return before << 4 | (actor_get_chest(a, (unsigned)flag) | actor_get_switch(a, (unsigned)flag) << 1 |
                          actor_get_clear(a, (unsigned)flag) << 2 | actor_get_collect(a, (unsigned)flag) << 3);
}

/* ---- collide ---------------------------------------------------------- */

static collider_t   cols[8];

void    co_clear(void)
{
    unsigned char *p = (unsigned char *)cols;
    unsigned int i;
    for (i = 0; i < sizeof(cols); ++i) p[i] = 0;
    collide_begin();
}

void    co_cyl(int i, int x, int y, int z, int radius, int height, int mass)
{
    cols[i].shape = COLSHAPE_CYLINDER;
    cols[i].x = x; cols[i].y = y; cols[i].z = z;
    cols[i].radius = (int16_t)radius; cols[i].height = (int16_t)height;
    cols[i].mass = (uint8_t)mass;
}

void    co_capsule(int i, int ax, int ay, int az, int bx, int by, int bz, int radius)
{
    cols[i].shape = COLSHAPE_CAPSULE;
    cols[i].ax = ax; cols[i].ay = ay; cols[i].az = az;
    cols[i].bx = bx; cols[i].by = by; cols[i].bz = bz;
    cols[i].radius = (int16_t)radius;
}

static const uint8_t table[32] = {
    [0] = DMG_ENTRY(0, 1),      /* deku nut: stun, no damage */
    [8] = DMG_ENTRY(2, 0),      /* kokiri slash */
    [22] = DMG_ENTRY(4, 0),     /* kokiri spin */
};

void    co_at(int i, unsigned dmg, int damage, int type)
{
    cols[i].at_dmg = dmg; cols[i].at_damage = (uint8_t)damage;
    cols[i].at_type = (uint8_t)type;
    collide_set_at(&cols[i]);
}

void    co_ac(int i, unsigned bumper, int use_table, int defense, int type,
              int invincible)
{
    cols[i].ac_bumper = bumper;
    cols[i].damage_table = use_table ? table : 0;
    cols[i].defense = (uint8_t)defense;
    cols[i].ac_type = (uint8_t)type;
    cols[i].invincible = (uint8_t)invincible;
    collide_set_ac(&cols[i]);
}

void    co_oc(int i, int flags1, int flags2)
{
    cols[i].oc_flags1 = (uint8_t)flags1;
    cols[i].oc_flags2 = (uint8_t)flags2;
    collide_set_oc(&cols[i]);
}

void    co_run(void)            { collide_run(); }
int     co_ac_hit(int i)        { return cols[i].ac_hit ? (int)(cols[i].ac_hit - cols) : -1; }
int     co_at_hit(int i)        { return cols[i].at_hit ? (int)(cols[i].at_hit - cols) : -1; }
int     co_oc_hit(int i)        { return cols[i].oc_hit ? (int)(cols[i].oc_hit - cols) : -1; }
int     co_damage(int i)        { return cols[i].ac_damage; }
int     co_effect(int i)        { return cols[i].ac_effect; }
int     co_disp_x(int i)        { return cols[i].disp_x; }
int     co_disp_z(int i)        { return cols[i].disp_z; }
void    co_apply(int i)         { collide_apply_displacement(&cols[i]); }
int     co_x(int i)             { return cols[i].x; }
void    co_tick(int i)          { collide_tick(&cols[i]); }
int     co_invincible(int i)    { return cols[i].invincible; }
int     co_overlap(int a, int b)
{
    int32_t o = -1;
    return collide_overlap(&cols[a], &cols[b], &o) ? o : -1;
}
