"""Execute the production player talk/reward bridge, without a renderer."""
from pathlib import Path
import unittest

import test_graphics_backend as graphics

function = graphics.function

ROOT = Path(__file__).resolve().parents[1]
PLAYER = ROOT / 'oot-core/src/bridge_player.cpp'
HOST = ROOT / 'src/oot_core_host.c'


class CoreDialogue(unittest.TestCase):
    run_c = graphics.GraphicsBackend.run_c

    def test_host_mirror_uses_source_scene_time_inventory_and_rewards(self):
        host = HOST.read_text()
        clock = host[host.index('static unsigned short core_skybox_time;'):
                     host.index('static void mirror_save(')]
        self.run_c(r'''
#include <assert.h>
#include <string.h>
''' + '#include "' + (ROOT / 'oot-core/include/oot_core_api.h').as_posix() + '"\n'
            + '#include "' + (ROOT / 'src/game_mode.h').as_posix() + '"\n'
            + '#include "' + (ROOT / 'src/save_state.c').as_posix() + '"\n' + r'''
static game_mode_t current_mode=GAME_MODE_PLAY;
game_mode_t game_mode(void) { return current_mode; }
static struct { unsigned save_scene,oot_scene; } scene;
static struct { unsigned rupees,dead,paused; } gameplay;
static unsigned world_blocked;
static int gameplay_blocks_world(void) { return world_blocked; }
#define scene_flow_entry() (&scene)
static OotCoreSave captured;
static void set_save(const OotCoreSave *s) { captured=*s; }
static OotCoreEntry entry={.set_save=set_save};
#define ENTRY (&entry)
static int loaded; /* oot_core_session_reset: no blob in this harness */
void oot_core_scene_unload(void) {}
''' + clock
            + function(HOST, 'static void mirror_save(')
            + function(ROOT / 'src/oot_core_host.c', 'static unsigned char host_give_item(')
            + function(ROOT / 'src/oot_core_host.c', 'static void host_rupees_change(') + r'''
int main(void) {
    save_new_game();
    scene.save_scene=255; scene.oot_scene=99;
    save_state.link_age=0; save_state.day_time=0xC001;
    save_state.owned_sword=save_state.equip_sword=1;
    save_state.owned_shield=save_state.equip_shield=1;
    save_state.fairy_ocarina=1; save_state.cutscene_index=0xfff1;
    save_state.source_entrance=0x604;
    save_state.total_days=11;save_state.bgs_day_count=3;
    mirror_save();
    assert(captured.entrance_index==0x604);
    assert(captured.day_time_out==&save_state.day_time);
    assert(captured.skybox_time_out==&core_skybox_time);
    assert(captured.total_days==&save_state.total_days && *captured.total_days==11);
    assert(captured.bgs_day_count==&save_state.bgs_day_count && *captured.bgs_day_count==3);
    assert(captured.reset_skybox_time && captured.skybox_time==0);
    assert(!core_skybox_reset && !captured.time_blocked);
    assert(captured.link_age==0 && captured.night && captured.cutscene_index==0xfff1);
    assert(captured.scene_flags==(unsigned long*)&save_state.generic_scene[99]);
    assert(captured.generic_scene && captured.fairy_ocarina && captured.equip_sword==1);
    assert(captured.quest_items==(unsigned int*)&save_state.quest_items);
    assert(captured.dungeon_keys==save_state.dungeon_keys);
    save_state.day_time=0xC000; mirror_save(); assert(!captured.night);
    save_state.day_time=0x4555; mirror_save(); assert(!captured.night);
    save_state.day_time=0x4554; mirror_save(); assert(captured.night);
    assert(!captured.reset_skybox_time);
    /* Source frozen-room sky may remain ahead of dayTime. Ordinary host
     * mirroring and scene changes must not turn that into another reset. */
    *captured.skybox_time_out=0x5556;
    *captured.day_time_out=0x4aaa;
    scene.oot_scene=81;
    mirror_save();
    assert(captured.skybox_time==0x5556 && captured.day_time==0x4aaa);
    assert(!captured.reset_skybox_time && oot_core_skybox_time()==0x5556);
    /* Explicit source/probe sky assignments preserve the song lifecycle.
     * Frontend reset separately clears pending time/song state (flag 2). */
    oot_core_clock_reset(0); mirror_save();
    assert(captured.reset_skybox_time==1 && !captured.skybox_time);
    assert(captured.day_time==0x4aaa);
    mirror_save(); assert(!captured.reset_skybox_time);
    oot_core_session_reset(save_state.day_time); mirror_save();
    assert(captured.reset_skybox_time==2 && captured.skybox_time==captured.day_time);
    mirror_save(); assert(!captured.reset_skybox_time);
    world_blocked=1; mirror_save(); assert(captured.time_blocked);
    assert(captured.player_cutscene);
    gameplay.paused=1;mirror_save();assert(!captured.player_cutscene);
    gameplay.paused=0;
    world_blocked=0; gameplay.dead=1; mirror_save(); assert(captured.time_blocked);
    assert(captured.player_cutscene);
    gameplay.dead=0; mirror_save(); assert(!captured.time_blocked);
    assert(!captured.player_cutscene);
    current_mode=GAME_MODE_CUTSCENE;mirror_save();assert(captured.player_cutscene);
    current_mode=GAME_MODE_PLAY;
    save_state.source_entrance=0xffff; mirror_save();
    assert(captured.entrance_index==0xffff);
    scene.save_scene=SAVE_SCENE_KOKIRI_FOREST; mirror_save();
    assert(!captured.generic_scene && captured.scene_flags==(unsigned long*)&save_state.scene[0]);
    assert(host_give_item(0x1a)==0xff && save_state.bottle_items[0]==0x1a);
    assert(host_give_item(0x82)==0x82); /* no empty bottle: no false success */
    save_state.bottle_items[0]=0x14;
    assert(host_give_item(0x82)==0xff && save_state.bottle_items[0]==0x1a);
    /* Child route grants (z_parameter.c Item_Give branches). */
    assert(host_give_item(0x21)==0xff && save_state.source_items[23]==0x21);
    assert(host_give_item(0x23)==0xff && save_state.source_items[23]==0x23);
    save_state.source_upgrades=0; save_state.source_ammo[2]=0;
    assert(host_give_item(0x8E)==0xff && save_state.source_ammo[2]==0); /* no bag: cap 0 */
    assert(host_give_item(0x4D)==0xff && ((save_state.source_upgrades>>3)&7)==1);
    assert(save_state.source_items[2]==0x02 && save_state.source_ammo[2]==20);
    save_state.source_ammo[2]=12;
    assert(host_give_item(0x8F)==0xff && save_state.source_ammo[2]==20); /* clamps */
    assert(host_give_item(0x50)==0xff && ((save_state.source_upgrades>>6)&7)==1);
    assert(((save_state.source_upgrades>>3)&7)==1);
    save_state.rupees=0;
    assert(host_give_item(0x87)==0xff && save_state.rupees==50 && gameplay.rupees==50);
    save_test_max_gear(); mirror_save();
    assert(*captured.quest_items==0x00ffffff); /* includes ALL three stones */
    assert(captured.inventory_items[7]==8 && captured.inventory_items[9]==11);
    assert(captured.inventory_equipment==0x7777 && captured.magic==0x60);
    assert(captured.skull_tokens==100 && captured.health_capacity==0x140);
    host_rupees_change(50); assert(save_state.rupees==500 && gameplay.rupees==500);
    host_rupees_change(-30); assert(save_state.rupees==470 && gameplay.rupees==470);
    save_damage(5); assert(save_state.health==317); /* source double defense rounds damage up */
    return 0;
}
''')

    def test_source_offers_auto_talk_rewards_and_close(self):
        self.run_c(r'''
#include <assert.h>
#include <stdint.h>
#include <string.h>
typedef uint8_t u8;
typedef uint16_t u16;
#define GI_NONE 0
#define GI_DEKU_NUTS_5 1
#define GI_DEKU_STICKS_1 2
#define GI_DEKU_SEEDS_5 3
#define GI_BOTTLE_MILK_FULL 4
#define GI_MILK 5
#define ITEM_NONE 255
#define ITEM_DEKU_NUTS_5 1
#define ITEM_DEKU_STICK 2
#define ITEM_DEKU_SEEDS 3
#define ITEM_BOTTLE_MILK_FULL 0x1a
#define ITEM_MILK 0x82
#define ACTOR_FLAG_TALK 1
#define ACTOR_FLAG_TALK_OFFER_AUTO_ACCEPTED 2
#define PLAYER_STATE1_TALKING 4
#define PLAYER_STATE1_29 8
#define TEXT_STATE_CLOSING 9
#define EXCH_ITEM_NONE 0
#define BTN_A 0x8000
#define PLAYER_STATE2_USING_OCARINA (1u<<27)
#define MSGMODE_NONE 0
#define MAXFLOAT 1000000
#define CHECK_BTN_ALL(value,mask) (((value)&(mask))==(mask))
#define ACTOR_FLAGS_CHECK_ALL(a,mask) CHECK_BTN_ALL((a)->flags,mask)
#define NA_SE_SY_GET_ITEM 1
typedef struct Actor { unsigned flags,textId; struct Actor *parent; } Actor;
typedef struct { struct { unsigned button; } press; } Input;
typedef struct { unsigned state,msgMode; } MessageContext;
typedef struct { struct { Input input[1]; } state; MessageContext msgCtx; } PlayState;
typedef struct { Actor actor; unsigned stateFlags1,stateFlags2,exchangeItemId,getItemId,getItemDirection;
    Actor *talkActor,*focusActor,*interactRangeActor,*naviActor; int talkActorDistance,naviTextId; } Player;
static unsigned gives,messages,sounds,last_item,last_text,refuse;
static unsigned sSariaSongTalk;
static void PlayerProxy_SariaSongTalk(PlayState *p) {}
static int gSfxDefaultPos,gSfxDefaultFreqAndVolScale,gSfxDefaultReverb;
static unsigned Message_GetState(MessageContext *m) { return m->state; }
static void Message_StartTextbox(PlayState *p,unsigned id,Actor *a) {
    ++messages; last_text=id; p->msgCtx.state=1;
}
static u8 Item_Give(PlayState *p,u8 item) { ++gives; last_item=item; return refuse ? item : ITEM_NONE; }
static void Audio_PlaySfxGeneral(int a,void *b,int c,void *d,void *e,void *f) { ++sounds; }
''' + function(PLAYER, 'static void PlayerProxy_GetItem(')
            + function(PLAYER, 'static void PlayerProxy_UpdateTalk(') + r'''
int main(void) {
    Player p={0}; PlayState play={0}; Actor npc={0};
    npc.textId=0x2040; p.talkActor=&npc;
    PlayerProxy_UpdateTalk(&p,&play); assert(!messages && !p.talkActor);
    p.talkActor=&npc; play.state.input[0].press.button=BTN_A;
    PlayerProxy_UpdateTalk(&p,&play);
    assert(messages==1 && last_text==npc.textId && (npc.flags&ACTOR_FLAG_TALK));
    assert(p.stateFlags1&PLAYER_STATE1_TALKING);
    play.msgCtx.state=TEXT_STATE_CLOSING; play.state.input[0].press.button=0;
    PlayerProxy_UpdateTalk(&p,&play); assert(!p.stateFlags1 && !p.talkActor && !p.focusActor);
    npc.flags=ACTOR_FLAG_TALK_OFFER_AUTO_ACCEPTED; p.talkActor=&npc;
    PlayerProxy_UpdateTalk(&p,&play); assert(messages==2); /* source auto talk, no A */
    play.msgCtx.state=TEXT_STATE_CLOSING; PlayerProxy_UpdateTalk(&p,&play);
    /* Successful source reward gets its own textbox and parent handshake once. */
    p.getItemId=GI_BOTTLE_MILK_FULL; p.interactRangeActor=&npc;
    PlayerProxy_GetItem(&p,&play);
    assert(gives==1 && last_item==ITEM_BOTTLE_MILK_FULL && npc.parent==&p.actor);
    assert(messages==3 && last_text==0x98 && sounds==1 && !p.getItemId);
    PlayerProxy_GetItem(&p,&play); assert(gives==1 && messages==3);
    play.msgCtx.state=TEXT_STATE_CLOSING; PlayerProxy_UpdateTalk(&p,&play);
    assert(!p.stateFlags1);
    /* No empty bottle: rejected refill never tells actor reward succeeded. */
    npc.parent=0; refuse=1; p.getItemId=GI_MILK; p.interactRangeActor=&npc;
    PlayerProxy_GetItem(&p,&play);
    assert(gives==2 && last_item==ITEM_MILK && !npc.parent && messages==3);
    refuse=0; p.getItemId=GI_MILK; p.interactRangeActor=&npc;
    PlayerProxy_GetItem(&p,&play); assert(npc.parent==&p.actor && messages==4);
    return 0;
}
''')

    def test_dawn_hatch_requires_persistent_trade_slot_replacement(self):
        self.run_c(r'''
#include <assert.h>
#include <stdint.h>
''' + '#include "' + (ROOT / 'src/save_state.c').as_posix() + '"\n' + r'''
typedef uint16_t u16;
typedef uint32_t u32;
typedef int32_t s32;
typedef struct {int unused;} PlayState;
static struct {unsigned rupees;} gameplay;
static struct {struct {struct {struct {unsigned char items[24];} inventory;} info;} save;} gSaveContext;
#define ARRAY_COUNT(a) (sizeof(a)/sizeof((a)[0]))
#define ITEM_NONE 0xff
''' + function(HOST, 'static unsigned char host_give_item(') + r'''
static unsigned char Item_Give(PlayState* play,unsigned char item) { return host_give_item(item); }
''' + function(ROOT/'oot-core/src/oot_core_api.cpp', 'static s32 OotCore_ReplaceDayItem(') + r'''
int main(void) {
    PlayState play={0};save_new_game();
    for(unsigned i=0;i<24;++i)gSaveContext.save.info.inventory.items[i]=0xff;
    save_state.source_items[23]=0x21;gSaveContext.save.info.inventory.items[23]=0x21;
    save_state.source_items[22]=0x2d;gSaveContext.save.info.inventory.items[22]=0x2d;
    save_state.c_items[0]=0x20+23;
    assert(OotCore_ReplaceDayItem(&play,0x21,0x22));
    assert(save_state.source_items[23]==0x22 && gSaveContext.save.info.inventory.items[23]==0x22);
    assert(save_state.c_items[0]==0x20+23); /* slot assignment stays */
    assert(OotCore_ReplaceDayItem(&play,0x2d,0x2e));
    assert(save_state.source_items[22]==0x2e && gSaveContext.save.info.inventory.items[22]==0x2e);
    assert(!OotCore_ReplaceDayItem(&play,0x21,0x22));
    /* A stale mirror must never overwrite an unrelated persistent trade item
     * or display a hatch textbox when the C backend refused the replacement. */
    save_state.source_items[23]=0x27;gSaveContext.save.info.inventory.items[23]=0x21;
    assert(!OotCore_ReplaceDayItem(&play,0x21,0x22));
    assert(save_state.source_items[23]==0x27 && gSaveContext.save.info.inventory.items[23]==0x21);
    return 0;
}
''')


if __name__ == '__main__':
    unittest.main()
