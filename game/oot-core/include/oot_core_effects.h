#ifndef OOT_CORE_EFFECTS_H
#define OOT_CORE_EFFECTS_H

/* Pointer-free snapshot of the source EffectSs state. Semantic billboard
 * recipes interpret regs per effect type; source update owns all clocks.
 * No display list, object pointer or actor pointer escapes the core. */
#define OOT_CORE_EFFECT_VIEWS_MAX 32u
/* Actor-owned projectile; source EnPoField still owns motion and damage. */
#define OOT_CORE_EFFECT_POE_FLAME 0xfeu
/* Source boss room material, regs[0] = lava cooling phase 0..256. */
#define OOT_CORE_EFFECT_DODONGO_LAVA 0xfdu
/* Boss-owned embers: radius, RGB8 and alpha in regs[0..4]. */
#define OOT_CORE_EFFECT_DODONGO_EMBER 0xfcu
/* Damaging source Beamos beam: endpoint XYZ and radius in regs[0..3]. */
#define OOT_CORE_EFFECT_BEAMOS_BEAM 0xfbu
/* Source Death Mountain falling fragments: radius, RGB8, alpha. */
#define OOT_CORE_EFFECT_MOUNTAIN_FRAGMENT 0xfau
/* Source minigame HUD score; regs[0] holds the current total. */
#define OOT_CORE_EFFECT_MINIGAME_SCORE 0xf9u
typedef struct OotCoreEffectView {
    int x, y, z;
    short regs[13];
    short life;
    unsigned char type, priority;
    unsigned short slot;
} OotCoreEffectView;

#endif
