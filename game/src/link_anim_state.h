#ifndef LINK_ANIM_STATE_H
# define LINK_ANIM_STATE_H
# include <stdbool.h>
# include <stdint.h>

/* Locomotion states for the slice. These are animation states, not OoT action
** functions: the slice needs idle/walk/run/fall/land/roll to read correctly,
** not Player's full action table. */
typedef enum
{
    LINK_STATE_IDLE = 0,
    LINK_STATE_WALK,
    LINK_STATE_RUN,
    LINK_STATE_FALL,
    LINK_STATE_LANDING,
    LINK_STATE_ROLL
}                   link_state_t;

/* Pose link_points for one frame of a clip. Cheap to call with an unchanged
** frame: the posed table is kept and the call returns immediately. */
void                link_anim_pose(unsigned int clip, unsigned int frame,
                                   unsigned int fraction);
void                link_anim_reset(void);
/* Clears the locomotion state itself; link_anim_reset() only clears the
** cached pose. Call both when Link (re-)enters gameplay. */
void                link_anim_reset_state(void);

/* Advance the locomotion state one 30 Hz step.
**
** `speed` is the distance actually moved this step in world units, so anything
** that stops movement -- a wall, a ledge constraint -- also stops the walk
** cycle, rather than leaving Link running on the spot. `fall_units` is how far
** he fell, measured at the moment he lands, and drives OoT's landing choice. */
void                link_anim_update(int32_t speed, bool grounded,
                                     int32_t fall_units, bool roll_pressed);
/* Combat presentation follows the gameplay clock, never render cadence. */
void                link_anim_combat(unsigned int swing_remaining,
                                     bool shielding);
/* One-step sound events from actual locomotion clip frame crossings. */
uint32_t            link_anim_motion_events(void);

/* What to draw now. */
link_state_t        link_anim_state(void);
unsigned int        link_anim_clip(void);
unsigned int        link_anim_frame(void);
unsigned int        link_anim_fraction(void); /* Q8 fraction toward next frame */

/* Forward travel the roll owns this step, in Q8 world units, or 0 when Link is
** not rolling. The clips are pose-only, so the caller applies this through
** collision.
**
** Source model (Player_Action_Roll, z_player.c:9754): the target is the speed
** ordinary locomotion would give for the current stick, times 1.5, floored at
** 3.0 -- and dropped to that floor outright once the stick stops pointing
** forward. It is NOT a decay to zero across the clip; the roll ends because
** the animation ends.
**
** `link_anim_roll_input` must be called every step with the speed ORDINARY
** LOCOMOTION would give for the pad right now (walk or run, in Q8), and
** whether that input points forward relative to Link's facing. The target is
** recomputed from those every step and approached in BOTH directions, so
** pressing forward again after letting go restores the roll's speed, exactly
** as re-centring the stick and pushing it again does in the original. */
int32_t             link_anim_roll_speed_q8(void);
void                link_anim_roll_input(int32_t locomotion_speed_q8,
                                         bool forward);
/* Drop a roll in progress. Anything that takes movement away from Link -- a
** text box, the menu, a swing, a raised shield -- must call this, or the roll
** would keep carrying him while he is supposed to be held still. */
void                link_anim_cancel_roll(void);

/* Root-motion-free: the slice drives translation from collision, so the clips
** are used for pose only. Exposed for tests and diagnostics. */
bool                link_anim_is_locked(void);

/* Last inputs the state machine decided on, and a count of how many landings
** it has seen. These exist to trace state changes in Kronos: repeated rolling
** has to be attributed to a real grounded transition and fall distance before
** it can be fixed, and neither value is visible from outside otherwise. */
int32_t             link_anim_last_fall(void);
unsigned int        link_anim_landings(void);
bool                link_anim_last_grounded(void);

#endif
