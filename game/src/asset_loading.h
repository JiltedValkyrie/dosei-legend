#ifndef DOSEI_ASSET_LOADING_H
#define DOSEI_ASSET_LOADING_H
#include <jo/jo.h>

/* Publish progress before a synchronous CD read, including ordinary builds. */
static inline void asset_loading(const char *name)
{
    jo_printf(0, 4, "LOAD %-32.32s", name);
    slSynch();
}

static inline void asset_loading_done(void)
{
    jo_printf(0, 4, "                                     ");
}
#endif
