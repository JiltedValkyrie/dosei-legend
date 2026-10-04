/* En_Arrow (seed / thrown nut) and En_M_Fire1. No random drops: neither
 * source actor owns any. World coordinates +Y up; Q8 velocity, 20 Hz source
 * updates sampled at the game's fixed 30 Hz. */
#include "player_items.h"
#include "gameplay.h"
#include "collide.h"
#include "save_state.h"
#include <string.h>
typedef struct {
    int32_t p[3], previous[3], velocity[3], fraction[3];
    uint8_t item, timer, phase;
    bool wall;
    collider_t collider;
} shot_t;
static shot_t shots[PLAYER_SHOTS];
static collider_t flash;
static unsigned flash_ticks, events, serial, cooldown;
/* Last seed impact point, shown briefly (En_Arrow: EffectSsStone1 there). */
static int32_t impact_p[3];
static unsigned impact_ticks;
static bool stick_held;
static unsigned burn_steps;
bool player_items_stick(void) { return stick_held; }
unsigned player_items_burning(void) { return burn_steps; }
void player_items_putaway(void) { stick_held = false; burn_steps = 0; }
void player_items_ignite(void) {
    if (!stick_held) return;
    if (!burn_steps) burn_steps=315;
    else if (burn_steps<300) burn_steps=300;
}
void player_items_extinguish(void) { burn_steps=0; }
void player_items_break_stick(void)
{
    if (stick_held && save_state.stick_ammo) --save_state.stick_ammo;
    player_items_putaway();
}

void player_items_reset(void)
{
    memset(shots, 0, sizeof(shots));
    memset(&flash, 0, sizeof(flash));
    flash_ticks = events = cooldown = impact_ticks = 0;
    player_items_putaway();
    /* Keep attack identity distinct from the last room's victim history. */
    if (++serial > 65535) serial = 1;
}

void player_items_room_changed(void)
{
    bool held = stick_held;
    unsigned burn = burn_steps;
    player_items_reset();
    stick_held = held; burn_steps = burn;
}

static bool use(unsigned item, int32_t x, int32_t y, int32_t z,
                uint16_t yaw, int16_t pitch, bool exact);

bool player_items_use(unsigned item, int32_t x, int32_t y, int32_t z,
                      uint16_t yaw, int16_t pitch)
{
    return use(item, x, y, z, yaw, pitch, false);
}

bool player_items_use_from(unsigned item, const int32_t origin[3],
                           uint16_t yaw, int16_t pitch)
{
    return use(item, origin[0], origin[1], origin[2], yaw, pitch, true);
}

static bool use(unsigned item, int32_t x, int32_t y, int32_t z,
                uint16_t yaw, int16_t pitch, bool exact)
{
    unsigned i;
    int32_t sy, cy, sp, cp;
    shot_t *s;
    if (item == 1) {
        if (!save_state.stick_owned || !save_state.stick_ammo) return false;
        stick_held = true;
        return true;
    }
    if (cooldown) return false;
    if (item == PLAYER_ITEM_SEED) {
        if (!save_state.slingshot || !save_state.ammo_seeds) return false;
    } else if (item == PLAYER_ITEM_NUT) {
        if (!save_state.nut_owned || !save_state.nut_ammo) return false;
        pitch = -0x4000;
    } else return false;
    for (i = 0; i < PLAYER_SHOTS && shots[i].item; ++i) {}
    if (i == PLAYER_SHOTS) return false;
    player_items_putaway();
    s = &shots[i];
    memset(s, 0, sizeof(*s));
    gameplay_sincos(yaw, &sy, &cy);
    gameplay_sincos((uint16_t)pitch, &sp, &cp);
    if (exact) {
        s->p[0] = x; s->p[1] = y; s->p[2] = z;
    } else {
        s->p[0] = x + ((sy * 12) >> 16);
        s->p[1] = y + 35;
        s->p[2] = z + ((cy * 12) >> 16);
    }
    memcpy(s->previous, s->p, sizeof(s->p));
    s->velocity[0] = (int32_t)((int64_t)sy * cp * (80 * 256) >> 32);
    s->velocity[1] = (sp * (80 * 256)) >> 16;
    s->velocity[2] = (int32_t)((int64_t)cy * cp * (80 * 256) >> 32);
    s->item = item;
    s->timer = 15;
    s->collider.shape = COLSHAPE_CAPSULE;
    s->collider.radius = 2;
    s->collider.at_type = AT_TYPE_PLAYER;
    s->collider.at_dmg = DMG_SLINGSHOT;
    s->collider.at_damage = 1;
    s->collider.ac_flags = COL_OUTSIDE_ACTOR;
    s->collider.tag = 0x7100 + i;
    if (++serial > 65535) serial = 1;
    s->collider.attack_id = serial;
    if (item == PLAYER_ITEM_SEED) --save_state.ammo_seeds;
    else --save_state.nut_ammo;
    cooldown = 12;
    if (item == PLAYER_ITEM_SEED) events |= PLAYER_ITEM_FIRE;
    return true;
}

static void impact(shot_t *s)
{
    if (s->item == PLAYER_ITEM_NUT) {
        memset(&flash, 0, sizeof(flash));
        flash.shape = COLSHAPE_CYLINDER;
        flash.radius = flash.height = 200;
        flash.x = s->p[0]; flash.y = s->p[1]; flash.z = s->p[2];
        flash.at_type = AT_TYPE_PLAYER;
        flash.at_dmg = DMG_DEKU_NUT;
        flash.ac_flags = COL_OUTSIDE_ACTOR;
        flash.tag = 0x7110;
        flash.attack_id = s->collider.attack_id;
        flash_ticks = 6; /* four source updates */
        events |= PLAYER_ITEM_FLASH;
    } else {
        events |= PLAYER_ITEM_IMPACT;
        memcpy(impact_p, s->p, sizeof(impact_p));
        impact_ticks = 8;
    }
    s->item = 0;
}

void player_items_step(void)
{
    unsigned i, axis;
    events = 0;
    if (burn_steps && !--burn_steps) player_items_break_stick();
    if (cooldown) --cooldown;
    if (flash_ticks) --flash_ticks;
    if (impact_ticks) --impact_ticks;
    for (i = 0; i < PLAYER_SHOTS; ++i) {
        shot_t *s = &shots[i];
        if (!s->item) continue;
        s->phase += 2;
        if (s->phase >= 3) {
            s->phase -= 3;
            if (!--s->timer) { s->item = 0; continue; }
            if (s->timer < 8) s->velocity[1] -= 102; /* -0.4 */
        }
        for (axis = 0; axis < 3; ++axis) {
            int32_t delta = s->fraction[axis] + s->velocity[axis] * 2;
            s->previous[axis] = s->p[axis];
            s->p[axis] += delta / 768;
            s->fraction[axis] = delta % 768;
        }
        if (player_items_wall(s->previous, s->p, s->item)) {
            /* Keep the clipped seed sweep for the contact pass: an enemy in
             * front of a wall must still be hit. Nuts have no AC collider. */
            if (s->item == PLAYER_ITEM_SEED) s->wall = true;
            else impact(s);
        }
    }
}

void player_items_register(void)
{
    unsigned i;
    for (i = 0; i < PLAYER_SHOTS; ++i) {
        shot_t *s = &shots[i];
        collider_t *c = &s->collider;
        if (s->item != PLAYER_ITEM_SEED) continue;
        c->ax = s->previous[0]; c->ay = s->previous[1]; c->az = s->previous[2];
        c->bx = s->p[0]; c->by = s->p[1]; c->bz = s->p[2];
        c->x = c->bx; c->y = c->by; c->z = c->bz;
        collide_set_at(c);
    }
    if (flash_ticks) collide_set_at(&flash);
}

void player_items_collect(void)
{
    unsigned i;
    for (i = 0; i < PLAYER_SHOTS; ++i)
        if (shots[i].item == PLAYER_ITEM_SEED &&
            (shots[i].wall || (shots[i].collider.result & COL_RES_AT_HIT))) impact(&shots[i]);
}
unsigned player_items_events(void) { unsigned result = events; events = 0; return result; }
unsigned player_items_flash(void) { return flash_ticks; }
unsigned player_items_impact(int32_t *x, int32_t *y, int32_t *z)
{
    if (!impact_ticks) return 0;
    *x = impact_p[0]; *y = impact_p[1]; *z = impact_p[2];
    return impact_ticks;
}
unsigned player_items_body(unsigned slot, int32_t *x, int32_t *y, int32_t *z)
{
    if (slot >= PLAYER_SHOTS || !shots[slot].item) return 0;
    *x = shots[slot].p[0]; *y = shots[slot].p[1]; *z = shots[slot].p[2];
    return shots[slot].item;
}
