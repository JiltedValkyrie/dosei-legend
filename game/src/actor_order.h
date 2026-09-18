#ifndef DOSEI_ACTOR_ORDER_H
#define DOSEI_ACTOR_ORDER_H

#include <stdint.h>

/* World commands have fixed back-to-front ranks 0..world_count-1.
 * Slot j is after world commands [0,j) and before [j,world_count).
 * Actor commands arrive in their original back-to-front order. A stable merge
 * at nondecreasing slots therefore preserves BOTH existing command orders.
 *
 * For world rank j, world-before-actor requires lo >= j+1; actor-before-world
 * requires hi <= j. Preserve an ambiguous pair's original relationship by
 * imposing the corresponding bound rather than guessing a plane side.
 */
typedef struct actor_order_interval {
    uint16_t lo;
    uint16_t hi;
    uint16_t original;
} actor_order_interval;

/* Solve without heap allocation or changing output on failure.
 *
 * intervals[0..count) and slots[0..capacity) must be valid, disjoint storage.
 * The caller bounds both arrays; capacity is the actual slots capacity. A
 * uint16_t slot also supports world_count == UINT16_MAX (the final slot).
 * No command links or depths are touched here: publish the stable merge only
 * after this function returns 1. A failed solve must retain the original list.
 *
 * Proof: let U[i] = min(hi[i..count)). Every nondecreasing feasible solution
 * has slot[i] <= U[i]. Such a solution exists exactly when lo[i] <= U[i]
 * for every i: the prefix maxima of lo then form one feasible solution.
 * The first backward pass checks this condition without writes. Afterward,
 * backward upper-bound propagation and forward clamping cannot fail.
 * With nondecreasing originals, clamping each original to the propagated
 * feasible bounds gives nondecreasing results and the nearest feasible slot
 * for every actor command (hence also minimum total absolute displacement).
 * Time O(count), storage O(count) in the caller's output, no extra scratch.
 */
static inline int actor_order_solve(const actor_order_interval *intervals,
                                   unsigned int count,
                                   unsigned int world_count,
                                   uint16_t *slots,
                                   unsigned int capacity)
{
    unsigned int i, upper, previous;

    if (world_count > UINT16_MAX || count > capacity)
        return 0;
    if (!count)
        return 1;
    if (!intervals || !slots)
        return 0;

    /* Validate all caller-provided bounds before using output as workspace. */
    previous = 0;
    for (i = 0; i < count; ++i) {
        const actor_order_interval *entry = &intervals[i];
        if (entry->lo > entry->hi || entry->hi > world_count ||
            entry->original > world_count || entry->original < previous)
            return 0;
        previous = entry->original;
    }
    upper = world_count;
    for (i = count; i != 0; ) {
        const actor_order_interval *entry = &intervals[--i];
        if (entry->hi < upper)
            upper = entry->hi;
        if (entry->lo > upper)
            return 0;
    }

    /* Feasibility is established. There are no failure exits below here. */
    upper = world_count;
    for (i = count; i != 0; ) {
        --i;
        if (intervals[i].hi < upper)
            upper = intervals[i].hi;
        slots[i] = (uint16_t)upper;
    }
    previous = 0;
    for (i = 0; i < count; ++i) {
        unsigned int lower = intervals[i].lo;
        unsigned int chosen = intervals[i].original;
        if (previous > lower)
            lower = previous;
        if (chosen < lower)
            chosen = lower;
        if (chosen > slots[i])
            chosen = slots[i];
        slots[i] = (uint16_t)chosen;
        previous = chosen;
    }
    return 1;
}

enum actor_order_plane_relation {
    ACTOR_ORDER_UNRESOLVED = 0,
    ACTOR_ORDER_WORLD_BEFORE_ACTOR = 1,
    ACTOR_ORDER_ACTOR_BEFORE_WORLD = 2
};

/* Signed distances use one consistent world-polygon plane and scale. The
 * actor range must bound EVERY posed vertex under consideration, not only
 * the feet or model origin. Test projected overlap separately to avoid
 * unnecessary constraints. For nonplanar quads, classify their triangles
 * separately; do not silently treat a bent quad as a single plane.
 *
 * A camera/actor pair on the same plane side cannot have this plane between
 * them. Opposite sides require the world surface first along the sight ray.
 * Zero-distance contact is permitted, but a straddling actor, a coplanar
 * actor, or a camera within epsilon of the plane is unresolved. Epsilon does
 * NOT forgive actor penetration: even a small negative minimum straddles.
 * Comparisons avoid multiplication or negation, including INT64_MIN.
 */
static inline enum actor_order_plane_relation actor_order_classify_plane(
    int64_t camera, int64_t actor_minimum, int64_t actor_maximum,
    int64_t epsilon)
{
    if (epsilon < 0 || actor_minimum > actor_maximum)
        return ACTOR_ORDER_UNRESOLVED;
    if (camera > epsilon) {
        if (actor_minimum >= 0 && actor_maximum > epsilon)
            return ACTOR_ORDER_WORLD_BEFORE_ACTOR;
        if (actor_maximum <= 0 && actor_minimum < -epsilon)
            return ACTOR_ORDER_ACTOR_BEFORE_WORLD;
    } else if (camera < -epsilon) {
        if (actor_maximum <= 0 && actor_minimum < -epsilon)
            return ACTOR_ORDER_WORLD_BEFORE_ACTOR;
        if (actor_minimum >= 0 && actor_maximum > epsilon)
            return ACTOR_ORDER_ACTOR_BEFORE_WORLD;
    }
    return ACTOR_ORDER_UNRESOLVED;
}

#endif
