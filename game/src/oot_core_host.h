#ifndef DOSEI_OOT_CORE_HOST_H
#define DOSEI_OOT_CORE_HOST_H
/*
** C side of the oot-core blob (oot-core/include/oot_core_api.h). Boot loads
** OOTCORE.BIN and the scene collision blobs into their cart carves; each
** 30 Hz gameplay step drives the decomp play state at the decomp's 20 Hz.
** Built only with OOT_CORE=1; the calls compile to nothing otherwise.
*/
#include <stdbool.h>

#ifdef DOSEI_OOT_CORE
#include "oot_core_api.h"

/* Boot: load + init the blob and run the gate bench. False if not loaded. */
bool oot_core_boot(void);
/* After gameplay_step (fixed 30 Hz). Starts/stops the decomp play state
** with the scene and steps it 2 of every 3 calls. */
void oot_core_frame(void);

bool oot_core_is_loaded(void);
/* Play state active for the current scene. */
bool oot_core_is_playing(void);
const OotCoreBench *oot_core_bench_result(void);
/* Same bench run from low work RAM (OOTBENCH.BIN); NULL if it did not run. */
const OotCoreBench *oot_core_bench_wram(void);
int oot_core_actors(int category);
/* Live actors of a category, for C drawing (see OotCoreActorView). */
int oot_core_view(int category, OotCoreActorView *out, int max);
/* Kokiri Forest grass (En_Kusa) and floor rupees (En_Item00) belong to the
** decomp while it plays: the C copies stop drawing, cutting and collecting. */
static inline bool oot_core_owns_kokiri_props(void) { return oot_core_is_playing(); }
#else
static inline void oot_core_frame(void) {}
static inline bool oot_core_owns_kokiri_props(void) { return false; }
#endif

#endif
