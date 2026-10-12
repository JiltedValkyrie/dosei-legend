/*
 * Phase 1 bridges: PlayState services, objects, overlays, fault/OS, audio,
 * and the z_player_lib / z_parameter calls the actor slice makes.
 *
 * Rule (OOT_CORE_PIPELINE_PLAN.md): game logic comes from the decomp. Each
 * function here is one of:
 *   REAL   - same body as the decomp (one-liners not worth importing a file).
 *   HOST   - Saturn backend through OotCoreHost (the C side owns that state).
 *   STUB   - no Saturn equivalent needed yet; the comment names the decomp
 *            file that replaces it when imported.
 */
#include "oot_prelude.h"
#include "ultra64.h"
#include "array_count.h"
#include "z_math.h"
#include "fault.h"
#include "libu64/debug.h"
#include "libu64/overlay.h"
#include "play_state.h"
#include "player.h"
#include "save.h"
#include "segmented_address.h"
#include "sfx.h"
#include "audio.h"
#include "oot_core_host.h"

const OotCoreHost* gOotCoreHost;

/* ---- globals owned by code we do not import ---- */
SaveContext gSaveContext;       /* z_sram/z_play own it on N64 */
uintptr_t gSegments[NUM_SEGMENTS]; /* sched/graph */

/* ---- z_play.c ---- */
void Play_SaveSceneFlags(PlayState* thisx) { /* REAL: z_play.c */
    SavedSceneFlags* flags = &gSaveContext.save.info.sceneFlags[thisx->sceneId];
    flags->chest = thisx->actorCtx.flags.chest;
    flags->swch = thisx->actorCtx.flags.swch;
    flags->clear = thisx->actorCtx.flags.clear;
    flags->collect = thisx->actorCtx.flags.collect;
}

Camera* Play_GetCamera(PlayState* this, s16 camId) { /* REAL */
    s16 camIdx = (camId == CAM_ID_NONE) ? this->activeCamId : camId;
    return this->cameraPtrs[camIdx];
}

s32 Play_GetActiveCamId(PlayState* this) { /* REAL */
    return this->activeCamId;
}

Gfx* Play_SetFog(PlayState* this, Gfx* gfx) { /* STUB: Saturn fog is the C renderer's */
    return gfx;
}

int Play_InCsMode(PlayState* this) { /* REAL */
    return (this->csCtx.state != CS_STATE_IDLE) || Player_InCsMode(this);
}

int FrameAdvance_IsEnabled(PlayState* this) { /* STUB: no frame advance on Saturn */
    return false;
}

/* ---- z_camera.c ---- */
s32 Camera_RequestMode(Camera* camera, s16 mode) {
#ifdef PLAYER_SOURCE
    /* Player_ActionHandler_13 treats NORMAL as refusal. The Saturn view
     * follows Player's first-person flag/focus; acknowledge its request. */
    if (camera != NULL) camera->mode = mode;
    return mode;
#else
    return 0;
#endif
}

/* ---- z_scene.c ---- */
#include "../../build/oot-core/objects/oot_objects_built.h"

/* REAL search over the loaded slots (set_objects). An object not built as
 * a data blob (gameplay_keep, field keep, object_kusa ...) has only
 * placeholder symbols in the blob, so it is always "resident" in slot 0.
 * A data object the scene did not load returns -1, as on N64. */
s32 Object_GetSlot(ObjectContext* objectCtx, s16 objectId) {
    s32 i;

    for (i = 0; i < objectCtx->numEntries; i++) {
        if (ABS(objectCtx->slots[i].id) == objectId) {
            return i;
        }
    }
    for (i = 0; i < (s32)ARRAY_COUNT(sBuiltObjects); i++) {
        if (sBuiltObjects[i] == objectId) {
            return -1;
        }
    }
    return 0;
}

s32 Object_IsLoaded(ObjectContext* objectCtx, s32 slot) { /* REAL */
    if (objectCtx->slots[slot].id > 0) {
        return true;
    } else {
        return false;
    }
}

/* ---- libu64 overlay: bridge_tables.cpp makes every overlay internal ---- */
size_t Overlay_Load(uintptr_t vromStart, uintptr_t vromEnd, void* vramStart, void* vramEnd,
                    void* allocatedRamAddr) {
    return 0;
}

/* ---- fault / debug / OS ---- */
void Fault_AddClient(FaultClient* client, void* callback, void* arg0, void* arg1) {
}
void Fault_RemoveClient(FaultClient* client) {
}
s32 Fault_Printf(const char* fmt, ...) {
    return 0;
}
void Fault_SetCursor(s32 x, s32 y) {
}
void LogUtils_HungupThread(const char* name, int line) {
    for (;;) {
    }
}
OSId osGetThreadId(OSThread* thread) {
    return 0;
}
OSIntMask osSetIntMask(OSIntMask mask) { /* single-threaded blob: nothing to mask */
    return 0;
}
OSTime osGetTime(void) {
    return 0;
}

/* ---- audio: sfxId -> host PCM bank ---- */
static void host_sfx(u16 sfxId, Vec3f* pos) {
    if (gOotCoreHost != NULL && gOotCoreHost->play_sfx != NULL) {
        gOotCoreHost->play_sfx(sfxId, pos ? (s32)pos->x : 0, pos ? (s32)pos->y : 0, pos ? (s32)pos->z : 0);
    }
}

void SfxSource_PlaySfxAtFixedWorldPos(PlayState* play, Vec3f* worldPos, s32 duration, u16 sfxId) { /* HOST */
    host_sfx(sfxId, worldPos);
}

void func_800F4C58(Vec3f* pos, u16 sfxId, u8 arg2) { /* HOST: sequence-tempo sfx variant */
    host_sfx(sfxId, pos);
}

void Audio_StopSfxByPos(Vec3f* pos) { /* STUB: host one-shots end on their own */
}

void Audio_StopSfxByPosAndId(Vec3f* pos, u16 id) {
    /* Host sounds have bounded tails; ending source requests ends held sounds.
     * Keep the stop scoped: never stop another actor sharing the area slot. */
    (void)pos; (void)id;
}

/* ---- z_player_lib.c: Link is the C player until z_player is imported ---- */
#ifndef PLAYER_SOURCE   /* real z_player_lib owns these with the source Player */
int Player_InCsMode(PlayState* play) { /* STUB */
    return false;
}

s32 Player_GetExplosiveHeld(Player* this) { /* STUB: no explosives yet (real returns -1 for none) */
    return -1;
}

void Player_ReleaseLockOn(Player* this) { /* STUB: C attention system owns lock-on */
}
#endif

/* ---- z_parameter.c: save-owned state stays on the C side for now ---- */
u8 Item_Give(PlayState* play, u8 item) { /* HOST */
    if (item >= ITEM_SONG_MINUET && item <= ITEM_SONG_STORMS) {
        /* z_parameter.c Item_Give: song ownership belongs to the source
         * inventory. save_copy_out commits it to the host after this update. */
        gSaveContext.save.info.inventory.questItems |=
            1u << (item - ITEM_SONG_MINUET + QUEST_SONG_MINUET);
        return ITEM_NONE;
    }
    if (gOotCoreHost != NULL && gOotCoreHost->give_item != NULL) {
        u8 result = gOotCoreHost->give_item(item);
        if (result == ITEM_NONE && (item == ITEM_BOTTLE_POE || item == ITEM_BOTTLE_BIG_POE)) {
            for (u32 slot = SLOT_BOTTLE_1; slot <= SLOT_BOTTLE_4; ++slot)
                if (gSaveContext.save.info.inventory.items[slot] == ITEM_BOTTLE_EMPTY) {
                    gSaveContext.save.info.inventory.items[slot] = item;
                    break;
                }
        }
        return result;
    }
    return ITEM_NONE;
}

s32 Health_ChangeBy(PlayState* play, s16 amount) { /* HOST */
    if (gOotCoreHost != NULL && gOotCoreHost->health_change != NULL) {
        return gOotCoreHost->health_change(amount);
    }
    return true;
}

/* Arrow*_Destroy: the host's magic meter (health_hud.c) owns magicState
 * until real Player; it reads this through OOT_CORE_TOOL_MAGIC_RESET. */
u8 gOotCoreMagicReset;
void Magic_Reset(PlayState* play) {
    gOotCoreMagicReset = 1;
}

/* ---- z_draw.c ---- */
void GetItem_Draw(PlayState* play, s16 giDrawId) { /* STUB: Phase 2 draw shim */
}

#ifndef PLAYER_SOURCE
u8 Player_GetMask(PlayState* play) { /* REAL (z_player_lib.c) */
    Player* this = GET_PLAYER(play);

    return this->currentMask;
}
#endif

/* ---- z_quake.c / rumble: the C camera owns shake; Saturn has no rumble ---- */
#include "quake.h"
#include "rumble.h"
s16 Quake_Request(Camera* camera, u32 type) { /* STUB: no shake yet */
    return 0;
}
u32 Quake_SetSpeed(s16 index, s16 speed) { /* STUB */
    return 0;
}
u32 Quake_SetPerturbations(s16 index, s16 y, s16 x, s16 fov, s16 roll) { /* STUB */
    return 0;
}
u32 Quake_SetDuration(s16 index, s16 duration) { /* STUB */
    return 0;
}
void Rumble_Request(FxSq distSq, u8 sourceStrength, u8 duration, u8 decreaseRate) { /* STUB */
}

/* ---- z_camera.c / z_onepointdemo.c: the C camera owns the view ---- */
#include "one_point_cutscene.h"
#include "z_lib.h"
s16 gOotCoreCamYaw; /* set_camera: C camera facing, binary angle */

s16 Camera_GetCamDirYaw(Camera* camera) { /* HOST: C camera direction */
    return gOotCoreCamYaw;
}

/* Npc_UpdateTalking's on-screen test (importer rewrite of z_actor.c): the C
 * camera sits ~200 units behind Link looking along gOotCoreCamYaw. Visible =
 * in front of that eye within ~53 degrees either side. 32-bit integers. */
s32 OotCore_ActorInCameraView(PlayState* play, Actor* actor) {
    Player* player = GET_PLAYER(play);
    s32 fx, fz, vx, vz, ahead, side;
    if (player == NULL)
        return true;
    fx = (s32)(Math_SinS(gOotCoreCamYaw) * 1024.0f);
    fz = (s32)(Math_CosS(gOotCoreCamYaw) * 1024.0f);
    vx = (s32)(actor->world.pos.x - player->actor.world.pos.x) + fx * 200 / 1024;
    vz = (s32)(actor->world.pos.z - player->actor.world.pos.z) + fz * 200 / 1024;
    ahead = (vx * fx + vz * fz) / 1024;
    side = (vx * fz - vz * fx) / 1024;
    if (side < 0)
        side = -side;
    return ahead > 0 && side * 3 < ahead * 4;
}
s32 OnePointCutscene_Attention(PlayState* play, Actor* actor) { /* STUB: no attention shots */
    return CAM_ID_NONE;
}

/* En_Elf (Navi, 2026-10-09) links these. Saturn: no light adjustment (no
 * N64 lighting), no Fixed-shop viewpoint camera, positional SFX plays plain. */
#include "environment.h"
void Environment_AdjustLights(PlayState* play, f32 arg1, f32 arg2, f32 arg3, f32 arg4) {
}
s32 Play_CheckViewpoint(PlayState* play, s16 viewpoint) {
    return false;
}
/* Source z_kankyo.c. */
f32 Environment_LerpWeight(u16 max, u16 min, u16 val) {
    f32 diff = max - min;

    if (diff != 0.0f) {
        f32 ret = 1.0f - (max - val) / diff;

        if (!(ret >= 1.0f)) {
            return ret;
        }
    }
    return 1.0f;
}
void func_800F4524(Vec3f* pos, u16 sfxId, s8 arg2) {
    Audio_PlaySfxGeneral(sfxId, pos, 4, &gSfxDefaultFreqAndVolScale, &gSfxDefaultFreqAndVolScale,
                         &gSfxDefaultReverb);
}
