"""Production actor view rows must not keep sprite identities across scenes."""
from pathlib import Path
import unittest

import test_graphics_backend as graphics

ROOT = Path(__file__).resolve().parents[1]
API = (ROOT / 'oot-core/include/oot_core_api.h').as_posix()


class CoreViews(unittest.TestCase):
    run_c = graphics.GraphicsBackend.run_c

    def test_render_queries_ignore_poison_and_preserve_low_ram_bounds(self):
        text = (ROOT / 'src/kokiri_sgl.c').read_text()
        start = text.index('#define OOT_ACTOR_EN_ITEM00')
        end = text.index('\n#endif\n\nvoid kokiri_rupees_draw', start)
        self.run_c(r'''
#include <assert.h>
#include <stdint.h>
#include <string.h>
''' + '#include "' + API + '"\n#include "' + (ROOT/'src/ram_low.h').as_posix() + '"\n' + r'''
static uint32_t low_words[(RAM_LOW_CORE_VIEW_BYTES+16)/4];
#undef RAM_LOW
#define RAM_LOW(offset) ((void *)((unsigned char *)low_words+8+(offset)-RAM_LOW_CORE_VIEW_OFFSET))
#define __sh__
typedef int32_t FIXED;
typedef uint16_t Uint16;
typedef struct { unsigned texno,atrb; } SPR_ATTR;
#define SPR_ATTRIBUTE(a,b,c,d,e) ((SPR_ATTR){0,0})
#define No_Palet 0
#define No_Gouraud 0
#define ECdis 0
#define sprNoflip 0
#define FUNC_Sprite 0
#define FAIRY_COLMODE_RGB 5
#define FALSE 0
#define FOREST_FAR 100
static struct { int x,y,z; } recomp_camera;
static unsigned grass_sprite=77,kokiri_rejected;
static OotCoreActorView rows[24];
static int row_count,wanted_category,query_calls,drop_count,grass_count;
static int dx[24],dy[24],dz[24],dtype[24];
static FIXED grass_positions[24][5];
static int oot_core_view(int category,OotCoreActorView *out,int capacity) {
    assert(category==wanted_category && capacity==24);
    assert(out==(OotCoreActorView *)RAM_LOW(RAM_LOW_CORE_VIEW_OFFSET));
    assert(row_count>=0 && row_count<=capacity);++query_calls;
    memcpy(out,rows,row_count*sizeof(*out));return row_count;
}
static void kokiri_drop_draw(unsigned type,int x,int y,int z,unsigned tick) {
    assert(tick==17 && drop_count<24);dtype[drop_count]=type;
    dx[drop_count]=x;dy[drop_count]=y;dz[drop_count++]=z;
}
static int slPutSprite(FIXED *pos,SPR_ATTR *attr,int priority) {
    assert(attr->texno==77 && attr->atrb==(5<<3) && priority==0 && grass_count<24);
    memcpy(grass_positions[grass_count++],pos,5*sizeof(FIXED));return 1;
}
''' + text[start:end] + r'''
static void guards(void) {
    unsigned i;unsigned char *bytes=(unsigned char *)low_words;
    for(i=0;i<8;++i)assert(bytes[i]==0xA5);
    for(i=8+24*sizeof(OotCoreActorView);i<sizeof low_words;++i)assert(bytes[i]==0xA5);
}
static void populate(int id) {
    int i;row_count=24;
    for(i=0;i<24;++i)rows[i]=(OotCoreActorView){id,0x100+i,i,2*i,-i,OOT_CORE_VIEW_DRAWN};
}
int main(void) {
    int i;
    memset(low_words,0xA5,sizeof low_words);
    wanted_category=8;core_drops_draw(17);assert(drop_count==0);guards();
    wanted_category=6;core_grass_draw();assert(grass_count==0);guards();
    populate(OOT_ACTOR_EN_ITEM00);wanted_category=8;core_drops_draw(17);
    assert(drop_count==24);
    for(i=0;i<24;++i)assert(dx[i]==i && dy[i]==2*i+14 && dz[i]==-i && dtype[i]==i);
    guards();
    /* Empty and partial category results must not reuse previous rows. */
    row_count=0;wanted_category=6;core_grass_draw();assert(grass_count==0);guards();
    populate(OOT_ACTOR_EN_KUSA);core_grass_draw();assert(grass_count==24);
    for(i=0;i<24;++i) {
        assert(grass_positions[i][0]==i*65536 && grass_positions[i][1]==-(2*i+20)*65536);
        assert(grass_positions[i][2]==-i*65536 && grass_positions[i][3]==98304 && grass_positions[i][4]==81920);
    }
    guards();drop_count=grass_count=0;row_count=1;
    rows[0]=(OotCoreActorView){OOT_ACTOR_EN_ITEM00,3,7,8,9,OOT_CORE_VIEW_DRAWN};
    wanted_category=8;core_drops_draw(17);assert(drop_count==1 && dx[0]==7 && dy[0]==22 && dz[0]==9);
    wanted_category=6;core_grass_draw();assert(grass_count==0);
    rows[0].id=OOT_ACTOR_EN_KUSA;rows[0].flags|=OOT_CORE_VIEW_GRASS_CUT;
    core_grass_draw();assert(grass_count==0);
    rows[0].flags=0;core_grass_draw();assert(grass_count==0);
    rows[0].flags=OOT_CORE_VIEW_DRAWN;rows[0].x=200;core_grass_draw();assert(grass_count==0);
    rows[0].x=7;core_grass_draw();assert(grass_count==1 && grass_positions[0][0]==7*65536);
    rows[0].id=OOT_ACTOR_EN_ITEM00;rows[0].flags=0;
    wanted_category=8;core_drops_draw(17);assert(drop_count==1);
    rows[0].flags=OOT_CORE_VIEW_DRAWN;rows[0].x=200;core_drops_draw(17);assert(drop_count==1);
    row_count=0;core_drops_draw(17);assert(drop_count==1);
    guards();assert(query_calls==14 && kokiri_rejected==0);
    return 0;
}
''')

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
