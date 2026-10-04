#ifndef DOSEI_SAVE_DEVICE_H
#define DOSEI_SAVE_DEVICE_H
#include <stdbool.h>
#include <stdint.h>
#include "save_file.h"

/*
** Backup-RAM access for the three save slots.
**
** This is the ONLY save-related file that touches the SDK. The byte format,
** the checksum and the version check all live in save_file.c, which is
** platform free and host tested; this layer just moves a validated block to
** and from a device. Keeping the split means a save bug is almost always
** reproducible on the host.
**
** Host tests cover device failure handling using a mocked BIOS/SDK boundary.
** Actual backup persistence still needs an emulator or console check. Writes
** succeed only after the SDK's BIOS verify succeeds; read failures on a mounted
** device are distinct from empty slots. Mount failures allow unsaved play and
** display a device error instead of silently claiming saving is available.
**
** Slot files are DOSEI0..DOSEI2 on the console's internal backup memory.
** Internal memory is used rather than the cartridge because the 4 MB RAM
** expansion occupies the cartridge slot -- a DRAM cart is not a backup device,
** so saving there is not an option on the hardware this game requires.
*/

/* Names are JO_BACKUP_MAX_FILENAME_LENGTH-bounded; these are 6 characters. */
#define SAVE_DEVICE_NAME_PREFIX "DOSEI"

/* Mount the backup device. Call once at startup, after jo_core_init(). Returns
** false when there is no usable internal backup memory, in which case the game
** is playable but cannot save, and the caller must say so rather than failing
** later at the first save. */
bool                save_device_init(void);

/* True when save_device_init() found a device. */
bool                save_device_ready(void);
/* Last device failure, including an unformatted BIOS backup device. */
const char *save_device_error(void);
/* Global UI configuration, separate from the three adventure save slots. */
bool save_device_write_preferences(void);
int save_device_preferences_report(void);

/* Write the live save_state to a slot. False on any device failure. */
bool                save_device_write(unsigned int slot);

/* Read a slot into the live save_state. On refusal the live state is left
** untouched (save_file_unpack guarantees that) and the reason is returned. */
save_file_status    save_device_read(unsigned int slot);

/* Describe a slot for the file select, without loading it. */
save_file_status    save_device_summary(unsigned int slot,
                                        save_file_summary *summary);

/* Erase a slot. False on device failure; erasing an already-empty slot is
** success, because the caller asked for it to end up empty. */
bool                save_device_erase(unsigned int slot);

/* Free blocks reported by the device, for a "not enough space" message.
** Negative when unknown. */
int                 save_device_free_blocks(void);

#endif
