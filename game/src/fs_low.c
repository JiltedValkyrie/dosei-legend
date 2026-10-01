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
#include "fs.c"
void fs_low_init(void)
{
    unsigned i;unsigned char *p=RAM_LOW(RAM_LOW_FS_DIRECTORY_OFFSET);
    for(i=0;i<RAM_LOW_FS_DIRECTORY_BYTES;++i)p[i]=0;
}
