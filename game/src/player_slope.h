#ifndef PLAYER_SLOPE_H
#define PLAYER_SLOPE_H
#include "kokiri_collision.h"
typedef struct {
    bool active,face_up;
    int32_t speed_q8,push_q8;
    uint16_t yaw,push_yaw;
} player_slope_t;
void player_slope_update(player_slope_t *s,const bg_hit_t *floor,
                          uint16_t movement_yaw,int32_t movement_speed_q8,
                          uint16_t *facing);
/* Preserve source ground glue while sliding: 11-unit ground tolerance plus
 * the 7.5-unit downward displacement used before its floor check. */
bool player_slope_ground(bg_vec_t *feet);
/* D_80854600 damage magnitude in health units (16 = one heart). Uses
 * floor TYPE, not floorProperty. M2 owns damage/death/invulnerability effects. */
unsigned player_fall_damage(int32_t distance,unsigned floor_type);
#endif
