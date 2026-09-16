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
** with CAM_YOFFSET_NORM = -0.1. For child Link (height 44) that is 0.4640, so
** the real camera sits 92.8 to 139.2 units behind him with a 9.3-unit
** downward at-offset, not the 260 units the viewer camera used.
**
** This is the normal follow mode only. Parallel/KeepOn targeting, first-person
** and the swing/collision behaviour are separate Camera_* functions and are
** NOT implemented here; see OPUS_HANDOFF.md for what remains.
*/

/* Scaled from the table above; see the derivation in oot_follow.c. */
#define OOT_CAM_DIST_MIN        93
#define OOT_CAM_DIST_MAX        139
#define OOT_CAM_Y_OFFSET        (-9)
/* CAM_DEG_TO_BINANG(10): 10 * 0x10000 / 360. */
#define OOT_CAM_PITCH_TARGET    1820

typedef struct
{
    /* Spherical, about the at-point: OoT stores the camera this way and the
    ** distance clamp and pitch approach are both natural in it. */
    int32_t     distance;
    uint16_t    yaw;
    int32_t     pitch;
    bool        initialised;
}               oot_follow_t;

/* Place the camera behind `facing` immediately, with no easing. Used on spawn,
** on recenter, and after a void recovery. */
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
