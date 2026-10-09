#ifndef HEALTH_HUD_H
#define HEALTH_HUD_H
#include <stdbool.h>
bool health_hud_init(void);
void health_hud_reset(void);
void health_hud_draw(bool visible);
/* Source magic meter state (z_parameter.c); see health_hud.c. */
void health_hud_magic_start(void);
void health_hud_magic_update(void);
void health_hud_magic_reset(void);
bool health_hud_magic_idle(void);
bool health_hud_magic_available(unsigned amount);
bool health_hud_magic_consume(unsigned amount);
#endif
