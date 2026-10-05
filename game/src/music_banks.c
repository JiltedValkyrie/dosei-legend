#pragma GCC optimize("Os") /* state logic, not draw loops: size over speed (work RAM) */
/*
** Bank definitions. Both generated score headers declare the same sample and
** trigger layouts, which is what lets the player point straight at their
** tables instead of copying them; the casts below rely on that and would break
** loudly if a future score changed shape.
*/

#include <jo/jo.h>
#include "music_banks.h"
#include "title_score.h"
#include "kokiri_score.h"
#include "navi_score.h"
#include "deku_tree_score.h"
#include "nightmare_score.h"
#include "house_score.h"
#include "shop_score.h"
#include "dungeon_score.h"
#include "woods_score.h"
#include "fairy_score.h"
#include "boss_score.h"
#include "bossclear_score.h"
#include "owl_score.h"
#include "fairyget_score.h"
#include "field_score.h"
#include "stone_score.h"

/* Trigger tables live on the cart (MUSICTRG.BIN, BUG-043); these copies in
** the headers are unreferenced and dropped. */
#pragma GCC diagnostic ignored "-Wunused-const-variable"
typedef char music_trigger_is_8_bytes[sizeof(music_trigger_t) == 8 ? 1 : -1];

static music_bank_t *const banks[] = {
    &music_bank_title, &music_bank_kokiri, &music_bank_navi,
    &music_bank_deku_tree, &music_bank_nightmare, &music_bank_house, &music_bank_shop, &music_bank_dungeon, &music_bank_woods, &music_bank_fairy, &music_bank_boss, &music_bank_bossclear, &music_bank_owl, &music_bank_fairyget, &music_bank_field, &music_bank_stone
};
static const unsigned int counts[] = {
    TITLE_TRIGGER_COUNT, KOKIRI_TRIGGER_COUNT, NAVI_TRIGGER_COUNT,
    DEKU_TREE_TRIGGER_COUNT, NIGHTMARE_TRIGGER_COUNT, HOUSE_TRIGGER_COUNT, SHOP_TRIGGER_COUNT, DUNGEON_TRIGGER_COUNT, WOODS_TRIGGER_COUNT, FAIRY_TRIGGER_COUNT, BOSS_TRIGGER_COUNT, BOSSCLEAR_TRIGGER_COUNT, OWL_TRIGGER_COUNT, FAIRYGET_TRIGGER_COUNT, FIELD_TRIGGER_COUNT, STONE_TRIGGER_COUNT
};
#define BANK_COUNT (sizeof(banks) / sizeof(banks[0]))

music_bank_t music_bank_title = {
    "TITLE.PCM", "TITLE.LVL",
    (const music_pcm_t *)title_pcm, 0,
    TITLE_TRIGGER_COUNT, TITLE_FRAMES, TITLE_LOOP_FRAME, TITLE_VOICES,
    TITLE_SAMPLE_BASE, TITLE_PCM_BYTES, TITLE_FRAMES * TITLE_VOICES
};

music_bank_t music_bank_kokiri = {
    "FOREST.PCM", "FOREST.LVL",
    (const music_pcm_t *)kokiri_pcm, 0,
    KOKIRI_TRIGGER_COUNT, KOKIRI_FRAMES, KOKIRI_LOOP_FRAME, KOKIRI_VOICES,
    KOKIRI_SAMPLE_BASE, KOKIRI_PCM_BYTES, KOKIRI_LEVEL_BYTES
};

/*
** The opening cutscenes' cues, named by the cutscenes' own CS_START_SEQ
** commands. These are one-pass cues rather than area themes, so they loop from
** the top: a beat that outlives its cue repeats instead of falling silent.
**
*/
music_bank_t music_bank_navi = {
    "CSNAVI.PCM", "CSNAVI.LVL",
    (const music_pcm_t *)navi_pcm, 0,
    NAVI_TRIGGER_COUNT, NAVI_FRAMES, NAVI_LOOP_FRAME, NAVI_VOICES,
    NAVI_SAMPLE_BASE, NAVI_PCM_BYTES, NAVI_LEVEL_BYTES
};

music_bank_t music_bank_deku_tree = {
    "CSDEKU.PCM", "CSDEKU.LVL",
    (const music_pcm_t *)deku_tree_pcm,
    0,
    DEKU_TREE_TRIGGER_COUNT, DEKU_TREE_FRAMES, DEKU_TREE_LOOP_FRAME,
    DEKU_TREE_VOICES, DEKU_TREE_SAMPLE_BASE, DEKU_TREE_PCM_BYTES,
    DEKU_TREE_LEVEL_BYTES
};

music_bank_t music_bank_nightmare = {
    "CSGANON.PCM", "CSGANON.LVL",
    (const music_pcm_t *)nightmare_pcm, 0,
    NIGHTMARE_TRIGGER_COUNT, NIGHTMARE_FRAMES, NIGHTMARE_LOOP_FRAME,
    NIGHTMARE_VOICES, NIGHTMARE_SAMPLE_BASE, NIGHTMARE_PCM_BYTES, NIGHTMARE_LEVEL_BYTES
};

music_bank_t music_bank_house = {
    "HOUSE.PCM", "HOUSE.LVL", (const music_pcm_t *)house_pcm, 0,
    HOUSE_TRIGGER_COUNT, HOUSE_FRAMES, HOUSE_LOOP_FRAME, HOUSE_VOICES,
    HOUSE_SAMPLE_BASE, HOUSE_PCM_BYTES, HOUSE_LEVEL_BYTES
};
music_bank_t music_bank_shop = {
    "SHOP.PCM", "SHOP.LVL", (const music_pcm_t *)shop_pcm, 0,
    SHOP_TRIGGER_COUNT, SHOP_FRAMES, SHOP_LOOP_FRAME, SHOP_VOICES,
    SHOP_SAMPLE_BASE, SHOP_PCM_BYTES, SHOP_LEVEL_BYTES
};

/* MUSICTRG.BIN (tools/build_cart_tables.py): 'KTRG', u16 bank count, u16
** count per bank, then the triggers in music_trigger_t layout. Any mismatch
** leaves every bank with no triggers: silent music, never a bad read. */
bool music_banks_bind(const uint8_t *blob, uint32_t bytes)
{
    unsigned int i, offset = 6 + 2 * BANK_COUNT;
    for (i = 0; i < BANK_COUNT; ++i) { banks[i]->triggers = 0; banks[i]->trigger_count = 0; }
    if (!blob || bytes < offset || blob[0] != 'K' || blob[1] != 'T' ||
        blob[2] != 'R' || blob[3] != 'G' ||
        ((blob[4] << 8) | blob[5]) != BANK_COUNT)
        return false;
    for (i = 0; i < BANK_COUNT; ++i)
        if (((unsigned int)(blob[6 + 2 * i] << 8) | blob[7 + 2 * i]) != counts[i])
            return false;
    {
        unsigned int total = offset;
        for (i = 0; i < BANK_COUNT; ++i) total += counts[i] * 8;
        if (total != bytes) return false;
    }
    for (i = 0; i < BANK_COUNT; ++i) {
        banks[i]->triggers = (const music_trigger_t *)(blob + offset);
        banks[i]->trigger_count = counts[i];
        offset += counts[i] * 8;
    }
    return true;
}

music_bank_t music_bank_dungeon = {
    "DUNGEON.PCM", "DUNGEON.LVL", (const music_pcm_t *)dungeon_pcm, 0,
    DUNGEON_TRIGGER_COUNT, DUNGEON_FRAMES, DUNGEON_LOOP_FRAME, DUNGEON_VOICES,
    DUNGEON_SAMPLE_BASE, DUNGEON_PCM_BYTES, DUNGEON_LEVEL_BYTES
};

music_bank_t music_bank_woods = {
    "WOODS.PCM", "WOODS.LVL", (const music_pcm_t *)woods_pcm, 0,
    WOODS_TRIGGER_COUNT, WOODS_FRAMES, WOODS_LOOP_FRAME, WOODS_VOICES,
    WOODS_SAMPLE_BASE, WOODS_PCM_BYTES, WOODS_LEVEL_BYTES
};

music_bank_t music_bank_fairy = {
    "FAIRY.PCM", "FAIRY.LVL", (const music_pcm_t *)fairy_pcm, 0,
    FAIRY_TRIGGER_COUNT, FAIRY_FRAMES, FAIRY_LOOP_FRAME, FAIRY_VOICES,
    FAIRY_SAMPLE_BASE, FAIRY_PCM_BYTES, FAIRY_LEVEL_BYTES
};

music_bank_t music_bank_boss = {
    "BOSS.PCM", "BOSS.LVL", (const music_pcm_t *)boss_pcm, 0,
    BOSS_TRIGGER_COUNT, BOSS_FRAMES, BOSS_LOOP_FRAME, BOSS_VOICES,
    BOSS_SAMPLE_BASE, BOSS_PCM_BYTES, BOSS_LEVEL_BYTES
};

music_bank_t music_bank_bossclear = {
    "BOSSCLR.PCM", "BOSSCLR.LVL", (const music_pcm_t *)bossclear_pcm, 0,
    BOSSCLEAR_TRIGGER_COUNT, BOSSCLEAR_FRAMES, BOSSCLEAR_LOOP_FRAME, BOSSCLEAR_VOICES,
    BOSSCLEAR_SAMPLE_BASE, BOSSCLEAR_PCM_BYTES, BOSSCLEAR_LEVEL_BYTES
};

music_bank_t music_bank_owl = {
    "OWL.PCM", "OWL.LVL", (const music_pcm_t *)owl_pcm, 0,
    OWL_TRIGGER_COUNT, OWL_FRAMES, OWL_LOOP_FRAME, OWL_VOICES, OWL_SAMPLE_BASE, OWL_PCM_BYTES, OWL_LEVEL_BYTES
};

music_bank_t music_bank_fairyget = {
    "FAIRYGET.PCM", "FAIRYGET.LVL", (const music_pcm_t *)fairyget_pcm, 0,
    FAIRYGET_TRIGGER_COUNT, FAIRYGET_FRAMES, FAIRYGET_LOOP_FRAME, FAIRYGET_VOICES, FAIRYGET_SAMPLE_BASE, FAIRYGET_PCM_BYTES, FAIRYGET_LEVEL_BYTES
};

music_bank_t music_bank_field = {
    "FIELD.PCM", "FIELD.LVL", (const music_pcm_t *)field_pcm, 0,
    FIELD_TRIGGER_COUNT, FIELD_FRAMES, FIELD_LOOP_FRAME, FIELD_VOICES, FIELD_SAMPLE_BASE, FIELD_PCM_BYTES, FIELD_LEVEL_BYTES
};

music_bank_t music_bank_stone = {
    "STONE.PCM", "STONE.LVL", (const music_pcm_t *)stone_pcm, 0,
    STONE_TRIGGER_COUNT, STONE_FRAMES, STONE_LOOP_FRAME, STONE_VOICES, STONE_SAMPLE_BASE, STONE_PCM_BYTES, STONE_LEVEL_BYTES
};
