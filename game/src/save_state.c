#pragma GCC optimize("Os") /* Flag/inventory bookkeeping: preserve fixed renderer and heap budgets. */
/*
** Persistent quest state. Contract, source references and what is deliberately
** not modelled are all in save_state.h.
*/

#include "save_state.h"
const char *save_scene_name(unsigned scene)
{
    static const char *const names[SAVE_SCENE_COUNT]={"KOKIRI FOREST","LOST WOODS","DEKU TREE","GOHMA'S LAIR",
        "KOKIRI SHOP","LINK'S HOUSE","KNOW-IT-ALL HOUSE","TWINS' HOUSE","MIDO'S HOUSE","SARIA'S HOUSE","HYRULE FIELD"};
    return scene<SAVE_SCENE_COUNT?names[scene]:"UNKNOWN AREA";
}

unsigned save_inventory_item(unsigned slot)
{
    if (slot >= 24) return 0xff;
    if (slot == 0) return save_state.stick_owned ? 0 : 0xff;
    if (slot == 1) return save_state.nut_owned ? 1 : 0xff;
    if (slot == 6) return save_state.slingshot ? 6 : 0xff;
    if (slot == 7) return save_state.source_items[7] == 8 ? 8 :
        save_state.fairy_ocarina ? 7 : 0xff;
    if (slot >= 18 && slot < 22) return save_state.bottle_items[slot - 18];
    return save_state.source_items[slot];
}

unsigned save_c_item_for_slot(unsigned slot)
{
    if (save_inventory_item(slot) == 0xff || !save_inventory_slot_usable(slot)) return 0;
    return slot == 0 ? 1 : slot == 6 ? 2 : slot == 1 ? 3 : slot == 7 ? 4 : 0x20 + slot;
}

bool save_inventory_slot_usable(unsigned slot)
{
    /* z_kaleido_scope.c gSlotAgeReqs: 0 adult, 1 child, 9 unrestricted. */
    static const uint8_t age[24] = {1,9,9,0,0,9,1,9,9,0,0,9,1,9,1,0,0,9,9,9,9,9,0,1};
    return slot < 24 && (age[slot] == 9 || age[slot] == save_state.link_age);
}

void __attribute__((optimize("Os"))) save_set_link_age(unsigned age)
{
    unsigned i;
    save_state.link_age = age ? 1 : 0;
    save_state.owned_sword = save_state.equip_sword = age ? EQUIP_VALUE_SWORD_KOKIRI : EQUIP_VALUE_SWORD_MASTER;
    save_state.owned_shield = save_state.equip_shield = age ? EQUIP_VALUE_SHIELD_DEKU : EQUIP_VALUE_SHIELD_HYLIAN;
    save_state.source_equipment |= age ? 0x11 : 0x22;
    if (age) save_state.boots = SAVE_BOOTS_KOKIRI; /* Iron/Hover: AGE_REQ_ADULT */
    for (i=0;i<3;++i)
        if (!save_inventory_slot_usable(save_c_item_inventory_slot(save_state.c_items[i])))
            save_state.c_items[i] = 0;
}

unsigned save_c_item_inventory_slot(unsigned action)
{
    static const uint8_t legacy[] = {0xff, 0, 6, 1, 7};
    if (action < sizeof(legacy)) return legacy[action];
    return action >= 0x20 && action < 0x38 ? action - 0x20 : 0xff;
}

#if !defined(__sh__)
save_state_t    save_state;
#endif
static uint32_t temporary_switches[SAVE_SCENE_COUNT];
bool save_skull_collected(unsigned group,unsigned mask) {
    return group<32 && (save_state.skull_flags[group]&(mask&255))!=0;
}
bool save_collect_skull(unsigned group,unsigned mask) {
    if(group>=32 || !(mask&255) || save_skull_collected(group,mask))return false;
    save_state.skull_flags[group]|=mask&255;return true;
}
unsigned save_skull_count(void) {
    unsigned i,n=0;for(i=0;i<32;++i){unsigned b=save_state.skull_flags[i];while(b){n+=b&1;b>>=1;}}
    return n<save_state.source_tokens?save_state.source_tokens:n;
}
bool save_tunic_unlocked(unsigned tunic) {
    return tunic==0 || (tunic==1 && ((save_state.source_equipment&0x400) || save_skull_count()>=1)) ||
           (tunic==2 && ((save_state.source_equipment&0x200) || save_skull_count()>=5));
}
bool save_equip_tunic(unsigned tunic) {
    if(!save_tunic_unlocked(tunic))return false;
    save_state.tunic=(uint8_t)tunic;return true;
}

/* The original's addressing, kept verbatim so a flag number copied out of the
** decomp behaves identically here: index = flag >> 4, mask = 1 << (flag & 15).
** (include/save.h EVENTCHKINF_INDEX / EVENTCHKINF_MASK.) */
#define FLAG_INDEX(flag)    ((flag) >> 4)
#define FLAG_MASK(flag)     ((uint16_t)(1u << ((flag) & 0xF)))

static bool     bits_get(const uint16_t *words, unsigned int count,
                         unsigned int flag)
{
    /* A flag past the end of the array is a bug in the caller. Report it as
    ** "not set" rather than reading a neighbouring field: silently wrong
    ** progression is far harder to find than a gate that never opens. */
    if (FLAG_INDEX(flag) >= count)
        return (false);
    return ((words[FLAG_INDEX(flag)] & FLAG_MASK(flag)) != 0);
}

static void     bits_set(uint16_t *words, unsigned int count,
                         unsigned int flag)
{
    if (FLAG_INDEX(flag) >= count)
        return;
    words[FLAG_INDEX(flag)] |= FLAG_MASK(flag);
}

bool            save_get_event_chk_inf(unsigned int flag)
{
    return (bits_get(save_state.event_chk_inf, SAVE_EVENTCHKINF_WORDS, flag));
}

void            save_set_event_chk_inf(unsigned int flag)
{
    bits_set(save_state.event_chk_inf, SAVE_EVENTCHKINF_WORDS, flag);
}

bool            save_get_inf_table(unsigned int flag)
{
    return (bits_get(save_state.inf_table, SAVE_INFTABLE_WORDS, flag));
}

void            save_set_inf_table(unsigned int flag)
{
    bits_set(save_state.inf_table, SAVE_INFTABLE_WORDS, flag);
}

bool            save_get_item_get_inf(unsigned int flag)
{
    return (bits_get(save_state.item_get_inf, SAVE_ITEMGETINF_WORDS, flag));
}

void            save_set_item_get_inf(unsigned int flag)
{
    bits_set(save_state.item_get_inf, SAVE_ITEMGETINF_WORDS, flag);
}

bool            save_check_quest_item(unsigned int quest_bit)
{
    if (quest_bit >= 32)
        return (false);
    return ((save_state.quest_items & (1u << quest_bit)) != 0);
}

void            save_give_quest_item(unsigned int quest_bit)
{
    if (quest_bit < 32)
        save_state.quest_items |= (1u << quest_bit);
}

/* ---- per-scene flags ----------------------------------------------------
** The original's scene flag words are 32 bits and its accessors take flags
** below 0x20 for the persisted half (higher numbers go to the temp half, which
** is not saved and so is not represented here).
*/
static save_scene_flags_t   *scene_of(unsigned int scene)
{
    if (scene >= SAVE_SCENE_COUNT)
        return ((save_scene_flags_t *)0);
    return (&save_state.scene[scene]);
}

static bool     scene_get(unsigned int scene, unsigned int flag,
                          unsigned int field)
{
    const save_scene_flags_t    *s = scene_of(scene);

    if (!s || flag >= 32)
        return (false);
    switch (field) {
        case 0: return ((s->chest   & (1u << flag)) != 0);
        case 1: return ((s->swch    & (1u << flag)) != 0);
        case 2: return ((s->clear   & (1u << flag)) != 0);
        default: return ((s->collect & (1u << flag)) != 0);
    }
}

static void     scene_set(unsigned int scene, unsigned int flag,
                          unsigned int field)
{
    save_scene_flags_t  *s = scene_of(scene);

    if (!s || flag >= 32)
        return;
    switch (field) {
        case 0: s->chest   |= (1u << flag); break;
        case 1: s->swch    |= (1u << flag); break;
        case 2: s->clear   |= (1u << flag); break;
        default: s->collect |= (1u << flag); break;
    }
}

bool    save_get_treasure(unsigned int scene, unsigned int flag)
{
    return (scene_get(scene, flag, 0));
}

void    save_set_treasure(unsigned int scene, unsigned int flag)
{
    scene_set(scene, flag, 0);
}

bool    save_get_switch(unsigned int scene, unsigned int flag)
{
    if (flag >= 32) return scene < SAVE_SCENE_COUNT && flag < 64 &&
        (temporary_switches[scene] & (1u << (flag - 32))) != 0;
    return (scene_get(scene, flag, 1));
}

void    save_set_switch(unsigned int scene, unsigned int flag)
{
    if (flag >= 32) {
        if (scene < SAVE_SCENE_COUNT && flag < 64) temporary_switches[scene] |= 1u << (flag - 32);
        return;
    }
    scene_set(scene, flag, 1);
}

void save_unset_switch(unsigned int scene, unsigned int flag)
{
    if (scene >= SAVE_SCENE_COUNT || flag >= 64) return;
    if (flag >= 32) temporary_switches[scene] &= ~(1u << (flag - 32));
    else save_state.scene[scene].swch &= ~(1u << flag);
}

void save_reset_temp_switches(unsigned int scene)
{
    if (scene < SAVE_SCENE_COUNT) temporary_switches[scene] = 0;
}

void save_room_changed(unsigned int scene)
{
    /* z_actor func_80031B14 clears only temporary flags 0x38..0x3f. */
    if (scene < SAVE_SCENE_COUNT) temporary_switches[scene] &= 0x00ffffffu;
}

bool    save_get_clear(unsigned int scene, unsigned int flag)
{
    return (scene_get(scene, flag, 2));
}

void    save_set_clear(unsigned int scene, unsigned int flag)
{
    scene_set(scene, flag, 2);
}

bool    save_get_collectible(unsigned int scene, unsigned int flag)
{
    return (scene_get(scene, flag, 3));
}

void    save_set_collectible(unsigned int scene, unsigned int flag)
{
    scene_set(scene, flag, 3);
}

/* ---- equipment --------------------------------------------------------- */

unsigned int    save_cur_equip_value(unsigned int equip_type)
{
    if (equip_type == EQUIP_TYPE_SWORD)
        return (save_state.equip_sword);
    if (equip_type == EQUIP_TYPE_SHIELD)
        return (save_state.equip_shield);
    return (0);
}

unsigned int    save_all_equip_value(unsigned int equip_type)
{
    if (equip_type == EQUIP_TYPE_SWORD)
        return (save_state.owned_sword);
    if (equip_type == EQUIP_TYPE_SHIELD)
        return (save_state.owned_shield);
    return (0);
}

void            save_give_equip(unsigned int equip_type, unsigned int value)
{
    if (equip_type == EQUIP_TYPE_SWORD)
        save_state.owned_sword = (uint8_t)value;
    else if (equip_type == EQUIP_TYPE_SHIELD)
        save_state.owned_shield = (uint8_t)value;
}

void            save_set_equip(unsigned int equip_type, unsigned int value)
{
    /* Equipping something not owned is a caller bug; refuse it rather than
    ** letting Mido's gate open on gear Link does not have. */
    if (value != 0 && save_all_equip_value(equip_type) < value)
        return;
    if (equip_type == EQUIP_TYPE_SWORD)
        save_state.equip_sword = (uint8_t)value;
    else if (equip_type == EQUIP_TYPE_SHIELD)
        save_state.equip_shield = (uint8_t)value;
}

bool            save_equip_source(unsigned int equip_type, unsigned int value)
{
    /* z_kaleido_scope.c gEquipAgeReqs rows sword/shield/boots, values 1..3:
    ** 0 adult, 1 child, 9 either. Child Hylian stays refused: the child
    ** model has no Hylian Shield presentation. */
    static const uint8_t age[3][3] = { {1,0,0}, {1,0,0}, {9,0,0} };
    unsigned row = equip_type == EQUIP_TYPE_BOOTS ? 2 : equip_type;
    unsigned bit = (row == 2 ? 12 : row * 4) + value - 1;
    /* Sram_InitNewSave owns Kokiri Boots from the start. */
    if (row > 2 || value < 1 || value > 3 ||
        (!(save_state.source_equipment & (1u << bit)) && bit != 12) ||
        (age[row][value - 1] != 9 && age[row][value - 1] != save_state.link_age))
        return false;
    if (row == 2) save_state.boots = (uint8_t)(value - 1);
    else { save_give_equip(equip_type, value); save_set_equip(equip_type, value); }
    return true;
}

bool            save_mido_demands_met(void)
{
    /* z_en_md.c:437 -- both tests are on CUR_EQUIP_VALUE, so owning the gear
    ** is not enough; it has to be equipped. */
    return (save_cur_equip_value(EQUIP_TYPE_SWORD) == EQUIP_VALUE_SWORD_KOKIRI
         && save_cur_equip_value(EQUIP_TYPE_SHIELD) == EQUIP_VALUE_SHIELD_DEKU);
}

/* ---- health ------------------------------------------------------------ */

void            save_resume_remap(void)
{
    /* Sram_OpenSave restores a dead Game Over save to its source minimum.
     * Game Over writes before its Continue fade gives Link 0x30, so a later
     * file-select load must not begin another death cycle. */
    if (save_state.health < SAVE_NEW_HEALTH_CAPACITY)
        save_state.health = SAVE_NEW_HEALTH_CAPACITY;
    /* Generic scenes use original SceneId to survive scene registration
     * changes. Full source dungeon/boss respawn remapping remains separate. */
    if (save_state.scene_id >= SAVE_SCENE_COUNT &&
        save_state.source_scene < SAVE_SOURCE_SCENE_COUNT) return;
    if (save_state.scene_id == SAVE_SCENE_DEKU_TREE ||
        save_state.scene_id == SAVE_SCENE_DEKU_TREE_BOSS) {
        save_state.scene_id = SAVE_SCENE_DEKU_TREE;
        save_state.entrance = 0;
        return;
    }
    save_state.scene_id = SAVE_SCENE_LINKS_HOUSE;
    save_state.entrance = 0;
}

void            save_damage(unsigned int units)
{
    /* Health_ChangeBy halves a negative amount with arithmetic shift. */
    if (save_state.source_double_defense) units = (units >> 1) + (units & 1);
    if (units >= save_state.health)
        save_state.health = 0;
    else
        save_state.health -= (uint16_t)units;
}

void            save_heal(unsigned int units)
{
    unsigned int    healed = save_state.health + units;

    if (healed > save_state.health_capacity)
        healed = save_state.health_capacity;
    save_state.health = (uint16_t)healed;
}

/* ---- Item_Give --------------------------------------------------------- */

static const uint8_t    stick_capacity[4] = { 0, 10, 20, 30 };
static const uint8_t    nut_capacity[4] = { 0, 20, 30, 40 };
unsigned save_wallet_capacity(void)
{
    static const uint16_t cap[4]={99,200,500,500};
    return cap[(save_state.source_upgrades>>12)&3];
}
unsigned save_seed_capacity(void)
{
    static const uint8_t cap[4]={30,30,40,50};
    return cap[(save_state.source_upgrades>>14)&3];
}

static void             ammo_add(uint8_t *owned, uint8_t *ammo, uint8_t *upgrade,
                                 const uint8_t capacity[4], unsigned int count,
                                 bool set_first)
{
    unsigned int    total;

    if (!*owned) {
        /* INV_CONTENT == ITEM_NONE: Inventory_ChangeUpgrade(.., 1). Source
        ** SETS stick ammo on a first get but ADDS nuts_5/10 without a clamp. */
        *owned = 1;
        if (*upgrade == 0)
            *upgrade = 1;
        total = set_first ? count : *ammo + count;
        *ammo = (uint8_t)(total > 255 ? 255 : total);
        return;
    }
    total = *ammo + count;
    if (total > capacity[*upgrade & 3])
        total = capacity[*upgrade & 3];
    *ammo = (uint8_t)total;
}

/* Human playtest cheat: hearts and every owned consumable to maximum.
** Never grants unowned items or upgrades. */
void            save_cheat_refill(void)
{
    save_state.health = save_state.health_capacity;
    save_state.rupees = save_wallet_capacity();
    if (save_state.stick_owned)
        save_state.stick_ammo = stick_capacity[save_state.stick_upgrade & 3];
    if (save_state.nut_owned)
        save_state.nut_ammo = nut_capacity[save_state.nut_upgrade & 3];
    if (save_state.slingshot)
        save_state.ammo_seeds = save_seed_capacity();
}

/* Test-entry setup is cold; keep it out of hot callers' inline expansion. */
void __attribute__((optimize("Os"))) save_test_max_gear(void)
{
    unsigned i;
    /* Source inventory slots, using upgraded ocarina/longshot. Bottle/trade
     * slots are mutually exclusive: four bottles and final trade/mask variants.
     * C actions still only implement their existing usable-item subset. */
    static const uint8_t items[24]={0,1,2,3,4,5,6,8,9,11,12,13,14,15,16,17,18,19,
        0x14,0x15,0x16,0x17,0x37,0x2b};
    static const uint8_t ammo[16]={30,40,40,50,1,1,50,1,50,1,1,1,1,1,10,1};
    for(i=0;i<24;++i)save_state.source_items[i]=items[i];
    for(i=0;i<16;++i)save_state.source_ammo[i]=ammo[i];
    save_state.source_equipment=0x7777;
    save_state.source_upgrades=0x0036e4db; /* z_inventory source maxima */
    save_state.source_magic_level=2;save_state.source_magic=0x60;
    save_state.source_double_defense=1;save_state.source_tokens=100;
    /* All stones/medallions/songs/agony/card/token bits; no heart-piece count
     * at twenty hearts and no story completion event/inf-table changes. */
    save_state.quest_items=0x00ffffff;
    save_item_give(SAVE_ITEM_SWORD_KOKIRI);
    save_item_give(SAVE_ITEM_SHIELD_DEKU);
    save_item_give(SAVE_ITEM_SLINGSHOT);
    save_set_equip(EQUIP_TYPE_SWORD,EQUIP_VALUE_SWORD_KOKIRI);
    save_set_equip(EQUIP_TYPE_SHIELD,EQUIP_VALUE_SHIELD_DEKU);
    save_state.stick_owned=save_state.nut_owned=1;
    save_state.stick_upgrade=save_state.nut_upgrade=3;
    save_state.fairy_ocarina=1;
    save_state.health_capacity=20*SAVE_HEART_UNIT;
    for(i=0;i<4;++i)save_state.bottle_items[i]=items[18+i];
    save_state.deku_dungeon_items=3;
    save_state.dungeon_items[0]=6; /* legacy compass/map to source bit layout */
    for(i=1;i<SAVE_DUNGEON_ITEMS_COUNT;++i)save_state.dungeon_items[i]=7;
    /* z_sram's debug inventory uses eight keys per slot; this is a useful
     * test quantity, not a new gameplay key cap. Door use still consumes one. */
    for(i=0;i<SAVE_DUNGEON_KEYS_COUNT;++i)save_state.dungeon_keys[i]=8;
    save_cheat_refill();
}

bool            save_item_give(save_item_t item)
{
    static const uint8_t rupee[3] = { 1, 5, 20 };
    unsigned int    total;

    switch (item) {
    case SAVE_ITEM_HEART_CONTAINER:
        if (save_state.health_capacity < 20 * SAVE_HEART_UNIT)
            save_state.health_capacity += SAVE_HEART_UNIT;
        save_heal(SAVE_HEART_UNIT);
        return true;
    case SAVE_ITEM_SLINGSHOT:
        save_state.slingshot = 1;
        save_state.ammo_seeds = save_seed_capacity();
        return true;
    case SAVE_ITEM_DEKU_MAP:
        save_state.deku_dungeon_items |= 2;
        return true;
    case SAVE_ITEM_DEKU_COMPASS:
        save_state.deku_dungeon_items |= 1;
        return true;
    case SAVE_ITEM_RUPEE_GREEN:
    case SAVE_ITEM_RUPEE_BLUE:
    case SAVE_ITEM_RUPEE_RED:
        total = save_state.rupees + rupee[item - SAVE_ITEM_RUPEE_GREEN];
        save_state.rupees = (uint16_t)(total > save_wallet_capacity() ?
                                       save_wallet_capacity() : total);
        return true;
    case SAVE_ITEM_SEEDS_5:
        if (!save_state.slingshot) return false;
        total = save_state.ammo_seeds + 5;
        save_state.ammo_seeds = (uint8_t)(total > save_seed_capacity() ? save_seed_capacity() : total);
        return true;
    case SAVE_ITEM_RECOVERY_HEART:
        save_heal(SAVE_HEART_UNIT);     /* Health_ChangeBy(play, 0x10) */
        return true;
    case SAVE_ITEM_DEKU_STICK:
    case SAVE_ITEM_DEKU_STICKS_5:
    case SAVE_ITEM_DEKU_STICKS_10:
        ammo_add(&save_state.stick_owned, &save_state.stick_ammo,
                 &save_state.stick_upgrade, stick_capacity,
                 item == SAVE_ITEM_DEKU_STICK ? 1 : item == SAVE_ITEM_DEKU_STICKS_5 ? 5 : 10,
                 true);
        return true;
    case SAVE_ITEM_DEKU_NUT:
    case SAVE_ITEM_DEKU_NUTS_5:
    case SAVE_ITEM_DEKU_NUTS_10:
        /* First single nut: AMMO = ITEM_DEKU_NUT (1). */
        ammo_add(&save_state.nut_owned, &save_state.nut_ammo,
                 &save_state.nut_upgrade, nut_capacity,
                 item == SAVE_ITEM_DEKU_NUT ? 1 : item == SAVE_ITEM_DEKU_NUTS_5 ? 5 : 10,
                 item == SAVE_ITEM_DEKU_NUT);
        return true;
    case SAVE_ITEM_SWORD_KOKIRI:
        save_give_equip(EQUIP_TYPE_SWORD, EQUIP_VALUE_SWORD_KOKIRI);
        return true;
    case SAVE_ITEM_SHIELD_DEKU:
        save_give_equip(EQUIP_TYPE_SHIELD, EQUIP_VALUE_SHIELD_DEKU);
        return true;
    case SAVE_ITEM_BOTTLE_POE:
    case SAVE_ITEM_BOTTLE_BIG_POE:
        for(total=0;total<4;++total)
            if(save_state.bottle_items[total]==0x14) {
                save_state.bottle_items[total]=item==SAVE_ITEM_BOTTLE_POE?0x20:0x1e;
                return true;
            }
        return false;
    case SAVE_ITEM_BOTTLE_EMPTY:
    case SAVE_ITEM_BOTTLE_MILK_FULL:
    case SAVE_ITEM_MILK:
        /* z_parameter Item_Give: milk refill consumes an empty bottle;
         * Talon's first reward adds a new bottle in an unowned slot. */
        for(total=0;total<4;++total)
            if(save_state.bottle_items[total]==(item==SAVE_ITEM_MILK?0x14:0xff)) {
                save_state.bottle_items[total]=item==SAVE_ITEM_BOTTLE_EMPTY?0x14:0x1a;
                return true;
            }
        return false;
    default:
        return false;
    }
}

bool save_finish_deku_warp(void)
{
    if (save_state.scene_id != SAVE_SCENE_DEKU_TREE_BOSS ||
        !save_get_clear(SAVE_SCENE_DEKU_TREE_BOSS, 1)) return false;
    save_set_event_chk_inf(EVENTCHKINF_ENTERED_BLUE_WARP);
    save_set_event_chk_inf(EVENTCHKINF_DEKU_TREE_CLEARED);
    save_give_quest_item(QUEST_KOKIRI_EMERALD);
    return true;
}

bool            save_item_first_get(save_item_t item)
{
    switch (item) {
    case SAVE_ITEM_DEKU_STICK: case SAVE_ITEM_DEKU_STICKS_5: case SAVE_ITEM_DEKU_STICKS_10:
        return !save_state.stick_owned;
    case SAVE_ITEM_DEKU_NUT: case SAVE_ITEM_DEKU_NUTS_5: case SAVE_ITEM_DEKU_NUTS_10:
        return !save_state.nut_owned;
    case SAVE_ITEM_SWORD_KOKIRI:
        return save_all_equip_value(EQUIP_TYPE_SWORD) != EQUIP_VALUE_SWORD_KOKIRI;
    case SAVE_ITEM_SHIELD_DEKU:
        return save_all_equip_value(EQUIP_TYPE_SHIELD) != EQUIP_VALUE_SHIELD_DEKU;
    default:
        return false;                   /* rupees/hearts are never ITEM_NONE */
    }
}

save_canbuy_t   save_item_can_buy(save_item_t item, unsigned int price)
{
    bool            full;

    switch (item) {
    case SAVE_ITEM_DEKU_STICK:
        full = save_state.stick_owned &&
               save_state.stick_ammo >= stick_capacity[save_state.stick_upgrade & 3];
        break;
    case SAVE_ITEM_DEKU_NUTS_5:
    case SAVE_ITEM_DEKU_NUTS_10:
        full = save_state.nut_owned &&
               save_state.nut_ammo >= nut_capacity[save_state.nut_upgrade & 3];
        break;
    case SAVE_ITEM_SHIELD_DEKU:
        full = !save_item_first_get(item);
        break;
    case SAVE_ITEM_RECOVERY_HEART:
        /* No fanfare branch in EnGirlA_CanBuy_RecoveryHeart. */
        if (save_state.health_capacity == save_state.health)
            return SAVE_CANBUY_CANT_GET_NOW;
        return save_state.rupees < price ? SAVE_CANBUY_NEED_RUPEES : SAVE_CANBUY_SUCCESS;
    default:
        return SAVE_CANBUY_CANT_GET_NOW;  /* not a Kokiri shop item */
    }
    if (full)
        return SAVE_CANBUY_CANT_GET_NOW;
    if (save_state.rupees < price)
        return SAVE_CANBUY_NEED_RUPEES;
    return save_item_first_get(item) ? SAVE_CANBUY_SUCCESS_FANFARE : SAVE_CANBUY_SUCCESS;
}

save_canbuy_t   save_item_buy(save_item_t item, unsigned int price)
{
    save_canbuy_t   result = save_item_can_buy(item, price);

    if (result == SAVE_CANBUY_SUCCESS || result == SAVE_CANBUY_SUCCESS_FANFARE) {
        /* EnGirlA_ItemGive_*: Item_Give, then Rupees_ChangeBy(-price). */
        save_item_give(item);
        save_state.rupees = (uint16_t)(save_state.rupees - price);
    }
    return result;
}

bool            save_is_dead(void)
{
    return (save_state.health == 0);
}

/* ---- lifecycle --------------------------------------------------------- */

void save_world_defaults(save_state_t *state)
{
    unsigned i;
    for(i=0;i<SAVE_SOURCE_SCENE_COUNT;++i)
        state->generic_scene[i]=(save_scene_flags_t){0};
    for(i=0;i<SAVE_DUNGEON_ITEMS_COUNT;++i)state->dungeon_items[i]=0;
    for(i=0;i<SAVE_DUNGEON_KEYS_COUNT;++i)state->dungeon_keys[i]=-1;
    state->link_age=1;
    state->day_time=0x8000;
    state->cutscene_index=0;
    for(i=0;i<4;++i)state->bottle_items[i]=0xff;
    state->source_scene=0xff;state->source_entrance=0xffff;
    for(i=0;i<24;++i)state->source_items[i]=0xff;
    for(i=0;i<16;++i)state->source_ammo[i]=0;
    state->source_equipment=0;state->source_upgrades=0;
    state->source_magic_level=state->source_magic=state->source_double_defense=state->source_tokens=0;
    state->total_days=state->bgs_day_count=0;
    state->ocarina_game_round=0;
}

void            save_new_game(void)
{
    unsigned int scene;
    for (scene=0;scene<SAVE_SCENE_COUNT;++scene) temporary_switches[scene]=0;
    unsigned int    i;

    for (i = 0; i < SAVE_EVENTCHKINF_WORDS; ++i)
        save_state.event_chk_inf[i] = 0;
    for (i = 0; i < SAVE_ITEMGETINF_WORDS; ++i)
        save_state.item_get_inf[i] = 0;
    for (i = 0; i < SAVE_INFTABLE_WORDS; ++i)
        save_state.inf_table[i] = 0;
    for (i = 0; i < SAVE_SCENE_COUNT; ++i) {
        save_state.scene[i].chest = 0;
        save_state.scene[i].swch = 0;
        save_state.scene[i].clear = 0;
        save_state.scene[i].collect = 0;
    }
    save_state.quest_items = 0;
    /* Sram_InitNewSave: three hearts, full. */
    save_state.health_capacity = SAVE_NEW_HEALTH_CAPACITY;
    save_state.health = SAVE_NEW_HEALTH_CAPACITY;
    save_state.rupees = 0;
    save_state.owned_sword = 0;
    save_state.owned_shield = 0;
    save_state.equip_sword = 0;
    save_state.equip_shield = 0;
    save_state.slingshot = 0;
    save_state.tunic = save_state.fairy_ocarina = save_state.boots = 0;
    save_state.ammo_seeds = 0;
    save_state.deku_dungeon_items = 0;
    save_state.deku_visited_rooms = 0;
    for(i=0;i<32;++i)save_state.skull_flags[i]=0;
    save_state.stick_owned = 0;
    save_state.stick_ammo = 0;
    save_state.stick_upgrade = 0;
    save_state.nut_owned = save_state.nut_ammo = save_state.nut_upgrade = 0;
    for (i = 0; i < 3; ++i) save_state.c_items[i] = 0;
    save_state.navi_timer = 0;
    /* A new file begins in Link's house, in bed, exactly as the original does.
    ** Spawn 0 of that scene is the bed, straight from the ROM's spawn list.
    ** Recorded here rather than in the caller so the resume path and the
    ** new-game path agree about where a file starts. */
    save_state.scene_id = SAVE_SCENE_LINKS_HOUSE;
    save_state.entrance = 0;
    save_world_defaults(&save_state);
}

/*
** END OF FILE
*/
