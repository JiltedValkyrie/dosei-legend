"""Execute core NPC page ownership and guarded double-speed reveal."""
from pathlib import Path
import os
import sys
import unittest
import test_graphics_backend as graphics

ROOT = Path(__file__).resolve().parents[1]


class DialogueCoreHandoff(unittest.TestCase):
    run_c = graphics.GraphicsBackend.run_c

    def test_native_npc_host_waits_for_core_choice_and_close(self):
        source = (ROOT / 'src/gameplay.c').read_text()
        start = source.index('    if (gameplay.talking && core_npc_talking) {')
        end = source.index('    if (gameplay.talking) {', start)
        self.run_c(r'''
#include <assert.h>
#include <stdbool.h>
typedef struct { unsigned next[3]; } dialogue_branch_t;
static struct { bool talking;int prompt;unsigned choice; } gameplay;
static bool core_npc_talking=true;
static unsigned state,closed,continued,text;
static dialogue_branch_t branch={{0x1039,0x103a,0}};
static unsigned oot_core_npc_text(unsigned c) { (void)c;return state; }
static const dialogue_branch_t *choice_branch(void) { return &branch; }
static bool continue_text(unsigned id) { ++continued;text=id;state=1;return true; }
static void close_talk(void) { ++closed;gameplay.talking=false;core_npc_talking=false; }
static void tick(void) {
''' + source[start:end] + r'''
}
int main(void) {
    gameplay.talking=true;state=1;tick();assert(!closed && !continued);
    state=0x104;tick();assert(continued==1 && text==0x103a && !closed);
    tick();assert(continued==1);
    state=2;tick();assert(closed==1 && !gameplay.talking);
    tick();assert(closed==1); /* quest/gate close callback runs once */
    gameplay.talking=core_npc_talking=true;state=0;tick();assert(closed==2);
    return 0;
}
''')

    def test_press_fills_source_page_without_advancing_it(self):
        sys.path.insert(0, str(ROOT / 'tools'))
        import oot_core_import as importer
        source = Path(os.environ.get('DOSEI_OOT',
            '/mnt/d/Workspace-Claude/game-decomps/n64/oot')) / 'src/code/z_message.c'
        if not source.exists():
            self.skipTest('local OoT source required')
        stats = {'problems': [], 'macros': 0}
        text = importer.fix_macros('src/code/z_message.c', source.read_text(), stats)
        self.assertFalse(stats['problems'])
        start = text.index('            case MSGMODE_TEXT_DISPLAYING:', text.index('void Message_Update('))
        end = text.index('            case MSGMODE_TEXT_AWAIT_INPUT:', start)
        self.run_c(r'''
#include <assert.h>
#include <stdbool.h>
enum { MSGMODE_TEXT_DISPLAYING=1, TEXTBOX_TYPE_NONE_BOTTOM=9, BTN_A=1, BTN_B=2 };
#define YREG(n) 0
#define CHECK_BTN_ANY(button,mask) ((button)&(mask))
static bool sTextboxSkipped;
typedef struct { int textBoxType,textUnskippable,textDrawPos,decodedTextLen; } Message;
typedef struct { struct { unsigned button; } press; } Input;
static void tick(Message *msgCtx,Input *input) {
    switch (MSGMODE_TEXT_DISPLAYING) {
''' + text[start:end] + r'''
    }
}
int main(void) {
    Message m={0,0,2,40};Input i={{0}};
    tick(&m,&i);assert(m.textDrawPos==2);
    i.press.button=BTN_A;tick(&m,&i);assert(m.textDrawPos==40 && !sTextboxSkipped);
    m.textDrawPos=3;sTextboxSkipped=false;i.press.button=BTN_B;tick(&m,&i);
    assert(m.textDrawPos==40 && sTextboxSkipped);
    m.textUnskippable=1;m.textDrawPos=3;sTextboxSkipped=false;i.press.button=BTN_A;
    tick(&m,&i);assert(m.textDrawPos==3 && !sTextboxSkipped);
    m.textBoxType=TEXTBOX_TYPE_NONE_BOTTOM;m.textDrawPos=3;
    tick(&m,&i);assert(m.textDrawPos==3); /* preserve automatic cinematic text */
    return 0;
}
''')

    def test_only_emphasis_uses_bold_glyph_copies(self):
        # Human rule 2026-10-08: regular text keeps SGL's glyphs; coloured
        # emphasis swaps to widened copies stored after the font.
        main = ROOT / 'src/main.c'
        code = graphics.function(main, 'static void __attribute__((optimize("Os"))) dialogue_font_init(')
        code += graphics.function(main, 'void __attribute__((optimize("Os"))) recomp_text_embolden(')
        code = code.replace('(volatile uint8_t *)0x25E60000u', 'font')
        self.run_c(r'''
#include <assert.h>
#include <stdint.h>
static uint8_t font[1024*32];
static uint16_t map, row[8];
static int locate_row;
static void jo_printf(int x,int y,const char *fmt,...) {
    static unsigned ch=33;(void)x;(void)y;(void)fmt;map=ch++*2;
}
static void *slLocate(int x,int y) { (void)x; return y==31 ? (void *)&map : (void *)row; }
static uint16_t bold_base;
#define BOLD(ch) (bold_base + 2u*((ch)-33u))
''' + code + r'''
int main(void) {
    for(unsigned ch=33;ch<127;++ch) {
        font[ch*64+1]=7;font[ch*64+7]=7;
    }
    dialogue_font_init();
    for(unsigned ch=33;ch<127;++ch) {
        assert(font[ch*64+1]==7 && !font[ch*64+2]);          /* regular untouched */
        assert(bold_base >= 254 && bold_base % 2 == 0);
        uint8_t *b=font+BOLD(ch)*32;
        assert(b[1]==7 && b[2]==7 && !b[3] && !b[8]);        /* widened, rows kept */
    }
    for(unsigned i=0;i<4;++i) row[i]=0x3000|(('A'+i)*2);
    recomp_text_embolden(0,5,"AB C",4);
    assert(row[0]==(0x3000|BOLD('A')) && row[1]==(0x3000|BOLD('B')));
    assert(row[2]==(0x3000|(('C')*2)) && row[3]==(0x3000|BOLD('C')));
    return 0;
}
''')

    def test_core_pages_choices_events_and_close(self):
        bridge = ROOT / 'oot-core/src/bridge_message.cpp'
        code = '\n'.join(graphics.function(bridge, marker) for marker in (
            'unsigned int OotCore_NpcText(', 'void OotCore_NpcTextStep('))
        self.run_c(r'''
#include <assert.h>
#include <stddef.h>
enum { MSGMODE_NONE, TEXT_STATE_DISPLAYING, TEXT_STATE_CHOICE,
       TEXT_STATE_EVENT, TEXT_STATE_CLOSING };
typedef struct { struct { unsigned msgMode,choiceIndex; } msgCtx; } PlayState;
static PlayState play, *gOotCorePlay=&play;
static unsigned sNpcText, press, opened, continued, closed, text;
static unsigned Message_GetState(void *p) { (void)p;return play.msgCtx.msgMode; }
static int Message_ShouldAdvance(PlayState *p) { (void)p;return press; }
static void Message_StartTextbox(PlayState *p,unsigned id,void *a) {
    (void)a;++opened;text=id;p->msgCtx.msgMode=TEXT_STATE_DISPLAYING;
}
static void Message_ContinueTextbox(PlayState *p,unsigned id) {
    ++continued;text=id;p->msgCtx.msgMode=TEXT_STATE_DISPLAYING;
}
static void Message_CloseTextbox(PlayState *p) { ++closed;p->msgCtx.msgMode=TEXT_STATE_CLOSING; }
''' + code + r'''
int main(void) {
    assert(OotCore_NpcText(0x11038)==1 && opened==1 && text==0x1038);
    press=1;OotCore_NpcTextStep(&play);assert(OotCore_NpcText(0)==1);
    play.msgCtx.msgMode=TEXT_STATE_CHOICE;play.msgCtx.choiceIndex=1;press=0;
    OotCore_NpcTextStep(&play);assert(OotCore_NpcText(0)==1);
    press=1;OotCore_NpcTextStep(&play);assert(OotCore_NpcText(0)==0x104);
    play.msgCtx.choiceIndex=0;OotCore_NpcTextStep(&play);
    assert(OotCore_NpcText(0)==0x104); /* result stays until host takes branch */
    assert(OotCore_NpcText(0x11039)==1 && continued==1 && text==0x1039);
    play.msgCtx.msgMode=TEXT_STATE_EVENT;press=0;
    OotCore_NpcTextStep(&play);assert(!closed);
    press=1;OotCore_NpcTextStep(&play);assert(closed==1);
    OotCore_NpcTextStep(&play);assert(OotCore_NpcText(0)==2);
    assert(!OotCore_NpcText(0x20000));
    play.msgCtx.msgMode=MSGMODE_NONE;
    assert(OotCore_NpcText(0x11002)==1 && opened==2);
    play.msgCtx.msgMode=MSGMODE_NONE;OotCore_NpcTextStep(&play);
    assert(OotCore_NpcText(0)==2); /* normal page completion releases C owner */
    OotCore_NpcText(0x20000);play.msgCtx.msgMode=TEXT_STATE_DISPLAYING;
    assert(!OotCore_NpcText(0x11002)); /* unrelated conversation owns box */
    return 0;
}
''')

    def test_double_reveal_never_advances_waits_or_song_timers(self):
        text = (ROOT / 'oot-core/src/oot_core_api.cpp').read_text()
        start = text.index('    {\n        bool revealing =')
        end = text.index('    gOotCorePhaseUs[3]', start)
        block = text[start:end]
        self.run_c(r'''
#include <assert.h>
#include <stdbool.h>
enum { MSGMODE_TEXT_DISPLAYING=1, WAIT=2, SONG=3 };
typedef struct { struct { int msgMode; } msgCtx; } PlayState;
static int draws,resets,finish;
static void Message_Draw(PlayState *p) { ++draws;if(finish)p->msgCtx.msgMode=WAIT; }
static void OotCore_GfxReset(void) { ++resets; }
static void tick(PlayState *play) {
''' + block + r'''
}
int main(void) {
    PlayState p={{MSGMODE_TEXT_DISPLAYING}};tick(&p);assert(draws==2 && resets==1);
    draws=resets=0;finish=1;tick(&p);assert(draws==1 && !resets);
    draws=0;finish=0;tick(&p);assert(draws==1 && p.msgCtx.msgMode==WAIT);
    draws=0;p.msgCtx.msgMode=SONG;tick(&p);assert(draws==1);
    return 0;
}
''')


if __name__ == '__main__':
    unittest.main()

