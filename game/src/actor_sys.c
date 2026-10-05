#pragma GCC optimize("Os") /* actor/state logic, not draw loops: size over speed (work RAM) */
/* Fixed actor pool. See actor_sys.h. Integer only, platform free. */
#include "actor_sys.h"
#include "save_state.h"

static actor_t     *pool;
static bool         updating;
/* Never reset by scene clear or pool re-init. Exhaustion refuses a spawn
 * rather than allowing an ancient contact to resolve to a new actor. */
static actor_handle_t next_identity;
static unsigned int   spawn_failures;

unsigned int    actor_sys_bytes(void)
{
    return (unsigned int)(ACTOR_POOL_MAX * sizeof(actor_t));
}

static void     wipe(actor_t *a)
{
    unsigned int    i;
    unsigned char  *p = (unsigned char *)a;
    for (i = 0; i < sizeof(*a); ++i)
        p[i] = 0;
}

bool            actor_sys_init(void *storage, unsigned int bytes)
{
    unsigned int    i;

    if (!storage || bytes < actor_sys_bytes())
        return (false);
    spawn_failures = 0;
    pool = (actor_t *)storage;
    for (i = 0; i < ACTOR_POOL_MAX; ++i)
        wipe(&pool[i]);
    updating = false;
    return (true);
}

static void     destroy(actor_t *a)
{
    a->kill = 1;
    if (a->profile && a->profile->destroy)
        a->profile->destroy(a);
    wipe(a);
}

void            actor_sys_clear(void)
{
    unsigned int    i;

    if (!pool)
        return;
    for (i = 0; i < ACTOR_POOL_MAX; ++i)
        if (pool[i].profile)
            destroy(&pool[i]);
}

actor_t        *actor_spawn(const actor_profile_t *profile, unsigned int scene,
                            int room, int32_t x, int32_t y, int32_t z,
                            uint16_t yaw, uint16_t params)
{
    unsigned int    i;
    actor_t        *a;

    if (!pool || !profile || profile->category >= ACTORCAT_MAX ||
        next_identity == UINT32_MAX)
        return ((actor_t *)0);
    for (i = 0; i < ACTOR_POOL_MAX; ++i)
        if (!pool[i].profile)
            break;
    if (i == ACTOR_POOL_MAX) {
        ++spawn_failures;           /* pool full: counted, never silent */
        return ((actor_t *)0);
    }
    a = &pool[i];
    wipe(a);
    a->identity = ++next_identity;
    a->profile = profile;
    a->x = x; a->y = y; a->z = z;
    a->yaw = yaw;
    a->params = params;
    a->room = (int8_t)room;
    a->scene = (uint8_t)scene;
    a->flags = profile->flags;
    if (profile->init)
        profile->init(a);
    return (a->profile ? a : (actor_t *)0);    /* init may self-kill */
}

void            actor_kill(actor_t *a)
{
    if (!a || !a->profile)
        return;
    if (updating)
        a->kill = 1;
    else
        destroy(a);
}

actor_handle_t actor_handle(const actor_t *actor)
{
    /* O(1): the contact loop asks this per collider pair. */
    uintptr_t offset;
    if (!pool || !actor) return ACTOR_HANDLE_NONE;
    offset = (uintptr_t)actor - (uintptr_t)pool;
    if ((uintptr_t)actor < (uintptr_t)pool ||
        offset >= ACTOR_POOL_MAX * sizeof(actor_t) || offset % sizeof(actor_t))
        return ACTOR_HANDLE_NONE;
    actor = &pool[offset / sizeof(actor_t)];
    return actor->profile && !actor->kill ? actor->identity : ACTOR_HANDLE_NONE;
}

actor_t *actor_resolve(actor_handle_t handle)
{
    unsigned int i;
    if (!pool || !handle) return (actor_t *)0;
    for (i = 0; i < ACTOR_POOL_MAX; ++i)
        if (pool[i].identity == handle && pool[i].profile && !pool[i].kill)
            return &pool[i];
    return (actor_t *)0;
}

static void     reap(void)
{
    unsigned int    i;
    for (i = 0; i < ACTOR_POOL_MAX; ++i)
        if (pool[i].profile && pool[i].kill)
            destroy(&pool[i]);
}

void actor_hit_filter(actor_t *a, bool blue, unsigned intensity, unsigned frames)
{
    if(!a)return;
    unsigned steps=(frames*3+1)/2;
    a->filter_timer=a->filter_duration=steps>255?255:steps;
    a->filter_blue=blue;a->filter_intensity=intensity;
}
unsigned actor_filter_level(const actor_t *a)
{
    if(!a || !a->filter_timer || !a->filter_duration)return 0;
    /* Saturn additive RGB offset approximates source fog tint, with its
     * strongest tint on impact and a bounded fade over the source duration. */
    unsigned level=(4+11*a->filter_timer/a->filter_duration)*a->filter_intensity/255;
    return 1+level+(a->filter_blue?16:0);
}

void            actor_sys_update(void)
{
    unsigned int    cat, i;

    if (!pool)
        return;
    for(i=0;i<ACTOR_POOL_MAX;++i)
        if(pool[i].profile && pool[i].filter_timer)--pool[i].filter_timer;
    updating = true;
    for (cat = 0; cat < ACTORCAT_MAX; ++cat)
        for (i = 0; i < ACTOR_POOL_MAX; ++i) {
            actor_t *a = &pool[i];
            if (a->profile && !a->kill && a->profile->category == cat &&
                a->profile->update)
                a->profile->update(a);
        }
    updating = false;
    reap();
}

void            actor_sys_draw(void)
{
    unsigned int    i;

    if (!pool)
        return;
    for (i = 0; i < ACTOR_POOL_MAX; ++i)
        if (pool[i].profile && !pool[i].kill && pool[i].profile->draw)
            pool[i].profile->draw(&pool[i]);
}

void            actor_sys_room_unload(int room)
{
    unsigned int    i;

    if (!pool || room == ACTOR_ROOM_NONE)
        return;
    for (i = 0; i < ACTOR_POOL_MAX; ++i)
        if (pool[i].profile && pool[i].room == room &&
            !(pool[i].flags & ACTOR_FLAG_PERSISTENT))
            actor_kill(&pool[i]);
}

void            actor_sys_scene_unload(void)
{
    unsigned int    i;

    if (!pool)
        return;
    for (i = 0; i < ACTOR_POOL_MAX; ++i)
        if (pool[i].profile && !(pool[i].flags & ACTOR_FLAG_PERSISTENT))
            actor_kill(&pool[i]);
}

unsigned int    actor_sys_live(void)
{
    unsigned int    i, n = 0;

    if (!pool)
        return (0);
    for (i = 0; i < ACTOR_POOL_MAX; ++i)
        if (pool[i].profile && !pool[i].kill)
            ++n;
    return (n);
}

actor_t        *actor_sys_slot(unsigned int index)
{
    if (!pool || index >= ACTOR_POOL_MAX || !pool[index].profile)
        return ((actor_t *)0);
    return (&pool[index]);
}

actor_t        *actor_sys_find(uint16_t id, const actor_t *after)
{
    unsigned int    i = 0;

    if (!pool)
        return ((actor_t *)0);
    if (after)
        i = (unsigned int)(after - pool) + 1;
    for (; i < ACTOR_POOL_MAX; ++i)
        if (pool[i].profile && !pool[i].kill && pool[i].profile->id == id)
            return (&pool[i]);
    return ((actor_t *)0);
}

/* sAttentionRanges {range, lockOnLeashRange}; RANGE_6/7 leash rounded. */
static const uint16_t attention_ranges[ATTN_RANGE_COUNT][2] = {
    {70, 140}, {170, 255}, {280, 5600}, {350, 525}, {700, 1050},
    {1000, 1500}, {100, 105}, {140, 163}, {240, 576}, {280, 65535},
    {320, 420},
};

uint32_t        actor_attention_range_sq(const actor_t *actor)
{
    uint32_t r = attention_ranges[actor->range < ATTN_RANGE_COUNT ? actor->range : 0][0];
    return r * r;
}

uint32_t        actor_attention_leash_sq(const actor_t *actor)
{
    unsigned int k = actor->range < ATTN_RANGE_COUNT ? actor->range : 0;
    /* The slice NPC keeps its planar 420 drop: 420^2, not 320 * 420. */
    if (k == ATTN_RANGE_SLICE_NPC)
        return 420u * 420u;
    return (uint32_t)attention_ranges[k][0] * attention_ranges[k][1];
}

actor_t        *actor_sys_nearest_attention(int32_t x, int32_t y, int32_t z,
                                            int32_t range, unsigned int mask)
{
    unsigned int    i;
    actor_t        *best = (actor_t *)0;
    uint32_t        best_d2, limit;

    (void)y;
    if (!pool || range <= 0)
        return (best);
    if (range > 46340)
        range = 46340;             /* range^2 < 2^31 */
    limit = (uint32_t)(range * range);
    best_d2 = limit + 1;
    for (i = 0; i < ACTOR_POOL_MAX; ++i) {
        actor_t *a = &pool[i];
        int32_t dx, dz;
        uint32_t d2;
        if (!a->profile || a->kill || !(a->flags & ACTOR_FLAG_TARGETABLE) ||
            a->attention == ATTN_NONE || !(mask & (1u << a->attention)))
            continue;
        dx = a->x - x;
        dz = a->z - z;
        if (dx > range || dx < -range || dz > range || dz < -range)
            continue;
        /* Each square < 2^31 after the box test; the sum < 2^32 unsigned. */
        d2 = (uint32_t)(dx * dx) + (uint32_t)(dz * dz);
        if (d2 <= limit && d2 < best_d2) {
            best_d2 = d2;
            best = a;
        }
    }
    return (best);
}

bool    actor_get_chest(const actor_t *a, unsigned int f)   { return a && save_get_treasure(a->scene, f); }
void    actor_set_chest(const actor_t *a, unsigned int f)   { if (a) save_set_treasure(a->scene, f); }
bool    actor_get_switch(const actor_t *a, unsigned int f)  { return a && save_get_switch(a->scene, f); }
void    actor_set_switch(const actor_t *a, unsigned int f)  { if (a) save_set_switch(a->scene, f); }
bool    actor_get_clear(const actor_t *a, unsigned int f)   { return a && save_get_clear(a->scene, f); }
void    actor_set_clear(const actor_t *a, unsigned int f)   { if (a) save_set_clear(a->scene, f); }
bool    actor_get_collect(const actor_t *a, unsigned int f) { return a && save_get_collectible(a->scene, f); }
void    actor_set_collect(const actor_t *a, unsigned int f) { if (a) save_set_collectible(a->scene, f); }

unsigned int    actor_sys_spawn_failures(void)
{
    return (spawn_failures);
}
