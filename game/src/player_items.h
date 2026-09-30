#ifndef DOSEI_PLAYER_ITEMS_H
#define DOSEI_PLAYER_ITEMS_H
#include <stdbool.h>
#include <stdint.h>
#define PLAYER_SHOTS 2
#define PLAYER_ITEM_SEED 2
#define PLAYER_ITEM_NUT 3
#define PLAYER_ITEM_FIRE 1u
#define PLAYER_ITEM_IMPACT 2u
#define PLAYER_ITEM_FLASH 4u
void player_items_reset(void);
void player_items_room_changed(void);
/* Called only while gameplay owns input; pause/dialogue freeze these timers. */
bool player_items_use(unsigned item, int32_t x, int32_t y, int32_t z,
                      uint16_t yaw, int16_t pitch);
void player_items_step(void);
void player_items_register(void);
void player_items_collect(void);
unsigned player_items_events(void);
unsigned player_items_body(unsigned slot, int32_t *x, int32_t *y, int32_t *z);
unsigned player_items_flash(void);
bool player_items_stick(void);
void player_items_putaway(void);
void player_items_break_stick(void);
void player_items_ignite(void);
unsigned player_items_burning(void);
/* Swept scenery test; replaces endpoint with the first impact position. */
bool player_items_wall(const int32_t from[3], int32_t to[3]);
#endif
