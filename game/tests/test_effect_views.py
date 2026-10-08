"""Effect snapshots have bounded output and never own effect simulation/SFX."""
from pathlib import Path
import unittest
import test_graphics_backend as graphics

ROOT = Path(__file__).resolve().parents[1]

class EffectViews(unittest.TestCase):
    run_c = graphics.GraphicsBackend.run_c

    def test_lifecycle_bounds_and_update_only_sounds(self):
        self.run_c(r'''
#include <assert.h>
#include <string.h>
''' + '#include "' + (ROOT/'oot-core/include/oot_core_effects.h').as_posix() + '"\n' + r'''
typedef struct {
    struct { int x,y,z; } pos;
    short regs[13],life;
    unsigned char type,priority;
    void *draw;
} EffectSs;
static struct { EffectSs *table; unsigned int tableSize; } sEffectSsInfo;
#define ACTORCAT_MAX 1
#define ACTOR_EN_PO_FIELD 6
typedef struct Actor { struct Actor *next; int id; void *update; } Actor;
typedef struct { Actor actor; int flameTimer,flameScale; struct { int x,y,z; } flamePosition; } EnPoField;
static struct { struct { struct { Actor *head; } actorLists[1]; } actorCtx; } play,*gOotCorePlay;
#define EFFECT_SS_TYPE_MAX 38
''' + graphics.function(ROOT/'oot-core/src/oot_core_views.cpp', 'int OotCore_EffectView(') + r'''
int main(void) {
    EffectSs source[40] = {0}, before[40];
    struct { unsigned left; OotCoreEffectView rows[32]; unsigned right; } out;
    unsigned omitted=99;
    memset(&out,0xA5,sizeof out);
    sEffectSsInfo.table=source;sEffectSsInfo.tableSize=40;
    for(int i=0;i<40;++i) {
        source[i].draw=(void*)1;source[i].type=2;source[i].life=10;
        source[i].pos.x=i;source[i].regs[12]=i+200;
    }
    assert(OotCore_EffectView(out.rows,100,&omitted)==0 && omitted==0);
    gOotCorePlay=&play;source[0].life=-1;
    source[1].draw=0; /* DeadSound remains update-owned, never a visual. */
    source[2].type=EFFECT_SS_TYPE_MAX;
    memcpy(before,source,sizeof source);
    assert(OotCore_EffectView(out.rows,100,&omitted)==32 && omitted==5);
    assert(out.rows[0].x==3 && out.rows[31].slot==34 && out.rows[31].regs[12]==234);
    assert(out.left==0xA5A5A5A5u && out.right==0xA5A5A5A5u);
    assert(!memcmp(before,source,sizeof source));
    assert(OotCore_EffectView(0,32,&omitted)==0 && omitted==37);
    assert(OotCore_EffectView(out.rows,1,&omitted)==1 && omitted==36);
    sEffectSsInfo.table=0;
    assert(OotCore_EffectView(out.rows,32,&omitted)==0 && omitted==0);
    EnPoField poe={0}; poe.actor.id=ACTOR_EN_PO_FIELD; poe.actor.update=(void*)1;
    poe.flameTimer=50; poe.flameScale=1; poe.flamePosition.x=123;
    play.actorCtx.actorLists[0].head=&poe.actor;
    assert(OotCore_EffectView(out.rows,32,&omitted)==1 && !omitted);
    assert(out.rows[0].type==OOT_CORE_EFFECT_POE_FLAME && out.rows[0].x==123 && out.rows[0].life==50);
    sEffectSsInfo.table=source;
    assert(OotCore_EffectView(out.rows,1,&omitted)==1 && omitted==37);
    assert(out.rows[0].type==OOT_CORE_EFFECT_POE_FLAME); /* damage visual gets first slot */
    poe.flameTimer=0; sEffectSsInfo.table=0;
    assert(OotCore_EffectView(out.rows,32,&omitted)==0 && !omitted);
    return 0;
}
''')

if __name__ == '__main__': unittest.main()
