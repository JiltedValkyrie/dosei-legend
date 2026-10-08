#pragma GCC optimize("Os") /* small logic: size over speed (work RAM) */
/* Source: z_en_item00.c Item_DropCollectibleRandom/func_8001F404.
 * This slice is child Link, no bombs/bow/magic yet. No inventory means those
 * drops are suppressed by the original, not replaced with rupees. */
#include "item_drop.h"
#include "item_drop_tables.h"
#include "save_state.h"

int item_drop_filter(unsigned int item)
{
    if (item >= 8 && item <= 10) item = 0x10; /* child: arrows -> seeds */
    if (item == 4 || item == 11 || item == 25 || item == 14 || item == 15)
        return DROP_NONE;
    if (item == 16 && !save_state.slingshot) return DROP_NONE;
    if (item == 3 && save_state.health == save_state.health_capacity) return 0;
    return (int)item;
}

item_drop_t item_drop_random(unsigned int table, unsigned int roll)
{
    item_drop_t result = { DROP_NONE, 0 };
    unsigned int item;
    if (table >= sizeof item_drop_ids / sizeof item_drop_ids[0]) table = 0;
    roll &= 15;
    item = item_drop_ids[table][roll];
    if (item == 0x12) {
        if (save_state.health <= 0x10) {
            result.item = DROP_FAIRY; result.count = 1; return result;
        }
        if (save_state.health <= 0x30) { table = 11; roll = 0; item = 3; }
        else if (save_state.health <= 0x50) { table = 10; roll = 0; item = 3; }
        else if (save_state.ammo_seeds < 6) { table = 10; roll = 0; item = 16; }
        else {
            /* No bomb bag in M3: AMMO(BOMB)=0 selects bombs, then the
             * ownership filter suppresses them, before the rupee branch. */
            table = 13; roll = 0; item = 4;
        }
    }
    result.item = (uint8_t)item_drop_filter(item);
    if (result.item != DROP_NONE) result.count = item_drop_quantities[table][roll];
    return result;
}

bool item_drop_give(unsigned int item)
{
    switch (item) {
    case 0: return save_item_give(SAVE_ITEM_RUPEE_GREEN);
    case 1: return save_item_give(SAVE_ITEM_RUPEE_BLUE);
    case 2: return save_item_give(SAVE_ITEM_RUPEE_RED);
    case 3: return save_item_give(SAVE_ITEM_RECOVERY_HEART);
    case 12: return save_item_give(SAVE_ITEM_DEKU_NUTS_5);
    case 13: return save_item_give(SAVE_ITEM_DEKU_STICK);
    case 16: return save_item_give(SAVE_ITEM_SEEDS_5);
    case DROP_FAIRY: save_heal(0x80); return true;
    default: return false;
    }
}
