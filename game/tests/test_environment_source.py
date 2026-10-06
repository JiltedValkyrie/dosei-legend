"""Execute the imported NTSC clock with host state, without Saturn rendering."""
import ctypes
import os
import pathlib
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'tools'))
from environment_source import (clock_source, room_clock_source, room_time, sky_schedule,
    room_behavior, sun_song_source, destination_layer_source, transition_clock_source,
    clock_events_source)

OOT = pathlib.Path('D:/Workspace-Claude/game-decomps/n64/oot')
GCC = pathlib.Path('C:/msys64/mingw64/bin/gcc.exe')


@unittest.skipUnless(OOT.exists() and GCC.exists(), 'source and host GCC required')
class EnvironmentSource(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        folder = pathlib.Path(cls.temp.name)
        stub = r'''
#include <stdint.h>
typedef uint16_t u16;
typedef uint8_t u8;
typedef int16_t s16;
typedef int32_t s32;
typedef struct {int state;} PauseContext, GameOverContext;
typedef struct {int msgLength,msgMode,disableWarpSongs,disableSunsSong,ocarinaAction,ocarinaMode;} MessageContext;
typedef struct {int changeSkyboxTimer,sceneTimeSpeed;} EnvironmentContext;
typedef struct {struct {int sunsSong;} restrictions;} InterfaceContext;
typedef struct {PauseContext pauseCtx; GameOverContext gameOverCtx;
 MessageContext msgCtx; EnvironmentContext envCtx; int transitionMode;
 InterfaceContext interfaceCtx; struct {struct {int type;} curRoom;} roomCtx;
 int transitionType,haltAllActors,sceneId,nextEntranceIndex,transitionTrigger;} PlayState;
struct {struct {u16 dayTime;int nightFlag,cutsceneIndex,entranceIndex,linkAge,totalDays,bgsDayCount;} save;
 u16 skyboxTime,nextDayTime;int gameMode,sceneLayer,sunsSongState,nextTransitionType,respawnFlag,
 seqId,natureAmbienceId,dogIsLost;} gSaveContext;
typedef struct {u16 time;unsigned char time_speed,time_flags,room_type,behavior_flags;} OotSceneLayer;
u16 gTimeSpeed;
int advance,stones,event48,rental,last_sfx;
#define FrameAdvance_IsEnabled(p) advance
#define PAUSE_STATE_OFF 0
#define GAMEOVER_INACTIVE 0
#define MSGMODE_NONE 0
#define GAMEMODE_END_CREDITS 1
#define GAMEMODE_NORMAL 0
#define TRANS_MODE_OFF 0
#define IS_DAY (gSaveContext.save.nightFlag == 0)
#define OOT_VERSION NTSC_1_2
#include "versions.h"
#define CS_INDEX_0 0xFFF0
#define ENTR_LAKE_HYLIA_8 0x604
#define SUNSSONG_INACTIVE 0
#define SUNSSONG_START 1
#define SUNSSONG_SPEED_TIME 2
#define SUNSSONG_SPECIAL 3
#define NEXT_TIME_NONE 0xffff
#define NEXT_TIME_DAY_SET 0xfffe
#define NEXT_TIME_NIGHT_SET 0xfffd
#define NA_SE_EV_CHICKEN_CRY_M 1
#define NA_SE_EV_DOG_CRY_EVENING 2
#define Sfx_PlaySfxCentered(i) (last_sfx=(i))
#define Sfx_PlaySfxCentered2(i) (last_sfx=(i))
#define false 0
#define true 1
#define OCARINA_ACTION_CHECK_NOWARP_DONE 10
#define OCARINA_MODE_04 4
#define OCARINA_MODE_08 8
#define INGO_RACE_STATE_HORSE_RENTAL_PERIOD 1
#define GET_EVENTINF_INGO_RACE_STATE() rental
#define ROOM_TYPE_DUNGEON 1
#define TRANS_TYPE_FADE_BLACK_FAST 1
#define TRANS_TYPE_FADE_BLACK 2
#define TRANS_TYPE_FADE_WHITE_FAST 3
#define TRANS_TYPE_FADE_WHITE 4
#define TRANS_TYPE_SANDSTORM_PERSIST 5
#define TRANS_TRIGGER_START 1
#define SCENE_HAUNTED_WASTELAND 94
#define NA_BGM_DISABLED 255
#define NATURE_ID_DISABLED 255
#define OotCore_SunSongAudioFade(frames) ((void)(frames))
#define LINK_IS_ADULT (gSaveContext.save.linkAge==0)
#define SCENE_LAYER_CHILD_DAY 0
#define SCENE_LAYER_CHILD_NIGHT 1
#define SCENE_LAYER_ADULT_DAY 2
#define SCENE_LAYER_ADULT_NIGHT 3
#define SCENE_LAYER_CUTSCENE_FIRST 4
#define GET_CUTSCENE_LAYER(i) (4+((i)&15))
#define SCENE_HYRULE_FIELD 81
#define SCENE_KOKIRI_FOREST 85
#define QUEST_KOKIRI_EMERALD 0
#define QUEST_GORON_RUBY 1
#define QUEST_ZORA_SAPPHIRE 2
#define CHECK_QUEST_ITEM(i) (stones&(1<<(i)))
#define EVENTCHKINF_48 0x48
#define GET_EVENTCHKINF(i) event48
#define ITEM_WEIRD_EGG 0x21
#define ITEM_CHICKEN 0x22
#define ITEM_POCKET_EGG 0x2d
#define ITEM_POCKET_CUCCO 0x2e
#define OotCore_ReplaceDayItem(p,a,b) 0
#define Message_StartTextbox(p,id,actor) ((void)0)
#include <string.h>
#include <stddef.h>
static void OotCore_DaySequenceUpdate(PlayState* play) { (void)play; }
'''
        wrapper = r'''
unsigned tick(unsigned time,unsigned sky,unsigned speed,unsigned flags) {
 PlayState p={0};
 gSaveContext.nextDayTime=NEXT_TIME_NONE;
 gSaveContext.save.dayTime=time;gSaveContext.skyboxTime=sky;gTimeSpeed=speed;
 gSaveContext.save.nightFlag=time>49152 || time<17749;
 gSaveContext.gameMode=(flags>>7)&1;
 gSaveContext.sceneLayer=(flags&256)?5:0;
 p.pauseCtx.state=flags&1;p.gameOverCtx.state=(flags>>1)&1;
 p.msgCtx.msgLength=(flags>>2)&1;p.msgCtx.msgMode=(flags>>3)&1;
 p.envCtx.changeSkyboxTimer=(flags>>4)&1;advance=(flags>>5)&1;
 p.transitionMode=(flags>>6)&1;
 OotCore_EnvironmentClock(&p);
 return gSaveContext.save.dayTime | ((unsigned)gSaveContext.skyboxTime<<16);
}
unsigned room(unsigned time,unsigned sky,unsigned speed,unsigned entrance) {
 PlayState p={0};OotSceneLayer layer={0,speed,1};
 gSaveContext.save.dayTime=time;gSaveContext.skyboxTime=sky;
 gSaveContext.save.cutsceneIndex=0;gSaveContext.save.entranceIndex=entrance;
 gSaveContext.sunsSongState=0;
 OotCore_EnvironmentRoom(&p,&layer);
 return gSaveContext.save.dayTime | ((unsigned)gSaveContext.skyboxTime<<16);
}
static PlayState song_play;
void song_setup(unsigned time,unsigned speed,unsigned type,unsigned restriction) {
 memset(&song_play,0,sizeof(song_play));memset(&gSaveContext,0,sizeof(gSaveContext));
 gSaveContext.save.dayTime=time;gSaveContext.skyboxTime=time;
 gSaveContext.save.nightFlag=time>49152||time<17749;
 gSaveContext.save.entranceIndex=0x33;gSaveContext.nextDayTime=NEXT_TIME_NONE;
 song_play.envCtx.sceneTimeSpeed=speed;gTimeSpeed=speed;
 song_play.roomCtx.curRoom.type=type;song_play.interfaceCtx.restrictions.sunsSong=restriction;
 rental=advance=last_sfx=0;OotCore_SunSongStart(&song_play);
}
unsigned song_tick(void) {
 OotCore_SunSongUpdate(&song_play);OotCore_EnvironmentEvents(&song_play);OotCore_EnvironmentClock(&song_play);
 return gSaveContext.save.dayTime|((unsigned)gSaveContext.sunsSongState<<16);
}
unsigned song_field(unsigned which) {
 switch(which){case 0:return gTimeSpeed;case 1:return gSaveContext.nextDayTime;
 case 2:return song_play.nextEntranceIndex;case 3:return song_play.transitionTrigger;
 case 4:return gSaveContext.respawnFlag;case 5:return last_sfx;case 6:return gSaveContext.save.totalDays;
 case 7:return song_play.transitionType;case 8:return gSaveContext.save.dayTime;
 case 9:return gSaveContext.skyboxTime;default:return 0;}
}
void song_time(unsigned time) {
 gSaveContext.save.dayTime=time;gSaveContext.save.nightFlag=time>49152||time<17749;
}
void song_load(void){OotCore_TransitionTimeBegin();OotCore_TransitionTimeFinish(&song_play);}
unsigned destination(unsigned scene,unsigned time,unsigned age,unsigned cutscene,unsigned quest,unsigned flag) {
 gSaveContext.save.dayTime=time;gSaveContext.save.linkAge=age;
 gSaveContext.save.cutsceneIndex=cutscene;gSaveContext.gameMode=0;
 stones=quest;event48=flag;gSaveContext.sceneLayer=7;
 unsigned answer=OotCore_DestinationLayer(scene);
 return answer|((unsigned)gSaveContext.sceneLayer<<8);
}
void song_gate(unsigned which) {
 if(which==0)gTimeSpeed=400;
 if(which==1)song_play.msgCtx.disableSunsSong=1;
 if(which==2)rental=1;
 if(which==3){song_play.msgCtx.ocarinaAction=10;song_play.msgCtx.ocarinaMode=8;}
 gSaveContext.sunsSongState=0;OotCore_SunSongStart(&song_play);
}
unsigned song_state(void){return gSaveContext.sunsSongState;}
'''
        (folder/'clock.c').write_text(stub + clock_source(OOT) + room_clock_source(OOT) +
             sun_song_source(OOT) + destination_layer_source(OOT) + transition_clock_source(OOT) +
             clock_events_source(OOT) + wrapper)
        env=dict(os.environ,PATH=str(GCC.parent)+os.pathsep+os.environ.get('PATH',''))
        subprocess.run([str(GCC),'-shared','-O2','-I'+str(OOT/'include'),str(folder/'clock.c'),'-o',str(folder/'clock.dll')],check=True,env=env)
        cls.lib=ctypes.CDLL(str(folder/'clock.dll'))
        cls.lib.tick.argtypes=[ctypes.c_uint]*4
        cls.lib.tick.restype=ctypes.c_uint
        cls.lib.room.argtypes=[ctypes.c_uint]*4
        cls.lib.room.restype=ctypes.c_uint
        for name,count in [('song_setup',4),('song_tick',0),('song_field',1),('song_time',1),
                           ('song_load',0),('destination',6),('song_gate',1),('song_state',0)]:
            function=getattr(cls.lib,name);function.argtypes=[ctypes.c_uint]*count
            function.restype=ctypes.c_uint

    def test_day_night_wrap_and_fast_song(self):
        for time,speed,expected in [(32768,10,32778),(0,10,20),(65530,10,14),
                                    (1000,400,1400),(32768,0,32768),
                                    (17749,10,17759),(49152,10,49162),(49153,10,49173)]:
            self.assertEqual(self.lib.tick(time,time,speed,0)&65535,expected)

    def test_each_source_gate(self):
        for flag in range(7):
            self.assertEqual(self.lib.tick(32768,32768,10,1<<flag)&65535,32768)
        # Credits ignore message and transition gates, but not pause/game over.
        self.assertEqual(self.lib.tick(32768,32768,10,128|4|8|64)&65535,32778)

    def test_sky_holds_ahead_except_midnight(self):
        self.assertEqual(self.lib.tick(20000,22000,0,0)>>16,22000)
        self.assertEqual(self.lib.tick(100,22000,0,0)>>16,100)
        self.assertEqual(self.lib.tick(22000,20000,0,0)>>16,20000)
        self.assertEqual(self.lib.tick(22000,20000,0,256)>>16,22000)

    def test_ntsc_12_frozen_room_and_lake_exception(self):
        # NTSC 1.2 is newer than PAL 1.0; its 05:30 frozen-room rule differs
        # from NTSC 1.0/1.1. Compare the actual source version constants.
        self.assertEqual(self.lib.room(15019,0,0,0)>>16,13654)
        self.assertEqual(self.lib.room(19115,0,0,0)>>16,21846)
        self.assertEqual(self.lib.room(19115,22000,10,0)>>16,22000)
        self.assertEqual(self.lib.room(19115,0,10,0x604)>>16,21846)

    def test_source_room_and_sky_schedule(self):
        self.assertEqual(room_time(OOT/'extracted/ntsc-1.2/assets/scenes/overworld/spot00/spot00_room_0.inc.c'),(0,10,1))
        schedules=sky_schedule(OOT)
        self.assertEqual(len(schedules),4)
        for rows in schedules:
            self.assertEqual(rows[0][0],0)
            self.assertEqual(rows[-1][1],65535)
            for a,b in zip(rows,rows[1:]): self.assertEqual(a[1],b[0])

    def test_sun_song_accelerates_then_restores_source_speed(self):
        self.lib.song_setup(32768,10,0,0)
        self.assertEqual(self.lib.song_tick(),33168|(2<<16))
        self.lib.song_time(49153)
        self.assertEqual(self.lib.song_tick()>>16,2)
        self.assertEqual(self.lib.song_tick()>>16,0)
        self.assertEqual(self.lib.song_field(0),10)
        self.lib.song_setup(65000,10,0,0)
        for _ in range(100):
            if self.lib.song_tick()>>16==0:break
        else:self.fail('night song never finished')
        self.assertGreaterEqual(self.lib.song_field(8),17749)
        self.assertEqual(self.lib.song_field(0),10)

    def test_frozen_song_reload_day_and_delayed_sfx(self):
        self.lib.song_setup(0,0,2,0)
        self.lib.song_tick()
        self.assertEqual(self.lib.song_field(1),32769)
        self.assertEqual(self.lib.song_field(2),0x33)
        self.assertEqual(self.lib.song_field(3),1)
        # Pending day chooses the new entrance before reload changes save time.
        self.assertEqual(self.lib.destination(90,0,1,0,0,0),0|(7<<8))
        self.lib.song_load()
        self.assertEqual(self.lib.song_field(8),32769)
        self.assertEqual(self.lib.song_field(9),32769)
        self.assertEqual(self.lib.song_field(6),1)
        for _ in range(14):self.lib.song_tick()
        self.assertEqual(self.lib.song_field(5),0)
        self.lib.song_tick()
        self.assertEqual(self.lib.song_field(5),1)
        self.assertEqual(self.lib.song_field(1),65535)
        self.lib.song_setup(32768,0,0,0);self.lib.song_tick();self.lib.song_load()
        self.assertEqual(self.lib.song_field(8),0)
        for _ in range(15):self.lib.song_tick()
        self.assertEqual(self.lib.song_field(5),2)

    def test_song_special_rooms_and_start_gates(self):
        for kind,restriction in [(1,0),(0,3)]:
            self.lib.song_setup(32768,0,kind,restriction)
            self.assertEqual(self.lib.song_tick()>>16,3)
            self.assertEqual(self.lib.song_field(3),0)
        for gate in range(4):
            self.lib.song_setup(32768,10,0,0);self.lib.song_gate(gate)
            self.assertEqual(self.lib.song_state(),0)

    def test_destination_layers_keep_loaded_layer(self):
        self.lib.song_setup(32768,10,0,0)
        for scene,time,age,cutscene,quest,event,expected in [
            (90,32768,1,0,0,0,0),(90,0,1,0,0,0,1),
            (90,32768,0,0,0,0,2),(90,0,0,0,0,0,3),
            (81,0,1,0,0,0,0),(81,32768,1,0,7,0,1),
            (85,0,0,0,0,0,2),(85,32768,0,0,0,1,3),
            (81,32768,1,0xfff2,0,0,6)]:
            self.assertEqual(self.lib.destination(scene,time,age,cutscene,quest,event),expected|(7<<8))

    def test_room_behavior_and_generated_math_are_integer(self):
        field=OOT/'extracted/ntsc-1.2/assets/scenes/overworld/spot00/spot00_room_0.inc.c'
        self.assertEqual(room_behavior(field,OOT),(0,1))
        body=sun_song_source(OOT)+transition_clock_source(OOT)
        self.assertNotIn('CLOCK_TIME(',body)
        self.assertNotIn('NEXT_TIME_DAY;',body)

if __name__=='__main__': unittest.main()
