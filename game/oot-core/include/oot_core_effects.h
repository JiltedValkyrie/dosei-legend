#ifndef OOT_CORE_EFFECTS_H
#define OOT_CORE_EFFECTS_H

/* Pointer-free snapshot of the source EffectSs state. Semantic billboard
 * recipes interpret regs per effect type; source update owns all clocks.
 * No display list, object pointer or actor pointer escapes the core. */
#define OOT_CORE_EFFECT_VIEWS_MAX 32u
/* Actor-owned projectile; source EnPoField still owns motion and damage. */
#define OOT_CORE_EFFECT_POE_FLAME 0xfeu
typedef struct OotCoreEffectView {
    int x, y, z;
    short regs[13];
    short life;
    unsigned char type, priority;
    unsigned short slot;
} OotCoreEffectView;

#endif
