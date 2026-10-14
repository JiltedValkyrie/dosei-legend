/* Execute source bomb ingestion, heart pickup and first/repeat child warp. */
#include "oot_prelude.h"
#include "play_state.h"
#include "player.h"
#include "save.h"
#include "z_lib.h"
#include "interface.h"
#include "overlays/actors/ovl_Boss_Dodongo/z_boss_dodongo.h"
#include "overlays/actors/ovl_Item_B_Heart/z_item_b_heart.h"
#include "overlays/actors/ovl_Door_Warp1/z_door_warp1.h"
extern "C" int printf(const char*, ...);
extern "C" void abort(void);
#define CHECK(x) do { if (!(x)) { printf("line %d: %s\n", __LINE__, #x); abort(); } } while (0)
s32 BossDodongo_AteExplosive(BossDodongo*, PlayState*);
s32 DoorWarp1_PlayerInRange(DoorWarp1*, PlayState*);
void DoorWarp1_ChildWarpOut(DoorWarp1*, PlayState*);
void ItemBHeart_Update(Actor*, PlayState*);
SaveContext gSaveContext;
static PlayState play;
static Player player;
static int killed, offered, collected, ruby, beaten;
static void alive(Actor*, PlayState*) {}
void Actor_Kill(Actor* actor) { actor->update = NULL; ++killed; }
u32 Actor_HasParent(Actor* actor, PlayState*) { return actor->parent != NULL; }
s32 Actor_OfferGetItem(Actor*, PlayState*, s32 item, f32 xz, f32 y) {
    CHECK(item == GI_HEART_CONTAINER_2 && xz == 30 && y == 40); ++offered; return 1;
}
void Flags_SetCollectible(PlayState*, s32 flag) { CHECK(flag == 0x1F); ++collected; }
void Actor_UpdateBgCheckInfo(PlayState*, Actor*, f32, f32, f32, s32) {}
void func_80B85264(ItemBHeart*, PlayState*) {}
s32 Flags_GetEventChkInf(s32 flag) { CHECK(flag == EVENTCHKINF_25); return beaten; }
void Flags_SetEventChkInf(s32 flag) { CHECK(flag == EVENTCHKINF_25); beaten = 1; }
u8 Item_Give(PlayState*, u8 item) { CHECK(item == ITEM_GORON_RUBY); ++ruby; return 0; }
f32 Math_SmoothStepToF(f32* value, f32 target, f32, f32, f32) { *value = target; return 0; }
s32 Math_StepToF(f32* value, f32 target, f32) { *value = target; return 1; }
void Lights_PointNoGlowSetInfo(LightInfo*, s16, s16, s16, u8, u8, u8, s16) {}

int main() {
    play.actorCtx.actorLists[ACTORCAT_PLAYER].head = &player.actor;
    BossDodongo boss = {};
    Actor bomb = {};
    bomb.update = alive; bomb.world.pos = {39, 39, 39};
    play.actorCtx.actorLists[ACTORCAT_EXPLOSIVE].head = &bomb;
    CHECK(BossDodongo_AteExplosive(&boss, &play));
    CHECK(killed == 1 && bomb.update == NULL);
    bomb.update = alive; bomb.world.pos.x = 40;
    CHECK(!BossDodongo_AteExplosive(&boss, &play));

    ItemBHeart heart = {};
    heart.actor.update = alive;
    ItemBHeart_Update(&heart.actor, &play);
    CHECK(offered == 1 && collected == 0 && heart.actor.update);
    heart.actor.parent = &player.actor;
    ItemBHeart_Update(&heart.actor, &play);
    CHECK(offered == 1 && collected == 1 && !heart.actor.update);

    DoorWarp1 warp = {};
    warp.actor.xzDistToPlayer = 59;
    CHECK(DoorWarp1_PlayerInRange(&warp, &play));
    warp.actor.xzDistToPlayer = 60;
    CHECK(!DoorWarp1_PlayerInRange(&warp, &play));
    warp.actor.xzDistToPlayer = 0; player.actor.world.pos.y = 20;
    CHECK(!DoorWarp1_PlayerInRange(&warp, &play));
    player.actor.world.pos.y = 0;
    play.sceneId = SCENE_DODONGOS_CAVERN_BOSS;
    gSaveContext.nextCutsceneIndex = NEXT_CS_INDEX_NONE;
    warp.warpTimer = 99;
    DoorWarp1_ChildWarpOut(&warp, &play);
    CHECK(ruby == 0 && !beaten);
    DoorWarp1_ChildWarpOut(&warp, &play);
    CHECK(ruby == 1 && beaten);
    CHECK(play.nextEntranceIndex == ENTR_DEATH_MOUNTAIN_TRAIL_0);
    CHECK(gSaveContext.nextCutsceneIndex == CS_INDEX_1);
    CHECK(play.transitionTrigger == TRANS_TRIGGER_START);
    CHECK(play.transitionType == TRANS_TYPE_FADE_WHITE_SLOW);
    // Pending cutscene blocks a repeated reward before the scene transfers.
    DoorWarp1_ChildWarpOut(&warp, &play);
    CHECK(ruby == 1);
    gSaveContext.nextCutsceneIndex = NEXT_CS_INDEX_NONE;
    DoorWarp1_ChildWarpOut(&warp, &play);
    CHECK(ruby == 1 && play.nextEntranceIndex == ENTR_DEATH_MOUNTAIN_TRAIL_5);
    CHECK(gSaveContext.nextCutsceneIndex == CS_INDEX_NONE);
    printf("King Dodongo source: mouth gate, heart latch, child warp gates, first/repeat Ruby exit pass\n");
    return 0;
}
