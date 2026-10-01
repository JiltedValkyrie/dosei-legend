#ifndef COLLIDE_H
#define COLLIDE_H

/* Simplified OoT CollisionCheck (src/code/z_collision_check.c,
** include/collision_check.h) for actor-vs-actor contacts only.
**
** AT = attacker hitbox, AC = hurtbox, OC = body push-out. Shapes: vertical
** cylinder (ColliderCylinder) and capsule (sword swept quad stand-in).
** World geometry is NOT here: static/dynamic BG collision is kokiri_collision.
**
** Damage uses OoT's DMG_* bits and the 32-entry DamageTable packing
** DMG_ENTRY(damage, reaction) = damage | reaction << 4. OC push-out follows
** CollisionCheck_SetOCvsOC mass rules (immovable / heavy / normal).
** Integer only. Frame order: collide_begin, register, collide_run.
**
** M2b contact loop. Results live on the colliders and in a bounded event log
** until the next collide_begin. Actor identity in results is a validated
** actor_handle_t: consumers resolve it before use, so a victim killed or a slot
** reused between run and consumption reads as gone, never as a new actor.
** Collider result pointers are only valid inside the step that ran them.
**
** Source rules kept (z_collision_check.c):
** - CollisionCheck_SetATvsAC: an AC_HARD hurtbox marks AT_BOUNCED/AC_BOUNCED
**   when both sides have actors; the contact is still recorded as a hit.
** - One AT may hit several ACs in a pass (multiple victims per attack).
** - Priority is the consumer's job, as in Player's damage check: a bounced
**   shield wins before the body hit is read (collide_guard_blocked), so
**   registration order never decides a guard.
** Port addition: an AT's attack_id (nonzero) makes each victim remember the
** last COLLIDE_SEEN_MAX (attacker, tag, attack) that hit it, so a lingering
** overlap cannot re-hit; a new attack instance can. The memory is bounded: a
** fifth live attack evicts the oldest, which may then hit again. Actor-level
** protection is the source's own: the victim's damage reaction/intangibility
** (Link: `invincible` from gameplay.intangible). Consumers that take damage
** must set that, not rely on this history (BUG-030). */

#include <stdbool.h>
#include <stdint.h>
#include "actor_sys.h"

#define COLLIDE_LIST_MAX    32

/* include/collision_check.h DMG_* bits */
#define DMG_DEKU_NUT        (1u << 0)
#define DMG_DEKU_STICK      (1u << 1)
#define DMG_SLINGSHOT       (1u << 2)
#define DMG_EXPLOSIVE       (1u << 3)
#define DMG_BOOMERANG       (1u << 4)
#define DMG_ARROW_NORMAL    (1u << 5)
#define DMG_HAMMER_SWING    (1u << 6)
#define DMG_HOOKSHOT        (1u << 7)
#define DMG_SLASH_KOKIRI    (1u << 8)
#define DMG_SLASH_MASTER    (1u << 9)
#define DMG_SLASH_GIANT     (1u << 10)
#define DMG_SHIELD          (1u << 20)
#define DMG_MIR_RAY         (1u << 21)
#define DMG_SPIN_KOKIRI     (1u << 22)
#define DMG_SPIN_GIANT      (1u << 23)
#define DMG_SPIN_MASTER     (1u << 24)
#define DMG_JUMP_KOKIRI     (1u << 25)
#define DMG_JUMP_GIANT      (1u << 26)
#define DMG_JUMP_MASTER     (1u << 27)
#define DMG_UNBLOCKABLE     (1u << 29)
#define DMG_DEFAULT         (~(DMG_SHIELD | DMG_MIR_RAY))
#define DMG_ENTRY(damage, reaction) ((uint8_t)((damage) | ((reaction) << 4)))

/* include/actor.h */
#define MASS_IMMOVABLE      0xFF
#define MASS_HEAVY          0xFE

/* ocFlags1 / ocFlags2 subset */
#define OC1_ON              (1u << 0)
#define OC1_NO_PUSH         (1u << 2)
#define OC1_TYPE_PLAYER     (1u << 3)
#define OC1_TYPE_1          (1u << 4)
#define OC1_TYPE_2          (1u << 5)
#define OC1_TYPE_ALL        (OC1_TYPE_PLAYER | OC1_TYPE_1 | OC1_TYPE_2)
#define OC2_TYPE_PLAYER     OC1_TYPE_PLAYER
#define OC2_TYPE_1          OC1_TYPE_1
#define OC2_TYPE_2          OC1_TYPE_2

/* atFlags / acFlags alignment: AT hits AC when they share a type bit. */
#define AT_TYPE_PLAYER      (1u << 3)
#define AT_TYPE_ENEMY       (1u << 4)
#define AT_TYPE_OTHER       (1u << 5)
#define AC_TYPE_PLAYER      AT_TYPE_PLAYER
#define AC_TYPE_ENEMY       AT_TYPE_ENEMY
#define AC_TYPE_OTHER       AT_TYPE_OTHER

#define COLLIDE_EVENT_MAX   32
#define COLLIDE_SEEN_MAX    4

/* acFlags subset kept on the collider. */
#define COL_AC_HARD         (1u << 0)   /* AC_HARD: attacks bounce off */
/* Owned by a source actor that is not in actor_sys (Link, the boulder):
** counts as `actor != NULL` for the AC_HARD bounce rule. */
#define COL_OUTSIDE_ACTOR   (1u << 1)
/* Element of its actor's one multi-element source collider (ColliderJntSph/
** Tris): an AT takes only the first element of that actor per pass, since
** CollisionCheck_AC_*VsJntSph returns after SetATvsAC. Separate source
** colliders (Link's cylinder and shield quad) must NOT set it. */
#define COL_AC_ELEMENT      (1u << 2)
/* result flags */
#define COL_RES_AT_HIT      (1u << 0)
#define COL_RES_AT_BOUNCED  (1u << 1)
#define COL_RES_AC_HIT      (1u << 2)
#define COL_RES_AC_BOUNCED  (1u << 3)

/* COLSHAPE_SECTOR: slice sword stand-in until pose-driven quads (M2c). An
** AT-only wedge at the base point: planar reach `radius`, vertical tolerance
** `height` either way, heading `yaw`, half angle `arc` (binang). It covers the
** whole live window every step, so no step can tunnel past a target. */
typedef enum { COLSHAPE_CYLINDER, COLSHAPE_CAPSULE, COLSHAPE_SECTOR } collide_shape_t;

/* Platform heading helper (atan2(dx, dz) as binang). Saturn: demo_camera.c. */
uint16_t collide_heading(int32_t dx, int32_t dz);

typedef struct collider collider_t;

struct collider
{
    actor_t        *actor;
    uint8_t         shape;          /* collide_shape_t */
    uint8_t         mass;           /* MASS_* or 0..253 */
    uint8_t         at_type, ac_type;   /* AT_TYPE_* / AC_TYPE_* */
    uint8_t         oc_flags1, oc_flags2;
    uint8_t         ac_flags;       /* COL_AC_* */
    uint8_t         result;         /* COL_RES_* from the last collide_run */
    uint16_t        tag;            /* owner's index for actorless colliders */
    uint16_t        yaw, arc;       /* sector heading / half angle */
    /* base point: world x,y,z, or an offset from the owning actor. Sectors
    ** also use it; capsules use their own world endpoints. */
    int16_t         radius, height, y_shift;
    int32_t         x, y, z;
    /* capsule: world endpoints + radius */
    int32_t         ax, ay, az, bx, by, bz;
    /* attacker side */
    uint32_t        at_dmg;         /* DMG_* this hitbox deals */
    uint8_t         at_damage;      /* used when target has no table */
    uint8_t         at_hits;        /* victims this pass (saturates) */
    uint16_t        attack_id;      /* 0 = untracked; else attack instance */
    uint8_t         defense;        /* acDmgInfo.defense, no-table path */
    /* hurt side */
    uint32_t        ac_bumper;      /* DMG_* this hurtbox accepts */
    const uint8_t  *damage_table;   /* 32 DMG_ENTRY bytes or 0 */
    uint8_t         invincible;     /* frames; AC ignored while > 0 */
    /* victim side: recent tracked attacks, oldest overwritten first. Each
    ** entry is one (attacker, tag, attack_id); more than this many distinct
    ** live attacks on one victim at once may re-hit the oldest (tested). */
    struct { actor_handle_t attacker; uint16_t attack, tag; }
                    seen[COLLIDE_SEEN_MAX];
    uint8_t         seen_next;
    /* owner identity captured at registration (collide_set_*): a slot
    ** reused before the run no longer matches, so the collider is skipped */
    actor_handle_t  owner;
    /* results of the last collide_run */
    collider_t     *at_hit, *ac_hit, *oc_hit;  /* this step only */
    actor_handle_t  at_hit_actor, ac_hit_actor, oc_hit_actor;
    uint8_t         ac_damage, ac_effect;
    int32_t         disp_x, disp_z; /* accumulated OC displacement */
};

void    collide_begin(void);
bool    collide_set_at(collider_t *c);
bool    collide_set_ac(collider_t *c);
bool    collide_set_oc(collider_t *c);
void    collide_run(void);

/* One AT-vs-AC contact from the last run, in resolution order. */
typedef struct
{
    actor_handle_t  at_actor, ac_actor;     /* ACTOR_HANDLE_NONE if actorless */
    uint16_t        at_tag, ac_tag;
    uint16_t        attack_id;
    uint8_t         damage, effect;
    uint8_t         bounced;                /* AC_HARD bounce */
    uint8_t         pad;
}   collide_event_t;

unsigned int            collide_event_count(void);
const collide_event_t  *collide_event(unsigned int index);
/* Registrations and events refused since boot/reset because a list was full.
** Nonzero means the frame lost contacts: tests treat it as a failure. */
unsigned int            collide_overflow(void);
void                    collide_overflow_reset(void);
/* Forget a victim's tracked attacks (respawn, or a new life for the slot). */
void                    collide_forget(collider_t *c);

/* Player-style guard check (z_player.c damage update): true when `shield`
** bounced an attack this run, so the body hit must be ignored whatever order
** the two were registered in. */
bool    collide_guard_blocked(const collider_t *shield);

/* Apply and clear OC displacement onto the owning actor. An actor moves
** through collide_world_push, so a push can never carry it into scenery. */
void    collide_apply_displacement(collider_t *c);
/* Platform: move actor `a` by (dx, dz) with world wall/floor checks
** (Saturn: kokiri_collision_move_actor; host tests: a stand-in). */
void    collide_world_push(actor_t *a, int32_t dx, int32_t dz);
/* Tick one invincibility frame. */
void    collide_tick(collider_t *c);

/* Exposed for tests / other modules. */
uint32_t collide_isqrt(uint32_t v);
bool    collide_overlap(const collider_t *a, const collider_t *b,
                        int32_t *overlap);

#endif
