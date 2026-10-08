/* Temporary C Player ownership contract. Retire with bridge_player.cpp. */
#ifndef OOT_CORE_COMBAT_H
#define OOT_CORE_COMBAT_H

#define OOT_COMBAT_SHIELD 1u
#define OOT_COMBAT_INTANGIBLE 2u
#define OOT_COMBAT_DODGE 4u
#define OOT_COMBAT_DISABLED 8u
#define OOT_COMBAT_LOCKED 16u
#define OOT_HIT_GUARD 1u
#define OOT_HIT_LARGE 2u

typedef struct OotCoreCombatState {
    unsigned int flags, damage_flags;
    unsigned short swing;
    unsigned char damage, shield;
} OotCoreCombatState;

typedef struct OotCorePlayerHit {
    int speed_q16;
    unsigned short yaw;
    unsigned char damage, effect; /* source HIT_SPECIAL_EFFECT_* */
    unsigned int flags;
} OotCorePlayerHit;

#endif
