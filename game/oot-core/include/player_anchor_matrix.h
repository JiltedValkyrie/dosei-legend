#ifndef OOT_PLAYER_ANCHOR_MATRIX_H
#define OOT_PLAYER_ANCHOR_MATRIX_H
#include "z_math.h"

/* Exact bounded affine path; unusual matrices retain the source fallback. */
void OotCore_PlayerTranslateRotateZYX(Vec3f* translation, Vec3s* rotation);
void OotCore_PlayerMatrixOrigin(Vec3f* destination);
#endif
