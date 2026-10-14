/* Source audio/game/general.c intent, adapted to one Saturn music bank.
 * Source channels survive the offline SCSP voice allocation. Nearest-source
 * selection and volume gates stay here; no sound hardware on the slave. */
#include "oot_prelude.h"
#include "audio.h"
#include "play_state.h"
#include "save.h"
#include "sfx.h"
#include "oot_core_audio.h"
#include "oot_core_host.h"

extern PlayState* gOotCorePlay;
extern const OotCoreHost* gOotCoreHost;
static unsigned sSinging=0x7f7f, sSpatial=0x407f;
static unsigned sLastSinging=~0u, sLastSpatial=~0u;
static int sNearest=0x7fffffff;
static u8 sMalonDisabled, sLower=127, sLastLower=127;
static u16 sSubSequence=0xffff, sWantedSequence=0xffff;

void OotCore_RouteAudioBegin(void) {
    sSinging=0x7f7f;sSpatial=0x407f;sNearest=0x7fffffff;sLower=127;sWantedSequence=0xffff;
    if(gOotCorePlay && gOotCorePlay->gameplayFrames==0){
        sMalonDisabled=0;sSubSequence=0xffff;
        sLastSinging=sLastSpatial=~0u;sLastLower=255;
    }
}

void OotCore_RouteAudioEnd(void) {
    if(sWantedSequence!=sSubSequence){
        if(sSubSequence!=0xffff)OotCore_AudioRequest(OOT_CORE_AUDIO_POP_SEQUENCE,0);
        if(sWantedSequence!=0xffff)OotCore_AudioRequest(OOT_CORE_AUDIO_PUSH_SEQUENCE,sWantedSequence);
        sSubSequence=sWantedSequence;
    }
    if(sLastSinging!=sSinging){OotCore_AudioRequest(OOT_CORE_AUDIO_SINGING,sSinging);sLastSinging=sSinging;}
    if(sLastSpatial!=sSpatial){OotCore_AudioRequest(OOT_CORE_AUDIO_SPATIAL,sSpatial);sLastSpatial=sSpatial;}
    if(sLastLower!=sLower){OotCore_AudioRequest(OOT_CORE_AUDIO_MAIN_VOLUME,sLower|(10u<<8));sLastLower=sLower;}
}

void Audio_ToggleMalonSinging(u8 disabled) { sMalonDisabled=disabled; }
void Audio_UpdateMalonSinging(f32 distance,u16 seqId) {
    if((seqId&0xff)!=NA_BGM_LONLON || !gOotCorePlay)return;
    int dist=(int)distance;
    unsigned melody=dist>2000?127:dist<200?0:(unsigned)(dist-200)*127/1800;
    unsigned alone=gOotCorePlay->sceneSequences.seqId==NA_BGM_NATURE_AMBIENCE;
    if(alone && !sMalonDisabled)sWantedSequence=NA_BGM_LONLON;
    sSinging=(sMalonDisabled?0:127-melody)|(melody<<8)|(alone?0x8000:0);
}

void Audio_LowerMainBgmVolume(u8 volume) { sLower=volume; }
void func_800F4E30(Vec3f* pos,f32 distance) {
    int dist=(int)distance;
    if(dist>sNearest)return;
    sNearest=dist;
    int x=(int)pos->x;
    unsigned pan=x>100?127:x<-100?0:(unsigned)(x*64/100+64);
    unsigned gain=dist>400?12:dist<120?127:127-(unsigned)(dist-120)*114/280;
    sSpatial=gain|(pan<<8);
}

void Audio_PlaySariaBgm(Vec3f* pos,u16 seqId,u16 distMax) {
    /* Nearest XZ source, integer octagonal norm: bounded, no squared Fx
     * overflow. A single bank carries the stronger source on Saturn. */
    int x=(int)pos->x,z=(int)pos->z,y=(int)pos->y;
    if(x<0)x=-x;if(z<0)z=-z;if(y<0)y=-y;
    int dist=x>z?x+z/2:z+x/2;
    if(!distMax || dist>sNearest)return;
    sNearest=dist;
    unsigned gain=y>distMax/15 || dist>=distMax?0:127-(unsigned)dist*127/distMax;
    if(gain){sWantedSequence=seqId&0xff;sSpatial=gain|(64u<<8);}
}

void Audio_ClearSariaBgm(void) { sWantedSequence=0xffff;sSpatial=0x407f; }
void Audio_ClearSariaBgm2(void) { Audio_ClearSariaBgm(); }
void Audio_ClearSariaBgmAtPos(Vec3f*) { Audio_ClearSariaBgm(); }
void OotCore_AudioSfxPitched(u16 sfxId,Vec3f* pos,f32 frequency) {
    int ratio=(int)(frequency*64);
    if(ratio<1)ratio=1;if(ratio>255)ratio=255;
    if(ratio!=64)OotCore_AudioRequest(OOT_CORE_AUDIO_SFX_PITCH|((unsigned)ratio<<8),sfxId);
    else if(gOotCoreHost && gOotCoreHost->play_sfx)
        gOotCoreHost->play_sfx(sfxId,pos?(int)pos->x:0,pos?(int)pos->y:0,pos?(int)pos->z:0);
}
static f32 sMotionFrequency=FXL(1.0f);
static s8 sFlapCount=20,sFlapFast=30,sFlapSlow=20;
void func_800F436C(Vec3f* pos,u16 sfxId,f32 weight) {
    sMotionFrequency=weight<FXL(0.75f)?weight/FXL(3.0f)+FXL(0.5f):weight;
    if(sMotionFrequency>FXL(0.5f))OotCore_AudioSfxPitched(sfxId,pos,sMotionFrequency);
}
void func_800F4414(Vec3f* pos,u16 sfxId,f32 weight) {
    if(--sFlapCount==0){
        OotCore_AudioSfxPitched(sfxId,pos,sMotionFrequency);
        if(weight>FXL(2.0f))weight=FXL(2.0f);
        sFlapCount=(s8)((sFlapSlow-sFlapFast)*(FXL(1.0f)-weight))+sFlapSlow;
    }
}
void func_800F44EC(s8 slow,s8 fast) { sFlapCount=1;sFlapFast=fast;sFlapSlow=slow; }
void Audio_PlaySfxRiver(Vec3f* pos,f32 freqScale) {
    OotCore_AudioSfxPitched(NA_SE_EV_RIVER_STREAM-SFX_FLAG,pos,freqScale);
}
void func_800F5BF0(u8 natureAmbienceId) {
    OotCore_AudioRequest(OOT_CORE_AUDIO_PUSH_SEQUENCE,NA_BGM_NATURE_AMBIENCE);
}
void func_800F5C2C(void) { OotCore_AudioRequest(OOT_CORE_AUDIO_POP_SEQUENCE,0); }
void Audio_SetMainBgmTempoFreqAfterFanfare(f32 scale,u8) {
    /* Host queue waits for the fanfare; source pitch shift is not applied. */
    OotCore_AudioRequest(OOT_CORE_AUDIO_TEMPO,(unsigned)(int)(scale*256));
}
void Audio_PlayNatureAmbienceSequence(u8) {
    /* Source replaces main BGM with the ambience sequence; no Saturn nature
     * channels yet, so the host renders it as silence (pending backend). */
    OotCore_AudioRequest(OOT_CORE_AUDIO_SEQUENCE,NA_BGM_NATURE_AMBIENCE);
}
void Audio_SetGanonsTowerBgmVolumeLevel(u8 level) {
    /* Source volume table; N64 filter/reverb and level-7 2-frame delay omitted. */
    static const u8 vol[8]={127,80,75,73,70,68,65,60};
    OotCore_AudioRequest(OOT_CORE_AUDIO_MAIN_VOLUME,vol[level&7]|(2u<<8));
}
void Audio_PlaySfxTransposed(Vec3f* pos,u16 sfxId,s8 semitone) {
    /* Source gPitchFrequencies, rounded offline to Q12; no runtime float. */
    static const u16 notes[12]={4096,4340,4598,4871,5161,5468,5793,6137,6502,6889,7298,7732};
    int octave=0,note=semitone;
    while(note<0){note+=12;--octave;}while(note>=12){note-=12;++octave;}
    unsigned ratio=notes[note];
    if(octave>0)ratio<<=octave>4?4:octave;
    else if(octave<0)ratio>>=(-octave>4?4:-octave);
    OotCore_AudioSfxPitched(sfxId,pos,Fx::raw(ratio<<4));
}
