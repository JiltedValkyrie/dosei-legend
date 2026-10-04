#ifndef PUSH_BLOCK_H
#define PUSH_BLOCK_H
#include "actor_sys.h"
#include "kokiri_collision.h"

/* Obj_Oshihiki: mesh storage belongs to the scene/asset owner and must outlive
 * every instance. Actor state lives in the fixed cart actor pool. No drops:
 * z_obj_oshihiki.c has no Item_Drop* path. */
bool push_block_set_mesh(const bg_mesh_t *mesh);
actor_t *push_block_spawn(unsigned scene, int room, bg_vec_t position,
                          uint16_t yaw, uint16_t params);
actor_t *push_block_from_bg(unsigned bg_id);
unsigned push_block_bg(const actor_t *actor);
/* Signed push/pull request, facing toward the block. A started 20-unit step
 * completes even if the hand is released; cooldown is 10 source frames. */
bool push_block_request(actor_t *actor, uint16_t facing, int direction,
                         unsigned strength);
bool push_block_moving(const actor_t *actor);
void push_block_lock(actor_t *actor);
/* Called by the profile draw callback; installed by the target renderer. */
void push_block_set_draw(void (*draw)(const actor_t *, int32_t half_size));
#endif
