/* Host adapter for file_select.c.
**
** file_select.c is platform free, so nothing here stands in for the Saturn --
** the fake device does that, in save_device_fake.c. These are only accessors
** ctypes cannot reach directly: struct fields, and the fake's controls. */
#include <stdint.h>
#include "../../src/file_select.h"
#include "../../src/save_state.h"

extern int  fake_erase_fails;
extern int  fake_write_fails;

int  fs_step(int up, int down, int confirm, int cancel)
{
    file_select_input in;

    in.up = up != 0;
    in.down = down != 0;
    in.confirm = confirm != 0;
    in.cancel = cancel != 0;
    return ((int)file_select_step(&in));
}

int  fs_mode(void)          { return ((int)file_select.mode); }
int  fs_cursor(void)        { return ((int)file_select.cursor); }
int  fs_result(void)        { return ((int)file_select.result); }
int  fs_slot(void)          { return ((int)file_select.slot); }
int  fs_open_row(void)      { return ((int)file_select.open_row); }
int  fs_open_slot(void)     { return ((int)file_select_open_slot()); }
bool fs_device_failed(void) { return (file_select.device_failed); }

int  fs_status(unsigned int slot)
{
    return (slot < SAVE_FILE_SLOTS ? (int)file_select.status[slot] : -1);
}

int  fs_rupees(void)        { return ((int)save_state.rupees); }

void fs_set_rupees(int rupees)
{
    save_state.rupees = (uint16_t)rupees;
}

void fs_set_erase_fails(int value) { fake_erase_fails = value; }
void fs_set_write_fails(int value) { fake_write_fails = value; }
