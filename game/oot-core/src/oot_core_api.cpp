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
#include "oot_core_api.h"
#include "oot_scene_blob.h"

void oot_core_bench_run(OotCoreBench* out, unsigned int (*ticks)(void),
                        unsigned int (*ticks_to_us)(unsigned int));
extern const OotCoreHost* gOotCoreHost;
extern Vec3f gOotCorePlayerPos;
extern s16 gOotCorePlayerYaw;

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
static const s16 sRoomActorIds[] = { ACTOR_EN_KUSA };
#define ROOM_ENTRIES_MAX 64
static ActorEntry sRoomEntries[ROOM_ENTRIES_MAX];

/* Scene_CommandActorEntryList for the room's main header, filtered to the
 * imported ids. Actor_UpdateAll spawns play->actorEntryList next frame. */
static void load_room_actors(PlayState* play, int room) {
    const ActorEntry* list;
    u32 i, k, n = 0;

    play->numActorEntries = 0;
    if (sScene == NULL || room < 0 || (u32)room >= sScene->num_rooms) {
        return;
    }
    list = (const ActorEntry*)sScene->rooms[room].actors;
    for (i = 0; i < sScene->rooms[room].num_actors && n < ROOM_ENTRIES_MAX; i++) {
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
    oot_core_update,
    oot_core_draw,
    oot_core_spawn,
    oot_core_actor_count,
};
