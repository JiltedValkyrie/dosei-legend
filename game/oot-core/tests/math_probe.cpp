/*
 * Host probe: run the imported decomp math (z_lib, sys_math*, math64,
 * sins/coss, qrand) on fixed inputs and print every result. Built twice --
 * Fx and OOT_CORE_HWFLOAT=1 -- and compared by tests/compare_probe.py.
 */
#include "oot_prelude.h"
#include "ultra64.h"
#include "z_lib.h"
#include "sys_math.h"
#include "sys_math3d.h"
#include "libc64/math64.h"
#include "libc64/qrand.h"
#include "rand.h"
#include "array_count.h"

extern "C" int printf(const char*, ...);
extern "C" int sprintf(char*, const char*, ...);

/* `double` is macro-renamed to Fx; spell the hardware type for printf. */
typedef decltype(0.0) hw_double;
static hw_double D(f32 f) {
    return (hw_double)(decltype(0.0f))f;
}

#define OUT(name, val) printf("%s %.6f\n", name, D(val))
#define OUTI(name, val) printf("%s %ld\n", name, (long)(val))

int main() {
    char name[64];

    for (s32 a = -32768; a < 32768; a += 1111) {
        sprintf(name, "SinS(%ld)", (long)a);
        OUT(name, Math_SinS((s16)a));
        sprintf(name, "CosS(%ld)", (long)a);
        OUT(name, Math_CosS((s16)a));
    }
    for (s32 i = -20; i <= 20; i++) {
        f32 r = (f32)i * FXL(0.37f);
        sprintf(name, "sinf(%ld)", (long)i);
        OUT(name, sinf(r));
        sprintf(name, "SinF(%ld)", (long)i);
        OUT(name, Math_SinF(r));
    }
    static const s32 sq[] = { 0, 1, 2, 3, 10, 100, 1000, 12345, 30000, 1000000, 100000000 };
    for (u32 i = 0; i < ARRAY_COUNT(sq); i++) {
        sprintf(name, "sqrtf(%ld)", (long)sq[i]);
        OUT(name, sqrtf((f32)sq[i]));
    }
    for (s32 y = -3; y <= 3; y++) {
        for (s32 x = -3; x <= 3; x++) {
            f32 fy = (f32)y * FXL(123.5f);
            f32 fx = (f32)x * FXL(77.25f);
            sprintf(name, "FAtan2F(%ld,%ld)", (long)y, (long)x);
            OUT(name, Math_FAtan2F(fy, fx));
            sprintf(name, "Atan2S(%ld,%ld)", (long)y, (long)x);
            OUTI(name, Math_Atan2S(fy, fx));
        }
    }

    Vec3f a = { FXL(100.0f), FXL(-50.5f), FXL(2000.0f) };
    Vec3f b = { FXL(-3000.0f), FXL(250.25f), FXL(-1200.0f) };
    OUT("Vec3f_DistXYZ", Math_Vec3f_DistXYZ(&a, &b));
    OUT("Vec3f_DistXZ", Math_Vec3f_DistXZ(&a, &b));
    OUTI("Vec3f_Yaw", Math_Vec3f_Yaw(&a, &b));
    OUTI("Vec3f_Pitch", Math_Vec3f_Pitch(&a, &b));
    OUT("Math3D_Vec3fDistSq", Math3D_Vec3fDistSq(&a, &b));
    OUT("Math3D_Vec3f_DistXYZ", Math3D_Vec3f_DistXYZ(&a, &b));
    OUT("Math3D_Vec3fMagnitude", Math3D_Vec3fMagnitude(&b));

    Vec3f p0 = { FXL(0.0f), FXL(0.0f), FXL(0.0f) };
    Vec3f p1 = { FXL(100.0f), FXL(10.0f), FXL(0.0f) };
    Vec3f p2 = { FXL(0.0f), FXL(20.0f), FXL(100.0f) };
    f32 nx, ny, nz, od;
    Math3D_DefPlane(&p0, &p1, &p2, &nx, &ny, &nz, &od);
    OUT("DefPlane.nx", nx);
    OUT("DefPlane.ny", ny);
    OUT("DefPlane.nz", nz);
    OUT("DefPlane.d", od);

    f32 v = FXL(0.0f);
    for (s32 i = 0; i < 40; i++) {
        Math_SmoothStepToF(&v, FXL(500.0f), FXL(0.3f), FXL(40.0f), FXL(1.0f));
        sprintf(name, "SmoothStepToF[%ld]", (long)i);
        OUT(name, v);
    }
    v = FXL(10.0f);
    for (s32 i = 0; i < 30; i++) {
        Math_ApproachF(&v, FXL(-75.0f), FXL(0.2f), FXL(6.5f));
        sprintf(name, "ApproachF[%ld]", (long)i);
        OUT(name, v);
    }
    v = FXL(0.0f);
    for (s32 i = 0; i < 10; i++) {
        s32 done = Math_StepToF(&v, FXL(3.3f), FXL(0.45f));
        sprintf(name, "StepToF[%ld]", (long)i);
        OUT(name, v);
        OUTI(name, done);
    }

    Rand_Seed(0x12345678);
    for (s32 i = 0; i < 32; i++) {
        sprintf(name, "Rand_ZeroOne[%ld]", (long)i);
        OUT(name, Rand_ZeroOne());
    }
    for (s32 i = 0; i < 16; i++) {
        sprintf(name, "Rand_ZeroOne*0xFFFF->s16[%ld]", (long)i);
        OUTI(name, (s16)(Rand_ZeroOne() * 0xFFFF));
    }
    return 0;
}
