/*
** Backup-RAM access for the three save slots. Split rationale and the reason
** internal memory is used rather than the cartridge are in save_device.h.
*/

#include <jo/jo.h>
#include "save_device.h"
#include "ui_preferences.h"

#define DEVICE      JoInternalMemoryBackup

static bool         device_ready = false;
extern int save_backup_status(void); /* project-local BIOS wrapper: raw status */
static int last_error;
static save_file_status read_status;
static char prefs_name[] = "DOSEICFG", prefs_comment[] = "UI SETUP";
static int prefs_report = -1;

/* Slot file names. Built once rather than sprintf'd per call: the SDK takes a
** non-const char* and keeps no copy, so the storage has to outlive the call. */
static char         slot_name[SAVE_FILE_SLOTS][8] = {
    "DOSEI0", "DOSEI1", "DOSEI2"
};
static char         slot_comment[] = "DOSEI LEG";   /* 9 chars, limit is 10 */

bool                save_device_init(void)
{
    unsigned int length;
    uint8_t *data;
    ui_preferences_reset();
    device_ready = jo_backup_mount(DEVICE);
    last_error = device_ready ? 0 : save_backup_status();
    if (device_ready && jo_backup_file_exists(DEVICE, prefs_name)) {
        data = jo_backup_load_file_contents(DEVICE, prefs_name, &length);
        if (data) { ui_preferences_unpack(data, length); jo_free(data); }
    }
    return (device_ready);
}

bool save_device_write_preferences(void)
{
    uint8_t data[UI_PREF_BYTES];
    ui_preferences_pack(data);
    prefs_report = device_ready && jo_backup_save_file_contents(DEVICE, prefs_name,
        prefs_comment, data, UI_PREF_BYTES);
    if (device_ready) last_error = prefs_report ? 0 : save_backup_status();
    return prefs_report != 0;
}
int save_device_preferences_report(void) { return prefs_report; }

bool                save_device_ready(void)
{
    return (device_ready);
}

const char *save_device_error(void)
{
    switch (last_error) {
    case 2: return "INIT BACKUP IN BIOS";
    case 3: return "BACKUP WRITE PROTECTED";
    case 4: return "BACKUP MEMORY FULL";
    case 7: return "BACKUP VERIFY FAILED";
    case 8: return "BACKUP MEMORY DAMAGED";
    default: return device_ready ? "BACKUP ACCESS FAILED" : "NO BACKUP MEMORY";
    }
}

bool                save_device_write(unsigned int slot)
{
    uint8_t     block[SAVE_FILE_BYTES];

    if (!device_ready || slot >= SAVE_FILE_SLOTS)
        return (false);
    save_file_pack(&save_state, block);
    bool ok = jo_backup_save_file_contents(DEVICE, slot_name[slot],
                                          slot_comment, block, SAVE_FILE_BYTES);
    last_error = ok ? 0 : save_backup_status();
    return ok;
}

/* Read one slot's raw bytes. The SDK allocates the buffer, so every caller has
** to free it; both callers below go through this to keep that paired. */
static uint8_t     *slot_contents(unsigned int slot, unsigned int *bytes)
{
    void            *data;
    unsigned int     length = 0;

    *bytes = 0;
    read_status = SAVE_FILE_DEVICE_ERROR;
    if (!device_ready) {
        /* Preserve unsaved play when no device mounts. The file-select and
         * save panel show the mount error, and writes remain disabled. */
        read_status = SAVE_FILE_EMPTY;
        return ((uint8_t *)0);
    }
    if (slot >= SAVE_FILE_SLOTS)
        return ((uint8_t *)0);
    if (!jo_backup_file_exists(DEVICE, slot_name[slot])) {
        last_error = save_backup_status();
        /* BUP_Dir returns zero matches for a missing file. Other results
         * are device failures, never permission to start a new save. */
        if (last_error == 0 || last_error == 5) read_status = SAVE_FILE_EMPTY;
        return ((uint8_t *)0);
    }
    data = jo_backup_load_file_contents(DEVICE, slot_name[slot], &length);
    if (!data) {
        last_error = save_backup_status();
        return ((uint8_t *)0);
    }
    *bytes = length;
    return ((uint8_t *)data);
}

save_file_status    save_device_read(unsigned int slot)
{
    unsigned int        bytes;
    uint8_t            *data = slot_contents(slot, &bytes);
    save_file_status    status;

    if (!data)
        return read_status;
    status = save_file_unpack(&save_state, data, bytes);
    jo_free(data);
    return (status);
}

save_file_status    save_device_summary(unsigned int slot,
                                        save_file_summary *summary)
{
    unsigned int        bytes;
    uint8_t            *data = slot_contents(slot, &bytes);
    save_file_status    status;

    if (!data) {
        if (summary) {
            /* Clear stale row contents even when the read failed. */
            save_file_read_summary(summary, (const uint8_t *)0, 0);
        }
        return read_status;
    }
    status = save_file_read_summary(summary, data, bytes);
    jo_free(data);
    return (status);
}

bool                save_device_erase(unsigned int slot)
{
    if (!device_ready || slot >= SAVE_FILE_SLOTS)
        return (false);
    if (!jo_backup_file_exists(DEVICE, slot_name[slot]))
        return (true);          /* already the state the caller asked for */
    return (jo_backup_delete_file(DEVICE, slot_name[slot]));
}

int                 save_device_free_blocks(void)
{
    if (!device_ready)
        return (-1);
    return (jo_backup_get_free_block_count(DEVICE));
}

/*
** END OF FILE
*/
