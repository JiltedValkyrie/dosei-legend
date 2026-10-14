/* Production camera bridge + imported source spline; deterministic cardinal
 * sine/cosine endpoints stand in for the platform trigonometry table. */
#include "oot_prelude.h"
#include "ultra64.h"
#include "play_state.h"
#include "player.h"
#include "camera.h"
#include "letterbox.h"
#include "math.h"
#include "oot_cutscene_camera.h"
#include "scene.h"
#include "one_point_cutscene.h"
#include "save.h"
SaveContext gSaveContext;
extern "C" int oot_pack_onepoint_setup(PlayState*,s16,s16,Actor*,s16);
extern "C" int oot_pack_onepoint_step(Camera*);
int OotCore_PackOnePointStep(Camera* c) {return oot_pack_onepoint_step(c);}
int OotCore_PackOnePointSetup(PlayState* p,s16 cam,s16 id,Actor* a,s16 timer) {
    return oot_pack_onepoint_setup(p,cam,id,a,timer);
}
Camera* Play_GetCamera(PlayState* p,s16 id) {return p->cameraPtrs[id==CAM_ID_NONE?p->activeCamId:id];}
extern s32 Camera_RequestModeImpl(Camera*,s16,u8);
s32 Camera_RequestMode(Camera* camera,s16 mode) {return Camera_RequestModeImpl(camera,mode,false);}
f32 Player_GetHeight(Player*) {return 40;}
s32 Player_SetCsActionWithHaltedActors(PlayState* p,Actor* a,u8 action) {
    return Player_SetCsAction(p,a,action);
}
s16 Quake_Request(Camera*,u32) {return 0;}
u32 Quake_SetSpeed(s16,s16) {return 0;}
u32 Quake_SetPerturbations(s16,s16,s16,s16,s16) {return 0;}
u32 Quake_SetDuration(s16,s16) {return 0;}
static u16 lastCameraSfx;
void Sfx_PlaySfxCentered(u16 id) {lastCameraSfx=id;}
f32 Rand_ZeroOne(void) {return FXL(0.5f);}
extern "C" int printf(const char*, ...);
extern "C" void exit(int);
#define CHECK(x) do { if (!(x)) { printf("line %d: %s\n", __LINE__, #x); exit(1); } } while (0)

static PlayState play;
static Player player;
static CutsceneCameraPoint eyePoints[6], atPoints[6];
static void alive(Actor*, PlayState*) {}
void bzero(void* memory, unsigned int bytes) { __builtin_memset(memory, 0, bytes); }
f32 Math_SinS(s16 angle) {
    if ((u16)angle & 0x3FFF)
        return f32(__builtin_sin((fx_hwdouble)angle * 6.283185307179586 / 65536.0));
    return angle == 0x4000 ? 1 : angle == (s16)0xC000 ? -1 : 0;
}
f32 Math_CosS(s16 angle) { return Math_SinS((s16)(angle + 0x4000)); }
f32 Math_FAtan2F(f32 y,f32 x) {
    return f32(__builtin_atan2((fx_hwdouble)y.v / 65536.0, (fx_hwdouble)x.v / 65536.0));
}
PosRot Actor_GetFocus(Actor* a) {return a->focus;}
PosRot Actor_GetWorld(Actor* a) {return a->world;}
PosRot Actor_GetWorldPosShapeRot(Actor* a) {PosRot out=a->world;out.rot=a->shape.rot;return out;}
s32 Player_SetCsAction(PlayState* p,Actor*,u8 action) {GET_PLAYER(p)->csAction=action;return true;}
void Interface_ChangeHudVisibilityMode(u16) {}
s32 BgCheck_CameraLineTest1(CollisionContext*,Vec3f*,Vec3f*,Vec3f*,CollisionPoly**,s32,s32,s32,s32,s32*) {return false;}
f32 BgCheck_CameraRaycastDown2(CollisionContext*,CollisionPoly**,s32*,Vec3f*) {return BGCHECK_Y_MIN;}
f32 BgCheck_EntityRaycastDown3(CollisionContext*,CollisionPoly**,s32*,Vec3f* p) {return p->y;}
f32 Math3D_Vec3f_DistXYZ(Vec3f* a, Vec3f* b) {
    return sqrtf(OOT_SQ(a->x - b->x) + OOT_SQ(a->y - b->y) + OOT_SQ(a->z - b->z));
}
static bool near(int value, int target) { return value >= target - 2 && value <= target + 2; }
static void reset(void) {
    bzero(&play, sizeof(play));
    bzero(&player, sizeof(player));
    play.actorCtx.actorLists[ACTORCAT_PLAYER].head = &player.actor;
    player.actor.update = alive;
    player.actor.world.pos = { 1000, 200, 3000 };
    OotCore_CutsceneCameraReset(&play);
}
static Camera* start_spline(bool relative) {
    s16 id = Play_CreateSubCamera(&play);
    CHECK(id == 1);
    CHECK(Play_RequestCameraSetting(&play, id, CAM_SET_CS_0) == CAM_SET_CS_0);
    CHECK(Play_ChangeCameraStatus(&play, CAM_ID_MAIN, CAM_STAT_WAIT) == CAM_STAT_WAIT);
    CHECK(Play_ChangeCameraStatus(&play, id, CAM_STAT_ACTIVE) == CAM_STAT_ACTIVE);
    for (unsigned i = 0; i < 6; ++i) {
        eyePoints[i] = {}; atPoints[i] = {};
        eyePoints[i].continueFlag = atPoints[i].continueFlag = i == 5 ? CS_CAM_STOP : CS_CAM_CONTINUE;
        eyePoints[i].pos = { (s16)(i * 60), 30, 120 };
        atPoints[i].pos = { (s16)(i * 60), 30, 0 };
        eyePoints[i].viewAngle = atPoints[i].viewAngle = 60;
        eyePoints[i].cameraRoll = atPoints[i].cameraRoll = 2;
        atPoints[i].nextPointFrame = 10;
    }
    Camera* camera = play.cameraPtrs[id];
    Camera_ResetAnim(camera);
    Camera_SetCSParams(camera, atPoints, eyePoints, &player, relative);
    return camera;
}

int main(void) {
    OotCoreCutsceneCameraView view;
    Camera* camera;
    reset();
    CHECK(!OotCore_CutsceneCameraRead(&play, &view));
    CHECK(!view.active && !view.letterbox);
    CHECK(Play_CreateSubCamera(&play) == 1);
    CHECK(Play_CreateSubCamera(&play) == 2);
    CHECK(Play_CreateSubCamera(&play) == 3);
    CHECK(Play_CreateSubCamera(&play) == CAM_ID_NONE);
    Play_ClearCamera(&play, 2);
    CHECK(Play_CreateSubCamera(&play) == 2);
    Play_ClearCamera(&play, CAM_ID_MAIN);
    CHECK(play.cameraPtrs[CAM_ID_MAIN] == &play.mainCamera);
    CHECK(Play_ChangeCameraStatus(&play, 1, CAM_STAT_ACTIVE) == CAM_STAT_ACTIVE);
    Vec3f at = { 1100, 240, 3000 }, eye = { 1100, 250, 3200 };
    CHECK(Play_SetCameraAtEye(&play, CAM_ID_NONE, &at, &eye) == 3);
    CHECK(Play_SetCameraFov(&play, CAM_ID_NONE, 50));
    CHECK(Play_SetCameraRoll(&play, CAM_ID_NONE, -512));
    CHECK(!Play_SetCameraFov(&play, NUM_CAMS, 40));
    CHECK(!Camera_SetViewParam(play.cameraPtrs[1], CAM_VIEW_AT, NULL));
    CHECK(OotCore_CutsceneCameraRead(&play, &view));
    CHECK(view.eye[2] == 3200 && view.at[1] == 240 && view.fov_q8 == 50 * 256 && view.roll == -512);
    CHECK((int)play.cameraPtrs[1]->playerToAtOffset.x == 100);
    Play_CopyCamera(&play, CAM_ID_MAIN, CAM_ID_NONE);
    CHECK(play.mainCamera.camId == CAM_ID_MAIN && play.mainCamera.play == &play);
    CHECK((int)play.mainCamera.eye.z == 3200 && (int)play.mainCamera.fov == 50);
    CHECK(Camera_SetFinishedFlag(&play.mainCamera) == 1);
    CHECK(play.cameraPtrs[1]->stateFlags & CAM_STATE_EXTERNAL_FINISHED);
    camera = play.cameraPtrs[1];
    Camera_SetCameraData(camera, CAM_DATA_SET_0 | CAM_DATA_SET_1, eyePoints, atPoints, 19, 21, 0);
    CHECK(camera->data0 == eyePoints && camera->data1 == atPoints && camera->data2 == 0);
    Camera_SetCameraData(camera, CAM_DATA_SET_2 | CAM_DATA_SET_3, NULL, NULL, -30, 0, 0);
    CHECK(camera->data2 == -30 && camera->data3 == 0 && camera->data0 == eyePoints);
    Play_ChangeCameraStatus(&play, CAM_ID_MAIN, CAM_STAT_ACTIVE);
    Play_ClearAllSubCameras(&play);
    CHECK(!OotCore_CutsceneCameraRead(&play, &view));
    CHECK(!play.cameraPtrs[1] && !play.cameraPtrs[2] && !play.cameraPtrs[3]);
    printf("subcamera lifecycle/direct shots/copy/finished: pass\n");

    reset();
    camera = start_spline(false);
    OotCore_CutsceneCameraStep(&play);
    CHECK(OotCore_CutsceneCameraRead(&play, &view));
    CHECK(near(view.eye[0], 60) && near(view.eye[1], 30) && near(view.eye[2], 120));
    CHECK(near(view.at[0], 60) && view.at[2] == 0);
    CHECK(near(view.fov_q8, 60 * 256) && near(view.roll, 512));
    int initialX = view.eye[0];
    for (unsigned i = 0; i < 8; ++i) OotCore_CutsceneCameraStep(&play);
    OotCore_CutsceneCameraRead(&play, &view);
    CHECK(view.eye[0] > initialX);
    for (unsigned i = 0; i < 100; ++i) OotCore_CutsceneCameraStep(&play);
    CHECK(camera->animState == 2);
    OotCore_CutsceneCameraRead(&play, &view);
    OotCoreCutsceneCameraView held = view;
    OotCore_CutsceneCameraStep(&play);
    OotCore_CutsceneCameraRead(&play, &view);
    for (unsigned i = 0; i < 3; ++i) CHECK(held.eye[i] == view.eye[i] && held.at[i] == view.at[i]);
    CHECK(held.roll == view.roll && held.fov_q8 == view.fov_q8);
    printf("source spline interpolation/advance/end hold: pass\n");

    reset();
    player.actor.world.rot.y = 0x4000;
    start_spline(true);
    OotCore_CutsceneCameraStep(&play);
    CHECK(OotCore_CutsceneCameraRead(&play, &view));
    CHECK(near(view.eye[0], 1120) && near(view.eye[1], 230) && near(view.eye[2], 2940));
    CHECK(near(view.at[0], 1000) && near(view.at[2], 2940));
    printf("source Player-relative position/yaw: pass\n");

    reset();
    CollisionHeader collision = {};
    BgCamInfo cameras[2] = {};
    BgCamFuncData browse = {};
    browse.pos = {-30,60,60};browse.rot.y=(s16)0x8000;browse.fov=6000;browse.flags=3;
    cameras[1].setting=CAM_SET_PIVOT_SHOP_BROWSING;
    cameras[1].bgCamFuncData=(Vec3s*)&browse;
    collision.bgCamList=cameras;play.colCtx.colHeader=&collision;
    play.sceneId=SCENE_BAZAAR;player.stateFlags2|=PLAYER_STATE2_29;
    OotCore_CutsceneCameraStep(&play);
    CHECK(OotCore_CutsceneCameraRead(&play,&view));
    CHECK(view.eye[0]==-30 && view.eye[1]==60 && view.eye[2]==60 && view.at[2]==-140);
    CHECK(view.fov_q8==60*256);
    Camera_SetCameraData(&play.mainCamera,CAM_DATA_SET_2,NULL,NULL,90,0,0);
    OotCore_CutsceneCameraStep(&play);
    CHECK(OotCore_CutsceneCameraRead(&play,&view) && view.at[0]==-230);
    player.stateFlags2&=~PLAYER_STATE2_29;
    CHECK(!OotCore_CutsceneCameraRead(&play,&view));
    printf("source shop fixed eye/angle/FOV/release: pass\n");

    reset();
    OotCoreCutsceneCameraView seed = {{950,250,2850},{1000,240,3000},60*256,0,0,0};
    OotCore_CutsceneCameraSeed(&play,&seed);
    CHECK((int)play.mainCamera.eye.x==950 && (int)play.view.fovy==60);
    player.actor.focus.pos=player.actor.world.pos;player.actor.focus.pos.y+=40;
    Actor owl={};owl.update=alive;owl.world.pos={1100,250,3300};
    owl.focus.pos=owl.world.pos;owl.focus.pos.y+=60;owl.shape.rot.y=(s16)0x8000;
    s16 owlCamera=OnePointCutscene_Init(&play,8700,-100,&owl,CAM_ID_MAIN);
    CHECK(owlCamera==1 && play.activeCamId==1);
    seed.eye[0]=0;OotCore_CutsceneCameraSeed(&play,&seed);
    CHECK((int)play.mainCamera.eye.x==950);
    for(unsigned i=0;i<90;++i)OotCore_CutsceneCameraStep(&play);
    CHECK(OotCore_CutsceneCameraRead(&play,&held));
    CHECK(held.fov_q8>49*256 && held.fov_q8<51*256);
    CHECK(held.eye[2]<3300 && held.at[2]<3300);
    for(unsigned i=0;i<90;++i)OotCore_CutsceneCameraStep(&play);
    CHECK(OotCore_CutsceneCameraRead(&play,&view));
    CHECK(play.activeCamId==owlCamera && view.fov_q8==held.fov_q8);
    for(unsigned i=0;i<3;++i)CHECK(view.eye[i]==held.eye[i] && view.at[i]==held.at[i]);
    Camera_SetFinishedFlag(&play.mainCamera);
    OotCore_CutsceneCameraStep(&play);OotCore_CutsceneCameraStep(&play);
    CHECK(player.csAction==PLAYER_CSACTION_1);
    owl.world.pos.x+=100;owl.focus.pos.x+=100;
    for(unsigned i=0;i<300 && play.activeCamId!=CAM_ID_MAIN;++i)OotCore_CutsceneCameraStep(&play);
    CHECK(play.activeCamId==CAM_ID_MAIN && !play.cameraPtrs[owlCamera]);
    CHECK(play.mainCamera.childCamId==CAM_ID_MAIN);
    CHECK(!OotCore_CutsceneCameraRead(&play,&view));
    CHECK(Letterbox_GetSizeTarget()==0);
    CHECK(OnePointCutscene_Init(&play,9999,-1,&owl,CAM_ID_MAIN)==CAM_ID_NONE);
    printf("source owl 8700 entry/dialogue hold/departure/return: pass\n");

    reset();
    OotCore_CutsceneCameraSeed(&play,&seed);
    s16 platform=OnePointCutscene_Init(&play,3060,51,&owl,CAM_ID_MAIN);
    CHECK(platform==1 && player.csAction==PLAYER_CSACTION_8);
    OotCore_CutsceneCameraStep(&play);
    CHECK(OotCore_CutsceneCameraRead(&play,&view));
    CHECK(view.at[0]==165 && view.at[1]==85 && view.eye[0]==65 && view.eye[2]==-720);
    for(int i=0;i<70 && play.activeCamId!=CAM_ID_MAIN;++i)OotCore_CutsceneCameraStep(&play);
    CHECK(play.activeCamId==CAM_ID_MAIN && player.csAction==PLAYER_CSACTION_7);
    CHECK((int)play.mainCamera.eye.x==seed.eye[0]); /* action 17 does not copy */
    CHECK(!play.mainCamera.childCamId);
    printf("source DC platform shot/timer/player release/no-copy return: pass\n");

    reset();
    OotCore_CutsceneCameraSeed(&play,&seed);
    s16 stairs=OnePointCutscene_Init(&play,3050,-99,&owl,CAM_ID_MAIN);
    CHECK(stairs==1 && play.cameraPtrs[stairs]->setting==CAM_SET_CS_3);
    OotCore_CutsceneCameraStep(&play);
    CHECK(OotCore_CutsceneCameraRead(&play,&view) && view.eye[0]<-1700 && view.eye[1]>400);
    bool returned=false;
    for(int i=0;i<300 && play.activeCamId!=CAM_ID_MAIN;++i) {
        OotCore_CutsceneCameraStep(&play);
        Camera* active=play.cameraPtrs[play.activeCamId];
        if(active && active->csId==1020) returned=true;
    }
    CHECK(returned && play.activeCamId==CAM_ID_MAIN && !play.mainCamera.childCamId);
    CHECK(player.csAction==PLAYER_CSACTION_7);
    printf("source DC stairs Demo9 spline/queued 1020 return/player release: pass\n");

    reset();
    OotCore_CutsceneCameraSeed(&play,&seed);
    s16 darunia=OnePointCutscene_Init(&play,3330,-99,&owl,CAM_ID_MAIN);
    for(int i=0;i<100;++i)OotCore_CutsceneCameraStep(&play);
    CHECK(play.activeCamId==darunia);
    CHECK(OotCore_CutsceneCameraRead(&play,&held));
    for(int i=0;i<50;++i)OotCore_CutsceneCameraStep(&play);
    CHECK(OotCore_CutsceneCameraRead(&play,&view));
    CHECK(view.eye[0]==held.eye[0] && view.at[2]==held.at[2]);
    Camera_SetFinishedFlag(&play.mainCamera);
    for(int i=0;i<130 && play.activeCamId!=CAM_ID_MAIN;++i)OotCore_CutsceneCameraStep(&play);
    CHECK(play.activeCamId==CAM_ID_MAIN && player.csAction==PLAYER_CSACTION_7);
    printf("source Darunia spherical camera/reward hold/release: pass\n");

    reset();
    OotCore_CutsceneCameraSeed(&play,&seed);
    s16 warp=OnePointCutscene_Init(&play,9703,999,&owl,CAM_ID_MAIN);
    for(int i=0;i<91;++i)OotCore_CutsceneCameraStep(&play);
    CHECK(play.activeCamId==warp && OotCore_CutsceneCameraRead(&play,&held));
    player.actor.world.pos.y+=10;
    for(int i=0;i<5;++i)OotCore_CutsceneCameraStep(&play);
    CHECK(OotCore_CutsceneCameraRead(&play,&view));
    CHECK(view.eye[0]!=held.eye[0] || view.eye[2]!=held.eye[2]);
    CHECK(view.at[1]>held.at[1]);
    printf("source child boss warp orbit/follows ascending Player: pass\n");

    reset();
    seed.eye[0]=1000;seed.eye[1]=240;seed.eye[2]=2800;
    seed.at[0]=1000;seed.at[1]=240;seed.at[2]=3000;
    OotCore_CutsceneCameraSeed(&play,&seed);
    player.actor.focus.pos={1000,240,3000};
    Actor button={},chest={};
    button.update=chest.update=alive;
    button.category=ACTORCAT_SWITCH;chest.category=ACTORCAT_CHEST;
    button.focus.pos=button.world.pos={1000,230,3050};
    chest.focus.pos=chest.world.pos={1050,230,3090};
    s16 screenX,screenY;
    OotCore_CameraActorScreenPos(&play,&button,&screenX,&screenY);
    CHECK(screenX==160 && screenY>120 && screenY<160);
    s16 buttonCam=OnePointCutscene_AttentionSetSfx(&play,&button,0x4812);
    CHECK(buttonCam==1 && OnePointCutscene_CheckForCategory(&play,ACTORCAT_SWITCH));
    CHECK(OnePointCutscene_Attention(&play,&button)==CAM_ID_NONE);
    s16 chestCam=OnePointCutscene_Attention(&play,&chest);
    CHECK(chestCam==2 && play.activeCamId==buttonCam);
    CHECK(play.cameraPtrs[chestCam]->childCamId==buttonCam);
    lastCameraSfx=0;
    OotCore_CutsceneCameraStep(&play);
    CHECK(lastCameraSfx==0x4812 && play.cameraPtrs[buttonCam]->setting==CAM_SET_CS_C);
    CHECK(OotCore_CutsceneCameraRead(&play,&view));
    bool showedChest=false;
    for(int i=0;i<260 && play.activeCamId!=CAM_ID_MAIN;++i) {
        ++play.state.frames;
        OotCore_CutsceneCameraStep(&play);
        if(play.activeCamId==chestCam) showedChest=true;
    }
    CHECK(showedChest && play.activeCamId==CAM_ID_MAIN && !play.mainCamera.childCamId);
    CHECK(!play.cameraPtrs[buttonCam] && !play.cameraPtrs[chestCam]);
    CHECK(player.csAction==PLAYER_CSACTION_7);
    printf("source attention projection/category queue/chime/chest/switch/player release: pass\n");

    reset();
    OotCore_CutsceneCameraSeed(&play,&seed);
    Camera_RequestSetting(&play.mainCamera,CAM_SET_FREE0);
    play.mainCamera.eye={-440,117,0};play.mainCamera.at={-490,120,0};play.mainCamera.fov=45;
    Letterbox_SetSizeTarget(32);
    OotCore_CutsceneCameraStep(&play);
    CHECK(OotCore_CutsceneCameraRead(&play,&view) && view.eye[0]==-440 && view.fov_q8==45*256);
    OotCore_CutsceneCameraSeed(&play,&seed);
    CHECK((int)play.mainCamera.eye.x==-440 && Letterbox_GetSizeTarget()==32);
    Camera_RequestSetting(&play.mainCamera,CAM_SET_CS_0);
    Camera_SetCSParams(&play.mainCamera,atPoints,eyePoints,&player,0);
    Camera_ResetAnim(&play.mainCamera);
    OotCore_CutsceneCameraStep(&play);
    CHECK(OotCore_CutsceneCameraRead(&play,&view) && near(view.eye[0],60));
    Camera_RequestSetting(&play.mainCamera,CAM_SET_NORMAL0);
    OotCore_CutsceneCameraStep(&play);
    CHECK(!OotCore_CutsceneCameraRead(&play,&view) && Letterbox_GetSizeTarget()==0);
    OotCore_CutsceneCameraSeed(&play,&seed);
    CHECK((int)play.mainCamera.eye.x==seed.eye[0]);
    printf("source courtyard main camera/direct/spline/normal release: pass\n");

    reset();
    start_spline(false);

    Letterbox_SetSizeTarget(32);
    OotCore_CutsceneCameraStep(&play);
    CHECK(Letterbox_GetSize() == 10);
    OotCore_CutsceneCameraStep(&play);
    OotCore_CutsceneCameraStep(&play);
    OotCore_CutsceneCameraStep(&play);
    CHECK(Letterbox_GetSize() == 32);
    OotCore_CutsceneCameraRead(&play, &view);
    CHECK(view.letterbox == 32);
    Play_ChangeCameraStatus(&play, CAM_ID_MAIN, CAM_STAT_ACTIVE);
    Play_ClearCamera(&play, 1);
    OotCore_CutsceneCameraStep(&play);
    CHECK(Letterbox_GetSizeTarget() == 0 && Letterbox_GetSize() == 22);
    reset();
    CHECK(!OotCore_CutsceneCameraRead(&play, &view) && !view.letterbox);
    printf("letterbox growth/exit/reset: pass\n");
    return 0;
}
