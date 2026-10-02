/*
 * Phase 1 link roots. --gc-sections keeps only code reachable from the blob's
 * entry table, so these pointers pull the decomp actor/collision systems into
 * the link. The undefined symbols they drag in are the Saturn bridge work list
 * (OOT_CORE_PIPELINE_PLAN.md, Phase 1 step 3). Step 4 replaces this table
 * with real entry points (init/update/draw/spawn).
 */
#include "oot_prelude.h"
#include "ultra64.h"
#include "actor.h"
#include "bgcheck.h"
#include "collision_check.h"

extern ActorProfile En_Kusa_Profile;
extern ActorProfile En_Item00_Profile;

extern "C" const void* const oot_core_roots[] __attribute__((section(".oot_entry.roots"), used)) = {
    (const void*)Actor_InitContext,
    (const void*)Actor_UpdateAll,
    (const void*)Actor_DrawAll,
    (const void*)Actor_Spawn,
    (const void*)BgCheck_Allocate,
    (const void*)CollisionCheck_AT,
    (const void*)CollisionCheck_OC,
    (const void*)&En_Kusa_Profile,
    (const void*)&En_Item00_Profile,
};
