/* Additional source shop ItemId grants. Include before host_give_item.
 * Return -1 for its existing cases, 0 for unavailable capacity, 1 on grant.
 * Source: z_parameter.c Item_Give. Currency is charged by source EnGirlA.
 */
static int core_item_grants(unsigned char item)
{
    unsigned int i, count, total;
    if ((item >= 0x15 && item <= 0x19) || item == 0x1c || item == 0x1d) {
        /* Potion/fairy/fish/fire/bugs fill an existing empty bottle. */
        for (i = 0; i < 4; ++i) if (save_state.bottle_items[i] == 0x14) {
            save_state.bottle_items[i] = item;
            return 1;
        }
        return 0;
    }
    if (item >= 0x24 && item <= 0x2c) { /* Child masks / sold-out trade slot. */
        save_state.source_items[23] = item;
        return 1;
    }
    switch (item) {
    case 0x56: case 0x57: /* Adult/Giant wallet, source upgrade bits 12..13. */
        save_state.source_upgrades = (save_state.source_upgrades & ~(3u << 12)) | ((item - 0x55u) << 12);
        return 1;
    case 0x47: case 0x48: case 0x49: /* Bullet bags 30/40/50. */
        save_state.source_upgrades = (save_state.source_upgrades & ~(7u << 14)) | ((item - 0x46u) << 14);
        save_state.slingshot = 1;
        save_state.ammo_seeds = (uint8_t)save_seed_capacity();
        return 1;
    case 0x98: case 0x99:
        save_state.stick_owned = 1; save_state.stick_upgrade = item - 0x96;
        save_state.stick_ammo = (item - 0x96) * 10;
        return 1;
    case 0x9a: case 0x9b:
        save_state.nut_owned = 1; save_state.nut_upgrade = item - 0x98;
        save_state.nut_ammo = (item - 0x97) * 10;
        return 1;
    case 0x73: case 0x7a: /* Four source quest nibbles become a heart. */
        count = (save_state.quest_items >> 28) + 1;
        save_state.quest_items = (save_state.quest_items & 0x0fffffffu) | ((count & 3u) << 28);
        if (count >= 4 && save_state.health_capacity < 0x140) {
            save_state.health_capacity += 0x10;
            save_state.health += 0x10;
        }
        return 1;
    case 0x3f: /* Hylian shield. Ownership never auto-equips source gear. */
        save_state.source_equipment |= 0x20;
        return 1;
    case 0x42: case 0x43: /* Goron/Zora tunics; child can-buy rejects these. */
        save_state.source_equipment |= (uint16_t)(1u << (item - 0x41 + 8));
        return 1;
    case 0x95: /* Seeds30, source slingshot capacity. */
        if (!save_state.slingshot) return 0;
        total = save_state.ammo_seeds + 30;
        save_state.ammo_seeds = (uint8_t)(total > save_seed_capacity() ? save_seed_capacity() : total);
        return 1;
    case 0x09: case 0x96: case 0x97: /* Bombchu10/5/20. */
        count = item == 0x09 ? 10u : item == 0x96 ? 5u : 20u;
        total = save_state.source_ammo[8] + count;
        if (item == 0x09 && save_state.source_items[8] == 0xff) total = 10;
        save_state.source_items[8] = 0x09;
        save_state.source_ammo[8] = (uint8_t)(total > 50 ? 50 : total);
        return 1;
    default:
        return -1;
    }
}
