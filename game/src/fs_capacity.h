/* Project-local override: include SDK config first so its unconditional
 * default cannot overwrite this. Applied only to the SDK filesystem object. */
#include <jo/jo.h>
/* The SDK name table is unused (fs_low.c): GFS keeps an ID-only table in the
 * low-RAM FS carve and exact packed 8.3 keys live in the cart FSKEYS carve. */
#undef JO_FS_MAX_FILES
#define JO_FS_MAX_FILES 1
#define DOSEI_FS_MAX_FILES 2560 /* root entries incl. '.' and '..' */
