"""Run production save mirror against source inventory/flag layouts."""
from pathlib import Path
import unittest
import test_graphics_backend as graphics

ROOT = Path(__file__).resolve().parents[1]


class CoreSave(unittest.TestCase):
    run_c = graphics.GraphicsBackend.run_c

    def test_dialogue_inventory_and_door_flags_round_trip(self):
        source = ROOT / 'oot-core/src/oot_core_api.cpp'
        self.run_c(r'''
#include <stdint.h>
#include <stdbool.h>
#include <assert.h>
#include <string.h>
''' + '#include "' + (ROOT / 'oot-core/include/oot_core_api.h').as_posix() + '"\n'
            + '#include "' + (ROOT / 'src/save_state.c').as_posix() + '"\n' + r'''
typedef uint32_t u32;
typedef struct { unsigned char playerName[8];int health,healthCapacity,rupees,magicLevel,magic;
    int isMagicAcquired,isDoubleMagicAcquired,isDoubleDefenseAcquired,bgsFlag;
} SavePlayerData;
typedef struct {
    unsigned char items[24];signed char ammo[16];unsigned short equipment;
    u32 upgrades,questItems;unsigned char dungeonItems[20];signed char dungeonKeys[19];int gsTokens,defenseHearts;
} Inventory;
typedef struct { unsigned long chest,swch,clear,collect; } SavedSceneFlags;
static struct {
    struct { int linkAge,nightFlag,dayTime,cutsceneIndex;
        struct { SavePlayerData playerData;Inventory inventory;
            struct {unsigned equipment;} equips;
            unsigned short eventChkInf[14],itemGetInf[4],infTable[30];
            SavedSceneFlags sceneFlags[124];
        } info;
    } save;
    int language;
} gSaveContext;
typedef struct {
    struct {struct {unsigned long chest,swch,clear,collect;} flags;} actorCtx;
} PlayState;
static PlayState play,*gOotCorePlay=&play;
static const OotCoreSave *sHostSave;
static unsigned sGenericScene;
#define ARRAY_COUNT(a) (sizeof(a)/sizeof((a)[0]))
#define LANGUAGE_ENG 0
#define FILENAME_DIGIT(c) ((c)-'0')
#define FILENAME_UPPERCASE(c) ((c)-'A'+0x0a)
#define FILENAME_LOWERCASE(c) ((c)-'a'+0x24)
#define FILENAME_DASH 0x3e
#define FILENAME_PERIOD 0x40
#define FILENAME_SPACE 0x3f
enum {SLOT_DEKU_STICK=0,SLOT_DEKU_NUT=1,SLOT_BOMB=2,SLOT_BOW=3,
      SLOT_SLINGSHOT=6,SLOT_OCARINA=7,SLOT_BOTTLE_1=18};
enum {ITEM_DEKU_STICK=0,ITEM_DEKU_NUT=1,ITEM_SLINGSHOT=6,ITEM_OCARINA_FAIRY=7,ITEM_OCARINA_OF_TIME=8,ITEM_NONE=255};
''' + graphics.function(source, 'static void seed_scene_save(')
            + graphics.function(source, 'static void save_copy_out(')
            + graphics.function(source, 'static void oot_core_set_save(') + r'''
int main(void) {
    unsigned short events[14]={0},items[4]={0},info[30]={0};
    unsigned long scene[4]={0x11223344,1u<<31,2,4};
    unsigned quest=1u<<18;
    unsigned char dungeons[20]={0},bottles[4]={0x14,0x1a,0xff,0xff};
    signed char keys[19];
    OotCoreSave in={0};
    memset(keys,-1,sizeof(keys));keys[3]=2;dungeons[3]=1;
    in.link_age=1;in.night=1;in.day_time=0x1000;in.cutscene_index=0xfff2;
    in.event_chk_inf=events;in.item_get_inf=items;in.inf_table=info;in.scene_flags=scene;
    in.health=0x30;in.health_capacity=0x40;in.rupees=42;
    in.owned_sword=1;in.owned_shield=1;in.equip_sword=1;in.equip_shield=1;
    in.fairy_ocarina=1;in.slingshot_owned=1;in.seed_ammo=29;
    in.stick_owned=1;in.stick_ammo=8;in.stick_upgrade=2;
    in.nut_owned=1;in.nut_ammo=17;in.nut_upgrade=3;
    in.deku_dungeon_items=3;in.skull_tokens=7;
    in.quest_items=&quest;in.dungeon_items=dungeons;in.dungeon_keys=keys;in.bottle_items=bottles;
    memcpy(in.player_name,"Link    ",8);
    oot_core_set_save(&in);
    Inventory *inv=&gSaveContext.save.info.inventory;
    assert(gSaveContext.save.linkAge==1 && gSaveContext.save.nightFlag==1);
    assert(gSaveContext.save.dayTime==0x1000 && gSaveContext.save.cutsceneIndex==0xfff2);
    assert(gSaveContext.save.info.equips.equipment==0x1111); /* Mido CUR_EQUIP_VALUE */
    assert(inv->equipment==0x1111 && inv->questItems==(1u<<18));
    assert(inv->items[SLOT_OCARINA]==7 && inv->items[18]==0x14 && inv->items[19]==0x1a);
    assert(inv->items[20]==255 && inv->items[SLOT_BOW]==255);
    assert(inv->upgrades==((2u<<17)|(3u<<20)|(1u<<14)));
    assert(inv->ammo[SLOT_DEKU_STICK]==8 && inv->ammo[SLOT_DEKU_NUT]==17);
    assert(inv->ammo[SLOT_SLINGSHOT]==29 && inv->gsTokens==7);
    assert(inv->dungeonItems[0]==6 && inv->dungeonItems[3]==1);
    assert(inv->dungeonKeys[0]==-1 && inv->dungeonKeys[3]==2);
    assert(play.actorCtx.flags.swch==(1u<<31));
    seed_scene_save(99);
    assert(gSaveContext.save.info.sceneFlags[99].swch==(1u<<31));
    assert(gSaveContext.save.info.sceneFlags[99].chest==0x11223344);
    assert(!gSaveContext.save.info.sceneFlags[98].swch);
    seed_scene_save(-1);seed_scene_save(124);
    inv->dungeonKeys[3]--;inv->dungeonItems[3]|=2;inv->questItems|=1u<<12;
    play.actorCtx.flags.swch|=1u<<5;gSaveContext.save.info.eventChkInf[1]|=8;
    save_copy_out(&play);
    assert(keys[3]==1 && dungeons[3]==3 && quest==((1u<<18)|(1u<<12)));
    assert(scene[1]==((1u<<31)|(1u<<5)) && events[1]==8);
    memset(&gSaveContext,0,sizeof(gSaveContext));oot_core_set_save(&in);
    assert(inv->dungeonKeys[3]==1 && play.actorCtx.flags.swch==scene[1]);
    /* Ownership must not imply equipment or a refill/new bottle. */
    in.equip_sword=in.equip_shield=in.fairy_ocarina=0;
    bottles[0]=0x1a;in.owned_shield=2;
    oot_core_set_save(&in);
    assert(gSaveContext.save.info.equips.equipment==0x1100);
    assert(inv->equipment==0x1121 && inv->items[SLOT_OCARINA]==255);
    assert(inv->items[18]==0x1a && inv->items[20]==255);
    /* Max Level Select loadout must reach source predicates, including the
     * stones/songs and slots that have no C action implementation yet. */
    save_new_game();save_test_max_gear();
    in.inventory_items=save_state.source_items;in.inventory_ammo=save_state.source_ammo;
    in.inventory_equipment=save_state.source_equipment;in.inventory_upgrades=save_state.source_upgrades;
    in.magic_level=save_state.source_magic_level;in.magic=save_state.source_magic;
    in.double_defense=save_state.source_double_defense;in.skull_tokens=save_state.source_tokens;
    in.fairy_ocarina=save_state.fairy_ocarina;in.bottle_items=save_state.bottle_items;
    in.quest_items=&save_state.quest_items;in.rupees=save_state.rupees;
    in.stick_upgrade=save_state.stick_upgrade;in.nut_upgrade=save_state.nut_upgrade;
    in.stick_ammo=save_state.stick_ammo;in.nut_ammo=save_state.nut_ammo;in.seed_ammo=save_state.ammo_seeds;
    oot_core_set_save(&in);
    assert(inv->items[7]==8 && inv->items[9]==11 && inv->items[2]==2 && inv->items[3]==3);
    assert(inv->items[22]==0x37 && inv->items[23]==0x2b);
    assert(inv->equipment==0x7777 && inv->upgrades==0x36e4db && inv->questItems==0x00ffffff);
    assert(inv->ammo[0]==30 && inv->ammo[1]==40 && inv->ammo[2]==40 && inv->ammo[3]==50 && inv->ammo[6]==50);
    assert(gSaveContext.save.info.playerData.rupees==500 && gSaveContext.save.info.playerData.magic==96);
    assert(gSaveContext.save.info.playerData.isMagicAcquired && gSaveContext.save.info.playerData.isDoubleMagicAcquired);
    assert(gSaveContext.save.info.playerData.isDoubleDefenseAcquired && gSaveContext.save.info.playerData.bgsFlag);
    assert(inv->defenseHearts==20 && inv->gsTokens==100);
    oot_core_set_save(0);save_copy_out(&play);
    return 0;
}
''')


if __name__ == '__main__':
    unittest.main()
