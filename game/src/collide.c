#pragma GCC optimize ("Os") /* Bounded integer contacts; keep code within high RAM. */
/* Actor-vs-actor collision check. See collide.h. Integer only. */
#include "collide.h"

static collider_t  *at_list[COLLIDE_LIST_MAX], *ac_list[COLLIDE_LIST_MAX],
                   *oc_list[COLLIDE_LIST_MAX];
static unsigned int at_count, ac_count, oc_count;
static collide_event_t events[COLLIDE_EVENT_MAX];
static unsigned int event_count, overflow;

uint32_t    collide_isqrt(uint32_t v)
{
    uint32_t    r = 0, bit = 1u << 30;

    while (bit > v)
        bit >>= 2;
    while (bit) {
        if (v >= r + bit) {
            v -= r + bit;
            r = (r >> 1) + bit;
        } else {
            r >>= 1;
        }
        bit >>= 2;
    }
    return (r);
}

void        collide_begin(void)
{
    at_count = ac_count = oc_count = 0;
    event_count = 0;
}

static bool push(collider_t **list, unsigned int *count, collider_t *c)
{
    if (!c)
        return (false);
    c->owner = actor_handle(c->actor);      /* BUG-028: identity at registration */
    if (*count >= COLLIDE_LIST_MAX) {
        ++overflow;
        return (false);
    }
    list[(*count)++] = c;
    return (true);
}

bool        collide_set_at(collider_t *c)
{
    if (c) {
        c->at_hit = 0;
        c->at_hit_actor = ACTOR_HANDLE_NONE;
        c->at_hits = 0;
        c->result &= (uint8_t)~(COL_RES_AT_HIT | COL_RES_AT_BOUNCED);
    }
    return (push(at_list, &at_count, c));
}

bool        collide_set_ac(collider_t *c)
{
    if (c) {
        c->ac_hit = 0;
        c->ac_hit_actor = ACTOR_HANDLE_NONE;
        c->ac_damage = c->ac_effect = 0;
        c->result &= (uint8_t)~(COL_RES_AC_HIT | COL_RES_AC_BOUNCED);
    }
    return (push(ac_list, &ac_count, c));
}

bool        collide_set_oc(collider_t *c)
{
    if (c) {
        c->oc_hit = 0;
        c->oc_hit_actor = ACTOR_HANDLE_NONE;
    }
    return (push(oc_list, &oc_count, c));
}

unsigned int            collide_event_count(void) { return (event_count); }
const collide_event_t  *collide_event(unsigned int index)
{
    return (index < event_count ? &events[index] : (const collide_event_t *)0);
}
unsigned int            collide_overflow(void) { return (overflow); }
void                    collide_overflow_reset(void) { overflow = 0; }

void        collide_forget(collider_t *c)
{
    if (c) {
        unsigned int i;
        for (i = 0; i < COLLIDE_SEEN_MAX; ++i) {
            c->seen[i].attacker = ACTOR_HANDLE_NONE;
            c->seen[i].attack = c->seen[i].tag = 0;
        }
        c->seen_next = 0;
    }
}

bool        collide_guard_blocked(const collider_t *shield)
{
    return (shield && (shield->result & COL_RES_AC_BOUNCED) != 0);
}

/* World-space cylinder centre (feet) of a cylinder collider. */
static void base(const collider_t *c, int32_t *x, int32_t *y, int32_t *z)
{
    *x = c->x; *y = c->y + c->y_shift; *z = c->z;
    if (c->actor) {
        *x += c->actor->x; *y += c->actor->y; *z += c->actor->z;
    }
}

static int32_t clamp32(int32_t v, int32_t lo, int32_t hi)
{
    return (v < lo ? lo : v > hi ? hi : v);
}

static bool cyl_cyl(const collider_t *a, const collider_t *b, int32_t *overlap)
{
    int32_t ax, ay, az, bx, by, bz, dx, dz, reach, dist;

    base(a, &ax, &ay, &az);
    base(b, &bx, &by, &bz);
    if (ay + a->height < by || by + b->height < ay)
        return (false);
    dx = bx - ax;
    dz = bz - az;
    reach = a->radius + b->radius;
    if (dx > reach || dx < -reach || dz > reach || dz < -reach)
        return (false);
    dist = (int32_t)collide_isqrt((uint32_t)(dx * dx + dz * dz));
    if (dist >= reach)
        return (false);
    *overlap = reach - dist;
    return (true);
}

/* Capsule (segment A-B, radius) vs vertical cylinder. The segment is first
** clipped (Q12 parameter) to the cylinder's height span widened by the
** capsule radius; inside that interval the XZ distance to the axis is convex
** in t, so its minimum is the unconstrained XZ minimum clamped into the
** interval. Rounded capsule ends are treated as flat (slightly generous). */
static bool cap_cyl(const collider_t *cap, const collider_t *cyl,
                    int32_t *overlap)
{
    int32_t cx, cy, cz, sx, sy, sz, len2, dot, t, t0, t1, lo, hi, px, pz,
            dx, dz, reach, dist;

    base(cyl, &cx, &cy, &cz);
    sx = cap->bx - cap->ax;
    sy = cap->by - cap->ay;
    sz = cap->bz - cap->az;
    lo = cy - cap->radius;
    hi = cy + cyl->height + cap->radius;
    if (sy == 0) {
        if (cap->ay < lo || cap->ay > hi)
            return (false);
        t0 = 0;
        t1 = 4096;
    } else {
        int32_t ta = ((lo - cap->ay) * 4096) / sy;
        int32_t tb = ((hi - cap->ay) * 4096) / sy;
        if (sy < 0) { int32_t swap = ta; ta = tb; tb = swap; }
        t0 = ta > 0 ? ta : 0;
        t1 = tb < 4096 ? tb : 4096;
        if (t0 > t1)
            return (false);
    }
    len2 = sx * sx + sz * sz;
    t = t0;                                         /* vertical: any t */
    if (len2 > 0) {
        dot = clamp32((cx - cap->ax) * sx + (cz - cap->az) * sz, 0, len2);
        t = len2 < (1 << 18) ? (dot << 12) / len2 : dot / (len2 >> 12);
        t = clamp32(t, t0, t1);
    }
    px = cap->ax + ((sx * t) >> 12);
    pz = cap->az + ((sz * t) >> 12);
    dx = cx - px;
    dz = cz - pz;
    reach = cap->radius + cyl->radius;
    if (dx > reach || dx < -reach || dz > reach || dz < -reach)
        return (false);
    dist = (int32_t)collide_isqrt((uint32_t)(dx * dx + dz * dz));
    if (dist >= reach)
        return (false);
    *overlap = reach - dist;
    return (true);
}

/* Closest points of two finite segments. Q12 parameters retain integer SH-2
 * math and also cover zero-length capsules (enemy head spheres). */
static bool __attribute__((optimize("Os"))) cap_cap(const collider_t *a, const collider_t *b, int32_t *overlap)
{
    int64_t u[3]={a->bx-a->ax,a->by-a->ay,a->bz-a->az};
    int64_t v[3]={b->bx-b->ax,b->by-b->ay,b->bz-b->az};
    int64_t w[3]={a->ax-b->ax,a->ay-b->ay,a->az-b->az};
    int64_t aa=0,bb=0,cc=0,dd=0,ee=0,den,s=0,t=0,d2=0;
    int32_t reach=a->radius+b->radius,dist;
    unsigned i;
    for(i=0;i<3;++i) {
        /* Reject disjoint segment bounds before the divisions. */
        int64_t amin=w[i]+(u[i]<0?u[i]:0), amax=w[i]+(u[i]>0?u[i]:0);
        if(amin>(v[i]>0?v[i]:0)+reach || amax<(v[i]<0?v[i]:0)-reach)return false;
        aa+=u[i]*u[i];bb+=u[i]*v[i];cc+=v[i]*v[i];dd+=u[i]*w[i];ee+=v[i]*w[i];
    }
    if(!aa) t=cc?ee*4096/cc:0;
    else if(!cc) s=-dd*4096/aa;
    else {
        den=aa*cc-bb*bb;
        if(den>0) s=(bb*ee-cc*dd)*4096/den;
        if(s<0)s=0;else if(s>4096)s=4096;
        t=(bb*s+ee*4096)/cc;
        if(t<0) {t=0;s=-dd*4096/aa;}
        else if(t>4096) {t=4096;s=(bb-dd)*4096/aa;}
    }
    if(s<0)s=0;else if(s>4096)s=4096;
    if(t<0)t=0;else if(t>4096)t=4096;
    for(i=0;i<3;++i) {int64_t d=w[i]*4096+u[i]*s-v[i]*t;d2+=d*d;}
    if(d2>=(int64_t)reach*reach*4096*4096)return false;
    dist=collide_isqrt((uint32_t)(d2/(4096*4096)));
    *overlap=reach-dist;
    return true;
}

/* Sword wedge vs a cylinder's base point: the slice swing's reach test. */
static bool sector_cyl(const collider_t *sec, const collider_t *cyl,
                       int32_t *overlap)
{
    int32_t sx, sy, sz, cx, cy, cz, dx, dy, dz, turn;

    base(sec, &sx, &sy, &sz);
    base(cyl, &cx, &cy, &cz);
    dy = sy - cy;
    if (dy < 0) dy = -dy;
    if (dy > sec->height)
        return (false);
    dx = cx - sx;
    dz = cz - sz;
    if (dx > sec->radius || dx < -sec->radius ||
        dz > sec->radius || dz < -sec->radius)
        return (false);
    if (dx * dx + dz * dz > (int32_t)sec->radius * sec->radius)
        return (false);
    turn = (int32_t)(int16_t)(uint16_t)(collide_heading(dx, dz) - sec->yaw);
    if (turn < 0) turn = -turn;
    if (turn > sec->arc)
        return (false);
    *overlap = 1;
    return (true);
}

bool        collide_overlap(const collider_t *a, const collider_t *b,
                            int32_t *overlap)
{
    int32_t dummy;

    if (!overlap)
        overlap = &dummy;
    if (a->shape == COLSHAPE_CYLINDER && b->shape == COLSHAPE_CYLINDER)
        return (cyl_cyl(a, b, overlap));
    if (a->shape == COLSHAPE_CAPSULE && b->shape == COLSHAPE_CYLINDER)
        return (cap_cyl(a, b, overlap));
    if (a->shape == COLSHAPE_CYLINDER && b->shape == COLSHAPE_CAPSULE)
        return (cap_cyl(b, a, overlap));
    if (a->shape == COLSHAPE_SECTOR && b->shape == COLSHAPE_CYLINDER)
        return (sector_cyl(a, b, overlap));
    if (a->shape == COLSHAPE_CYLINDER && b->shape == COLSHAPE_SECTOR)
        return (sector_cyl(b, a, overlap));
    if (a->shape == COLSHAPE_CAPSULE && b->shape == COLSHAPE_CAPSULE)
        return cap_cap(a, b, overlap);
    return false;
}

/* CollisionCheck_ApplyDamage: table index is the highest set DMG bit. */
static void apply_damage(collider_t *ac, const collider_t *at)
{
    uint32_t    flags = at->at_dmg;
    unsigned int i = 0;

    if (ac->damage_table) {
        if (!flags)
            return;
        while (flags > 1) {
            flags >>= 1;
            ++i;
        }
        ac->ac_damage = ac->damage_table[i] & 0xF;
        ac->ac_effect = (ac->damage_table[i] >> 4) & 0xF;
    } else {
        ac->ac_damage = at->at_damage > ac->defense ?
                        (uint8_t)(at->at_damage - ac->defense) : 0;
    }
}

/* Colliders of an actor killed before the run take no part (the source skips
** actors whose update is gone). Actorless colliders always take part. */
static bool live(const collider_t *c)
{
    return (!c->actor ||
            (c->owner != ACTOR_HANDLE_NONE && actor_handle(c->actor) == c->owner));
}

/* The victim already took this attack instance: the overlap lingers. */
static bool already_hit(const collider_t *ac, const collider_t *at,
                        actor_handle_t attacker)
{
    unsigned int i;
    if (!at->attack_id)
        return (false);
    for (i = 0; i < COLLIDE_SEEN_MAX; ++i)
        if (ac->seen[i].attack == at->attack_id &&
            ac->seen[i].attacker == attacker && ac->seen[i].tag == at->tag)
            return (true);
    return (false);
}

static void record(const collider_t *at, const collider_t *ac,
                   actor_handle_t attacker, actor_handle_t victim, bool bounced)
{
    collide_event_t *e;

    if (event_count >= COLLIDE_EVENT_MAX) {
        ++overflow;
        return;
    }
    e = &events[event_count++];
    e->at_actor = attacker;
    e->ac_actor = victim;
    e->at_tag = at->tag;
    e->ac_tag = ac->tag;
    e->attack_id = at->attack_id;
    e->damage = ac->ac_damage;
    e->effect = ac->ac_effect;
    e->bounced = bounced;
    e->pad = 0;
}

/* True when `at` already hit another element of ac's actor this pass. */
static bool took_element(const collider_t *at, const collider_t *ac, unsigned int upto)
{
    unsigned int k;
    if (!ac->actor)
        return (false);
    for (k = 0; k < upto; ++k)
        if (ac_list[k] != ac && ac_list[k]->actor == ac->actor &&
            (ac_list[k]->ac_flags & COL_AC_ELEMENT) && ac_list[k]->ac_hit == at)
            return (true);
    return (false);
}

/* CollisionCheck_AT / CollisionCheck_SetATvsAC. The first AT to reach an AC
** in a pass owns its damage; an AT keeps going to further victims. */
static void at_vs_ac(void)
{
    unsigned int i, j;

    for (i = 0; i < at_count; ++i) {
        collider_t *at = at_list[i];
        actor_handle_t attacker;
        if (!live(at))
            continue;
        attacker = at->owner;
        for (j = 0; j < ac_count; ++j) {
            collider_t *ac = ac_list[j];
            actor_handle_t victim;
            bool bounced;
            if (ac->ac_hit || ac->invincible || !live(ac))
                continue;
            if (at == ac || (at->actor && at->actor == ac->actor))
                continue;               /* one collider as both AT and AC */
            if (!(at->at_type & ac->ac_type) || !(at->at_dmg & ac->ac_bumper))
                continue;
            if (already_hit(ac, at, attacker))
                continue;
            if ((ac->ac_flags & COL_AC_ELEMENT) && took_element(at, ac, j))
                continue;
            if (!collide_overlap(at, ac, (int32_t *)0))
                continue;
            victim = ac->owner;
            bounced = (ac->ac_flags & COL_AC_HARD) &&
                      (at->actor || (at->ac_flags & COL_OUTSIDE_ACTOR)) &&
                      (ac->actor || (ac->ac_flags & COL_OUTSIDE_ACTOR));
            at->at_hit = ac;
            at->at_hit_actor = victim;
            if (at->at_hits < 0xFF)
                ++at->at_hits;
            at->result |= COL_RES_AT_HIT | (bounced ? COL_RES_AT_BOUNCED : 0);
            ac->ac_hit = at;
            ac->ac_hit_actor = attacker;
            ac->result |= COL_RES_AC_HIT | (bounced ? COL_RES_AC_BOUNCED : 0);
            if (at->attack_id) {
                unsigned int k = ac->seen_next % COLLIDE_SEEN_MAX;
                ac->seen[k].attacker = attacker;
                ac->seen[k].attack = at->attack_id;
                ac->seen[k].tag = at->tag;
                ac->seen_next = (uint8_t)(k + 1);
            }
            apply_damage(ac, at);
            record(at, ac, attacker, victim, bounced);
        }
    }
}

/* CollisionCheck_GetMassType */
static int  mass_type(uint8_t mass)
{
    return (mass == MASS_IMMOVABLE ? 0 : mass == MASS_HEAVY ? 1 : 2);
}

/* CollisionCheck_SetOCvsOC. Ratios are in 1/256. */
static void oc_push(collider_t *l, collider_t *r, int32_t overlap)
{
    int     lt = mass_type(l->mass), rt = mass_type(r->mass);
    int32_t lr, rr, lx, ly, lz, rx, ry, rz, dx, dz, dist;

    l->oc_hit = r;
    r->oc_hit = l;
    l->oc_hit_actor = r->owner;
    r->oc_hit_actor = l->owner;
    if ((l->oc_flags1 & OC1_NO_PUSH) || (r->oc_flags1 & OC1_NO_PUSH))
        return;
    if (lt == 0) {
        if (rt == 0) return;
        lr = 0; rr = 256;
    } else if (lt == 1) {
        if (rt == 0)      { lr = 256; rr = 0; }
        else if (rt == 1) { lr = 128; rr = 128; }
        else              { lr = 0; rr = 256; }
    } else if (rt == 2) {
        int32_t total = l->mass + r->mass;
        if (!total) { lr = rr = 128; }
        else { lr = (r->mass * 256) / total; rr = (l->mass * 256) / total; }
    } else {
        lr = 256; rr = 0;
    }
    base(l, &lx, &ly, &lz);
    base(r, &rx, &ry, &rz);
    dx = rx - lx;
    dz = rz - lz;
    dist = (int32_t)collide_isqrt((uint32_t)(dx * dx + dz * dz));
    if (dist) {
        dx = dx * overlap / dist;
        dz = dz * overlap / dist;
    } else {
        dx = overlap ? overlap : 1;
        dz = 0;
    }
    l->disp_x -= (dx * lr) >> 8;
    l->disp_z -= (dz * lr) >> 8;
    r->disp_x += (dx * rr) >> 8;
    r->disp_z += (dz * rr) >> 8;
}

/* CollisionCheck_SkipOC / type masks: each side must accept the other. */
static bool oc_pair_ok(const collider_t *l, const collider_t *r)
{
    if (!(l->oc_flags1 & OC1_ON) || !(r->oc_flags1 & OC1_ON))
        return (false);
    if (l->actor && l->actor == r->actor)
        return (false);
    return ((l->oc_flags1 & r->oc_flags2 & OC1_TYPE_ALL) &&
            (r->oc_flags1 & l->oc_flags2 & OC1_TYPE_ALL));
}

static void oc_vs_oc(void)
{
    unsigned int i, j;
    int32_t overlap;

    for (i = 0; i < oc_count; ++i)
        for (j = i + 1; j < oc_count; ++j) {
            collider_t *l = oc_list[i], *r = oc_list[j];
            if (l->shape != COLSHAPE_CYLINDER || r->shape != COLSHAPE_CYLINDER)
                continue;
            if (!oc_pair_ok(l, r) || !live(l) || !live(r))
                continue;
            if (collide_overlap(l, r, &overlap))
                oc_push(l, r, overlap);
        }
}

void        collide_run(void)
{
    at_vs_ac();
    oc_vs_oc();
}

void        collide_apply_displacement(collider_t *c)
{
    if (!c)
        return;
    if (c->actor && !live(c)) {
        /* owner gone or slot reused: never shove the replacement */
    } else if (c->actor) {
        if (c->disp_x || c->disp_z)
            collide_world_push(c->actor, c->disp_x, c->disp_z);
    } else {
        c->x += c->disp_x;
        c->z += c->disp_z;
    }
    c->disp_x = c->disp_z = 0;
}

void        collide_tick(collider_t *c)
{
    if (c && c->invincible)
        --c->invincible;
}
