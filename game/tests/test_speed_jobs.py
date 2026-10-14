"""Exercise the production slave lifecycle and shared skin-cache entry points."""
import unittest
import test_graphics_backend as graphics
from test_graphics_backend import ROOT, function


class SpeedJobs(unittest.TestCase):
    run_c = graphics.GraphicsBackend.run_c

    def test_scene_watchdog_allows_progress_and_reports_a_stall(self):
        source = ROOT / 'src/kokiri_sgl.c'
        self.run_c(r'''
#include <stdbool.h>
#include <assert.h>
static unsigned prep_kicked, prep_done, prep_progress, now, calls, errors, purges, mode;
#define PREP_DONE prep_done
#define PREP_PROGRESS prep_progress
static unsigned frame_timer_ticks(void) {
    now+=100000;
    if(mode==0 && ++calls<12) ++prep_progress;
    if(mode==0 && calls==12) prep_done=1;
    return now;
}
static unsigned frame_timer_ticks_to_us(unsigned ticks) {return ticks;}
static void jo_core_error(const char* message,unsigned progress) {
    ++errors; assert(progress==7); prep_done=1;
}
static void slCashPurge(void) {++purges;}
#define PS_ACC(i, us) ((void)0)
static unsigned kokiri_frame_slave_us(void) {return 0;}
static void prep_phase_take(void) {}
''' + function(source, 'static void prep_wait(') + r'''
int main(void) {
    prep_kicked=1; prep_wait();
    assert(now>1000000 && !errors && purges==1 && !prep_kicked);
    mode=1; prep_kicked=1; prep_done=0; prep_progress=7; now=0;
    prep_wait(); assert(errors==1 && purges==2 && !prep_kicked);
    return 0;
}
''')

    def test_frc_byte_reads_stay_monotonic_with_mednafen_latch(self):
        """FRCH latches FRCL into TEMP (SH7604, Mednafen sh7095). An ISR that
        re-reads FRCH between our two bytes must not make time run backwards,
        or read_ticks counts a false wrap (+293 ms) and trips the watchdog."""
        header = function(ROOT / 'src/frame_timer.h', 'static inline uint16_t frame_timer_frc(')
        header = '\n'.join(l for l in header.splitlines() if '0xFFFFFE1' not in l)
        header = header.replace('*frch', 'rd_h()').replace('*frcl', 'rd_l()')
        ticks = 'static uint32_t ' + function(ROOT / 'src/frame_timer.c', 'read_ticks(void)')
        self.run_c(r'''
#include <stdint.h>
#include <assert.h>
static uint32_t real; static uint8_t temp; static unsigned lreads, relatches;
static uint8_t rd_h(void) { real += 37; temp = (uint8_t)real; return (uint8_t)(real >> 8); }
static uint8_t rd_l(void) {
    real += 37;
    if (++lreads % 7 == 0) { real += 300; temp = (uint8_t)real; ++relatches; } /* ISR reads FRCH */
    return temp;
}
static uint16_t previous_count; static uint32_t extended;
''' + header + '\n' + ticks + r'''
int main(void) {
    uint32_t start_real, prev, now, i;
    previous_count = frame_timer_frc(); extended = 0;
    start_real = real; prev = previous_count;
    for (i = 0; i < 200000; ++i) {
        now = read_ticks();
        assert(now >= prev && now - prev < 4096);
        prev = now;
    }
    /* 32-bit extended count tracks the real counter (< one read apart). */
    assert(real - start_real - (prev - (start_real & 0xFFFF)) < 4096);
    assert(real - start_real > 50u * 65536u && relatches > 1000);
    return 0;
}
''')

    def test_slave_prescale_selects_128_and_keeps_input_edge(self):
        """SGL wakes the slave by FRT input capture: TCR bit 7 (IEDG) stays."""
        body = function(ROOT / 'src/frame_timer.h', 'static inline void frame_timer_slave_prescale(')
        body = body.replace('(volatile uint8_t *)0xFFFFFE16', '&tcr_reg')
        self.run_c(r'''
#include <stdint.h>
#include <assert.h>
static volatile uint8_t tcr_reg;
''' + body + r'''
int main(void) {
    tcr_reg = 0x80; frame_timer_slave_prescale(); assert(tcr_reg == 0x82);
    tcr_reg = 0x01; frame_timer_slave_prescale(); assert(tcr_reg == 0x02);
    tcr_reg = 0x82; frame_timer_slave_prescale(); assert(tcr_reg == 0x82);
    return 0;
}
''')

    def test_no_word_reads_of_the_8bit_frt(self):
        for path in (ROOT / 'src').rglob('*.[ch]'):
            text = path.read_text(errors='replace')
            self.assertNotIn('uint16_t *)0xFFFFFE12', text, path)
            self.assertNotIn('uint32_t *)0xFFFFFE1', text, path)

    def test_collision_stamp_initialization_and_wrap(self):
        source = ROOT / 'build/oot-core/decomp/src/code/z_bgcheck.cpp'
        alloc = function(source, 'void SSNodeList_Alloc(PlayState* play, SSNodeList* this, s32 tblMax, s32 numPolys) {')
        self.run_c(r'''
#include <stdint.h>
#include <string.h>
#include <assert.h>
typedef int32_t s32;
typedef uint8_t u8;
typedef struct { int node; } SSNode;
typedef struct { int max,count; SSNode* tbl; u8* polyCheckTbl; } SSNodeList;
typedef struct { struct {int tha;} state; } PlayState;
static SSNode nodes[16];
static u8 bytes[16],gOotCoreBgCheckStamp=1;
#define THA_AllocTailAlign(...) nodes
#define GAME_STATE_ALLOC(...) bytes
#define ALIGNOF_MASK(t) 3
#define ASSERT(c,...) assert(c)
''' + alloc + function(source, 'void BgCheck_ResetPolyCheckTbl(SSNodeList* nodeList, s32 numPolys) {') + r'''
int main(void){
    PlayState play={0};SSNodeList list={0};
    memset(bytes,2,sizeof bytes);SSNodeList_Alloc(&play,&list,16,16);
    BgCheck_ResetPolyCheckTbl(&list,16);
    for(int i=0;i<16;++i)assert(bytes[i]!=gOotCoreBgCheckStamp);
    for(int query=0;query<600;++query){
        bytes[query%16]=gOotCoreBgCheckStamp;
        BgCheck_ResetPolyCheckTbl(&list,16);
        assert(gOotCoreBgCheckStamp!=0);
        for(int i=0;i<16;++i)assert(bytes[i]!=gOotCoreBgCheckStamp);
    }
    memset(bytes,gOotCoreBgCheckStamp+1,sizeof bytes);
    SSNodeList_Alloc(&play,&list,16,16);BgCheck_ResetPolyCheckTbl(&list,16);
    for(int i=0;i<16;++i)assert(bytes[i]!=gOotCoreBgCheckStamp);
    return 0;
}
''')

    def test_uncached_busy_controls_kick_guard_and_join(self):
        source = ROOT / 'src/oot_core_host.c'
        self.run_c(r'''
#include <stdbool.h>
#include <stdint.h>
#include <assert.h>
typedef struct { int (*tool)(unsigned,int*); void (*player_push)(int*,int*); } OotCoreEntry;
static int tool(unsigned c,int*p){return 0;}
static void push(int*x,int*z){*x=*z=0;}
static OotCoreEntry entry={tool,push};
#define ENTRY_RAW (&entry)
/* Separate cached and uncached values deliberately reproduce SH-2 stale
 * cache lines. The other CPU's alias writes do not update cached copies. */
static unsigned char async_busy, uncached_async_busy;
static unsigned async_violations, async_violation_line, core_due, async_updates, async_kick_tick;
static unsigned async_overlap_us, async_join_us, async_slave_us, update_us;
static unsigned uncached_sfx_queued, sfx_queued, deferred_fatal[4], sfx_queue[32];
static bool playing=true;
static int meshes_room=0;
static unsigned snapshots, jobs, readbacks, now;
static struct { unsigned updates,done,us; } box;
static struct {unsigned tool_bits;int tool_pull[6];} draw;
static struct {int x,z;} recomp_link;
#define UNCACHED(v) uncached_##v
#define ASYNC_BUSY() (UNCACHED(async_busy) != 0)
#define BOX (&box)
#define CORE_DRAW (&draw)
#define SFX_QUEUE 32
#define OOT_CORE_TOOL_STATE 0
#define OOT_CORE_TOOL_MAGIC_RESET 1
static bool gameplay_is_paused(void){return false;}
static bool responsive;
static bool ui_core_responsive(void){return responsive;}
static bool cdda_busy(void){return false;}
static void snapshot_views(void){snapshots++;}
static unsigned frame_timer_ticks(void){return ++now;}
static unsigned frame_timer_ticks_to_us(unsigned t){return t;}
static void slave_job(void*a){}
static void slSlaveFunc(void(*fn)(void*),void*a){jobs++;}
#define PS_ACC(i, us) ((void)0)
static void slCashPurge(void){}
static void jo_core_error(const char*s){assert(0);}
static void host_sfx_now(unsigned s){}
static void host_fatal(unsigned a,unsigned b,unsigned c){assert(0);}
static void read_player(void){readbacks++;}
static void health_hud_magic_reset(void){}
static void health_hud_magic_update(void){}
static bool scene_flow_is_interior(void){return false;}
static int kokiri_bank_room(void){return 0;}
static void load_meshes(void){}
static bool sprites_refresh(void){return false;}
static void npc_draw_reupload(void){}
''' + function(source, 'static inline const OotCoreEntry *entry_checked(') + r'''
#define ENTRY (entry_checked(__LINE__))
''' + function(source, 'void oot_core_async_kick(')
            + function(source, 'void oot_core_async_join(') + r'''
int main(void){
    async_busy=0;uncached_async_busy=1;core_due=1;
    entry_checked(__LINE__);assert(async_violations==1);
    oot_core_async_kick();assert(jobs==0 && snapshots==0 && core_due==1);
    box.done=1;box.us=123;async_updates=1;
    oot_core_async_join();assert(readbacks==1 && async_slave_us==123);
    assert(!uncached_async_busy);
    /* A stale cached one must not block a fresh kick or invent a join. */
    async_busy=1;
    oot_core_async_join();assert(readbacks==1);
    responsive=true;
    oot_core_async_kick();assert(jobs==0 && snapshots==0 && core_due==1);
    responsive=false;
    oot_core_async_kick();assert(jobs==1 && snapshots==1 && uncached_async_busy==1);
    assert(core_due==0 && box.updates==1 && box.done==0);
    return 0;
}
''')

    def test_sync_and_slave_skin_share_one_pose_key(self):
        source = ROOT / 'src/link_anim.c'
        self.run_c(r'''
#include <stdint.h>
#include <stdbool.h>
#include <string.h>
#include <assert.h>
#define LINK_LIMB_COUNT 21
static int16_t last_source_joints[3+LINK_LIMB_COUNT*3];
static int posed_frame=-1, skin_kicked, skin_done, pose, vertices, skins;
#define SKIN_DONE skin_done
static void link_anim_sync(void){}
static void pose_skeleton(const int16_t*r,const int16_t*j){pose=r[0];}
static void skin_vertices(void){vertices=pose;skins++;}
static void skin_slave_job(void*a){skin_vertices();}
static void slSlaveFunc(void(*fn)(void*),void*a){fn(a);}
''' + function(source, 'void link_anim_frame_start(')
            + function(source, 'void link_anim_pose_joints(') + r'''
int main(void){
    int16_t a[66]={1},b[66]={2};
    link_anim_frame_start(a,true);assert(vertices==1);
    link_anim_pose_joints(b);assert(vertices==2);
    link_anim_frame_start(a,true);assert(vertices==1);
    link_anim_pose_joints(b);assert(vertices==2);
    assert(skins==4);
    link_anim_frame_start(b,true);link_anim_pose_joints(b);assert(skins==4);
    posed_frame=-1;link_anim_frame_start(b,true);assert(skins==5);
    return 0;
}
''')

    def test_hidden_skin_keeps_anchors_joins_pending_and_refreshes_visible_or_age(self):
        source = ROOT / 'src/link_anim.c'
        code = r'''
#include <stdint.h>
#include <stdbool.h>
#include <string.h>
#include <assert.h>
#define PLAYER_SOURCE 1
#define LINK_LIMB_COUNT 21
typedef int limb_matrix_t;
static limb_matrix_t limb_matrices[LINK_LIMB_COUNT];
static int16_t last_source_joints[3+LINK_LIMB_COUNT*3];
static int posed_frame=-1,upper_clip=-1,skin_kicked,skin_done;
static int pose,vertices,skins,poses,model_seen;
static int link_age_model=1,pending_model=2,pending_frames;
static void (*pending_job)(void*);
#define SKIN_DONE skin_done
static void pose_skeleton(const int16_t*r,const int16_t*j) {
    assert(!pending_job);pose=r[0];limb_matrices[0]=pose;++poses;
}
static void skin_vertices(void) {vertices=pose;model_seen=link_age_model;++skins;}
static void skin_slave_job(void*a){skin_vertices();skin_done=1;}
static void slSlaveFunc(void(*fn)(void*),void*a){assert(!pending_job);pending_job=fn;}
static void link_anim_sync(void) {
    if(pending_job){void(*fn)(void*)=pending_job;pending_job=0;fn(0);skin_kicked=0;}
}
static void publish_frames(int unused) {assert(!pending_job);}
void link_anim_reset(void);
''' + function(source, 'void link_anim_frame_start(')
        code += function(source, 'void link_anim_pose_joints(')
        code += function(source, 'void link_anim_draw_sync(')
        code += function(source, 'void            link_anim_reset(')
        code += function(source, 'void link_anim_commit_age(')
        code += r'''
int main(void) {
    int16_t a[66]={1},b[66]={2};
    link_anim_frame_start(a,true);
    link_anim_frame_start(b,false); // join old skin before changing matrices
    assert(vertices==1 && pose==2 && limb_matrices[0]==2 && skins==1 && poses==2 && !pending_job);
    link_anim_frame_start(b,false);assert(skins==1 && poses==2);
    link_anim_frame_start(b,true);link_anim_sync();
    assert(vertices==2 && skins==2); // same hidden joints still require vertices
    link_anim_pose_joints(b);assert(skins==2);
    link_anim_frame_start(a,false);link_anim_pose_joints(a);
    assert(vertices==1 && skins==3); // synchronous clip/pose consumer also refreshes
    link_anim_frame_start(b,true);
    link_anim_commit_age();
    assert(!pending_job && model_seen==1 && link_age_model==2 && posed_frame==-1);
    assert(!limb_matrices[0]);
    link_anim_frame_start(b,false);assert(limb_matrices[0]==2 && skins==4);
    link_anim_frame_start(b,true);link_anim_sync();
    assert(vertices==2 && skins==5 && model_seen==2);
    link_anim_frame_start(b,false);link_anim_frame_start(b,true);link_anim_sync();
    assert(skins==5); // already skinned unchanged bones remain valid
    link_anim_frame_start(a,false);assert(vertices==2 && skins==5);
    link_anim_draw_sync(); // first-person exits during this frame's steps
    assert(vertices==1 && skins==6 && posed_frame==-2 && !pending_job);
    link_anim_draw_sync();assert(skins==6);
    return 0;
}
'''
        for defines in ('', '#define DOSEI_NO_SLAVE_JOBS 1\n'):
            with self.subTest(defines=defines):
                self.run_c(defines + code)
