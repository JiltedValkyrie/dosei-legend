/* Keep the SDK immutable. Cold GFS tables move into one bounded low-RAM
 * carve; capacities, two open handles and allocator behavior stay unchanged. */
#include "fs_capacity.h"
#include "ram_low.h"
#include <SEGA_GFS.H>
static GfsDirName __jo_fs_dirname[JO_FS_MAX_FILES]
    __attribute__((section(".lowfs")));
static char __jo_fs_work[GFS_WORK_SIZE(JO_MAX_FS_BACKGROUND_JOBS)]
    __attribute__((section(".lowfs"),aligned(4)));
typedef char fs_directory_fits[sizeof(__jo_fs_dirname)+sizeof(__jo_fs_work)<=RAM_LOW_FS_DIRECTORY_BYTES?1:-1];
#undef JO_IS_ARRAY_INSIDE_USER_RAM_AREA
#define JO_IS_ARRAY_INSIDE_USER_RAM_AREA(a) \
    ((JO_IS_PTR_INSIDE_USER_RAM_AREA((unsigned char *)(a)) && \
      JO_IS_PTR_INSIDE_USER_RAM_AREA((unsigned char *)(a)+sizeof(a))) || \
     ((unsigned int)(a)>=RAM_LOW_ADDRESS+RAM_LOW_FS_DIRECTORY_OFFSET && \
      (unsigned int)(a)+sizeof(a)<=RAM_LOW_ADDRESS+RAM_LOW_FS_DIRECTORY_OFFSET+RAM_LOW_FS_DIRECTORY_BYTES))
/* Cover whole-file, metadata and streaming Jo callers without editing SDK.
 * Music uses raw GFS on the main thread; its next service resumes read-ahead. */
#include "music.h"
#define GFS_Open(id) (music_yield_cd() ? GFS_Open(id) : (GfsHn)0)
#define GFS_Load(id, off, buf, size) \
    (music_yield_cd() ? GFS_Load(id, off, buf, size) : -1)
#define GFS_Fread(h, n, buf, size) \
    (music_yield_cd() ? GFS_Fread(h, n, buf, size) : -1)
#include "fs.c"
#undef GFS_Open
#undef GFS_Load
#undef GFS_Fread
#include "fs_range.h"

int fs_file_size(const char *name)
{
    int id = GFS_NameToId((Sint8 *)name);
    return id < 0 ? -1 : jo_fs_get_file_size(id);
}

bool fs_read_sectors(const char *name, unsigned int sector, void *buffer,
                     unsigned int bytes)
{
    int id, size, retry;
    unsigned int offset;
    if (!buffer || !bytes || sector > 0x7fffffffu / JO_SECTOR_SIZE) return false;
    offset = sector * JO_SECTOR_SIZE;
    id = GFS_NameToId((Sint8 *)name);
    if (id < 0 || (size = jo_fs_get_file_size(id)) < 0 ||
        offset > (unsigned int)size || bytes > (unsigned int)size - offset)
        return false;
    for (retry = JO_READ_RETRY_COUNT; retry > 0; --retry) {
        if (!music_yield_cd()) return false;
        if (GFS_Load(id, (Sint32)sector, buffer, (Sint32)bytes) == (Sint32)bytes)
            return true;
        jo_spin_wait(JO_READ_SPIN_WAIT);
    }
    return false;
}

void fs_low_init(void)
{
    unsigned i;unsigned char *p=RAM_LOW(RAM_LOW_FS_DIRECTORY_OFFSET);
    for(i=0;i<RAM_LOW_FS_DIRECTORY_BYTES;++i)p[i]=0;
}
