#ifndef VIEWER_RECOMP_H
#define VIEWER_RECOMP_H
#include "player_input.h"
#include "kokiri_camera.h"
bool recomp_init(void);
/* Bind TITLEPTH.BIN (cart carve): the title camera paths, BUG-043. */
bool recomp_title_paths_bind(const uint8_t *blob, uint32_t bytes);
void recomp_update(void);
bool recomp_title_is_visible(void);
bool recomp_code_fanfare_active(void);
bool recomp_chest_opening(void);
unsigned recomp_chest_frame(void);
int recomp_chest_index(void);
/* Live screen distance in pixels (main.c; slSetScreenDist uses it). */
int32_t recomp_screen_distance(void);
/* True while the file select owns the pad. The world does not step and the
** gameplay HUD must stay off, same as the title. */
bool recomp_file_select_is_visible(void);
/* Outcome of the last pause-menu save: -1 none yet, 0 failed, 1 succeeded. */
int recomp_save_report(void);
unsigned int recomp_clock(void);
unsigned int recomp_world_clock(void);
bool recomp_skip_prompt(void);
/* The crawlspace "Enter" A prompt (PLAYER_STATE2_DO_ACTION_ENTER). */
bool recomp_enter_prompt(void);
/* Camera_Subj4 in a crawlspace: first person, Link not drawn. */
bool recomp_first_person(void);
bool recomp_shop_browsing(void);
bool recomp_view_first_person(void);
extern camera_position_t recomp_camera;
extern uint16_t recomp_yaw;
extern int32_t recomp_pitch;

/* Link. recomp_link is his collision position, i.e. an eye at floor+EYE_HEIGHT
 * exactly like the free camera, so the baseline's swept movement, wall sliding,
 * floor/ceiling constraints and gravity apply to him. His feet, and so the
 * model's origin, are EYE_HEIGHT below it. */
extern camera_position_t recomp_link;
extern uint16_t recomp_link_yaw;
extern bool recomp_link_active;
#define RECOMP_LINK_EYE_HEIGHT 90
uint16_t kokiri_camera_facing(int32_t dx, int32_t dz);
extern bool recomp_collision_indexed;
/* Set for one frame when the L+R diagnostics chord is newly held. The HUD
 * clears it. Both buttons are consumed, so the chord cannot also recenter. */
extern bool recomp_diagnostics_toggled;
/* Inputs whose gameplay systems are not implemented yet (2026-09-18 layout):
 * A interact, X attack, and the four routed C buttons. Recorded, never
 * substituted with unrelated behavior. See src/player_input.h. */
extern unsigned int recomp_interact_requests;
extern unsigned int recomp_attack_requests;
extern player_c_button_t recomp_last_c_button;
extern unsigned recomp_evade_gates, recomp_evade_pose;   /* debug readout */
/* True only in LIFT_HOLD, where player_lift_update() actually accepts A.
 * The lift/throw/put animations still hold the prop, so the carried handle
 * alone would advertise a Drop the button cannot perform. */
bool recomp_lift_hold_actionable(void);
/* True while Link is holding a prop and speed is high enough to throw (>= 282 Q8)
 * or the prop is throw-only.  Read-only; no side effects. */
bool recomp_lift_throw_ready(void);
/* A close, front-facing push block can start A: Grab. */
bool recomp_push_prompt(void);
bool recomp_slingshot_aiming(void);
/* Selected aim tool's source inventory slot, or 0xff outside tool aim. */
unsigned int recomp_aim_inventory_slot(void);
bool recomp_target_marker(int32_t *x, int32_t *y, bool *locked, unsigned *kind);
/* Sword and shield in hand (drawn) rather than on Link's back. */
bool recomp_sword_out(void);
#endif
