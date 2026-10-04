/*
 * Overlay tables for the Saturn: z_actor_dlftbls.c / z_effect_soft_sprite_dlftbls.c
 * rebuilt from the same decomp table headers. There is no overlay loading:
 * every entry is "internal" (vramStart NULL), so Actor_Spawn and
 * EffectSs_Spawn use the profile in place. Profiles are weak, so an actor or
 * effect is registered just by adding its file to the importer's SOURCES; one
 * not imported has a NULL profile. Callers must not spawn a NULL-profile id
 * (oot_core_api spawn checks).
 */
#include "oot_prelude.h"
#include "ultra64.h"
#include "actor.h"
#include "effect.h"
#include "z_actor_dlftbls.h"

#define DEFINE_ACTOR(name, _1, _2, _3) extern ActorProfile name##_Profile __attribute__((weak));
#define DEFINE_ACTOR_INTERNAL(name, _1, _2, _3) extern ActorProfile name##_Profile __attribute__((weak));
#define DEFINE_ACTOR_UNSET(_0)
#include "tables/actor_table.h"
#undef DEFINE_ACTOR
#undef DEFINE_ACTOR_INTERNAL
#undef DEFINE_ACTOR_UNSET

#define DEFINE_ACTOR(name, _1, allocType, _3) \
    { ROM_FILE_UNSET, NULL, NULL, NULL, &name##_Profile, NULL, allocType, 0 },
#define DEFINE_ACTOR_INTERNAL(name, _1, allocType, _3) \
    { ROM_FILE_UNSET, NULL, NULL, NULL, &name##_Profile, NULL, allocType, 0 },
#define DEFINE_ACTOR_UNSET(_0) { 0 },
ActorOverlay gActorOverlayTable[] = {
#include "tables/actor_table.h"
};
#undef DEFINE_ACTOR
#undef DEFINE_ACTOR_INTERNAL
#undef DEFINE_ACTOR_UNSET

s32 gMaxActorId = 0;

void ActorOverlayTable_Init(void) {
    gMaxActorId = ACTOR_ID_MAX;
}

void ActorOverlayTable_Cleanup(void) {
    gMaxActorId = 0;
}

#define DEFINE_EFFECT_SS(name, _1) extern EffectSsProfile name##_Profile __attribute__((weak));
#define DEFINE_EFFECT_SS_UNSET(_0)
#include "tables/effect_ss_table.h"
#undef DEFINE_EFFECT_SS
#undef DEFINE_EFFECT_SS_UNSET

#define DEFINE_EFFECT_SS(name, _1) { ROM_FILE_UNSET, NULL, NULL, NULL, &name##_Profile, 1 },
#define DEFINE_EFFECT_SS_UNSET(_0) { ROM_FILE_UNSET, NULL, NULL, NULL, NULL, 0 },
EffectSsOverlay gEffectSsOverlayTable[] = {
#include "tables/effect_ss_table.h"
};
#undef DEFINE_EFFECT_SS
#undef DEFINE_EFFECT_SS_UNSET
