#ifndef DOSEI_ATTENTION_H
#define DOSEI_ATTENTION_H
#include <stdbool.h>
#include <stdint.h>
#include "actor_sys.h"

/*
** Z-target attention shared by Link's lock-on and Navi (z_actor.c
** Attention_*). One registry identity: gameplay keeps the lock as an actor
** handle, Navi hovers the same actor.
**
** Acquisition (Attention_FindActorInCategory): targetable + attention kind,
** not the current lock, weighted distance under the actor's range,
** roughly on screen (Attention_ActorOnScreen), not blocked on the line from
** Link's focus to the actor's focus. Every filter runs before a candidate
** can become the nearest, so a blocked near actor never hides a valid
** farther one.
**
** Retention (Attention_ShouldReleaseLockOn) is a different rule: still
** targetable, still attention-enabled, inside the lock-on leash. No cone and
** no line of sight, as in the source.
*/

/* Platform hook: BgCheck_CameraLineTest1 from a to b (walls, floors,
** ceilings, one-face; camera-ignored polys skipped), minus polys that
** SurfaceType_IsIgnoredByProjectiles. recomp.c on Saturn, stub on host. */
bool        attention_sight_blocked(const int32_t a[3], const int32_t b[3]);

/* Platform hook: Attention_ActorOnScreen through the live camera: focus
** projected to the 320x240 frame, x in (-20, 340), y in (-160, 400).
** Acquisition only; a held lock never checks it. */
bool        attention_on_screen(const int32_t focus[3]);

/* actor focus.pos in world units. */
void        attention_focus(const actor_t *actor, int32_t out[3]);

/* Nearest acquirable actor or 0. feet = Link world.pos, focus = Link
** focus.pos, yaw = shape.rot.y. `locked` is the current lock (skipped, and
** switches on the locked weighting), or 0. */
actor_t    *attention_find(const int32_t feet[3], const int32_t focus[3],
                           uint16_t yaw, const actor_t *locked);

/* True while a lock on `actor` may stay. */
bool        attention_retains(const actor_t *actor, const int32_t feet[3]);

/*
** Navi hover (Attention_Update + Attention_SetNaviState). Stepped at the
** source 20 Hz: call once per 30 Hz step, it runs on two of three.
** `hover` is the lock if any, else the arrow-hover actor, else Link.
** Link's lockOnArrowOffset 500 x scale 0.01 = 5 (ATTENTION_PLAYER_ARROW).
*/
#define ATTENTION_PLAYER_ARROW  5
typedef enum { ATTN_COLOUR_PLAYER, ATTN_COLOUR_NPC, ATTN_COLOUR_ENEMY, ATTN_COLOUR_OTHER } attention_colour_t;
void        attention_navi_reset(const int32_t focus[3]);
void        attention_navi_step(const int32_t feet[3], const int32_t focus[3],
                                const actor_t *hover);
/* naviHoverPos, world units. */
void        attention_navi_hover(int32_t out[3]);
/* naviHoverActor != 0 (Navi flies straight, no idle dash rule). */
bool        attention_navi_has_actor(void);
/* naviMoveProgressFactor != 0 (En_Elf plays FAIRY_DASH while it runs). */
bool        attention_navi_moving(void);
/* sAttentionColors of the hover category, set on arrival. */
attention_colour_t attention_navi_colour(void);

#endif
