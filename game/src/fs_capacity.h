/* Project-local override: include SDK config first so its unconditional
 * default cannot overwrite this. Applied only to the SDK filesystem object. */
#include <jo/jo.h>
#undef JO_FS_MAX_FILES
#define JO_FS_MAX_FILES 1536 /* all-scenes room banks + scene blobs */
