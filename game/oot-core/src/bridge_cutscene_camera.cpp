/* Source z_play/z_camera cutscene camera services. The Saturn gameplay
 * follow camera remains host-owned; subcamera shots and Demo1 splines use
 * source storage and source z_cutscene_spline interpolation at 20 Hz. */
#include "oot_prelude.h"
#include "ultra64.h"
#include "play_state.h"
#include "player.h"
#include "camera.h"
#include "cutscene_spline.h"
#include "letterbox.h"
#include "sys_math3d.h"
#include "z_lib.h"
#include "oot_cutscene_camera.h"
#include "regs.h"
#include "scene.h"
#include "one_point_cutscene.h"
#include "interface.h"
#include "olib.h"
#include "math.h"
#include "libc64/math64.h"
#include "attributes.h"
#include "printf.h"
#include "terminal.h"
#include "save.h"
#include "oot_actor_pack.h"
#include "sfx.h"

static s32 sLetterboxSize, sLetterboxTarget;
static bool sMainSourceCamera;
s32 D_8011D3AC = -1;
s32 func_8005B198(void) { return D_8011D3AC; }

void Letterbox_SetSizeTarget(s32 target) { sLetterboxTarget = target; }
u32 Letterbox_GetSizeTarget(void) { return sLetterboxTarget; }
void Letterbox_SetSize(s32 size) { sLetterboxSize = size; }
u32 Letterbox_GetSize(void) { return sLetterboxSize; }
void Letterbox_Init(void) { sLetterboxSize = sLetterboxTarget = 0; }
void Letterbox_Destroy(void) { sLetterboxSize = 0; }
void Letterbox_Update(s32 updateRate) {
    s32 step = updateRate == 3 ? 10 : 30 / updateRate;
    if (sLetterboxSize < sLetterboxTarget)
        sLetterboxSize = sLetterboxSize + step < sLetterboxTarget ? sLetterboxSize + step : sLetterboxTarget;
    else if (sLetterboxSize > sLetterboxTarget)
        sLetterboxSize = sLetterboxSize - step > sLetterboxTarget ? sLetterboxSize - step : sLetterboxTarget;
}

static Camera* camera_at(PlayState* play, s16 id) {
    if (id == CAM_ID_NONE) id = play->activeCamId;
    return id >= 0 && id < NUM_CAMS ? play->cameraPtrs[id] : NULL;
}

/* Cutscene fields from Camera_Init; N64 debug regs and normal-camera tuning
 * are not needed by Demo1 or actor-controlled at/eye shots. */
static void camera_init(Camera* camera, PlayState* play, s16 id) {
    bzero(camera, sizeof(*camera));
    camera->play = play;
    camera->player = GET_PLAYER(play);
    camera->camId = id;
    camera->uid = id;
    camera->up.y = 1;
    camera->fov = 60;
    camera->setting = camera->prevSetting = CAM_SET_FREE0;
    camera->bgCamIndex = camera->prevBgCamIndex = camera->nextBgCamIndex = -1;
    camera->bgId = BGCHECK_SCENE;
    camera->csId = 0x7FFF;
    camera->timer = -1;
    camera->stateFlags = CAM_STATE_CAM_INIT;
    camera->atLERPStepScale = 1;
}

void OotCore_CutsceneCameraReset(PlayState* play) {
    sMainSourceCamera = false;
    D_8011D3AC = -1;
    for (s16 id = CAM_ID_SUB_FIRST; id < NUM_CAMS; ++id) play->cameraPtrs[id] = NULL;
    play->cameraPtrs[CAM_ID_MAIN] = &play->mainCamera;
    play->activeCamId = CAM_ID_MAIN;
    camera_init(&play->mainCamera, play, CAM_ID_MAIN);
    play->mainCamera.status = CAM_STAT_ACTIVE;
    Letterbox_Init();
}

void OotCore_CutsceneCameraSeed(PlayState* play, const OotCoreCutsceneCameraView* view) {
    if (!view || play->activeCamId != CAM_ID_MAIN || sMainSourceCamera) return;
    Player* player = GET_PLAYER(play);
    if (player && (player->stateFlags2 & PLAYER_STATE2_29)) return;
    Camera* camera = &play->mainCamera;
    camera->eye = camera->eyeNext = {view->eye[0], view->eye[1], view->eye[2]};
    camera->at = {view->at[0], view->at[1], view->at[2]};
#if OOT_CORE_HWFLOAT
    camera->fov = f32(view->fov_q8) / 256;
#else
    camera->fov = f32::raw(view->fov_q8 * 256);
#endif
    camera->roll = view->roll;
    play->view.eye = camera->eye;
    play->view.at = camera->at;
    play->view.fovy = camera->fov;
}

s16 Play_CreateSubCamera(PlayState* play) {
    for (s16 id = CAM_ID_SUB_FIRST; id < NUM_CAMS; ++id) {
        if (play->cameraPtrs[id] != NULL) continue;
        Camera* camera = &play->subCameras[id - CAM_ID_SUB_FIRST];
        play->cameraPtrs[id] = camera;
        camera_init(camera, play, id);
        return id;
    }
    return CAM_ID_NONE;
}

s16 Camera_ChangeStatus(Camera* camera, s16 status) {
    if (!camera) return CAM_ID_NONE;
    camera->status = status;
    return camera->status;
}
s16 Play_ChangeCameraStatus(PlayState* play, s16 id, s16 status) {
    Camera* camera = camera_at(play, id);
    if (!camera) return CAM_ID_NONE;
    if (status == CAM_STAT_ACTIVE) play->activeCamId = camera->camId;
    return Camera_ChangeStatus(camera, status);
}
void Play_ClearCamera(PlayState* play, s16 id) {
    Camera* camera = camera_at(play, id);
    if (!camera || camera->camId == CAM_ID_MAIN) return;
    camera->status = CAM_STAT_UNK100;
    play->cameraPtrs[camera->camId] = NULL;
}
void Play_ReturnToMainCam(PlayState* play, s16 camId, s16 duration) {
    Play_ClearCamera(play, camId == CAM_ID_NONE ? play->activeCamId : camId);
    for (s16 id = CAM_ID_SUB_FIRST; id < NUM_CAMS; ++id) Play_ClearCamera(play, id);
    if (duration <= 0) {
        Play_ChangeCameraStatus(play, CAM_ID_MAIN, CAM_STAT_ACTIVE);
        play->cameraPtrs[CAM_ID_MAIN]->childCamId = play->cameraPtrs[CAM_ID_MAIN]->parentCamId = CAM_ID_MAIN;
    } else {
        OnePointCutscene_Init(play, 1020, duration, NULL, CAM_ID_MAIN);
    }
}
void Play_ClearAllSubCameras(PlayState* play) {
    for (s16 id = CAM_ID_SUB_FIRST; id < NUM_CAMS; ++id) Play_ClearCamera(play, id);
    play->activeCamId = CAM_ID_MAIN;
}

s32 Camera_SetViewParam(Camera* camera, s32 flag, void* param) {
    if (!camera || !param) return false;
    switch (flag) {
        case CAM_VIEW_AT:
            camera->viewFlags &= ~(CAM_VIEW_AT | CAM_VIEW_TARGET | CAM_VIEW_TARGET_POS);
            camera->at = *(Vec3f*)param;
            break;
        case CAM_VIEW_TARGET_POS:
            camera->viewFlags &= ~(CAM_VIEW_AT | CAM_VIEW_TARGET | CAM_VIEW_TARGET_POS);
            camera->targetPosRot.pos = *(Vec3f*)param;
            break;
        case CAM_VIEW_TARGET:
            if (camera->setting != CAM_SET_CS_C && camera->setting != CAM_SET_CS_ATTENTION) {
                camera->target = (Actor*)param;
                camera->viewFlags &= ~(CAM_VIEW_AT | CAM_VIEW_TARGET | CAM_VIEW_TARGET_POS);
            }
            break;
        case CAM_VIEW_EYE: camera->eye = camera->eyeNext = *(Vec3f*)param; break;
        case CAM_VIEW_UP: camera->up = *(Vec3f*)param; break;
        case CAM_VIEW_ROLL:
            camera->roll = (s16)(*(f32*)param * FXL(182.04167f));
            break;
        case CAM_VIEW_FOV: camera->fov = *(f32*)param; break;
        default: return false;
    }
    camera->viewFlags |= flag;
    return true;
}

s32 Play_SetCameraAtEye(PlayState* play, s16 id, Vec3f* at, Vec3f* eye) {
    Camera* camera = camera_at(play, id);
    if (!camera || !at || !eye) return false;
    s32 bits = (Camera_SetViewParam(camera, CAM_VIEW_AT, at) << 1) |
               Camera_SetViewParam(camera, CAM_VIEW_EYE, eye);
    camera->dist = Math3D_Vec3f_DistXYZ(at, eye);
    if (camera->player) {
        camera->playerToAtOffset.x = at->x - camera->player->actor.world.pos.x;
        camera->playerToAtOffset.y = at->y - camera->player->actor.world.pos.y;
        camera->playerToAtOffset.z = at->z - camera->player->actor.world.pos.z;
    } else camera->playerToAtOffset = { 0, 0, 0 };
    camera->atLERPStepScale = FXL(0.01f);
    return bits;
}
s32 Play_SetCameraAtEyeUp(PlayState* play, s16 id, Vec3f* at, Vec3f* eye, Vec3f* up) {
    return (Play_SetCameraAtEye(play, id, at, eye) << 1) |
           Camera_SetViewParam(camera_at(play, id), CAM_VIEW_UP, up);
}
s32 Play_SetCameraFov(PlayState* play, s16 id, f32 fov) {
    return Camera_SetViewParam(camera_at(play, id), CAM_VIEW_FOV, &fov);
}
s32 Play_SetCameraRoll(PlayState* play, s16 id, s16 roll) {
    Camera* camera = camera_at(play, id);
    if (!camera) return false;
    camera->roll = roll;
    return true;
}

/* Normal gameplay modes still use Saturn's follow implementation. Keep real
 * setting/animation state for source cutscene scripts instead of discarding
 * requests; general setting priority tables remain part of camera migration. */
s32 Camera_RequestSetting(Camera* camera, s16 setting) {
    if (!camera || setting <= CAM_SET_NONE || setting >= CAM_SET_MAX) return -99;
    if (camera->camId == CAM_ID_MAIN)
        sMainSourceCamera = setting == CAM_SET_FREE0 || setting == CAM_SET_CS_0;
    camera->behaviorFlags |= CAM_BEHAVIOR_SETTING_VALID;
    if (camera->setting == setting) return -1;
    camera->prevSetting = camera->setting;
    camera->setting = setting;
    camera->stateFlags &= ~(CAM_STATE_EXTERNAL_FINISHED | CAM_STATE_DEMO7);
    camera->animState = 0;
    return setting;
}
s32 Play_RequestCameraSetting(PlayState* play, s16 id, s16 setting) {
    return Camera_RequestSetting(camera_at(play, id), setting);
}
s32 Camera_ResetAnim(Camera* camera) { camera->animState = 0; return 1; }
void Camera_SetCameraData(Camera* camera, s16 flags, void* data0, void* data1,
                          s16 data2, s16 data3, s32 data4) {
    if (!camera) return;
    if (flags & CAM_DATA_SET_0) camera->data0 = data0;
    if (flags & CAM_DATA_SET_1) camera->data1 = data1;
    if (flags & CAM_DATA_SET_2) camera->data2 = data2;
    if (flags & CAM_DATA_SET_3) camera->data3 = data3;
    /* Source CAM_DATA_SET_4 only prints an unused-argument diagnostic. */
    (void)data4;
}
s32 Camera_SetCSParams(Camera* camera, CutsceneCameraPoint* at, CutsceneCameraPoint* eye,
                       Player* player, s16 relative) {
    camera->data0 = at;
    camera->data1 = eye;
    camera->data2 = relative;
    if (relative) {
        camera->player = player;
        camera->playerPosRot = player->actor.world;
        camera->playerPosRot.rot = player->actor.shape.rot;
        camera->nextBgCamIndex = -1;
        camera->xzSpeed = camera->speedRatio = 0;
    }
    return 1;
}
s16 Camera_SetFinishedFlag(Camera* camera) {
    if (!camera) return CAM_ID_NONE;
    camera->stateFlags |= CAM_STATE_EXTERNAL_FINISHED;
    if (camera->camId == CAM_ID_MAIN && camera->play->activeCamId != CAM_ID_MAIN) {
        Camera* active = camera_at(camera->play, CAM_ID_NONE);
        if (active) active->stateFlags |= CAM_STATE_EXTERNAL_FINISHED;
        return camera->play->activeCamId;
    }
    return camera->camId;
}
s32 Camera_Copy(Camera* dst, Camera* src) {
    if (!dst || !src) return false;
    dst->at = src->at;
    dst->eye = dst->eyeNext = src->eye;
    dst->dist = Math3D_Vec3f_DistXYZ(&dst->at, &dst->eye);
    dst->fov = src->fov;
    dst->roll = src->roll;
    dst->atLERPStepScale = FXL(0.1f);
    dst->playerToAtOffset = { 0, 0, 0 };
    if (dst->player) {
        dst->playerPosRot = dst->player->actor.world;
        dst->playerToAtOffset.x = dst->at.x - dst->playerPosRot.pos.x;
        dst->playerToAtOffset.y = dst->at.y - dst->playerPosRot.pos.y;
        dst->playerToAtOffset.z = dst->at.z - dst->playerPosRot.pos.z;
        dst->dist = Math3D_Vec3f_DistXYZ(&dst->playerPosRot.pos, &dst->eye);
        dst->xzOffsetUpdateRate = dst->yOffsetUpdateRate = 1;
    }
    return true;
}
void Play_CopyCamera(PlayState* play, s16 dst, s16 src) {
    Camera_Copy(camera_at(play, dst), camera_at(play, src));
}
void Play_SetShopBrowsingViewpoint(PlayState* play) {
    /* Scene camera-type registers are host-owned. The source shop scenes
     * carry the same fixed/pivot pair in their collision camera table. */
    if (R_SCENE_CAM_TYPE == SCENE_CAM_TYPE_FIXED_SHOP_VIEWPOINT ||
        (play->sceneId >= SCENE_BAZAAR && play->sceneId <= SCENE_HAPPY_MASK_SHOP))
        play->viewpoint = VIEWPOINT_PIVOT;
}

static bool shop_camera(PlayState* play, Camera* camera, bool apply) {
    Player* player = GET_PLAYER(play);
    if (camera->camId != CAM_ID_MAIN || !player || !(player->stateFlags2 & PLAYER_STATE2_29) ||
        play->sceneId < SCENE_BAZAAR || play->sceneId > SCENE_HAPPY_MASK_SHOP ||
        !play->colCtx.colHeader || !play->colCtx.colHeader->bgCamList) return false;
    BgCamInfo* info = &play->colCtx.colHeader->bgCamList[1];
    if (info->setting != CAM_SET_PIVOT_SHOP_BROWSING || !info->bgCamFuncData) return false;
    if (!apply) return true;
    BgCamFuncData* data = (BgCamFuncData*)info->bgCamFuncData;
    /* Camera_Data4: scene-fixed eye, EnOssan angle offsets selected by flags.
     * Shops enable both axes. Distance does not affect the fixed eye view. */
    s16 yaw = data->rot.y + ((data->flags & 1) ? camera->data2 * 65536 / 360 : 0);
    s16 pitch = data->rot.x + ((data->flags & 2) ? camera->data3 * 65536 / 360 : 0);
    camera->eye = camera->eyeNext = {data->pos.x, data->pos.y, data->pos.z};
    f32 distance = Math_CosS(pitch) * 200;
    camera->at = {camera->eye.x + Math_SinS(yaw) * distance,
                  camera->eye.y + Math_SinS(pitch) * 200,
                  camera->eye.z + Math_CosS(yaw) * distance};
    camera->fov = data->fov == -1 ? f32(60) :
        data->fov <= 360 ? f32(data->fov) : f32(data->fov) / 100;
    camera->roll = 0;
    return true;
}

/* Source Unique9/Demo9 interpolation and queue. Scene OAP services own the
 * exact source recipes; a missing recipe fails before changing any camera. */
s32 Camera_RequestModeImpl(Camera* camera, s16 mode, u8) {
    if (!camera) return -1;
    camera->mode = mode;
    camera->animState = 0;
    return mode;
}
#include "../../build/oot-core/owl_camera_source.inc"

/* Source screen-space attention choices need the current Saturn view. No N64
 * view matrix is installed by the renderer, so project the live eye/at basis.
 * Clamp only far-offscreen ratios; their exact pixels cannot change a branch. */
void OotCore_CameraActorScreenPos(PlayState* play, Actor* actor, s16* x, s16* y) {
    Vec3f forward = OLib_Vec3fDistNormalize(&play->view.eye, &play->view.at);
    Vec3f zero = {0,0,0}, right = {forward.z,0,-forward.x};
    right = OLib_Vec3fDistNormalize(&zero, &right);
    Vec3f up = {forward.y*right.z, forward.z*right.x-forward.x*right.z, -forward.y*right.x};
    Vec3f delta = {actor->focus.pos.x-play->view.eye.x, actor->focus.pos.y-play->view.eye.y,
                  actor->focus.pos.z-play->view.eye.z};
    f32 depth = delta.x*forward.x + delta.y*forward.y + delta.z*forward.z;
    if (depth < 1) depth = 1;
    f32 side = (delta.x*right.x + delta.z*right.z) / depth;
    f32 height = (delta.x*up.x + delta.y*up.y + delta.z*up.z) / depth;
    if (side < -32) side=-32; else if (side>32) side=32;
    if (height < -32) height=-32; else if (height>32) height=32;
    s16 halfFov=(s16)(play->view.fovy*FXL(91.02222f));
    f32 sine=Math_SinS(halfFov), focal=sine>0 ? Math_CosS(halfFov)/sine*120 : f32(120);
    *x=(s16)(160+side*focal); *y=(s16)(120-height*focal);
}

/* Cutscene part of source Camera_InitDataUsingPlayer. Gameplay camera floor,
 * water, tuning-register and priority work belongs to Saturn's follow owner. */
s32 Play_InitCameraDataUsingPlayer(PlayState* play, s16 id, Player* player, s16 setting) {
    Camera* camera = camera_at(play, id);
    if (!camera || !player) return false;
    camera->player = player;
    camera->playerPosRot = Actor_GetWorldPosShapeRot(&player->actor);
    f32 height = Player_GetHeight(player);
    VecGeo offset = {180, 0x71C, (s16)(camera->playerPosRot.rot.y - 0x7FFF)};
    camera->dist = 180;
    camera->inputDir = {0x71C, camera->playerPosRot.rot.y, 0};
    camera->camDir = camera->inputDir;
    camera->xzSpeed = 0;
    camera->playerPosDelta = {0,0,0};
    camera->at = camera->playerPosRot.pos;
    camera->at.y += height;
    camera->playerToAtOffset = {0,height,0};
    camera->eye = camera->eyeNext = Camera_AddVecGeoToVec3f(&camera->at, &offset);
    camera->roll = 0;
    camera->up = {0,1,0};
    camera->bgCamIndexBeforeUnderwater = camera->waterCamSetting = -1;
    camera->stateFlags |= CAM_STATE_CHECK_BG;
    camera->behaviorFlags = camera->viewFlags = 0;
    camera->nextBgCamIndex = -1;
    camera->atLERPStepScale = 1;
    return Camera_RequestSetting(camera, setting);
}
s16 OnePointCutscene_EndCutscene(PlayState* play, s16 id) {
    if (id == CAM_ID_NONE) id = play->activeCamId;
    Camera* camera = camera_at(play, id);
    if (camera) camera->timer = camera->csId == 5010 ? 5 : 0;
    return id;
}

/* Camera_RotateAroundPoint: yaw rotation, avoiding an unnecessary spherical
 * conversion. World units and Fx32 storage are unchanged. */
static Vec3f relative_point(Player* player, const Vec3f& pos) {
    f32 sine = Math_SinS(player->actor.world.rot.y);
    f32 cosine = Math_CosS(player->actor.world.rot.y);
    return { player->actor.world.pos.x + pos.x * cosine + pos.z * sine,
             player->actor.world.pos.y + pos.y,
             player->actor.world.pos.z + pos.z * cosine - pos.x * sine };
}

s32 Camera_Demo1(Camera* camera) {
    Demo1ReadWriteData* rw = &camera->paramData.demo1.rwData;
    if (camera->animState == 0) {
        rw->keyframe = 0;
        rw->curFrame = 0;
        camera->animState = 1;
    }
    if (camera->animState != 1 || !camera->data0 || !camera->data1) return true;
    Vec3f eye, at;
    f32 roll, fov = camera->fov;
    /* Keep the last valid view at a STOP sentinel. Source short-circuiting
     * can leave one local sample unwritten; never publish that stack data. */
    if (func_800BB2B4(&eye, &roll, &fov, (CutsceneCameraPoint*)camera->data1,
                      &rw->keyframe, &rw->curFrame) ||
        func_800BB2B4(&at, &roll, &fov, (CutsceneCameraPoint*)camera->data0,
                      &rw->keyframe, &rw->curFrame)) {
        camera->animState = 2;
        return true;
    }
    if (camera->data2) {
        if (!camera->player || !camera->player->actor.update) return true;
        eye = relative_point(camera->player, eye);
        at = relative_point(camera->player, at);
    }
    camera->eye = camera->eyeNext = eye;
    camera->at = at;
    camera->fov = fov;
    camera->roll = (s16)(roll * 256);
    camera->dist = Math3D_Vec3f_DistXYZ(&at, &eye);
    return true;
}

void OotCore_CutsceneCameraStep(PlayState* play) {
    Camera* camera = camera_at(play, CAM_ID_NONE);
    if (camera) shop_camera(play, camera, true);
    if (camera && camera->status == CAM_STAT_ACTIVE && camera->setting == CAM_SET_CS_0)
        Camera_Demo1(camera);
    if (camera && camera->status == CAM_STAT_ACTIVE &&
        (camera->setting == CAM_SET_CS_C || camera->setting == CAM_SET_CS_3 ||
         camera->setting == CAM_SET_CS_ATTENTION ||
         (camera->setting == CAM_SET_FREE2 && camera->camId != CAM_ID_MAIN))) {
        Vec3f previous = camera->playerPosRot.pos;
        camera->playerPosRot = Actor_GetWorldPosShapeRot(&camera->player->actor);
        camera->playerPosDelta = {camera->playerPosRot.pos.x-previous.x,
                                 camera->playerPosRot.pos.y-previous.y,
                                 camera->playerPosRot.pos.z-previous.z};
        OotCore_PackOnePointStep(camera);
        Camera_Finish(camera);
        camera = camera_at(play, CAM_ID_NONE);
    }
    if (camera && camera->status == CAM_STAT_ACTIVE) {
        play->view.eye = camera->eye;
        play->view.at = camera->at;
        play->view.fovy = camera->fov;
    }
    if (play->activeCamId == CAM_ID_MAIN && play->csCtx.state == CS_STATE_IDLE && !sMainSourceCamera)
        Letterbox_SetSizeTarget(0);
    Letterbox_Update(3);
}

int OotCore_CutsceneCameraRead(PlayState* play, OotCoreCutsceneCameraView* out) {
    if (!out) return 0;
    bzero(out, sizeof(*out));
    out->letterbox = sLetterboxSize < 0 ? 0 : sLetterboxSize > 120 ? 120 : sLetterboxSize;
    Camera* camera = camera_at(play, CAM_ID_NONE);
    if (!camera || camera->status != CAM_STAT_ACTIVE ||
        (camera->camId == CAM_ID_MAIN && !sMainSourceCamera && !shop_camera(play, camera, false))) return 0;
    out->eye[0] = (int)camera->eye.x; out->eye[1] = (int)camera->eye.y; out->eye[2] = (int)camera->eye.z;
    out->at[0] = (int)camera->at.x; out->at[1] = (int)camera->at.y; out->at[2] = (int)camera->at.z;
#if OOT_CORE_HWFLOAT
    out->fov_q8 = (int)(camera->fov * 256);
#else
    out->fov_q8 = camera->fov.v / 256;
#endif
    out->roll = camera->roll;
    out->active = 1;
    return 1;
}
