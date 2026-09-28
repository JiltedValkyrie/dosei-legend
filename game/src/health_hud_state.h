#ifndef HEALTH_HUD_STATE_H
#define HEALTH_HUD_STATE_H
/* z_lifemeter.c sHeartTextures: 1..5 quarter, 6..10 half, 11..15 three-quarter. */
static inline unsigned health_hud_fill(unsigned health, unsigned heart)
{
    unsigned base = heart * 16;
    if (health <= base) return 0;
    if (health >= base + 16) return 4;
    return health - base <= 5 ? 1 : health - base <= 10 ? 2 : 3;
}
#endif
