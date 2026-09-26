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
** Integer only. Frame order: collide_begin, register, collide_run. */

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
#define DMG_JUMP_KOKIRI     (1u << 25)
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

typedef enum { COLSHAPE_CYLINDER, COLSHAPE_CAPSULE } collide_shape_t;

typedef struct collider collider_t;

struct collider
{
    actor_t        *actor;
    uint8_t         shape;          /* collide_shape_t */
    uint8_t         mass;           /* MASS_* or 0..253 */
    uint8_t         at_type, ac_type;   /* AT_TYPE_* / AC_TYPE_* */
    uint8_t         oc_flags1, oc_flags2;
    /* cylinder, relative to actor position (or `x,y,z` when no actor) */
    int16_t         radius, height, y_shift;
    int32_t         x, y, z;
    /* capsule: world endpoints + radius */
    int32_t         ax, ay, az, bx, by, bz;
    /* attacker side */
    uint32_t        at_dmg;         /* DMG_* this hitbox deals */
    uint8_t         at_damage;      /* used when target has no table */
    uint8_t         defense;        /* acDmgInfo.defense, no-table path */
    /* hurt side */
    uint32_t        ac_bumper;      /* DMG_* this hurtbox accepts */
    const uint8_t  *damage_table;   /* 32 DMG_ENTRY bytes or 0 */
    uint8_t         invincible;     /* frames; AC ignored while > 0 */
    /* results of the last collide_run */
    collider_t     *at_hit, *ac_hit, *oc_hit;
    uint8_t         ac_damage, ac_effect;
    int32_t         disp_x, disp_z; /* accumulated OC displacement */
};

void    collide_begin(void);
bool    collide_set_at(collider_t *c);
bool    collide_set_ac(collider_t *c);
bool    collide_set_oc(collider_t *c);
void    collide_run(void);

/* Apply and clear OC displacement onto the owning actor. */
void    collide_apply_displacement(collider_t *c);
/* Tick one invincibility frame. */
void    collide_tick(collider_t *c);

/* Exposed for tests / other modules. */
uint32_t collide_isqrt(uint32_t v);
bool    collide_overlap(const collider_t *a, const collider_t *b,
                        int32_t *overlap);

#endif
