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
    /* z_camera.c Camera_CalcAtDefault/func_800458D4:
    ** atTarget.y = player origin + Player_GetHeight() + yOffset.
    ** Forgetting height put the camera only 9..20 units above the floor. */
    eye_out->y = player->y - OOT_CAM_PLAYER_ORIGIN + OOT_CAM_PLAYER_HEIGHT
                + OOT_CAM_Y_OFFSET + height;
}

static int32_t  clamp(int32_t value, int32_t limit)
{
    if (value > limit)
        return limit;
    if (value < -limit)
        return -limit;
    return value;
}

void            oot_follow_look(oot_follow_t *camera, int32_t yaw_delta,
                                int32_t pitch_delta)
{
    camera->look_active = true;
    camera->look_yaw = clamp(camera->look_yaw + yaw_delta,
                             OOT_LOOK_YAW_LIMIT);
    camera->look_pitch = clamp(camera->look_pitch + pitch_delta,
                               OOT_LOOK_PITCH_LIMIT);
}

void            oot_follow_look_exit(oot_follow_t *camera)
{
    camera->look_active = false;
    camera->look_yaw = 0;
    camera->look_pitch = 0;
}

bool            oot_follow_looking(const oot_follow_t *camera)
{
    return camera->look_active;
}

void            oot_follow_recenter(oot_follow_t *camera)
{
    /* Do not reset yaw here: the swing works from wherever the camera is now.
    ** Snapping first would defeat the whole point. */
    camera->swing_timer = OOT_CAM_SWING_STEPS;
    camera->initialised = true;
}

void            oot_follow_target(oot_follow_t *camera, bool active)
{
    if (active && !camera->targeting)
        oot_follow_recenter(camera);
    if (!active && camera->targeting)
        camera->swing_timer = 0;
    camera->targeting = active;
    if (active)
        oot_follow_look_exit(camera);
}

void            oot_follow_snap(oot_follow_t *camera,
                                const camera_position_t *player,
                                uint16_t facing)
{
    (void)player;
    camera->distance = OOT_CAM_DIST_MAX;
    camera->yaw = facing;
    camera->pitch = OOT_CAM_PITCH_TARGET;
    camera->swing_timer = 0;
    camera->initialised = true;
    camera->look_active = false;
    camera->look_yaw = 0;
    camera->look_pitch = 0;
    camera->targeting = false;
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
    if (camera->swing_timer > 0)
    {
        /*
        ** Camera_Parallel1's turn, z_camera.c:2277:
        **
        **   tangle = ((animTimer + 1) * animTimer) / 2
        **   yaw   += ((target - yaw) / tangle) * animTimer
        **
        ** The denominator is the triangular number of the remaining steps, and
        ** the step is multiplied by the countdown, so each step covers a
        ** SMALLER share than the last and the turn eases out, arriving exactly
        ** as the timer expires.
        **
        ** A plain diff/remaining -- which this used to do -- gives a constant
        ** share of a shrinking remainder, which is a linear turn, not an ease.
        */
        int32_t n = camera->swing_timer;
        int32_t tangle = ((n + 1) * n) / 2;
        int16_t diff = (int16_t)(player_facing - camera->yaw);
        int32_t step = ((int32_t)diff / tangle) * n;

        /* Integer division truncates toward zero, so a small remaining angle
        ** would freeze short of the target. Finish the turn instead. */
        if (step == 0)
            camera->yaw = player_facing;
        else
            camera->yaw = (uint16_t)(camera->yaw + (int16_t)step);
        --camera->swing_timer;
    }
    else if (camera->targeting) {
        /* Link already faces the target. Keep the eye on that same axis even
         * while idle, strafing, or backing up. Normal1's rear-half suppression
         * and move-only yaw tracking must never apply to an active lock.
         * This is a behind-Link adaptation, not full KeepOn1 two-actor framing. */
        camera->yaw = player_facing;
    }
    else if (moving) {
        /* D-pad travel is camera-relative. Chasing facing in the rear half
         * makes Down a moving 180-degree target: rounding flips the chosen
         * turn direction every step. Hold yaw on rearward travel; explicit L
         * still turns above. Full Normal1 eye/at swing remains separate work. */
        int16_t heading = (int16_t)(player_facing - camera->yaw);
        if (heading >= -16384 && heading <= 16384)
            camera->yaw = angle_approach(camera->yaw, player_facing, YAW_RATE);
    }

    /* Distance eases between distMin and distMax rather than being fixed: the
    ** camera trails out to distMax while he runs and draws back in to distMin
    ** as he slows. */
    camera->distance = approach(camera->distance,
                                moving ? OOT_CAM_DIST_MAX : OOT_CAM_DIST_MIN,
                                XZ_RATE);
    camera->pitch = approach(camera->pitch, OOT_CAM_PITCH_TARGET, PITCH_RATE);

    if (camera->look_active && !camera->targeting)
    {
        /* Aim from a copy: the stored follow state is untouched, so the view
        ** returns to the ordinary follow camera the moment Z is released. */
        oot_follow_t aimed = *camera;

        aimed.yaw = (uint16_t)(camera->yaw + camera->look_yaw);
        aimed.pitch = camera->pitch + camera->look_pitch;
        place(&aimed, player, eye_out);
        *yaw_out = aimed.yaw;
        *pitch_out = legacy_camera ? 0 : -aimed.pitch;
        return;
    }
    place(camera, player, eye_out);
    *yaw_out = camera->yaw;
    /* Negated: kokiri_camera_update() adds CAMERA_PITCH_SPEED for Up, so a
    ** positive demo_pitch looks UP. The eye has been raised above the player,
    ** so the view has to look DOWN by the same angle for the at-point to stay
    ** on him. Getting this sign wrong puts Link off the bottom of the screen,
    ** which is why the previous camera avoided pitch entirely. */
    *pitch_out = legacy_camera ? 0 : -camera->pitch;
}
