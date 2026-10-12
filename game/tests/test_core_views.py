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
#include <string.h>
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
    struct { Vec rot; int yOffset,shadowAlpha; } shape;
    struct { float x,y,z; } scale;
    int colorFilterTimer,colorFilterParams,category,gravity,flags;
};
typedef struct { int curFrame,limbCount; void *animation; void **skeleton; } SkelAnime;
typedef struct { Vec headRot,torsoRot; } NpcInteractInfo;
typedef struct { Actor actor; NpcInteractInfo interactInfo; SkelAnime skelAnime; int modelAlpha; } EnKo;
typedef struct { Actor actor; NpcInteractInfo interactInfo; SkelAnime skelAnime; int alpha; } EnMd;
typedef struct { Actor actor; int breakFlags; } EnSkb;
typedef struct { Actor actor; struct { unsigned char a; } lightColor; } EnPoField;
#define ACTOR_EN_SKB 4
#define ACTOR_EN_PEEHAT 5
#define ACTOR_EN_PO_FIELD 6
#define ACTOR_EN_SB 7
#define ACTOR_EN_WEIYER 8
#define ACTOR_EN_TITE 9
#define ACTOR_EN_FIREFLY 10
#define TEKTITE_BLUE (-2)
#define ACTOR_FLAG_REACT_TO_LENS 0x80
typedef struct { Actor actor; } EnTite;
typedef struct { Actor actor; unsigned char bodyElementalType; } EnFirefly;
#define ACTOR_EN_NY 11
typedef struct { Actor actor; int unk_1D4,unk_1D8; float unk_1E0; } EnNy;
typedef struct { void *draw; } ActorProfile;
static struct { const ActorProfile *profile; } gActorOverlayTable[16];
#define gEnNySpikeDL ((char*)0x06000460)
#define gEnNyRockBodyDL ((char*)0x06000180)
#define ACTORCAT_MISC 0
typedef struct {
    struct { struct { Actor *head; } actorLists[1]; unsigned char lensActive; } actorCtx;
    struct { struct { int id; } slots[1]; } objectCtx;
} PlayState;
#define ACTORCAT_MAX 1
#define ACTOR_EN_KO 1
#define ACTOR_EN_MD 2
#define NPC_VIEW_MAX 16
static OotCoreNpcView sNpcView[NPC_VIEW_MAX];
static PlayState *gOotCorePlay;
static u32 gOotCoreFlags=OOT_CORE_FLAG_NPC_SPRITES;
static SkelAnime generic={3,20,(void*)0x06001234,(void**)0x06005555};
static const SkelAnime *GenericNpc_Skel(Actor *a) { return a->id>=3 && a->id!=12 ? &generic : 0; }
static int captured[36];
static const int *OotCore_SkinMats(Actor *a,unsigned char *n,unsigned short *m) {
    if(a->id==12) {*n=3;*m=7;return captured;}
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
    assert(rows[0].skeleton==0x06005555 && rows[1].skeleton==0x06005555);
    ko.actor.id=ACTOR_EN_KO; md.actor.id=ACTOR_EN_MD;
    ko.actor.update=ko.actor.draw=md.actor.update=md.actor.draw=(void*)1;
    ko.actor.next=&md.actor; play.actorCtx.actorLists[0].head=&ko.actor;
    ko.actor.world.pos.x=123; ko.modelAlpha=255; md.alpha=128;
    ko.interactInfo.headRot.y=41; md.skelAnime.curFrame=7;
    assert(OotCore_NpcView(&rows)==2);
    for(int i=0;i<2;++i) {
        assert(rows[i].object==0 && rows[i].limbs==0 && rows[i].anim==0 && !rows[i].skeleton);
        assert(rows[i].flags & OOT_CORE_VIEW_DRAWN);
    }
    assert(rows[0].x==123 && rows[0].head_y==41 && rows[1].frame==7);
    assert(rows[1].alpha==128);
    EnSkb stal={0};
    stal.actor.id=ACTOR_EN_SKB; stal.actor.update=stal.actor.draw=(void*)1;
    stal.actor.scale.x=stal.actor.scale.y=0.02f; stal.breakFlags=2;
    stal.actor.colorFilterTimer=3; stal.actor.colorFilterParams=0x4000;
    play.actorCtx.actorLists[0].head=&stal.actor;
    assert(OotCore_NpcView(&rows)==1 && rows[0].scale_x==512 && rows[0].scale_y==512);
    assert(rows[0].tint==8 && rows[0].anim==(0x06001234|0x100000));
    EnPoField poe={0}; poe.actor.id=ACTOR_EN_PO_FIELD;
    poe.actor.update=poe.actor.draw=(void*)1; poe.actor.scale.x=poe.actor.scale.y=0.01f;
    poe.actor.params=1; poe.actor.gravity=-1; poe.lightColor.a=80;
    play.actorCtx.actorLists[0].head=&poe.actor;
    assert(OotCore_NpcView(&rows)==1 && rows[0].alpha==255);
    assert(((rows[0].anim>>20)&15)==2);
    poe.actor.gravity=0;
    assert(OotCore_NpcView(&rows)==1 && rows[0].alpha==80);
    assert(((rows[0].anim>>20)&15)==4 && rows[0].tint==0);
    Actor stinger={0}; stinger.id=ACTOR_EN_WEIYER;
    stinger.update=stinger.draw=(void*)1;
    stinger.scale.x=stinger.scale.y=0.01f; stinger.shape.shadowAlpha=64;
    play.actorCtx.actorLists[0].head=&stinger;
    assert(OotCore_NpcView(&rows)==1 && rows[0].alpha==64 && rows[0].scale_x==256);
    stinger.id=ACTOR_EN_SB; stinger.scale.x=stinger.scale.y=0.006f;
    assert(OotCore_NpcView(&rows)==1 && rows[0].alpha==255 && rows[0].scale_x==153);
    EnTite tite={0}; tite.actor.id=ACTOR_EN_TITE; tite.actor.update=tite.actor.draw=(void*)1;
    tite.actor.scale.x=tite.actor.scale.y=0.01f; tite.actor.params=-1;
    play.actorCtx.actorLists[0].head=&tite.actor;
    assert(OotCore_NpcView(&rows)==1 && ((rows[0].anim>>20)&15)==0);
    tite.actor.params=TEKTITE_BLUE;
    assert(OotCore_NpcView(&rows)==1 && ((rows[0].anim>>20)&15)==1);
    EnFirefly keese={0}; keese.actor.id=ACTOR_EN_FIREFLY; keese.actor.update=keese.actor.draw=(void*)1;
    keese.actor.scale.x=keese.actor.scale.y=0.005f;
    play.actorCtx.actorLists[0].head=&keese.actor;
    assert(OotCore_NpcView(&rows)==1 && ((rows[0].anim>>20)&15)==0);
    assert(rows[0].flags & OOT_CORE_VIEW_DRAWN);
    keese.bodyElementalType=1;
    assert(OotCore_NpcView(&rows)==1 && ((rows[0].anim>>20)&15)==1);
    keese.actor.flags=ACTOR_FLAG_REACT_TO_LENS;
    assert(OotCore_NpcView(&rows)==1 && !(rows[0].flags & OOT_CORE_VIEW_DRAWN));
    play.actorCtx.lensActive=1;
    assert(OotCore_NpcView(&rows)==1 && (rows[0].flags & OOT_CORE_VIEW_DRAWN));
    static ActorProfile nyProfile={(void*)2};
    gActorOverlayTable[ACTOR_EN_NY].profile=&nyProfile;
    EnNy ny={0}; ny.actor.id=ACTOR_EN_NY; ny.actor.update=(void*)1; ny.actor.draw=(void*)2;
    ny.actor.scale.x=ny.actor.scale.y=0.01f; ny.unk_1D4=255; ny.unk_1E0=0.25f;
    play.actorCtx.actorLists[0].head=&ny.actor;
    assert(OotCore_NpcView(&rows)==1 && rows[0].anim==0x06000460 && rows[0].skeleton==0x06000180);
    assert(rows[0].limbs==0 && rows[0].frame==0 && (rows[0].flags & OOT_CORE_VIEW_DRAWN));
    ny.unk_1D4=0; ny.unk_1D8=255;
    assert(OotCore_NpcView(&rows)==1 && rows[0].anim==(0x06000460|0x100000));
    ny.unk_1E0=1.0f;
    assert(OotCore_NpcView(&rows)==1 && rows[0].anim==(0x06000460|0x200000));
    ny.actor.draw=(void*)3; /* source death-effect draw */
    assert(OotCore_NpcView(&rows)==1 && !(rows[0].flags & OOT_CORE_VIEW_DRAWN));
    /* Rejected live props and killed actors leave every output byte alone. */
    Actor rejected[2]={{0}};
    rejected[0].update=(void*)1;rejected[0].next=&rejected[1];
    rejected[1].id=3;
    play.actorCtx.actorLists[0].head=rejected;
    memset(sNpcView,0xA5,sizeof sNpcView);
    assert(OotCore_NpcView(&rows)==0);
    for(unsigned i=0;i<sizeof sNpcView;++i) assert(((unsigned char*)sNpcView)[i]==0xA5);
    /* Accepted capture fallback clears all previous generic-sheet metadata. */
    Actor fallback={0};fallback.id=12;fallback.update=(void*)1;
    fallback.world.pos=(Vec){17,23,31};fallback.shape.rot.y=1234;
    play.actorCtx.actorLists[0].head=&fallback;
    assert(OotCore_NpcView(&rows)==1);
    assert(rows[0].id==12 && rows[0].x==17 && rows[0].y==23 && rows[0].z==31 && rows[0].yaw==1234);
    assert(rows[0].mats==captured && rows[0].mat_count==3 && rows[0].skin==7);
    assert(!rows[0].object && !rows[0].limbs && !rows[0].anim && !rows[0].skeleton && !rows[0].tint);
    assert(rows[0].scale_x==256 && rows[0].scale_y==256 && rows[0].alpha==255);
    /* Capacity and actor order: interleaved rejected props cannot consume
     * rows or change the exact accepted sprite values. */
    Actor many[40]={{0}};
    for(int i=0;i<40;++i) {
        many[i].id=i%2 ? 3 : 0;many[i].update=many[i].draw=(void*)1;
        many[i].world.pos=(Vec){i,i*2,-i};many[i].params=i;
        many[i].next=i<39 ? &many[i+1] : NULL;
    }
    play.actorCtx.actorLists[0].head=many;
    assert(OotCore_NpcView(&rows)==NPC_VIEW_MAX);
    for(int i=0;i<NPC_VIEW_MAX;++i) {
        const OotCoreNpcView *v=&rows[i];int key=2*i+1;
        assert(v->id==3 && v->params==key && v->x==key && v->y==key*2 && v->z==-key);
        assert(v->object==play.objectCtx.slots[0].id && v->limbs==20 && v->anim==0x06001234 && v->skeleton==0x06005555);
        assert(v->scale_x==256 && v->scale_y==256 && !v->tint && !v->mats && !v->mat_count && !v->skin);
        assert(v->frame==3 && v->alpha==255 && v->flags==OOT_CORE_VIEW_DRAWN);
        assert(!v->yaw && !v->head_x && !v->head_y && !v->torso_x && !v->torso_y);
    }
    return 0;
}
''')


if __name__ == '__main__':
    unittest.main()
