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
typedef uint8_t u8;
typedef int16_t s16;
typedef struct { u8 buttonItems[4], cButtonSlots[3]; unsigned equipment; } ItemEquips;
typedef struct { unsigned char playerName[8];int health,healthCapacity,rupees,magicLevel,magic;
    int isMagicAcquired,isDoubleMagicAcquired,isDoubleDefenseAcquired,bgsFlag,ocarinaGameRoundNum;
} SavePlayerData;
typedef struct {
    unsigned char items[24];signed char ammo[16];unsigned short equipment;
    u32 upgrades,questItems;unsigned char dungeonItems[20];signed char dungeonKeys[19];int gsTokens,defenseHearts;
} Inventory;
typedef struct { unsigned long chest,swch,clear,collect; } SavedSceneFlags;
static struct {
    struct { int linkAge,nightFlag,dayTime,cutsceneIndex,totalDays,bgsDayCount,entranceIndex;
        struct { SavePlayerData playerData;Inventory inventory;
            ItemEquips equips;
            int32_t gsFlags[6];
            unsigned short eventChkInf[14],itemGetInf[4],infTable[30];
            SavedSceneFlags sceneFlags[124];
        } info;
    } save;
    int mapIndex,language,skyboxTime,nextDayTime,nextCutsceneIndex,sunsSongState,dogIsLost,dogParams,seqId,natureAmbienceId,forcedSeqId,retainWeatherMode;
} gSaveContext;
static int gWeatherMode;
enum {NEXT_TIME_NONE=0xffff,NEXT_CS_INDEX_NONE=0xffef,SUNSSONG_INACTIVE=0,NA_BGM_DISABLED=0xffff,
      NATURE_ID_DISABLED=0xff,NA_BGM_GENERAL_SFX=0,WEATHER_MODE_CLEAR=0};
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
      SLOT_SLINGSHOT=6,SLOT_OCARINA=7,SLOT_BOTTLE_1=18,SLOT_BOTTLE_4=21};
enum {ITEM_SWORD_KOKIRI=0x3b,ITEM_SWORD_MASTER=0x3c,ITEM_SWORD_BIGGORON=0x3d,
      ITEM_BOTTLE_EMPTY=0x14,ITEM_BOTTLE_POE=0x20,ITEM_BOTTLE_BIG_POE=0x1e};
enum {ITEM_DEKU_STICK=0,ITEM_DEKU_NUT=1,ITEM_SLINGSHOT=6,ITEM_OCARINA_FAIRY=7,ITEM_OCARINA_OF_TIME=8,ITEM_NONE=255};
enum {ITEM_SONG_MINUET=0x5a,ITEM_SONG_STORMS=0x65,QUEST_SONG_MINUET=6};
enum {ITEM_MEDALLION_FOREST=0x66,ITEM_MEDALLION_LIGHT=0x6b,QUEST_MEDALLION_FOREST=0,
      ITEM_KOKIRI_EMERALD=0x6c,ITEM_GORON_RUBY=0x6d,ITEM_ZORA_SAPPHIRE=0x6e, /* QUEST_KOKIRI_EMERALD: save_state.h */
      ITEM_STONE_OF_AGONY=0x6f,ITEM_GERUDOS_CARD=0x70,QUEST_STONE_OF_AGONY=21,
      ITEM_SKULL_TOKEN=0x71,QUEST_SKULL_TOKEN=23,
      ITEM_DUNGEON_BOSS_KEY=0x74,ITEM_DUNGEON_COMPASS=0x75,ITEM_DUNGEON_MAP=0x76,ITEM_SMALL_KEY=0x77};
static struct { u8 (*give_item)(u8 item); } *gOotCoreHost;
/* Source-only quest/dungeon paths below never invoke a host item grant.
 * Shop grant mirror behavior has its own source purchase fixture. */
static void OotCore_MirrorItemGrant(u8 item) { assert(false); }
''' + graphics.function(source, 'static void seed_scene_save(')
            + graphics.function(source, 'static void save_copy_out(PlayState* play) {')
            + graphics.function(source, 'static void oot_core_set_save(')
            + graphics.function(ROOT / 'oot-core/src/bridge_play.cpp', 'u8 Item_Give(') + r'''
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
    unsigned char skulls[32]={0},tokens=7;
    unsigned char memory_round=1;
    in.ocarina_game_round=&memory_round;
    skulls[0]=0x81;skulls[1]=0x24;skulls[2]=0x48;skulls[3]=0x12;skulls[23]=0x80;skulls[31]=0x55;
    in.skull_flags=skulls;in.skull_tokens_out=&tokens;
    in.quest_items=&quest;in.dungeon_items=dungeons;in.dungeon_keys=keys;in.bottle_items=bottles;
    memcpy(in.player_name,"Link    ",8);
    gOotCorePlay=NULL; /* first scene: host chooses the initial source layer */
    oot_core_set_save(&in);
    gOotCorePlay=&play;
    in.cutscene_index=0;
    oot_core_set_save(&in); /* live cutscene index is source-owned */
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
    assert((u32)gSaveContext.save.info.gsFlags[0]==0x12482481u);
    assert((u32)gSaveContext.save.info.gsFlags[5]==0x80000000u);
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
    /* Message_Draw learning grants each song in core, then the end-of-update
     * copy commits it. A host-only grant used to be overwritten here. */
    quest=1u<<18;oot_core_set_save(&in);
    for(unsigned song=ITEM_SONG_MINUET;song<=ITEM_SONG_STORMS;++song) {
        assert(Item_Give(&play,song)==ITEM_NONE);
        save_copy_out(&play);
        assert(quest&(1u<<(song-ITEM_SONG_MINUET+QUEST_SONG_MINUET)));
        memset(&gSaveContext,0,sizeof(gSaveContext));oot_core_set_save(&in);
        assert(inv->questItems==quest);
    }
    assert(quest==((1u<<18)|0x3ffc0));
    assert(Item_Give(&play,ITEM_SONG_MINUET)==ITEM_NONE);
    save_copy_out(&play);assert(quest==((1u<<18)|0x3ffc0));
    /* King Dodongo's Ruby and Dodongo's Cavern (mapIndex 1) chests commit
     * through the same copy; mapIndex 0 stays with the C Deku Tree. */
    assert(Item_Give(&play,ITEM_GORON_RUBY)==ITEM_NONE);
    save_copy_out(&play);assert(quest&(1u<<19));
    gSaveContext.mapIndex=1;
    assert(Item_Give(&play,ITEM_DUNGEON_MAP)==ITEM_NONE && inv->dungeonItems[1]==4);
    assert(Item_Give(&play,ITEM_DUNGEON_COMPASS)==ITEM_NONE && inv->dungeonItems[1]==6);
    inv->dungeonKeys[1]=-1;
    assert(Item_Give(&play,ITEM_SMALL_KEY)==ITEM_NONE && inv->dungeonKeys[1]==1);
    assert(Item_Give(&play,ITEM_SMALL_KEY)==ITEM_NONE && inv->dungeonKeys[1]==2);
    save_copy_out(&play);assert(dungeons[1]==6 && keys[1]==2);
    gSaveContext.mapIndex=0;
    /* Source token collect increments immediately; group bits and count
     * survive reload without endian aliasing or overwriting host groups. */
    assert(Item_Give(&play,ITEM_SKULL_TOKEN)==ITEM_NONE && inv->gsTokens==8);
    gSaveContext.save.info.gsFlags[5]|=0x08u;
    save_copy_out(&play);
    assert(tokens==8 && skulls[20]==8 && skulls[23]==0x80 && skulls[31]==0x55);
    in.skull_tokens=tokens;
    memset(&gSaveContext,0,sizeof(gSaveContext));oot_core_set_save(&in);
    assert(inv->gsTokens==8 && (inv->questItems&(1u<<QUEST_SKULL_TOKEN)));
    assert((u32)gSaveContext.save.info.gsFlags[5]==0x80000008u);
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
    in.c_slots[0]=3;in.c_slots[1]=9;in.c_slots[2]=2; /* HUD down bow, left hook, right bomb */
    oot_core_set_save(&in);
    assert(gSaveContext.save.info.equips.buttonItems[1]==11); /* C-left longshot */
    assert(gSaveContext.save.info.equips.buttonItems[2]==3);  /* C-down bow */
    assert(gSaveContext.save.info.equips.buttonItems[3]==2);  /* C-right bomb */
    assert(gSaveContext.save.info.equips.cButtonSlots[0]==9);
    assert(gSaveContext.save.info.equips.cButtonSlots[1]==3);
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
