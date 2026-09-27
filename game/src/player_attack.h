#ifndef DOSEI_PLAYER_ATTACK_H
#define DOSEI_PLAYER_ATTACK_H
#include <stdint.h>
#include "collide.h"

/* Source PLAYER_MWA_* IDs, one-handed child subset. These are NOT clip indices.
 * D_80854190 supplies active_from and active_through to func_8084285C.
 * Negative weapon state enables the trail but not the damaging quads.
 * Tables are a contract for M2b/c; the old gameplay swing is not replaced yet. */
enum {
    ATTACK_FORWARD = 0, ATTACK_FORWARD_COMBO = 2,
    ATTACK_RIGHT = 4, ATTACK_RIGHT_COMBO = 6,
    ATTACK_LEFT = 8, ATTACK_LEFT_COMBO = 10,
    ATTACK_STAB = 12, ATTACK_STAB_COMBO = 14,
    ATTACK_FLIP_START = 16, ATTACK_JUMP_START = 17,
    ATTACK_FLIP_FINISH = 18, ATTACK_JUMP_FINISH = 19,
    ATTACK_BACK_RIGHT = 20, ATTACK_BACK_LEFT = 21, ATTACK_SPIN = 24,
    ATTACK_BIG_SPIN = 26
};
typedef struct { uint8_t source_id, active_from, active_through; } player_attack_spec_t;
static const player_attack_spec_t player_attack_specs[] = {
    {ATTACK_FORWARD,1,4}, {ATTACK_FORWARD_COMBO,0,5},
    {ATTACK_RIGHT,1,4}, {ATTACK_RIGHT_COMBO,2,8},
    {ATTACK_LEFT,0,4}, {ATTACK_LEFT_COMBO,0,6},
    {ATTACK_STAB,0,3}, {ATTACK_STAB_COMBO,1,9},
    {ATTACK_FLIP_START,1,10}, {ATTACK_JUMP_START,1,11},
    {ATTACK_FLIP_FINISH,1,2}, {ATTACK_JUMP_FINISH,1,2},
    {ATTACK_BACK_RIGHT,1,5}, {ATTACK_BACK_LEFT,1,4}, {ATTACK_SPIN,0,12},
    {ATTACK_BIG_SPIN,0,16}
};

static inline const player_attack_spec_t *player_attack_spec(unsigned int id)
{
    unsigned int i;
    for (i=0; i<sizeof(player_attack_specs)/sizeof(player_attack_specs[0]); ++i)
        if (player_attack_specs[i].source_id == id) return &player_attack_specs[i];
    return 0;
}

/* Frame in thirds avoids rounding the adjusted 2/3-frame-per-30Hz-step rate.
 * Contact uses the same action frame as pose sampling, not a render counter.
 * Airborne jump slash has its own action override (6,7,99); do not use the
 * ordinary table's start row until the corresponding ground action owns it. */
static inline int player_attack_weapon_state(unsigned int id, int frame_thirds,
                                             int airborne_jump)
{
    const player_attack_spec_t *spec = player_attack_spec(id);
    if (!spec || frame_thirds < 0) return 0;
    if (airborne_jump && (id == ATTACK_FLIP_START || id == ATTACK_JUMP_START)) {
        if (frame_thirds < 18 || frame_thirds > 297) return 0;
        return frame_thirds < 21 ? -1 : 1;
    }
    if (frame_thirds > spec->active_through * 3) return 0;
    return frame_thirds < spec->active_from * 3 ? -1 : 1;
}

/* func_80837948 / D_80854488: even ordinary nonmagic spin sword quads use
 * SLASH_KOKIRI. The separate magic Thunder cylinder uses SPIN_KOKIRI; it is
 * outside M2 scope. Damage amounts come from the victim's damage table. */
static inline uint32_t player_attack_damage_flags(unsigned int id)
{
    if (!player_attack_spec(id)) return 0;
    return id >= ATTACK_FLIP_START && id <= ATTACK_JUMP_FINISH
        ? DMG_JUMP_KOKIRI : DMG_SLASH_KOKIRI;
}

/* func_80837818 / D_80854480: source stick direction -1 none, 0 forward,
 * 1 left, 2 back, 3 right. Caller supplies source-relative direction, not
 * screen-space D-pad bits. Combo promotion is owned separately by the action. */
static inline unsigned int player_attack_select(int direction, int targeting,
                                                int quick_spin)
{
    if (quick_spin) return ATTACK_SPIN;
    if (direction < 0) return targeting ? ATTACK_FORWARD : ATTACK_RIGHT;
    if (direction == 0) return targeting ? ATTACK_STAB : ATTACK_FORWARD;
    return direction == 3 ? ATTACK_LEFT : ATTACK_RIGHT;
}
#endif
