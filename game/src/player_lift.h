#ifndef PLAYER_LIFT_H
#define PLAYER_LIFT_H
#include <stdbool.h>
#include <stdint.h>
/* Player-only contract; the prop owns attachment transforms, thrown physics,
 * impact and source drop behavior. Events must be consumed once by that owner.
 * No prop is created by this module. Large rocks require their separate action. */
enum { LIFT_NONE,LIFT_FAIL_START,LIFT_FAIL_WAIT,LIFT_FAIL_END,
       LIFT_START,LIFT_HOLD,LIFT_THROW,LIFT_PUT };
enum { LIFT_ATTACH=1,LIFT_RELEASE=2 };
typedef struct {
    int phase,timer;
    bool attached,throw_only;
    unsigned events;
    int32_t release_speed_q8,release_y_q8;
} player_lift_t;
void player_lift_begin(player_lift_t *p,bool bush,unsigned strength,bool throw_only);
/* source input action: A (or mapped attack/C action), while already carrying */
void player_lift_update(player_lift_t *p,bool action,int32_t speed_q8);
void player_lift_cancel(player_lift_t *p);
#endif
