"""Execute the production source-message Ocarina bridge and inventory mapping."""
from pathlib import Path
import re
import unittest

import test_graphics_backend as graphics

ROOT = Path(__file__).resolve().parents[1]
BRIDGE = ROOT / 'oot-core/src/bridge_message.cpp'
SOURCE = Path('D:/Workspace-Claude/game-decomps/n64/oot')


class Ocarina(unittest.TestCase):
    run_c = graphics.GraphicsBackend.run_c

    def test_inventory_mapping_and_old_c_action_ids(self):
        self.run_c('#include <assert.h>\n#include "' +
                   (ROOT / 'src/save_state.c').as_posix() + '"\n' + r'''
int main(void) {
    unsigned i;
    save_new_game();
    for(i=0;i<24;++i) assert(save_inventory_item(i)==255 && !save_c_item_for_slot(i));
    save_state.fairy_ocarina=1;
    assert(save_inventory_item(7)==7 && save_c_item_for_slot(7)==4);
    save_test_max_gear();
    assert(save_inventory_item(7)==8);
    assert(save_c_item_for_slot(0)==1 && save_c_item_for_slot(6)==2 && save_c_item_for_slot(1)==3);
    for(i=0;i<24;++i) {
        assert(save_inventory_item(i)!=255);
        if(save_inventory_slot_usable(i)) assert(save_c_item_inventory_slot(save_c_item_for_slot(i))==i);
        else assert(!save_c_item_for_slot(i));
    }
    save_state.c_items[0]=1;save_state.c_items[1]=4;
    save_set_link_age(0);
    assert(save_state.link_age==0 && save_state.equip_sword==2 && save_state.equip_shield==2);
    assert(save_state.c_items[0]==0 && save_state.c_items[1]==4);
    assert(!save_c_item_for_slot(0) && !save_c_item_for_slot(6));
    assert(save_c_item_for_slot(3)==0x23 && save_c_item_for_slot(9)==0x29);
    assert(save_c_item_inventory_slot(255)==255 && save_c_item_inventory_slot(5)==255);
    assert(save_inventory_item(24)==255 && !save_c_item_for_slot(24));
    return 0;
}
''')

    def test_all_source_song_patterns_match_and_obey_known_song_mask(self):
        text = BRIDGE.read_text()
        code = text[text.index('static OcarinaStaff sOcarinaStaff;'):] if 'static OcarinaStaff sOcarinaStaff;' in text else text[text.index('static OcarinaStaff sOcarinaStaff,'):]
        code = code[:code.index('/* ---- graph.c:')]
        code = code.replace(graphics.function(BRIDGE,'void OotCore_OcarinaScene('),'')
        for marker in ('unsigned int OotCore_NpcText(', 'void OotCore_NpcTextStep('):
            code = code.replace(graphics.function(BRIDGE,marker),'')
        self.run_c(r'''
#include <assert.h>
#include <stddef.h>
#include <stdint.h>
typedef uint8_t u8; typedef uint16_t u16; typedef int8_t s8; typedef int s32;
enum { OCARINA_SONG_MAX=14, OCARINA_BTN_INVALID=255, OCARINA_RECORD_OFF=0,
    OCARINA_RECORD_REJECTED=255, OCARINA_MODE_02=2, OCARINA_MODE_04=4,
    OCARINA_ACTION_FREE_PLAY=1, OCARINA_ACTION_FREE_PLAY_DONE=0x29,
    MSGMODE_NONE=0, TRANS_TRIGGER_START=1, ITEM_OCARINA_FAIRY=7, ITEM_OCARINA_OF_TIME=8,
    SCENE_HYRULE_FIELD=81,SCENE_OUTSIDE_GANONS_CASTLE=100 };
#define PLAYER_STATE2_USING_OCARINA 0x8000000u
#define PLAYER_STATE2_23 0x800000u
#define PLAYER_STATE2_24 0x1000000u
#define PLAYER_STATE2_25 0x2000000u
#define BTN_B 0x4000
#define BTN_A 0x8000
#define BTN_CDOWN 4
#define BTN_CRIGHT 1
#define BTN_CLEFT 2
#define BTN_CUP 8
typedef struct { u8 buttonIndex,state,pos; } OcarinaStaff;
typedef struct { u8 numButtons,buttonsIndex[8]; } OcarinaSongButtons;
typedef int OcarinaNote;
typedef struct { unsigned stateFlags2; } Player;
typedef struct { struct { struct { struct { u16 button; } press; } input[1]; } state;
    struct { unsigned msgMode,ocarinaMode,ocarinaAction,lastPlayedSong,disableSunsSong; } msgCtx;
    struct { struct { unsigned ocarina,warpSongs,sunsSong; } restrictions; } interfaceCtx;
    int nextEntranceIndex,transitionTrigger,sceneId; Player player; } PlayState;
static unsigned inventory=8,opened;
static int gTimeSpeed;
enum { INGO_RACE_STATE_HORSE_RENTAL_PERIOD=1,SUNSSONG_INACTIVE=0 };
#define GET_EVENTINF_INGO_RACE_STATE() 0
static struct { unsigned sunsSongState; } gSaveContext;
static void OotCore_SunSongStart(PlayState *p) { (void)p;gSaveContext.sunsSongState=1; }
static void Message_CloseTextbox(PlayState *p) { p->msgCtx.msgMode=0; }

PlayState* gOotCorePlay;
#define GET_PLAYER(p) (&(p)->player)
#define INV_CONTENT(item) inventory
static void Message_StartOcarina(PlayState *p,unsigned action) {
    ++opened;p->msgCtx.msgMode=1;p->msgCtx.ocarinaAction=action;p->msgCtx.ocarinaMode=1;
}
''' + code + r'''
static void note(PlayState *p,unsigned button) {
    const u16 bits[5]={BTN_A,BTN_CDOWN,BTN_CRIGHT,BTN_CLEFT,BTN_CUP};
    p->state.input[0].press.button=bits[button];OotCore_OcarinaStep(p);
    p->state.input[0].press.button=0;
    assert(OotCore_Ocarina(2)==button+1);assert(!OotCore_Ocarina(2));
}
int main(void) {
    PlayState play={0}; unsigned i,j;
    gOotCorePlay=&play;OotCore_OcarinaReset();inventory=255;
    assert(!OotCore_Ocarina(1));inventory=7;
    play.interfaceCtx.restrictions.ocarina=1;assert(!OotCore_Ocarina(1));
    play.interfaceCtx.restrictions.ocarina=0;
    assert(OotCore_Ocarina(1)&1);assert(opened==1 && !OotCore_Ocarina(1));
    assert(play.player.stateFlags2 & PLAYER_STATE2_USING_OCARINA);
    for(i=0;i<12;++i) {
        AudioOcarina_SetInstrument(1); AudioOcarina_Start(1u<<i);
        assert(OotCore_Ocarina(0)&2);
        for(j=0;j<gOcarinaSongButtons[i].numButtons;++j) note(&play,gOcarinaSongButtons[i].buttonsIndex[j]);
        assert(AudioOcarina_GetPlayingStaff()->state==i);
        assert(!(OotCore_Ocarina(0)&2));
        AudioOcarina_Start(0); /* an unowned song cannot match */
        assert(OotCore_Ocarina(0)&2); /* free play still sounds notes */
        for(j=0;j<gOcarinaSongButtons[i].numButtons;++j) {
            note(&play,gOcarinaSongButtons[i].buttonsIndex[j]);
        }
        assert(AudioOcarina_GetPlayingStaff()->state==0xfe);
    }
    play.state.input[0].press.button=0;
    AudioOcarina_Start(0xfff);
    for(i=0;i<32;++i) note(&play,0); /* bounded trailing note history */
    for(i=0;i<6;++i) note(&play,gOcarinaSongButtons[7].buttonsIndex[i]);
    assert(AudioOcarina_GetPlayingStaff()->state==7);
    for(i=0;i<12;++i) {
        AudioOcarina_SetPlaybackSong(i+1,1);
        for(j=0;j<(gOcarinaSongButtons[i].numButtons+1)*8u;++j) OotCore_OcarinaStep(&play);
        assert(!AudioOcarina_GetPlaybackStaff()->state);
        assert(AudioOcarina_GetPlaybackStaff()->pos==gOcarinaSongButtons[i].numButtons);
    }
    play.msgCtx.msgMode=0;play.msgCtx.ocarinaMode=4;
    OotCore_OcarinaStep(&play);assert(!OotCore_Ocarina(0));
    assert(!(play.player.stateFlags2&PLAYER_STATE2_USING_OCARINA));
    play.msgCtx.msgMode=0;assert(OotCore_Ocarina(1));
    play.msgCtx.ocarinaMode=2;play.msgCtx.lastPlayedSong=5;
    OotCore_OcarinaStep(&play);
    assert(play.transitionTrigger==1 && play.nextEntranceIndex==0x5f4);
    OotCore_OcarinaReset();assert(!OotCore_Ocarina(0));
    play.sceneId=81;assert(OotCore_Ocarina(4));
    play.msgCtx.disableSunsSong=1;assert(!OotCore_Ocarina(4));
    play.msgCtx.disableSunsSong=0;gTimeSpeed=400;assert(!OotCore_Ocarina(4));
    for(i=0;i<3;++i) {
        play.msgCtx.msgMode=0;assert(OotCore_Ocarina(1));
        AudioOcarina_SetInstrument(1);AudioOcarina_Start(1u<<10);
        for(j=0;j<6;++j) note(&play,gOcarinaSongButtons[10].buttonsIndex[j]);
        play.msgCtx.ocarinaAction=OCARINA_ACTION_FREE_PLAY_DONE;
        play.msgCtx.lastPlayedSong=10;play.msgCtx.msgMode=0;
        OotCore_OcarinaStep(&play);
        assert(!OotCore_Ocarina(0));assert(OotCore_Ocarina(3)==11);
        assert(!OotCore_Ocarina(3) && !sListening && !sInstrument);
    }
    assert(OotCore_Ocarina(1));
    play.msgCtx.ocarinaAction=OCARINA_ACTION_FREE_PLAY_DONE;
    AudioOcarina_SetPlaybackSong(11,1);
    play.state.input[0].press.button=BTN_B;OotCore_OcarinaStep(&play);
    assert(!OotCore_Ocarina(0) && !OotCore_Ocarina(3) && !sPlaybackStaff.state);
    assert(!(play.player.stateFlags2&PLAYER_STATE2_USING_OCARINA));

    return 0;
}
''')

    @unittest.skipUnless((SOURCE / 'src/audio/game/general.c').is_file(), 'local decomp needed')
    def test_button_table_and_warp_routes_are_original_source_values(self):
        source = (SOURCE / 'src/audio/game/general.c').read_text(encoding='utf-8')
        block = source.split('OcarinaSongButtons gOcarinaSongButtons[OCARINA_SONG_MAX] = {', 1)[1].split('};', 1)[0]
        mapped = {'A':0,'C_DOWN':1,'C_RIGHT':2,'C_LEFT':3,'C_UP':4}
        rows = re.findall(r'\{\s*(\d+)\s*,\s*\{(.*?)\}', block, re.S)[:12]
        expected = [(int(n), [mapped[x] for x in re.findall(r'OCARINA_BTN_(\w+)', notes)]) for n, notes in rows]
        actual = BRIDGE.read_text().split('gOcarinaSongButtons[OCARINA_SONG_MAX] = {', 1)[1].split('};', 1)[0]
        got = [(int(n),list(map(int,notes.split(',')))) for n,notes in re.findall(r'\{(\d+),\{([^}]+)\}',actual)[:12]]
        self.assertEqual(got, expected)
        self.assertEqual(len(got), 12)
        player = (SOURCE / 'src/overlays/actors/ovl_player_actor/z_player.c').read_text(encoding='utf-8')
        names = re.findall(r'ENTR_\w+',player.split('static s16 sWarpSongEntrances[] = {',1)[1].split('};',1)[0])
        table = (SOURCE / 'include/tables/entrance_table.h').read_text(encoding='utf-8')
        entrances = dict((name,int(value,16)) for value,name in re.findall(r'/\* 0x([0-9A-Fa-f]+) \*/ DEFINE_ENTRANCE\((ENTR_\w+),',table))
        actual = re.search(r'entrance\[6\] = \{([^}]+)\}', BRIDGE.read_text())[1]
        self.assertEqual(list(map(lambda value:int(value,16),actual.split(','))), [entrances[name] for name in names])

    def test_time_song_toggles_repeatedly_and_recovers_both_ages(self):
        self.run_c(r'''
#include <assert.h>
#include <stdbool.h>
static struct { unsigned day_time,entrance,link_age; } save_state;
static unsigned song,allowed=1,reloads,resets,failures,mode;
#define GAME_MODE_LOADING 1
#define GAME_MODE_PLAY 2
static unsigned oot_core_ocarina_song(void) { unsigned s=song;song=0;return s; }
static bool oot_core_ocarina_sun_start(void) { return allowed; }
static unsigned scene_flow_scene(void) { return 4; }
static void game_mode_set(unsigned m) { mode=m; }
static bool scene_flow_load(unsigned scene,unsigned spawn) { ++reloads;assert(scene==4 && spawn==2);if(failures){--failures;return false;}return true; }
static void gameplay_reset(void) { ++resets; }
static void save_set_link_age(unsigned age) { save_state.link_age=age; }
static void place_at_spawn(unsigned scene,unsigned spawn) { assert(scene==4 && spawn==2); }
static bool scene_flow_is_interior(void) { return false; }
static void interior_camera(void) { assert(0); }
static void scene_music(void) {}
static void jo_core_error(const char *message) { assert(!message); }
''' + graphics.function(ROOT/'src/recomp.c','static bool __attribute__((optimize("Os"))) finish_ocarina_song(') + r'''
int main(void) {
    save_state.entrance=2;save_state.link_age=1;
    for(unsigned i=0;i<4;++i) {
        unsigned old=save_state.link_age;song=11;
        assert(finish_ocarina_song() && save_state.link_age!=old);
        assert(reloads==i+1 && resets==i+1 && mode==GAME_MODE_PLAY);
        assert(!finish_ocarina_song());
    }
    for(unsigned age=0;age<2;++age) {
        save_state.link_age=age;song=11;failures=1;
        assert(finish_ocarina_song() && save_state.link_age==age);
    }
    assert(reloads==8 && resets==6);
    song=10;assert(finish_ocarina_song());
    allowed=0;song=10;assert(!finish_ocarina_song());
    return 0;
}
''')

    def test_pause_and_closing_press_never_reach_source_notes_or_song_reload(self):
        self.run_c(r'''
#include <assert.h>
#include <stdbool.h>
typedef struct { unsigned notes,cancel; } gameplay_input_t;
static bool paused;
static unsigned frames,note,sounds,songs;
static bool gameplay_is_paused(void) { return paused; }
static void oot_core_frame(const gameplay_input_t *in) { ++frames;assert(!in->cancel); }
static unsigned oot_core_ocarina_note(void) { unsigned n=note;note=0;return n; }
static void action_audio_ocarina(unsigned n) { ++sounds;assert(n==3); }
static bool finish_ocarina_song(void) { ++songs;return false; }
''' + graphics.function(ROOT/'src/recomp.c','static bool step_core_gameplay(') + r'''
int main(void) {
    gameplay_input_t in={1,1};note=4;
    paused=true;assert(!step_core_gameplay(&in,false)); /* opening press */
    for(unsigned i=0;i<10;++i)assert(!step_core_gameplay(&in,true));
    paused=false;assert(!step_core_gameplay(&in,true)); /* closing B */
    assert(!frames && !sounds && !songs && note==4);
    in.cancel=0;assert(!step_core_gameplay(&in,false));
    assert(frames==1 && sounds==1 && songs==1 && !note);
    return 0;
}
''')

    def test_saria_followup_choices_repeat_and_source_hint_conditions(self):
        player=ROOT/'oot-core/src/bridge_player.cpp'
        self.run_c(r'''
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <stddef.h>
typedef uint16_t u16;typedef uint8_t u8;typedef int32_t s32;typedef uint32_t u32;
typedef struct { s32 v; } f32; /* Fx: one Q16.16 word */
#define OOT_CORE_HWFLOAT 0
#define FX_FRAC 16
#define static_assert _Static_assert
static f32 fixed(int whole,unsigned fraction) {
    return (f32){(s32)(((u32)whole<<16)|fraction)};
}
''' + graphics.function(ROOT/'oot-core/include/bgcheck_bounds.h','static inline s32 OotCore_BgInt(') + r'''
enum {ACTORCAT_NPC=4,ACTOR_EN_SA=0x46,UPG_STRENGTH=0,
    EVENTCHKINF_25=0x25,EVENTCHKINF_37=0x37,EVENTCHKINF_43=0x43,
    QUEST_MEDALLION_FOREST=0,QUEST_MEDALLION_FIRE=1,QUEST_MEDALLION_WATER=2,
    QUEST_MEDALLION_SPIRIT=3,QUEST_MEDALLION_SHADOW=4,QUEST_SONG_STORMS=17,
    TEXT_STATE_CHOICE=1,TEXT_STATE_EVENT=2,TEXT_STATE_CLOSING=3};
typedef struct Actor { unsigned id;struct Actor *next;struct {struct {f32 x,y,z;}pos;}world; } Actor;
typedef struct { Actor actor; } Player;
typedef struct {struct {struct {Actor* head;}actorLists[12];}actorCtx;
    struct {unsigned choiceIndex,unk_E3F2;}msgCtx;Player player;}PlayState;
static unsigned quest,strength,events[14],message_state,advance,text,closed,continues;
static bool adult;
static u8 sSariaSongTalk;
#define LINK_IS_ADULT adult
#define GET_PLAYER(p) (&(p)->player)
#define CUR_UPG_VALUE(n) strength
#define GET_EVENTCHKINF(f) (events[(f)>>4] & (1u<<((f)&15)))
#define CHECK_QUEST_ITEM(n) (quest & (1u<<(n)))
#define Message_GetState(m) message_state
#define Message_ShouldAdvance(p) advance
static void Message_ContinueTextbox(PlayState *p,unsigned id) { ++continues;text=id;message_state=0; }
static void Message_CloseTextbox(PlayState *p) { ++closed;message_state=TEXT_STATE_CLOSING; }
''' + graphics.function(player,'static u16 PlayerProxy_SariaHint(')
            + graphics.function(player,'static void PlayerProxy_SariaSongTalk(') + r'''
int main(void) {
    PlayState p={0};Actor saria={0};
    assert(PlayerProxy_SariaHint(&p)==0x161);
    events[3]=0x80;assert(PlayerProxy_SariaHint(&p)==0x164);
    strength=1;assert(PlayerProxy_SariaHint(&p)==0x162);
    events[2]=0x20;events[3]=0;assert(PlayerProxy_SariaHint(&p)==0x163);
    events[3]=0x80;assert(PlayerProxy_SariaHint(&p)==0x165);
    events[4]=8;assert(PlayerProxy_SariaHint(&p)==0x166);
    quest=7;assert(PlayerProxy_SariaHint(&p)==0x167);
    quest|=1u<<17;assert(PlayerProxy_SariaHint(&p)==0x168);
    quest|=24;assert(PlayerProxy_SariaHint(&p)==0x169);
    saria.id=ACTOR_EN_SA;saria.world.pos.x=fixed(800,0);p.actorCtx.actorLists[4].head=&saria;
    assert(PlayerProxy_SariaHint(&p)==0x160);
    saria.world.pos.x=fixed(801,0);assert(PlayerProxy_SariaHint(&p)==0x169);
    p.player.actor.world.pos.x=fixed(-1001,32768); /* -1000.5, truncates toward zero */
    saria.world.pos.x=fixed(-1800,16384); /* -1799.75, nearby in negative world coordinates */
    assert(OotCore_BgInt(p.player.actor.world.pos.x)==-1000);
    assert(OotCore_BgInt(saria.world.pos.x)==-1799 && PlayerProxy_SariaHint(&p)==0x160);
    saria.world.pos.x=fixed(-1801,0);assert(PlayerProxy_SariaHint(&p)==0x169);
    p.player.actor.world.pos.x=fixed(0,0);saria.world.pos.x=fixed(0,0);
    adult=true;quest=0;assert(PlayerProxy_SariaHint(&p)==0x16a);
    quest=1;assert(PlayerProxy_SariaHint(&p)==0x16b);
    quest=7;assert(PlayerProxy_SariaHint(&p)==0x16c);
    quest=31;assert(PlayerProxy_SariaHint(&p)==0x16d);
    sSariaSongTalk=1;message_state=TEXT_STATE_CHOICE;
    PlayerProxy_SariaSongTalk(&p);assert(!continues); /* no button edge */
    advance=1;PlayerProxy_SariaSongTalk(&p);
    assert(text==0xe2 && sSariaSongTalk==2 && p.msgCtx.unk_E3F2==0xff);
    message_state=TEXT_STATE_EVENT;PlayerProxy_SariaSongTalk(&p);assert(text==0x16d && sSariaSongTalk==3);
    message_state=TEXT_STATE_EVENT;PlayerProxy_SariaSongTalk(&p);assert(text==0xe3 && sSariaSongTalk==4);
    quest=0;message_state=TEXT_STATE_CHOICE;PlayerProxy_SariaSongTalk(&p);
    assert(text==0x16a && sSariaSongTalk==3); /* repeats reevaluate save */
    message_state=TEXT_STATE_EVENT;PlayerProxy_SariaSongTalk(&p);
    p.msgCtx.choiceIndex=1;message_state=TEXT_STATE_CHOICE;PlayerProxy_SariaSongTalk(&p);
    assert(closed==1 && !sSariaSongTalk);
    sSariaSongTalk=1;message_state=TEXT_STATE_CHOICE;PlayerProxy_SariaSongTalk(&p);
    assert(text==0xe1 && sSariaSongTalk==5);
    p.msgCtx.choiceIndex=0;message_state=TEXT_STATE_CHOICE;PlayerProxy_SariaSongTalk(&p);
    assert(text==0x15f && !sSariaSongTalk); /* unavailable Navi scene script */
    sSariaSongTalk=5;p.msgCtx.choiceIndex=1;message_state=TEXT_STATE_CHOICE;PlayerProxy_SariaSongTalk(&p);
    assert(closed==2 && !sSariaSongTalk);
    return 0;
}
''')


if __name__ == '__main__':
    unittest.main()
