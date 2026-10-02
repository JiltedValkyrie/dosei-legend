/*
 * oot-core entry table (oot_core_api.h). Init and per-frame order copy
 * z_play.c (Play_Init / Play_Update) for the systems the blob has; the
 * rest (rooms, cutscenes, message, camera, environment) stays with the C
 * game until those files are imported.
 */
#include "oot_prelude.h"
#include "ultra64.h"
#include "actor.h"
#include "effect.h"
#include "play_state.h"
#include "regs.h"
#include "segmented_address.h"
#include "z_actor_dlftbls.h"
#include "zelda_arena.h"
#include "oot_core_api.h"

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

static int oot_core_play_init(void* block, unsigned int bytes, int scene_id, const void* col_header, short x,
                              short y, short z, short yaw) {
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
    if (col_header != NULL) {
        BgCheck_Allocate(&play->colCtx, play, (CollisionHeader*)col_header);
    }

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

    sPlay = play;
    return GET_PLAYER(play) != NULL;
}

static void oot_core_set_player(int x, int y, int z, short yaw) {
    gOotCorePlayerPos.x = x;
    gOotCorePlayerPos.y = y;
    gOotCorePlayerPos.z = z;
    gOotCorePlayerYaw = yaw;
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
    oot_core_update,
    oot_core_draw,
    oot_core_spawn,
    oot_core_actor_count,
};
