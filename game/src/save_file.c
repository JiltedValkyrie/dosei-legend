#pragma GCC optimize("Os") /* cold menu/save/script code: size over speed (work RAM) */
/*
** Save-file serialisation. Format, and why it is packed by hand rather than
** blitted, are in save_file.h.
*/

#include "save_file.h"
#if defined(__sh__)
typedef char save_summary_low_fits[sizeof(save_state_t) <= RAM_LOW_SAVE_SUMMARY_BYTES ? 1 : -1];
#endif

/* ---- byte cursor -------------------------------------------------------
** A tiny explicit cursor rather than pointer arithmetic sprinkled through
** both directions: pack and unpack then walk the fields in provably the same
** order, which is the one property this file has to get right.
*/
typedef struct
{
    uint8_t         *write;
    const uint8_t   *read;
    unsigned int     at;
}                   cursor;

static void     put8(cursor *c, uint8_t value)
{
    c->write[c->at++] = value;
}

static void     put16(cursor *c, uint16_t value)
{
    put8(c, (uint8_t)(value >> 8));
    put8(c, (uint8_t)(value & 0xFF));
}

static void     put32(cursor *c, uint32_t value)
{
    put16(c, (uint16_t)(value >> 16));
    put16(c, (uint16_t)(value & 0xFFFF));
}

static uint8_t  get8(cursor *c)
{
    return c->read[c->at++];
}

static uint16_t get16(cursor *c)
{
    uint16_t high = get8(c);
    return (uint16_t)((high << 8) | get8(c));
}

static uint32_t get32(cursor *c)
{
    uint32_t high = get16(c);
    return (high << 16) | get16(c);
}

/* ---- checksum ----------------------------------------------------------
** A 16-bit additive checksum with a rotate, which catches the failures a
** backup cartridge actually produces: a dead block reading back as all zeroes
** or all 0xFF, and single flipped bytes. A plain sum would pass an all-zero
** block, so the running value is seeded and rotated.
*/
uint16_t        save_file_checksum(const uint8_t *payload, unsigned int bytes)
{
    uint16_t        sum = 0x5A5A;
    unsigned int    i;

    for (i = 0; i < bytes; ++i) {
        sum = (uint16_t)(sum + payload[i]);
        sum = (uint16_t)((sum << 1) | (sum >> 15));   /* rotate left by one */
    }
    return sum;
}

/* ---- field order -------------------------------------------------------
** Walked identically by pack and unpack. Adding a field means appending here
** AND bumping SAVE_FILE_VERSION and SAVE_FILE_PAYLOAD_BYTES.
*/
static void     pack_payload(const save_state_t *state, cursor *c)
{
    unsigned int    i;

    for (i = 0; i < SAVE_EVENTCHKINF_WORDS; ++i)
        put16(c, state->event_chk_inf[i]);
    for (i = 0; i < SAVE_ITEMGETINF_WORDS; ++i)
        put16(c, state->item_get_inf[i]);
    for (i = 0; i < SAVE_INFTABLE_WORDS; ++i)
        put16(c, state->inf_table[i]);
    for (i = 0; i < SAVE_SCENE_COUNT; ++i) {
        put32(c, state->scene[i].chest);
        put32(c, state->scene[i].swch);
        put32(c, state->scene[i].clear);
        put32(c, state->scene[i].collect);
    }
    put32(c, state->quest_items);
    put16(c, state->health);
    put16(c, state->health_capacity);
    put16(c, state->rupees);
    put8(c, state->owned_sword);
    put8(c, state->owned_shield);
    put8(c, state->equip_sword);
    put8(c, state->equip_shield);
    put8(c, state->slingshot);
    put8(c, state->ammo_seeds);
    put8(c, state->scene_id);
    put8(c, state->entrance);
    /* v3 */
    put8(c, state->stick_owned);
    put8(c, state->stick_ammo);
    put8(c, state->stick_upgrade);
    put16(c, state->navi_timer);
    for (i = 0; i < 3; ++i) put8(c, state->c_items[i]);
    /* v5 */
    put8(c, state->nut_owned);
    put8(c, state->nut_ammo);
    put8(c, state->nut_upgrade);
    put8(c, state->deku_dungeon_items);
    put16(c, state->deku_visited_rooms);
    for(i=0;i<32;++i)put8(c,state->skull_flags[i]);
    put8(c,state->tunic);put8(c,state->fairy_ocarina);
    for(i=0;i<SAVE_SOURCE_SCENE_COUNT;++i) {
        put32(c,state->generic_scene[i].chest);
        put32(c,state->generic_scene[i].swch);
        put32(c,state->generic_scene[i].clear);
        put32(c,state->generic_scene[i].collect);
    }
    for(i=0;i<SAVE_DUNGEON_ITEMS_COUNT;++i)
        put8(c,i==0?(state->deku_dungeon_items&3)<<1:state->dungeon_items[i]);
    for(i=0;i<SAVE_DUNGEON_KEYS_COUNT;++i)put8(c,(uint8_t)state->dungeon_keys[i]);
    put8(c,state->link_age);put16(c,state->day_time);put16(c,state->cutscene_index);
    for(i=0;i<4;++i)put8(c,state->bottle_items[i]);
    put8(c,state->source_scene);put16(c,state->source_entrance);
    for(i=0;i<24;++i)put8(c,state->source_items[i]);
    for(i=0;i<16;++i)put8(c,state->source_ammo[i]);
    put16(c,state->source_equipment);put32(c,state->source_upgrades);
    put8(c,state->source_magic_level);put8(c,state->source_magic);
    put8(c,state->source_double_defense);put8(c,state->source_tokens);
    put8(c,state->boots);
    put32(c,state->total_days);put32(c,state->bgs_day_count);
}

static void     unpack_payload(save_state_t *state, cursor *c, uint16_t version)
{
    unsigned int    i;

    for (i = 0; i < SAVE_EVENTCHKINF_WORDS; ++i)
        state->event_chk_inf[i] = get16(c);
    for (i = 0; i < SAVE_ITEMGETINF_WORDS; ++i)
        state->item_get_inf[i] = get16(c);
    for (i = 0; i < SAVE_INFTABLE_WORDS; ++i)
        state->inf_table[i] = get16(c);
    for (i = 0; i < SAVE_SCENE_COUNT; ++i) {
        state->scene[i].chest = get32(c);
        state->scene[i].swch = get32(c);
        state->scene[i].clear = get32(c);
        state->scene[i].collect = get32(c);
    }
    state->quest_items = get32(c);
    state->health = get16(c);
    state->health_capacity = get16(c);
    state->rupees = get16(c);
    state->owned_sword = get8(c);
    state->owned_shield = get8(c);
    state->equip_sword = get8(c);
    state->equip_shield = get8(c);
    state->slingshot = get8(c);
    state->ammo_seeds = get8(c);
    state->scene_id = get8(c);
    state->entrance = get8(c);
    for (i = 0; i < 3; ++i) state->c_items[i] = 0;
    state->nut_owned = state->nut_ammo = state->nut_upgrade = 0;
    state->deku_dungeon_items = 0;
    state->deku_visited_rooms = 0;
    for(i=0;i<32;++i)state->skull_flags[i]=0;
    state->tunic=state->fairy_ocarina=0;
    save_world_defaults(state);
    if (version < 3) {
        state->stick_owned = state->stick_ammo = state->stick_upgrade = 0;
        state->navi_timer = 0;
        return;
    }
    state->stick_owned = get8(c);
    state->stick_ammo = get8(c);
    state->stick_upgrade = get8(c);
    state->navi_timer = get16(c);
    if (version >= 4)
        for (i = 0; i < 3; ++i) {
            unsigned item = get8(c);
            state->c_items[i] = item <= 4 || (item >= 0x20 && item < 0x38) ? item : 0;
        }
    if (version >= 5) {
        state->nut_owned = get8(c);
        state->nut_ammo = get8(c);
        state->nut_upgrade = get8(c);
    }
    if (version >= 7) state->deku_dungeon_items = get8(c) & 3;
    if (version >= 8) state->deku_visited_rooms = get16(c) & 0x0FFF;
    if(version>=9)for(i=0;i<32;++i)state->skull_flags[i]=get8(c);
    if(version>=10){
        state->tunic=get8(c);state->fairy_ocarina=get8(c)!=0;
    }
    if(version>=11) {
        for(i=0;i<SAVE_SOURCE_SCENE_COUNT;++i) {
            state->generic_scene[i].chest=get32(c);
            state->generic_scene[i].swch=get32(c);
            state->generic_scene[i].clear=get32(c);
            state->generic_scene[i].collect=get32(c);
        }
        for(i=0;i<SAVE_DUNGEON_ITEMS_COUNT;++i)state->dungeon_items[i]=get8(c)&7;
        for(i=0;i<SAVE_DUNGEON_KEYS_COUNT;++i) {
            unsigned n=get8(c);
            state->dungeon_keys[i]=n<=127?(int8_t)n:-1;
        }
        state->link_age=get8(c)!=0;
        state->day_time=get16(c);state->cutscene_index=get16(c);
        for(i=0;i<4;++i) {
            unsigned n=get8(c);
            state->bottle_items[i]=n>=0x14 && n<=0x20?n:0xff;
        }
        state->source_scene=get8(c);state->source_entrance=get16(c);
        if(state->source_scene>=SAVE_SOURCE_SCENE_COUNT)state->source_scene=0xff;
        for(i=0;i<24;++i)state->source_items[i]=get8(c);
        for(i=0;i<16;++i)state->source_ammo[i]=get8(c);
        state->source_equipment=get16(c);state->source_upgrades=get32(c);
        state->source_magic_level=get8(c);state->source_magic=get8(c);
        state->source_double_defense=get8(c)!=0;state->source_tokens=get8(c);
    }
    state->boots=version>=12?get8(c):SAVE_BOOTS_KOKIRI;
    if(version>=13) {
        state->total_days=get32(c);state->bgs_day_count=get32(c);
    }
    if(state->boots>2 || !(state->source_equipment&(0x1000u<<state->boots)) ||
        (state->boots && state->link_age))state->boots=SAVE_BOOTS_KOKIRI;
    {
        unsigned n=0,j;
        for(i=0;i<32;++i)for(j=state->skull_flags[i];j;j>>=1)n+=j&1;
        if(n<state->source_tokens)n=state->source_tokens;
        if(state->tunic>2 || (state->tunic==1 && n<1 && !(state->source_equipment&0x400)) ||
            (state->tunic==2 && n<5 && !(state->source_equipment&0x200)))state->tunic=0;
    }
    state->dungeon_items[0]=(state->deku_dungeon_items&3)<<1;
}

static unsigned int payload_bytes(uint16_t version)
{
    return version == 2 ? SAVE_FILE_V2_PAYLOAD_BYTES :
           version == 3 ? SAVE_FILE_V3_PAYLOAD_BYTES :
           version == 4 ? SAVE_FILE_V4_PAYLOAD_BYTES :
           version < 7 ? SAVE_FILE_V6_PAYLOAD_BYTES :
           version == 7 ? SAVE_FILE_V7_PAYLOAD_BYTES :
           version == 8 ? SAVE_FILE_V8_PAYLOAD_BYTES :
           version == 9 ? SAVE_FILE_V9_PAYLOAD_BYTES :
           version == 10 ? SAVE_FILE_V10_PAYLOAD_BYTES :
           version == 11 ? SAVE_FILE_V11_PAYLOAD_BYTES :
           version == 12 ? SAVE_FILE_V12_PAYLOAD_BYTES : SAVE_FILE_PAYLOAD_BYTES;
}

/* ---- public ------------------------------------------------------------ */

void            save_file_pack(const save_state_t *state, uint8_t *out)
{
    cursor  c;

    c.write = out;
    c.read = 0;
    c.at = 0;
    put8(&c, SAVE_FILE_MAGIC_0);
    put8(&c, SAVE_FILE_MAGIC_1);
    put8(&c, SAVE_FILE_MAGIC_2);
    put8(&c, SAVE_FILE_MAGIC_3);
    put16(&c, SAVE_FILE_VERSION);
    put16(&c, 0);                       /* reserved */
    pack_payload(state, &c);
    put16(&c, save_file_checksum(out + 8, SAVE_FILE_PAYLOAD_BYTES));
}

/* Shared validation, so unpack and read_summary cannot disagree about what
** counts as a good block. */
static save_file_status validate(const uint8_t *in, unsigned int bytes)
{
    uint16_t    version, stored;
    unsigned int payload;

    /* Header first: an older layout is also a different size, and must be
    ** reported as an old version, not as a truncated block. */
    if (!in || bytes < 8)
        return (bytes == 0 ? SAVE_FILE_EMPTY : SAVE_FILE_BAD_SIZE);
    if (in[0] != SAVE_FILE_MAGIC_0 || in[1] != SAVE_FILE_MAGIC_1 ||
        in[2] != SAVE_FILE_MAGIC_2 || in[3] != SAVE_FILE_MAGIC_3) {
        /* A wiped or never-written block reads back uniform. Report that as an
        ** empty slot rather than corruption: it is not an error to have no
        ** save yet, and the file select says different things for the two. */
        unsigned int    i;
        for (i = 0; i < 4; ++i)
            if (in[i] != in[0])
                return (SAVE_FILE_BAD_MAGIC);
        if (in[0] == 0x00 || in[0] == 0xFF)
            return (SAVE_FILE_EMPTY);
        return (SAVE_FILE_BAD_MAGIC);
    }
    version = (uint16_t)((in[4] << 8) | in[5]);
    if (version != SAVE_FILE_VERSION && version != 12 && version != 11 && version != 10 && version != 9 && version != 8 && version != 7 && version != 6 && version != 5 && version != 4 && version != 3 &&
        version != 2)
        return (SAVE_FILE_BAD_VERSION);
    payload = payload_bytes(version);
    if (bytes < 8 + payload + 2)
        return (SAVE_FILE_BAD_SIZE);
    stored = (uint16_t)((in[8 + payload] << 8) | in[8 + payload + 1]);
    if (stored != save_file_checksum(in + 8, payload))
        return (SAVE_FILE_BAD_CHECKSUM);
    return (SAVE_FILE_OK);
}

save_file_status    save_file_unpack(save_state_t *state, const uint8_t *in,
                                     unsigned int bytes)
{
    save_file_status    status = validate(in, bytes);
    cursor              c;

    if (status != SAVE_FILE_OK || !state)
        return (status != SAVE_FILE_OK ? status : SAVE_FILE_BAD_SIZE);
    /* Only now is `state` touched: a refused load must not leave the live quest
    ** state half replaced. */
    c.write = 0;
    c.read = in;
    c.at = 8;
    unpack_payload(state, &c, (uint16_t)((in[4] << 8) | in[5]));
    if (((in[4] << 8) | in[5]) < 6) {
        /* v2-v5 saved forest rupee indices, not source collectible flags.
         * Greens have temporary flags >=32; persistent blues migrate. */
        uint32_t old = state->scene[SAVE_SCENE_KOKIRI_FOREST].collect;
        state->scene[SAVE_SCENE_KOKIRI_FOREST].collect = (old & ~255u) |
            ((old & 0x10) ? 1u<<0x12 : 0) | ((old & 0x20) ? 1u<<0x11 : 0) |
            ((old & 0x40) ? 1u<<0x0F : 0) | ((old & 0x80) ? 1u<<0x0E : 0);
    }
    return (SAVE_FILE_OK);
}

save_file_status    save_file_read_summary(save_file_summary *summary,
                                           const uint8_t *in,
                                           unsigned int bytes)
{
    save_file_status    status;
#if defined(__sh__)
    /* Called synchronously by file-select summaries, never from VBlank. */
    save_state_t *decoded=(save_state_t *)RAM_LOW(RAM_LOW_SAVE_SUMMARY_OFFSET);
#else
    save_state_t decoded_storage;
    save_state_t *decoded=&decoded_storage;
#endif

    if (!summary)
        return (SAVE_FILE_BAD_SIZE);
    summary->present = false;
    summary->hearts = 0;
    summary->hearts_full = 0;
    summary->rupees = 0;
    summary->has_emerald = false;
    summary->deku_tree_cleared = false;
    summary->scene_id = 0;
    status = save_file_unpack(decoded, in, bytes);
    if (status != SAVE_FILE_OK)
        return (status);
    summary->present = true;
    summary->hearts = (uint8_t)(decoded->health_capacity / SAVE_HEART_UNIT);
    summary->hearts_full = (uint8_t)(decoded->health / SAVE_HEART_UNIT);
    summary->rupees = decoded->rupees;
    summary->has_emerald =
        (decoded->quest_items & (1u << QUEST_KOKIRI_EMERALD)) != 0;
    summary->deku_tree_cleared =
        (decoded->event_chk_inf[EVENTCHKINF_DEKU_TREE_CLEARED >> 4] &
         (1u << (EVENTCHKINF_DEKU_TREE_CLEARED & 0xF))) != 0;
    summary->scene_id = decoded->scene_id;
    return (SAVE_FILE_OK);
}

const char         *save_file_status_text(save_file_status status)
{
    switch (status) {
        case SAVE_FILE_OK:              return "OK";
        case SAVE_FILE_EMPTY:           return "NEW FILE";
        case SAVE_FILE_BAD_MAGIC:       return "NOT A DOSEI SAVE";
        case SAVE_FILE_BAD_VERSION:     return "OLDER SAVE - CANNOT READ";
        case SAVE_FILE_BAD_CHECKSUM:    return "SAVE DAMAGED";
        case SAVE_FILE_DEVICE_ERROR:    return "BACKUP READ FAILED";
        default:                        return "SAVE UNREADABLE";
    }
}

/*
** END OF FILE
*/
