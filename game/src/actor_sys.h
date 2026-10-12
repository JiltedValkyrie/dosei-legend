#ifndef ACTOR_SYS_H
#define ACTOR_SYS_H

/* Fixed actor pool, shaped after OoT's ActorContext / ActorProfile
** (include/actor.h, include/actor_profile.h, src/code/z_actor.c).
**
** Platform free: caller supplies storage (Saturn uses high WRAM, with the
** reserved cart carve available via CART_ACTOR_POOL=1; host tests use a
** static buffer). Pool ownership remains on the master CPU.
**
** Room ownership follows Actor_Spawn: an actor spawned by a room's actor list
** carries that room and dies when the room unloads; room ACTOR_ROOM_NONE
** (OoT's -1) survives room changes within the scene. Scene unload kills all
** but ACTOR_FLAG_PERSISTENT (player/Navi-style actors). */

#include <stdbool.h>
#include <stdint.h>

/* M3 worst case (docs/M3A_ACTOR_MANIFEST.md, OPUS_HANDOFF M3 pool budget):
** 49 placed pool actors in spot04 child day/night + 8 Obj_Mure2 children
** = 57, plus runtime drops/Navi/effects reserve. 96 x 72 B (SH-2) = 6,912 B,
** inside the 0x2000 cart carve. A full pool is counted, never silent. */
#define ACTOR_POOL_MAX      96
#define ACTOR_ROOM_NONE     (-1)
#define ACTOR_DATA_WORDS    8

/* OoT ActorCategory order; update runs category by category like
** Actor_UpdateAll. */
typedef enum
{
    ACTORCAT_SWITCH,
    ACTORCAT_BG,
    ACTORCAT_PLAYER,
    ACTORCAT_EXPLOSIVE,
    ACTORCAT_NPC,
    ACTORCAT_ENEMY,
    ACTORCAT_PROP,
    ACTORCAT_ITEMACTION,
    ACTORCAT_MISC,
    ACTORCAT_BOSS,
    ACTORCAT_DOOR,
    ACTORCAT_CHEST,
    ACTORCAT_MAX
}   actor_category_t;

/* Z-target attention kind, shared by Link's targeting and Navi. */
typedef enum
{
    ATTN_NONE,
    ATTN_NPC,
    ATTN_ENEMY,
    ATTN_SIGN,
    ATTN_POI
}   actor_attention_t;

/* sAttentionRanges (z_actor.c): acquisition range and lock-on leash.
** ATTN_RANGE_SLICE_NPC keeps the slice's Kokiri 320/420 until each NPC's
** source attentionRangeType is ported (logged gap). */
typedef enum
{
    ATTN_RANGE_0, ATTN_RANGE_1, ATTN_RANGE_2, ATTN_RANGE_3, ATTN_RANGE_4,
    ATTN_RANGE_5, ATTN_RANGE_6, ATTN_RANGE_7, ATTN_RANGE_8, ATTN_RANGE_9,
    ATTN_RANGE_SLICE_NPC,
    ATTN_RANGE_COUNT
}   actor_attention_range_t;

#define ACTOR_FLAG_PERSISTENT   (1u << 0)   /* survives scene unload */
#define ACTOR_FLAG_TARGETABLE   (1u << 1)   /* OoT ACTOR_FLAG_ATTENTION_ENABLED */
#define ACTOR_FLAG_HOSTILE      (1u << 2)   /* OoT ACTOR_FLAG_HOSTILE (lock-on sound, Battle1) */

typedef struct actor actor_t;
typedef uint32_t actor_handle_t;
#define ACTOR_HANDLE_NONE 0u

typedef struct
{
    uint16_t    id;                         /* project actor id */
    uint8_t     category;                   /* actor_category_t */
    uint8_t     flags;                      /* ACTOR_FLAG_* defaults */
    void      (*init)(actor_t *);
    void      (*update)(actor_t *);
    void      (*draw)(const actor_t *);
    void      (*destroy)(actor_t *);
}   actor_profile_t;

struct actor
{
    const actor_profile_t  *profile;        /* 0 = free slot */
    int32_t     x, y, z;                    /* world units */
    int16_t     focus[3];                   /* focus.pos - world.pos */
    int16_t     arrow_y;                    /* lockOnArrowOffset * scale.y */
    uint16_t    navi_text;                  /* C-Up text while locked (naviEnemyId), 0 none */
    uint16_t    yaw;
    uint16_t    params;
    int8_t      room;                       /* ACTOR_ROOM_NONE = scene wide */
    uint8_t     scene;                      /* SAVE_SCENE_* for flag hooks */
    uint8_t     flags;
    uint8_t     attention;                  /* actor_attention_t */
    uint8_t     kill;                       /* marked; freed after update */
    uint8_t     range;                      /* actor_attention_range_t */
    uint8_t filter_timer, filter_duration, filter_blue, filter_intensity;
    actor_handle_t identity;               /* never reused during this boot */
    int32_t     data[ACTOR_DATA_WORDS];     /* per-type state */
};

/* Bytes the caller must supply. */
unsigned int    actor_sys_bytes(void);
bool            actor_sys_init(void *storage, unsigned int bytes);
/* Spawns refused because the pool was full, since init. */
unsigned int    actor_sys_spawn_failures(void);
void            actor_sys_clear(void);      /* destroy everything */

actor_t        *actor_spawn(const actor_profile_t *profile, unsigned int scene,
                            int room, int32_t x, int32_t y, int32_t z,
                            uint16_t yaw, uint16_t params);
void            actor_kill(actor_t *actor);  /* deferred to end of update */

/* Source color-filter duration in 20 Hz frames; draw strength quantized for VDP1. */
void actor_hit_filter(actor_t *actor, bool blue, unsigned intensity, unsigned frames);
unsigned actor_filter_level(const actor_t *actor); /* 0 none, 1..16 red, 17..32 blue */
void            actor_sys_update(void);
/* Diagnostic: retain empty category passes; normal updates skip them only
 * when no live actor has an update callback. */
extern volatile unsigned actor_update_slow;
void            actor_sys_draw(void);
void            actor_sys_room_unload(int room);
void            actor_sys_scene_unload(void);

unsigned int    actor_sys_live(void);
actor_t        *actor_sys_slot(unsigned int index);  /* 0 when free */
actor_t        *actor_sys_find(uint16_t id, const actor_t *after);
/* Contacts/targets retain handles, not pool pointers. A kill invalidates a
 * handle immediately, including before deferred destruction runs. */
actor_handle_t  actor_handle(const actor_t *actor);
actor_t        *actor_resolve(actor_handle_t handle);

/* Nearest live targetable actor of an attention mask (1 << ATTN_*) within
** `range` on the XZ plane. */
actor_t        *actor_sys_nearest_attention(int32_t x, int32_t y, int32_t z,
                                            int32_t range, unsigned int mask);

/* Attention_ActorIsInRange: distSq < range^2. Leash (ShouldReleaseLockOn):
** distSq * range / leash < range^2, i.e. distSq < range * leash. */
uint32_t        actor_attention_range_sq(const actor_t *actor);
uint32_t        actor_attention_leash_sq(const actor_t *actor);

/* Per-scene flag hooks: Flags_Get/SetTreasure, Switch, Clear, Collectible on
** the actor's own scene. */
bool            actor_get_chest(const actor_t *a, unsigned int flag);
void            actor_set_chest(const actor_t *a, unsigned int flag);
bool            actor_get_switch(const actor_t *a, unsigned int flag);
void            actor_set_switch(const actor_t *a, unsigned int flag);
bool            actor_get_clear(const actor_t *a, unsigned int flag);
void            actor_set_clear(const actor_t *a, unsigned int flag);
bool            actor_get_collect(const actor_t *a, unsigned int flag);
void            actor_set_collect(const actor_t *a, unsigned int flag);

#endif
