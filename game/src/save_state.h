#ifndef DOSEI_SAVE_STATE_H
#define DOSEI_SAVE_STATE_H
#include <stdbool.h>
#include <stdint.h>

/*
** Persistent quest state: the part of OoT's SaveContext this slice needs.
**
** Deliberately platform free, like gameplay.c and player_input.c: no jo, no
** SGL, integers only. Backup-RAM I/O lives elsewhere (save_file.c) so the host
** tests can drive the whole progression without a Saturn or a BUP device.
**
** This is the file that makes progression possible at all. Before it existed,
** gameplay_reset() wiped everything on every entry to the world, so nothing a
** conversation or a chest did could ever be remembered -- which is why NPCs
** appeared to say quest-dependent lines while the quest never advanced.
**
** Field and accessor names follow the originals so the source trace stays
** obvious. The originals are in the decomp at:
**   include/save.h          -- SaveInfo, SavedSceneFlags, the *_INDEX/_MASK macros
**   src/code/z_actor.c:4891 -- Flags_GetEventChkInf / SetEventChkInf
**   src/code/z_actor.c:4911 -- Flags_GetInfTable / SetInfTable
**   src/code/z_actor.c:707  -- Flags_GetTreasure / SetTreasure
**   src/code/z_sram.c:100   -- Sram_InitNewSave
**
** What is NOT modelled, and stays labelled as missing rather than faked: the
** full 124-scene SavedSceneFlags table (we index a small scene set instead),
** adult equips, dungeon keys, the Triforce/medallion fields, and everything
** after the Kokiri Emerald.
*/

/* ---- flag spaces ---------------------------------------------------------
** All three are bit arrays addressed exactly as the original does it:
** index = flag >> 4, mask = 1 << (flag & 15). Sizes match the original so a
** flag number lifted straight from the decomp can never land out of range.
*/
#define SAVE_EVENTCHKINF_WORDS  14
#define SAVE_ITEMGETINF_WORDS   4
#define SAVE_INFTABLE_WORDS     30

/* ---- event_chk_inf flags used by the opening -----------------------------
** Names and values from include/save.h. Only the ones this slice reads or
** writes are listed; add from the decomp rather than inventing numbers.
*/
#define EVENTCHKINF_MIDO_DENIED_DEKU_TREE_ACCESS    0x02
#define EVENTCHKINF_SARIA_WAS_TOLD_ABOUT_MIDO       0x03
#define EVENTCHKINF_MIDO_STOOD_ASIDE_KOKIRI         0x04  /* EVENTCHKINF_04 */
#define EVENTCHKINF_DEKU_TREE_MOUTH_OPEN            0x05  /* EVENTCHKINF_05 */
#define EVENTCHKINF_ENTERED_BLUE_WARP               0x07  /* EVENTCHKINF_07 */
#define EVENTCHKINF_DEKU_TREE_CLEARED               0x09  /* EVENTCHKINF_09 */
#define EVENTCHKINF_MIDO_STOOD_ASIDE_LOST_WOODS     0x0A  /* EVENTCHKINF_0A */
#define EVENTCHKINF_MET_DEKU_TREE                   0x0C  /* EVENTCHKINF_0C */
#define EVENTCHKINF_MIDO_LEFT_FOR_HIS_HOUSE         0x1C  /* EVENTCHKINF_1C */
#define EVENTCHKINF_BEGAN_GOHMA_BATTLE              0x70
#define EVENTCHKINF_DEKU_TREE_INTRO_CS_SEEN         0xA8

/* ---- inf_table flags (per-NPC conversation memory) ---------------------- */
#define INFTABLE_SARIA_GREETED_LINK                 0x00
#define INFTABLE_SARIA_NOTICED_FAIRY                0x01
#define INFTABLE_SARIA_WAS_TOLD_ABOUT_MIDO          0x03
#define INFTABLE_MIDO_REFUSED_ONCE                  0x0C  /* INFTABLE_0C */
#define INFTABLE_1E                                 0x1E
#define INFTABLE_22                                 0x22
#define INFTABLE_24                                 0x24
#define INFTABLE_26                                 0x26

/* ---- quest items --------------------------------------------------------
** Bit positions within quest_items, from include/save.h QUEST_*.
*/
#define QUEST_KOKIRI_EMERALD    18

/* ---- one-off pickups ----------------------------------------------------
** item_get_inf bits for the slice's two AUTHORED ground pickups. Kokiri
** Forest has no sword or shield lying on the ground in the original -- the
** sword is in the room 2 chest and the shield is bought -- so these bit
** numbers are this slice's own choice, not values lifted from the decomp.
** They live in item_get_inf because that is where OoT keeps "this one-off
** item has been taken", and because they must survive a save and reload:
** without them a loaded file respawns gear the player already collected.
*/
#define ITEMGETINF_GROUND_SWORD     0x00
#define ITEMGETINF_GROUND_SHIELD    0x01

/* ---- equipment ----------------------------------------------------------
** OoT packs equips.equipment as one nibble per EquipType. Mido tests
** CUR_EQUIP_VALUE (what is EQUIPPED), not ALL_EQUIP_VALUE (what is OWNED), so
** the two must stay distinguishable here. See z_en_md.c:437.
*/
#define EQUIP_TYPE_SWORD        0
#define EQUIP_TYPE_SHIELD       1
#define EQUIP_VALUE_SWORD_KOKIRI    1
#define EQUIP_VALUE_SHIELD_DEKU     1

/* ---- scenes -------------------------------------------------------------
** The original carries SavedSceneFlags for all 124 scenes. Our slice visits a
** handful, so we index a small table. These ids are OUR OWN compact numbering,
** not the original SCENE_* values; scene_flow.c maps between them.
*/
#define SAVE_SCENE_KOKIRI_FOREST    0
#define SAVE_SCENE_LOST_WOODS       1
#define SAVE_SCENE_DEKU_TREE        2
#define SAVE_SCENE_DEKU_TREE_BOSS   3
#define SAVE_SCENE_KOKIRI_SHOP      4
#define SAVE_SCENE_LINKS_HOUSE      5
#define SAVE_SCENE_KNOW_IT_ALL_HOUSE 6  /* kokiri_home  */
#define SAVE_SCENE_TWINS_HOUSE      7   /* kokiri_home3 */
#define SAVE_SCENE_MIDOS_HOUSE      8   /* kokiri_home4 */
#define SAVE_SCENE_SARIAS_HOUSE     9   /* kokiri_home5 */
#define SAVE_SCENE_HYRULE_FIELD     10  /* spot00       */
#define SAVE_SCENE_COUNT            11

/* Per-scene flag words, mirroring SavedSceneFlags (include/save.h:96).
** The original keeps a persisted half and a temp half and deliberately does
** NOT save the temp half; that split is preserved -- temp flags live in the
** actor system, not here. */
typedef struct
{
    uint32_t    chest;      /* Flags_GetTreasure / SetTreasure  */
    uint32_t    swch;       /* Flags_GetSwitch  / SetSwitch     */
    uint32_t    clear;      /* Flags_GetClear   / SetClear      */
    uint32_t    collect;    /* Flags_GetCollectible / Set       */
}               save_scene_flags_t;

/* Hearts are stored in OoT's units: 0x10 per heart. A new file is 0x30, three
** hearts (Sram_InitNewSave, z_sram.c). Keeping the original unit means the
** Heart Container and damage values port without a conversion factor. */
#define SAVE_HEART_UNIT             0x10
#define SAVE_NEW_HEALTH_CAPACITY    0x30

typedef struct
{
    uint16_t            event_chk_inf[SAVE_EVENTCHKINF_WORDS];
    uint16_t            item_get_inf[SAVE_ITEMGETINF_WORDS];
    uint16_t            inf_table[SAVE_INFTABLE_WORDS];
    save_scene_flags_t  scene[SAVE_SCENE_COUNT];
    uint32_t            quest_items;
    uint16_t            health;             /* current, in SAVE_HEART_UNIT */
    uint16_t            health_capacity;    /* maximum, in SAVE_HEART_UNIT */
    uint16_t            rupees;
    uint8_t             owned_sword;        /* EQUIP_VALUE_SWORD_*  */
    uint8_t             owned_shield;       /* EQUIP_VALUE_SHIELD_* */
    uint8_t             equip_sword;        /* 0 when nothing equipped */
    uint8_t             equip_shield;
    uint8_t             slingshot;          /* owned flag */
    uint8_t             ammo_seeds;
    uint8_t             scene_id;           /* SAVE_SCENE_*, for resume */
    uint8_t             entrance;           /* spawn point within that scene */
    /* playerData.naviTimer: En_Elf's quest-hint clock, 20 Hz updates. */
    uint16_t            navi_timer;
    /* INV_CONTENT(ITEM_DEKU_STICK) != ITEM_NONE, AMMO(ITEM_DEKU_STICK),
    ** CUR_UPG_VALUE(UPG_DEKU_STICKS): capacity {0, 10, 20, 30}. */
    uint8_t             stick_owned;
    uint8_t             stick_ammo;
    uint8_t             stick_upgrade;
}                       save_state_t;

extern save_state_t     save_state;

/* ---- flag accessors ----------------------------------------------------
** Named after the originals. Out-of-range flags return false / are ignored
** rather than corrupting neighbouring words: a bad flag number is a bug, but
** it must not silently rewrite an unrelated part of the save.
*/
bool    save_get_event_chk_inf(unsigned int flag);
void    save_set_event_chk_inf(unsigned int flag);
bool    save_get_inf_table(unsigned int flag);
void    save_set_inf_table(unsigned int flag);
bool    save_get_item_get_inf(unsigned int flag);
void    save_set_item_get_inf(unsigned int flag);

bool    save_check_quest_item(unsigned int quest_bit);
void    save_give_quest_item(unsigned int quest_bit);

/* Per-scene flags. `scene` is a SAVE_SCENE_* id. */
bool    save_get_treasure(unsigned int scene, unsigned int flag);
void    save_set_treasure(unsigned int scene, unsigned int flag);
bool    save_get_switch(unsigned int scene, unsigned int flag);
void    save_set_switch(unsigned int scene, unsigned int flag);
bool    save_get_clear(unsigned int scene, unsigned int flag);
void    save_set_clear(unsigned int scene, unsigned int flag);
bool    save_get_collectible(unsigned int scene, unsigned int flag);
void    save_set_collectible(unsigned int scene, unsigned int flag);

/* ---- equipment --------------------------------------------------------
** CUR_EQUIP_VALUE vs ALL_EQUIP_VALUE. Mido's gate uses the current one.
*/
unsigned int    save_cur_equip_value(unsigned int equip_type);
unsigned int    save_all_equip_value(unsigned int equip_type);
void            save_give_equip(unsigned int equip_type, unsigned int value);
void            save_set_equip(unsigned int equip_type, unsigned int value);

/* True when Link has the Kokiri Sword AND Deku Shield equipped -- the single
** state check that makes Mido stand aside (z_en_md.c:437). Not a counter of
** his four spoken demands; those are narrative text inside one message. */
bool            save_mido_demands_met(void);

/* ---- health ----------------------------------------------------------- */
void            save_damage(unsigned int units);
/* Sram_OpenSave: where a loaded file resumes. Dungeon -> its entrance 0;
** every other scene (the overworld, the houses) -> Link's house, entrance 0,
** for child Link. Continue after Game Over does NOT go through this. */
void            save_resume_remap(void);
void            save_heal(unsigned int units);
bool            save_is_dead(void);

/* ---- lifecycle -------------------------------------------------------- */
/* Fresh file: three hearts, no items, no flags. Mirrors Sram_InitNewSave. */
void            save_new_game(void);

#endif
