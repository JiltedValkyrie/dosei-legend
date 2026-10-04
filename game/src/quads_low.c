/* Cold SDK sprite-to-quad lookup. jo_3d_init clears every entry before use.
 * The shared SDK and all rendering code remain unchanged. */
#include <jo/jo.h>
#include "ram_low.h"
jo_3d_quad *__jo_sprite_quad[JO_MAX_SPRITE] __attribute__((section(".lowquad")));
typedef char quad_directory_fits[sizeof(__jo_sprite_quad)<=RAM_LOW_QUADS_BYTES?1:-1];
#include "3d.c"
