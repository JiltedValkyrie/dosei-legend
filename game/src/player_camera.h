#ifndef PLAYER_CAMERA_H
#define PLAYER_CAMERA_H
#include "oot_follow.h"
enum { PLAYER_CAMERA_NORMAL, PLAYER_CAMERA_CLIMB, PLAYER_CAMERA_HANG };
typedef struct {
    unsigned mode;
    int32_t at_y, previous_y, climb_offset;
    bool initialized, returning;
} player_camera_t;
void player_camera_reset(player_camera_t *camera);
/* Validated Camera_Subj4 line: reject unrelated, truncated or zero-length data. */
bool player_camera_crawl_line(const bg_mesh_t *mesh, unsigned index,
                             bg_vec_t *point, int32_t direction[3]);
void player_camera_update(player_camera_t *camera, oot_follow_t *follow,
    unsigned mode, const camera_position_t *player, uint16_t facing, bool moving,
    camera_position_t *eye, uint16_t *yaw, int32_t *pitch);
/* Source Subj3 ordinary look: full yaw, spring-to-stick pitch, five-unit
 * eye behind focus. Input deltas use the mapper's 420/280 full-throw units. */
void player_camera_first_person(oot_follow_t *state, const bg_vec_t *focus,
    uint16_t facing, int yaw_input, int pitch_input,
    camera_position_t *eye, uint16_t *yaw, int32_t *pitch);
#endif
