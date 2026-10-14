"""Source shop predicates, grants, stock assets and one-owner boundaries."""
import os
from pathlib import Path
import re
import sys
import unittest

import test_graphics_backend as graphics
from test_child_route_npcs import function

GAME = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(GAME / 'tools'))
import child_route_shops as shops
import build_shop_sprites

OOT = Path(os.environ.get('DOSEI_OOT', 'D:/Workspace-Claude/game-decomps/n64/oot'))


def enum(text, name):
    return re.search(r'typedef enum ' + name + r' \{.*?\} ' + name + ';', text, re.S)[0]


@unittest.skipUnless((OOT / shops.ITEM_SOURCE).exists(), 'local OoT decomp required')
class ChildRouteShops(unittest.TestCase):
    run_c = graphics.GraphicsBackend.run_c

    def fixture(self):
        item = (OOT / 'include/item.h').read_text()
        girl = (OOT / shops.ITEM_SOURCE).with_suffix('.h').read_text()
        return r'''
#include <stdint.h>
#include <stdbool.h>
#include <string.h>
#include <assert.h>
''' + '#include "' + (GAME / 'src/save_state.c').as_posix() + '"\n' + enum(item, 'ItemID') + enum(item, 'InventorySlot') + enum(girl, 'EnGirlAShopItem') + enum(girl, 'EnGirlACanBuyResult') + r'''
typedef uint8_t u8; typedef uint32_t u32; typedef int32_t s32; typedef int16_t s16;
typedef struct { int unused; } PlayState;
typedef struct { u8 items[24]; signed char ammo[16]; unsigned equipment,upgrades,questItems; } Inventory;
typedef struct { u8 buttonItems[4],cButtonSlots[3]; } ItemEquips;
static struct { struct { struct { Inventory inventory; ItemEquips equips;
    struct { int rupees,health,healthCapacity; } playerData;
    unsigned itemGetInf[4]; } info; } save; } gSaveContext;
enum { UPG_QUIVER,UPG_BOMB_BAG,UPG_STRENGTH,UPG_SCALE,UPG_WALLET,UPG_BULLET_BAG,UPG_DEKU_STICKS,UPG_DEKU_NUTS };
static const unsigned shifts[]={0,3,6,9,12,14,17,20};
static const int caps[][4]={{0,30,40,50},{0,20,30,40},{0},{0},{99,200,500,500},{0,30,40,50},{0,10,20,30},{0,20,30,40}};
static int slot_of(int item) { if(item<=6)return item; if(item==ITEM_BOMBCHU)return 8;
    if(item>=ITEM_BOTTLE_EMPTY && item<=ITEM_BOTTLE_POE)return 18; return 23; }
#define SLOT(i) slot_of(i)
#define INV_CONTENT(i) gSaveContext.save.info.inventory.items[SLOT(i)]
#define AMMO(i) gSaveContext.save.info.inventory.ammo[SLOT(i)]
#define CUR_UPG_VALUE(u) ((gSaveContext.save.info.inventory.upgrades>>shifts[u])&3)
#define CUR_CAPACITY(u) caps[u][CUR_UPG_VALUE(u)]
#define ITEMGETINF_13 0x13
#define SET_ITEMGETINF(x) (gSaveContext.save.info.itemGetInf[(x)>>4]|=1u<<((x)&15))
#define GET_ITEMGETINF(x) (gSaveContext.save.info.itemGetInf[(x)>>4]&(1u<<((x)&15)))
''' + '#include "' + (GAME / 'src/core_item_grants.inc').as_posix() + '"\n' + '#include "' + (GAME / 'oot-core/include/core_item_grant_mirror.inc').as_posix() + '"\n'

    def test_stock_recipes_and_source_scene_closure(self):
        self.assertEqual(len(shops.stock_entries(OOT)), 50)
        self.assertEqual(len(shops.stock_draws(OOT)), 34)
        self.assertEqual(build_shop_sprites.header(OOT), (GAME / 'oot-core/include/child_route_shop_items.h').read_text())
        root = OOT / 'extracted/ntsc-1.2/assets/scenes/shops'
        for name in shops.SOURCE_SCENES:
            objects = shops.scene_objects(OOT, root / name / (name + '_scene.c'))
            self.assertTrue(objects)
            self.assertLessEqual(len(objects), 11)
        self.assertNotIn('kokiri_shop', shops.SOURCE_SCENES)
        self.assertIn('object_gi_soldout', shops.scene_objects(OOT, root / 'night_shop/night_shop_scene.c'))

    def test_source_purchase_actions_unchanged_and_no_keeper_pose(self):
        for rel in shops.SOURCES:
            original = (OOT / rel).read_text(encoding='utf-8')
            adapted = shops.adapt(rel, original)
            if rel == shops.SHELF_SOURCE:
                self.assertEqual(original, adapted)
                continue
            self.assertNotRegex(adapted, r'\b(?:SkelAnime_Draw\w*|SkelAnime_Init\w*|Matrix_\w+)\(')
            for name in re.findall(r'^(?:void|s32) (En(?:GirlA_(?:CanBuy|ItemGive|BuyEvent)\w*|Ossan_State_\w+))\(', original, re.M):
                self.assertEqual(function(original, name), function(adapted, name), name)

    def test_host_grants_and_same_tick_mirror(self):
        self.run_c(self.fixture() + r'''
int main(void) {
    save_new_game(); memset(gSaveContext.save.info.inventory.items,255,24);
    for(int i=0;i<3;++i)gSaveContext.save.info.equips.cButtonSlots[i]=255;
    assert(core_item_grants(ITEM_BOTTLE_POTION_RED)==0);
    save_state.bottle_items[0]=ITEM_BOTTLE_EMPTY;
    INV_CONTENT(ITEM_BOTTLE_EMPTY)=ITEM_BOTTLE_EMPTY;
    gSaveContext.save.info.equips.cButtonSlots[1]=18;
    assert(core_item_grants(ITEM_BOTTLE_POTION_RED)==1); OotCore_MirrorItemGrant(ITEM_BOTTLE_POTION_RED);
    assert(save_state.bottle_items[0]==ITEM_BOTTLE_POTION_RED);
    assert(INV_CONTENT(ITEM_BOTTLE_EMPTY)==ITEM_BOTTLE_POTION_RED);
    assert(gSaveContext.save.info.equips.buttonItems[2]==ITEM_BOTTLE_POTION_RED);
    assert(core_item_grants(ITEM_BOTTLE_FISH)==0); /* Full bottle cannot be overwritten. */
    assert(core_item_grants(ITEM_SHIELD_HYLIAN)==1); OotCore_MirrorItemGrant(ITEM_SHIELD_HYLIAN);
    assert(save_state.source_equipment==0x20 && !save_state.equip_shield);
    assert(gSaveContext.save.info.inventory.equipment==0x20);
    assert(core_item_grants(ITEM_MASK_KEATON)==1); OotCore_MirrorItemGrant(ITEM_MASK_KEATON);
    assert(save_state.source_items[23]==ITEM_MASK_KEATON && gSaveContext.save.info.inventory.items[23]==ITEM_MASK_KEATON);
    save_state.slingshot=1;save_state.ammo_seeds=25;
    gSaveContext.save.info.inventory.upgrades=1u<<14;AMMO(ITEM_SLINGSHOT)=25;
    assert(core_item_grants(ITEM_DEKU_SEEDS_30)==1); OotCore_MirrorItemGrant(ITEM_DEKU_SEEDS_30);
    assert(save_state.ammo_seeds==30 && AMMO(ITEM_SLINGSHOT)==30 && GET_ITEMGETINF(ITEMGETINF_13));
    assert(core_item_grants(ITEM_BOMBCHU)==1); OotCore_MirrorItemGrant(ITEM_BOMBCHU);
    assert(save_state.source_ammo[8]==10 && AMMO(ITEM_BOMBCHU)==10);
    for(int i=0;i<3;++i) { assert(core_item_grants(ITEM_BOMBCHUS_20)==1);OotCore_MirrorItemGrant(ITEM_BOMBCHUS_20); }
    assert(save_state.source_ammo[8]==50 && AMMO(ITEM_BOMBCHU)==50);
    assert(core_item_grants(ITEM_RUPEE_GREEN)==-1 && save_state.rupees==0);
    assert(core_item_grants(ITEM_ADULTS_WALLET)==1);OotCore_MirrorItemGrant(ITEM_ADULTS_WALLET);
    assert(save_wallet_capacity()==200 && CUR_CAPACITY(UPG_WALLET)==200);
    assert(core_item_grants(ITEM_GIANTS_WALLET)==1);OotCore_MirrorItemGrant(ITEM_GIANTS_WALLET);
    assert(save_wallet_capacity()==500 && CUR_CAPACITY(UPG_WALLET)==500);
    assert(core_item_grants(ITEM_BULLET_BAG_50)==1);OotCore_MirrorItemGrant(ITEM_BULLET_BAG_50);
    assert(save_state.ammo_seeds==50 && AMMO(ITEM_SLINGSHOT)==50);
    assert(core_item_grants(ITEM_DEKU_STICK_UPGRADE_20)==1);OotCore_MirrorItemGrant(ITEM_DEKU_STICK_UPGRADE_20);
    assert(save_state.stick_ammo==20 && AMMO(ITEM_DEKU_STICK)==20);
    assert(core_item_grants(ITEM_DEKU_NUT_UPGRADE_40)==1);OotCore_MirrorItemGrant(ITEM_DEKU_NUT_UPGRADE_40);
    assert(save_state.nut_ammo==40 && AMMO(ITEM_DEKU_NUT)==40);
    gSaveContext.save.info.playerData.healthCapacity=save_state.health_capacity;
    gSaveContext.save.info.playerData.health=save_state.health;
    for(int i=0;i<4;++i) { assert(core_item_grants(ITEM_HEART_PIECE)==1);OotCore_MirrorItemGrant(ITEM_HEART_PIECE); }
    assert(save_state.health_capacity==64 && gSaveContext.save.info.playerData.healthCapacity==64);
    assert((save_state.quest_items>>28)==0 && (gSaveContext.save.info.inventory.questItems>>28)==0);
    return 0;
}
''')

    def test_source_purchase_predicates_order_and_route_gates(self):
        source = (OOT / shops.ITEM_SOURCE).read_text(encoding='utf-8')
        names = ('Arrows','Bombs','DekuNuts','DekuSticks','RedPotion','HylianShield','GoronTunic','RecoveryHeart','Bombchus','DekuSeeds','SoldOut')
        self.run_c(self.fixture() + r'''
typedef struct { int basePrice; } EnGirlA;
static int first,child=1;
#define EQUIP_TYPE_TUNIC 2
#define EQUIP_INV_SHIELD_HYLIAN 1
#define EQUIP_INV_TUNIC_GORON 1
#define CHECK_OWNED_EQUIP_ALT(t,v) (gSaveContext.save.info.inventory.equipment&(1u<<((t)*4+(v))))
#define QUEST_GORON_RUBY 19
#define CHECK_QUEST_ITEM(q) (gSaveContext.save.info.inventory.questItems&(1u<<(q)))
#define YEARS_CHILD 5
#define LINK_AGE_IN_YEARS (child?5:17)
static int Item_CheckObtainability(int item) { return first?ITEM_NONE:item; }
static int Inventory_HasEmptyBottle(void) { for(int i=18;i<=21;++i)if(gSaveContext.save.info.inventory.items[i]==ITEM_BOTTLE_EMPTY)return 1;return 0; }
''' + '\n'.join(function(source, 'EnGirlA_CanBuy_' + n) for n in names) + r'''
int main(void) {
    PlayState play={0};EnGirlA stock={30};Inventory* inv=&gSaveContext.save.info.inventory;
    memset(inv->items,255,24);
    assert(EnGirlA_CanBuy_RedPotion(&play,&stock)==CANBUY_RESULT_NEED_BOTTLE);
    inv->items[18]=ITEM_BOTTLE_EMPTY;
    assert(EnGirlA_CanBuy_RedPotion(&play,&stock)==CANBUY_RESULT_NEED_RUPEES);
    gSaveContext.save.info.playerData.rupees=30;first=1;
    assert(EnGirlA_CanBuy_RedPotion(&play,&stock)==CANBUY_RESULT_SUCCESS_FANFARE);
    assert(EnGirlA_CanBuy_Arrows(&play,&stock)==CANBUY_RESULT_CANT_GET_NOW_5);
    assert(EnGirlA_CanBuy_DekuNuts(&play,&stock)==CANBUY_RESULT_SUCCESS_FANFARE);
    assert(EnGirlA_CanBuy_DekuSticks(&play,&stock)==CANBUY_RESULT_SUCCESS_FANFARE);
    assert(EnGirlA_CanBuy_GoronTunic(&play,&stock)==CANBUY_RESULT_CANT_GET_NOW);
    inv->equipment=0x20;gSaveContext.save.info.playerData.rupees=0;
    assert(EnGirlA_CanBuy_HylianShield(&play,&stock)==CANBUY_RESULT_CANT_GET_NOW);
    inv->upgrades=1u<<3;gSaveContext.save.info.playerData.rupees=99;
    assert(EnGirlA_CanBuy_Bombs(&play,&stock)==CANBUY_RESULT_CANT_GET_NOW);
    inv->questItems=1u<<19;AMMO(ITEM_BOMB)=19;
    assert(EnGirlA_CanBuy_Bombs(&play,&stock)==CANBUY_RESULT_SUCCESS);
    AMMO(ITEM_BOMB)=20;assert(EnGirlA_CanBuy_Bombs(&play,&stock)==CANBUY_RESULT_CANT_GET_NOW);
    AMMO(ITEM_BOMBCHU)=50;assert(EnGirlA_CanBuy_Bombchus(&play,&stock)==CANBUY_RESULT_CANT_GET_NOW);
    assert(EnGirlA_CanBuy_DekuSeeds(&play,&stock)==CANBUY_RESULT_CANT_GET_NOW);
    assert(EnGirlA_CanBuy_SoldOut(&play,&stock)==CANBUY_RESULT_CANT_GET_NOW_5);
    return 0;
}
''')

    def test_shop_input_keeps_two_axes_while_descriptions_are_open(self):
        self.run_c(r'''
#include <stdbool.h>
#include <assert.h>
''' + '#include "' + (GAME / 'oot-core/include/oot_core_shop.h').as_posix() + '"\n' + r'''
typedef struct { int interact,cancel,n64_stick_x,n64_stick_y,menu_dx,menu_dy,menu_step,c_up,c_use; } gameplay_input_t;
static struct { OotCoreShopView shop; } draw;
#define CORE_DRAW (&draw)
static int npc_text_opened,busy,held,press,x,y;
static int cdda_busy(void) { return busy; }
static unsigned ocarina(unsigned cmd) { return 0; }
static void set_input(unsigned short h,unsigned short p,signed char sx,signed char sy) { held=h;press=p;x=sx;y=sy; }
static struct { void (*set_input)(unsigned short,unsigned short,signed char,signed char); unsigned (*ocarina)(unsigned); } entry={set_input,ocarina};
#define ENTRY (&entry)
''' + graphics.function(GAME / 'src/oot_core_host.c', 'static void send_input(') + r'''
int main(void) {
    gameplay_input_t in={0};draw.shop.flags=OOT_SHOP_CONTROL;
    in.n64_stick_x=60;in.n64_stick_y=-60;in.interact=1;
    send_input(&in);assert(x==60 && y==-60 && press==0x8000);
    in.n64_stick_x=in.n64_stick_y=0;in.menu_dx=-1;in.menu_dy=-1;npc_text_opened=1;
    send_input(&in);assert(x==-60 && y==60 && !press && !npc_text_opened);
    draw.shop.flags=0;in.menu_step=-1;send_input(&in);assert(!x && y==60);
    busy=1;draw.shop.flags=OOT_SHOP_CONTROL;send_input(&in);assert(!x && !y && !press);
    return 0;
}
''')

    def test_source_fanfare_parent_and_purchase_charge_once(self):
        source = (OOT / shops.KEEPER_SOURCE).read_text(encoding='utf-8')
        girl = (OOT / shops.ITEM_SOURCE).read_text(encoding='utf-8')
        ossan = (OOT / shops.KEEPER_SOURCE).with_suffix('.h').read_text()
        self.run_c(self.fixture() + enum(ossan, 'EnOssanState') + r'''
typedef struct Actor { int params; struct Actor* parent; } Actor;
typedef struct EnGirlA { Actor actor; int getItemId,basePrice;void (*updateStockedItemFunc)(PlayState*,struct EnGirlA*);void (*buyEventFunc)(PlayState*,struct EnGirlA*); } EnGirlA;
typedef struct { Actor actor;int stateFlag,cursorIndex,happyMaskShopState;EnGirlA* shelfSlots[8]; } EnOssan;
typedef int Player;
enum { OSSAN_TYPE_MASK=10,OSSAN_HAPPY_STATE_BORROWED_FIRST_MASK,TEXT_STATE_DONE=4 };
enum { ITEMGETINF_03=3,ITEMGETINF_04,ITEMGETINF_05,ITEMGETINF_06,ITEMGETINF_07,ITEMGETINF_08,ITEMGETINF_09,ITEMGETINF_0A,ITEMGETINF_3F=63 };
static int offers,charges,advance,message_state;
static int Actor_HasParent(Actor* actor,PlayState* play) {return actor->parent!=0;}
static void Actor_OfferGetItem(Actor* actor,PlayState* play,int id,float x,float y) {++offers;}
static void Rupees_ChangeBy(int price) {gSaveContext.save.info.playerData.rupees+=price;++charges;}
static int Message_GetState(void* ctx) {return message_state;}
static int Message_ShouldAdvance(PlayState* play) {return advance;}
static void Message_ContinueTextbox(PlayState* play,int text) {message_state=0;}
static void EnOssan_ResetItemPosition(EnOssan* shop) {}
static void EnOssan_UpdateShopOfferings(EnOssan* shop,PlayState* play) {}
static void EnOssan_EndInteraction(PlayState* play,EnOssan* shop) {}
''' + function(girl, 'EnGirlA_BuyEvent_ObtainBombchuPack') + function(source, 'EnOssan_State_GiveItemWithFanfare') + function(source, 'EnOssan_State_ItemPurchased').replace('&play->msgCtx', '&play->unused') + r'''
int main(void) {
    PlayState play={0};Player player=0;EnOssan shop={0};EnGirlA item={0};Actor parent={0};
    item.actor.params=SI_BOMBCHU_10_1;item.basePrice=100;item.buyEventFunc=EnGirlA_BuyEvent_ObtainBombchuPack;
    shop.shelfSlots[0]=&item;shop.stateFlag=OSSAN_STATE_GIVE_ITEM_FANFARE;
    gSaveContext.save.info.playerData.rupees=150;
    EnOssan_State_GiveItemWithFanfare(&shop,&play,&player);assert(offers==1 && !charges);
    shop.actor.parent=&parent;EnOssan_State_GiveItemWithFanfare(&shop,&play,&player);
    assert(shop.stateFlag==OSSAN_STATE_ITEM_PURCHASED && !shop.actor.parent && !charges);
    EnOssan_State_ItemPurchased(&shop,&play,&player);assert(!charges);
    message_state=TEXT_STATE_DONE;advance=1;EnOssan_State_ItemPurchased(&shop,&play,&player);
    assert(charges==1 && gSaveContext.save.info.playerData.rupees==50 && GET_ITEMGETINF(ITEMGETINF_03));
    assert(shop.stateFlag==OSSAN_STATE_CONTINUE_SHOPPING_PROMPT);
    EnOssan_State_ItemPurchased(&shop,&play,&player);assert(charges==1);
    return 0;
}
''')


if __name__ == '__main__':
    unittest.main()
