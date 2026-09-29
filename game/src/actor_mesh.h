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
void actor_mesh_draw_static(actor_mesh_t *mesh, int32_t x, int32_t y, int32_t z,
                            uint16_t yaw);
bool actor_mesh_upload(actor_mesh_t *mesh);
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
