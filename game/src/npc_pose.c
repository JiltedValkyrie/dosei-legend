#include "npc_pose.h"

/* Per-NPC, 20 Hz: size over speed (work RAM). Only the per-vertex
 * npc_limb_transform keeps -O2. */
#define COLD __attribute__((optimize("Os")))

void npc_limb_transform(int32_t p[3], const int16_t basis[9], const int16_t origin[3],
                        int32_t pivot, const int16_t rot[9])
{
    int32_t d[3], local[3], turned[3];
    unsigned int i;
    for (i = 0; i < 3; ++i) d[i] = p[i] - origin[i];
    for (i = 0; i < 3; ++i)
        local[i] = (basis[i] * d[0] + basis[3+i] * d[1] + basis[6+i] * d[2]) / 16384;
    local[0] -= pivot;
    for (i = 0; i < 3; ++i)
        turned[i] = (rot[i*3] * local[0] + rot[i*3+1] * local[1] + rot[i*3+2] * local[2]) / 16384;
    turned[0] += pivot;
    for (i = 0; i < 3; ++i)
        p[i] = origin[i] + (basis[i*3] * turned[0] + basis[i*3+1] * turned[1] +
                            basis[i*3+2] * turned[2]) / 16384;
}

COLD static void axis_matrix(int32_t m[9], unsigned int axis, int32_t s, int32_t c)
{
    unsigned int u = (axis + 1) % 3, v = (axis + 2) % 3, i;
    for (i = 0; i < 9; ++i) m[i] = 0;
    m[axis*3 + axis] = 16384;
    m[u*3 + u] = c; m[u*3 + v] = -s;
    m[v*3 + u] = s; m[v*3 + v] = c;
}

COLD void npc_rot_matrix(int16_t rot[9], unsigned int a, int32_t sa, int32_t ca,
                    unsigned int b, int32_t sb, int32_t cb)
{
    int32_t ma[9], mb[9];
    unsigned int r, c;
    axis_matrix(ma, a, sa, ca);
    axis_matrix(mb, b, sb, cb);
    for (r = 0; r < 3; ++r)
        for (c = 0; c < 3; ++c)
            rot[r*3+c] = (int16_t)((ma[r*3] * mb[c] + ma[r*3+1] * mb[3+c] +
                                    ma[r*3+2] * mb[6+c]) / 16384);
}

COLD int16_t npc_smooth_step(int16_t *value, int16_t target, int16_t scale,
                        int16_t step, int16_t min_step)
{
    int16_t diff = (int16_t)(target - *value);
    if (*value != target) {
        int16_t size = (int16_t)(diff / scale);
        if (size > min_step || size < -min_step) {
            if (size > step) size = step;
            if (size < -step) size = (int16_t)-step;
            *value = (int16_t)(*value + size);
        } else if (diff >= 0) {
            *value = (int16_t)(*value + min_step);
            if ((int16_t)(target - *value) <= 0) *value = target;
        } else {
            *value = (int16_t)(*value - min_step);
            if ((int16_t)(target - *value) >= 0) *value = target;
        }
    }
    return diff;
}

/* sNpcTrackingPresets rotLimits (z_actor.c): maxHeadYaw, minHeadPitch,
 * maxHeadPitch, maxTorsoYaw, minTorsoPitch, maxTorsoPitch; rotateYaw is
 * true in every preset. */
static const int16_t presets[13][6] = {
    { 0x2AA8, -0x0E38, 0x18E2, 0x1554, 0x0000, 0x0000 },
    { 0x2AA8, -0x1554, 0x1554, 0x1554, -0x071C, 0x0E38 },
    { 0x31C4, -0x1C70, 0x0E38, 0x0E38, -0x0E38, 0x071C },
    { 0x1554, -0x0E38, 0x0000, 0x071C, -0x071C, 0x0000 },
    { 0x2AA8, -0x071C, 0x071C, 0x0E38, -0x2AA8, 0x2AA8 },
    { 0x0000, -0x1C70, 0x2AA8, 0x3FFC, -0x0E38, 0x0E38 },
    { 0x2AA8, -0x0E38, 0x0E38, 0x0E38, 0x0000, 0x0000 },
    { 0x2AA8, -0x0E38, 0x0000, 0x0E38, 0x0000, 0x1C70 },
    { 0x2AA8, -0x0E38, -0x0E38, 0x0000, 0x0000, 0x0000 },
    { 0x071C, -0x0E38, 0x0E38, 0x1C70, 0x0000, 0x0000 },
    { 0x0E38, -0x0E38, 0x0000, 0x1C70, 0x0000, 0x0E38 },
    { 0x2AA8, -0x1C70, 0x1C70, 0x0E38, -0x0E38, 0x0E38 },
    { 0x18E2, -0x0E38, 0x0E38, 0x0E38, 0x0000, 0x0000 },
};

COLD static int32_t clamp(int32_t v, int32_t lo, int32_t hi)
{
    return v < lo ? lo : v > hi ? hi : v;
}

COLD static int32_t magnitude(int16_t v)
{
    int32_t a = v < 0 ? -(int32_t)v : v;
    return a >= 0x8000 ? 0 : a;
}

/* Npc_TrackPoint + Npc_TrackPointWithLimits. */
COLD void npc_track_point(npc_track_t *t, uint16_t *shape_yaw, int16_t yaw_to,
                     int16_t pitch_to, unsigned int preset, unsigned int mode)
{
    int32_t head_yaw, head_lo, head_hi, torso_yaw, torso_lo, torso_hi, m;
    int16_t body, pitch, shape;
    const int16_t *l = presets[preset < 13 ? preset : 2];
    head_yaw = l[0]; head_lo = l[1]; head_hi = l[2];
    torso_yaw = l[3]; torso_lo = l[4]; torso_hi = l[5];
    if (mode == NPC_TRACKING_NONE) head_yaw = head_lo = head_hi = 0;
    if (mode == NPC_TRACKING_NONE || mode == NPC_TRACKING_HEAD)
        torso_yaw = torso_lo = torso_hi = 0;

    body = (int16_t)(yaw_to - (int16_t)*shape_yaw);
    npc_smooth_step(&t->head[1], (int16_t)clamp(body, -head_yaw, head_yaw), 6, 2000, 1);
    m = magnitude(body);
    t->head[1] = (int16_t)clamp(t->head[1], -m, m);
    body = (int16_t)(body - t->head[1]);
    npc_smooth_step(&t->torso[1], (int16_t)clamp(body, -torso_yaw, torso_yaw), 6, 2000, 1);
    m = magnitude(body);
    t->torso[1] = (int16_t)clamp(t->torso[1], -m, m);
    if (mode == NPC_TRACKING_FULL_BODY) {
        shape = (int16_t)*shape_yaw;
        npc_smooth_step(&shape, yaw_to, 6, 2000, 1);
        *shape_yaw = (uint16_t)shape;
    }
    pitch = pitch_to;
    npc_smooth_step(&t->head[0], (int16_t)clamp(pitch, head_lo, head_hi), 6, 2000, 1);
    pitch = (int16_t)(pitch - t->head[0]);
    npc_smooth_step(&t->torso[0], (int16_t)clamp(pitch, torso_lo, torso_hi), 6, 2000, 1);
}
