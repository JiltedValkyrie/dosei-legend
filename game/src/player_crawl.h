#ifndef PLAYER_CRAWL_H
# define PLAYER_CRAWL_H
# include <stdbool.h>
# include <stdint.h>
# include "kokiri_collision.h"
# include "player_bg.h"

/*
** Crawlspaces (M1f): z_player.c Player_TryEnteringCrawlspace,
** Player_Action_8084C760 (in the tunnel), Player_TryLeavingCrawlspace and
** Player_Action_8084C81C (out). Child only. Feet space, integer.
*/

typedef enum
{
    PLAYER_CRAWL_NONE = 0,
    PLAYER_CRAWL_ENTER,         /* tunnel_start, AnimMovement x/z */
    PLAYER_CRAWL_IN,            /* sliding: speedXZ = stick_y x 0.03 */
    PLAYER_CRAWL_LEAVE,         /* tunnel_end, or tunnel_start reversed */
    PLAYER_CRAWL_DONE           /* out: locomotion again this step */
}           player_crawl_phase_t;

typedef struct
{
    player_crawl_phase_t phase;
    int32_t     speed_q8;       /* speedXZ, signed, along the facing */
}           player_crawl_t;

/* Player_TryEnteringCrawlspace, from Player_ActionHandler_5 (the caller has
** checked WALL_INTERACT and shape yaw < 0x3000). Needs an A press and the
** hole's centre within 8. Moves *feet, sets *facing, starts tunnel_start. */
bool        player_crawl_enter(player_crawl_t *crawl, const player_bg_t *bg,
                               bool a_pressed, bg_vec_t *feet, uint16_t *facing);

/* PLAYER_STATE2_DO_ACTION_ENTER: the "Enter" A prompt -- every enter
** condition except the press. */
bool        player_crawl_prompt(const player_bg_t *bg, const bg_vec_t *feet);

/* One step. `stick_y` = rel.stick_y (raw N64 scale, forward positive).
** `wall` / `wall_hit` = last step's BGCHECKFLAG_WALL and wall (the source
** acts on the previous update's collision). In PLAYER_CRAWL_IN the caller
** moves him by speed_q8 through collision (crawl dimensions). */
void        player_crawl_update(player_crawl_t *crawl, int32_t stick_y, bool wall,
                                const bg_hit_t *wall_hit, bg_vec_t *feet,
                                uint16_t *facing);

#endif
