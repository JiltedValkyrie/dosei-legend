/* Host adapter for save_file.c and save_state.c.
**
** Both files are platform free, so nothing here stands in for the Saturn. These
** are only conveniences the test cannot express through ctypes directly:
** operating on the single live `save_state`, and reducing it to one number so a
** round trip can be asserted without reading 200 bytes field by field. */
#include <stdint.h>
#include "../../src/save_file.h"

void sf_pack(unsigned char *out)
{
    save_file_pack(&save_state, out);
}

int sf_unpack(const unsigned char *in, unsigned int bytes)
{
    return (int)save_file_unpack(&save_state, in, bytes);
}

int sf_summary(save_file_summary *summary, const unsigned char *in,
               unsigned int bytes)
{
    return (int)save_file_read_summary(summary, in, bytes);
}

/* Fields with no setter of their own in save_state.h, needed to make a test
** save distinguishable. */
void sf_set_rupees(int rupees)
{
    save_state.rupees = (uint16_t)rupees;
}

void sf_set_scene(int scene, int entrance)
{
    save_state.scene_id = (uint8_t)scene;
    save_state.entrance = (uint8_t)entrance;
}

void sf_set_sticks(int owned, int ammo, int upgrade, int timer)
{
    save_state.stick_owned = (uint8_t)owned;
    save_state.stick_ammo = (uint8_t)ammo;
    save_state.stick_upgrade = (uint8_t)upgrade;
    save_state.navi_timer = (uint16_t)timer;
}

int sf_stick_ammo(void) { return save_state.stick_ammo; }
int sf_stick_upgrade(void) { return save_state.stick_upgrade; }
int sf_navi_timer(void) { return save_state.navi_timer; }
void sf_set_health(int health, int capacity)
{
    save_state.health = (uint16_t)health;
    save_state.health_capacity = (uint16_t)capacity;
}
int sf_health(void) { return save_state.health; }
void sf_set_days(unsigned total,unsigned bgs) { save_state.total_days=total;save_state.bgs_day_count=bgs; }
unsigned sf_total_days(void) { return save_state.total_days; }
unsigned sf_bgs_day_count(void) { return save_state.bgs_day_count; }
void sf_resume_remap(void) { save_resume_remap(); }
unsigned int sf_checksum(const unsigned char *p, unsigned int n) { return save_file_checksum(p, n); }

unsigned int sf_quest_items(void)
{
    return save_state.quest_items;
}

/* One number that changes if ANY byte of the quest state changes. Built from
** the serialiser itself, so a field the packer forgets is a field this cannot
** see -- which is why the round-trip tests also assert individual gates. */
unsigned int sf_fingerprint(void)
{
    unsigned char   block[SAVE_FILE_BYTES];

    save_file_pack(&save_state, block);
    return (unsigned int)save_file_checksum(block + 8, SAVE_FILE_PAYLOAD_BYTES);
}

void sf_set_c_item(int slot, int item) { save_state.c_items[slot] = item; }
int sf_c_item(int slot) { return save_state.c_items[slot]; }
void sf_set_nuts(int owned, int ammo, int upgrade)
{
    save_state.nut_owned = owned;
    save_state.nut_ammo = ammo;
    save_state.nut_upgrade = upgrade;
}
int sf_nut_ammo(void) { return save_state.nut_owned * 1000 + save_state.nut_ammo * 10 + save_state.nut_upgrade; }

int sf_tunic(void){return save_state.tunic;}
int sf_ocarina(void){return save_state.fairy_ocarina;}
void sf_ocarina_give(void){save_state.fairy_ocarina=1;}
int sf_tunic_equip(int value){return save_equip_tunic(value);}
void sf_skull_set(int bank,int mask){save_state.skull_flags[bank]=mask;}

void sf_set_world(void)
{
    unsigned i;
    for(i=0;i<SAVE_SOURCE_SCENE_COUNT;++i) {
        save_state.generic_scene[i].chest=1u<<(i%32);
        save_state.generic_scene[i].swch=0x11223300u+i;
        save_state.generic_scene[i].clear=0x88776600u+i;
        save_state.generic_scene[i].collect=0x44332200u+i;
    }
    for(i=1;i<SAVE_DUNGEON_ITEMS_COUNT;++i)save_state.dungeon_items[i]=i&7;
    for(i=0;i<SAVE_DUNGEON_KEYS_COUNT;++i)save_state.dungeon_keys[i]=(int)i-1;
    save_state.link_age=0;save_state.day_time=0x1234;save_state.cutscene_index=0xfff3;
    for(i=0;i<4;++i)save_state.bottle_items[i]=0x14+i;
    save_state.source_scene=99;save_state.source_entrance=0x345;
    for(i=0;i<24;++i)save_state.source_items[i]=i;
    for(i=0;i<16;++i)save_state.source_ammo[i]=i+1;
    save_state.source_equipment=0x7777;save_state.source_upgrades=0x36e4db;
    save_state.source_magic_level=2;save_state.source_magic=96;
    save_state.source_double_defense=1;save_state.source_tokens=100;
}

int sf_world_defaults(void)
{
    unsigned i;
    for(i=0;i<SAVE_SOURCE_SCENE_COUNT;++i) {
        const save_scene_flags_t *s=&save_state.generic_scene[i];
        if(s->chest || s->swch || s->clear || s->collect)return 0;
    }
    for(i=1;i<SAVE_DUNGEON_ITEMS_COUNT;++i)if(save_state.dungeon_items[i])return 0;
    for(i=0;i<SAVE_DUNGEON_KEYS_COUNT;++i)if(save_state.dungeon_keys[i]!=-1)return 0;
    for(i=0;i<4;++i)if(save_state.bottle_items[i]!=0xff)return 0;
    for(i=0;i<24;++i)if(save_state.source_items[i]!=0xff)return 0;
    for(i=0;i<16;++i)if(save_state.source_ammo[i])return 0;
    if(save_state.source_equipment || save_state.source_upgrades || save_state.source_magic_level ||
       save_state.source_magic || save_state.source_double_defense || save_state.source_tokens)return 0;
    return save_state.link_age==1 && save_state.day_time==0x8000 && !save_state.cutscene_index &&
        save_state.source_scene==0xff && save_state.source_entrance==0xffff;
}

int sf_world_matches(void)
{
    unsigned i;
    for(i=0;i<SAVE_SOURCE_SCENE_COUNT;++i) {
        const save_scene_flags_t *s=&save_state.generic_scene[i];
        if(s->chest!=(1u<<(i%32)) || s->swch!=0x11223300u+i ||
           s->clear!=0x88776600u+i || s->collect!=0x44332200u+i)return 0;
    }
    for(i=1;i<SAVE_DUNGEON_ITEMS_COUNT;++i)if(save_state.dungeon_items[i]!=(i&7))return 0;
    for(i=0;i<SAVE_DUNGEON_KEYS_COUNT;++i)if(save_state.dungeon_keys[i]!=(int)i-1)return 0;
    for(i=0;i<4;++i)if(save_state.bottle_items[i]!=0x14+i)return 0;
    for(i=0;i<24;++i)if(save_state.source_items[i]!=i)return 0;
    for(i=0;i<16;++i)if(save_state.source_ammo[i]!=i+1)return 0;
    if(save_state.source_equipment!=0x7777 || save_state.source_upgrades!=0x36e4db ||
       save_state.source_magic_level!=2 || save_state.source_magic!=96 ||
       !save_state.source_double_defense || save_state.source_tokens!=100)return 0;
    return !save_state.link_age && save_state.day_time==0x1234 && save_state.cutscene_index==0xfff3 &&
        save_state.source_scene==99 && save_state.source_entrance==0x345;
}

int sf_check_bottle_rewards(void)
{
    unsigned i;
    if(save_item_give(SAVE_ITEM_MILK))return 0;
    if(!save_item_give(SAVE_ITEM_BOTTLE_MILK_FULL) || save_state.bottle_items[0]!=0x1a)return 0;
    if(save_item_give(SAVE_ITEM_MILK))return 0;
    if(!save_item_give(SAVE_ITEM_BOTTLE_EMPTY) || save_state.bottle_items[1]!=0x14)return 0;
    if(!save_item_give(SAVE_ITEM_MILK) || save_state.bottle_items[1]!=0x1a)return 0;
    for(i=2;i<4;++i)if(!save_item_give(SAVE_ITEM_BOTTLE_MILK_FULL))return 0;
    return !save_item_give(SAVE_ITEM_BOTTLE_EMPTY) && !save_item_give(SAVE_ITEM_BOTTLE_MILK_FULL);
}
