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
