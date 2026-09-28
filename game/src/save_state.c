/*
** Persistent quest state. Contract, source references and what is deliberately
** not modelled are all in save_state.h.
*/

#include "save_state.h"

save_state_t    save_state;

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
    return (scene_get(scene, flag, 1));
}

void    save_set_switch(unsigned int scene, unsigned int flag)
{
    scene_set(scene, flag, 1);
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

bool            save_item_give(save_item_t item)
{
    static const uint8_t rupee[3] = { 1, 5, 20 };
    unsigned int    total;

    switch (item) {
    case SAVE_ITEM_RUPEE_GREEN:
    case SAVE_ITEM_RUPEE_BLUE:
    case SAVE_ITEM_RUPEE_RED:
        total = save_state.rupees + rupee[item - SAVE_ITEM_RUPEE_GREEN];
        save_state.rupees = (uint16_t)(total > SAVE_WALLET_CAPACITY ?
                                       SAVE_WALLET_CAPACITY : total);
        return true;
    case SAVE_ITEM_SEEDS_5:
        if (!save_state.slingshot) return false;
        total = save_state.ammo_seeds + 5;
        save_state.ammo_seeds = (uint8_t)(total > 30 ? 30 : total);
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
    default:
        return false;
    }
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

void            save_new_game(void)
{
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
    save_state.ammo_seeds = 0;
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
}

/*
** END OF FILE
*/
