"""Execute the actual z_message / EnSkj memory-round choreography in C tests."""
import re
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'tools'))
from owl_sources import function


def source_fixture(oot):
    message = oot/'src/code/z_message.c'
    text = message.read_text(encoding='utf-8')
    cases = text[text.index('            case MSGMODE_MEMORY_GAME_START:'):
                 text.index('            case MSGMODE_FROGS_START:')]
    modes = re.findall(r'/\* 0x([0-9A-F]+) \*/ (MSGMODE_MEMORY_GAME_\w+)',
                      (oot/'include/message.h').read_text())
    declarations = 'enum {' + ','.join(name+'=0x'+value for value,name in modes) + '};\n'
    declarations += r'''
enum { OCARINA_INSTRUMENT_OFF=0,OCARINA_INSTRUMENT_DEFAULT=1,OCARINA_INSTRUMENT_FLUTE=6,
    OCARINA_MODE_03=3,OCARINA_MODE_0F=15,NA_SE_SY_METRONOME_LV=0x4838,SFX_FLAG=0x800,
    NA_SE_SY_OCARINA_ERROR=0x4809,NA_SE_SY_GET_ITEM=0x4824,NA_SE_SY_CORRECT_CHIME=0x4802,
    SKULL_KID_LEFT=0,SKULL_KID_RIGHT=1,SKULL_KID_OCARINA_WAIT=0,SKULL_KID_OCARINA_PLAY_NOTES=1 };
#define PRINTF(...) ((void)0)
#define DRAW_TEXT(...) ((void)0)
#define SFX_PLAY_CENTERED(id) OotCore_OcarinaSfxStarted(id)
static u8 sOcarinaButtonIndexBuf[10],sOcarinaButtonIndexBufPos;
static void Message_ResetOcarinaNoteState(void) { }
typedef struct { int unused; } Actor;
typedef struct EnSkj EnSkj;
struct EnSkj { Actor actor;int minigameState,songFailTimer,textId;void (*actionFunc)(EnSkj*,PlayState*); };
static struct { EnSkj* skullkid; } sOcarinaMinigameSkullKids[2];
static void EnSkj_TurnPlayer(EnSkj* self,Player* player) { }
static void Actor_OfferTalk(Actor* self,PlayState* play,int range) { }
static void Sfx_PlaySfxCentered(unsigned id) { OotCore_OcarinaSfxStarted(id); }
static void EnSkj_FailedMiniGame(EnSkj* self,PlayState* play) { }
static void EnSkj_WonOcarinaMiniGame(EnSkj* self,PlayState* play) { }
'''
    declarations += function(text, 'Message_UpdateOcarinaMemoryGame')
    declarations += '\nstatic void SourceMemoryDraw(PlayState* play) {\nMessageContext* msgCtx=&play->msgCtx;\nswitch(msgCtx->msgMode) {\n'+cases+'}\n}\n'
    declarations += function((oot/'src/overlays/actors/ovl_En_Skj/z_en_skj.c').read_text(encoding='utf-8'),
                             'EnSkj_WaitForPlayback')
    return declarations + r'''
static void memoryFrame(PlayState* play,EnSkj* controller) {
    OotCore_OcarinaStep(play);
    EnSkj_WaitForPlayback(controller,play);
    if(controller->actionFunc!=EnSkj_FailedMiniGame && controller->actionFunc!=EnSkj_WonOcarinaMiniGame)
        SourceMemoryDraw(play);
    play->state.input[0].press.button=0;
}
static void test_source_memory_choreography(void) {
    const u16 bits[5]={BTN_A,BTN_CDOWN,BTN_CRIGHT,BTN_CLEFT,BTN_CUP};
    unsigned round,frame,i,waitFrames;
    for(round=0;round<3;++round) {
        PlayState play={0};EnSkj controller={0},left={0},right={0};
        gOotCorePlay=&play;OotCore_OcarinaReset();
        sOcarinaMinigameSkullKids[0].skullkid=&left;sOcarinaMinigameSkullKids[1].skullkid=&right;
        gSaveContext.save.info.playerData.ocarinaGameRoundNum=round;
        play.msgCtx.msgMode=MSGMODE_MEMORY_GAME_START;play.msgCtx.ocarinaMode=1;
        controller.songFailTimer=160;waitFrames=0;
        for(frame=0;frame<6000 && controller.actionFunc!=EnSkj_WonOcarinaMiniGame;++frame) {
            unsigned oldMode=play.msgCtx.msgMode;
            if(oldMode==MSGMODE_MEMORY_GAME_PLAYER_PLAYING && sListening)
                play.state.input[0].press.button=bits[gOcarinaSongButtons[13].buttonsIndex[sNoteCount]];
            if(oldMode==MSGMODE_MEMORY_GAME_LEFT_SKULLKID_WAIT && Audio_IsSfxPlaying(NA_SE_SY_METRONOME))
                ++waitFrames;
            memoryFrame(&play,&controller);
            assert(controller.actionFunc!=EnSkj_FailedMiniGame);
        }
        assert(frame<6000 && controller.textId==0x10bf);
        assert(gOcarinaSongButtons[13].numButtons==(round==0?5:round==1?6:8));
        assert(waitFrames>=OOT_SFX_METRONOME_TICKS-1);
        /* Repeat a real round and enter the wrong first note: source failure
         * dialogue/action must own the result, not a host reward shortcut. */
        OotCore_OcarinaReset();controller.actionFunc=0;
        play.msgCtx.msgMode=MSGMODE_MEMORY_GAME_START;play.msgCtx.ocarinaMode=1;
        for(i=0;i<500 && play.msgCtx.msgMode!=MSGMODE_MEMORY_GAME_PLAYER_PLAYING;++i)
            memoryFrame(&play,&controller);
        assert(i<500 && sListening);
        play.state.input[0].press.button=bits[(gOcarinaSongButtons[13].buttonsIndex[0]+1)%5];
        memoryFrame(&play,&controller);memoryFrame(&play,&controller);
        assert(controller.actionFunc==EnSkj_FailedMiniGame && controller.textId==0x102d);
    }
    gOotCorePlay=0;
}
'''
