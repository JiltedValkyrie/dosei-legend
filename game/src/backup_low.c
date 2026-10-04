/* Project-local BIOS backup driver placement; shared Jo SDK stays immutable.
 * BUP_Init copies executable code, so reserve console RAM before cart assets.
 * Sega STN-52 corrects the old 8192-byte work area to 8312 bytes. */
#include "ram_low.h"
#define jo_backup_mount dosei_sdk_backup_mount
#define jo_backup_unmount dosei_sdk_backup_unmount
#include "backup.c"
#undef jo_backup_mount
#undef jo_backup_unmount

bool jo_backup_mount(const jo_backup_device device)
{
    if ((unsigned int)device >= 3) return false;
    if (!__jo_backup_initialized) {
        unsigned int i;
        unsigned char *work = RAM_LOW(RAM_LOW_BACKUP_WORK_OFFSET);
        __jo_backup_lib_space = RAM_LOW(RAM_LOW_BACKUP_LIB_OFFSET);
        __jo_backup_work_space = (unsigned int *)work;
        for (i = 0; i < RAM_LOW_BACKUP_WORK_BYTES; ++i) work[i] = 0;
        jo_core_disable_reset();
        JO_BACKUP_DRIVER_INIT(__jo_backup_lib_space, __jo_backup_work_space, __jo_backup_cntb);
        jo_core_enable_reset();
        __jo_backup_initialized = true;
    }
    __jo_backup_devices[device].status =
        JO_BACKUP_DRIVER_STAT(device, 10, &__jo_backup_devices[device].sttb);
    /* Never format existing backup memory as a side effect of mounting it.
     * An unformatted device is reported to the player for BIOS setup. */
    __jo_backup_devices[device].is_mounted = __jo_backup_devices[device].status == 0;
    return __jo_backup_devices[device].is_mounted;
}

bool jo_backup_unmount(const jo_backup_device device)
{
    if ((unsigned int)device >= 3 || !__jo_backup_devices[device].is_mounted) return false;
    __jo_backup_devices[device].is_mounted = false;
    /* Fixed low-RAM workspaces stay reserved for the lifetime of the game. */
    return true;
}

int save_backup_status(void)
{
    return __jo_backup_devices[JoInternalMemoryBackup].status;
}
