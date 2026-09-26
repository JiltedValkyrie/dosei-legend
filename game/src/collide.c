/* Actor-vs-actor collision check. See collide.h. Integer only. */
#include "collide.h"

static collider_t  *at_list[COLLIDE_LIST_MAX], *ac_list[COLLIDE_LIST_MAX],
                   *oc_list[COLLIDE_LIST_MAX];
static unsigned int at_count, ac_count, oc_count;

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
}

static bool push(collider_t **list, unsigned int *count, collider_t *c)
{
    if (!c || *count >= COLLIDE_LIST_MAX)
        return (false);
    list[(*count)++] = c;
    return (true);
}

bool        collide_set_at(collider_t *c)
{
    if (c) c->at_hit = 0;
    return (push(at_list, &at_count, c));
}

bool        collide_set_ac(collider_t *c)
{
    if (c) { c->ac_hit = 0; c->ac_damage = c->ac_effect = 0; }
    return (push(ac_list, &ac_count, c));
}

bool        collide_set_oc(collider_t *c)
{
    if (c) c->oc_hit = 0;
    return (push(oc_list, &oc_count, c));
}

/* World-space cylinder centre (feet) of a cylinder collider. */
static void base(const collider_t *c, int32_t *x, int32_t *y, int32_t *z)
{
    if (c->actor) {
        *x = c->actor->x; *y = c->actor->y; *z = c->actor->z;
    } else {
        *x = c->x; *y = c->y; *z = c->z;
    }
    *y += c->y_shift;
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
    return (false);                     /* capsule vs capsule: not needed */
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

static void at_vs_ac(void)
{
    unsigned int i, j;

    for (i = 0; i < at_count; ++i) {
        collider_t *at = at_list[i];
        for (j = 0; j < ac_count; ++j) {
            collider_t *ac = ac_list[j];
            if (ac->ac_hit || ac->invincible)
                continue;
            if (at->actor && at->actor == ac->actor)
                continue;
            if (!(at->at_type & ac->ac_type) || !(at->at_dmg & ac->ac_bumper))
                continue;
            if (!collide_overlap(at, ac, (int32_t *)0))
                continue;
            at->at_hit = ac;
            ac->ac_hit = at;
            apply_damage(ac, at);
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
            if (!oc_pair_ok(l, r))
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
    if (c->actor) {
        c->actor->x += c->disp_x;
        c->actor->z += c->disp_z;
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
