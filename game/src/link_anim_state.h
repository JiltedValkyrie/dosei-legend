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
    LINK_STATE_ROLL,
    /* Automatic jump off a ledge (func_8083A4A8): jump or run_jump clip,
    ** held on its last frame until he lands or drops below the departure
    ** height (Player_Action_8084411C then switches to the falling pose). */
    LINK_STATE_JUMP,
    /* Landing straight out of a run jump: run_jump_end, never a roll. */
    LINK_STATE_JUMP_LANDING,
    /* Player_Action_80845668: 100/150 step up onto a ledge, then the start
    ** of the 250 jump. Played at the source rate (playSpeed 1.3); Link is
    ** held still until the clip ends or its last 4 frames are interrupted
    ** by movement input. */
    LINK_STATE_STEP_UP,
    LINK_STATE_JUMP_START,
    /* Player_Action_8084BBE4: hanging from a ledge (the actor stands on its
    ** top; the clip's root hangs the body below). Then 8084BDFC's pull-up. */
    LINK_STATE_HANG,
    LINK_STATE_PULL_UP,
    /* An AnimMovement clip (ladder / vine climbing, its starts and ends):
    ** the clip's root motion moves the actor; see link_anim_move_*. */
    LINK_STATE_CLIMB,
    /* Player_Action_8084C760 inside a crawlspace: the pose holds the last
    ** frame of tunnel_start while he slides. */
    LINK_STATE_CRAWL,
    LINK_STATE_TURN,
    LINK_STATE_BONK,
    LINK_STATE_PUSH,
    LINK_STATE_SLIDE,
    LINK_STATE_SLIDE_END,
    LINK_STATE_SWIM,
    /* M2e damage reactions and death (func_80837C0C, func_80836448): a
    ** one-shot clip, optionally chained (downA -> down_wake) or held on its
    ** last frame (derth_rebirth until the Game Over flow ends). */
    LINK_STATE_REACT
}                   link_state_t;

/* Pose link_points for one frame of a clip. Cheap to call with an unchanged
** frame: the posed table is kept and the call returns immediately. */
void                link_anim_pose(unsigned int clip, unsigned int frame,
                                   unsigned int fraction);
/* Upper-body overlay (Player_UpdateUpperBody): the given clip/frame owns the
** UPPER..TORSO limbs of the next pose while the played clip keeps the legs.
** This is how OoT carries an object -- there is no carry-walk animation. */
void                link_anim_upper_overlay(unsigned int clip, unsigned int frame,
                                            unsigned int fraction);
void                link_anim_upper_clear(void);
void                link_anim_reset(void);
/* Play a reaction clip once; `next` (or LINK_REACT_NONE) follows it; `hold`
** keeps the last frame. link_anim_react_done(): a held clip reached its end. */
#define LINK_REACT_NONE     0xFFFFu
void                link_anim_react(unsigned int clip, unsigned int next, bool hold);
bool                link_anim_react_active(void);
bool                link_anim_react_done(void);
void                link_anim_react_cancel(void);
/* Sample the posed blade once per displayed gameplay step; world-space trail. */
void                link_anim_trail_update(int x, int y, int z, int yaw, bool active);
void                link_anim_trail_draw(void);
void                link_anim_trail_reset(void);
void                link_anim_blade(int32_t out[2][3]);
/* Child Deku Stick attachment on PLAYER_LIMB_L_HAND.  This uses the source
 * model attach transform, while blade remains the Kokiri-sword line. */
void                link_anim_stick(int32_t out[2][3]);
/* Player focus.pos (head x (1100,-700,0)), Link-local Q16. */
void                link_anim_focus(int32_t out[3]);
/* Idle analog turn: advances facing by at most 800 binang per 30 Hz step.
** Caller supplies only eligible grounded, unlocked light-tilt input. */
void                link_anim_turn(bool requested, uint16_t target, uint16_t *facing);
/* Roll wall response. Angle is absolute world-yaw-to-wall, from player_bg. */
bool                link_anim_bonk(bool wall_interact, uint16_t wall_angle);
int32_t             link_anim_bonk_speed_q8(void);
void                link_anim_slide(bool face_up);
void                link_anim_slide_end(bool face_up);
void                link_anim_slide_cancel(void);
/* Start the automatic ledge jump; `run` picks gPlayerAnim_link_normal_run_jump
** over gPlayerAnim_link_normal_jump (player_air.h decides). Ends a roll. */
void                link_anim_auto_jump(bool run);
/* Start a ledge step-up (already placed on the ledge by the caller).
** `tall` = 150 step, else 100. `y_dist` = yDistToLedge: the drawn model
** starts that far down, less the clip's own rise (shape.yOffset). */
void                link_anim_step_up(bool tall, int32_t y_dist);
/* Start gPlayerAnim_link_normal_250jump_start. */
void                link_anim_jump_start(void);
/* True on the step the 250 jump reaches its frame 8: the caller launches
** (player_ledge_jump250_velocity_q8) and the clip carries on into the air. */
bool                link_anim_jump250_launch(void);
/* The step-up's shape.yOffset, Q8 world units, added to the drawn feet. */
int32_t             link_anim_y_offset_q8(void);
/* Hop off a low ledge (func_808389E8): the jump clip, like the auto jump. */
void                link_anim_hop(void);
/* Start hanging: `walk_off` = func_8083A6AC (normal_fall, then fall_wait),
** else the mid-air grab (jump_climb_hold, then jump_climb_wait). */
void                link_anim_hang(bool walk_off);
/* The hang has reached its grab frame (actionVar1 != 0): input counts. */
bool                link_anim_hang_ready(void);
/* func_8083A9B8: pull up (fall_up / jump_climb_up at playSpeed 1.3). */
void                link_anim_pull_up(void);
/* The same with a given clip, from any state (a vine top: climb_up_free). */
void                link_anim_pull_up_clip(unsigned int clip);

/* AnimMovement clips (Player_StartAnimMovement / AnimTask_ActorMovement).
** Play `clip` forwards, or from its last frame backwards (LinkAnimation_Change
** with -1). `adjust_start` = ANIM_FLAG_ADJUST_STARTING_POS: the first step
** moves nothing. The root at the play's start is prevTransl; the source's
** continuity tables (unk_4A/62/7A/86/44) equal those first/last roots. */
void                link_anim_move_play(unsigned int clip, bool reverse,
                                        bool adjust_start);
/* Stationary push/pull action clips: use the same source-rate phase clock,
** but roots are visual only and normal floor/gravity checks still apply. */
void                link_anim_push_play(unsigned int clip);
/* Water controller owns the clip clock and collision travel. */
void                link_anim_swim_play(unsigned int clip);
/* One step at |playSpeed| x 30 (30ths of a frame). LinkAnimation_Once: true,
** with no motion, when the play already sat at its end as the step began.
** Else `delta` = this step's root motion, raw model units, model-local (the
** caller turns it by the facing and applies actor scale 0.01). */
bool                link_anim_move_step(unsigned int speed_30ths, int32_t delta[3]);
unsigned int        link_anim_move_clip(void);
/* The clip currently set by link_anim_push_play (same storage as move_clip).
** Use to query the active carry-state clip without modifying any state. */
/* The play passed source frame `frame` on the last step (LinkAnimation_OnFrame). */
bool                link_anim_move_crossed(unsigned int frame);
/* Player_FinishAnimMovement: back to ordinary locomotion. */
void                link_anim_move_end(void);
/* func_80837B9C from a climb: straight into the falling pose. */
void                link_anim_fall(void);
/* Hold the finished tunnel_start pose (movementFlags cleared). */
void                link_anim_crawl_hold(void);
/* Right after link_anim_move_play: keep the previous play's prevTransl (the
** source changes clip without resetting it, func_8083F070). */
void                link_anim_move_keep_prev(void);
/* Current play position, 30ths of a source frame, and its direction. */
unsigned int        link_anim_move_phase(void);
bool                link_anim_move_reversed(void);
/* One-shot, on the step the pull-up ends: Player_ApplyAnimMovementScaledByAge
** (UPDATE_XZ) then the root yaw -- the clip's last root x/z in model-local
** Q8 world units (skeleton base x/z is 0) and its root limb yaw. */
bool                link_anim_pull_up_done(int32_t *local_x_q8, int32_t *local_z_q8,
                                           uint16_t *yaw);
/* func_80837B60 + func_80837B9C: let go. Writes where the hanging pelvis is
** (model-local Q8 x/z; y relative to the standing pelvis) and starts the
** fall. */
void                link_anim_let_go(int32_t *local_x_q8, int32_t *y_q8,
                                     int32_t *local_z_q8);
/* Per step while airborne: true once he is descending below the height he
** left the ground from (velocity < 0 and fallDistance > 0). */
void                link_anim_set_air(bool falling_below_start);
/* Saturn build: read LINKANIM.BIN (per-frame roots/rotations) into cart RAM.
** Must succeed before the first link_anim_pose; false = missing/stale file.
** Host builds link the arrays from link_clips.c and always return true. */
bool                link_anim_load(void);
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
/* A clip's root (model units) at a time in thirds of a frame. */
void link_anim_clip_root(unsigned int clip, unsigned int thirds, int32_t out[3]);
/* Sidehop/backflip flight clip, then its landing clip (func_8083BCD0). */
void link_anim_evade(unsigned int clip, unsigned int end_clip);
void link_anim_combat(bool attacking, unsigned int clip, unsigned int frame,
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
