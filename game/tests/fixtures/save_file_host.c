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
