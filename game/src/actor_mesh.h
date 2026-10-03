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
void actor_mesh_draw_transform(actor_mesh_t *mesh, int32_t x,int32_t y,int32_t z,
    uint16_t yaw,uint16_t pitch,uint16_t roll,int32_t scale);
bool actor_mesh_upload(actor_mesh_t *mesh);
/* translate * Ry(yaw) * Rx(pitch) * Rz(roll) * scale, OoT axes and angles,
** scale Q16 (oot-core draw items). */
void actor_mesh_draw_euler(actor_mesh_t *mesh, int32_t x, int32_t y, int32_t z,
    int16_t yaw, int16_t pitch, int16_t roll, int32_t sx, int32_t sy, int32_t sz);
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
