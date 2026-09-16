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

/* What to draw now. */
link_state_t        link_anim_state(void);
unsigned int        link_anim_clip(void);
unsigned int        link_anim_frame(void);
unsigned int        link_anim_fraction(void); /* Q8 fraction toward next frame */

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
