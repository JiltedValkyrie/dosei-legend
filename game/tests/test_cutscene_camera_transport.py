"""Execute the camera snapshot transport while simulated slave state changes."""
from pathlib import Path
import unittest
import test_graphics_backend as graphics

ROOT = Path(__file__).resolve().parents[1]


class CutsceneCameraTransport(unittest.TestCase):
    run_c = graphics.GraphicsBackend.run_c

    def test_script_destination_index_survives_handoff_and_cancel(self):
        api = ROOT / 'oot-core/src/oot_core_api.cpp'
        self.run_c(r'''
#include <assert.h>
typedef unsigned short u16;
#define TRANS_TRIGGER_START 1
#define TRANS_TRIGGER_OFF 0
#define NEXT_CS_INDEX_NONE 0xffef
#define CS_INDEX_D 0xfffd
#define CS_INDEX_NONE 0
#define NEXT_TIME_NONE 0xffff
#define SUNSSONG_INACTIVE 0
#define OOT_CORE_TRANSITION_RELOAD 0xfffe
typedef struct {int transitionTrigger,nextEntranceIndex;} PlayState;
static PlayState play, *gOotCorePlay=&play;
static struct {struct {u16 cutsceneIndex;} save;u16 nextCutsceneIndex,nextDayTime;int respawnFlag,sunsSongState;} gSaveContext;
static u16 host_index;
static struct {u16* cutscene_index_out;} host={&host_index},*sHostSave=&host;
''' + graphics.function(api, 'static int oot_core_transition_request(') +
        graphics.function(api, 'static void oot_core_cancel_transition_time(') + r'''
int main(void) {
    play.transitionTrigger=TRANS_TRIGGER_START;play.nextEntranceIndex=0x242;
    gSaveContext.nextCutsceneIndex=0xfff1;
    assert(oot_core_transition_request(0)==0x242 && host_index==0);
    assert(oot_core_transition_request(1)==0x242 && host_index==0xfff1);
    assert(gSaveContext.nextCutsceneIndex==0xfff1 && gSaveContext.save.cutsceneIndex==0);
    assert(oot_core_transition_request(0)==-1);
    oot_core_cancel_transition_time();
    assert(host_index==0 && gSaveContext.nextCutsceneIndex==NEXT_CS_INDEX_NONE);
    play.transitionTrigger=TRANS_TRIGGER_START;gSaveContext.nextCutsceneIndex=CS_INDEX_D;
    assert(oot_core_transition_request(1)==0x242 && host_index==0);
    play.transitionTrigger=TRANS_TRIGGER_START;play.nextEntranceIndex=0xffff;
    gSaveContext.respawnFlag=-2;gSaveContext.nextCutsceneIndex=NEXT_CS_INDEX_NONE;
    assert(oot_core_transition_request(1)==OOT_CORE_TRANSITION_RELOAD && host_index==0);
    return 0;
}
''')

    def test_letterbox_geometry_tracks_projection_and_releases(self):
        self.run_c(r'''
#include <assert.h>
#include <stdint.h>
''' + '#include "%s"\n' % (ROOT / 'oot-core/include/oot_cutscene_camera.h').as_posix() + r'''
typedef int32_t POINT[3];
typedef struct { int normal[3], indices[4]; } POLYGON;
typedef int ATTR;
typedef struct { POINT* pntbl; int nbPoint; POLYGON* pltbl; int nbPolygon; ATTR* attbl; } PDATA;
#define ATTRIBUTE(...) 0
#define JO_TV_HEIGHT 240
#define KOKIRI_ZDSP_LEVEL 3
static struct { POINT letterbox_points[8]; PDATA letterbox_data; } draw;
#define CORE_DRAW (&draw)
static OotCoreCutsceneCameraView view;
static int distance=208, submitted, stack, identity;
static const OotCoreCutsceneCameraView* oot_core_cutscene_camera(void){return &view;}
static int recomp_screen_distance(void){return distance;}
static void slPushMatrix(void){++stack;}
static void slUnitMatrix(int m){assert(stack==1 && m==0);++identity;}
static void slPopMatrix(void){--stack;}
static void kokiri_submit_pdata(PDATA* p){assert(p==&draw.letterbox_data);++submitted;}
''' + graphics.function(ROOT / 'src/oot_core_host.c', 'void oot_core_cutscene_letterbox_draw(') + r'''
int main(void) {
    oot_core_cutscene_letterbox_draw(); assert(!submitted);
    view.letterbox=32;
    for(distance=120;distance<=290;distance+=17){
        oot_core_cutscene_letterbox_draw();
        assert(stack==0 && submitted==identity);
        assert(draw.letterbox_data.nbPoint==8 && draw.letterbox_data.nbPolygon==2);
        int depth=(distance>>3)+1;
        int y=draw.letterbox_points[2][1]*distance/depth/65536;
        int x=draw.letterbox_points[0][0]*distance/depth/65536;
        assert(y>=-88 && y<=-87 && x<=-160 && x>=-161);
        assert(draw.letterbox_points[6][1]==-draw.letterbox_points[2][1]);
        assert(draw.letterbox_points[0][2]==depth*65536);
    }
    int count=submitted; view.letterbox=0;
    oot_core_cutscene_letterbox_draw(); assert(submitted==count);
    return 0;
}
''')

    def test_joined_view_is_stable_during_slave_and_projects_source_fov(self):
        host = ROOT / 'src/oot_core_host.c'
        code = r'''
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <math.h>
''' + '#include "%s"\n' % (ROOT / 'oot-core/include/oot_cutscene_camera.h').as_posix() + r'''
static struct { OotCoreCutsceneCameraView cutscene_camera; int cutscene_distance, shop, timer; } draw;
#define CORE_DRAW (&draw)
static bool playing=true, busy;
static unsigned reads;
static OotCoreCutsceneCameraView source;
static struct { int x,y,z; } recomp_camera;
static uint16_t recomp_yaw;
static int32_t recomp_pitch;
static int read_camera(OotCoreCutsceneCameraView *out) {
    assert(!busy); ++reads; *out=source; return source.active;
}
static void read_other(void* out) { assert(!busy); *(int*)out=0; }
static struct { int (*cutscene_camera)(OotCoreCutsceneCameraView *); void (*shop_view)(void*); void (*timer_view)(void*); } api={read_camera,read_other,read_other};
#define ENTRY (&api)
static void kokiri_camera_sincos(uint16_t angle,int *s,int *c) {
    double radians=angle*6.283185307179586/65536.0;
    *s=(int)lround(sin(radians)*65536); *c=(int)lround(cos(radians)*65536);
}
static uint16_t collide_heading(int x,int z) {
    return (uint16_t)lround(atan2(x,z)*65536.0/6.283185307179586);
}
static uint32_t collide_isqrt(uint32_t n) { return (uint32_t)sqrt(n); }
'''
        for marker in ('const OotCoreCutsceneCameraView* oot_core_cutscene_camera(',
                       'int oot_core_cutscene_screen_distance(', 'static void read_cutscene_camera(',
                       'void oot_core_cutscene_camera_apply('):
            code += graphics.function(host, marker)
        self.run_c(code + r'''
int main(void) {
    source=(OotCoreCutsceneCameraView){.eye={100,200,300},.at={100,200,500},.fov_q8=60*256,.active=1,.roll=-512};
    read_cutscene_camera();
    assert(reads==1);
    assert(oot_core_cutscene_screen_distance()>=207 && oot_core_cutscene_screen_distance()<=209);
    busy=true; source.eye[0]=9000; source.fov_q8=10*256;
    assert(oot_core_cutscene_camera()->eye[0]==100);
    oot_core_cutscene_camera_apply();
    assert(recomp_camera.x==100 && recomp_camera.y==200 && recomp_camera.z==300);
    assert(recomp_yaw==0 && recomp_pitch==0 && reads==1);
    busy=false; source.fov_q8=50*256; read_cutscene_camera();
    assert(oot_core_cutscene_screen_distance()>=256 && oot_core_cutscene_screen_distance()<=258);
    source.eye[0]=-30000; source.eye[1]=-30000; source.eye[2]=-30000;
    source.at[0]=30000; source.at[1]=30000; source.at[2]=30000;
    read_cutscene_camera(); oot_core_cutscene_camera_apply();
    assert(recomp_yaw==0x2000 && recomp_pitch<-6000 && recomp_pitch>-6700);
    source.active=0; source.letterbox=22; read_cutscene_camera();
    assert(!oot_core_cutscene_screen_distance() && oot_core_cutscene_camera()->letterbox==22);
    recomp_camera.x=17; oot_core_cutscene_camera_apply(); assert(recomp_camera.x==17);
    playing=false; assert(!oot_core_cutscene_camera() && !oot_core_cutscene_screen_distance());
    return 0;
}
''')


if __name__ == '__main__':
    unittest.main()
