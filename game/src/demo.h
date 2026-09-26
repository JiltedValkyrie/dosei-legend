#ifndef VIEWER_DEMO_H
#define VIEWER_DEMO_H
#include "player_input.h"
#include "kokiri_camera.h"
bool demo_init(void);
void demo_update(void);
bool demo_title_is_visible(void);
/* True while the file select owns the pad. The world does not step and the
** gameplay HUD must stay off, same as the title. */
bool demo_file_select_is_visible(void);
/* Outcome of the last pause-menu save: -1 none yet, 0 failed, 1 succeeded. */
int demo_save_report(void);
unsigned int demo_clock(void);
bool demo_skip_prompt(void);
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
/* Inputs whose gameplay systems are not implemented yet (2026-09-18 layout):
 * A interact, X attack, and the four routed C buttons. Recorded, never
 * substituted with unrelated behavior. See src/player_input.h. */
extern unsigned int demo_interact_requests;
extern unsigned int demo_attack_requests;
extern player_c_button_t demo_last_c_button;
#endif
