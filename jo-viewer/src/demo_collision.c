/* Compile the platform-independent baseline unchanged, into local objects. */
/* Bundled newlib limits.h includes a missing GCC limits.h. stdint.h supplies
 * INT32_MIN, the only limit this translation unit needs. */
#define _GCC_LIMITS_H_
#include "../../title-screen/src/scene/kokiri_collision.c"
