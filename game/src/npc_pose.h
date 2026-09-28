#ifndef DOSEI_NPC_POSE_H
#define DOSEI_NPC_POSE_H
#include <stdint.h>
/* Q6 model point/origin/pivot, Q14 orthonormal parent basis and matrices.
 * Source limb override: parent * T(pivot) * R * T(-pivot), R in the parent's
 * frame (head pivot along parent X; torso pivot 0). */
void npc_limb_transform(int32_t p[3], const int16_t basis[9], const int16_t origin[3],
                        int32_t pivot, const int16_t rot[9]);
/* rot = R_a(first) * R_b(second): Matrix_Rotate{a} then Matrix_Rotate{b}
 * with MTXMODE_APPLY. Axis 0 X, 1 Y, 2 Z; sine/cosine Q14. */
void npc_rot_matrix(int16_t rot[9], unsigned int a, int32_t sa, int32_t ca,
                    unsigned int b, int32_t sb, int32_t cb);

/* NpcTrackingMode (include/actor.h). AUTO_TURN is not used by the slice cast. */
enum { NPC_TRACKING_NONE = 1, NPC_TRACKING_HEAD_AND_TORSO, NPC_TRACKING_HEAD,
       NPC_TRACKING_FULL_BODY };
/* NpcInteractInfo head/torso rotation: [0] = rot.x (pitch), [1] = rot.y (yaw). */
typedef struct { int16_t head[2], torso[2]; } npc_track_t;
/* Math_SmoothStepToS. */
int16_t npc_smooth_step(int16_t *value, int16_t target, int16_t scale,
                        int16_t step, int16_t min_step);
/* Npc_TrackPoint with sNpcTrackingPresets[preset]. `yaw_to`/`pitch_to` are
 * Math_Vec3f_Yaw/Pitch from the yOffset-raised actor position to trackPos. */
void npc_track_point(npc_track_t *t, uint16_t *shape_yaw, int16_t yaw_to,
                     int16_t pitch_to, unsigned int preset, unsigned int mode);
#endif
