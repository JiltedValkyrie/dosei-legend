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
