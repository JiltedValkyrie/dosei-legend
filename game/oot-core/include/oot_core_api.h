/*
 * oot-core blob interface. Shared by C (main loop) and oot-core C++.
 *
 * OOTCORE.BIN starts with OotCoreEntry (oot-core/oot-core.ld, section
 * .oot_entry). The blob is linked at OOT_CORE_LOAD_ADDR (cached cart alias)
 * and is self-contained: the game reaches it only through these pointers,
 * and it reaches the game only through OotCoreHost.
 *
 * Call order: init once after load; play_init per scene; then each frame
 * set_player, update, draw. Units are the decomp's: world units, binary
 * angles (0x10000 = full turn).
 */
#ifndef OOT_CORE_API_H
#define OOT_CORE_API_H

#include "oot_core_bench.h"
#include "oot_core_host.h"

#define OOT_CORE_MAGIC 0x4F4F5443u /* 'OOTC' */
#define OOT_CORE_VERSION 7u

/* PlayState (~78 KB with Fx) + TwoHeadArena + ZeldaArena come from one block
 * the host allocates, so they never take the blob's fixed cart carve. */
#define OOT_CORE_PLAY_THA_BYTES   0x30000u /* bgcheck lookup + scene polys */
#define OOT_CORE_PLAY_ARENA_BYTES 0x20000u /* ZeldaArena: actor instances */

/* One live actor, for the C renderer until the Phase 2 draw shim. */
#define OOT_CORE_VIEW_DRAWN     0x1u /* actor->draw set (object ready) */
#define OOT_CORE_VIEW_GRASS_CUT 0x2u /* ACTOR_FLAG_GRASS_DESTROYED */
typedef struct OotCoreActorView {
    short id, params;
    int x, y, z;          /* world.pos, Q0 */
    unsigned int flags;   /* OOT_CORE_VIEW_* */
} OotCoreActorView;

/* C save -> gSaveContext fields the decomp reads (drop tables, Item00
 * filters). Health in 1/16 hearts. Items not listed are ITEM_NONE. */
typedef struct OotCoreSave {
    unsigned short health, health_capacity, rupees;
    unsigned char stick_owned, stick_ammo, nut_owned, nut_ammo;
    unsigned char slingshot_owned, seed_ammo;
} OotCoreSave;

typedef struct OotCoreEntry {
    unsigned int magic;
    unsigned int version;
    const void* end; /* first address past .bss: must fit the cart carve */
    OotCoreBenchFn bench;
    /* Once after load, before anything else: runs the blob's static ctors
     * and stores the host table (may be NULL). */
    void (*init)(const OotCoreHost* host);
    /* Bytes play_init needs from the host block. */
    unsigned int (*play_bytes)(void);
    /* Per scene. scene_id = decomp SceneId; scene = OotSceneBlob
     * (oot_scene_blob.h, pointers already absolute); room = current room.
     * Player proxy spawns at (x, y, z) facing yaw. Returns 0 on failure. */
    int (*play_init)(void* block, unsigned int bytes, int scene_id, const void* scene, int room,
                     short x, short y, short z, short yaw);
    /* C Link -> player proxy (Q0 world units). Call before update. */
    void (*set_player)(int x, int y, int z, short yaw);
    /* Player entered another room: z_room room change (kills the old
     * room's actors, spawns the new room's list). No-op if unchanged. */
    void (*set_room)(int room);
    /* C sword -> player proxy melee quad (AT, DMG_SLASH_KOKIRI). base/tip
     * = blade line in world units; active 0 = blade not live. Before update. */
    void (*set_sword)(int active, const int* base, const int* tip);
    /* C save mirror into gSaveContext. Before update. */
    void (*set_save)(const OotCoreSave* save);
    /* One game frame: collision checks, Actor_UpdateAll, effects. */
    void (*update)(void);
    /* Actor_DrawAll into the blob's display lists (Phase 2 shim reads them). */
    void (*draw)(void);
    /* Actor_Spawn. Refuses an id whose actor is not imported. Nonzero = ok. */
    int (*spawn)(short actor_id, short params, short x, short y, short z, short rot_y);
    /* Live actors in a category (0..11), for the debug panel. */
    int (*actor_count)(int category);
    /* Copy up to max actors of a category into out; returns the count. */
    int (*actor_view)(int category, OotCoreActorView* out, int max);
} OotCoreEntry;

#endif
