#ifndef ACTOR_SYS_H
#define ACTOR_SYS_H

/* Fixed actor pool, shaped after OoT's ActorContext / ActorProfile
** (include/actor.h, include/actor_profile.h, src/code/z_actor.c).
**
** Platform free: the caller hands in the storage (the Saturn build uses the
** fixed cart carve `ram_cart_fixed`, outside every jo_malloc zone; host tests
** use a static buffer), so nothing here touches jo, SGL or the scarce .bss.
**
** Room ownership follows Actor_Spawn: an actor spawned by a room's actor list
** carries that room and dies when the room unloads; room ACTOR_ROOM_NONE
** (OoT's -1) survives room changes within the scene. Scene unload kills all
** but ACTOR_FLAG_PERSISTENT (player/Navi-style actors). */

#include <stdbool.h>
#include <stdint.h>

#define ACTOR_POOL_MAX      64
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

#define ACTOR_FLAG_PERSISTENT   (1u << 0)   /* survives scene unload */
#define ACTOR_FLAG_TARGETABLE   (1u << 1)   /* OoT ACTOR_FLAG_ATTENTION_ENABLED */

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
    int16_t     focus_y;                    /* focus point above origin */
    uint16_t    yaw;
    uint16_t    params;
    int8_t      room;                       /* ACTOR_ROOM_NONE = scene wide */
    uint8_t     scene;                      /* SAVE_SCENE_* for flag hooks */
    uint8_t     flags;
    uint8_t     attention;                  /* actor_attention_t */
    uint8_t     kill;                       /* marked; freed after update */
    uint8_t     pad;
    actor_handle_t identity;               /* never reused during this boot */
    int32_t     data[ACTOR_DATA_WORDS];     /* per-type state */
};

/* Bytes the caller must supply. */
unsigned int    actor_sys_bytes(void);
bool            actor_sys_init(void *storage, unsigned int bytes);
void            actor_sys_clear(void);      /* destroy everything */

actor_t        *actor_spawn(const actor_profile_t *profile, unsigned int scene,
                            int room, int32_t x, int32_t y, int32_t z,
                            uint16_t yaw, uint16_t params);
void            actor_kill(actor_t *actor);  /* deferred to end of update */

void            actor_sys_update(void);
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
