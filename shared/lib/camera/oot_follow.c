/*
** OoT Normal1 follow camera, in fixed point.
**
** Derivation of the constants in the header, from Camera_Normal1() and
** sSetNormal0ModeNormalData:
**
**   playerHeight            62      (OUR baked Link, in world units)
**   CAM_YOFFSET_NORM        -0.1
**   yNormal = 1 + (-0.1) - (-0.1 * (68/62))            = 1.00968
**   scale   = yNormal * (62 * 0.01)                    = 0.62600
**
**   yOffset  -20 * 0.626 = -12.52  -> -12
**   distMin  200 * 0.626 = 125.20  -> 125
**   distMax  300 * 0.626 = 187.80  -> 188
**
** Scaling to 44 (OoT's child height in ITS units) was wrong: Camera_Normal1
** scales to whatever the player actually measures, and it framed Link with his
** feet below the bottom of the screen.
**
** The previous viewer camera sat 260 units back with no pitch, so this is a
** substantially closer and slightly downward-looking view. That is what the
** original does; it is not a tuning choice.
**
** What this does NOT implement, and must not be described as doing:
** Camera_Parallel1 (Z-parallel), Camera_KeepOn1/3 (targeting and talk),
** Camera_Subj3 (first person), the swing/startSwingTimer behaviour that
** reorients the camera after the player stops, slope pitch adjustment, or the
** at/eye collision poly handling that pulls the camera in past geometry.
*/

#include "oot_follow.h"
#include "kokiri_camera.h"

/*
** Camera_LERPCeilF with a shift instead of a float step scale.
**
** OoT's yawUpdateRateTarget 12 and xzUpdateRateTarget 10 are inverse rates:
** the step is diff/rate per update at 20 Hz. At our 30 Hz that would be too
** fast, so the equivalent per-step divisor is rate * 30/20 = rate * 3/2.
**
** The minDiff branch matters as much as the step: without it a shift-based
** approach stalls short of the target, which is what made the old follow
** camera creep. Anything within one unit snaps.
*/
static int32_t  approach(int32_t current, int32_t target, int32_t rate)
{
    int32_t diff = target - current;
    int32_t step;

    if (diff == 0)
        return target;
    step = diff / rate;
    /* Integer division truncates toward zero, so once |diff| < rate the step
    ** becomes 0 and the value freezes short of the target -- the camera would
    ** sit permanently a dozen units too far back. Always move at least one
    ** unit, which both guarantees arrival and matches Camera_LERPCeilF's
    ** minDiff branch snapping the remainder. */
    if (step == 0)
        step = diff > 0 ? 1 : -1;
    return current + step;
}

/* Shortest-path angular approach, in binang. The subtraction wraps, so this
** turns the short way round without an explicit comparison. */
static uint16_t angle_approach(uint16_t current, uint16_t target, int32_t rate)
{
    int16_t diff = (int16_t)(target - current);
    int16_t step;

    if (diff == 0)
        return target;
    step = (int16_t)(diff / rate);
    /* Same truncation stall as approach(): without this the heading settles a
    ** few binang off and never finishes turning. */
    if (step == 0)
        step = diff > 0 ? 1 : -1;
    return (uint16_t)(current + step);
}

/* 20 Hz inverse rates scaled to our 30 Hz step: rate * 3 / 2. */
#define YAW_RATE    18      /* yawUpdateRateTarget 12 */
#define XZ_RATE     15      /* xzUpdateRateTarget  10 */
#define PITCH_RATE  18

/* Retired viewer follow: fixed 260 units back, 40 below the eye, no pitch.
** Kept only so the new camera can be compared against it in place. */
#define LEGACY_DISTANCE     260
#define LEGACY_HEIGHT       (-40)
static bool     legacy_camera;

void            oot_follow_set_legacy(bool legacy)
{
    legacy_camera = legacy;
}

bool            oot_follow_legacy(void)
{
    return legacy_camera;
}

static void     place(const oot_follow_t *camera,
                      const camera_position_t *player,
                      camera_position_t *eye_out)
{
    int32_t sine, cosine, horizontal, height;

    if (legacy_camera)
    {
        kokiri_camera_sincos(camera->yaw, &sine, &cosine);
        eye_out->x = player->x
            - (int32_t)(((int64_t)sine * LEGACY_DISTANCE) >> 16);
        eye_out->z = player->z
            - (int32_t)(((int64_t)cosine * LEGACY_DISTANCE) >> 16);
        eye_out->y = player->y + LEGACY_HEIGHT;
        return;
    }

    /* Pitch tilts the eye up and shortens its ground reach. slSin/slCos are
    ** 16.16, so each product is shifted back down after multiplying. */
    kokiri_camera_sincos((uint16_t)camera->pitch, &sine, &cosine);
    horizontal = (int32_t)(((int64_t)camera->distance * cosine) >> 16);
    height = (int32_t)(((int64_t)camera->distance * sine) >> 16);

    kokiri_camera_sincos(camera->yaw, &sine, &cosine);
    /* Forward is (sin, cos), the same basis kokiri_camera_update() moves in,
    ** so the eye sits directly behind the camera's own heading. */
    eye_out->x = player->x - (int32_t)(((int64_t)sine * horizontal) >> 16);
    eye_out->z = player->z - (int32_t)(((int64_t)cosine * horizontal) >> 16);
    /* player->y is the EYE at floor+90; OoT aims at the player's origin, his
    ** feet. Without this the at-point is 90 units too high and his feet fall
    ** off the bottom of the screen. */
    eye_out->y = player->y - OOT_CAM_PLAYER_ORIGIN + OOT_CAM_Y_OFFSET + height;
}

void            oot_follow_snap(oot_follow_t *camera,
                                const camera_position_t *player,
                                uint16_t facing)
{
    (void)player;
    camera->distance = OOT_CAM_DIST_MAX;
    camera->yaw = facing;
    camera->pitch = OOT_CAM_PITCH_TARGET;
    camera->initialised = true;
}

void            oot_follow_update(oot_follow_t *camera,
                                  const camera_position_t *player,
                                  uint16_t player_facing, bool moving,
                                  camera_position_t *eye_out,
                                  uint16_t *yaw_out, int32_t *pitch_out)
{
    if (!camera->initialised)
        oot_follow_snap(camera, player, player_facing);

    /* Normal1 only swings back behind the player while he is actually moving
    ** (xzSpeed > 0.001). Standing still holds the current yaw, which is what
    ** keeps the view from drifting on its own. */
    if (moving)
        camera->yaw = angle_approach(camera->yaw, player_facing, YAW_RATE);

    /* Distance eases between distMin and distMax rather than being fixed: the
    ** camera trails out to distMax while he runs and draws back in to distMin
    ** as he slows. */
    camera->distance = approach(camera->distance,
                                moving ? OOT_CAM_DIST_MAX : OOT_CAM_DIST_MIN,
                                XZ_RATE);
    camera->pitch = approach(camera->pitch, OOT_CAM_PITCH_TARGET, PITCH_RATE);

    place(camera, player, eye_out);
    *yaw_out = camera->yaw;
    /* Negated: kokiri_camera_update() adds CAMERA_PITCH_SPEED for Up, so a
    ** positive demo_pitch looks UP. The eye has been raised above the player,
    ** so the view has to look DOWN by the same angle for the at-point to stay
    ** on him. Getting this sign wrong puts Link off the bottom of the screen,
    ** which is why the previous camera avoided pitch entirely. */
    *pitch_out = legacy_camera ? 0 : -camera->pitch;
}
