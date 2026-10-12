#ifndef DOSEI_ACTOR_MESH_H
#define DOSEI_ACTOR_MESH_H
#include <stdbool.h>
#include <stdint.h>
/* Shared KFR1/CVA1 loader. Ownership stays with caller; no per-frame CD reads. */
typedef struct actor_mesh actor_mesh_t;
actor_mesh_t *actor_mesh_load(const char *file);
void actor_mesh_free(actor_mesh_t *mesh);
actor_mesh_t *actor_mesh_load_animated(const char *file);
actor_mesh_t *actor_mesh_load_static(const char *file);
/* Copy a static mesh and its current materials into caller-owned, 4-byte
 * aligned storage. Refresh after source texture uploads; returns NULL if it
 * will not fit. Borrowed result: never pass it to actor_mesh_free/upload. */
actor_mesh_t *actor_mesh_cache_static(const actor_mesh_t *mesh, void *storage, unsigned bytes);
/* Borrow geometry, copy materials with Saturn mesh transparency enabled.
 * Same storage/alignment/lifetime rules as cache_static; immutable during draw. */
actor_mesh_t *actor_mesh_cache_fade(const actor_mesh_t *mesh, void *storage, unsigned bytes);
unsigned actor_mesh_origin_radius(const actor_mesh_t *mesh);
void actor_mesh_draw_static(actor_mesh_t *mesh, int32_t x, int32_t y, int32_t z,
                            uint16_t yaw);
void actor_mesh_draw_transform(actor_mesh_t *mesh, int32_t x,int32_t y,int32_t z,
    uint16_t yaw,uint16_t pitch,uint16_t roll,int32_t scale);
bool actor_mesh_upload(actor_mesh_t *mesh);
/* translate * Ry(yaw) * Rx(pitch) * Rz(roll) * scale, OoT axes and angles,
** scale Q16 (oot-core draw items). */
void actor_mesh_draw_euler(actor_mesh_t *mesh, int32_t x, int32_t y, int32_t z,
    int16_t yaw, int16_t pitch, int16_t roll, int32_t sx, int32_t sy, int32_t sz);
/* Runtime skinning (oot-core NPCs): each vertex = mats[slot] * local, from
** an NPCnn.SKN table (build_npc_models.py) and the decomp flex draw's limb
** matrices (12 Q16 ints each, OoT world space). False = not drawn (table
** does not match the mesh or too few matrices): use the baked clip. */
bool actor_mesh_draw_skinned(actor_mesh_t *mesh, const unsigned char *skin,
                             const int32_t *mats, unsigned int count);
bool actor_mesh_load_scroll(actor_mesh_t *mesh, const char *file);
/* Replace only the clip on a loaded mesh: same geometry, same uploaded
** tiles, different .ANM/.TRK. `stem` is the file name without extension. */
bool actor_mesh_swap_clip(actor_mesh_t *mesh, const char *stem);
void actor_mesh_scroll(actor_mesh_t *mesh, unsigned int frame);
void actor_mesh_draw(actor_mesh_t *mesh, unsigned int frame,
                     int32_t x, int32_t y, int32_t z, uint16_t yaw,
                     const int16_t head_rot[9], const int16_t torso_rot[9],
                     int32_t focus[3]);  /* rot 0 = source pose */
#endif
