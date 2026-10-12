"""Bound Saturn table angles against real atan2 and source Player anchors."""
from collections import defaultdict
import subprocess
import tempfile
import unittest
from pathlib import Path

from test_core_bgcheck import compiler_env
from test_fx32 import ROOT, host_flags, importer


def body(text, name):
    start = text.index('\nvoid ' + name + '(') + 1
    return text[start:text.index('\n}\n', start) + 3]


def fixed(text):
    stats = defaultdict(int)
    return importer.fix_mtxf(importer.fix_float_literals(text, stats), stats)


PRELUDE = r'''
#include "sys_matrix.h"
#include "sys_math.h"
#include "libc64/math64.h"
extern "C" int printf(const char*, ...);
static int failures;
#define CHECK(c) do { if (!(c)) {printf("line %d: %s\n", __LINE__, #c); return 1;} } while (0)
static unsigned seed = 0x3759abd3u;
static unsigned random_word() {seed = seed*1664525u + 1013904223u; return seed;}
static int angle_error(s16 a, s16 b) {int n=(s16)(a-b); return n<0?-n:n;}
static const fx_hwdouble pi = 3.14159265358979323846;
static s16 OracleAtan2S(f32 x,f32 y) {
    if (!x.v && !y.v) return 0;
    fx_hwdouble n=__builtin_atan2((fx_hwdouble)y.v,(fx_hwdouble)x.v)*32768.0/pi;
    return (s16)(int)(n<0?n-0.5:n+0.5);
}

/* IK matrix/floor fixtures provide limb endpoints, then execute the complete
 * source leg function: geometry, floor test, rotations and floor effects. */
struct Actor {Vec3f scale;};
struct Player {Actor actor; unsigned stateFlags1; int itemAction; f32 unk_6C4;};
struct SkelAnime {Vec3s* jointTable;};
struct CollisionPoly {};
struct CollisionContext {};
struct PlayState {CollisionContext colCtx;};
struct {struct {int linkAge;} save;} gSaveContext;
#define PLAYER_STATE1_DEAD 1
#define FLOOR_TYPE_2 2
#define FLOOR_TYPE_3 3
#ifndef ABS
#define ABS(x) ((x)<0?-(x):(x))
#endif
static Vec3f endpoints[3];
static int point_index, queries, fires, surface;
static f32 floor_y;
static CollisionPoly floor_poly;
void Matrix_Push() {point_index=0;}
void Matrix_Pop() {}
void Matrix_TranslateRotateZYX(Vec3f*,Vec3s*) {}
void Matrix_Translate(f32,f32,f32,u8) {}
void Matrix_MultVec3f(Vec3f*,Vec3f* dest) {*dest=endpoints[point_index++];}
static int Player_ActionToMagicSpell(Player*,int action) {return action ? 0 : -1;}
static f32 BgCheck_EntityRaycastDown4(CollisionContext*,CollisionPoly** poly,s32* bg,Actor*,Vec3f*) {
    ++queries; *poly=&floor_poly; *bg=0; return floor_y;
}
static int SurfaceType_GetFloorType(CollisionContext*,CollisionPoly*,s32) {return surface;}
static int func_80042108(CollisionContext*,CollisionPoly*,s32) {return 0;}
static void EffectSsGFire_Spawn(PlayState*,Vec3f*) {++fires;}
'''


PROBES = r'''
static int table_test() {
    const int edges[]={-0x7fffffff,-65537,-65536,-65535,-2,-1,0,1,2,65535,65536,65537,0x7fffffff};
    int maximum=0;
    for(int x:edges) for(int y:edges) {
        int e=angle_error(Math_Atan2S(Fx::raw(x),Fx::raw(y)),OracleAtan2S(Fx::raw(x),Fx::raw(y)));
        CHECK(e<=7); if(e>maximum) maximum=e;
    }
    /* Full raw range, plus dense table-cell boundaries in every quadrant. */
    for(unsigned i=0;i<500000;++i) {
        int x=(int)(random_word()&0x7fffffff), y=(int)(random_word()&0x7fffffff);
        if(i&1)x=-x; if(i&2)y=-y;
        int e=angle_error(Math_Atan2S(Fx::raw(x),Fx::raw(y)),OracleAtan2S(Fx::raw(x),Fx::raw(y)));
        CHECK(e<=7); if(e>maximum)maximum=e;
    }
    for(int i=0;i<=65536;++i) for(int q=0;q<8;++q) {
        int x=65536,y=i;if(q&1){x=i;y=65536;}if(q&2)x=-x;if(q&4)y=-y;
        CHECK(angle_error(Math_Atan2S(Fx::raw(x),Fx::raw(y)),OracleAtan2S(Fx::raw(x),Fx::raw(y)))<=7);
    }
    CHECK(Math_Atan2S(Fx(0),Fx(0))==0);
    CHECK(Math_Atan2S(Fx(1),Fx(0))==0);
    CHECK(Math_Atan2S(Fx(0),Fx(1))==0x4000);
    CHECK(Math_Atan2S(Fx(-1),Fx(0))==(s16)0x8000);
    CHECK(Math_Atan2S(Fx(0),Fx(-1))==-0x4000);
    printf("table: max %d binang (limit 7 = 0.039 degrees)\n",maximum);
    return 0;
}

static void rotation(Vec3s a,int order,fx_hwdouble out[3][3]) {
    fx_hwdouble x=a.x*pi/32768.0,y=a.y*pi/32768.0,z=a.z*pi/32768.0;
    fx_hwdouble cx=__builtin_cos(x),sx=__builtin_sin(x),cy=__builtin_cos(y),sy=__builtin_sin(y);
    fx_hwdouble cz=__builtin_cos(z),sz=__builtin_sin(z);
    fx_hwdouble axis[3][3][3]={{{1,0,0},{0,cx,-sx},{0,sx,cx}},
        {{cy,0,sy},{0,1,0},{-sy,0,cy}},{{cz,-sz,0},{sz,cz,0},{0,0,1}}};
    int list[2][3]={{1,0,2},{2,1,0}};
    for(int i=0;i<3;++i)for(int j=0;j<3;++j)out[i][j]=i==j?1:0;
    for(int p=0;p<3;++p) {
        fx_hwdouble temp[3][3];
        for(int i=0;i<3;++i)for(int j=0;j<3;++j){
            temp[i][j]=0;for(int k=0;k<3;++k)temp[i][j]+=out[i][k]*axis[list[order][p]][k][j];
        }
        for(int i=0;i<3;++i)for(int j=0;j<3;++j)out[i][j]=temp[i][j];
    }
}

static int matrix_test() {
    fx_hwdouble maximum=0;
    const int near_axis[]={0,1,-1,0x3ffa,0x3fff,0x4000,0x4001,-0x4000,0x7fff,-0x8000};
    for(int i=0;i<40000;++i)for(int order=0;order<2;++order) {
        Vec3s in={(s16)random_word(),(s16)random_word(),(s16)random_word()},got,expected;
        if(i<100){in.x=near_axis[i%10];in.y=near_axis[i/10];}
        fx_hwdouble source[3][3],a[3][3],b[3][3];rotation(in,order,source);
        MtxF matrix={};fx_hwdouble scale=i%3==0?0.01:(i%3==1?1.0:2.0);
        for(int r=0;r<3;++r)for(int c=0;c<3;++c)matrix.mf[c][r]=Fx(source[r][c]*scale);
        if(!order){Matrix_MtxFToYXZRotS(&matrix,&got,i&1);Oracle_Matrix_MtxFToYXZRotS(&matrix,&expected,i&1);}
        else {Matrix_MtxFToZYXRotS(&matrix,&got,i&1);Oracle_Matrix_MtxFToZYXRotS(&matrix,&expected,i&1);}
        /* Near gimbal lock Euler components may differ by pi while the
         * orientation remains the same. Compare reconstructed rotations. */
        rotation(got,order,a);rotation(expected,order,b);
        for(int r=0;r<3;++r)for(int c=0;c<3;++c){
            fx_hwdouble error=__builtin_fabs(a[r][c]-b[r][c]);
            CHECK(error<0.004);if(error>maximum)maximum=error;
        }
    }
    printf("matrix: max element difference %.7f across gimbal/scales\n",maximum);
    return 0;
}

static int ik_test() {
    int oracle_max=0,source_max=0;
    for(int i=0;i<20000;++i) {
        Vec3s original[3],fast[3],reference[3];
        for(int j=0;j<3;++j) {
            original[j]={(s16)random_word(),(s16)random_word(),(s16)random_word()};
            fast[j]=reference[j]=original[j];
        }
        Vec3s ro={(s16)random_word(),(s16)random_word(),(s16)random_word()},rf=ro,rr=ro;
        Player player={}; player.actor.scale.y=Fx(1);
        if(i%17==0)player.stateFlags1=PLAYER_STATE1_DEAD;
        if(i%19==0)player.itemAction=1;
        if(i%23==0)player.actor.scale.y=Fx(-1);
        player.unk_6C4=Fx::raw(random_word()%65536);
        gSaveContext.save.linkAge=i&1;
        endpoints[0]={Fx(0),Fx(20),Fx(0)};
        endpoints[1]={Fx::raw((int)(random_word()%655360)-327680),
            Fx::raw(1310720-(int)(random_word()%983040)),
            Fx::raw((int)(random_word()%655360)-327680)};
        endpoints[2]=endpoints[1];
        floor_y=Fx::raw((int)(random_word()%1572864)-262144);surface=i%4;
        SkelAnime so={original},sf={fast},sr={reference}; PlayState play;Vec3f pos={};
        queries=fires=0;Original_IK(&play,&player,&so,&pos,&ro,0,1,2);
        int old_queries=queries,old_fires=fires;
        queries=fires=0;func_8008F87C(&play,&player,&sf,&pos,&rf,0,1,2);
        CHECK(queries==old_queries && fires==old_fires);
        queries=fires=0;Oracle_IK(&play,&player,&sr,&pos,&rr,0,1,2);
        CHECK(queries==old_queries && fires==old_fires);
        for(int j=0;j<3;++j){
            int e=angle_error(fast[j].z,reference[j].z),o=angle_error(fast[j].z,original[j].z);
            CHECK(e<=24);CHECK(o<=32);
            if(e>oracle_max)oracle_max=e;if(o>source_max)source_max=o;
            CHECK(fast[j].x==original[j].x && fast[j].y==original[j].y);
        }
        CHECK(angle_error(rf.z,rr.z)<=14 && angle_error(rf.z,ro.z)<=32);
        CHECK(rf.x==ro.x && rf.y==ro.y);
    }
    printf("IK: max %d binang vs real atan, %d vs old Fx; floor effects unchanged\n",oracle_max,source_max);
    return 0;
}
int main(int argc,char** argv) {
    if(argc<2)return 1;
    return argv[1][0]=='t'?table_test():(argv[1][0]=='m'?matrix_test():ik_test());
}
'''


class PlayerFastAngles(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.folder = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.folder.cleanup)
        folder = Path(cls.folder.name)
        matrix_rel = 'src/code/sys_matrix.c'
        player_rel = 'src/code/z_player_lib.c'
        cls.raw_matrix = (importer.OOT_DEFAULT / matrix_rel).read_text()
        cls.raw_player = (importer.OOT_DEFAULT / player_rel).read_text()
        matrix = importer.fix_player_fast_angles(matrix_rel, cls.raw_matrix, {})
        player = importer.fix_player_fast_angles(player_rel, cls.raw_player, {})
        source = PRELUDE
        for name in ('Matrix_MtxFToYXZRotS', 'Matrix_MtxFToZYXRotS'):
            fast = fixed(body(matrix, name))
            source += fast + '\n'
            source += fast.replace(name, 'Oracle_' + name).replace('Math_Atan2S(', 'OracleAtan2S(') + '\n'
        first = cls.raw_player.index('Vec3f sZeroVec =')
        end = cls.raw_player.index('\nvoid func_8008F87C(', first)
        source += fixed(cls.raw_player[first:end])
        original = fixed(body(cls.raw_player, 'func_8008F87C'))
        fast = fixed(body(player, 'func_8008F87C'))
        source += original.replace('func_8008F87C(', 'Original_IK(') + '\n'
        source += fast + '\n'
        source += fast.replace('func_8008F87C(', 'Oracle_IK(').replace('Math_Atan2S(', 'OracleAtan2S(') + '\n'
        source += PROBES
        path = folder / 'angles.cpp'
        path.write_text(source)
        cls.exe = folder / 'angles'
        compiler, cls.env = compiler_env()
        result = subprocess.run(
            [compiler, *host_flags(), '-fsanitize=undefined', '-fno-sanitize-recover=undefined',
             '-ffunction-sections', '-fdata-sections', str(path),
             str(ROOT / 'build/oot-core/decomp/src/code/sys_math_atan.cpp'),
             str(ROOT / 'build/oot-core/decomp/src/libc64/math64.cpp'),
             str(ROOT / 'oot-core/src/oot_math.cpp'), str(ROOT / 'oot-core/src/oot_rand.cpp'),
             '-Wl,--gc-sections', '-lm', '-o', str(cls.exe)],
            env=cls.env, text=True, capture_output=True)
        if result.returncode:
            raise RuntimeError(result.stdout + result.stderr)

    def probe(self, mode):
        result = subprocess.run([str(self.exe), mode], env=self.env,
                                capture_output=True, text=True, timeout=45)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        print(result.stdout.strip())

    def test_full_range_table_and_axis_endpoints(self):
        self.probe('table')

    def test_matrix_rotations_scales_and_gimbal_endpoints(self):
        self.probe('matrix')

    def test_full_foot_ik_keeps_joint_bounds_and_floor_effects(self):
        self.probe('ik')

    def test_import_rejects_changed_math_anchors(self):
        changed = self.raw_matrix.replace('Math_FAtan2F(-mf->yz, sqrtf(temp))',
                                          'Math_FAtan2F(mf->yz, sqrtf(temp))')
        with self.assertRaisesRegex(ValueError, 'fast angle anchor changed'):
            importer.fix_player_fast_angles('src/code/sys_matrix.c', changed, {})
