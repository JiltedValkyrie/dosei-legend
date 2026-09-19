#ifndef OOT_FOLLOW_H
#define OOT_FOLLOW_H
#include <stdbool.h>
#include <stdint.h>
#include "kokiri_collision.h"

/*
** OoT's Normal1 follow camera, as used by CAM_SET_NORMAL0.
**
** Parameters come from sSetNormal0ModeNormalData in z_camera_data.inc.c:
**
**   yOffset -20, eyeDist 200, eyeDistNext 300, pitchTarget 10,
**   yawUpdateRateTarget 12, xzUpdateRateTarget 10, maxYawUpdate 35, fov 60
**
** Those are raw data values. Camera_Normal1() scales the three distances by
**
**   yNormal = 1 + CAM_YOFFSET_NORM - CAM_YOFFSET_NORM * (68 / playerHeight)
**   scale   = yNormal * playerHeight * 0.01
**
** with CAM_YOFFSET_NORM = -0.1.
**
** playerHeight is OUR model's height, not OoT's 44: Camera_Normal1 scales the
** whole camera to whatever the player actually measures, and our baked child
** Link is 62 world units tall. Using 44 produced a camera correct for a
** smaller Link -- too close, and framed so his feet fell off the bottom of the
** screen. At 62 the scale is 0.6260, giving 125.2 to 187.8 units of distance
** and a 12.5-unit at-offset.
**
** Includes a behind-Link targeting adaptation. Full Parallel/KeepOn, first-person
** and the swing/collision behaviour are separate Camera_* functions and are
** NOT implemented here; see OPUS_HANDOFF.md for what remains.
*/

/* Scaled from the table above; see the derivation in oot_follow.c. */
#define OOT_CAM_DIST_MIN        125
#define OOT_CAM_DIST_MAX        188
#define OOT_CAM_Y_OFFSET        (-12)
/* CAM_DEG_TO_BINANG(10): 10 * 0x10000 / 360. */
#define OOT_CAM_PITCH_TARGET    1820

/* Storage Y is feet+90. Camera_CalcAtDefault targets player origin PLUS
** Player_GetHeight() PLUS yOffset; neither the storage eye nor feet alone. */
#define OOT_CAM_PLAYER_ORIGIN   90
#define OOT_CAM_PLAYER_HEIGHT   62

typedef struct
{
    /* Spherical, about the at-point: OoT stores the camera this way and the
    ** distance clamp and pitch approach are both natural in it. */
    int32_t     distance;
    uint16_t    yaw;
    int32_t     pitch;
    bool        initialised;
    /* Counts down while a recenter swing is running. OoT divides the
    ** remaining angle by this, so the turn eases out instead of snapping. */
    int32_t     swing_timer;
    /* Z-look aim, applied on TOP of the follow solution and never written back
    ** into it, so releasing Z returns to exactly the follow camera that would
    ** have been there anyway. Both are bounded; neither moves the player. */
    int32_t     look_yaw;
    int32_t     look_pitch;
    bool        look_active;
    bool        targeting;     /* behind-Link lock, independent of movement */
}               oot_follow_t;

/* Bounds for the Z-look aim, in binang. Yaw is limited rather than free so the
** look camera cannot be used as an unbounded orbit. */
#define OOT_LOOK_YAW_LIMIT      16384
#define OOT_LOOK_PITCH_LIMIT    12000

/* Aim the look camera by one step's deltas, clamped. */
void    oot_follow_look(oot_follow_t *camera, int32_t yaw_delta,
                        int32_t pitch_delta);
/* Leave look mode: the aim offsets are cleared so the follow camera resumes
** cleanly with no residual angle. */
void    oot_follow_look_exit(oot_follow_t *camera);
bool    oot_follow_looking(const oot_follow_t *camera);

/*
** Z-recenter turn length, in 30 Hz gameplay steps.
**
** This is Camera_Parallel1's animTimer, NOT Normal1's idle swing. An earlier
** revision used Normal1's startSwingTimer (CAM_GLOBAL_50 + CAM_GLOBAL_51),
** which is the camera drifting back behind a player who has STOPPED -- a
** different behaviour that happens to involve a turn.
**
** sSetNormal0ModeZParallelData sets PARALLEL1_FLAG_3 | PARALLEL1_FLAG_1 and
** not PARALLEL1_FLAG_2, so animTimer takes CAM_DEFAULT_ANIM_TIME = 4, at
** OoT's 20 Hz. Four updates at 20 Hz is 0.2 s, which is 6 steps at our 30 Hz.
*/
#define OOT_CAM_SWING_STEPS     6

/* Begin a Z-recenter turn: the camera rotates behind the player over
** OOT_CAM_SWING_STEPS instead of cutting there. Does not reset yaw -- the
** turn starts from wherever the camera currently is. */
void    oot_follow_recenter(oot_follow_t *camera);
/* Enter with eased turn; track facing every step until released. */
void    oot_follow_target(oot_follow_t *camera, bool active);

/* Place the camera behind `facing` immediately, with no easing. Used on spawn
** and after a void recovery, where easing would show empty space. */
/* Swap between the OoT geometry and the retired 260-unit viewer follow, so the
** two can be compared at the same spot. Development only; the viewer camera is
** NOT a design reference and must not become the shipping default. */
void    oot_follow_set_legacy(bool legacy);
bool    oot_follow_legacy(void);

void    oot_follow_snap(oot_follow_t *camera, const camera_position_t *player,
                        uint16_t facing);

/*
** Advance one 30 Hz step and write the resulting eye position.
**
** `moving` is whether the player actually travelled this step: OoT only swings
** the camera back behind the player while xzSpeed is non-zero, which is what
** stops the view from creeping when he is standing still.
*/
void    oot_follow_update(oot_follow_t *camera, const camera_position_t *player,
                          uint16_t player_facing, bool moving,
                          camera_position_t *eye_out, uint16_t *yaw_out,
                          int32_t *pitch_out);

#endif
