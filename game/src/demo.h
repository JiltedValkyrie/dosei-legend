#ifndef VIEWER_DEMO_H
#define VIEWER_DEMO_H
#include "kokiri_camera.h"
bool demo_init(void);
void demo_update(void);
bool demo_title_is_visible(void);
unsigned int demo_clock(void);
extern camera_position_t demo_camera;
extern uint16_t demo_yaw;
extern int32_t demo_pitch;

/* Link. demo_link is his collision position, i.e. an eye at floor+EYE_HEIGHT
 * exactly like the free camera, so the baseline's swept movement, wall sliding,
 * floor/ceiling constraints and gravity apply to him. His feet, and so the
 * model's origin, are EYE_HEIGHT below it. */
extern camera_position_t demo_link;
extern uint16_t demo_link_yaw;
extern bool demo_link_active;
#define DEMO_LINK_EYE_HEIGHT 90
uint16_t kokiri_camera_facing(int32_t dx, int32_t dz);
extern bool demo_collision_indexed;
/* Set for one frame when the L+R diagnostics chord is newly held. The HUD
 * clears it. Both buttons are consumed, so the chord cannot also recenter. */
extern bool demo_diagnostics_toggled;
#endif
