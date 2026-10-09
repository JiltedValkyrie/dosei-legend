"""Execute the live inventory/tool boundary, including failed source spawns."""
from pathlib import Path
import unittest

import test_graphics_backend as graphics

ROOT = Path(__file__).resolve().parents[1]


class InventoryTools(unittest.TestCase):
    run_c = graphics.GraphicsBackend.run_c

    def test_core_step_sweep_hits_between_arrow_endpoints_and_keeps_source_damage(self):
        self.run_c(r'''
#include <assert.h>
#include <string.h>
''' + '#include "' + (ROOT/'src/collide.c').as_posix() + '"\n' +
        '#include "' + (ROOT/'oot-core/include/oot_core_api.h').as_posix() + '"\n' + r'''
actor_handle_t actor_handle(const actor_t *a) { (void)a;return ACTOR_HANDLE_NONE; }
uint16_t collide_heading(int32_t x,int32_t z) { (void)x;(void)z;return 0; }
#define ACTOR_EN_BOM 0x10
#define ACTOR_EN_ARROW 0x16
static bool playing=true;
static struct {collider_t tool_at[OOT_CORE_TOOL_VIEWS_MAX];int tool_pull[6];unsigned tool_bits;} storage;
#define CORE_DRAW (&storage)
static OotCoreToolView views[2];
static int count;
static int tool_view(const OotCoreToolView **out){*out=views;return count;}
static struct {int (*tool_view)(const OotCoreToolView **);} entry={tool_view};
#define ENTRY (&entry)
''' + graphics.function(ROOT/'src/oot_core_host.c','void oot_core_tool_register(') +
        graphics.function(ROOT/'src/oot_core_host.c','bool oot_core_tool_pull(') + r'''
int main(void) {
    collider_t victim={0};int32_t step[3];unsigned i;
    victim.shape=COLSHAPE_CYLINDER;victim.x=1000;victim.y=490;victim.z=-800;
    victim.radius=12;victim.height=30;victim.ac_type=AC_TYPE_PLAYER;victim.ac_bumper=DMG_ARROW_NORMAL;
    views[0]=(OotCoreToolView){.id=ACTOR_EN_ARROW,.attack_id=1,.x=1000,.y=500,.z=-675,
        .previous_x=1000,.previous_y=500,.previous_z=-900,.dmg=DMG_ARROW_NORMAL,.damage=1};
    count=1;collide_begin();oot_core_tool_register();collide_set_ac(&victim);collide_run();
    assert(victim.result & COL_RES_AC_HIT);assert(victim.ac_damage==1);
    assert(storage.tool_at[0].shape==COLSHAPE_CAPSULE);
    /* Skipped core update repeats the same sweep without a second hit. */
    collide_begin();oot_core_tool_register();collide_set_ac(&victim);collide_run();
    assert(!(victim.result & COL_RES_AC_HIT));
    /* Row order can change; identity belongs to the source spawn. */
    views[1]=views[0];views[0].held=1;count=2;
    collide_begin();oot_core_tool_register();collide_set_ac(&victim);collide_run();
    assert(!(victim.result & COL_RES_AC_HIT));
    views[1].attack_id=2;
    collide_begin();oot_core_tool_register();collide_set_ac(&victim);collide_run();
    assert(victim.result & COL_RES_AC_HIT);
    views[0]=(OotCoreToolView){.id=ACTOR_EN_BOM,.attack_id=3,.x=1000,.y=500,.z=-800,
        .radius=24,.dmg=DMG_EXPLOSIVE,.damage=8};count=1;victim.ac_bumper=DMG_EXPLOSIVE;
    collide_begin();oot_core_tool_register();collide_set_ac(&victim);collide_run();
    assert(victim.result & COL_RES_AC_HIT);assert(victim.ac_damage==8);
    assert(storage.tool_at[0].shape==COLSHAPE_CYLINDER);
    assert(!oot_core_tool_pull(step));storage.tool_bits=OOT_CORE_TOOL_PULLING;
    storage.tool_pull[0]=30*256;storage.tool_pull[1]=-15*256;storage.tool_pull[2]=257;
    assert(oot_core_tool_pull(step));for(i=0;i<3;++i)assert(step[i]==storage.tool_pull[i]);
    playing=false;assert(!oot_core_tool_pull(step));
    return 0;
}
''')

    def test_pause_equips_source_owned_big_sword_and_mirror_with_legacy_cache_empty(self):
        self.run_c(r'''
#include <assert.h>
''' + '#include "' + (ROOT/'src/gameplay.h').as_posix() + '"\n' +
        '#include "' + (ROOT/'src/save_state.c').as_posix() + '"\n' +
        '#include "' + (ROOT/'src/pause_window_state.c').as_posix() + '"\n' + r'''
gameplay_t gameplay;
''' + graphics.function(ROOT/'src/gameplay.c','static void __attribute__((optimize("Os"))) update_menu(') + r'''
static void equip(unsigned cursor) {
    gameplay_input_t input={0};
    gameplay.paused=true;gameplay.events=0;
    gameplay.pause_window.page=PAUSE_EQUIPMENT;
    gameplay.pause_window.cursor[PAUSE_EQUIPMENT]=cursor;
    input.interact=true;update_menu(&input);
}
int main(void) {
    save_state.link_age=0;save_state.source_equipment=0x44;
    assert(gameplay.owned==0 && save_state.owned_sword==0 && save_state.owned_shield==0);
    equip(3);assert(gameplay.events & GP_EVENT_EQUIP);
    assert(save_state.equip_sword==3 && (gameplay.owned & GP_SWORD) && (gameplay.equipped & GP_SWORD));
    equip(7);assert(gameplay.events & GP_EVENT_EQUIP);
    assert(save_state.equip_shield==3 && (gameplay.owned & GP_SHIELD) && (gameplay.equipped & GP_SHIELD));
    equip(2);assert(gameplay.events & GP_EVENT_DENIED);assert(save_state.equip_sword==3);
    equip(6);assert(gameplay.events & GP_EVENT_DENIED);assert(save_state.equip_shield==3);
    save_state.source_equipment=0x7777;save_state.owned_sword=save_state.equip_sword=2;
    save_state.owned_shield=save_state.equip_shield=2;
    equip(3);assert(gameplay.events & GP_EVENT_EQUIP);assert(save_state.equip_sword==3);
    equip(7);assert(gameplay.events & GP_EVENT_EQUIP);assert(save_state.equip_shield==3);
    equip(2);assert(gameplay.events & GP_EVENT_EQUIP);assert(save_state.equip_sword==2);
    equip(6);assert(gameplay.events & GP_EVENT_EQUIP);assert(save_state.equip_shield==2);
    save_state.link_age=1;save_state.equip_sword=save_state.equip_shield=1;
    equip(3);assert(gameplay.events & GP_EVENT_DENIED);assert(save_state.equip_sword==1);
    equip(7);assert(gameplay.events & GP_EVENT_DENIED);assert(save_state.equip_shield==1);
    return 0;
}
''')

    def test_source_tool_admission_commits_ammo_and_magic_once(self):
        self.run_c(r'''
#include <assert.h>
#include <stdint.h>
#include <stdbool.h>
#include <string.h>
''' + '#include "' + (ROOT/'src/save_state.c').as_posix() + '"\n' +
        '#include "' + (ROOT/'oot-core/include/oot_core_api.h').as_posix() + '"\n' + r'''
static bool playing;
static struct { unsigned tool_bits; } storage;
#define CORE_DRAW (&storage)
static int accepted, calls, last[6];
static int tool(unsigned command, int *io) {
    assert(command == OOT_CORE_TOOL_USE);
    ++calls; memcpy(last,io,sizeof last); return accepted;
}
static struct { int (*tool)(unsigned,int*); } entry = {tool};
#define ENTRY (&entry)
/* health_hud.c magic state: consume here completes at once (the meter's
 * 2-per-frame drain is health_hud_magic_update's job). */
static bool magic_busy; static unsigned errors;
static void action_audio_decomp_sfx(unsigned id) { if (id == 0x4806) ++errors; }
static bool health_hud_magic_idle(void) { return !magic_busy; }
static bool health_hud_magic_available(unsigned a) {
    return save_state.source_magic_level && save_state.source_magic >= a;
}
static bool health_hud_magic_consume(unsigned a) { save_state.source_magic -= a; magic_busy = true; return true; }
''' + graphics.function(ROOT/'src/oot_core_host.c','bool oot_core_tool_use(') + r'''
static const int32_t origin[3] = {123,456,-789};
static void reset(void) {
    memset(&save_state,0,sizeof save_state);
    memset(save_state.source_items,0xff,sizeof save_state.source_items);
    playing=true;accepted=1;calls=0;storage.tool_bits=0;magic_busy=false;errors=0;
    save_state.link_age=0;save_state.source_magic_level=1;
    save_state.source_magic=24;save_state.source_items[3]=3;
    save_state.source_ammo[3]=10;
}
static bool use(unsigned slot) { return oot_core_tool_use(slot,origin,0x1234,-0x2345); }
int main(void) {
    const unsigned slots[3]={4,10,16}, items[3]={4,12,18}, costs[3]={4,4,8};
    unsigned i;
    reset();assert(use(3));assert(calls==1 && last[0]==3);
    assert(last[1]==123 && last[2]==456 && last[3]==-789 && last[4]==0x1234 && last[5]==-0x2345);
    assert(save_state.source_ammo[3]==9 && save_state.source_magic==24);
    for(i=0;i<3;++i) {
        reset();save_state.source_items[slots[i]]=items[i];
        assert(use(slots[i]));assert(last[0]==(int)items[i]);
        assert(save_state.source_ammo[3]==9 && save_state.source_magic==24-costs[i]);
        reset();save_state.source_items[slots[i]]=items[i];accepted=0;
        assert(!use(slots[i]));assert(calls==1);
        assert(save_state.source_ammo[3]==10 && save_state.source_magic==24);
        reset();save_state.source_items[slots[i]]=items[i];save_state.source_magic=costs[i]-1;
        assert(use(slots[i]));assert(last[0]==3);
        assert(save_state.source_ammo[3]==9 && save_state.source_magic==costs[i]-1);
        assert(save_state.source_items[slots[i]]==items[i]);
        reset();save_state.source_items[slots[i]]=items[i];save_state.source_magic=costs[i];
        assert(use(slots[i]));assert(last[0]==(int)items[i] && save_state.source_magic==0);
        reset();save_state.source_items[slots[i]]=items[i];save_state.source_items[3]=0xff;
        assert(!use(slots[i]));assert(calls==0 && save_state.source_magic==24);
    }
    /* func_8083442C: a busy meter refuses the next magic arrow (error). */
    reset();save_state.source_items[4]=4;magic_busy=true;
    assert(!use(4));assert(calls==0 && errors==1 && save_state.source_magic==24);
    /* Short magic: error sound, normal arrow. */
    reset();save_state.source_items[4]=4;save_state.source_magic=3;
    assert(use(4));assert(last[0]==3 && errors==1 && save_state.source_magic==3);
    reset();save_state.source_items[4]=4;save_state.source_magic_level=0;
    assert(use(4));assert(last[0]==3 && save_state.source_magic==24);
    reset();save_state.source_ammo[3]=0;
    assert(!use(3));assert(calls==0 && save_state.source_magic==24);
    reset();save_state.link_age=1;
    assert(!use(3));assert(calls==0 && save_state.source_ammo[3]==10);
    reset();playing=false;assert(!use(3));assert(calls==0);
    reset();assert(!use(24));assert(calls==0);
    reset();storage.tool_bits=OOT_CORE_TOOL_HOLDING;
    assert(!use(3));assert(calls==0 && save_state.source_ammo[3]==10);
    for(i=0;i<2;++i) {
        unsigned slot=i?8:2;
        reset();save_state.source_items[slot]=i?9:2;save_state.source_ammo[slot]=3;accepted=0;
        assert(!use(slot));assert(storage.tool_bits==0 && save_state.source_ammo[slot]==3);
        accepted=1;assert(use(slot));assert(storage.tool_bits==OOT_CORE_TOOL_HOLDING);
        assert(save_state.source_ammo[slot]==2);
        assert(!use(slot));assert(save_state.source_ammo[slot]==2 && calls==2);
    }
    reset();save_state.source_items[9]=11;
    assert(use(9));assert(last[0]==11 && save_state.source_ammo[3]==10 && save_state.source_magic==24);
    reset();save_state.link_age=1;save_state.source_items[12]=14;
    assert(use(12));assert(last[0]==14 && save_state.source_magic==24);
    return 0;
}
''')

    def test_player_proxy_survives_room_change_and_iron_boots_leave_swim_clip(self):
        # Player_Init: room -1, else func_80031B14 deletes Player on a room
        # change and every C tool use is refused (human report 2026-10-08).
        init = graphics.function(ROOT/'oot-core/src/bridge_player.cpp', 'static void PlayerProxy_Init(')
        self.assertIn('thisx->room = -1;', init)
        recomp = (ROOT/'src/recomp.c').read_text(encoding='utf-8')
        self.assertIn('if (iron && was_water) { link_anim_move_end();', recomp)
        self.assertIn('if (!was_water && st == LINK_STATE_SWIM) { link_anim_move_end();', recomp)


if __name__ == '__main__':
    unittest.main()
