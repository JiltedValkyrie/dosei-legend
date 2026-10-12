#pragma GCC optimize("Os") /* actor/state logic, not draw loops: size over speed (work RAM) */
/* Z-target attention: see attention.h. z_actor.c Attention_* in integers. */
#include "attention.h"
#include "gameplay.h"           /* gameplay_facing */

void        attention_focus(const actor_t *actor, int32_t out[3])
{
    out[0] = actor->x + actor->focus[0];
    out[1] = actor->y + actor->focus[1];
    out[2] = actor->z + actor->focus[2];
}

/* xyzDistToPlayerSq. False when too far to square safely: three squares
** under 37000^2 each sum below 2^32, far past every attention range. */
static bool dist_sq(const int32_t p[3], const actor_t *a, uint32_t *out)
{
    int32_t dx = a->x - p[0], dy = a->y - p[1], dz = a->z - p[2];
    if (dx <= -37000 || dx >= 37000 || dy <= -37000 || dy >= 37000 ||
        dz <= -37000 || dz >= 37000)
        return false;
    *out = (uint32_t)(dx * dx) + (uint32_t)(dy * dy) + (uint32_t)(dz * dz);
    return true;
}

static bool attention_enabled(const actor_t *a)
{
    return a && a->profile && !a->kill && (a->flags & ACTOR_FLAG_TARGETABLE) &&
           a->attention != ATTN_NONE;
}

actor_t    *attention_find(const int32_t feet[3], const int32_t focus[3],
                           uint16_t yaw, const actor_t *locked)
{
    actor_t *best = (actor_t *)0;
    uint32_t best_d = UINT32_MAX;
    unsigned int i;
    for (i = 0; i < ACTOR_POOL_MAX; ++i) {
        actor_t *a = actor_sys_slot(i);
        uint32_t d, w, range, minimum;
        int32_t turn, at[3];
        if (a == locked || !attention_enabled(a) || !dist_sq(feet, a, &d))
            continue;
        /* Avoid SGL atan for actors that cannot beat the current candidate
         * or enter their range. Locked weighting is 60--100% of d: d/2 is
         * a conservative cheap lower bound, with no multiply or divide. */
        range = actor_attention_range_sq(a);
        minimum = locked ? d >> 1 : d;
        if (minimum >= best_d || minimum >= range)
            continue;
        /* (yawTowardsPlayer - 0x8000) - shape.rot.y: the turn from Link's
        ** facing to the actor. */
        turn = (int16_t)(gameplay_facing(a->x - feet[0], a->z - feet[2]) - yaw);
        if (turn < 0) turn = -turn;
        if (locked) {
            /* Attention_WeightedDistToPlayerSq with a focus actor: up to 90
            ** degrees, distance scaled from 100% (90) down to 60% (0). */
            if (turn > 0x4000)
                continue;
            /* d * f * 0.8 / 0x8000 = d * f / 40960, split so every
            ** product stays in 32 bits (no 64-bit libgcc divide). */
            uint32_t f = (uint32_t)(0x4000 - turn);
            w = d - (d / 40960u) * f - ((d % 40960u) * f) / 40960u;
        } else {
            if (turn > 0x2AAA)             /* ~60 degrees */
                continue;
            w = d;
        }
        /* Every filter before the winner changes. */
        if (w >= best_d || w >= range)
            continue;
        attention_focus(a, at);
        if (!attention_on_screen(at) || attention_sight_blocked(focus, at))
            continue;
        best = a;
        best_d = w;
    }
    return best;
}

bool        attention_retains(const actor_t *actor, const int32_t feet[3])
{
    uint32_t d;
    return attention_enabled(actor) && dist_sq(feet, actor, &d) &&
           d < actor_attention_leash_sq(actor);
}

/* ---- Navi hover ---------------------------------------------------------- */

#define PLAYER_CATEGORY 0xFF
static int32_t          hover_q8[3];
static actor_handle_t   hover_id;
static uint8_t          hover_category = PLAYER_CATEGORY;
static uint8_t          progress;           /* naviMoveProgressFactor x 4 */
static uint8_t          step_phase;
static attention_colour_t colour;

static attention_colour_t colour_of(unsigned int category)
{
    if (category == PLAYER_CATEGORY) return ATTN_COLOUR_PLAYER;
    if (category == ACTORCAT_NPC) return ATTN_COLOUR_NPC;
    if (category == ACTORCAT_ENEMY || category == ACTORCAT_BOSS) return ATTN_COLOUR_ENEMY;
    return ATTN_COLOUR_OTHER;
}

void        attention_navi_reset(const int32_t focus[3])
{
    hover_q8[0] = focus[0] * 256;
    hover_q8[1] = (focus[1] + ATTENTION_PLAYER_ARROW) * 256;
    hover_q8[2] = focus[2] * 256;
    hover_id = ACTOR_HANDLE_NONE;
    hover_category = PLAYER_CATEGORY;
    progress = 0;
    step_phase = 0;
    colour = ATTN_COLOUR_PLAYER;
}

void        attention_navi_step(const int32_t feet[3], const int32_t focus[3],
                                const actor_t *hover)
{
    actor_handle_t id = hover ? actor_handle(hover) : ACTOR_HANDLE_NONE;
    uint8_t category = hover ? hover->profile->category : PLAYER_CATEGORY;
    unsigned int k;
    /* Source 20 Hz on the 30 Hz step: two updates in three. */
    step_phase = (uint8_t)(step_phase + 2);
    if (step_phase < 3)
        return;
    step_phase = (uint8_t)(step_phase - 3);
    if (id != hover_id || category != hover_category) {
        hover_id = id;
        hover_category = category;
        progress = 4;                       /* 1.0 */
    }
    if (progress)
        --progress;                         /* Math_StepToF(.., 0, 0.25) */
    if (progress) {
        /* In flight: toward world.pos + arrow (not focus: source quirk),
        ** 0.25 / factor of the remaining gap. */
        int32_t target[3];
        if (hover) {
            target[0] = hover->x;
            target[1] = hover->y + hover->arrow_y;
            target[2] = hover->z;
        } else {
            target[0] = feet[0];
            target[1] = feet[1] + ATTENTION_PLAYER_ARROW;
            target[2] = feet[2];
        }
        for (k = 0; k < 3; ++k)
            hover_q8[k] += (target[k] * 256 - hover_q8[k]) / (int32_t)progress;
        return;
    }
    /* Arrived: Attention_SetNaviState, focus.pos + arrow, category colour. */
    if (hover) {
        int32_t at[3];
        attention_focus(hover, at);
        hover_q8[0] = at[0] * 256;
        hover_q8[1] = (at[1] + hover->arrow_y) * 256;
        hover_q8[2] = at[2] * 256;
    } else {
        hover_q8[0] = focus[0] * 256;
        hover_q8[1] = (focus[1] + ATTENTION_PLAYER_ARROW) * 256;
        hover_q8[2] = focus[2] * 256;
    }
    colour = colour_of(category);
}

void        attention_navi_hover(int32_t out[3])
{
    out[0] = hover_q8[0] / 256;
    out[1] = hover_q8[1] / 256;
    out[2] = hover_q8[2] / 256;
}

bool        attention_navi_has_actor(void) { return hover_id != ACTOR_HANDLE_NONE; }
bool        attention_navi_moving(void)    { return progress != 0; }
attention_colour_t attention_navi_colour(void) { return colour; }
