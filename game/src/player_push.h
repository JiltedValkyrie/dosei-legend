#ifndef PLAYER_PUSH_H
#define PLAYER_PUSH_H
#include "player_bg.h"
typedef struct {
    int phase, direction;
    unsigned bg_id;
    int32_t block_x,block_z;
} player_push_t;
/* True while the same close, front-facing dynamic-wall contact that starts
 * Handler_5 is present.  The HUD uses this read-only query for A: Grab. */
bool player_push_prompt(const player_bg_t *bg);
bool player_push_start(player_push_t *p,const player_bg_t *bg,bool held,
                        uint16_t *facing);
void player_push_update(player_push_t *p,bool held,int32_t speed_q8,
                         uint16_t heading,bg_vec_t *feet,uint16_t facing);
void player_push_cancel(player_push_t *p);
#endif
