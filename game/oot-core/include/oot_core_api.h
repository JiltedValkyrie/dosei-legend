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
#define OOT_CORE_VERSION 12u

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

/* One decomp NPC (ACTORCAT_NPC) for the C npc_draw renderer: the baked
 * Saturn clip of the actor's model is drawn at the decomp skeleton's frame,
 * with the decomp head/torso turn (NpcInteractInfo). Route step 3 shim. */
typedef struct OotCoreNpcView {
    short id, params;
    int x, y, z;                 /* world.pos, Q0 */
    unsigned short yaw;          /* shape.rot.y */
    short head_x, head_y;        /* interactInfo.headRot x (pitch), y (yaw) */
    short torso_x, torso_y;      /* interactInfo.torsoRot */
    unsigned short frame;        /* skelAnime.curFrame, whole frames */
    unsigned char alpha;         /* model alpha (fade), 0 = hidden */
    unsigned char flags;         /* OOT_CORE_VIEW_DRAWN */
} OotCoreNpcView;

/* z_message state for the VDP2 text box (route step 4). The blob lays the
 * decoded page out in character cells; the C side only prints rows. */
#define OOT_CORE_MSG_ROWS 4
#define OOT_CORE_MSG_COLS 38
#define OOT_CORE_MSG_PROMPT_NONE 0
#define OOT_CORE_MSG_PROMPT_NEXT 1   /* triangle: more pages */
#define OOT_CORE_MSG_PROMPT_END  2   /* square: last page */
typedef struct OotCoreMessageView {
    unsigned char active;        /* a text box is on screen */
    unsigned char box_pos;       /* TEXTBOX_POS_* (0 variable, 1 top, 2 middle, 3 bottom) */
    unsigned char rows;          /* rows in use */
    unsigned char prompt;        /* OOT_CORE_MSG_PROMPT_* */
    unsigned char choices;       /* 0, 2 or 3: last rows are the choices */
    unsigned char choice;        /* selected choice */
    unsigned short serial;       /* changes whenever the cells change */
    char text[OOT_CORE_MSG_ROWS][OOT_CORE_MSG_COLS + 1];
    /* Per cell z_message colour index (Message_SetTextColor, 0 = default). */
    unsigned char colour[OOT_CORE_MSG_ROWS][OOT_CORE_MSG_COLS];
} OotCoreMessageView;

/* Phase 2 draw item: one placeholder display list the real draw code called,
 * and the modelview at the call as translate * Ry(yaw) * Rx(pitch) * Rz(roll)
 * * scale (OoT axes, binary angles; scale Q16). kind KEEP: index into
 * keep_ph.txt; kind OBJECT: index into the object's O<id>_ph.txt. */
#define OOT_CORE_DRAW_KEEP   0
#define OOT_CORE_DRAW_OBJECT 1
#define OOT_CORE_DRAW_ITEMS_MAX 96
typedef struct OotCoreDrawItem {
    unsigned short kind, object, index;
    short actor;                 /* actor id */
    short yaw, pitch, roll;
    unsigned char xlu;           /* from the translucent list */
    unsigned char pad;
    int x, y, z;                 /* world units */
    int sx, sy, sz;              /* Q16 */
} OotCoreDrawItem;

/* A prebuilt mesh the scene may draw (K/Q<key>.MSH, build_core_meshes.py). */
typedef struct OotCoreMeshKey {
    unsigned short kind, object, index;
} OotCoreMeshKey;

/* C save <-> gSaveContext. Values are copied in before each update; the
 * flag words and scene flags behind the pointers are copied back after it,
 * so flags the decomp sets reach the C save. Health in 1/16 hearts. Items
 * not listed are ITEM_NONE. Flag words use the decomp layout (save.h). */
#define OOT_CORE_EVENTCHKINF_WORDS 14
#define OOT_CORE_ITEMGETINF_WORDS 4
#define OOT_CORE_INFTABLE_WORDS 30
typedef struct OotCoreSave {
    unsigned short health, health_capacity, rupees;
    unsigned char stick_owned, stick_ammo, nut_owned, nut_ammo;
    unsigned char slingshot_owned, seed_ammo;
    unsigned char link_age;   /* LinkAge: 0 adult, 1 child */
    unsigned char night;      /* nightFlag */
    unsigned short day_time;  /* dayTime, 0x10000 per day */
    unsigned short* event_chk_inf; /* [OOT_CORE_EVENTCHKINF_WORDS] */
    unsigned short* item_get_inf;  /* [OOT_CORE_ITEMGETINF_WORDS] */
    unsigned short* inf_table;     /* [OOT_CORE_INFTABLE_WORDS] */
    /* Current scene's persistent flags: chest, swch, clear, collect (the
     * C save_scene_flags_t order), or NULL when the scene keeps none. */
    unsigned long* scene_flags;
    /* File name, ASCII, space padded (z_message MESSAGE_NAME). */
    char player_name[8];
    /* Not one of the slice scenes: the decomp also spawns (and the Phase 2
     * shim draws) the generic-draw actors, which C owns in slice scenes. */
    unsigned char generic_scene;
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
    /* After play_init: loaded object blobs, objects[i] for scene->objects[i]
     * (NULL = not loaded). Fills the objectCtx slots (Object_GetSlot). */
    void (*set_objects)(const void* const* objects, unsigned int count);
    /* Once after init: ROM nes_message_data_static, resident in the cart. */
    void (*set_text)(const void* data, unsigned int bytes);
    /* N64 controller state for play->state.input[0] (BTN_* bits, held and
     * newly pressed; stick -128..127). Before update. */
    void (*set_input)(unsigned short held, unsigned short press, signed char stick_x, signed char stick_y);
    /* Current text box, laid out (never NULL; active 0 when closed). */
    const OotCoreMessageView* (*message_view)(void);
    /* Live decomp NPCs (ACTORCAT_NPC) into a blob buffer; returns the count. */
    int (*npc_view)(const OotCoreNpcView** out);
    /* Player proxy is talking or a decomp NPC offers talk this frame: the C
     * game must not use A for its own actions (bit 0 talking, bit 1 offer). */
    unsigned int (*talk_state)(void);
    /* OC push the decomp gave the player proxy since the last call (world
     * units, x and z): the C game moves C Link by it. Clears it. */
    void (*player_push)(int* x, int* z);
    /* State word of the live actor `actor_id` nearest (x, z) within 24 units,
     * -1 if none. En_Kanban: partFlags (11 sign pieces, C draws them). */
    int (*prop_query)(short actor_id, int x, int z);
    /* One debug-panel line: player proxy talk state, message mode, counts. */
    const char* (*debug_text)(void);
    /* Draw items of the last update (Phase 2 shim); returns the count. */
    int (*draw_items)(const OotCoreDrawItem** out);
    /* Meshes the current scene can draw (keep + loaded objects); count. */
    int (*mesh_list)(const OotCoreMeshKey** out);
    /* C camera facing (binary angle, OoT convention). Before update. */
    void (*set_camera)(short yaw);
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
