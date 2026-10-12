"""Unused source sign queries must not delay starting the slave update."""
import unittest
import test_graphics_backend as graphics
from test_graphics_backend import ROOT, function


class SignSnapshotCost(unittest.TestCase):
    run_c = graphics.GraphicsBackend.run_c

    def test_sign_owner_gates_queries_without_changing_other_snapshots(self):
        self.run_c(r'''
#include <stdbool.h>
#include <assert.h>
#define KOKIRI_SIGN_COUNT 20
#define SAVE_SCENE_KOKIRI_FOREST 1
#define SNAP_NPC_MAX 2
#define OOT_CORE_DRAW_ITEMS_MAX 2
#define OOT_CORE_TOOL_VIEWS_MAX 2
#define SNAP_VIEW_MAX 2
#define OOT_CORE_EFFECT_VIEWS_MAX 2
typedef struct {int value;} OotCoreNpcView;
typedef OotCoreNpcView OotCoreDrawItem;
typedef OotCoreNpcView OotCoreToolView;
typedef OotCoreNpcView OotCoreEffectView;
static struct {unsigned scene_id;} save_state;
static struct {int x,z;} kokiri_signs[KOKIRI_SIGN_COUNT];
static int source_owned, queries, other_queries;
static bool oot_core_owns_kokiri_npcs(void) {return source_owned;}
static int prop_query(short id,int x,int z) {
    assert(id==0x141 && x==queries && z==100+queries);
    ++queries; return x+9;
}
static OotCoreNpcView rows[3]={{12},{34},{56}};
static int view(const OotCoreNpcView** out) {*out=rows;++other_queries;return 3;}
static int actor_view(int cat,OotCoreNpcView*out,int cap) {
    assert((cat==6 || cat==8) && cap==2);
    out[0].value=cat;++other_queries;return 1;
}
static int effects(OotCoreEffectView*out,unsigned cap,unsigned*omit) {
    assert(cap==2 && *omit==0);out[0].value=77;++other_queries;return 1;
}
static struct {
    int (*prop_query)(short,int,int);
    int (*npc_view)(const OotCoreNpcView**);
    int (*draw_items)(const OotCoreDrawItem**);
    int (*tool_view)(const OotCoreToolView**);
    int (*actor_view)(int,OotCoreNpcView*,int);
    int (*effect_view)(OotCoreEffectView*,unsigned,unsigned*);
} entry={prop_query,view,view,view,actor_view,effects};
#define ENTRY_RAW (&entry)
static int snap_sign_parts[KOKIRI_SIGN_COUNT];
static OotCoreNpcView snap_npc[2],snap_items[2],snap_tools[2],snap_view[2][2];
static int snap_npc_n,snap_items_n,snap_tools_n,snap_view_n[2],snap_effect_n;
''' + function(ROOT/'src/oot_core_host.c','static void snapshot_views(void)') + r'''
int main(void) {
    for(int i=0;i<KOKIRI_SIGN_COUNT;++i) {kokiri_signs[i].x=i;kokiri_signs[i].z=100+i;}
    for(int pass=0;pass<4;++pass) {
        source_owned=pass!=0;
        save_state.scene_id=pass==2 ? 2 : SAVE_SCENE_KOKIRI_FOREST;
        queries=other_queries=0;
        snapshot_views();
        assert(queries==((pass==1 || pass==3) ? KOKIRI_SIGN_COUNT : 0));
        for(int i=0;i<KOKIRI_SIGN_COUNT;++i)
            assert(snap_sign_parts[i]==((pass==1 || pass==3) ? i+9 : -1));
        assert(other_queries==6 && snap_npc_n==2 && snap_items_n==2 && snap_tools_n==2);
        assert(snap_npc[1].value==34 && snap_items[1].value==34 && snap_tools[1].value==34);
        assert(snap_view_n[0]==1 && snap_view_n[1]==1 && snap_effect_n==1);
        assert(snap_view[0][0].value==6 && snap_view[1][0].value==8);
    }
    return 0;
}
''')


if __name__ == '__main__':
    unittest.main()
