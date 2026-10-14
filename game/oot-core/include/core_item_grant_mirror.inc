/* Include in bridge_play.cpp. Successful HOST grants must be visible to the
 * next source actor in the same update. This never calls a host grant again.
 * Original source z_parameter.c Item_Give; host save remains persistent owner.
 */
static void OotCore_MirrorItemGrant(u8 item) {
    Inventory* inv = &gSaveContext.save.info.inventory;
    ItemEquips* equips = &gSaveContext.save.info.equips;
    s32 slot = -1, count = 0, cap = 0;
    if (item == ITEM_ADULTS_WALLET || item == ITEM_GIANTS_WALLET) {
        inv->upgrades = (inv->upgrades & ~(3u << 12)) | ((item - ITEM_ADULTS_WALLET + 1u) << 12);
        return;
    }
    if (item >= ITEM_BULLET_BAG_30 && item <= ITEM_BULLET_BAG_50) {
        inv->upgrades = (inv->upgrades & ~(7u << 14)) | ((item - ITEM_BULLET_BAG_30 + 1u) << 14);
        INV_CONTENT(ITEM_SLINGSHOT) = ITEM_SLINGSHOT;
        AMMO(ITEM_SLINGSHOT) = CUR_CAPACITY(UPG_BULLET_BAG);
        return;
    }
    if (item >= ITEM_DEKU_STICK_UPGRADE_20 && item <= ITEM_DEKU_NUT_UPGRADE_40) {
        u32 level = 2 + ((item - ITEM_DEKU_STICK_UPGRADE_20) & 1);
        if (item <= ITEM_DEKU_STICK_UPGRADE_30) {
            inv->upgrades = (inv->upgrades & ~(7u << 17)) | (level << 17);
            INV_CONTENT(ITEM_DEKU_STICK) = ITEM_DEKU_STICK;
            AMMO(ITEM_DEKU_STICK) = CUR_CAPACITY(UPG_DEKU_STICKS);
        } else {
            inv->upgrades = (inv->upgrades & ~(7u << 20)) | (level << 20);
            INV_CONTENT(ITEM_DEKU_NUT) = ITEM_DEKU_NUT;
            AMMO(ITEM_DEKU_NUT) = CUR_CAPACITY(UPG_DEKU_NUTS);
        }
        return;
    }
    if (item == ITEM_HEART_PIECE || item == ITEM_HEART_PIECE_2) {
        u32 pieces = (inv->questItems >> 28) + 1;
        inv->questItems = (inv->questItems & 0x0fffffffu) | ((pieces & 3u) << 28);
        if (pieces >= 4 && gSaveContext.save.info.playerData.healthCapacity < 0x140) {
            gSaveContext.save.info.playerData.healthCapacity += 0x10;
            gSaveContext.save.info.playerData.health += 0x10;
        }
        return;
    }
    if ((item >= ITEM_BOTTLE_EMPTY && item <= ITEM_BOTTLE_POE) || item == ITEM_MILK) {
        u8 previous = (item == ITEM_BOTTLE_EMPTY || item == ITEM_BOTTLE_MILK_FULL ||
                       item == ITEM_BOTTLE_RUTOS_LETTER) ? ITEM_NONE : ITEM_BOTTLE_EMPTY;
        if (item == ITEM_MILK) item = ITEM_BOTTLE_MILK_FULL;
        for (s32 i = SLOT_BOTTLE_1; i <= SLOT_BOTTLE_4; ++i) if (inv->items[i] == previous) {
            inv->items[i] = item;
            for (s32 button = 1; button <= 3; ++button)
                if (equips->cButtonSlots[button - 1] == i) equips->buttonItems[button] = item;
            return;
        }
        return;
    }
    if (item >= ITEM_WEIRD_EGG && item <= ITEM_SOLD_OUT) {
        inv->items[SLOT_TRADE_CHILD] = item;
        for (s32 button = 1; button <= 3; ++button)
            if (equips->cButtonSlots[button - 1] == SLOT_TRADE_CHILD) equips->buttonItems[button] = item;
        return;
    }
    if (item >= ITEM_SHIELD_DEKU && item <= ITEM_SHIELD_MIRROR) {
        inv->equipment |= 1u << (item - ITEM_SHIELD_DEKU + 4);
        return;
    }
    if (item >= ITEM_TUNIC_KOKIRI && item <= ITEM_TUNIC_ZORA) {
        inv->equipment |= 1u << (item - ITEM_TUNIC_KOKIRI + 8);
        return;
    }
    if (item == ITEM_STRENGTH_GORONS_BRACELET) {
        inv->upgrades = (inv->upgrades & ~(7u << 6)) | (1u << 6);
        return;
    }
    if (item >= ITEM_BOMB_BAG_20 && item <= ITEM_BOMB_BAG_40) {
        u32 level = item - ITEM_BOMB_BAG_20 + 1;
        if (level == 1 && CUR_UPG_VALUE(UPG_BOMB_BAG)) {
            if (AMMO(ITEM_BOMB) < CUR_CAPACITY(UPG_BOMB_BAG)) ++AMMO(ITEM_BOMB);
        } else {
            inv->upgrades = (inv->upgrades & ~(7u << 3)) | (level << 3);
            INV_CONTENT(ITEM_BOMB) = ITEM_BOMB;
            AMMO(ITEM_BOMB) = CUR_CAPACITY(UPG_BOMB_BAG);
        }
        return;
    }
    if (item == ITEM_DEKU_STICK || item == ITEM_DEKU_STICKS_5 || item == ITEM_DEKU_STICKS_10) {
        count = item == ITEM_DEKU_STICK ? 1 : item == ITEM_DEKU_STICKS_5 ? 5 : 10;
        if (INV_CONTENT(ITEM_DEKU_STICK) == ITEM_NONE) {
            inv->upgrades = (inv->upgrades & ~(7u << 17)) | (1u << 17);
            INV_CONTENT(ITEM_DEKU_STICK) = ITEM_DEKU_STICK;
            AMMO(ITEM_DEKU_STICK) = count;
            return;
        }
        slot = SLOT_DEKU_STICK; cap = CUR_CAPACITY(UPG_DEKU_STICKS);
    } else if (item == ITEM_DEKU_NUT || item == ITEM_DEKU_NUTS_5 || item == ITEM_DEKU_NUTS_10) {
        count = item == ITEM_DEKU_NUT ? 1 : item == ITEM_DEKU_NUTS_5 ? 5 : 10;
        if (INV_CONTENT(ITEM_DEKU_NUT) == ITEM_NONE) {
            inv->upgrades = (inv->upgrades & ~(7u << 20)) | (1u << 20);
            INV_CONTENT(ITEM_DEKU_NUT) = ITEM_DEKU_NUT;
            AMMO(ITEM_DEKU_NUT) = item == ITEM_DEKU_NUT ? 1 : AMMO(ITEM_DEKU_NUT) + count;
            return;
        }
        slot = SLOT_DEKU_NUT; cap = CUR_CAPACITY(UPG_DEKU_NUTS);
    } else if (item >= ITEM_BOMBS_5 && item <= ITEM_BOMBS_30) {
        static const u8 refill[] = { 5, 10, 20, 30 };
        slot = SLOT_BOMB; count = refill[item - ITEM_BOMBS_5]; cap = CUR_CAPACITY(UPG_BOMB_BAG);
    } else if (item == ITEM_BOMBCHU || item == ITEM_BOMBCHUS_5 || item == ITEM_BOMBCHUS_20) {
        count = item == ITEM_BOMBCHU ? 10 : item == ITEM_BOMBCHUS_5 ? 5 : 20;
        if (item == ITEM_BOMBCHU && INV_CONTENT(ITEM_BOMBCHU) == ITEM_NONE) AMMO(ITEM_BOMBCHU) = 0;
        INV_CONTENT(ITEM_BOMBCHU) = ITEM_BOMBCHU;
        slot = SLOT_BOMBCHU; cap = 50;
    } else if (item == ITEM_DEKU_SEEDS || item == ITEM_DEKU_SEEDS_30) {
        slot = SLOT_SLINGSHOT; count = item == ITEM_DEKU_SEEDS ? 5 : 30;
        cap = CUR_CAPACITY(UPG_BULLET_BAG);
        SET_ITEMGETINF(ITEMGETINF_13);
    }
    if (slot >= 0) {
        s32 total = inv->ammo[slot] + count;
        inv->ammo[slot] = total > cap ? cap : total;
    }
}
