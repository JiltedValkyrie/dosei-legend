/* Compile the unmodified SDK source locally. All consumers retain the same
 * array symbols/types; only their linker placement changes. */
#include <jo/jo.h>
#include "ram_low.h"
extern jo_texture_definition __jo_sprite_def[JO_MAX_SPRITE]
    __attribute__((section(".lowmeta")));
extern jo_picture_definition __jo_sprite_pic[JO_MAX_SPRITE]
    __attribute__((section(".lowmeta")));
#ifdef JO_COMPILE_WITH_SPRITE_HASHTABLE
extern int __jo_hash_table[JO_MAX_SPRITE]
    __attribute__((section(".lowmeta")));
#endif
typedef char sprite_carve_fits[(sizeof(__jo_sprite_def) + sizeof(__jo_sprite_pic)
#ifdef JO_COMPILE_WITH_SPRITE_HASHTABLE
    + sizeof(__jo_hash_table)
#endif
    <= RAM_LOW_SPRITES_BYTES) ? 1 : -1];

/* Preserve the SDK's bounds check, extending it only to this reserved carve. */
#undef JO_IS_ARRAY_INSIDE_USER_RAM_AREA
#define JO_IS_ARRAY_INSIDE_USER_RAM_AREA(a) \
    ((JO_IS_PTR_INSIDE_USER_RAM_AREA((unsigned char *)(a)) && \
      JO_IS_PTR_INSIDE_USER_RAM_AREA((unsigned char *)(a) + sizeof(a))) || \
     ((unsigned int)(a) >= RAM_LOW_ADDRESS + RAM_LOW_SPRITES_OFFSET && \
      (unsigned int)(a) + sizeof(a) <= RAM_LOW_ADDRESS + RAM_LOW_SPRITES_OFFSET + RAM_LOW_SPRITES_BYTES))
#include "sprites.c"

void sprites_low_init(void)
{
    unsigned int i;
    unsigned char *p = RAM_LOW(RAM_LOW_SPRITES_OFFSET);
    for (i = 0; i < RAM_LOW_SPRITES_BYTES; ++i) p[i] = 0;
}
