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
#include "oot_core_bg.h"
#include "item.h"
#include "save.h"
#include "message.h"
#include "ocarina.h"
#include "animation.h"
#include "gfx.h"
#include "libu64/pad.h"
#include "controller.h"
#include "object.h"
#include "z_lib.h"
#include "z_math.h"
#include "sys_matrix.h"
#include "player.h"
#include "oot_core_api.h"
#include "oot_scene_blob.h"
#include "environment.h"
#include "frame_advance.h"
#include "scene.h"
#include "interface.h"
#include "audio.h"
#include "sequence.h"
#include "sfx.h"
#include "skybox.h"

u16 gTimeSpeed = 0;
u8 gWeatherMode = WEATHER_MODE_CLEAR;
static const OotCoreSave* sHostSave;
#include "../../build/oot-core/environment_player_gate.inc"
static int OotCore_DayPlayerInCsMode(PlayState* play) {
    return (sHostSave && sHostSave->player_cutscene) || GET_PLAYER(play) == NULL ||
        OotCore_ClockPlayer_InCsMode(play);
}
/* The Saturn music backend does not yet expose the source's 30-frame fade. */
static void OotCore_SunSongAudioFade(u16 frames) { (void)frames; }
static s32 OotCore_ReplaceDayItem(PlayState* play, u16 oldItem, u16 newItem) {
    for (u32 i = 0; i < ARRAY_COUNT(gSaveContext.save.info.inventory.items); ++i) {
        if (gSaveContext.save.info.inventory.items[i] != oldItem) continue;
        /* C owns inventory persistence and C-button icons. The original item
         * backend replaces the trade slot; also update this frame's mirror. */
        if (Item_Give(play, newItem) != ITEM_NONE) return false;
        gSaveContext.save.info.inventory.items[i] = newItem;
        return true;
    }
    return false;
}
#include "../../build/oot-core/environment_clock.inc"

void oot_core_bench_run(OotCoreBench* out, unsigned int (*ticks)(void),
                        unsigned int (*ticks_to_us)(unsigned int));
extern const OotCoreHost* gOotCoreHost;
extern Vec3f gOotCorePlayerPos;
extern s16 gOotCorePlayerYaw;
extern s32 gOotCoreSwordActive;
extern Vec3f gOotCoreSwordBase;
extern Vec3f gOotCoreSwordTip;
extern s32 gOotCorePlayerPushX;
extern s32 gOotCorePlayerPushZ;
/* bridge_message.cpp / oot_core_views.cpp */
void OotCore_SetText(const void* data, u32 bytes);
unsigned int OotCore_Ocarina(unsigned int command);
void OotCore_OcarinaReset(void);
void OotCore_OcarinaScene(PlayState* play);
void OotCore_OcarinaStep(PlayState* play);
void OotCore_NpcTextStep(PlayState* play);
unsigned int OotCore_NpcText(unsigned int command);
GraphicsContext* OotCore_GfxCtx(void);
void OotCore_GfxReset(void);
u32 OotCore_GfxBytes(void);
void OotCore_GfxInit(void* mem);
const OotCoreMessageView* OotCore_MessageView(void);
int OotCore_NpcView(const OotCoreNpcView** out);
unsigned int OotCore_TalkState(void);
int OotCore_PropQuery(short actor_id, int x, int z);
const char* OotCore_DebugText(void);
s32 OotCore_DrawActors(PlayState* play);
int OotCore_DrawItems(const OotCoreDrawItem** out);
const char* OotCore_DebugText2(void);
int OotCore_SkinList(const unsigned short** out);
void OotCore_ProfileReset(void);
/* bridge_items.cpp */
void OotCore_ToolStep(PlayState* play);
void OotCore_ToolReset(void);
int OotCore_ToolCommand(unsigned int command, int* io);
int OotCore_ToolView(const OotCoreToolView** out);
int OotCore_DynaView(const OotCoreDynaView** out);
int OotCore_MeshList(const OotCoreMeshKey** out);
s32 OotCore_IsGenericDraw(s16 id);
static u8 sGenericScene;
static void save_copy_out(PlayState* play);
static void reset_input(void);
extern s16 gOotCoreCamYaw;
static void oot_core_set_camera(short yaw) {
    gOotCoreCamYaw = yaw;
}

/* Linker-script symbols: first address past the blob's .bss; ctor table. */
extern "C" char oot_core_end[];
typedef void (*OotCoreCtor)(void);
extern "C" OotCoreCtor oot_core_ctors_start[], oot_core_ctors_end[];

static RegEditor sRegEditor; /* *REG macros read gRegEditor->data */
PlayState* gOotCorePlay; /* oot_core_views.cpp reads it */
static ActorEntry sPlayerEntry;
static const OotSceneBlob* sScene;

int OotCore_PackBind(void* image, unsigned int bytes, unsigned int core_crc);
int OotCore_PackRelease(void);
int OotCore_SceneLoad(unsigned int scene, const char* name, unsigned int core_crc,
                      const void* const** objects, unsigned int* count);
extern EffectSsInfo sEffectSsInfo;

static void oot_core_play_destroy(void) {
    reset_input();
#ifdef PLAYER_SOURCE
    extern void OotCore_PlayerInputReset(void);
    OotCore_PlayerInputReset();
#endif
    PlayState* play = gOotCorePlay;
    if (!play) return;
    /* Source scene cleanup destroys every actor before its code/objects go.
     * The previous mirror owns these scene words. Global save values already
     * mirrored at the last step may have changed on the host during transition. */
    func_80031C3C(&play->actorCtx, play);
    if (sHostSave && sHostSave->scene_flags) {
        sHostSave->scene_flags[0] = play->actorCtx.flags.chest;
        sHostSave->scene_flags[1] = play->actorCtx.flags.swch;
        sHostSave->scene_flags[2] = play->actorCtx.flags.clear;
        sHostSave->scene_flags[3] = play->actorCtx.flags.collect;
    }
    /* Source ClearAll zeroes table before iterating: delete live entries first. */
    for (s32 i = 0; i < sEffectSsInfo.tableSize; ++i) EffectSs_Delete(&sEffectSsInfo.table[i]);
    EffectSs_ClearAll(play);
    Effect_DeleteAll(play);
    CollisionCheck_ClearContext(play, &play->colChkCtx);
    OotCore_ToolReset();
    OotCore_OcarinaReset();
    OotCore_GfxReset();
    ZeldaArena_Cleanup();
    gOotCorePlay = NULL;
    sScene = NULL;
}

/* Room-list actor ids the blob owns; every other id stays with the C game
 * until its overlay is imported (plan Phase 1 step 6). */
/* 2026-10-03: grass and drops only (NPCs/signs/wonder spots back to C until
 * the 32-bit Fx conversion; their imports stay compiled). */
static const s16 sRoomActorIds[] = { ACTOR_EN_ITEM00, ACTOR_EN_KUSA };
#define ROOM_ENTRIES_MAX 64
static ActorEntry sRoomEntries[ROOM_ENTRIES_MAX];

/* Scene_CommandActorEntryList for the room's main header, filtered to the
 * imported ids. Actor_UpdateAll spawns play->actorEntryList next frame. */
/* Play_Init: gSaveContext.sceneLayer from cutscene index, age and time. */
static void environment_sky_commands(PlayState* play, const OotSceneLayer* layer) {
    if (layer->sky_flags & 1) {
        play->skyboxId = layer->sky_id;
        play->envCtx.skyboxConfig = play->envCtx.changeSkyboxNextConfig = layer->sky_config;
        play->envCtx.lightMode = layer->sky_light;
    }
    if (layer->sky_flags & 2) {
        play->envCtx.skyboxDisabled = (layer->sky_flags >> 2) & 1;
        play->envCtx.sunMoonDisabled = (layer->sky_flags >> 3) & 1;
    }
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

/* Preserve original transition indices: door params address this exact table.
 * Only admit the table when every profile is available, before source spawning
 * can mark an unavailable door as already spawned. Other scenes keep their
 * existing host doors until their own source integration is ready. */
static void load_transition_actors(PlayState* play) {
    play->transitionActors.count = 0;
    play->transitionActors.list = NULL;
    if (!sScene || play->sceneId != SCENE_WATER_TEMPLE || !sScene->num_transition_layers) return;
    const OotSceneLayer* rows = sScene->transitions;
    s32 layer = gSaveContext.sceneLayer;
    const OotSceneLayer* use = &rows[0];
    if (layer > 0 && (u32)layer < sScene->num_transition_layers && rows[layer].present)
        use = &rows[layer];
    else if (layer == SCENE_LAYER_ADULT_NIGHT &&
             SCENE_LAYER_ADULT_DAY < (s32)sScene->num_transition_layers && rows[SCENE_LAYER_ADULT_DAY].present)
        use = &rows[SCENE_LAYER_ADULT_DAY];
    TransitionActorEntry* entries = (TransitionActorEntry*)use->actors;
    if (use->num_actors > 255 || (use->num_actors && !entries)) return;
    for (u32 i = 0; i < use->num_actors; ++i) {
        s32 id = entries[i].id;
        if (id < 0) id = -id; /* source destroy restores this on normal unload */
        id &= 0x1FFF;
        if (id >= ACTOR_ID_MAX || !gActorOverlayTable[id].profile) return;
    }
    for (u32 i = 0; i < use->num_actors; ++i)
        if (entries[i].id < 0) entries[i].id = -entries[i].id;
    play->transitionActors.list = entries;
    play->transitionActors.count = use->num_actors;
}

/* A generic-draw actor id listed in any room of the current scene layer
 * (mesh_list: load only the meshes the scene can use). */
s32 OotCore_SceneHasActor(s16 id) {
    u32 r, i;

    if (sScene == NULL || !sGenericScene) {
        return false;
    }
    for (r = 0; r < sScene->num_rooms; r++) {
        const OotSceneLayer* layer = room_layer(r);
        const ActorEntry* list = (const ActorEntry*)layer->actors;

        for (i = 0; list != NULL && i < layer->num_actors; i++) {
            if ((list[i].id & 0x1FFF) == id) {
                return true;
            }
        }
    }
    return false;
}

static const s16 sGenericNpcIds[] = {
#include "../../build/oot-core/generic_npc_ids.h"
};
static s32 IsGenericNpc(s16 id) {
    u32 i;
    for (i = 1; i < ARRAY_COUNT(sGenericNpcIds); i++) {
        if (sGenericNpcIds[i] == id) {
            return true;
        }
    }
    return false;
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
    environment_sky_commands(play, layer);
    OotCore_EnvironmentRoom(play, layer);
    list = (const ActorEntry*)layer->actors;
    for (i = 0; list != NULL && i < layer->num_actors && n < ROOM_ENTRIES_MAX; i++) {
        for (k = 0; k < ARRAY_COUNT(sRoomActorIds); k++) {
            if ((list[i].id & 0x1FFF) == sRoomActorIds[k]) {
                sRoomEntries[n++] = list[i];
                break;
            }
        }
        /* Generic-draw actors: only where no C copy exists. */
        if (k == ARRAY_COUNT(sRoomActorIds) && sGenericScene && n < ROOM_ENTRIES_MAX &&
            (OotCore_IsGenericDraw(list[i].id & 0x1FFF) || IsGenericNpc(list[i].id & 0x1FFF))) {
            sRoomEntries[n++] = list[i];
        }
        /* Field's source-selected layer owns era/time placement. Dynamic
         * children come from these source actions, never injected here. */
        else if (k == ARRAY_COUNT(sRoomActorIds) && play->sceneId == SCENE_HYRULE_FIELD &&
                 n < ROOM_ENTRIES_MAX) {
            s16 id = list[i].id & 0x1FFF;
            if ((id == ACTOR_EN_ENCOUNT1 || id == ACTOR_EN_SKB ||
                 id == ACTOR_EN_PEEHAT || id == ACTOR_EN_PO_FIELD) &&
                gActorOverlayTable[id].profile != NULL)
                sRoomEntries[n++] = list[i];
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
    /* GameState_Init (game.c): source motion and scaled steps use this rate.
     * Regs_InitData does not set it; zero freezes arrows/hooks in place. */
    R_UPDATE_RATE = 3;
    gSaveContext.nextDayTime = NEXT_TIME_NONE;
    gSaveContext.dogIsLost = true;
    gSaveContext.seqId = (u8)NA_BGM_DISABLED;
    gSaveContext.natureAmbienceId = NATURE_ID_DISABLED;
    gSaveContext.forcedSeqId = NA_BGM_GENERAL_SFX;
    /* No KSEG0 on Saturn: segment 2 maps cart pointers to themselves
     * (SEGMENTED_TO_VIRTUAL, importer fixup). Segment 6 = current object. */
    gSegments[2] = 0x02000000;
}

#define ALIGN16(n) (((n) + 15u) & ~15u)

static unsigned int oot_core_play_bytes(void) {
    return ALIGN16(sizeof(PlayState)) + OOT_CORE_PLAY_THA_BYTES + OOT_CORE_PLAY_ARENA_BYTES +
           ALIGN16(OotCore_GfxBytes());
}

static void seed_scene_save(int scene_id) {
    if (sHostSave == NULL || sHostSave->scene_flags == NULL ||
        (u32)scene_id >= ARRAY_COUNT(gSaveContext.save.info.sceneFlags)) return;
    /* Actor_InitContext reads this table before the first actor init. Updating
     * only actorCtx later lets cleared chests/locks respawn on scene entry. */
    SavedSceneFlags* flags = &gSaveContext.save.info.sceneFlags[scene_id];
    flags->chest = sHostSave->scene_flags[0];
    flags->swch = sHostSave->scene_flags[1];
    flags->clear = sHostSave->scene_flags[2];
    flags->collect = sHostSave->scene_flags[3];
}

static unsigned int sExitCount;
unsigned int OotCore_PlayerExitIndex(unsigned int index) {
    /* Some cutscene headers share collision with longer gameplay exit lists. */
    return index <= sExitCount ? index : 0;
}

static void load_scene_exits(PlayState* play) {
    play->exitList = NULL;
    sExitCount = 0;
    if (!sScene || !sScene->num_exit_layers) return;
    const OotSceneLayer* rows = sScene->exits;
    s32 layer = gSaveContext.sceneLayer;
    const OotSceneLayer* use = &rows[0];
    if (layer > 0 && (u32)layer < sScene->num_exit_layers && rows[layer].present)
        use = &rows[layer];
    else if (layer == SCENE_LAYER_ADULT_NIGHT && SCENE_LAYER_ADULT_DAY < (s32)sScene->num_exit_layers &&
             rows[SCENE_LAYER_ADULT_DAY].present)
        use = &rows[SCENE_LAYER_ADULT_DAY];
    play->exitList = (s16*)use->actors;
    sExitCount = use->num_actors;
}

static int oot_core_play_init(void* block, unsigned int bytes, int scene_id, const void* scene, int room, int spawn,
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
    OotCoreBg_FastReset();
    mem += OOT_CORE_PLAY_ARENA_BYTES;
    OotCore_GfxInit(mem); /* scratch display lists (never executed) */

    play->sceneId = scene_id;
    play->spawn = spawn; /* source special return exits depend on entrance spawn */
    play->state.gfxCtx = OotCore_GfxCtx();
    OotCore_GfxReset();
    /* Slot 0: gameplay_keep, resident (placeholder symbols in the blob).
     * set_objects adds the scene's data objects after it. */
    play->objectCtx.slots[0].id = OBJECT_GAMEPLAY_KEEP;
    play->objectCtx.slots[0].segment = NULL;
    play->objectCtx.numEntries = 1;
    play->objectCtx.numPersistentEntries = 1;
    /* Play_Init: the main camera exists; the C camera drives the real view. */
    play->cameraPtrs[CAM_ID_MAIN] = &play->mainCamera;
    play->activeCamId = CAM_ID_MAIN;

    LightContext_Init(play, &play->lightCtx);
    Effect_InitContext(play);
    EffectSs_InitInfo(play, 0x55);
    Regs_InitData(play);
    Message_Init(play);
    OotCore_OcarinaReset();
    OotCore_ToolReset();
    OotCore_OcarinaScene(play);
    Matrix_Init(&play->state); /* Play_Init: sys_matrix stack (draws, some updates) */
    CollisionCheck_InitContext(play, &play->colChkCtx);
    AnimTaskQueue_Reset(&play->animTaskQueue);
    sScene = (const OotSceneBlob*)scene;
    if (sScene != NULL && sScene->col_header != NULL) {
        BgCheck_Allocate(&play->colCtx, play, (CollisionHeader*)sScene->col_header);
    }
    play->roomCtx.curRoom.num = room;
    play->roomCtx.prevRoom.num = -1;
    /* set_save ran first, so age/time/cutscene index are the C save's. */
    OotCore_TransitionTimeBegin();
    gSaveContext.sceneLayer = OotCore_DestinationLayer(scene_id);
    load_scene_exits(play); /* Player reads exitList while checking floor collision */
    gTimeSpeed = 0;
    /* Sky time belongs to the session. A frozen room may hold it ahead of
     * dayTime; ordinary scene transitions must preserve that source state. */
    gSaveContext.sunsSongState = SUNSSONG_INACTIVE;
    /* Scene_CommandPathList of the scene header the layer runs (Scene_
     * CommandAlternateHeaderList fallback as for the room lists). */
    if (sScene != NULL && sScene->num_path_layers > 0) {
        const OotSceneLayer* paths = sScene->paths;
        s32 layer = gSaveContext.sceneLayer;
        const OotSceneLayer* use = &paths[0];

        if (layer > 0 && (u32)layer < sScene->num_path_layers && paths[layer].present) {
            use = &paths[layer];
        } else if (layer == SCENE_LAYER_ADULT_NIGHT && SCENE_LAYER_ADULT_DAY < (s32)sScene->num_path_layers &&
                   paths[SCENE_LAYER_ADULT_DAY].present) {
            use = &paths[SCENE_LAYER_ADULT_DAY];
        }
        play->pathList = (Path*)use->actors;
        environment_sky_commands(play, use);
        if (use->sound_flags & 1) {
            play->sceneSequences.seqId = use->seq_id;
            play->sceneSequences.natureAmbienceId = use->nature_id;
        }
    }
    OotCore_EnvironmentSkyInit(play);

    sPlayerEntry.id = ACTOR_PLAYER;
    sPlayerEntry.pos.x = x;
    sPlayerEntry.pos.y = y;
    sPlayerEntry.pos.z = z;
    sPlayerEntry.rot.x = 0;
    sPlayerEntry.rot.y = yaw;
    sPlayerEntry.rot.z = 0;
    sPlayerEntry.params = 0;
#ifdef PLAYER_SOURCE
    /* Real Player: arrive standing (or swimming); no title card, no N64
     * scene table entry (loadedScene only feeds the title card). A void-out
     * or respawn set gSaveContext.respawnFlag before this reload; Player_Init
     * consumes it, then Play_Init's reset follows. */
    sPlayerEntry.params = PLAYER_PARAMS(PLAYER_START_MODE_IDLE, PLAYER_START_BG_CAM_DEFAULT);
    {
        static SceneTableEntry sSaturnScene;
        play->loadedScene = &sSaturnScene;
    }
    gSaveContext.showTitleCard = false;
#endif
    play->playerEntry = &sPlayerEntry;
    seed_scene_save(scene_id);
    Actor_InitContext(play, &play->actorCtx, play->playerEntry);
#ifdef PLAYER_SOURCE
    gSaveContext.respawnFlag = 0;
#endif
    load_transition_actors(play);
    Actor_SpawnTransitionActors(play, &play->actorCtx);
    load_room_actors(play, room);
    OotCore_TransitionTimeFinish(play);
    OotCore_DaySequenceInit(play);
    gSaveContext.seqId = play->sceneSequences.seqId;
    gSaveContext.natureAmbienceId = play->sceneSequences.natureAmbienceId;
    save_copy_out(play);

    gOotCorePlay = play;
    return GET_PLAYER(play) != NULL;
}

/* Scene_CommandObjectList outcome: the host loaded each listed object's
 * data blob (linked at segment 6) somewhere in the cart. */
static void oot_core_set_objects(const void* const* objects, unsigned int count) {
    ObjectContext* objectCtx;
    u32 i;

    if (gOotCorePlay == NULL || sScene == NULL || objects == NULL) {
        return;
    }
    objectCtx = &gOotCorePlay->objectCtx;
    objectCtx->numEntries = 1;
    for (i = 0; i < count && i < sScene->num_objects && objectCtx->numEntries < ARRAY_COUNT(objectCtx->slots);
         i++) {
        if (objects[i] == NULL) {
            continue;
        }
        objectCtx->slots[objectCtx->numEntries].id = sScene->objects[i];
        objectCtx->slots[objectCtx->numEntries].segment = (void*)objects[i];
        objectCtx->numEntries++;
    }
    /* Player's object is always resident in OoT (Arms_Hook's profile names
     * it). C draws Link and the tools, so the slot only has to exist. */
    if (Object_GetSlot(objectCtx, OBJECT_LINK_BOY) < 0 && objectCtx->numEntries < ARRAY_COUNT(objectCtx->slots)) {
        static u64 sLinkObjectStub[1];
        objectCtx->slots[objectCtx->numEntries].id = OBJECT_LINK_BOY;
        objectCtx->slots[objectCtx->numEntries].segment = sLinkObjectStub;
        objectCtx->numEntries++;
    }
}

static void oot_core_player_push(int* x, int* z) {
    *x = gOotCorePlayerPushX;
    *z = gOotCorePlayerPushZ;
    gOotCorePlayerPushX = 0;
    gOotCorePlayerPushZ = 0;
}

static Input sHostInput;
/* Retain the last delivered press across idle/release ticks for interaction
 * diagnosis. Written by the core owner; read only after the host joins it. */
unsigned short gOotCoreInputTrace[6];
static s8 sPendingStickY;
static s8 sHeldStickY;   /* PLAYER_SOURCE: the stick as held, for the real Player */

static void reset_input(void) {
    sHostInput = {};
    for (int i = 0; i < 6; ++i) gOotCoreInputTrace[i] = 0;
    sPendingStickY = sHeldStickY = 0;
}

static void oot_core_set_input(unsigned short held, unsigned short press, signed char stick_x, signed char stick_y) {
    press |= (held & ~sHostInput.cur.button) & BTN_R;
    sHostInput.cur.button = held;
    sHostInput.cur.stick_x = stick_x;
    sHostInput.cur.stick_y = stick_y;
    /* Saturn steps the decomp 2 of 3 gameplay steps: keep presses until
     * an update consumes them, or a press on the skipped step is lost. */
    sHostInput.press.button |= press;
    sHostInput.rel.stick_x = stick_x;
    /* A one-step stick flick (menu step) must reach one update, then read as
     * released: Message_HandleChoiceSelection steps on flick, not on hold. */
    if (stick_y != 0) {
        sPendingStickY = stick_y;
    }
    sHeldStickY = stick_y;
}

static void oot_core_set_player(int x, int y, int z, short yaw) {
    gOotCorePlayerPos.x = x;
    gOotCorePlayerPos.y = y;
    gOotCorePlayerPos.z = z;
    gOotCorePlayerYaw = yaw;
}

u32 gOotCoreFlags;
static void oot_core_set_flags(unsigned int flags) {
    gOotCoreFlags = flags;
}

static void oot_core_set_sword(int active, const int* base, const int* tip) {
    /* Points arrive whenever the C blade exists (also between swings): the
     * proxy sweeps from the last idle pose, so the first live step hits. */
    gOotCoreSwordActive = active && base != NULL && tip != NULL;
    if (base != NULL && tip != NULL) {
        gOotCoreSwordBase.x = base[0];
        gOotCoreSwordBase.y = base[1];
        gOotCoreSwordBase.z = base[2];
        gOotCoreSwordTip.x = tip[0];
        gOotCoreSwordTip.y = tip[1];
        gOotCoreSwordTip.z = tip[2];
    }
}

/* The C save owns the supported inventory until z_sram/z_parameter are
 * imported. Unsupported items remain absent, rather than implied by an era. */

/* Flags back to the C save after an update (set_save copied them in). */
static void save_copy_out(PlayState* play) {
    const OotCoreSave* in = sHostSave;
    u32 i;

    if (in == NULL) {
        return;
    }
    if (in->day_time_out) *in->day_time_out = gSaveContext.save.dayTime;
    if (in->skybox_time_out) *in->skybox_time_out = gSaveContext.skyboxTime;
    if (in->total_days) *in->total_days = gSaveContext.save.totalDays;
    if (in->bgs_day_count) *in->bgs_day_count = gSaveContext.save.bgsDayCount;
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
    if (in->quest_items) *in->quest_items = gSaveContext.save.info.inventory.questItems;
    /* The legacy C dungeon code owns entry zero's map/compass. Other dungeon
     * state and consumed keys belong to the source actors/door transactions. */
    for (i = 1; i < 20 && in->dungeon_items; i++)
        in->dungeon_items[i] = gSaveContext.save.info.inventory.dungeonItems[i];
    for (i = 0; i < 19 && in->dungeon_keys; i++)
        in->dungeon_keys[i] = gSaveContext.save.info.inventory.dungeonKeys[i];
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
    /* A room time command does not recalculate nightFlag until the source
     * environment update. Do not overwrite that state on each host mirror. */
    if (in->reset_skybox_time || gSaveContext.save.dayTime != in->day_time)
        gSaveContext.save.nightFlag = in->night;
    gSaveContext.save.dayTime = in->day_time;
    if (in->total_days) gSaveContext.save.totalDays = *in->total_days;
    if (in->bgs_day_count) gSaveContext.save.bgsDayCount = *in->bgs_day_count;
    gSaveContext.save.entranceIndex = in->entrance_index;
    if (in->reset_skybox_time) gSaveContext.skyboxTime = in->skybox_time;
    if (in->reset_skybox_time == 2) {
        gSaveContext.nextDayTime = NEXT_TIME_NONE;
        gSaveContext.sunsSongState = SUNSSONG_INACTIVE;
        gSaveContext.dogIsLost = true;
        gSaveContext.seqId = (u8)NA_BGM_DISABLED;
        gSaveContext.natureAmbienceId = NATURE_ID_DISABLED;
        gSaveContext.forcedSeqId = NA_BGM_GENERAL_SFX;
        gSaveContext.retainWeatherMode = false;
        gWeatherMode = WEATHER_MODE_CLEAR;
    }
    gSaveContext.save.cutsceneIndex = in->cutscene_index;
    for (i = 0; i < OOT_CORE_EVENTCHKINF_WORDS && in->event_chk_inf; i++) {
        gSaveContext.save.info.eventChkInf[i] = in->event_chk_inf[i];
    }
    for (i = 0; i < OOT_CORE_ITEMGETINF_WORDS && in->item_get_inf; i++) {
        gSaveContext.save.info.itemGetInf[i] = in->item_get_inf[i];
    }
    for (i = 0; i < OOT_CORE_INFTABLE_WORDS && in->inf_table; i++) {
        gSaveContext.save.info.infTable[i] = in->inf_table[i];
    }
    if (in->scene_flags && gOotCorePlay != NULL) {
        gOotCorePlay->actorCtx.flags.chest = in->scene_flags[0];
        gOotCorePlay->actorCtx.flags.swch = in->scene_flags[1];
        gOotCorePlay->actorCtx.flags.clear = in->scene_flags[2];
        gOotCorePlay->actorCtx.flags.collect = in->scene_flags[3];
    }
    gSaveContext.language = LANGUAGE_ENG;
    sGenericScene = in->generic_scene;
    /* MESSAGE_NAME: ASCII -> file name charset (Message_Decode reverses it). */
    for (i = 0; i < ARRAY_COUNT(pd->playerName); i++) {
        char ch = in->player_name[i];
        pd->playerName[i] = (ch >= '0' && ch <= '9')   ? FILENAME_DIGIT(ch)
                            : (ch >= 'A' && ch <= 'Z') ? FILENAME_UPPERCASE(ch)
                            : (ch >= 'a' && ch <= 'z') ? FILENAME_LOWERCASE(ch)
                            : (ch == '-')              ? FILENAME_DASH
                            : (ch == '.')              ? FILENAME_PERIOD
                                                       : FILENAME_SPACE;
    }
    pd->health = in->health;
    pd->healthCapacity = in->health_capacity;
    pd->rupees = in->rupees;
    pd->magicLevel = in->magic_level;
    pd->magic = in->magic;
    pd->isMagicAcquired = in->magic_level != 0;
    pd->isDoubleMagicAcquired = in->magic_level >= 2;
    pd->isDoubleDefenseAcquired = in->double_defense != 0;
    pd->bgsFlag = (in->inventory_equipment & 4) != 0;
    inv->defenseHearts = in->double_defense ? 20 : 0;
    for (i = 0; i < ARRAY_COUNT(inv->items); i++) {
        inv->items[i] = in->inventory_items ? in->inventory_items[i] : ITEM_NONE;
    }
    for (i = 0; i < ARRAY_COUNT(inv->ammo); i++)
        inv->ammo[i] = in->inventory_ammo ? in->inventory_ammo[i] : 0;
    if (in->stick_owned) {
        inv->items[SLOT_DEKU_STICK] = ITEM_DEKU_STICK;
    }
    if (in->nut_owned) {
        inv->items[SLOT_DEKU_NUT] = ITEM_DEKU_NUT;
    }
    if (in->slingshot_owned) {
        inv->items[SLOT_SLINGSHOT] = ITEM_SLINGSHOT;
    }
    if (in->fairy_ocarina && inv->items[SLOT_OCARINA] != ITEM_OCARINA_OF_TIME)
        inv->items[SLOT_OCARINA] = ITEM_OCARINA_FAIRY;
    for (i = 0; i < 4 && in->bottle_items; i++)
        inv->items[SLOT_BOTTLE_1 + i] = in->bottle_items[i];
    /* z_inventory: equipped nibbles are values; inventory nibbles are bits.
     * C tunic colours are cosmetic, not Goron/Zora equipment grants. */
    inv->equipment = 0x1100 | in->inventory_equipment;
    if (in->owned_sword >= 1 && in->owned_sword <= 3)
        inv->equipment |= 1u << (in->owned_sword - 1);
    if (in->owned_shield >= 1 && in->owned_shield <= 3)
        inv->equipment |= 1u << (in->owned_shield + 3);
    gSaveContext.save.info.equips.equipment = 0x0100 | (((in->boots > 2 ? 0 : in->boots) + 1) << 12) |
        (in->equip_sword & 3) | ((in->equip_shield & 3) << 4);
    inv->questItems = in->quest_items ? *in->quest_items : 0;
    inv->gsTokens = in->skull_tokens;
    inv->upgrades = (in->inventory_upgrades & ~0x007e0000u) |
        ((u32)(in->stick_upgrade & 3) << 17) | ((u32)(in->nut_upgrade & 3) << 20);
    if (in->slingshot_owned && !(inv->upgrades & 0x0001c000u)) inv->upgrades |= 1u << 14;
    for (i = 0; i < ARRAY_COUNT(inv->dungeonItems); i++)
        inv->dungeonItems[i] = in->dungeon_items ? in->dungeon_items[i] : 0;
    /* Legacy C packs compass/map at bits 0/1; source uses bits 1/2. */
    inv->dungeonItems[0] = (in->deku_dungeon_items & 3) << 1;
    for (i = 0; i < ARRAY_COUNT(inv->dungeonKeys); i++)
        inv->dungeonKeys[i] = in->dungeon_keys ? in->dungeon_keys[i] : -1;
    inv->ammo[SLOT_DEKU_STICK] = in->stick_ammo;
    inv->ammo[SLOT_DEKU_NUT] = in->nut_ammo;
    inv->ammo[SLOT_SLINGSHOT] = in->seed_ammo;
    /* B is the equipped sword, C buttons the host's assignments (source
     * buttonItems/cButtonSlots): the real Player uses items from these. */
    {
        static const u8 swords[4] = { ITEM_NONE, ITEM_SWORD_KOKIRI, ITEM_SWORD_MASTER, ITEM_SWORD_BIGGORON };
        ItemEquips* eq = &gSaveContext.save.info.equips;
        eq->buttonItems[0] = swords[in->equip_sword & 3];
        for (i = 0; i < 3; i++) {
            /* Host/HUD: down, left, right. Source: left, down, right. */
            u8 slot = in->c_slots[i < 2 ? 1 - i : i];
            eq->cButtonSlots[i] = slot;
            eq->buttonItems[i + 1] = slot < ARRAY_COUNT(inv->items) ? inv->items[slot] : ITEM_NONE;
        }
        eq->equipment = (eq->equipment & ~0x0F00) | (((in->tunic > 2 ? 0 : in->tunic) + 1) << 8);
#ifdef PLAYER_SOURCE
        /* KaleidoScope's equip path: the real Player re-reads its sword,
         * shield, tunic and boots when the pause menu changed them. */
        {
            static u16 sLastEquips = 0xFFFF;
            Player* player = gOotCorePlay != NULL ? GET_PLAYER(gOotCorePlay) : NULL;
            if (eq->equipment != sLastEquips && player != NULL) {
                Player_SetEquipmentData(gOotCorePlay, player);
            }
            sLastEquips = player != NULL ? eq->equipment : 0xFFFF;
        }
#endif
    }
}

/* Room_RequestNewRoom + Room_ProcessRoomRequest (actor list) +
 * Room_FinishRoomChange (old room's actors die), done at once: the C game
 * has already swapped the room geometry. */
static void oot_core_set_room(int room) {
    PlayState* play = gOotCorePlay;

    if (play == NULL || room == play->roomCtx.curRoom.num) {
        return;
    }
    play->roomCtx.prevRoom = play->roomCtx.curRoom;
    play->roomCtx.curRoom.num = room;
    load_room_actors(play, room);
    save_copy_out(play);
    play->roomCtx.prevRoom.num = -1;
    play->roomCtx.prevRoom.segment = NULL;
    func_80031B14(play, &play->actorCtx);
    Actor_SpawnTransitionActors(play, &play->actorCtx);
}

/* Actor_DrawAll's culling pass (Actor_CullingCheck) is what sets
 * ACTOR_FLAG_INSIDE_CULLING_VOLUME, and Actor_UpdateAll only updates an actor
 * with that flag or UPDATE_CULLING_DISABLED. Actor_DrawAll does not run yet
 * (Phase 2), so without this an actor such as En_Kusa stops updating once it
 * clears UPDATE_CULLING_DISABLED. APPROXIMATE: a sphere around the player of
 * the actor's culling distance (projected z ~ world distance for the default
 * view), no frustum sides. */
static void OotCore_CullActors(PlayState* play) {
    Player* player = GET_PLAYER(play);
    s32 i;

    if (player == NULL) {
        return;
    }
    for (i = 0; i < ACTORCAT_MAX; i++) {
        Actor* actor;

        for (actor = play->actorCtx.actorLists[i].head; actor != NULL; actor = actor->next) {
            f32 dx = actor->world.pos.x - player->actor.world.pos.x;
            f32 dy = actor->world.pos.y - player->actor.world.pos.y;
            f32 dz = actor->world.pos.z - player->actor.world.pos.z;
            f32 range = actor->cullingVolumeDistance + actor->cullingVolumeScale;

            if (SQ(dx) + SQ(dy) + SQ(dz) < SQ(range)) { /* no sqrt per actor per step */
                actor->flags |= ACTOR_FLAG_INSIDE_CULLING_VOLUME;
            } else {
                actor->flags &= ~ACTOR_FLAG_INSIDE_CULLING_VOLUME;
            }
        }
    }
}

/* Per-phase decomp step time, us (debug row 16): collision checks, actor
 * update, message, draw. */
u32 gOotCorePhaseUs[4];
static u32 Phase_Now(void) {
    return (gOotCoreHost != NULL && gOotCoreHost->ticks != NULL) ? gOotCoreHost->ticks() : 0;
}
static u32 Phase_Us(u32 t0) {
    return (gOotCoreHost != NULL && gOotCoreHost->ticks_to_us != NULL) ? gOotCoreHost->ticks_to_us(Phase_Now() - t0)
                                                                        : 0;
}
u32 OotCore_PhaseNow(void) {
    return Phase_Now();
}
u32 OotCore_PhaseUs(u32 t0) {
    return Phase_Us(t0);
}

static void consume_input(PlayState* play) {
    sHostInput.rel.stick_y = sPendingStickY;
    sHostInput.cur.stick_y = sPendingStickY;
#ifdef PLAYER_SOURCE
    /* Walking reads the held stick; only text choices step on a flick. */
    if (play->msgCtx.msgMode == MSGMODE_NONE) {
        sHostInput.rel.stick_y = sHostInput.cur.stick_y = sHeldStickY;
    }
#endif
    sPendingStickY = 0;
    play->state.input[0] = sHostInput;
    /* A short press may already be released by a later host step. Give it
     * one source frame held; derive releases against the last consumed pad,
     * not against another 30 Hz host sample. */
    play->state.input[0].cur.button |= sHostInput.press.button;
#ifdef PLAYER_SOURCE
    {
        extern void OotCore_PlayerInput(PlayState*, Input*);
        OotCore_PlayerInput(play, &play->state.input[0]);
    }
#endif
    play->state.input[0].rel.button = sHostInput.prev.button & ~play->state.input[0].cur.button;
    sHostInput.prev = play->state.input[0].cur;
    if (play->state.input[0].press.button) {
        Player* player = GET_PLAYER(play);
        gOotCoreInputTrace[0] = play->state.input[0].press.button;
        gOotCoreInputTrace[1] = play->state.input[0].cur.button;
        gOotCoreInputTrace[2] = player ? (u8)player->heldItemId : 0xFF;
        gOotCoreInputTrace[3] = player ? (u8)player->heldItemAction : 0xFF;
        gOotCoreInputTrace[4] = player && player->talkActor ? (u16)player->talkActor->id : 0xFFFF;
        gOotCoreInputTrace[5] = player ? player->actor.bgCheckFlags & BGCHECKFLAG_GROUND : 0;
    }
    sHostInput.press.button = 0;
}

static void oot_core_update(void) {
    PlayState* play = gOotCorePlay;
    u32 t0;

    if (play == NULL) {
        return;
    }
    consume_input(play);
    OotCore_OcarinaStep(play);
    /* Play_Update order. */
    AnimTaskQueue_Reset(&play->animTaskQueue);
    t0 = Phase_Now();
    CollisionCheck_AT(play, &play->colChkCtx);
    CollisionCheck_OC(play, &play->colChkCtx);
    CollisionCheck_Damage(play, &play->colChkCtx);
    CollisionCheck_ClearContext(play, &play->colChkCtx);
    gOotCorePhaseUs[0] = Phase_Us(t0);
    t0 = Phase_Now();
    OotCore_ProfileReset();
    OotCore_CullActors(play);
    Actor_UpdateAll(play, &play->actorCtx);
    OotCore_ToolStep(play);
    Effect_UpdateAll(play);
    EffectSs_UpdateAll(play);
    gOotCorePhaseUs[1] = Phase_Us(t0);
    t0 = Phase_Now();
    OotCore_NpcTextStep(play);
    Message_Update(play);
    OotCore_SunSongUpdate(play);
    OotCore_EnvironmentEvents(play);
    if (!sHostSave || !sHostSave->time_blocked) OotCore_EnvironmentClock(play);
    AnimTaskQueue_Update(play, &play->animTaskQueue);
    /* Play_Draw's Message_Draw: it advances the text reveal (textDrawPos)
     * and page state; its display list goes to a scratch buffer. */
    OotCore_GfxReset();
    gOotCorePhaseUs[2] = Phase_Us(t0);
    t0 = Phase_Now();
    OotCore_DrawActors(play);
#ifdef PLAYER_SOURCE
    {
        extern void OotCore_CarryAfter(PlayState*);
        OotCore_CarryAfter(play);
    }
#endif
    {
        bool revealing = play->msgCtx.msgMode == MSGMODE_TEXT_DISPLAYING;
        Message_Draw(play);
        /* Two reveal ticks, but never accelerate page waits, choices, fades
         * or Ocarina. The source parser still handles every control byte. */
        if (revealing && play->msgCtx.msgMode == MSGMODE_TEXT_DISPLAYING) {
            OotCore_GfxReset();
            Message_Draw(play);
        }
    }
    gOotCorePhaseUs[3] = Phase_Us(t0);
    save_copy_out(play);
    play->gameplayFrames++;
    play->state.frames++;
}

/* The C press that fired a tool must not reach the actor this step:
 * Arms_Hook retracts on any A/B/R/C press while it flies. */
static int oot_core_tool(unsigned int command, int* io) {
    int result = OotCore_ToolCommand(command, io);
    if (command == OOT_CORE_TOOL_USE && result)
        sHostInput.press.button = 0;
    return result;
}

static unsigned int oot_core_npc_text(unsigned int command) {
    unsigned int result=OotCore_NpcText(command);
    if ((command & 0x10000u) && result) sHostInput.press.button=0;
    return result;
}

static void oot_core_draw(void) {
    /* Phase 2: Actor_DrawAll into the shim. Message_Draw runs in update. */
}

static int oot_core_spawn(short actor_id, short params, short x, short y, short z, short rot_y) {
    if (gOotCorePlay == NULL || actor_id < 0 || actor_id >= ACTOR_ID_MAX ||
        gActorOverlayTable[actor_id].profile == NULL) {
        return 0;
    }
    return Actor_Spawn(&gOotCorePlay->actorCtx, gOotCorePlay, actor_id, x, y, z, 0, rot_y, 0, params) != NULL;
}

static int oot_core_actor_count(int category) {
    if (gOotCorePlay == NULL || category < 0 || category >= ACTORCAT_MAX) {
        return 0;
    }
    return gOotCorePlay->actorCtx.actorLists[category].length;
}

static int oot_core_actor_view(int category, OotCoreActorView* out, int max) {
    Actor* actor;
    int n = 0;

    if (gOotCorePlay == NULL || out == NULL || category < 0 || category >= ACTORCAT_MAX) {
        return 0;
    }
    for (actor = gOotCorePlay->actorCtx.actorLists[category].head; actor != NULL && n < max; actor = actor->next) {
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

/* Shared source door policy. En_Door_SetupType/Idle and
 * DoorShutter_SetupDoor/Idle; rendering and the opening clock stay host-side.
 * Boss encounter bars/block actors (types 4/6) remain encounter-owned. */
static int oot_core_door_action(unsigned int kind, unsigned int data, int front_side, unsigned int commit) {
    PlayState* play = gOotCorePlay;
    unsigned int flag = data & 63u;
    int key = 0, boss = 0;
    int dungeon;
    if (play == NULL) return 0xFF00;
    dungeon = play->sceneId;
    /* Scene IDs 0..9 are the ten source dungeons; boss scenes 17..24 map
     * back to their dungeon. Ganon's boss room inherits the tower key slot. */
    if (dungeon >= SCENE_DEKU_TREE_BOSS && dungeon <= SCENE_SHADOW_TEMPLE_BOSS)
        dungeon -= SCENE_DEKU_TREE_BOSS;
    if (play->sceneId == SCENE_GANONS_TOWER || play->sceneId == SCENE_GANONDORF_BOSS)
        dungeon = SCENE_GANONS_TOWER;
    if (kind >= 24 && kind < 32) {
        unsigned int type = kind - 24;
        if (type == 6) {
            /* Strict source window: 18:00 < dayTime < 21:00. */
            type = gSaveContext.save.dayTime > 0xC000 && gSaveContext.save.dayTime < 0xE000 ? 3 : 5;
        }
        if (type == 5) {
            if (flag != 0x29 || GET_EVENTCHKINF(EVENTCHKINF_TALON_RETURNED_FROM_CASTLE))
                return 0x200 + flag;
        }
        key = type == 1;
    } else if (kind >= 8 && kind < 24) {
        unsigned int type = kind - 8;
        if (type == 4 || type == 6 || type == 8 || type == 9 || type == 10 || type > 11)
            return 0xFF00;
        if (front_side && type != 11) type = type == 7 ? 1 : type == 5 ? 3 : 0;
        if (type == 1 && !Flags_GetClear(play, play->roomCtx.curRoom.num)) {
            if (!Flags_GetTempClear(play, play->roomCtx.curRoom.num)) return 0xFF00;
            /* DoorShutter_WaitClear promotes the last enemy's temporary flag. */
            Flags_SetClear(play, play->roomCtx.curRoom.num);
            save_copy_out(play);
        }
        if ((type == 2 || type == 7) && !Flags_GetSwitch(play, flag)) return 0xFF00;
        if (type == 3) return 0xFF00;
        key = type == 11;
        boss = type == 5;
    } else return 0xFF00;
    if ((key || boss) && !Flags_GetSwitch(play, flag)) {
        if (dungeon < 0 || dungeon >= (int)ARRAY_COUNT(gSaveContext.save.info.inventory.dungeonKeys))
            return boss ? 0x204 : 0x203;
        if (boss) {
            if (!(gSaveContext.save.info.inventory.dungeonItems[dungeon] & 1u)) return 0x204;
        } else if (gSaveContext.save.info.inventory.dungeonKeys[dungeon] <= 0) return 0x203;
        if (commit) {
            if (key) --gSaveContext.save.info.inventory.dungeonKeys[dungeon];
            Flags_SetSwitch(play, flag);
            save_copy_out(play);
        }
    }
    return 0;
}

static unsigned int oot_core_current_layer(void) {
    return gOotCorePlay ? (unsigned int)gSaveContext.sceneLayer : 0;
}

static unsigned int oot_core_skybox_settings(void) {
    PlayState* play = gOotCorePlay;
    if (!play) return 0;
    return ((unsigned int)play->skyboxId & 255u) |
        ((unsigned int)play->envCtx.skyboxConfig << 8) |
        ((unsigned int)(play->envCtx.skyboxDisabled != 0) << 16) |
        ((unsigned int)play->envCtx.lightMode << 24);
}

static void oot_core_cancel_transition_time(void) {
    /* The host may already have replaced the play arena on a failed load.
     * Touch only session globals, never the old PlayState. */
    gSaveContext.nextDayTime = NEXT_TIME_NONE;
    gSaveContext.respawnFlag = 0;
    gSaveContext.sunsSongState = SUNSSONG_INACTIVE;
}

static int oot_core_transition_request(unsigned int consume) {
    PlayState* play = gOotCorePlay;
    int entrance;
    if (!play || play->transitionTrigger != TRANS_TRIGGER_START) return -1;
    entrance = play->nextEntranceIndex;
    if (entrance == 0xffff && gSaveContext.respawnFlag == -2)
        entrance = OOT_CORE_TRANSITION_RELOAD; /* level select has no source entrance */
    if (consume) play->transitionTrigger = TRANS_TRIGGER_OFF;
    return entrance;
}

int OotCore_EffectView(OotCoreEffectView* out, unsigned int capacity, unsigned int* omitted);
static unsigned int oot_core_water_boxes(const void** boxes) {
    static_assert(sizeof(WaterBox) == 16, "host water view stride");
    *boxes = NULL;
    if (!gOotCorePlay || gOotCorePlay->sceneId != SCENE_WATER_TEMPLE ||
        !gOotCorePlay->colCtx.colHeader) return 0;
    const CollisionHeader* col = gOotCorePlay->colCtx.colHeader;
    *boxes = col->waterBoxes;
    return col->waterBoxes ? col->numWaterBoxes : 0;
}
#ifdef PLAYER_SOURCE
int OotCore_PlayerBank(const void* bank, unsigned int bytes);   /* bridge_player_source.cpp */
int OotCore_PlayerView(OotCorePlayerView* out);
void OotCore_PlayerDamage(int damage);
int OotCore_PlayerPose(unsigned int id, unsigned int frame, short* out);
int OotCore_PlayerJump(void);
void OotCore_PlayerWarp(int x, int y, int z, short yaw);
#endif
unsigned int OotCore_SpritePreload(const void*, const OotCoreSpriteLibrary*, unsigned int,
                                  unsigned char**, unsigned int*);
const unsigned char* OotCore_SpriteClip(const unsigned char*, unsigned int);

/* First bytes of OOTCORE.BIN (oot-core.ld KEEPs .oot_entry at the load address). */
extern "C" const OotCoreEntry oot_core_entry __attribute__((section(".oot_entry"), used)) = {
    OOT_CORE_MAGIC,
    OOT_CORE_VERSION,
    oot_core_end,
    oot_core_bench_run,
    oot_core_init,
    oot_core_play_bytes,
    oot_core_play_init,
    oot_core_set_objects,
    OotCore_SetText,
    oot_core_set_input,
    OotCore_MessageView,
    OotCore_NpcView,
    OotCore_TalkState,
    oot_core_player_push,
    OotCore_PropQuery,
    OotCore_DebugText,
    OotCore_DrawItems,
    OotCore_MeshList,
    oot_core_set_camera,
    OotCore_DebugText2,
    OotCore_SkinList,
    oot_core_set_player,
    oot_core_set_room,
    oot_core_set_sword,
    oot_core_set_save,
    oot_core_update,
    oot_core_draw,
    oot_core_spawn,
    oot_core_actor_count,
    oot_core_actor_view,
    oot_core_set_flags,
    oot_core_door_action,
    oot_core_current_layer,
    oot_core_transition_request,
    OotCore_Ocarina,
    oot_core_tool,
    OotCore_ToolView,
    OotCore_DestinationLayer,
    oot_core_skybox_settings,
    oot_core_cancel_transition_time,
    oot_core_npc_text,
    OotCore_DynaView,
    OotCore_EffectView,
    oot_core_play_destroy,
    OotCore_PackBind,
    OotCore_PackRelease,
    OotCore_SceneLoad,
    OotCore_SpritePreload,
    OotCore_SpriteClip,
    oot_core_water_boxes,
    OotCoreBg_Api,
#ifdef PLAYER_SOURCE
    OotCore_PlayerBank,
    OotCore_PlayerView,
    OotCore_PlayerDamage,
    OotCore_PlayerPose,
    OotCore_PlayerJump,
    OotCore_PlayerWarp,
#else
    NULL,
    NULL,
    NULL,
    NULL,
    NULL,
    NULL,
#endif
};
