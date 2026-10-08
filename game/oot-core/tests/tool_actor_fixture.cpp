/* Actual bridge + imported En_Arrow/Arms_Hook/En_Bom actions, fake engine I/O.
 * No renderer runs: gameplay anchors must be supplied by the sprite bridge. */
#include "oot_prelude.h"
#include "ultra64.h"
#include "actor.h"
#include "play_state.h"
#include "player.h"
#include "item.h"
#include "z_lib.h"
#include "z_math.h"
#include "save.h"
#include "regs.h"
#include "effect.h"
#include "ichain.h"
#include "oot_core_api.h"
#include "overlays/actors/ovl_En_Arrow/z_en_arrow.h"
#include "overlays/actors/ovl_Arms_Hook/z_arms_hook.h"
#include "overlays/actors/ovl_En_Bom/z_en_bom.h"
#include "overlays/actors/ovl_En_Boom/z_en_boom.h"

extern "C" int printf(const char*, ...);
extern "C" void abort(void);
#define CHECK(x) do { if (!(x)) { printf("line %d: %s\n", __LINE__, #x); abort(); } } while (0)

PlayState* gOotCorePlay;
SaveContext gSaveContext;
static RegEditor regs;
RegEditor* gRegEditor = &regs;
Vec3f gSfxDefaultPos;
f32 gSfxDefaultFreqAndVolScale;
s8 gSfxDefaultReverb;
static PlayState play;
static Player player;
static EnArrow arrows[8];
static ArmsHook hook;
static EnBom bomb;
static EnBoom boom;
static int arrowCount, atCount, spawnFail, deferred, hookable, lineHit, spawnCalls;
static Vec3f lastLineStart, lastLineEnd;
static CollisionPoly hitPoly;
static Vec3f clipPoint;
static int lineClip;

void EnArrow_Init(Actor*, PlayState*);
void EnArrow_Update(Actor*, PlayState*);
void EnArrow_CarryActor(EnArrow*, PlayState*);
void ArmsHook_Init(Actor*, PlayState*);
void ArmsHook_Update(Actor*, PlayState*);
void ArmsHook_Wait(ArmsHook*, PlayState*);
void ArmsHook_Shoot(ArmsHook*, PlayState*);
void EnBom_Explode(EnBom*, PlayState*);
void EnBoom_Init(Actor*, PlayState*);
void EnBoom_Update(Actor*, PlayState*);
int OotCore_ToolCommand(unsigned int, int*);
void OotCore_ToolStep(PlayState*);
void OotCore_ToolReset(void);
int OotCore_ToolView(const OotCoreToolView**);

static void idle(Actor*, PlayState*) {}
/* Engine fixture supplies a held bomb body; the tested blast action remains
 * the real imported EnBom_Explode. Fuse/movement initialization is separate. */
static void bomb_body_init(Actor* a, PlayState*) {
    EnBom* b=(EnBom*)a;
    b->timer=70;b->explosionCollider.elements=b->explosionColliderElements;
    b->explosionColliderElements[0].base.atDmgInfo.dmgFlags=DMG_EXPLOSIVE;
    b->explosionColliderElements[0].base.atDmgInfo.damage=8;
}
void Actor_Kill(Actor* a) { a->update = NULL; }
void Actor_SetScale(Actor*, f32) {}
Actor* Actor_Spawn(ActorContext* ctx, PlayState* p, s16 id, f32 x, f32 y, f32 z,
                   s16 rx, s16 ry, s16 rz, s16 param) {
    ++spawnCalls;
    if (spawnFail) return NULL;
    Actor* a = NULL;
    if (id == ACTOR_EN_ARROW) {
        CHECK(arrowCount < 8); a = &arrows[arrowCount++].actor;
        a->init = EnArrow_Init; a->update = EnArrow_Update;
    } else if (id == ACTOR_ARMS_HOOK) {
        a = &hook.actor; a->init = ArmsHook_Init; a->update = ArmsHook_Update;
    } else if (id == ACTOR_EN_BOOM) {
        a = &boom.actor; a->init = EnBoom_Init; a->update = EnBoom_Update;
    } else if (id == ACTOR_EN_BOM) {
        a = &bomb.actor; a->init = bomb_body_init; a->update = idle;
    } else return NULL;
    a->id = id; a->params = param; a->world.pos = {x,y,z}; a->prevPos = a->world.pos;
    a->world.rot = {rx,ry,rz}; a->shape.rot = a->world.rot;
    a->minVelocityY = -20;
    int category = id == ACTOR_EN_BOOM ? ACTORCAT_MISC :
        id == ACTOR_EN_BOM ? ACTORCAT_EXPLOSIVE : ACTORCAT_ITEMACTION;
    a->next = ctx->actorLists[category].head;
    ctx->actorLists[category].head = a;
    if (!deferred) { a->init(a,p); a->init = NULL; }
    return a;
}
s32 Collider_InitQuad(PlayState*, ColliderQuad* q) { *q = {}; return 1; }
s32 Collider_SetQuad(PlayState*, ColliderQuad* q, Actor* a, ColliderQuadInit* init) {
    q->base.actor = a; q->base.atFlags = init->base.atFlags;
    q->elem.atDmgInfo = init->elem.atDmgInfo; return 1;
}
s32 Collider_DestroyQuad(PlayState*, ColliderQuad*) { return 1; }
s32 CollisionCheck_SetAT(PlayState*, CollisionCheckContext*, Collider*) { ++atCount; return 1; }
s32 Collider_ResetQuadAT(PlayState*, Collider*) { return 1; }
void Collider_SetQuadVertices(ColliderQuad* q, Vec3f* a, Vec3f* b, Vec3f* c, Vec3f* d) {
    CHECK(a->x != b->x || a->y != b->y || a->z != b->z);
    q->dim.quad[0]=*a; q->dim.quad[1]=*b; q->dim.quad[2]=*c; q->dim.quad[3]=*d;
}
void Player_PlaySfx(Player*, u16) {}
void Actor_PlaySfx(Actor*, u16) {}
void Actor_PlaySfx_Flagged2(Actor*, u16) {}
void Actor_PlaySfx_Flagged(Actor*, u16) {}
void Actor_SetFocus(Actor* a, f32 y) { a->focus.pos=a->world.pos; a->focus.pos.y+=y; }
s16 Actor_WorldYawTowardPoint(Actor* a, Vec3f* b) { return Math_Vec3f_Yaw(&a->world.pos,b); }
s16 Actor_WorldPitchTowardPoint(Actor* a, Vec3f* b) { return Math_Vec3f_Pitch(&a->world.pos,b); }
void Audio_PlaySfxGeneral(u16, Vec3f*, u8, f32*, f32*, s8*) {}
void Effect_Add(PlayState*, s32* index, s32, u8, u8, void*) { *index=0; }
void Effect_Delete(PlayState*, s32) {}
void OotCore_SpriteInitFlex(PlayState*, SkelAnime*, FlexSkeletonHeader*, AnimationHeader*, Vec3s*, Vec3s*, s32) {}
void SkelAnime_Free(SkelAnime*, PlayState*) {}
void Animation_PlayOnce(SkelAnime*, AnimationHeader*) {}
s32 SkelAnime_Update(SkelAnime*) { return 0; }
void CollisionCheck_SpawnShieldParticlesMetal(PlayState*, Vec3f*) {}
void EffectSsStone1_Spawn(PlayState*, Vec3f*, s32) {}
void EffectSsHitMark_SpawnCustomScale(PlayState*, s32, s16, Vec3f*) {}
void SfxSource_PlaySfxAtFixedWorldPos(PlayState*, Vec3f*, s32, u16) {}
void func_8002836C(PlayState*, Vec3f*, Vec3f*, Vec3f*, Color_RGBA8*, Color_RGBA8*, s16, s16, s16) {}
void Rumble_Request(FxSq, u8, u8, u8) {}
FxSq Math3D_Vec3fMagnitudeSq(Vec3f* v) { return SQ(v->x)+SQ(v->y)+SQ(v->z); }
f32 Actor_WorldDistXYZToActor(Actor* a, Actor* b) { return Math_Vec3f_DistXYZ(&a->world.pos,&b->world.pos); }
DynaPolyActor* DynaPoly_GetActor(CollisionContext*, s32) { return NULL; }
u32 SurfaceType_CanHookshot(CollisionContext*, CollisionPoly*, s32) { return hookable; }
s32 func_8002F9EC(PlayState*, Actor*, CollisionPoly*, s32, Vec3f*) { return 0; }
s32 BgCheck_ProjectileLineTest(CollisionContext*, Vec3f*, Vec3f*, Vec3f*, CollisionPoly**, s32, s32, s32, s32, s32*) { return 0; }
s32 BgCheck_EntityLineTest1(CollisionContext*, Vec3f* a, Vec3f* b, Vec3f* out, CollisionPoly** poly,
                           s32, s32, s32, s32, s32* bg) {
    lastLineStart=*a; lastLineEnd=*b;
    if (!lineHit) return 0;
    *out=lineClip ? clipPoint : *b; *poly=&hitPoly; *bg=BGCHECK_SCENE; return 1;
}

static void reset(void) {
    play={}; player={}; hook={}; bomb={}; boom={};
    for (int i=0;i<8;++i) arrows[i]={};
    arrowCount=atCount=spawnFail=deferred=hookable=lineHit=spawnCalls=lineClip=0;
    gOotCorePlay=&play; play.actorCtx.actorLists[ACTORCAT_PLAYER].head=&player.actor;
    player.actor.update=idle; player.actor.world.pos={1000,100,2000};
    player.actor.focus.pos={1000,150,2000}; R_UPDATE_RATE=3;
    OotCore_ToolReset(); int hand[3]={1000,150,2000}; OotCore_ToolCommand(OOT_CORE_TOOL_HAND,hand);
}
static void step(void) {
    for (int cat=0;cat<ACTORCAT_MAX;++cat)
    for (Actor* a=play.actorCtx.actorLists[cat].head;a;a=a->next) {
        if (!a->update) continue;
        if (a->init) { if (!deferred) { a->init(a,&play);a->init=NULL; } continue; }
        a->prevPos=a->world.pos; a->update(a,&play);
    }
    OotCore_ToolStep(&play);
}
int main(void) {
    int io[6]={ITEM_BOW,1000,150,2000,0,0};
    const OotCoreToolView* views;
    reset(); CHECK(OotCore_ToolCommand(OOT_CORE_TOOL_USE,io)); step(); step();
    CHECK(arrows[0].timer==11 && arrows[0].actor.world.pos.z > 2224 && arrows[0].actor.world.pos.z <= 2225);
    CHECK(OotCore_ToolView(&views)==1 && views[0].previous_z==2000 && views[0].damage==1);
    CHECK(atCount>0 && arrows[0].collider.elem.atDmgInfo.dmgFlags==DMG_ARROW_NORMAL);
    /* Multiple shots can launch while an earlier arrow remains. */
    CHECK(OotCore_ToolCommand(OOT_CORE_TOOL_USE,io));
    for (int i=2;i<8;++i) CHECK(OotCore_ToolCommand(OOT_CORE_TOOL_USE,io));
    CHECK(!OotCore_ToolCommand(OOT_CORE_TOOL_USE,io)); CHECK(OotCore_ToolView(&views)==8);
    const int bowItems[]={ITEM_BOW,ITEM_ARROW_FIRE,ITEM_ARROW_ICE,ITEM_ARROW_LIGHT};
    const unsigned masks[]={DMG_ARROW_NORMAL,DMG_ARROW_FIRE,DMG_ARROW_ICE,DMG_ARROW_LIGHT};
    for (int i=0;i<4;++i) {
        reset();io[0]=bowItems[i];io[5]=8192;
        CHECK(OotCore_ToolCommand(OOT_CORE_TOOL_USE,io));step();step();
        CHECK(arrows[0].actor.world.pos.y>300 && arrows[0].actor.world.pos.z>2150);
        CHECK(OotCore_ToolView(&views)==1 && views[0].dmg==masks[i] && views[0].damage==1);
    }
    reset();io[0]=ITEM_BOW;io[5]=0;spawnFail=1;
    CHECK(!OotCore_ToolCommand(OOT_CORE_TOOL_USE,io) && !player.actor.child && !player.unk_A73);
    /* Source carry projection at the real 225-unit step. Both denominator
     * 225^2 and the farther offset's numerator exceed plain Fx range. */
    reset();Actor carried={};carried.update=idle;
    arrows[0].actor.world.pos={0,0,225};arrows[0].unk_210={0,0,0};arrows[0].hitActor=&carried;
    const int offsets[]={-25,125,250};
    for (int i=0;i<3;++i) {
        carried.world.pos={0,0,offsets[i]};EnArrow_CarryActor(&arrows[0],&play);
        f32 expected=offsets[i]>225 ? offsets[i]:225;
        CHECK(carried.world.pos.z>expected-FXL(0.1f) && carried.world.pos.z<=expected+FXL(0.1f));
    }
    arrows[0].actor.world.pos={159,0,159};carried.world.pos={-25,0,-25};
    EnArrow_CarryActor(&arrows[0],&play);
    CHECK(carried.world.pos.x>FXL(158.9f) && carried.world.pos.x<FXL(159.1f));
    CHECK(carried.world.pos.z>FXL(158.9f) && carried.world.pos.z<FXL(159.1f));
    arrows[0].actor.world.pos={0,0,225};carried.world.pos={0,0,125};
    lineHit=lineClip=1;clipPoint={0,0,150};EnArrow_CarryActor(&arrows[0],&play);
    CHECK(carried.world.pos.z==149 && lastLineEnd.z>FXL(224.9f) && lastLineEnd.z<FXL(225.1f));
    lineHit=lineClip=0;arrows[0].actor.world.pos={0,0,FXL(0.5f)};carried.world.pos={0,0,-25};
    EnArrow_CarryActor(&arrows[0],&play);CHECK(carried.world.pos.z==-25);
    reset(); deferred=1; CHECK(OotCore_ToolCommand(OOT_CORE_TOOL_USE,io));
    for (int i=0;i<8;++i) step(); deferred=0; step(); step(); step();
    CHECK(arrows[0].actor.update && arrows[0].actor.world.pos.z > 2149);
    reset(); io[0]=ITEM_SLINGSHOT; CHECK(OotCore_ToolCommand(OOT_CORE_TOOL_USE,io)); step();step();
    CHECK(arrows[0].actor.params==ARROW_SEED && arrows[0].actor.world.pos.z > 2079);
    CHECK(arrows[0].collider.elem.atDmgInfo.dmgFlags==DMG_SLINGSHOT);
    for (int item=ITEM_HOOKSHOT;item<=ITEM_LONGSHOT;++item) {
        reset(); io[0]=item; CHECK(OotCore_ToolCommand(OOT_CORE_TOOL_USE,io));step();step();
        CHECK(hook.actor.world.pos.z > 2019); CHECK(hook.timer==(item==ITEM_HOOKSHOT ? 12:25));
        CHECK(lastLineStart.z > 1970 && lastLineStart.z < 2010 && lastLineEnd.z > 2038);
        CHECK(OotCore_ToolView(&views)==1 && !views[0].held); CHECK(atCount>0);
        for (int i=0;i<40;++i) step();
        CHECK(!hook.actor.update && !player.heldActor && !player.actor.child && !player.actor.parent);
    }
    reset(); io[0]=ITEM_HOOKSHOT; CHECK(OotCore_ToolCommand(OOT_CORE_TOOL_USE,io));step();
    lineHit=hookable=1;step(); CHECK(player.actor.parent==&hook.actor);
    lineHit=0;step(); CHECK(player.actor.velocity.z>0);
    OotCore_ToolCommand(OOT_CORE_TOOL_CANCEL,io);
    CHECK(!player.actor.parent && !player.actor.child && !player.heldActor);
    /* Deleted actors are gone from the list before bridge post-update. */
    reset(); CHECK(OotCore_ToolCommand(OOT_CORE_TOOL_USE,io));
    play.actorCtx.actorLists[ACTORCAT_ITEMACTION].head=NULL;step();
    CHECK(!OotCore_ToolCommand(OOT_CORE_TOOL_STATE,io) && !player.heldActor);
    reset(); io[0]=ITEM_BOOMERANG; CHECK(OotCore_ToolCommand(OOT_CORE_TOOL_USE,io));
    step();step();CHECK(boom.actor.world.pos.z>2045);
    CHECK(OotCore_ToolView(&views)==1 && views[0].id==ACTOR_EN_BOOM && views[0].attack_id && views[0].damage==1);
    CHECK(OotCore_ToolCommand(OOT_CORE_TOOL_STATE,io)&OOT_CORE_TOOL_BOOMERANG_OUT);
    CHECK(!OotCore_ToolCommand(OOT_CORE_TOOL_USE,io));
    for (int i=0;i<90;++i) step();
    CHECK(!boom.actor.update && !(player.stateFlags1&PLAYER_STATE1_BOOMERANG_THROWN));
    reset();Actor explosives[3]={};
    for (int i=0;i<3;++i) {
        explosives[i].id=i==1 ? ACTOR_EN_BOM_CHU:ACTOR_EN_BOM;
        explosives[i].update=idle;explosives[i].next=i<2 ? &explosives[i+1]:NULL;
    }
    play.actorCtx.actorLists[ACTORCAT_EXPLOSIVE].head=explosives;
    io[0]=ITEM_BOMB;CHECK(!OotCore_ToolCommand(OOT_CORE_TOOL_USE,io));
    io[0]=ITEM_BOMBCHU;CHECK(!OotCore_ToolCommand(OOT_CORE_TOOL_USE,io));CHECK(spawnCalls==0);
    /* A carried body tracks the hand, but its real explosion stays where the
     * body last placed its sphere. The source carry lifetime lasts to timer0. */
    reset();io[0]=ITEM_BOMB;CHECK(OotCore_ToolCommand(OOT_CORE_TOOL_USE,io));
    OotCore_ToolStep(&play);
    CHECK(OotCore_ToolCommand(OOT_CORE_TOOL_STATE,io)&OOT_CORE_TOOL_HOLDING);
    CHECK(OotCore_ToolView(&views)==1 && views[0].held && views[0].y==162);
    bomb.actor.params=BOMB_EXPLOSION;bomb.timer=10;
    int movedHand[3]={1400,300,2400};OotCore_ToolCommand(OOT_CORE_TOOL_HAND,movedHand);
    for (int i=1;i<=4;++i) {
        EnBom_Explode(&bomb,&play);OotCore_ToolStep(&play);
        CHECK(bomb.explosionColliderElements[0].dim.worldSphere.radius==8*i);
        CHECK(bomb.actor.world.pos.z==2400 && bomb.actor.world.pos.y==312);
        CHECK(bomb.explosionColliderElements[0].dim.worldSphere.center.x==1000);
        CHECK(bomb.explosionColliderElements[0].dim.worldSphere.center.y==162);
        CHECK(bomb.explosionColliderElements[0].dim.worldSphere.center.z==2000);
        CHECK(OotCore_ToolView(&views)==1 && !views[0].held && views[0].damage==8 && views[0].dmg==DMG_EXPLOSIVE);
        CHECK(views[0].x==1000 && views[0].y==162 && views[0].z==2000);
        CHECK(views[0].previous_x==views[0].x && views[0].previous_y==views[0].y && views[0].previous_z==views[0].z);
    }
    bomb.timer=0;EnBom_Explode(&bomb,&play);OotCore_ToolStep(&play);
    CHECK(!(OotCore_ToolCommand(OOT_CORE_TOOL_STATE,io)&OOT_CORE_TOOL_HOLDING));
    CHECK(!player.heldActor && !player.actor.child && !(player.stateFlags1&PLAYER_STATE1_CARRYING_ACTOR));
    printf("tool actor fixture: arrows/seed, pitch/carry, capacity, deferred init, hook flight/return/pull/cancel, boomerang MISC/return, mixed explosive cap, held blast pass\n");
    return 0;
}
