#ifndef PLAYER_WATER_H
#define PLAYER_WATER_H
#include "kokiri_collision.h"

enum {
    PLAYER_WATER_DRY, PLAYER_WATER_ENTER, PLAYER_WATER_SURFACE,
    PLAYER_WATER_DIVE_START, PLAYER_WATER_DIVE, PLAYER_WATER_TURN,
    PLAYER_WATER_RISE, PLAYER_WATER_SURFACE_END
};
typedef struct {
    unsigned phase, timer, submerged_steps;
    int32_t speed_q8, velocity_q8, remainder[3], rise_depth;
    uint16_t yaw;
    bool grounded;
} player_water_t;
typedef struct {
    int32_t speed_q8;
    uint16_t yaw;
    unsigned room, scale;
    bool dive_pressed, dive_held, stroke_pressed, blocked;
} player_water_input_t;

void player_water_reset(player_water_t *water);
/* Feet coordinates, source water boxes. False hands control back to ordinary
 * locomotion; true means water owns this entire step (including a shore exit).
 * Child thresholds: enter >32, leave <22; scale dive limits 120/240/360.
 * incoming_velocity is used only on entry, never as a second gravity update. */
bool player_water_step(player_water_t *water, const player_water_input_t *input,
                       bg_vec_t *feet, uint16_t *facing, int32_t incoming_velocity,
                       bool was_grounded);
/* Source underwater hazard becomes eligible after 300 source steps (15 s).
 * This is an M2 environmental timer hook, NOT an immediate drowning deadline. */
bool player_water_hazard(const player_water_t *water);
#endif
