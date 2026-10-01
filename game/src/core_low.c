/* Project-local SDK wrapper. The linker places core.o's zero-initialized
 * heap/callback storage in low work RAM. Capacity and allocator stay intact. */
#include <jo/jo.h>
#include "ram_low.h"
#undef JO_IS_ARRAY_INSIDE_USER_RAM_AREA
#define JO_IS_ARRAY_INSIDE_USER_RAM_AREA(a) \
    ((JO_IS_PTR_INSIDE_USER_RAM_AREA((unsigned char *)(a)) && \
      JO_IS_PTR_INSIDE_USER_RAM_AREA((unsigned char *)(a)+sizeof(a))) || \
     ((unsigned int)(a)>=RAM_LOW_ADDRESS+RAM_LOW_CORE_OFFSET && \
      (unsigned int)(a)+sizeof(a)<=RAM_LOW_ADDRESS+RAM_LOW_CORE_OFFSET+RAM_LOW_CORE_BYTES))
#include "core.c"
void core_low_init(void)
{
    unsigned i; unsigned char *p=RAM_LOW(RAM_LOW_CORE_OFFSET);
    for(i=0;i<RAM_LOW_CORE_BYTES;++i)p[i]=0;
}
