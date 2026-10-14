/* Actual source reward, bomb and shop-child actions with deterministic I/O. */
#include "oot_prelude.h"
#include "play_state.h"
#include "z_lib.h"
#include "z_en_item00.h"
#include "overlays/actors/ovl_En_Dodojr/z_en_dodojr.h"
#include "overlays/actors/ovl_En_Dodongo/z_en_dodongo.h"
#include "overlays/actors/ovl_En_Shopnuts/z_en_shopnuts.h"
extern "C" int printf(const char*, ...);
extern "C" void abort(void);
#define CHECK(x) do { if (!(x)) { printf("line %d: %s\n", __LINE__, #x); abort(); } } while (0)
void EnDodojr_DropItem(EnDodojr*, PlayState*);
s32 EnDodojr_CheckNearbyBombs(EnDodojr*, PlayState*);
s32 EnDodongo_AteBomb(EnDodongo*, PlayState*);
void EnShopnuts_SpawnSalesman(EnShopnuts*, PlayState*);
static PlayState play;
static int drops, kills, spawned, finished;
static s16 merchantType;
static void alive(Actor*, PlayState*) {}
void Actor_Kill(Actor* actor) { actor->update = NULL; ++kills; }
void Item_DropCollectibleRandom(PlayState*, Actor*, Vec3f*, s16 params) {
    CHECK(params == COLLECTIBLE_DROP_RANDOM_PARAMS(COLLECTIBLE_DROP_TABLE_4, false));
    ++drops;
}
s32 SkelAnime_Update(SkelAnime*) { return finished; }
void Math_ApproachS(s16*, s16, s16, s16) {}
Actor* Actor_Spawn(ActorContext*, PlayState*, s16 id, f32, f32, f32, s16, s16, s16, s16 params) {
    CHECK(id == ACTOR_EN_DNS); ++spawned; merchantType = params; return NULL;
}

int main() {
    EnDodojr baby = {};
    baby.actor.update = alive; baby.timer = 8;
    for (int i = 0; i < 7; ++i) EnDodojr_DropItem(&baby, &play);
    CHECK(drops == 0 && kills == 0 && baby.timer == 1);
    EnDodojr_DropItem(&baby, &play);
    CHECK(drops == 1 && kills == 1 && baby.actor.update == NULL);
    // The scheduler cannot update a killed source actor, avoiding duplicate loot.
    if (baby.actor.update) EnDodojr_DropItem(&baby, &play);
    CHECK(drops == 1);

    Actor bomb = {};
    bomb.id = ACTOR_EN_BOM; bomb.update = alive;
    bomb.world.pos = {10, 5, 10};
    play.actorCtx.actorLists[ACTORCAT_EXPLOSIVE].head = &bomb;
    CHECK(EnDodojr_CheckNearbyBombs(&baby, &play) && baby.bomb == &bomb);
    bomb.params = 1; CHECK(!EnDodojr_CheckNearbyBombs(&baby, &play));
    bomb.params = 0; bomb.parent = &baby.actor; CHECK(!EnDodojr_CheckNearbyBombs(&baby, &play));
    bomb.parent = NULL; bomb.update = NULL; CHECK(!EnDodojr_CheckNearbyBombs(&baby, &play));
    bomb.update = alive; bomb.id = ACTOR_EN_BOMBF; CHECK(!EnDodojr_CheckNearbyBombs(&baby, &play));

    EnDodongo adult = {};
    adult.mouthPos = {100, 200, 300};
    bomb.id = ACTOR_EN_BOM; bomb.world.pos = {119, 209, 319};
    CHECK(EnDodongo_AteBomb(&adult, &play));
    CHECK(adult.actor.child == &bomb && bomb.parent == &adult.actor);
    CHECK(!EnDodongo_AteBomb(&adult, &play));
    bomb.parent = NULL; bomb.world.pos.y = 210;
    CHECK(!EnDodongo_AteBomb(&adult, &play));
    bomb.world.pos.y = 209; bomb.params = 1;
    CHECK(!EnDodongo_AteBomb(&adult, &play));
    bomb.params = 0; bomb.id = ACTOR_EN_BOMBF;
    CHECK(EnDodongo_AteBomb(&adult, &play) && adult.actor.parent == &bomb);

    EnShopnuts scrub = {};
    scrub.actor.params = 3; scrub.actor.update = alive;
    EnShopnuts_SpawnSalesman(&scrub, &play);
    CHECK(spawned == 0 && scrub.actor.update != NULL);
    finished = 1; EnShopnuts_SpawnSalesman(&scrub, &play);
    CHECK(spawned == 1 && merchantType == 3 && scrub.actor.update == NULL);
    printf("Dodongo source actions: delayed source table drop, bomb gates, source shop-child handoff pass\n");
}
