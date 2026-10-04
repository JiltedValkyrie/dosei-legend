/*
** OoT Normal1 follow camera, in fixed point.
**
** Derivation of the constants in the header, from Camera_Normal1() and
** sSetNormal0ModeNormalData:
**
**   playerHeight            44      (Player_GetHeight, child)
**   CAM_YOFFSET_NORM        -0.1
**   yNormal = 1 + (-0.1) - (-0.1 * (68/44))            = 1.05455
**   scale   = yNormal * (44 * 0.01)                    = 0.46400
**
**   yOffset  -20 * 0.464 =  -9.28  -> -9
**   distMin  200 * 0.464 =  92.80  -> 93
**   distMax  300 * 0.464 = 139.20  -> 139
**
** 44 is Player_GetHeight (child). An earlier 62 matched a Link baked at
** 1.45x the source scale; BUG-009 put the model back at 0.01.
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

oot_follow_scale_t oot_follow_scale = {44, 93, 139, -9};

void oot_follow_set_adult(bool adult)
{
    /* Adult Player_GetHeight=68, yNormal=1: source scale is exactly .68.
    ** Precomputed integers avoid division in the camera's hot path. */
    oot_follow_scale = adult ? (oot_follow_scale_t){68,136,204,-14} :
                              (oot_follow_scale_t){44,93,139,-9};
}

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

/* Keeps each squared axis below 2^30 so the sum fits 32 bits. */
static int32_t  clamp_axis(int32_t v)
{
    return v > 30000 ? 30000 : v < -30000 ? -30000 : v;
}

static uint32_t isqrt_u32(uint32_t v)
{
    uint32_t r = 0, bit = 1u << 30;
    while (bit > v) bit >>= 2;
    while (bit) {
        if (v >= r + bit) { v -= r + bit; r = (r >> 1) + bit; }
        else r >>= 1;
        bit >>= 2;
    }
    return r;
}

void            oot_follow_aim(oot_follow_t *camera, const int32_t *focus,
                               int32_t distance, bool off_ground)
{
    camera->aim_active = focus != 0 && distance > 0;
    if (!camera->aim_active)
        return;
    camera->aim_focus[0] = focus[0];
    camera->aim_focus[1] = focus[1];
    camera->aim_focus[2] = focus[2];
    camera->aim_distance = distance;
    camera->aim_off_ground = off_ground;
}

/* Target at-offset, Q8, from the player's head toward the lock focus. */
static void     aim_target(const oot_follow_t *camera,
                           const camera_position_t *player, int32_t out[3])
{
    int32_t v[3], k, scale_q16;
    uint32_t r;
    if (!camera->aim_active || !camera->targeting) {
        out[0] = out[1] = out[2] = 0;
        return;
    }
    v[0] = camera->aim_focus[0] - player->x;
    v[1] = camera->aim_focus[1] - (player->y - OOT_CAM_PLAYER_ORIGIN + oot_follow_scale.height);
    v[2] = camera->aim_focus[2] - player->z;
    for (k = 0; k < 3; ++k) v[k] = clamp_axis(v[k]);
    r = isqrt_u32((uint32_t)(v[0] * v[0]) + (uint32_t)(v[1] * v[1]) + (uint32_t)(v[2] * v[2]));
    /* CAM_GLOBAL_38 0.15, CAM_GLOBAL_39 0.75 (z_camera.c, retail). */
    if ((int32_t)r > camera->aim_distance)
        scale_q16 = 9830;
    else
        scale_q16 = 49152 - (int32_t)(39322u * r / (uint32_t)camera->aim_distance);
    if (camera->aim_off_ground)
        scale_q16 /= 5;
    for (k = 0; k < 3; ++k)
        out[k] = (int32_t)(((int64_t)v[k] * scale_q16) >> 8);
}

/*
** Camera_KeepOn1 / Camera_Battle1 lock framing (z_camera.c), integer port.
** The camera does NOT sit straight behind Link: it keeps the target
** swingAngle degrees off the view centre (25..45 friendly, 10..80 hostile,
** wider as the target gets closer), so Link never hides it.
**
**   swingAngle = init + (final - init) * (1.1 - distRatio)
**   |off| > swingAngle: view turns toward it by off^2 / t1 degrees, t1 the
**                       source's curve through (t2, 1 degree);
**   otherwise:          view drifts so the target settles AT swingAngle,
**                       by (swing - off) * 0.02 (0.05 hostile) while still.
**   pitch = lerp(pitchInit, pitchFinal, distRatio)
**         - headToTarget.pitch * (0.5 + 0.5 distRatio)
**         + atToTarget.pitch * swingPitchAdj, clamped.
** Rates are the 20 Hz source's, scaled x2/3 for this 30 Hz step. The
** animTimer eye blend on lock start stays the Parallel1 recenter swing.
** sSetNormal0ModeZTargetFriendlyData (KEEP1) -20,120,140, yaw 25/45,
** pitch -5/15, adj 15%; ZTargetUnfriendly (BATT1) -20,180, yaw 10/80,
** pitch 0/10, adj 25%.
*/
typedef struct {
    int32_t dist_min, dist_max, yaw_init, yaw_final, pitch_init, pitch_final;
    int32_t adj_percent, drift_per_150, pitch_limit;
} lock_frame_t;
static const lock_frame_t lock_friendly = {120, 140, 25, 45, -5, 15, 15, 2, 0x3200};
static const lock_frame_t lock_hostile  = {180, 180, 10, 80, 0, 10, 25, 5, 0x2AA8};

__attribute__((optimize("Os")))  /* once a step: size over speed */
static uint16_t geo_pitch(int32_t dx, int32_t dy, int32_t dz)
{
    dx = clamp_axis(dx); dz = clamp_axis(dz);
    return kokiri_camera_facing(dy, (int32_t)isqrt_u32((uint32_t)(dx * dx) + (uint32_t)(dz * dz)));
}

__attribute__((optimize("Os")))
static void     lock_frame(oot_follow_t *camera, const camera_position_t *player,
                           bool moving)
{
    const lock_frame_t *m = camera->aim_distance >= OOT_CAM_LOCK_DIST_UNFRIENDLY ?
                            &lock_hostile : &lock_friendly;
    int32_t at[3], v[3], k, ratio, swing, want, ring;
    int32_t off, ec, t2, temp, t1, f;                                /* Q8 degrees */
    uint32_t r_head, r_at;
    int16_t x;
    int32_t head_y = player->y - OOT_CAM_PLAYER_ORIGIN + oot_follow_scale.height;

    at[0] = player->x + camera->aim_q8[0] / 256;
    at[1] = head_y + camera->aim_q8[1] / 256;
    at[2] = player->z + camera->aim_q8[2] / 256;
    /* distRatio: player head -> target over the mode distance. */
    for (k = 0; k < 3; ++k)
        v[k] = clamp_axis(camera->aim_focus[k] - (k == 1 ? head_y : k ? player->z : player->x));
    r_head = isqrt_u32((uint32_t)(v[0]*v[0]) + (uint32_t)(v[1]*v[1]) + (uint32_t)(v[2]*v[2]));
    ratio = (int32_t)r_head >= m->dist_min ? 65536 :
            (int32_t)((r_head << 16) / (uint32_t)m->dist_min);
    swing = (int32_t)(m->yaw_final - m->yaw_init);
    ec = m->yaw_init * 256 + (swing * (72090 - ratio)) / 256;

    /* Distance: KeepOn1 clamps into [eyeDist, eyeDistNext]; Battle1 fixed. */
    want = camera->distance < m->dist_min ? m->dist_min :
           camera->distance > m->dist_max ? m->dist_max : camera->distance;
    camera->distance = approach(camera->distance, want, 25);  /* CAM_GLOBAL_11 */

    for (k = 0; k < 3; ++k) v[k] = clamp_axis(camera->aim_focus[k] - at[k]);
    r_at = isqrt_u32((uint32_t)(v[0]*v[0]) + (uint32_t)(v[1]*v[1]) + (uint32_t)(v[2]*v[2]));
    x = (int16_t)(kokiri_camera_facing(v[0], v[2]) - camera->yaw);
    off = (int32_t)x * 360 / 256;
    if ((off < 0 ? -off : off) > ec) {
        /* atToTarget.r = dist - min(r, dist) * 0.5, ClampMaxDist'd by dist. */
        int32_t d = camera->distance > 0 ? camera->distance : 1;
        int32_t rr = d - (int32_t)(r_at < (uint32_t)d ? r_at : (uint32_t)d) / 2;
        t2 = ec + 10 * 256 * rr / d;                                 /* CAM_GLOBAL_13 */
        temp = ((t2 * t2 / 256) - 2 * 256) * 256 / (t2 - 360 * 256);
        t1 = temp * off / 256 + 2 * 256 - 360 * temp;
        if (t1 < 16) t1 = 16;
        f = (off / 16) * (off / 16);                                 /* off^2, Q8 */
        f = (f * 16) / (t1 / 16) * 2 / 3;
        ring = f * 256 / 360;                                        /* binang */
        camera->yaw = (uint16_t)(camera->yaw + (x >= 0 ? ring : -ring));
    } else if (!moving) {
        int32_t edge = ec * 256 / 360;                               /* binang */
        int32_t diff = (x >= 0 ? edge : -edge) - x;
        camera->yaw = (uint16_t)(camera->yaw - diff * m->drift_per_150 * 2 / 150);
    }

    /* Pitch, at -> eye, positive above. */
    {
        int32_t base = (m->pitch_init * 65536 +
                        (m->pitch_final - m->pitch_init) * ratio) / 360;  /* binang */
        int16_t p_head = (int16_t)geo_pitch(camera->aim_focus[0] - player->x,
                                            camera->aim_focus[1] - head_y,
                                            camera->aim_focus[2] - player->z);
        int16_t p_at = (int16_t)geo_pitch(v[0], v[1], v[2]);
        int32_t target = base - (p_head * ((32768 + ratio / 2) >> 4)) / 4096
                       + p_at * m->adj_percent / 100;
        if (target < -m->pitch_limit) target = -m->pitch_limit;
        if (target > m->pitch_limit) target = m->pitch_limit;
        camera->pitch = approach(camera->pitch, target, 15);          /* CAM_GLOBAL_12 */
    }
}

static void     place(const oot_follow_t *camera,
                      const camera_position_t *player,
                      camera_position_t *eye_out, int32_t y_offset)
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
    eye_out->y = player->y - OOT_CAM_PLAYER_ORIGIN + oot_follow_scale.height
                + y_offset + height;
    eye_out->x += camera->aim_q8[0] / 256;
    eye_out->y += camera->aim_q8[1] / 256;
    eye_out->z += camera->aim_q8[2] / 256;
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
    camera->distance = oot_follow_scale.distance_max;
    camera->yaw = facing;
    camera->pitch = OOT_CAM_PITCH_TARGET;
    camera->swing_timer = 0;
    camera->initialised = true;
    camera->look_active = false;
    camera->look_yaw = 0;
    camera->look_pitch = 0;
    camera->targeting = false;
    camera->aim_q8[0] = camera->aim_q8[1] = camera->aim_q8[2] = 0;
    camera->aim_active = false;
}

void            oot_follow_update_profile(oot_follow_t *camera,
                                  const camera_position_t *player,
                                  uint16_t player_facing, bool moving,
                                  camera_position_t *eye_out,
                                  uint16_t *yaw_out, int32_t *pitch_out,
                                  const oot_follow_profile_t *profile)
{
    if (!camera->initialised)
        oot_follow_snap(camera, player, player_facing);

    /* Normal1 only swings back behind the player while he is actually moving
    ** (xzSpeed > 0.001). Standing still holds the current yaw, which is what
    ** keeps the view from drifting on its own. */
    if (profile->yaw_policy) {
        camera->swing_timer = 0;
        if (profile->yaw_policy == 1)
            camera->yaw = angle_approach(camera->yaw, player_facing, 3);
    }
    else if (camera->swing_timer > 0 && !(camera->targeting && camera->aim_active))
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
    else if (camera->targeting && camera->aim_active) {
        /* KeepOn1 / Battle1 two-actor framing: see lock_frame. It starts from
         * the current eye (source animTimer blend), not a behind-Link swing. */
        camera->swing_timer = 0;
        lock_frame(camera, player, moving);
    }
    else if (camera->targeting) {
        /* Parallel lock without a target: hold Link's facing. */
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
    ** as he slows. Climbing retains the far end of the same source range:
    ** stopping on vines must not pull the eye into Link and the wall. */
    if (!(camera->targeting && camera->aim_active && !profile->yaw_policy)) {
        camera->distance = approach(camera->distance,
                                    profile->yaw_policy == 1 ? oot_follow_scale.distance_max * 3 / 2 :
                                    moving ? oot_follow_scale.distance_max : oot_follow_scale.distance_min,
                                    XZ_RATE);
        camera->pitch = approach(camera->pitch, profile->pitch_target, profile->pitch_rate);
    }
    {
        /* Battle1 xyz offset rate 0.6 a 20 Hz update ~ 0.45 a 30 Hz step. */
        int32_t want[3], k;
        aim_target(camera, player, want);
        for (k = 0; k < 3; ++k) {
            int32_t step = (want[k] - camera->aim_q8[k]) * 9 / 20;
            /* Truncation would stall short of the target: finish instead. */
            camera->aim_q8[k] = step ? camera->aim_q8[k] + step : want[k];
        }
    }

    if (camera->look_active && !camera->targeting && !profile->yaw_policy)
    {
        /* Aim from a copy: the stored follow state is untouched, so the view
        ** returns to the ordinary follow camera the moment Z is released. */
        oot_follow_t aimed = *camera;

        aimed.yaw = (uint16_t)(camera->yaw + camera->look_yaw);
        aimed.pitch = camera->pitch + camera->look_pitch;
        place(&aimed, player, eye_out, profile->y_offset);
        *yaw_out = aimed.yaw;
        *pitch_out = legacy_camera ? 0 : -aimed.pitch;
        return;
    }
    place(camera, player, eye_out, profile->y_offset);
    *yaw_out = camera->yaw;
    /* Negated: kokiri_camera_update() adds CAMERA_PITCH_SPEED for Up, so a
    ** positive demo_pitch looks UP. The eye has been raised above the player,
    ** so the view has to look DOWN by the same angle for the at-point to stay
    ** on him. Getting this sign wrong puts Link off the bottom of the screen,
    ** which is why the previous camera avoided pitch entirely. */
    *pitch_out = legacy_camera ? 0 : -camera->pitch;
}

void oot_follow_update(oot_follow_t *camera, const camera_position_t *player,
                      uint16_t facing, bool moving, camera_position_t *eye,
                      uint16_t *yaw, int32_t *pitch)
{
    const oot_follow_profile_t normal = {oot_follow_scale.y_offset, OOT_CAM_PITCH_TARGET,
                                         PITCH_RATE, 0};
    oot_follow_update_profile(camera, player, facing, moving, eye, yaw, pitch, &normal);
}
