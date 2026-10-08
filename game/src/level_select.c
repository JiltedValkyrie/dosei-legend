/* Debug test menu, also retained behind the title cheat. All retail maps are offered.
 * Test runs use a fresh in-memory file; the caller leaves no backup slot bound. */
#include "level_select.h"
#include "scene_table.h"
#include "save_state.h"
level_select_t level_select;
/* Explicit region membership preserves stable scene IDs and includes every map. */
static const unsigned char regions[SCENE_COUNT]={
    [SCENE_LINK_HOME]=0,[SCENE_SPOT04]=0,[SCENE_KOKIRI_SHOP]=0,[SCENE_KOKIRI_HOME]=0,[SCENE_KOKIRI_HOME3]=0,[SCENE_KOKIRI_HOME4]=0,[SCENE_KOKIRI_HOME5]=0,[SCENE_YDAN]=0,[SCENE_SPOT10]=0,[SCENE_YDAN_BOSS]=0,[SCENE_SPOT05]=0,[SCENE_BMORI1]=0,[SCENE_MORIBOSSROOM]=0,
    [SCENE_SPOT00]=1,
    [SCENE_MALON_STABLE]=2,[SCENE_SOUKO]=2,[SCENE_SPOT20]=2,
    [SCENE_GANON_SONOGO]=3,[SCENE_GANONTIKASONOGO]=3,[SCENE_TAKARAYA]=3,[SCENE_GANON_BOSS]=3,[SCENE_ENTRA]=3,[SCENE_ENTRA_N]=3,[SCENE_ENRUI]=3,[SCENE_MARKET_ALLEY]=3,[SCENE_MARKET_ALLEY_N]=3,[SCENE_MARKET_DAY]=3,[SCENE_MARKET_NIGHT]=3,[SCENE_MARKET_RUINS]=3,[SCENE_SHRINE]=3,[SCENE_SHRINE_N]=3,[SCENE_SHRINE_R]=3,[SCENE_SHOP1]=9,[SCENE_DRAG]=4,[SCENE_ALLEY_SHOP]=3,[SCENE_NIGHT_SHOP]=3,[SCENE_FACE_SHOP]=3,[SCENE_TOKINOMA]=3,[SCENE_KENJYANOMA]=3,[SCENE_HAIRAL_NIWA_N]=3,[SCENE_NAKANIWA]=3,[SCENE_BOWLING]=3,[SCENE_MIHARIGOYA]=3,[SCENE_GANON_DEMO]=3,[SCENE_GANON_TOU]=3,[SCENE_GANON]=3,[SCENE_GANONTIKA]=3,[SCENE_GANON_FINAL]=3,[SCENE_HAIRAL_NIWA]=3,[SCENE_HIRAL_DEMO]=3,[SCENE_SPOT15]=3,
    [SCENE_HAKADANCH]=4,[SCENE_HAKADAN_BS]=4,[SCENE_KAKARIKO]=4,[SCENE_KAKARIKO3]=3,[SCENE_IMPA]=3,[SCENE_HAKAANA]=4,[SCENE_HAKAANA2]=4,[SCENE_HAKAANA_OUKE]=4,[SCENE_MAHOUYA]=4,[SCENE_KINSUTA]=4,[SCENE_SPOT01]=4,[SCENE_SPOT02]=4,[SCENE_HAKADAN]=4,[SCENE_HAKASITARELAY]=4,
    [SCENE_DDAN_BOSS]=5,[SCENE_FIRE_BS]=5,[SCENE_GOLON]=5,[SCENE_LABO]=4,[SCENE_SPOT17]=5,[SCENE_SPOT18]=5,[SCENE_DDAN]=5,[SCENE_HIDAN]=5,[SCENE_SPOT16]=5,
    [SCENE_ZOORA]=6,[SCENE_SPOT03]=6,[SCENE_BDAN]=6,[SCENE_ICE_DOUKUTU]=6,[SCENE_BDAN_BOSS]=6,[SCENE_SPOT07]=6,[SCENE_SPOT08]=6,
    [SCENE_MIZUSIN_BS]=7,[SCENE_HYLIA_LABO]=7,[SCENE_SPOT06]=7,[SCENE_MIZUSIN]=7,[SCENE_TURIBORI]=7,
    [SCENE_GERUDOWAY]=8,[SCENE_JYASINBOSS]=8,[SCENE_TENT]=8,[SCENE_SPOT12]=8,[SCENE_JYASINZOU]=8,[SCENE_MEN]=8,[SCENE_SPOT09]=8,[SCENE_SPOT11]=8,[SCENE_SPOT13]=8,
    [SCENE_HUT]=4,[SCENE_DAIYOUSEI_IZUMI]=9,[SCENE_YOUSEI_IZUMI_TATE]=9,[SCENE_YOUSEI_IZUMI_YOKO]=9,[SCENE_SYATEKIJYOU]=9,[SCENE_KAKUSIANA]=9,
};
static const char *const region_names[]={
    "Kokiri Forest",
    "Hyrule Field",
    "Lon Lon Ranch",
    "Market & Castle",
    "Kakariko & Graveyard",
    "Death Mountain",
    "Zora's Domain",
    "Lake Hylia",
    "Gerudo Desert",
    "Shared Interiors",
};
const char *level_select_region(unsigned region) {return region_names[region];}
unsigned level_select_map(unsigned region,unsigned index)
{
    unsigned i;
    for(i=0;i<SCENE_COUNT;++i)if(regions[i]==region && index--==0)return i;
    return SCENE_COUNT;
}
unsigned level_select_count(void)
{
    unsigned i,n=0;
    if(level_select.page==LEVEL_REGIONS)return sizeof(region_names)/sizeof(region_names[0]);
    if(level_select.page==LEVEL_OPTIONS)return 5;
    for(i=0;i<SCENE_COUNT;++i)if(regions[i]==level_select.region)++n;
    return n;
}
unsigned __attribute__((optimize("Os"))) level_select_step(int vertical,int horizontal,bool confirm,bool cancel)
{
    unsigned n=level_select_count();
    if(cancel) {
        if(level_select.page==LEVEL_REGIONS)return LEVEL_BACK;
        if(level_select.page==LEVEL_OPTIONS) {
            level_select.page=LEVEL_MAPS;level_select.cursor=level_select.map_cursor;
        } else {level_select.page=LEVEL_REGIONS;level_select.cursor=level_select.region;}
        level_select.failed=false;
        return LEVEL_NONE;
    }
    if(vertical)level_select.cursor=(level_select.cursor+n+(vertical<0?-1:1))%n;
    if(level_select.page==LEVEL_OPTIONS) {
        if(level_select.cursor==0 && (horizontal || confirm))level_select_move(0,horizontal?horizontal:1);
        else if(confirm) {
            switch(level_select.cursor) {
            case 1:level_select_toggle_era();break;
            case 2:level_select_toggle_max_gear();break;
            case 3:return LEVEL_BEGIN;
            case 4:return level_select_step(0,0,false,true);
            }
        }
    } else if(confirm) {
        if(level_select.page==LEVEL_REGIONS) {
            level_select.region=level_select.cursor;level_select.page=LEVEL_MAPS;
        } else {
            level_select.map_cursor=level_select.cursor;
            level_select.scene=level_select_map(level_select.region,level_select.cursor);
            level_select.room=0;level_select.page=LEVEL_OPTIONS;level_select.failed=false;
        }
        level_select.cursor=0;
    }
    return LEVEL_NONE;
}

void level_select_open(void) {level_select=(level_select_t){.scene=SCENE_YDAN,.visible=true};}
void level_select_toggle_max_gear(void) {level_select.max_gear=!level_select.max_gear;}
void level_select_toggle_era(void) {level_select.adult=!level_select.adult;}
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
void __attribute__((optimize("Os"))) level_select_prepare(void)
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
    if(level_select.max_gear)save_test_max_gear();
    save_set_link_age(level_select.adult ? 0 : 1);
    if(level_select.adult) {
        /* Adult C defaults: bow, bombs, hookshot -- only when owned/usable. */
        static const uint8_t slots[3]={3,2,9};
        unsigned i,action;
        for(i=0;i<3;++i)if((action=save_c_item_for_slot(slots[i]))!=0)save_state.c_items[i]=(uint8_t)action;
    }
}
