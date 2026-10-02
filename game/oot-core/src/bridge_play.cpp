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

int FrameAdvance_IsEnabled(PlayState* this) { /* STUB: no frame advance on Saturn */
    return false;
}

/* ---- z_camera.c ---- */
s32 Camera_RequestMode(Camera* camera, s16 mode) { /* STUB: C camera owns modes until z_camera */
    return 0;
}

/* ---- z_scene.c: every imported object is resident (prebuilt Saturn meshes) ---- */
s32 Object_GetSlot(ObjectContext* objectCtx, s16 objectId) { /* HOST-side model: always slot 0 */
    return 0;
}

s32 Object_IsLoaded(ObjectContext* objectCtx, s32 slot) {
    return true;
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

/* ---- z_player_lib.c: Link is the C player until z_player is imported ---- */
int Player_InCsMode(PlayState* play) { /* STUB */
    return false;
}

s32 Player_GetExplosiveHeld(Player* this) { /* STUB: no explosives yet (real returns -1 for none) */
    return -1;
}

void Player_ReleaseLockOn(Player* this) { /* STUB: C attention system owns lock-on */
}

/* ---- z_parameter.c: save-owned state stays on the C side for now ---- */
u8 Item_Give(PlayState* play, u8 item) { /* HOST */
    if (gOotCoreHost != NULL && gOotCoreHost->give_item != NULL) {
        return gOotCoreHost->give_item(item);
    }
    return ITEM_NONE;
}

s32 Health_ChangeBy(PlayState* play, s16 amount) { /* HOST */
    if (gOotCoreHost != NULL && gOotCoreHost->health_change != NULL) {
        return gOotCoreHost->health_change(amount);
    }
    return true;
}

void Magic_Reset(PlayState* play) { /* STUB: no magic meter yet */
}

/* ---- z_draw.c ---- */
void GetItem_Draw(PlayState* play, s16 giDrawId) { /* STUB: Phase 2 draw shim */
}
