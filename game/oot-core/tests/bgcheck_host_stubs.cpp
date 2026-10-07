/* Link stubs for bgcheck_probe on MinGW (PE ld cannot ignore unresolved
 * symbols). None run: the probe spawns no dyna actors. */
#include "oot_prelude.h"
#include "ultra64.h"
#include "actor.h"
#include "skin_matrix.h"

void bzero(void* p, unsigned int n) { __builtin_memset(p, 0, n); }
void LogUtils_HungupThread(const char*, int) { for (;;) {} }
void Actor_SetObjectDependency(PlayState*, Actor*) {}
#ifndef BG_REAL_SKIN_MATRIX /* real z_bg_item linked by run_bg_port_probe.sh */
void DynaPolyActor_UnsetAllInteractFlags(DynaPolyActor*) {}
#endif
#ifndef BG_REAL_SKIN_MATRIX /* bg_dyna_probe links the real z_skin_matrix */
void SkinMatrix_SetTranslateRotateYXZScale(MtxF*, f32, f32, f32, s16, s16, s16, f32, f32, f32) {}
void SkinMatrix_Vec3fMtxFMultXYZ(MtxF*, Vec3f*, Vec3f*) {}
#endif
