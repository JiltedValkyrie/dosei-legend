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
#include "oot_core_effects.h"
#include "oot_core_bg.h"
#include "oot_cutscene_camera.h"
#include "oot_core_shop.h"
#include "oot_core_timer.h"

#define OOT_CORE_MAGIC 0x4F4F5443u /* 'OOTC' */
#define OOT_CORE_VERSION 36u
/* Player clip groups: bit order of tools/split_player_bank.py GROUPS. */
#define OOT_CORE_PLAYER_GROUP_HORSE 0
#define OOT_CORE_PLAYER_GROUP_SWIM 1
#define OOT_CORE_PLAYER_GROUP_FISH 2
#define OOT_CORE_PLAYER_GROUP_BOTTLE 3
#define OOT_CORE_PLAYER_GROUP_MAGIC 4
#define OOT_CORE_PLAYER_GROUP_HAMMER 5
#define OOT_CORE_PLAYER_GROUP_BOOM 6
#define OOT_CORE_PLAYER_GROUP_HOOK 7
#define OOT_CORE_TRANSITION_RELOAD 0x10000 /* debug scene has no source entrance */
/* set_flags bits. NPC_SPRITES: generic NPCs are host sprites (NPC views carry
 * object/anim/frame; their Actor_Draw is skipped, no limb matrices). */
#define OOT_CORE_FLAG_NPC_SPRITES 1u
/* Prerendered interior / fixed view: Play_CamIsNotFixed is false. */
#define OOT_CORE_FLAG_FIXED_CAMERA 2u

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
    /* The real flex draw's limb matrices (SkelAnime_DrawFlex, one per limb
     * with a display list, depth first), OoT world space, 12 ints each:
     * 3x3 rotation*scale rows then translation, Q16. NULL if not drawn. */
    const int* mats;
    unsigned char mat_count;
    /* Generic skinned model (N<object><n>.BIN/.SKN, build_core_skins.py):
     * object << 4 | n, 0 = none (Kokiri NPCs use npc_draw's models). */
    unsigned short skin;
    /* Sprite path (OOT_CORE_FLAG_NPC_SPRITES): the actor's object id, its
     * SkelAnime limb count and animation (segment address), frame above. */
    unsigned short object;
    unsigned char limbs;
    unsigned char tint;          /* resident red/blue hit table, 0 = none */
    unsigned int anim;
    unsigned int skeleton;       /* opaque linked key; never dereferenced */
    unsigned short scale_x, scale_y; /* Q8 relative to offline 0.01 scale */
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
    unsigned char alpha;         /* source primitive alpha; 255 by default */
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
    unsigned char owned_sword, owned_shield, equip_sword, equip_shield;
    unsigned char fairy_ocarina, stick_upgrade, nut_upgrade, deku_dungeon_items;
    unsigned short skull_tokens, cutscene_index;
    unsigned int* quest_items;       /* source QUEST_* bits, copied both ways */
    unsigned char* dungeon_items;    /* [20]; legacy C owns Deku entry zero */
    signed char* dungeon_keys;       /* [19]; -1 means no keys collected */
    const unsigned char* bottle_items; /* [4] source ItemId; C Item_Give owns */
    const unsigned char* inventory_items; /* [24], source ItemId */
    const unsigned char* inventory_ammo; /* [16], source slot capacities */
    unsigned short inventory_equipment;
    unsigned int inventory_upgrades;
    unsigned char magic_level,magic,double_defense;
    unsigned char boots; /* PLAYER_BOOTS_KOKIRI/IRON/HOVER (fills old padding) */
    unsigned short* day_time_out;
    unsigned short* skybox_time_out;
    unsigned short entrance_index; /* original EntranceIndex, or 0xffff if unknown */
    unsigned short skybox_time; /* used only when reset_skybox_time is set */
    unsigned char time_blocked; /* host pause/dialogue/game-over gate */
    unsigned char reset_skybox_time; /* 1 explicit sky assignment; 2 frontend session reset */
    unsigned char player_cutscene; /* C player cutscene/game-over ownership for dawn textbox */
    unsigned int* total_days; /* source Save.totalDays; copied both ways */
    unsigned int* bgs_day_count; /* source Save.bgsDayCount; copied both ways */
    /* v28: C-button inventory slots (SLOT_*, 0xFF empty) and tunic
     * (PLAYER_TUNIC_*): the real Player's item buttons and equipment. */
    unsigned char c_slots[3];
    unsigned char tunic;
    unsigned short* cutscene_index_out; /* current source index / pending destination */
    unsigned char* skull_flags; /* source's 24 groups; host has 32 bytes */
    unsigned char* skull_tokens_out; /* source token grants, committed after update */
    unsigned char* ocarina_game_round; /* source playerData.ocarinaGameRoundNum */
} OotCoreSave;

/* Link's tools on the decomp actors (v19, bridge_items.cpp). io is int[6]. */
#define OOT_CORE_TOOL_HAND   0 /* io[0..2] C hand point, world units, each step */
#define OOT_CORE_TOOL_USE    1 /* io[0] ItemId, [1..3] origin, [4] yaw, [5] pitch (+up) */
#define OOT_CORE_TOOL_THROW  2 /* release the held bomb/Bombchu */
#define OOT_CORE_TOOL_STATE  3 /* returns OOT_CORE_TOOL_* bits; PULLING sets io[0..2] Q8 velocity */
#define OOT_CORE_TOOL_CANCEL 4 /* drop held explosive, retract hookshot */
/* v33 host prop adapter. OFFER io: handle,id,x,y,z,yaw,params. READ io:
 * handle,x,y,z,yaw,speedQ8,vyQ8; result 0 idle,1 pickup,2 attached,3 released.
 * Master calls only before kick / after join. */
#define OOT_CORE_TOOL_CARRY_OFFER 5
#define OOT_CORE_TOOL_CARRY_READ  6
#define OOT_CORE_TOOL_CARRY_CANCEL 7 /* host room/reset invalidated the prop */
#define OOT_CORE_TOOL_HOLDING       1u
#define OOT_CORE_TOOL_HOOK_OUT      2u
#define OOT_CORE_TOOL_BOOMERANG_OUT 4u
#define OOT_CORE_TOOL_PULLING       8u
#define OOT_CORE_TOOL_MAGIC_RESET  16u /* Magic_Reset since the last state read */
#define OOT_CORE_TOOL_VIEWS_MAX 8
typedef struct OotCoreToolView {
    short id, params;            /* ACTOR_EN_ARROW/BOM/BOM_CHU/BOOM, ARMS_HOOK */
    unsigned short attack_id;    /* spawn serial; stable across view reordering */
    int x, y, z;                 /* world.pos */
    int previous_x, previous_y, previous_z; /* source sweep start */
    short yaw, pitch;            /* shape.rot.y, pitch +up */
    unsigned short timer;        /* bomb/chu fuse */
    unsigned char held, flash;   /* actually held; bomb flash 0..140 */
    unsigned char damage;        /* source collider fallback; victim tables override */
    int radius;                  /* bomb blast sphere radius, 0 = none */
    unsigned int dmg;            /* AT dmgFlags (C contacts mirror them) */
} OotCoreToolView;

/* One decomp DynaPoly actor (DynaPoly_SetBgActor, v22): its untransformed
 * CollisionHeader data (object blob, cart) and the actor transform, so the C
 * collision (bg_dyna) gets the same mesh. Layouts are the decomp's own POD:
 * vertices Vec3s, polys CollisionPoly (8 halfwords: type, flags_vIA,
 * flags_vIB, vIC, normal xyz (n / 32767), dist), surfaces SurfaceType pairs. */
#define OOT_CORE_DYNA_VIEWS_MAX 16
typedef struct OotCoreDynaView {
    unsigned int key;            /* actor address: stable while it lives */
    const short* vertices;
    const unsigned short* polys;
    const unsigned int* surfaces;
    unsigned short num_vertices, num_polys;
    int x, y, z;                 /* world.pos, Q0 */
    unsigned short rot_y;        /* shape.rot.y */
    unsigned char transform;     /* DYNA_TRANSFORM_* (POS 1, ROT_Y 2) */
    unsigned char enabled;       /* !BGACTOR_COLLISION_DISABLED */
    int scale_q16;               /* actor scale.x, Q16 */
} OotCoreDynaView;

/* Real decomp Player, read once after each update (v28, PLAYER_SOURCE=1).
 * Units are the decomp's (world units, binary angles). */
#define OOT_CORE_PLAYER_JOINTS 67 /* jointTable: root xyz, 21 limb rotations xyz, face */
typedef struct OotCorePlayerView {
    int x, y, z;                 /* actor.world.pos (feet) */
    int focus_x, focus_y, focus_z; /* actor.focus.pos */
    short yaw;                   /* shape.rot.y */
    short room_request;          /* door Room_RequestNewRoom, -1 none; cleared by this read */
    unsigned int state1, state2, state3; /* PLAYER_STATE1/2/3_* */
    short joints[OOT_CORE_PLAYER_JOINTS];
    unsigned char left_hand, right_hand, sheath, waist; /* PLAYER_MODELTYPE_* */
    unsigned char age;           /* LINK_AGE_* the skeleton uses */
    unsigned char boots, tunic, shield; /* currentBoots/Tunic/Shield */
    signed char item_action, held_item; /* heldItemAction, heldItemId */
    unsigned char weapon_state;  /* meleeWeaponState */
    unsigned char ground;        /* BGCHECKFLAG_GROUND */
    unsigned char water;         /* BGCHECKFLAG_WATER */
    unsigned char invincible;    /* invincibilityTimer: flicker while nonzero */
    unsigned char hidden;        /* actor.draw == NULL (start mode NOTHING, some cutscenes) */
    unsigned char held_visual;   /* v33: bit 0 stick visible, bit 1 burning */
    int blade_tip[3], blade_base[3]; /* meleeWeaponInfo[0] tip (posA) / base (posB) */
    unsigned int draw_us;        /* last anchor draw pass (debug overlay) */
    /* v29: Player naviActor (En_Elf FAIRY_NAVI). */
    short navi[3];               /* world.pos */
    unsigned char navi_shown;    /* EnElf_Draw would draw her */
    unsigned char navi_colour;   /* 0 plain, 1 NPC, 2 enemy (focusActor category) */
    /* v30: actor.floorHeight (Link's shadow without a host floor query). */
    int floor_y;
    /* v31: source first-person aim, also used by projectile release. */
    short focus_pitch, focus_yaw;
    unsigned char item_button;   /* source left/down/right = 1/2/3 */
    unsigned char aim_mode;      /* Player unk_6AD: 1 look, 2 item */
    /* v34: Player_UpdateInterface A label, OOT_CORE_DO_* (= DO_ACTION_*). */
    unsigned char do_action;
} OotCorePlayerView;
#define OOT_CORE_DO_THROW 0x09
#define OOT_CORE_DO_NONE  0x0A
#define OOT_CORE_DO_DROP  0x0C
#define OOT_CORE_DO_GRAB  0x11

typedef struct OotCoreSpriteLibrary {
    unsigned short object;
    unsigned int skeleton;
    unsigned char file;
} OotCoreSpriteLibrary;

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
     * spawn is the scene entrance-list index, including special return exits.
     * Player spawns at (x, y, z) facing yaw. Returns 0 on failure. */
    int (*play_init)(void* block, unsigned int bytes, int scene_id, const void* scene, int room, int spawn,
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
     * -1 if none. En_Kanban: OOT_SIGN_INTACT, fade ticks, or zero (hidden). */
    int (*prop_query)(short actor_id, int x, int z);
    /* One debug-panel line: player proxy talk state, message mode, counts. */
    const char* (*debug_text)(void);
    /* Draw items of the last update (Phase 2 shim); returns the count. */
    int (*draw_items)(const OotCoreDrawItem** out);
    /* Meshes the current scene can draw (keep + loaded objects); count. */
    int (*mesh_list)(const OotCoreMeshKey** out);
    /* C camera facing (binary angle, OoT convention). Before update. */
    void (*set_camera)(short yaw);
    /* Second debug line: phase times (0.1 ms) and nearest NPC talk data. */
    const char* (*debug_text2)(void);
    /* Skinned models the current scene can draw (object << 4 | n); count. */
    int (*skin_list)(const unsigned short** out);
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
    /* OOT_CORE_FLAG_* (v16). Call after load; default 0. */
    void (*set_flags)(unsigned int flags);
    /* Shared En_Door/Door_Shutter gate. 0 permitted, positive refusal text.
     * commit applies the source key/switch change only after opening starts. */
    int (*door_action)(unsigned int kind, unsigned int flag, int front_side, unsigned int commit);
    unsigned int (*scene_layer)(void);
    /* Actor/script-owned transition request; -1 absent. Consume after handling. */
    int (*transition_request)(unsigned int consume);
    /* 0 state (active bit0, accepts notes bit1, song+1 byte1), 1 start,
     * 2 consume sounded note+1, 3 consume completed song+1,
     * 4 Sun's Song start allowed, 5 source effect-end/start guard. */
    unsigned int (*ocarina)(unsigned int command);
    int (*tool)(unsigned int command, int* io);
    int (*tool_view)(const OotCoreToolView** out);
    /* Recompute destination variant; current scene_layer remains fixed. */
    unsigned int (*destination_layer)(unsigned int original_base_scene);
    /* low8 sky id, next8 config, bit16 disabled, high8 light mode. */
    unsigned int (*skybox_settings)(void);
    void (*cancel_transition_time)(void); /* failed load: discard pending Sun time */
    /* 0 query; 0x10000|text opens/continues; 0x20000 closes. Result:
     * 1 active, 2 ended, 4 choice accepted with index in bits 8+. */
    unsigned int (*npc_text)(unsigned int command);
    /* Live DynaPoly actors (v22); returns the count, at most
     * OOT_CORE_DYNA_VIEWS_MAX. After update. */
    int (*dyna_view)(const OotCoreDynaView** out);
    /* Caller-owned effect buffer; omitted reports visual overflow only. */
    int (*effect_view)(OotCoreEffectView* out, unsigned int capacity, unsigned int* omitted);
    /* Scene teardown runs while code and object payloads still exist. */
    void (*play_destroy)(void);
    /* Exact-core-bound OAP1, validated before constructors/profile publish. */
    int (*pack_bind)(void* image, unsigned int bytes, unsigned int core_crc);
    /* Refuses release while a PlayState still owns actors/effects. */
    int (*pack_release)(void);
    /* 1 ready, 0 optional OOC absent, -1 failed admission (remain stopped). */
    int (*scene_load)(unsigned int scene, const char* name, unsigned int core_crc,
                      const void* const** objects, unsigned int* count);
    /* Cold scene-only sprite admission runs in the cart with the pack loader.
     * Return loaded libraries; missing counts failed required libraries. */
    unsigned int (*sprite_preload)(const void* scene, const OotCoreSpriteLibrary* rows,
                                   unsigned int count, unsigned char** archives, unsigned int* missing,
                                   unsigned int layer);
    /* UINT_MAX animation queries largest cel; other values select exact clip. */
    const unsigned char* (*sprite_clip)(const unsigned char* archive, unsigned int animation);
    /* Borrowed source WaterBox array (five s16 fields, u32 properties, 16-byte
     * stride). Valid only during this PlayState; no host writes or ownership. */
    unsigned int (*water_boxes)(const void** boxes);
    /* v27: the one collision world (oot_core_bg.h). C bg_* queries go
     * through src/bg_core_shim.c when built with CORE_COLLISION. */
    const OotCoreBgApi* (*bg_api)(void);
    /* v28, real Player (PLAYER_SOURCE=1; NULL in the C Link rollback core).
     * Once at boot, before any play_init: the resident frame bank (PFB2,
     * build_player_frame_bank.py), kept for the session. 1 accepted. */
    int (*player_bank)(const void* bank, unsigned int bytes);
    /* After update: Link's state for the Saturn renderer/camera/HUD. 0 = no Player. */
    int (*player_view)(OotCorePlayerView* out);
    /* A C-side enemy hit Link (temporary until those enemies are decomp):
     * Player_InflictDamage, 1/16 heart units. */
    void (*player_damage)(int damage);
    /* One frame of bank clip `id` (OOT_CORE_PLAYER_JOINTS shorts) for the
     * host's own Link poses; frame clamped to the clip. 0 = not in the bank. */
    int (*player_pose)(unsigned int id, unsigned int frame, short* out);
    /* Saturn Y jump extension: 1 when the Player could jump now. */
    int (*player_jump)(void);
    /* The host moved Link (spawn placement, story events, C pushes): feet
     * position and facing; speed is kept. */
    void (*player_warp)(int x, int y, int z, short yaw);
    /* v35: copy active source subcamera, after update/join. */
    int (*cutscene_camera)(OotCoreCutsceneCameraView* out);
    /* Joined source shop controls and world-space stock cursor. */
    int (*shop_view)(OotCoreShopView* out);
    /* Main host camera seeds actor cutscenes before source Update. */
    void (*camera_seed)(const OotCoreCutsceneCameraView* view);
    void (*timer_view)(OotCoreTimerView* out);
    /* Cold scene admission: host copies retire only when source owns the id. */
    int (*actor_admitted)(unsigned int id);
    /* v36, real Player demand clips (tools/split_player_bank.py). Unregister
     * a demand bank before its memory is freed (no Player consumer may run). */
    void (*player_bank_release)(const void* bank, unsigned int bytes);
    /* Groups (OOT_CORE_PLAYER_GROUP_* bits) registered now. Player_UseItem
     * refuses an item whose group bit is clear: the action waits. */
    void (*player_groups)(unsigned int mask);
} OotCoreEntry;

#endif
