#pragma GCC optimize("Os") /* actor/state logic, not draw loops: size over speed (work RAM) */
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
/* The anchor the caller passes is the player's focus.pos: the head limb
 * times sPlayerFocusOffsetFromHead (1100, -700, 0), link_anim_focus(). With
 * nothing targeted Attention_SetNaviState makes naviHoverPos that point plus
 * lockOnArrowOffset (500) * the player's 0.01 scale, and func_80A03CF8 adds
 * 1500.0f * the fairy's 0.008 scale on top. The old fixed 46 (head JOINT
 * over the feet) sat about 16 units low. */
#define ARROW_OFFSET        5
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
/* En_Elf func_80A04414 colour hand-off: unk_2C6 (arrived) and unk_29C
** (fade, quarters). VDP1 has three baked glow sets, so the colour swaps when
** the source fade would end instead of blending (logged gap). */
static bool     hover_moving, colour_arrived;
static unsigned int colour_fade, colour_shown, colour_want;
/* Q8 position/velocity; 0 life = free slot. */
typedef struct { int32_t pos[3]; int16_t vel[3], accel_y; uint16_t yaw; uint8_t life; } sparkle_t;
static sparkle_t sparkles[NAVI_SPARKLES];

static uint32_t random_next(void)
{
    random_state = random_state * 1664525u + 1013904223u;
    return random_state >> 8;
}

/* Rand_ZeroOne() * range in Q8, 0..range. */
static int32_t  random_q8(int32_t range_q8)
{
    return (int32_t)((random_next() & 0xFFFF) * (uint32_t)range_q8 >> 16);
}

/* EnElf_SpawnSparkles + EffectSsKiraKira_SpawnDispersed + func_809AABF0,
** per source update. Velocity (0,-0.05,0) and accel (0,-0.025,0) are
** randomised to [v, v/2]; x/z accel rerolls in +-0.2 every update; yaw
** starts at rand * 0x4000 and turns 0x1518 an update. */
static void     sparkles_update(void)
{
    unsigned int i, k;
    for (i = 0; i < NAVI_SPARKLES; ++i) {
        sparkle_t *s = &sparkles[i];
        if (!s->life)
            continue;
        if (--s->life == 0)
            continue;
        s->vel[0] = (int16_t)(s->vel[0] + random_q8(Q8(0.4)) - Q8(0.2));
        s->vel[2] = (int16_t)(s->vel[2] + random_q8(Q8(0.4)) - Q8(0.2));
        s->vel[1] = (int16_t)(s->vel[1] + s->accel_y);
        for (k = 0; k < 3; ++k)
            s->pos[k] += s->vel[k];
        s->yaw = (uint16_t)(s->yaw + 0x1518);
    }
    for (i = 0; i < NAVI_SPARKLES; ++i)
        if (!sparkles[i].life)
            break;
    if (i == NAVI_SPARKLES)
        return;
    {
        sparkle_t *s = &sparkles[i];
        s->pos[0] = pos_q8[0] + random_q8(Q8(6)) - Q8(3);     /* Rand_CenteredFloat(6) */
        s->pos[1] = pos_q8[1] + random_q8(Q8(6));             /* Rand_ZeroOne() * 6 */
        s->pos[2] = pos_q8[2] + random_q8(Q8(6)) - Q8(3);
        s->vel[0] = s->vel[2] = 0;
        s->vel[1] = (int16_t)(-(random_q8(Q8(0.05)) + Q8(0.05)) / 2);
        s->accel_y = (int16_t)(-(random_q8(Q8(0.025)) + Q8(0.025)) / 2);
        s->yaw = (uint16_t)(random_next() & 0x3FFF);
        s->life = NAVI_SPARKLE_LIFE;
    }
}

bool            navi_sparkle(unsigned int i, int32_t pos[3], uint16_t *yaw, unsigned int *life)
{
    if (!active || i >= NAVI_SPARKLES || !sparkles[i].life)
        return false;
    pos[0] = sparkles[i].pos[0] / 256;
    pos[1] = sparkles[i].pos[1] / 256;
    pos[2] = sparkles[i].pos[2] / 256;
    *yaw = sparkles[i].yaw;
    *life = sparkles[i].life;
    return true;
}

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

/* anchor = naviHoverPos (focus + lockOnArrowOffset x scale). */
static void     hover_point(int32_t link_x, int32_t link_y, int32_t link_z,
                            int32_t *out)
{
    int32_t sine, cosine;
    kokiri_camera_sincos(orbit_xz, &sine, &cosine);
    out[0] = link_x * 256 + (int32_t)(((int64_t)sine * ORBIT_XZ) >> 16);
    out[2] = link_z * 256 + (int32_t)(((int64_t)cosine * ORBIT_XZ) >> 16);
    kokiri_camera_sincos(orbit_y, &sine, &cosine);
    out[1] = (link_y + HOVER_RISE) * 256
             + (int32_t)(((int64_t)sine * ORBIT_Y) >> 16);
}

void            navi_reset(int32_t link_x, int32_t link_y, int32_t link_z)
{
    int32_t target[3];
    link_y += ARROW_OFFSET;
    unsigned int i;
    orbit_xz = 0;
    orbit_y = 0;
    timer = 0;
    step_phase = 0;
    dashing = false;
    dash_cue = false;
    speed_cap = SPEED_BASE + 5;
    random_state = 0x2A8u;
    hover_moving = colour_arrived = false;
    colour_fade = 0;
    colour_shown = colour_want = 0;
    hover_point(link_x, link_y, link_z, target);
    pos_q8[0] = target[0];
    pos_q8[1] = target[1];
    pos_q8[2] = target[2];
    vel_q8[0] = vel_q8[1] = vel_q8[2] = 0;
    for (i = 0; i < NAVI_SPARKLES; ++i)
        sparkles[i].life = 0;
    active = true;
}

/* anchor: naviHoverPos. hat: PLAYER_BODYPART_HAT (~ Link focus). */
static void     update(const int32_t anchor[3], const int32_t hat[3], bool has_actor)
{
    int32_t link_x = anchor[0], link_y = anchor[1], link_z = anchor[2];
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
    head[0] = hat[0] - pos_q8[0] / 256;
    head[1] = hat[1] - pos_q8[1] / 256;
    head[2] = hat[2] - pos_q8[2] / 256;
    distance = isqrt32(head[0] * head[0] + head[1] * head[1] + head[2] * head[2]);

    /* func_80A03CF8 default case: with a hover actor she flies straight at
    ** func_80A03148(.., 20) and the idle dash rule does not run. */
    if (has_actor) {
        dashing = false;
    } else if (dashing) {
        if (distance < DASH_LEAVE) dashing = false;
    } else if (distance > DASH_ENTER) {
        dashing = true;
        dash_cue = true;
    }
    if ((timer & 31) == 0) speed_cap = SPEED_BASE + 3 + (random_state >> 28) % 8;
    random_state = random_state * 1664525u + 1013904223u;
    ++timer;
    cap = (int32_t)(dashing || has_actor ? DASH_SPEED : speed_cap);

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
    sparkles_update();
}

static void     colour_update(const int32_t anchor[3], bool has_actor, bool moving)
{
    if (moving) {
        colour_arrived = false;
        colour_fade = 4;
        return;
    }
    if (!colour_arrived) {
        int32_t d[3], k;
        for (k = 0; k < 3; ++k) {
            d[k] = pos_q8[k] / 256 - anchor[k];
            if (d[k] < 0) d[k] = -d[k];
        }
        if (!has_actor || (d[0] < 50 && d[1] < 50 && d[2] < 50 &&
                           d[0] * d[0] + d[1] * d[1] + d[2] * d[2] < 2500))
            colour_arrived = true;
    } else if (colour_fade && --colour_fade == 0) {
        colour_shown = colour_want;
    }
}

void            navi_step(int32_t link_x, int32_t link_y, int32_t link_z)
{
    int32_t anchor[3] = { link_x, link_y + ARROW_OFFSET, link_z };
    int32_t hat[3] = { link_x, link_y, link_z };
    if (!active) { navi_reset(link_x, link_y, link_z); return; }
    dash_cue = false;
    step_phase += STEP_NUM;
    while (step_phase >= STEP_DEN) {
        step_phase -= STEP_DEN;
        update(anchor, hat, false);
    }
}

void            navi_step_hover(const int32_t hover[3], const int32_t hat[3],
                                bool has_actor, bool moving, unsigned int colour)
{
    if (!active) { navi_reset(hat[0], hat[1], hat[2]); return; }
    dash_cue = false;
    /* func_80A04414: FAIRY_DASH while naviMoveProgressFactor runs. */
    if (moving && !hover_moving)
        dash_cue = true;
    hover_moving = moving;
    colour_want = colour;
    step_phase += STEP_NUM;
    while (step_phase >= STEP_DEN) {
        step_phase -= STEP_DEN;
        update(hover, hat, has_actor);
        colour_update(hover, has_actor, moving);
    }
}

unsigned int    navi_colour(void)   { return (colour_shown); }

bool            navi_active(void)   { return (active); }
int32_t         navi_x(void)        { return (pos_q8[0] / 256); }
int32_t         navi_y(void)        { return (pos_q8[1] / 256); }
int32_t         navi_z(void)        { return (pos_q8[2] / 256); }
bool            navi_dash_started(void) { return (dash_cue); }
