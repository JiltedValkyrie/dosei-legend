#ifndef OOT_CHILD_ROUTE_NPC_SPRITE_H
#define OOT_CHILD_ROUTE_NPC_SPRITE_H
#include "sprite_actor.h"
#include "actor.h"
#include "z_lib.h"

/* Source auto-turn state/timers/RNG remain authoritative. Presets 0, 2, 3,
 * and 4 used by these actors share 170 units / 0x3FFC. Only the final body
 * yaw is needed for sprites: no head/torso pose or pitch computation. */
s16 Npc_UpdateAutoTurn(Actor*, NpcInteractInfo*, f32, s16, s16);
static inline void ChildRouteSprite_TrackBody(Actor* actor, NpcInteractInfo* info,
                                            s16 preset, s16 mode) {
    info->trackingMode = Npc_UpdateAutoTurn(actor, info, preset < 6 ? 170 : 0,
                                           preset < 6 ? 0x3FFC : 0, mode);
    if (info->trackingMode == NPC_TRACKING_FULL_BODY)
        Math_SmoothStepToS(&actor->shape.rot.y,
                          Math_Vec3f_Yaw(&actor->world.pos, &info->trackPos), 6, 2000, 1);
}
#endif
