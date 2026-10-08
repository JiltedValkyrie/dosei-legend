/* Actual source actions, deterministic engine I/O. No draw or emulator needed. */
#include "oot_prelude.h"
#include "ultra64.h"
#include "actor.h"
#include "player.h"
#include "play_state.h"
#include "save.h"
#include "bgcheck.h"
#include "z_lib.h"
#include "z_math.h"
#include "item.h"
#include "z_en_item00.h"
#include "overlays/actors/ovl_En_Encount1/z_en_encount1.h"
#include "overlays/actors/ovl_En_Peehat/z_en_peehat.h"
#include "overlays/actors/ovl_En_Skb/z_en_skb.h"
extern "C" int printf(const char*, ...);
extern "C" void abort(void);
#define CHECK(x) do { if (!(x)) { printf("line %d: %s\n", __LINE__, #x); abort(); } } while (0)

SaveContext gSaveContext;
static PlayState play;
static Player player;
static Actor child;
static int spawned, mask, rise, disturbed, randomDrops, blueDrops, redDrops;
static int floorValid = 1;
static s16 spawnParams;
void EnEncount1_SpawnStalchildOrWolfos(EnEncount1*, PlayState*);
void EnPeehat_Ground_StateGround(EnPeehat*, PlayState*);
void EnSkb_Death(EnSkb*, PlayState*);
void FieldSprite_BreakStart(BodyBreak*, s32, PlayState*);
s32 FieldSprite_BreakStep(Actor*, BodyBreak*, PlayState*, s16);
void EnPeehat_Ground_SetStateRise(EnPeehat*) { ++rise; }
void EnPeehat_HitWhenGrounded(EnPeehat*, PlayState*) { ++disturbed; }
u8 Player_GetMask(PlayState*) { return mask; }
f32 Rand_CenteredFloat(f32) { return 0; }
f32 Math_SinS(s16) { return 0; }
f32 Math_CosS(s16) { return 1; }
f32 Math_SmoothStepToF(f32* value, f32 target, f32, f32, f32) { *value=target; return 0; }
f32 BgCheck_EntityRaycastDown4(CollisionContext*, CollisionPoly**, s32* bg, Actor*, Vec3f*) {
    *bg = BGCHECK_SCENE; return floorValid ? f32(0) : BGCHECK_Y_MIN;
}
Actor* Actor_SpawnAsChild(ActorContext*, Actor*, PlayState*, s16 id, f32, f32, f32,
                         s16, s16, s16, s16 params) {
    CHECK(id == ACTOR_EN_SKB); ++spawned; spawnParams=params; return &child;
}
void Actor_Kill(Actor* a) { a->update=NULL; }
void Item_DropCollectibleRandom(PlayState*, Actor*, Vec3f*, s16 params) {
    CHECK(params==COLLECTIBLE_DROP_RANDOM_PARAMS(COLLECTIBLE_DROP_TABLE_1, false)); ++randomDrops;
}
EnItem00* Item_DropCollectible(PlayState*, Vec3f*, s16 params) {
    if (params==ITEM00_RUPEE_BLUE) ++blueDrops;
    else { CHECK(params==ITEM00_RUPEE_RED); ++redDrops; }
    return NULL;
}
static void alive(Actor*, PlayState*) {}

static EnEncount1 spawner(void) {
    EnEncount1 a={}; a.maxCurSpawns=2; a.maxTotalSpawns=10000; a.spawnType=SPAWNER_STALCHILDREN;
    return a;
}

int main(void) {
    play.sceneId=SCENE_HYRULE_FIELD;
    play.actorCtx.actorLists[ACTORCAT_PLAYER].head=&player.actor;
    player.actor.floorBgId=BGCHECK_SCENE;
    player.actor.bgCheckFlags=BGCHECKFLAG_GROUND;
    player.actor.depthInWater=BGCHECK_Y_MIN;
    player.floorSfxOffset=SURFACE_SFX_OFFSET_GRASS;
    EnEncount1 a=spawner();
    gSaveContext.save.nightFlag=0;
    EnEncount1_SpawnStalchildOrWolfos(&a,&play); CHECK(spawned==0);
    gSaveContext.save.nightFlag=1;
    mask=PLAYER_MASK_BUNNY;
    EnEncount1_SpawnStalchildOrWolfos(&a,&play); CHECK(spawned==0);
    mask=0;
    player.floorSfxOffset=SURFACE_SFX_OFFSET_DIRT;
    EnEncount1_SpawnStalchildOrWolfos(&a,&play); CHECK(spawned==0 && a.fieldSpawnTimer==60);
    player.floorSfxOffset=SURFACE_SFX_OFFSET_GRASS;
    player.actor.bgCheckFlags=0; a=spawner();
    EnEncount1_SpawnStalchildOrWolfos(&a,&play); CHECK(spawned==0);
    player.actor.bgCheckFlags=BGCHECKFLAG_GROUND;
    player.actor.floorBgId=0; a=spawner();
    EnEncount1_SpawnStalchildOrWolfos(&a,&play); CHECK(spawned==0);
    player.actor.floorBgId=BGCHECK_SCENE;
    floorValid=0; a=spawner();
    EnEncount1_SpawnStalchildOrWolfos(&a,&play); CHECK(spawned==0);
    floorValid=1; player.actor.depthInWater=-10; player.actor.world.pos.y=0; a=spawner();
    EnEncount1_SpawnStalchildOrWolfos(&a,&play); CHECK(spawned==0);
    player.actor.depthInWater=BGCHECK_Y_MIN; a=spawner();
    EnEncount1_SpawnStalchildOrWolfos(&a,&play); CHECK(spawned==2 && a.curNumSpawn==2);
    EnEncount1_SpawnStalchildOrWolfos(&a,&play); CHECK(spawned==2);
    a=spawner(); a.killCount=10; a.maxCurSpawns=1;
    EnEncount1_SpawnStalchildOrWolfos(&a,&play); CHECK(spawnParams==5);

    EnPeehat ph={}; ph.xzDistToRise=500; ph.actor.xzDistToPlayer=20;
    EnPeehat_Ground_StateGround(&ph,&play); CHECK(rise==0 && disturbed==0);
    ph.colliderCylinder.base.acFlags=AC_HIT;
    EnPeehat_Ground_StateGround(&ph,&play); CHECK(rise==0 && disturbed==1);
    gSaveContext.save.nightFlag=0;
    EnPeehat_Ground_StateGround(&ph,&play); CHECK(rise==1);

    EnSkb skb={}; skb.actor.update=alive; skb.actor.scale.x=FXL(0.01f);
    FieldSprite_BreakStart(&skb.bodyBreak,18,&play);
    CHECK(skb.bodyBreak.matrices==NULL && skb.bodyBreak.dLists==NULL);
    EnSkb_Death(&skb,&play); CHECK(randomDrops==0 && skb.actor.update!=NULL);
    EnSkb_Death(&skb,&play); CHECK(randomDrops==1 && skb.actor.update==NULL && (skb.breakFlags&8));
    skb.actor.scale.x=FXL(0.015f); FieldSprite_BreakStart(&skb.bodyBreak,18,&play);
    EnSkb_Death(&skb,&play); EnSkb_Death(&skb,&play); CHECK(blueDrops==1);
    skb.actor.scale.x=FXL(0.02f); FieldSprite_BreakStart(&skb.bodyBreak,18,&play);
    EnSkb_Death(&skb,&play); EnSkb_Death(&skb,&play); CHECK(redDrops==3);
    printf("PASS Field source: day/night, mask, terrain/water, spawn cap, giant, Peahat disturbance, death/drop gates\n");
}
