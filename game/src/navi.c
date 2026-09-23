/* Navi, Link's companion fairy. Idle-follow behaviour from ovl_En_Elf. */
#include "navi.h"
#include "kokiri_camera.h"

/* Positions and velocities are Q8 world units: the source works in floats
 * whose fractions matter here, because one approach step is a fifth of the
 * remaining distance and would otherwise truncate to nothing. */
#define Q8(v)               ((int32_t)((v) * 256))
#define ORBIT_XZ            Q8(7.5)     /* unk_2B8, state 1 */
#define ORBIT_Y             Q8(5)       /* unk_2B4, state 1 */
#define ORBIT_STEP_XZ       0x800       /* unk_2B0 */
#define ORBIT_STEP_Y        0x1000      /* unk_2AE */
/* func_80A03148: (target - pos) * 0.2 horizontally, and func_80A02BD8's
 * 0.2 + 0.3 vertically, each approached at a fixed rate per source frame. */
#define VEL_STEP_XZ         Q8(5)
#define VEL_STEP_Y          Q8(32)
#define VEL_CAP_Y           Q8(20)
/* arg3 + 30.0f. The idle cap rerolls in 3..10 like unk_2A0; the catch-up
 * dash passes 20. */
#define SPEED_BASE          30
#define DASH_SPEED          (SPEED_BASE + 20)
/* The hover point is Link's HEAD, plus 1500.0f * the fairy's 0.008 scale.
 * Source: naviHoverPos is the player's focus (head) when nothing is targeted,
 * and func_80A03CF8 adds that rise on top of it.
 *
 * LINK_HEAD is measured from our own model: posing the idle frame's skeleton
 * puts limb 10, the head joint, 4291 model units up, which is 45 world units
 * over his feet at LINK_ANIM_SCALE_Q16 with LINK_ANIM_SHIFT_Y. It is NOT the
 * camera eye height (90): anchoring there floated her a head and a half above
 * him. tests/test_navi.py re-derives it from the generated clip data. */
#define LINK_HEAD           45
#define HOVER_RISE          12
/* Source thresholds on the distance to PLAYER_BODYPART_HAT. */
#define DASH_ENTER          100
#define DASH_LEAVE          30
/* En_Elf runs at the 20 Hz update rate; the caller steps at 30 Hz. */
#define STEP_NUM            2
#define STEP_DEN            3

static bool     active;
static int32_t  pos_q8[3];
static int32_t  vel_q8[3];
static uint16_t orbit_xz, orbit_y;
static bool     dashing, dash_cue;
static unsigned int timer, step_phase, speed_cap;
static uint32_t random_state;

static int32_t  isqrt32(int32_t value)
{
    int32_t root = 0, bit = 1 << 30;
    if (value <= 0) return (0);
    while (bit > value) bit >>= 2;
    while (bit) {
        if (value >= root + bit) { value -= root + bit; root = (root >> 1) + bit; }
        else root >>= 1;
        bit >>= 2;
    }
    return (root);
}

static int32_t  step_to(int32_t value, int32_t target, int32_t rate)
{
    if (target > value) { value += rate; if (value > target) value = target; }
    else if (target < value) { value -= rate; if (value < target) value = target; }
    return (value);
}

static void     hover_point(int32_t link_x, int32_t link_y, int32_t link_z,
                            int32_t *out)
{
    int32_t sine, cosine;
    kokiri_camera_sincos(orbit_xz, &sine, &cosine);
    out[0] = link_x * 256 + (int32_t)(((int64_t)sine * ORBIT_XZ) >> 16);
    out[2] = link_z * 256 + (int32_t)(((int64_t)cosine * ORBIT_XZ) >> 16);
    kokiri_camera_sincos(orbit_y, &sine, &cosine);
    out[1] = (link_y + LINK_HEAD + HOVER_RISE) * 256
             + (int32_t)(((int64_t)sine * ORBIT_Y) >> 16);
}

void            navi_reset(int32_t link_x, int32_t link_y, int32_t link_z)
{
    int32_t target[3];
    orbit_xz = 0;
    orbit_y = 0;
    timer = 0;
    step_phase = 0;
    dashing = false;
    dash_cue = false;
    speed_cap = SPEED_BASE + 5;
    random_state = 0x2A8u;
    hover_point(link_x, link_y, link_z, target);
    pos_q8[0] = target[0];
    pos_q8[1] = target[1];
    pos_q8[2] = target[2];
    vel_q8[0] = vel_q8[1] = vel_q8[2] = 0;
    active = true;
}

static void     update(int32_t link_x, int32_t link_y, int32_t link_z)
{
    int32_t target[3], want[3], head[3], distance, magnitude, cap;
    unsigned int axis;

    /* func_80A02A20 builds the offset from the CURRENT angles and advances
     * them afterwards. */
    hover_point(link_x, link_y, link_z, target);
    orbit_xz = (uint16_t)(orbit_xz + ORBIT_STEP_XZ);
    orbit_y = (uint16_t)(orbit_y + ORBIT_STEP_Y);

    /* Distance to Link, in whole units: the source compares it with 100 and
     * 30, so the fraction cannot change the outcome and the squares stay
     * inside 32 bits. */
    head[0] = link_x - pos_q8[0] / 256;
    head[1] = link_y + LINK_HEAD - pos_q8[1] / 256;
    head[2] = link_z - pos_q8[2] / 256;
    distance = isqrt32(head[0] * head[0] + head[1] * head[1] + head[2] * head[2]);

    if (dashing) {
        if (distance < DASH_LEAVE) dashing = false;
    } else if (distance > DASH_ENTER) {
        dashing = true;
        dash_cue = true;
    }
    if ((timer & 31) == 0) speed_cap = SPEED_BASE + 3 + (random_state >> 28) % 8;
    random_state = random_state * 1664525u + 1013904223u;
    ++timer;
    cap = (int32_t)(dashing ? DASH_SPEED : speed_cap);

    /* Horizontal: a fifth of the gap, capped as a LENGTH so a diagonal catch
     * up is not faster than a straight one, then eased into. */
    want[0] = (target[0] - pos_q8[0]) / 5;
    want[2] = (target[2] - pos_q8[2]) / 5;
    magnitude = isqrt32((want[0] / 256) * (want[0] / 256) +
                        (want[2] / 256) * (want[2] / 256));
    if (magnitude > cap) {
        want[0] = (int32_t)(((int64_t)want[0] * cap) / magnitude);
        want[2] = (int32_t)(((int64_t)want[2] * cap) / magnitude);
    }
    want[1] = (target[1] - pos_q8[1]) / 2;
    if (want[1] > VEL_CAP_Y) want[1] = VEL_CAP_Y;
    if (want[1] < -VEL_CAP_Y) want[1] = -VEL_CAP_Y;

    vel_q8[0] = step_to(vel_q8[0], want[0], VEL_STEP_XZ);
    vel_q8[2] = step_to(vel_q8[2], want[2], VEL_STEP_XZ);
    vel_q8[1] = step_to(vel_q8[1], want[1], VEL_STEP_Y);
    for (axis = 0; axis < 3; ++axis) pos_q8[axis] += vel_q8[axis];
}

void            navi_step(int32_t link_x, int32_t link_y, int32_t link_z)
{
    if (!active) { navi_reset(link_x, link_y, link_z); return; }
    dash_cue = false;
    step_phase += STEP_NUM;
    while (step_phase >= STEP_DEN) {
        step_phase -= STEP_DEN;
        update(link_x, link_y, link_z);
    }
}

bool            navi_active(void)   { return (active); }
int32_t         navi_x(void)        { return (pos_q8[0] / 256); }
int32_t         navi_y(void)        { return (pos_q8[1] / 256); }
int32_t         navi_z(void)        { return (pos_q8[2] / 256); }
bool            navi_dash_started(void) { return (dash_cue); }
