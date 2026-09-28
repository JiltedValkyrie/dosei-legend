#ifndef HEALTH_HUD_H
#define HEALTH_HUD_H
#include <stdbool.h>
bool health_hud_init(void);
void health_hud_reset(void);
void health_hud_draw(bool visible);
#endif
