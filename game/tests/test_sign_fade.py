"""Actual imported sign hit/read/collision lifecycle, without any fragments."""
import types
import unittest
from test_graphics_backend import ROOT, function
import test_graphics_backend as graphics
import oot_core_import as importer


class SignFade(unittest.TestCase):
    run_c = graphics.GraphicsBackend.run_c

    def test_source_sign_hit_fades_no_fragments_then_distance_reset_restores_collision(self):
        rel = 'src/overlays/actors/ovl_En_Kanban/z_en_kanban.c'
        path = importer.OOT_DEFAULT / rel
        if not path.exists():
            self.skipTest('source decomp required')
        original = path.read_text()
        stats = {'macros': 0, 'problems': []}
        adapted = importer.fix_sign_fade(rel, original, stats)
        adapted_file = types.SimpleNamespace(read_text=lambda: adapted)
        # Reading remains the source function verbatim, including its facing
        # test, offer acceptance and close-message cooldown.
        self.assertEqual(function(path, 'void EnKanban_Message('),
                         function(adapted_file, 'void EnKanban_Message('))
        source = '#include "%s"\n' % (ROOT/'oot-core/include/oot_sign_visual.h').as_posix()
        source += r'''
#include <assert.h>
#include <stdint.h>
#include <string.h>
typedef int32_t s32;
typedef struct {float x,y,z;} Vec3f;
typedef struct Actor {
    struct Actor *next;
    void (*update)(void);
    int id,params,flags,textId,attentionRangeType;
    struct {Vec3f pos;} home,world,focus;
    float xzDistToPlayer;
} Actor;
typedef struct {struct {unsigned acFlags;} base;} Collider;
typedef struct {
    Actor actor;
    uint16_t partFlags;
    int actionState,cutMarkTimer,frameCount,bounceX;
    Collider collider;
} EnKanban;
#define ACTORCAT_MAX 2
typedef struct {int colChkCtx;struct {struct {Actor *head;} actorLists[ACTORCAT_MAX];} actorCtx;} PlayState;
static PlayState play, *gOotCorePlay=&play;
#define ACTOR_EN_KANBAN 0x141
#define ENKANBAN_SIGN 0
#define ENKANBAN_AIR 1
#define ENKANBAN_PIECE ((int16_t)0xffdd)
#define ENKANBAN_FISHING 0x300
#define LINK_IS_CHILD 1
#define ACTOR_FLAG_ATTENTION_ENABLED 1
#define ATTENTION_RANGE_0 0
#define UPDBGCHECKINFO_FLAG_2 4
#define AC_HIT 2
#define NA_SE_IT_SWORD_STRIKE 3
#define PRINTF(...) ((void)0)
static int sCylinderInit,init_collider,ac,oc,messages,sounds,kills;
static void alive(void) {}
static void Actor_Kill(Actor *a) {++kills;a->update=0;}
static void Actor_SetScale(Actor *a,float scale) {assert(scale==0.01f);}
static void Collider_InitCylinder(PlayState *p,Collider *c) {++init_collider;}
static void Collider_SetCylinder(PlayState *p,Collider *c,Actor *a,int *init) {}
static void Actor_UpdateBgCheckInfo(PlayState *p,Actor *a,float x,float y,float z,int flags) {}
static void EnKanban_Message(EnKanban *s,PlayState *p) {++messages;}
static void Actor_PlaySfx(Actor *a,int sound) {assert(sound==NA_SE_IT_SWORD_STRIKE);++sounds;}
static void Collider_UpdateCylinder(Actor *a,Collider *c) {}
static void CollisionCheck_SetAC(PlayState *p,int *ctx,void *c) {++ac;}
static void CollisionCheck_SetOC(PlayState *p,int *ctx,void *c) {++oc;}
'''
        for marker in ('void EnKanban_Init(', 'void EnKanban_Update(', 'void EnKanban_Draw('):
            # Source prototypes precede definitions: select the adapted definition.
            at = adapted.index(marker, adapted.index('void EnKanban_SetFloorRot('))
            source += function(types.SimpleNamespace(read_text=lambda at=at: adapted[at:]), marker)
        source += function(ROOT/'oot-core/src/oot_core_views.cpp', 'int OotCore_PropQuery(')
        source += r'''
int main(void) {
    EnKanban s={0}, old_piece={0};
    s.actor.id=ACTOR_EN_KANBAN;s.actor.params=4;s.actor.update=alive;
    s.actor.world.pos=(Vec3f){1,25,2};s.actor.home.pos=s.actor.world.pos;
    play.actorCtx.actorLists[1].head=&s.actor;
    EnKanban_Init(&s.actor,&play);
    assert(init_collider==1 && s.partFlags==OOT_SIGN_INTACT && s.actor.textId==0x304);
    assert(s.actor.world.pos.y==10);
    EnKanban_Update(&s.actor,&play);
    assert(ac==1 && oc==1 && messages==1);
    assert(s.actor.focus.pos.y==54 && OotCore_PropQuery(ACTOR_EN_KANBAN,1,2)==OOT_SIGN_INTACT);
    s.collider.base.acFlags|=AC_HIT;
    EnKanban_Update(&s.actor,&play);
    assert(!s.partFlags && s.cutMarkTimer==OOT_SIGN_FADE_TICKS);
    assert(!(s.actor.flags&ACTOR_FLAG_ATTENTION_ENABLED) && sounds==1);
    assert(ac==1 && oc==1 && messages==2 && !kills);
    for(unsigned i=OOT_SIGN_FADE_TICKS;i;--i) {
        assert(OotCore_PropQuery(ACTOR_EN_KANBAN,1,2)==i);
        s.collider.base.acFlags|=AC_HIT; /* a second hit never restarts fade */
        EnKanban_Update(&s.actor,&play);
        assert(!(s.collider.base.acFlags&AC_HIT));
        assert(ac==1 && oc==1 && messages==2 && sounds==1 && !kills);
    }
    assert(OotCore_PropQuery(ACTOR_EN_KANBAN,1,2)==0);
    for(unsigned i=0;i<30;++i)EnKanban_Update(&s.actor,&play);
    assert(ac==1 && oc==1 && !s.cutMarkTimer && s.actor.update);
    s.actor.xzDistToPlayer=501;
    EnKanban_Update(&s.actor,&play);
    assert(s.partFlags==OOT_SIGN_INTACT && !s.cutMarkTimer && ac==2 && oc==2 && messages==3);
    assert(s.actor.flags&ACTOR_FLAG_ATTENTION_ENABLED);
    assert(OotCore_PropQuery(ACTOR_EN_KANBAN,100,100)==-1);
    old_piece.actor.params=ENKANBAN_PIECE;old_piece.actor.update=alive;
    EnKanban_Init(&old_piece.actor,&play);
    assert(kills==1 && init_collider==1 && !old_piece.actor.update);
    assert(old_piece.actionState!=ENKANBAN_SIGN); /* destroy cannot free uninitialized collider */
    old_piece.actor.update=alive;
    EnKanban_Update(&old_piece.actor,&play);assert(kills==2 && !old_piece.actor.update);
    EnKanban_Draw(&s.actor,&play); /* no display-list/fragment allocation */
    return 0;
}
'''
        self.run_c(source)
