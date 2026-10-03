/*
 * oot-core entry table (oot_core_api.h). Init and per-frame order copy
 * z_play.c (Play_Init / Play_Update) for the systems the blob has; the
 * rest (rooms, cutscenes, message, camera, environment) stays with the C
 * game until those files are imported.
 */
#include "oot_prelude.h"
#include "ultra64.h"
#include "actor.h"
#include "array_count.h"
#include "effect.h"
#include "play_state.h"
#include "regs.h"
#include "segmented_address.h"
#include "z_actor_dlftbls.h"
#include "zelda_arena.h"
#include "item.h"
#include "save.h"
#include "oot_core_api.h"
#include "oot_scene_blob.h"

void oot_core_bench_run(OotCoreBench* out, unsigned int (*ticks)(void),
                        unsigned int (*ticks_to_us)(unsigned int));
extern const OotCoreHost* gOotCoreHost;
extern Vec3f gOotCorePlayerPos;
extern s16 gOotCorePlayerYaw;
extern s32 gOotCoreSwordActive;
extern Vec3f gOotCoreSwordBase;
extern Vec3f gOotCoreSwordTip;

/* Linker-script symbols: first address past the blob's .bss; ctor table. */
extern "C" char oot_core_end[];
typedef void (*OotCoreCtor)(void);
extern "C" OotCoreCtor oot_core_ctors_start[], oot_core_ctors_end[];

static RegEditor sRegEditor; /* *REG macros read gRegEditor->data */
static PlayState* sPlay;
static ActorEntry sPlayerEntry;
static const OotSceneBlob* sScene;

/* Room-list actor ids the blob owns; every other id stays with the C game
 * until its overlay is imported (plan Phase 1 step 6). */
static const s16 sRoomActorIds[] = { ACTOR_EN_ITEM00, ACTOR_EN_KUSA };
#define ROOM_ENTRIES_MAX 64
static ActorEntry sRoomEntries[ROOM_ENTRIES_MAX];

/* Scene_CommandActorEntryList for the room's main header, filtered to the
 * imported ids. Actor_UpdateAll spawns play->actorEntryList next frame. */
/* Play_Init: gSaveContext.sceneLayer from cutscene index, age and time. */
static s32 scene_layer(void) {
    if (gSaveContext.save.cutsceneIndex >= 0xFFF0) {
        return SCENE_LAYER_CUTSCENE_FIRST + (gSaveContext.save.cutsceneIndex & 0xF);
    }
    if (!LINK_IS_ADULT) {
        return IS_DAY ? SCENE_LAYER_CHILD_DAY : SCENE_LAYER_CHILD_NIGHT;
    }
    return IS_DAY ? SCENE_LAYER_ADULT_DAY : SCENE_LAYER_ADULT_NIGHT;
}

/* Scene_CommandAlternateHeaderList fallback: an absent layer uses the main
 * header, except adult night, which first tries adult day. */
static const OotSceneLayer* room_layer(int room) {
    const OotSceneLayer* row = &sScene->layers[(u32)room * sScene->num_layers];
    s32 layer = gSaveContext.sceneLayer;

    if (layer > 0 && (u32)layer < sScene->num_layers && row[layer].present) {
        return &row[layer];
    }
    if (layer == SCENE_LAYER_ADULT_NIGHT && SCENE_LAYER_ADULT_DAY < (s32)sScene->num_layers &&
        row[SCENE_LAYER_ADULT_DAY].present) {
        return &row[SCENE_LAYER_ADULT_DAY];
    }
    return &row[0];
}

static void load_room_actors(PlayState* play, int room) {
    const ActorEntry* list;
    const OotSceneLayer* layer;
    u32 i, k, n = 0;

    play->numActorEntries = 0;
    if (sScene == NULL || room < 0 || (u32)room >= sScene->num_rooms || sScene->num_layers == 0) {
        return;
    }
    layer = room_layer(room);
    list = (const ActorEntry*)layer->actors;
    for (i = 0; list != NULL && i < layer->num_actors && n < ROOM_ENTRIES_MAX; i++) {
        for (k = 0; k < ARRAY_COUNT(sRoomActorIds); k++) {
            if ((list[i].id & 0x1FFF) == sRoomActorIds[k]) {
                sRoomEntries[n++] = list[i];
                break;
            }
        }
    }
    play->actorEntryList = sRoomEntries;
    play->numActorEntries = n;
}

static void oot_core_init(const OotCoreHost* host) {
    for (OotCoreCtor* c = oot_core_ctors_start; c != oot_core_ctors_end; ++c) {
        (*c)();
    }
    gOotCoreHost = host;
    gRegEditor = &sRegEditor;
}

#define ALIGN16(n) (((n) + 15u) & ~15u)

static unsigned int oot_core_play_bytes(void) {
    return ALIGN16(sizeof(PlayState)) + OOT_CORE_PLAY_THA_BYTES + OOT_CORE_PLAY_ARENA_BYTES;
}

static int oot_core_play_init(void* block, unsigned int bytes, int scene_id, const void* scene, int room,
                              short x, short y, short z, short yaw) {
    u8* mem = (u8*)(((uintptr_t)block + 15u) & ~(uintptr_t)15u);
    PlayState* play;

    if (block == NULL || bytes < oot_core_play_bytes() + 16u) {
        return 0;
    }
    play = (PlayState*)mem;
    bzero(play, sizeof(PlayState));
    mem += ALIGN16(sizeof(PlayState));
    THA_Init(&play->state.tha, mem, OOT_CORE_PLAY_THA_BYTES);
    mem += OOT_CORE_PLAY_THA_BYTES;
    ZeldaArena_Init(mem, OOT_CORE_PLAY_ARENA_BYTES);

    play->sceneId = scene_id;
    /* Play_Init: the main camera exists; the C camera drives the real view. */
    play->cameraPtrs[CAM_ID_MAIN] = &play->mainCamera;
    play->activeCamId = CAM_ID_MAIN;

    LightContext_Init(play, &play->lightCtx);
    Effect_InitContext(play);
    EffectSs_InitInfo(play, 0x55);
    CollisionCheck_InitContext(play, &play->colChkCtx);
    sScene = (const OotSceneBlob*)scene;
    if (sScene != NULL && sScene->col_header != NULL) {
        BgCheck_Allocate(&play->colCtx, play, (CollisionHeader*)sScene->col_header);
    }
    play->roomCtx.curRoom.num = room;
    play->roomCtx.prevRoom.num = -1;
    /* set_save ran first, so age/time/cutscene index are the C save's. */
    gSaveContext.sceneLayer = scene_layer();

    sPlayerEntry.id = ACTOR_PLAYER;
    sPlayerEntry.pos.x = x;
    sPlayerEntry.pos.y = y;
    sPlayerEntry.pos.z = z;
    sPlayerEntry.rot.x = 0;
    sPlayerEntry.rot.y = yaw;
    sPlayerEntry.rot.z = 0;
    sPlayerEntry.params = 0;
    play->playerEntry = &sPlayerEntry;
    Actor_InitContext(play, &play->actorCtx, play->playerEntry);
    load_room_actors(play, room);

    sPlay = play;
    return GET_PLAYER(play) != NULL;
}

static void oot_core_set_player(int x, int y, int z, short yaw) {
    gOotCorePlayerPos.x = x;
    gOotCorePlayerPos.y = y;
    gOotCorePlayerPos.z = z;
    gOotCorePlayerYaw = yaw;
}

static void oot_core_set_sword(int active, const int* base, const int* tip) {
    gOotCoreSwordActive = active && base != NULL && tip != NULL;
    if (gOotCoreSwordActive) {
        gOotCoreSwordBase.x = base[0];
        gOotCoreSwordBase.y = base[1];
        gOotCoreSwordBase.z = base[2];
        gOotCoreSwordTip.x = tip[0];
        gOotCoreSwordTip.y = tip[1];
        gOotCoreSwordTip.z = tip[2];
    }
}

/* The C save owns these until z_sram/z_parameter are imported. Child
 * Link, no magic, no bomb bag or bow (M3 scope). */
static const OotCoreSave* sHostSave;

/* Flags back to the C save after an update (set_save copied them in). */
static void save_copy_out(PlayState* play) {
    const OotCoreSave* in = sHostSave;
    u32 i;

    if (in == NULL) {
        return;
    }
    for (i = 0; i < OOT_CORE_EVENTCHKINF_WORDS && in->event_chk_inf; i++) {
        in->event_chk_inf[i] = gSaveContext.save.info.eventChkInf[i];
    }
    for (i = 0; i < OOT_CORE_ITEMGETINF_WORDS && in->item_get_inf; i++) {
        in->item_get_inf[i] = gSaveContext.save.info.itemGetInf[i];
    }
    for (i = 0; i < OOT_CORE_INFTABLE_WORDS && in->inf_table; i++) {
        in->inf_table[i] = gSaveContext.save.info.infTable[i];
    }
    if (in->scene_flags) {
        in->scene_flags[0] = play->actorCtx.flags.chest;
        in->scene_flags[1] = play->actorCtx.flags.swch;
        in->scene_flags[2] = play->actorCtx.flags.clear;
        in->scene_flags[3] = play->actorCtx.flags.collect;
    }
}

static void oot_core_set_save(const OotCoreSave* in) {
    SavePlayerData* pd = &gSaveContext.save.info.playerData;
    Inventory* inv = &gSaveContext.save.info.inventory;
    u32 i;

    sHostSave = in;
    if (in == NULL) {
        return;
    }
    gSaveContext.save.linkAge = in->link_age;
    gSaveContext.save.nightFlag = in->night;
    gSaveContext.save.dayTime = in->day_time;
    for (i = 0; i < OOT_CORE_EVENTCHKINF_WORDS && in->event_chk_inf; i++) {
        gSaveContext.save.info.eventChkInf[i] = in->event_chk_inf[i];
    }
    for (i = 0; i < OOT_CORE_ITEMGETINF_WORDS && in->item_get_inf; i++) {
        gSaveContext.save.info.itemGetInf[i] = in->item_get_inf[i];
    }
    for (i = 0; i < OOT_CORE_INFTABLE_WORDS && in->inf_table; i++) {
        gSaveContext.save.info.infTable[i] = in->inf_table[i];
    }
    if (in->scene_flags && sPlay != NULL) {
        sPlay->actorCtx.flags.chest = in->scene_flags[0];
        sPlay->actorCtx.flags.swch = in->scene_flags[1];
        sPlay->actorCtx.flags.clear = in->scene_flags[2];
        sPlay->actorCtx.flags.collect = in->scene_flags[3];
    }
    pd->health = in->health;
    pd->healthCapacity = in->health_capacity;
    pd->rupees = in->rupees;
    pd->magicLevel = 0;
    pd->magic = 0;
    for (i = 0; i < ARRAY_COUNT(inv->items); i++) {
        inv->items[i] = ITEM_NONE;
    }
    if (in->stick_owned) {
        inv->items[SLOT_DEKU_STICK] = ITEM_DEKU_STICK;
    }
    if (in->nut_owned) {
        inv->items[SLOT_DEKU_NUT] = ITEM_DEKU_NUT;
    }
    if (in->slingshot_owned) {
        inv->items[SLOT_SLINGSHOT] = ITEM_SLINGSHOT;
    }
    inv->ammo[SLOT_DEKU_STICK] = in->stick_ammo;
    inv->ammo[SLOT_DEKU_NUT] = in->nut_ammo;
    inv->ammo[SLOT_SLINGSHOT] = in->seed_ammo;
    inv->ammo[SLOT_BOMB] = 0;
    inv->ammo[SLOT_BOW] = 0;
}

/* Room_RequestNewRoom + Room_ProcessRoomRequest (actor list) +
 * Room_FinishRoomChange (old room's actors die), done at once: the C game
 * has already swapped the room geometry. */
static void oot_core_set_room(int room) {
    PlayState* play = sPlay;

    if (play == NULL || room == play->roomCtx.curRoom.num) {
        return;
    }
    play->roomCtx.prevRoom = play->roomCtx.curRoom;
    play->roomCtx.curRoom.num = room;
    load_room_actors(play, room);
    play->roomCtx.prevRoom.num = -1;
    play->roomCtx.prevRoom.segment = NULL;
    func_80031B14(play, &play->actorCtx);
}

static void oot_core_update(void) {
    PlayState* play = sPlay;

    if (play == NULL) {
        return;
    }
    /* Play_Update order. */
    CollisionCheck_AT(play, &play->colChkCtx);
    CollisionCheck_OC(play, &play->colChkCtx);
    CollisionCheck_Damage(play, &play->colChkCtx);
    CollisionCheck_ClearContext(play, &play->colChkCtx);
    Actor_UpdateAll(play, &play->actorCtx);
    Effect_UpdateAll(play);
    EffectSs_UpdateAll(play);
    save_copy_out(play);
    play->gameplayFrames++;
    play->state.frames++;
}

static void oot_core_draw(void) {
    /* Phase 2: Actor_DrawAll needs a GraphicsContext with display-list
     * buffers for the draw shim. Until then actors update but do not draw. */
}

static int oot_core_spawn(short actor_id, short params, short x, short y, short z, short rot_y) {
    if (sPlay == NULL || actor_id < 0 || actor_id >= ACTOR_ID_MAX ||
        gActorOverlayTable[actor_id].profile == NULL) {
        return 0;
    }
    return Actor_Spawn(&sPlay->actorCtx, sPlay, actor_id, x, y, z, 0, rot_y, 0, params) != NULL;
}

static int oot_core_actor_count(int category) {
    if (sPlay == NULL || category < 0 || category >= ACTORCAT_MAX) {
        return 0;
    }
    return sPlay->actorCtx.actorLists[category].length;
}

static int oot_core_actor_view(int category, OotCoreActorView* out, int max) {
    Actor* actor;
    int n = 0;

    if (sPlay == NULL || out == NULL || category < 0 || category >= ACTORCAT_MAX) {
        return 0;
    }
    for (actor = sPlay->actorCtx.actorLists[category].head; actor != NULL && n < max; actor = actor->next) {
        if (actor->update == NULL) {
            continue; /* killed, removed next frame */
        }
        out[n].id = actor->id;
        out[n].params = actor->params;
        out[n].x = (s32)actor->world.pos.x;
        out[n].y = (s32)actor->world.pos.y;
        out[n].z = (s32)actor->world.pos.z;
        out[n].flags = (actor->draw != NULL ? OOT_CORE_VIEW_DRAWN : 0u) |
                       ((actor->flags & ACTOR_FLAG_GRASS_DESTROYED) ? OOT_CORE_VIEW_GRASS_CUT : 0u);
        n++;
    }
    return n;
}

/* First bytes of OOTCORE.BIN (oot-core.ld KEEPs .oot_entry at the load address). */
extern "C" const OotCoreEntry oot_core_entry __attribute__((section(".oot_entry"), used)) = {
    OOT_CORE_MAGIC,
    OOT_CORE_VERSION,
    oot_core_end,
    oot_core_bench_run,
    oot_core_init,
    oot_core_play_bytes,
    oot_core_play_init,
    oot_core_set_player,
    oot_core_set_room,
    oot_core_set_sword,
    oot_core_set_save,
    oot_core_update,
    oot_core_draw,
    oot_core_spawn,
    oot_core_actor_count,
    oot_core_actor_view,
};
