"""Execute imported scene/day-sequence logic with bounded host state."""
import ctypes
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from environment_sequence_source import (_remove_calls, _sound_constants,
                                         sequence_source, sound_settings)
from environment_selection_source import _enum

OOT = Path('D:/Workspace-Claude/game-decomps/n64/oot')
GCC = Path('C:/msys64/mingw64/bin/gcc.exe')


def clock(hour, minute=0):
    return ((hour * 60 + minute) * 65536 + 720) // 1440


class StatementRemoval(unittest.TestCase):
    def test_multiline_nested_debug_statement_and_literals(self):
        source = 'if (x) { PRINTF(T("a ) ;", "b"), call(1, 2)); keep++; }'
        output = _remove_calls(source, {'PRINTF': 1}, 'debug omitted')
        self.assertIn('keep++;', output)
        self.assertNotIn('call(1', output)
        self.assertEqual(output.count('{'), output.count('}'))
        with self.assertRaises(ValueError):
            _remove_calls(source, {'PRINTF': 2}, 'debug omitted')


@unittest.skipUnless(OOT.exists() and GCC.exists(), 'source and host GCC required')
class EnvironmentSequence(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        folder = Path(cls.temp.name)
        constants = _sound_constants(str(OOT)) | _enum(OOT/'include/environment.h', 'TimeBasedSeqState')
        defines = '\n'.join(f'#define {name} {value}' for name, value in constants.items())
        stub = r'''
#include <stdint.h>
#include <stddef.h>
#include <stdbool.h>
#include <string.h>
typedef int32_t s32;
typedef struct {
 struct {unsigned char timeSeqState; unsigned precipitation[2];} envCtx;
 struct {unsigned char seqId,natureAmbienceId;} sceneSequences;
 struct {int state;} csCtx;
} PlayState;
struct {
 struct {uint16_t dayTime; int entranceIndex,totalDays,bgsDayCount;} save;
 uint16_t forcedSeqId;
 unsigned char seqId,natureAmbienceId;
 int dogIsLost;
} gSaveContext;
static PlayState play;
static int eggs,replacements,texts,in_cs,last_sfx;
#define ENTR_LOST_WOODS_8 0x4de
#define ENTR_LOST_WOODS_9 0x5e0
#define PRECIP_RAIN_MAX 0
#define PRECIP_SOS_MAX 1
#define ITEM_WEIRD_EGG 1
#define ITEM_CHICKEN 2
#define ITEM_POCKET_EGG 3
#define ITEM_POCKET_CUCCO 4
#define NA_SE_EV_CHICKEN_CRY_M 1
#define NA_SE_EV_DOG_CRY_EVENING 2
static int OotCore_ReplaceDayItem(PlayState* p, int old, int next) {
 int bit=old==ITEM_WEIRD_EGG?1:2;
 ++replacements;
 if (!(eggs&bit))return false;
 eggs&=~bit;return true;
}
static int OotCore_DayPlayerInCsMode(PlayState* p){return in_cs;}
static void Message_StartTextbox(PlayState* p,int id,void* actor){if(id==0x3066)++texts;}
static void Sfx_PlaySfxCentered(int id){last_sfx=id;}
static void Sfx_PlaySfxCentered2(int id){last_sfx=id;}
'''
        wrapper = r'''
void setup(unsigned time,unsigned seq,unsigned nature,unsigned forced,unsigned entrance) {
 memset(&play,0,sizeof play);memset(&gSaveContext,0,sizeof gSaveContext);
 eggs=replacements=texts=in_cs=last_sfx=0;
 gSaveContext.save.dayTime=time;gSaveContext.forcedSeqId=forced;
 gSaveContext.seqId=0xff;gSaveContext.natureAmbienceId=0xff;
 gSaveContext.save.entranceIndex=entrance;
 play.sceneSequences.seqId=seq;play.sceneSequences.natureAmbienceId=nature;
 OotCore_DaySequenceInit(&play);
}
void set_state(unsigned state){play.envCtx.timeSeqState=state;}
void gates(unsigned egg_bits,unsigned cutscene,unsigned player_cs,unsigned rain) {
 eggs=egg_bits;play.csCtx.state=cutscene;in_cs=player_cs;
 play.envCtx.precipitation[0]=rain&1;play.envCtx.precipitation[1]=(rain>>1)&1;
}
unsigned step(unsigned time){gSaveContext.save.dayTime=time;OotCore_DaySequenceUpdate(&play);return play.envCtx.timeSeqState;}
unsigned field(unsigned which) {
 switch(which){case 0:return play.envCtx.timeSeqState;case 1:return gSaveContext.forcedSeqId;
 case 2:return gSaveContext.save.totalDays;case 3:return gSaveContext.save.bgsDayCount;
 case 4:return gSaveContext.dogIsLost;case 5:return eggs;case 6:return replacements;
 case 7:return texts;case 8:return last_sfx;default:return 0;}
}
'''
        (folder/'sequence.c').write_text(defines+'\n'+stub+sequence_source(OOT)+wrapper, encoding='utf-8')
        env = dict(os.environ, PATH=str(GCC.parent)+os.pathsep+os.environ.get('PATH',''))
        subprocess.run([str(GCC), '-shared', '-O2', str(folder/'sequence.c'), '-o', str(folder/'sequence.dll')],
                       check=True, env=env)
        cls.lib = ctypes.CDLL(str(folder/'sequence.dll'))
        cls.lib.setup.argtypes = [ctypes.c_uint]*5
        cls.lib.gates.argtypes = [ctypes.c_uint]*4
        cls.lib.step.argtypes = cls.lib.field.argtypes = cls.lib.set_state.argtypes = [ctypes.c_uint]
        cls.lib.step.restype = cls.lib.field.restype = ctypes.c_uint

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def setup(self, time, seq=2, nature=0, forced=0, entrance=0):
        self.lib.setup(time, seq, nature, forced, entrance)

    def test_sound_metadata_is_header_specific(self):
        header = OOT/'extracted/ntsc-1.2/assets/scenes/overworld/spot00/spot00_scene.inc.c'
        self.assertEqual(sound_settings(header, OOT), (2, 0, 1))
        self.assertEqual(sound_settings(None, OOT), (0, 0, 0))
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp)/'header.c'
            path.write_text('/* SCENE_CMD_SOUND_SETTINGS(1,2,3) */\nSCENE_CMD_END()')
            self.assertEqual(sound_settings(path, OOT), (0, 0, 0))
            path.write_text('SCENE_CMD_SOUND_SETTINGS(2, NATURE_ID_NONE, NA_BGM_NO_MUSIC)')
            self.assertEqual(sound_settings(path, OOT), (127, 19, 1))
            path.write_text('SCENE_CMD_SOUND_SETTINGS(2, 0, 2)\n'*2)
            with self.assertRaises(ValueError):
                sound_settings(path, OOT)

    def test_initial_state_boundaries(self):
        for time, state in [(0,5), (clock(6,30)-1,5), (clock(6,30),7),
                            (clock(7),1), (clock(17,10),1), (clock(17,10)+1,3),
                            (clock(19),3), (clock(19)+1,7), (clock(19)+2,5)]:
            with self.subTest(time=time):
                self.setup(time)
                self.assertEqual(self.lib.field(0), state)
        self.assertNotIn('CLOCK_TIME(', sequence_source(OOT))

    def test_disabled_and_forced_init_paths(self):
        for seq, nature in [(127,19), (127,0), (2,19)]:
            self.setup(clock(12), seq=seq, nature=nature)
            self.assertEqual(self.lib.field(0), 255)
        for entrance in [0x4de,0x5e0]:
            self.setup(clock(12), forced=7, entrance=entrance)
            self.assertEqual((self.lib.field(0),self.lib.field(1)), (255,7))
        for forced in [7,65535]:
            self.setup(clock(12), forced=forced)
            self.assertEqual((self.lib.field(0),self.lib.field(1)), (255,0))

    def test_nine_state_cycle_and_exact_dawn(self):
        self.setup(clock(7))
        for time, state in [(clock(17,10),1), (clock(17,10)+1,2),
                            (clock(18),2), (clock(18)+1,3), (clock(18)+1,4),
                            (clock(19),4), (clock(19)+1,5), (clock(19)+2,6),
                            (0,6), (clock(6,30),6), (clock(6,30)+1,7),
                            (clock(6,30)+1,8), (clock(7),8), (clock(7)+1,0),
                            (clock(7)+1,1)]:
            with self.subTest(time=time, state=state):
                self.assertEqual(self.lib.step(time), state)
        self.assertEqual([self.lib.field(i) for i in [2,3,4,8]], [1,1,1,1])
        for _ in range(10):
            self.lib.step(clock(12))
        self.assertEqual(self.lib.field(2), 1)

    def test_hatch_happens_before_text_gates_and_short_circuits(self):
        for cutscene, player_cs in [(0,0),(1,0),(0,1)]:
            self.setup(clock(1))
            self.lib.set_state(6)
            self.lib.gates(3,cutscene,player_cs,0)
            self.assertEqual(self.lib.step(clock(6,30)+1),7)
            self.assertEqual([self.lib.field(i) for i in [2,3,4,5,6]], [1,1,1,2,1])
            self.assertEqual(self.lib.field(7), int(not (cutscene or player_cs)))
        self.setup(clock(1))
        self.lib.set_state(6)
        self.lib.gates(2,0,0,0)
        self.lib.step(clock(6,30)+1)
        self.assertEqual([self.lib.field(i) for i in [5,6,7]], [0,2,1])

    def test_rain_does_not_disable_dawn_progress(self):
        self.setup(clock(1))
        self.lib.gates(0,0,0,3)
        self.assertEqual(self.lib.step(clock(1)),6)
        self.assertEqual(self.lib.step(clock(6,30)+1),7)
        self.assertEqual(self.lib.field(2),1)


if __name__ == '__main__':
    unittest.main()
