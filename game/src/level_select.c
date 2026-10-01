/* Secret title test menu. Only registered playable scenes are offered.
 * Test runs use a fresh in-memory file; the caller leaves no backup slot bound. */
#include "level_select.h"
#include "scene_table.h"
#include "save_state.h"
level_select_t level_select;
void level_select_open(void) {level_select=(level_select_t){SCENE_YDAN,0,true,false};}
void level_select_move(int vertical,int horizontal)
{
    if(vertical) {
        level_select.scene=(level_select.scene+SCENE_COUNT+(vertical<0?-1:1))%SCENE_COUNT;
        level_select.room=0;
    }
    if(horizontal) {
        unsigned count=scene_entries[level_select.scene].rooms;
        if(count)level_select.room=(level_select.room+count+(horizontal<0?-1:1))%count;
    }
    if(vertical || horizontal)level_select.failed=false;
}
void level_select_prepare(void)
{
    save_new_game();
    save_item_give(SAVE_ITEM_SWORD_KOKIRI);save_item_give(SAVE_ITEM_SHIELD_DEKU);
    save_set_equip(EQUIP_TYPE_SWORD,EQUIP_VALUE_SWORD_KOKIRI);save_set_equip(EQUIP_TYPE_SHIELD,EQUIP_VALUE_SHIELD_DEKU);
    save_item_give(SAVE_ITEM_SLINGSHOT);save_item_give(SAVE_ITEM_DEKU_STICKS_10);save_item_give(SAVE_ITEM_DEKU_NUTS_10);
    save_item_give(SAVE_ITEM_DEKU_MAP);save_item_give(SAVE_ITEM_DEKU_COMPASS);
    save_state.c_items[0]=1;save_state.c_items[1]=2;save_state.c_items[2]=3;
    save_set_inf_table(INFTABLE_SARIA_GREETED_LINK);save_set_inf_table(INFTABLE_SARIA_NOTICED_FAIRY);
    save_set_event_chk_inf(EVENTCHKINF_MET_DEKU_TREE);save_set_event_chk_inf(EVENTCHKINF_DEKU_TREE_MOUTH_OPEN);
    save_set_event_chk_inf(EVENTCHKINF_MIDO_STOOD_ASIDE_KOKIRI);save_set_event_chk_inf(EVENTCHKINF_DEKU_TREE_INTRO_CS_SEEN);
    save_state.scene_id=scene_entries[level_select.scene].save_scene;save_state.entrance=0;
}
