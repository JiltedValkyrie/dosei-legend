"""Production actor view rows must not keep sprite identities across scenes."""
from pathlib import Path
import unittest

import test_graphics_backend as graphics

ROOT = Path(__file__).resolve().parents[1]
API = (ROOT / 'oot-core/include/oot_core_api.h').as_posix()


class CoreViews(unittest.TestCase):
    run_c = graphics.GraphicsBackend.run_c

    def test_ranch_to_native_forest_clears_generic_sprite_identity(self):
        self.run_c(r'''
#include <assert.h>
#include <stddef.h>
#include <stdint.h>
''' + '#include "' + API + '"\n' + r'''
typedef int s32;
typedef unsigned int u32;
typedef unsigned short u16;
typedef unsigned char u8;
typedef struct { int x,y,z; } Vec;
typedef struct Actor Actor;
struct Actor {
    Actor *next;
    void *update,*draw;
    int id,params,objectSlot;
    struct { Vec pos; } world;
    struct { Vec rot; } shape;
};
typedef struct { int curFrame,limbCount; void *animation; } SkelAnime;
typedef struct { Vec headRot,torsoRot; } NpcInteractInfo;
typedef struct { Actor actor; NpcInteractInfo interactInfo; SkelAnime skelAnime; int modelAlpha; } EnKo;
typedef struct { Actor actor; NpcInteractInfo interactInfo; SkelAnime skelAnime; int alpha; } EnMd;
typedef struct {
    struct { struct { Actor *head; } actorLists[1]; } actorCtx;
    struct { struct { int id; } slots[1]; } objectCtx;
} PlayState;
#define ACTORCAT_MAX 1
#define ACTOR_EN_KO 1
#define ACTOR_EN_MD 2
#define NPC_VIEW_MAX 16
static OotCoreNpcView sNpcView[NPC_VIEW_MAX];
static PlayState *gOotCorePlay;
static u32 gOotCoreFlags=OOT_CORE_FLAG_NPC_SPRITES;
static SkelAnime generic={3,20,(void*)0x06001234};
static const SkelAnime *GenericNpc_Skel(Actor *a) { return a->id==3 ? &generic : 0; }
static const int *OotCore_SkinMats(Actor *a,unsigned char *n,unsigned short *m) {
    *n=0; *m=0; return 0;
}
''' + graphics.function(ROOT / 'oot-core/src/oot_core_views.cpp', 'int OotCore_NpcView(') + r'''
int main(void) {
    PlayState play={0};
    Actor ranch[2]={{0}};
    EnKo ko={0}; EnMd md={0};
    const OotCoreNpcView *rows;
    gOotCorePlay=&play;
    play.objectCtx.slots[0].id=0xc0;
    for(int i=0;i<2;++i) {
        ranch[i].id=3; ranch[i].update=ranch[i].draw=(void*)1;
    }
    ranch[0].next=&ranch[1]; play.actorCtx.actorLists[0].head=&ranch[0];
    assert(OotCore_NpcView(&rows)==2);
    assert(rows[0].object==0xc0 && rows[1].anim==0x06001234 && rows[1].limbs==20);
    ko.actor.id=ACTOR_EN_KO; md.actor.id=ACTOR_EN_MD;
    ko.actor.update=ko.actor.draw=md.actor.update=md.actor.draw=(void*)1;
    ko.actor.next=&md.actor; play.actorCtx.actorLists[0].head=&ko.actor;
    ko.actor.world.pos.x=123; ko.modelAlpha=255; md.alpha=128;
    ko.interactInfo.headRot.y=41; md.skelAnime.curFrame=7;
    assert(OotCore_NpcView(&rows)==2);
    for(int i=0;i<2;++i) {
        assert(rows[i].object==0 && rows[i].limbs==0 && rows[i].anim==0);
        assert(rows[i].flags & OOT_CORE_VIEW_DRAWN);
    }
    assert(rows[0].x==123 && rows[0].head_y==41 && rows[1].frame==7);
    assert(rows[1].alpha==128);
    return 0;
}
''')


if __name__ == '__main__':
    unittest.main()
