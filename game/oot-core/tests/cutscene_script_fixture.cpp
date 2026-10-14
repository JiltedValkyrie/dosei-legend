/* Real source dispatcher, cue selection, text/audio/misc commands and camera.
 * Device services are deterministic observations. Destination loading and
 * actor animation/rendering are outside this fixture. */
#define main camera_fixture_main
#include "cutscene_camera_fixture.cpp"
#undef main
#include "audio.h"
#include "cutscene_flags.h"
#include "environment.h"
#include "interface.h"
#include "memory_utils.h"
#include "message.h"
#include "ocarina.h"
#include "quake.h"
#include "regs.h"
#include "rumble.h"
#include "save.h"
#include "scene.h"
#include "seqcmd.h"
#include "sfx.h"
#include "transition.h"
#include "z_lib.h"
static_assert(sizeof(CutsceneData)==4 && sizeof(CsCmdMisc)==48 && sizeof(CsCmdActorCue)==48,
              "source script ABI must match SH-2");

LightningStrike gLightningStrike;
Color_RGBA8_u32 gVisMonoColor;
u8 gWeatherMode;
u16 gTimeSpeed;
u16 sCurTextId, sCurOcarinaAction, gCamAtSplinePointsAppliedFrame;
u16 gCamEyePointAppliedFrame, gCamAtPointAppliedFrame;
s16 sReturnToCamId, sQuakeIndex;
u8 gUseCutsceneCam;
u32 gBitFlags[32];
Vec3f gSfxDefaultPos;
f32 gSfxDefaultFreqAndVolScale;
s8 gSfxDefaultReverb;
void Audio_PlaySfxGeneral(u16,Vec3f*,u8,f32*,f32*,s8*) {}
static unsigned titleCards, lastText, lastStartSequence, lastStopSequence, destination;
static bool lullabyTeach, lullabyPlayback;
void* MemCopy(void* dst, void* src, s32 n) { return __builtin_memcpy(dst, src, n); }
f32 Environment_LerpWeight(u16 end, u16 start, u16 frame) {
    if (end <= start || frame >= end) return 1;
    if (frame <= start) return 0;
    return f32(frame-start) / f32(end-start);
}
void Audio_SetNatureAmbienceChannelIO(u8,u8,u8) {}
void Environment_AddLightningBolts(PlayState*,u8) {}
void CutsceneFlags_Set(PlayState*,s16) {}
void Sfx_PlaySfxCentered2(u16) {}
void Play_SetViewpoint(PlayState* p,s16 v) {p->viewpoint=v;}
void TitleCard_InitPlaceName(PlayState*,TitleCardContext*,void*,s32,s32,s32,s32,s32) {++titleCards;}
u32 Quake_RemoveRequest(s16) {return 1;}
void AudioOcarina_PlayLongScarecrowSong(void) {CHECK(false);}
void Audio_PlaySequenceInCutscene(u16 id) {lastStartSequence=id;}
void Audio_StopSequenceInCutscene(u16 id) {lastStopSequence=id;}
void Audio_QueueSeqCmd(u32) {}
void Rumble_Request(FxSq,u8,u8,u8) {}
void Message_StartTextbox(PlayState*,u16 id,Actor*) {lastText=id;}
void Message_ContinueTextbox(PlayState*,u16 id) {lastText=id;}
void Message_StartOcarina(PlayState*,u16 id) {
    lastText=id;
    if(id==OCARINA_ACTION_TEACH_LULLABY) lullabyTeach=true;
    if(id==OCARINA_ACTION_PLAYBACK_LULLABY) lullabyPlayback=true;
}
u8 Message_GetState(MessageContext*) {return TEXT_STATE_NONE;}
u8 Message_ShouldAdvance(PlayState*) {return true;}
void CutsceneCmd_Destination(PlayState*,CutsceneContext* cs,CsCmdDestination* cmd) {
    if (cs->curFrame == cmd->startFrame) destination=cmd->destination;
}
#include "cutscene_script_source.inc"

static void begin_script(void) {
    reset(); bzero(&gSaveContext,sizeof(gSaveContext));
    for(unsigned i=0;i<32;++i) gBitFlags[i]=1u<<i;
    gUseCutsceneCam=true;sReturnToCamId=CAM_ID_MAIN;
    sCurTextId=sCurOcarinaAction=0;
    gCamAtSplinePointsAppliedFrame=gCamEyePointAppliedFrame=gCamAtPointAppliedFrame=0xffff;
    play.csCtx.camEyeSplinePointsAppliedFrame=0xffff;
    play.csCtx.subCamId=Play_CreateSubCamera(&play);
    play.csCtx.state=CS_STATE_RUN;
    titleCards=lastText=lastStartSequence=lastStopSequence=destination=0;
    lullabyTeach=lullabyPlayback=false;
}
static OotCoreCutsceneCameraView step_script(CutsceneData* data,unsigned frame) {
    play.csCtx.curFrame=frame;
    Cutscene_ProcessScript(&play,&play.csCtx,(u8*)data);
    OotCore_CutsceneCameraStep(&play);
    OotCoreCutsceneCameraView view;
    OotCore_CutsceneCameraRead(&play,&view);
    return view;
}
int main(void) {
    begin_script();
    OotCoreCutsceneCameraView view=step_script(gGoronCityDaruniaDancingCs,1);
    CHECK(play.csCtx.actorCues[2] && play.csCtx.actorCues[2]->id==1);
    CHECK(play.csCtx.playerCue && play.csCtx.playerCue->id==PLAYER_CUEID_5);
    CHECK(view.active && near(view.eye[0],91) && near(view.eye[1],93) && near(view.eye[2],-1393));
    /* Source At spline controls FOV too: 45.8*(1/6+4/6)+35.8/6. */
    CHECK(view.fov_q8>44*256 && view.fov_q8<45*256);
    for(unsigned frame=2;frame<=710;++frame) {
        view=step_script(gGoronCityDaruniaDancingCs,frame);
        if(frame==30) CHECK(lastStartSequence==NA_BGM_SARIA_THEME);
        if(frame==55) CHECK(play.csCtx.actorCues[2]->id==1);
        if(frame==56) CHECK(play.csCtx.actorCues[2]->id==7);
        if(frame==45) CHECK(view.roll>6000 && view.roll<6600);
        if(frame==201) CHECK(play.csCtx.playerCue->id==PLAYER_CUEID_40);
        if(frame==336) CHECK(lastText==0x3007);
        if(frame==708) CHECK(lastStartSequence==NA_BGM_GORON_CITY);
    }
    CHECK(play.csCtx.state==CS_STATE_STOP);
    printf("complete Darunia dance: cue boundaries, camera/FOV/roll, sequences/text/stop pass\n");

    begin_script();
    for(unsigned frame=0;frame<=170;++frame) {
        view=step_script(gDcOpeningCs,frame);
        if(frame==1) CHECK(view.active && near(view.eye[0],147) && near(view.eye[2],269));
        if(frame==50) CHECK(titleCards==1);
    }
    CHECK(play.csCtx.state==CS_STATE_STOP && titleCards==1);
    printf("complete Dodongo opening: title command, camera and stop pass\n");

    begin_script();
    for(unsigned frame=0;frame<=3000 && !destination;++frame)
        view=step_script(gLonLonRanchEponasSongCs,frame);
    CHECK(destination==CS_DEST_LON_LON_RANCH_FROM_EPONAS_SONG && view.active);
    CHECK(lastStartSequence==NA_BGM_OCA_FAIRY_GET);
    printf("complete Epona song: relative camera, sequence and destination dispatch pass\n");

    begin_script();
    for(unsigned frame=1;frame<=210;++frame) {
        view=step_script(gZeldasCourtyardGanonCs,frame);
        if(frame==1) CHECK(view.active && near(view.eye[0],-461) && view.fov_q8>45*256);
        if(frame==57) CHECK(play.csCtx.actorCues[1]->id==9);
        if(frame==58) CHECK(play.csCtx.actorCues[1]->id==10);
        if(frame==197) CHECK(play.csCtx.actorCues[1]->id==4);
    }
    CHECK(play.csCtx.state==CS_STATE_STOP && lastText==0x7009);
    printf("complete courtyard Ganondorf window: walk/kneel/look cues, zoom, text and stop pass\n");

    begin_script();
    for(unsigned frame=1;frame<=875;++frame) {
        view=step_script(gZeldasCourtyardLullabyCs,frame);
        if(frame==1) CHECK(view.active && play.csCtx.actorCues[5]->id==2);
        if(frame==243) CHECK(play.csCtx.actorCues[5]->id==7);
        if(frame==537) CHECK(play.csCtx.actorCues[5]->id==8);
        if(frame==538) CHECK(play.csCtx.actorCues[5]->id==9);
        if(frame==611) CHECK(play.csCtx.playerCue->id==PLAYER_CUEID_66);
    }
    CHECK(lullabyTeach && lullabyPlayback && lastStartSequence==NA_BGM_OCA_FAIRY_GET);
    CHECK(destination==CS_DEST_HYRULE_FIELD_FROM_ZELDAS_COURTYARD && lastText==0x708E);
    printf("complete Impa Lullaby: cue chain, teach/playback commands, reward sequence and Field dispatch pass\n");

    begin_script();
    for(unsigned frame=1;frame<=740;++frame) {
        view=step_script(gCutsceneMapThreeGoddessesCs,frame);
        if(frame==1) CHECK(view.active && near(view.eye[0],-10) && near(view.eye[1],375));
        if(frame==20) CHECK(play.csCtx.actorCues[0]->startPos.y==200);
        if(frame==21) CHECK(play.csCtx.actorCues[0]->startPos.y==400);
        if(frame==372) CHECK(play.csCtx.actorCues[0]->id==2);
        if(frame==382) CHECK(play.csCtx.actorCues[1]->id==2);
        if(frame==392) CHECK(play.csCtx.actorCues[2]->id==2);
        if(frame==391) CHECK(play.csCtx.actorCues[3]->id==2);
    }
    CHECK(destination==CS_DEST_ZELDAS_COURTYARD_RECEIVE_LETTER && lastText==0x7036);
    printf("complete Three Goddesses legend: all deity/Triforce cues, spline and letter-return dispatch pass\n");
    return 0;
}
