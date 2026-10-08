/* Profiles are owned by SA.OAP and disappear with the Field scene. */
#include "oot_prelude.h"
#include "actor.h"
#include "effect.h"
#include "oot_actor_pack.h"
extern ActorProfile En_Encount1_Profile, En_Skb_Profile, En_Peehat_Profile, En_Po_Field_Profile;
extern "C" const OotActorPackProfile field_enemy_profiles[]
    __attribute__((section(".pack_actors"), used)) = {
        {ACTOR_EN_ENCOUNT1, (u32)(uintptr_t)&En_Encount1_Profile},
        {ACTOR_EN_SKB, (u32)(uintptr_t)&En_Skb_Profile},
        {ACTOR_EN_PEEHAT, (u32)(uintptr_t)&En_Peehat_Profile},
        {ACTOR_EN_PO_FIELD, (u32)(uintptr_t)&En_Po_Field_Profile},
    };
extern EffectSsProfile Effect_Ss_Dust_Profile, Effect_Ss_Hahen_Profile, Effect_Ss_En_Fire_Profile,
    Effect_Ss_Dead_Db_Profile, Effect_Ss_Dead_Sound_Profile, Effect_Ss_HitMark_Profile;
extern "C" const OotActorPackProfile field_effect_profiles[]
    __attribute__((section(".pack_effects"), used)) = {
        {EFFECT_SS_DUST, (u32)(uintptr_t)&Effect_Ss_Dust_Profile},
        {EFFECT_SS_HAHEN, (u32)(uintptr_t)&Effect_Ss_Hahen_Profile},
        {EFFECT_SS_EN_FIRE, (u32)(uintptr_t)&Effect_Ss_En_Fire_Profile},
        {EFFECT_SS_DEAD_DB, (u32)(uintptr_t)&Effect_Ss_Dead_Db_Profile},
        {EFFECT_SS_DEAD_SOUND, (u32)(uintptr_t)&Effect_Ss_Dead_Sound_Profile},
        {EFFECT_SS_HITMARK, (u32)(uintptr_t)&Effect_Ss_HitMark_Profile},
    };
