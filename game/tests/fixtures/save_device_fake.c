/* In-memory stand-in for save_device.c, so the real file_select.c can be
** driven on the host.
**
** It implements save_device.h exactly, storing three blocks in RAM. The point
** is to produce the states a real backup cartridge makes awkward to arrange on
** demand: an empty slot, a slot damaged in transit, and a device that refuses
** to write or erase. save_file.c does the actual packing here, same as on the
** Saturn, so only the device is fake. */
#include <stdint.h>
#include "../../src/save_device.h"

#define FAKE_BLOCK  SAVE_FILE_BYTES

static uint8_t      block[SAVE_FILE_SLOTS][FAKE_BLOCK];
static int          stored[SAVE_FILE_SLOTS];
static int          ready = 1;

/* --- test controls (not part of save_device.h) --------------------------- */

int  fake_write_fails = 0;
int  fake_erase_fails = 0;

void fake_reset(void)
{
    unsigned int slot, i;

    for (slot = 0; slot < SAVE_FILE_SLOTS; ++slot) {
        stored[slot] = 0;
        for (i = 0; i < FAKE_BLOCK; ++i)
            block[slot][i] = 0x00;      /* a blank device reads back uniform */
    }
    ready = 1;
    fake_write_fails = 0;
    fake_erase_fails = 0;
}

void fake_set_device_ready(int value)
{
    ready = value;
}

/* Write the CURRENT live save into a slot without going through the game, so a
** test can arrange a populated slot. */
void fake_store_current(unsigned int slot)
{
    if (slot >= SAVE_FILE_SLOTS)
        return;
    save_file_pack(&save_state, block[slot]);
    stored[slot] = 1;
}

/* Flip one byte of a stored slot: the checksum must then refuse it. */
void fake_corrupt(unsigned int slot, unsigned int offset)
{
    if (slot >= SAVE_FILE_SLOTS || offset >= FAKE_BLOCK)
        return;
    block[slot][offset] ^= 0xFF;
}

/* Overwrite a stored slot's version word, to simulate an older save. */
void fake_set_version(unsigned int slot, unsigned int version)
{
    if (slot >= SAVE_FILE_SLOTS)
        return;
    block[slot][4] = (uint8_t)(version >> 8);
    block[slot][5] = (uint8_t)(version & 0xFF);
}

int  fake_is_stored(unsigned int slot)
{
    return (slot < SAVE_FILE_SLOTS ? stored[slot] : 0);
}

/* --- save_device.h ------------------------------------------------------- */

bool save_device_init(void)
{
    return (ready != 0);
}

bool save_device_ready(void)
{
    return (ready != 0);
}

bool save_device_write(unsigned int slot)
{
    if (!ready || slot >= SAVE_FILE_SLOTS || fake_write_fails)
        return (false);
    save_file_pack(&save_state, block[slot]);
    stored[slot] = 1;
    return (true);
}

save_file_status save_device_read(unsigned int slot)
{
    if (!ready || slot >= SAVE_FILE_SLOTS || !stored[slot])
        return (SAVE_FILE_EMPTY);
    return (save_file_unpack(&save_state, block[slot], FAKE_BLOCK));
}

save_file_status save_device_summary(unsigned int slot,
                                    save_file_summary *summary)
{
    if (!ready || slot >= SAVE_FILE_SLOTS || !stored[slot])
        return (save_file_read_summary(summary, (const uint8_t *)0, 0));
    return (save_file_read_summary(summary, block[slot], FAKE_BLOCK));
}

bool save_device_erase(unsigned int slot)
{
    unsigned int i;

    if (!ready || slot >= SAVE_FILE_SLOTS || fake_erase_fails)
        return (false);
    if (!stored[slot])
        return (true);
    stored[slot] = 0;
    for (i = 0; i < FAKE_BLOCK; ++i)
        block[slot][i] = 0x00;
    return (true);
}

int save_device_free_blocks(void)
{
    return (ready ? 100 : -1);
}
