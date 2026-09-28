/*
** Crawlspaces. Contract in player_crawl.h.
**
** Source: ovl_player_actor/z_player.c Player_TryEnteringCrawlspace,
** func_8083A40C, Player_Action_8084C760, Player_TryLeavingCrawlspace,
** Player_Action_8084C81C.
*/

#include "player_crawl.h"
#include "kokiri_camera.h"
#include "link_anim_state.h"
#include "link_clips.h"

/* LinkAnimation_PlayOnce: playSpeed 1.0, one frame a step. */
#define CRAWL_ANIM_SPEED    30

static int32_t  carry_x_q8, carry_z_q8;

static int32_t  magnitude(int32_t v)
{
    return v < 0 ? -v : v;
}

/* AnimTask_ActorMovement with UPDATE_XZ only: raw x/z delta x 0.01, turned
** by the facing. */
static void     apply_xz(bg_vec_t *feet, uint16_t facing, const int32_t d[3])
{
    int32_t sine, cosine;

    kokiri_camera_sincos(facing, &sine, &cosine);
    carry_x_q8 += (d[0] * (cosine / 256) + d[2] * (sine / 256)) / 100;
    carry_z_q8 += (d[2] * (cosine / 256) - d[0] * (sine / 256)) / 100;
    feet->x += carry_x_q8 / 256; carry_x_q8 %= 256;
    feet->z += carry_z_q8 / 256; carry_z_q8 %= 256;
}

/* The hole's doubled x/z centre; false unless a crawlspace wall with the
** player within 8 of its centre line. */
static bool     hole_centre(const player_bg_t *bg, const bg_vec_t *feet,
                            int32_t *sx, int32_t *sz)
{
    const bg_hit_t *wall = &bg->wall_hit;
    int16_t v[3][3];
    int32_t x0, x1, z0, z1, lateral, i;

    if (!(bg->touched_flags & BG_WALL_CRAWLSPACE) || !bg_poly_vertices(wall, v))
        return false;
    /* The hole's x/z centre (the source's min/max scan, kept). */
    x0 = x1 = v[0][0]; z0 = z1 = v[0][2];
    for (i = 1; i < 3; i++) {
        if (x0 > v[i][0]) x0 = v[i][0]; else if (x1 < v[i][0]) x1 = v[i][0];
        if (z0 > v[i][2]) z0 = v[i][2]; else if (z1 < v[i][2]) z1 = v[i][2];
    }
    *sx = x0 + x1;
    *sz = z0 + z1;
    lateral = (feet->x * 2 - *sx) * wall->normal[2] - (feet->z * 2 - *sz) * wall->normal[0];
    return magnitude(lateral) < 16 * 16384;
}

bool            player_crawl_prompt(const player_bg_t *bg, const bg_vec_t *feet)
{
    int32_t sx, sz;
    return hole_centre(bg, feet, &sx, &sz);
}

bool            player_crawl_enter(player_crawl_t *crawl, const player_bg_t *bg,
                                   bool a_pressed, bg_vec_t *feet, uint16_t *facing)
{
    int32_t nx = bg->wall_hit.normal[0], nz = bg->wall_hit.normal[2], sx, sz;

    /* PLAYER_STATE2_DO_ACTION_ENTER within 8; A enters. */
    if (!hole_centre(bg, feet, &sx, &sz) || !a_pressed)
        return false;
    *facing = (uint16_t)(bg->wall_yaw + 0x8000);
    feet->x = (sx * 16384 + 2 * bg->dist_to_wall * nx) / (2 * 16384);
    feet->z = (sz * 16384 + 2 * bg->dist_to_wall * nz) / (2 * 16384);
    carry_x_q8 = carry_z_q8 = 0;
    crawl->phase = PLAYER_CRAWL_ENTER;
    crawl->speed_q8 = 0;
    link_anim_move_play(LINK_CLIP_TUNNEL_START, false, true);
    kokiri_collision_actor_set_crawl(true);
    return true;
}

void            player_crawl_update(player_crawl_t *crawl, int32_t stick_y, bool wall,
                                    const bg_hit_t *wall_hit, bg_vec_t *feet,
                                    uint16_t *facing)
{
    int32_t delta[3];

    if (crawl->phase == PLAYER_CRAWL_ENTER || crawl->phase == PLAYER_CRAWL_LEAVE) {
        if (!link_anim_move_step(CRAWL_ANIM_SPEED, delta)) {
            apply_xz(feet, *facing, delta);
            return;
        }
        if (crawl->phase == PLAYER_CRAWL_ENTER) {
            /* Inside: movementFlags cleared, the skeleton holds still. */
            link_anim_crawl_hold();
            crawl->phase = PLAYER_CRAWL_IN;
        } else {
            /* Player_Action_8084C81C: control back, CRAWLING off. */
            link_anim_move_end();
            kokiri_collision_actor_set_crawl(false);
            crawl->phase = PLAYER_CRAWL_DONE;
        }
        crawl->speed_q8 = 0;
        return;
    }
    if (crawl->phase != PLAYER_CRAWL_IN)
        return;

    /* Player_TryLeavingCrawlspace: an interior exit wall, met going forward
    ** (facing it) or backward (backing into it). */
    if (crawl->speed_q8 != 0 && wall && (bg_wall_flags(wall_hit) & BG_WALL_CRAWLSPACE)) {
        uint16_t wall_yaw = kokiri_camera_facing(wall_hit->normal[0], wall_hit->normal[2]);
        int16_t to_wall = (int16_t)(uint16_t)(*facing - wall_yaw);
        if (crawl->speed_q8 < 0)
            to_wall = (int16_t)(to_wall + 0x8000);
        if (magnitude(to_wall) > 0x4000) {
            carry_x_q8 = carry_z_q8 = 0;
            if (crawl->speed_q8 > 0) {
                *facing = (uint16_t)(wall_yaw + 0x8000);
                link_anim_move_play(LINK_CLIP_TUNNEL_END, false, true);
            } else {
                *facing = wall_yaw;
                link_anim_move_play(LINK_CLIP_TUNNEL_START, true, true);
            }
            crawl->speed_q8 = 0;
            crawl->phase = PLAYER_CRAWL_LEAVE;
            return;
        }
    }
    /* speedXZ = rel.stick_y x 0.03, per 20 Hz update = per 30 Hz step. */
    crawl->speed_q8 = stick_y * 768 / 100;
}
