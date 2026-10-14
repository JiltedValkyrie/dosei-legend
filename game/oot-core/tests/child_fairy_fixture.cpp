/* Execute the original source cue-driven magic/spell reward and warp latch. */
#include "oot_prelude.h"
#include "play_state.h"
#include "player.h"
#include "save.h"
#include "z_lib.h"
#include "interface.h"
#include "oot_core_api.h"
#include "sfx.h"
#include "oot_core_reward_sync.h"
#include "overlays/actors/ovl_Bg_Dy_Yoseizo/z_bg_dy_yoseizo.h"
#include "overlays/actors/ovl_En_Ex_Item/z_en_ex_item.h"
#include "assets/objects/object_dy_obj/object_dy_obj.h"
extern "C" int printf(const char*,...);
extern "C" void abort(void);
#define CHECK(x) do {if(!(x)){printf("fairy line%d: %s\n",__LINE__,#x);abort();}}while(0)
SaveContext gSaveContext;
AnimationHeader gGreatFairyAfterUpgradeAnim, gGreatFairyAfterSpellAnim;
static PlayState play;
static Player player;
static EnExItem item;
static int hud,magic,given,spawned,warps;
static bool spawnFails;
static int capacity,defense,healed,chimes;
static int CommitMagic(short amount,short type){
    if(type==OOT_CORE_MAGIC_ACQUIRE)capacity=amount;
    else if(type==OOT_CORE_DEFENSE_ACQUIRE)defense=amount;
    else CHECK(false);
    return 1;
}
static int CommitHealth(short amount){healed+=amount;return 1;}
static void CommitSfx(unsigned short id,int,int,int){CHECK(id==NA_SE_SY_HP_RECOVER);++chimes;}
void BgDyYoseizo_Reward_GiveReward(BgDyYoseizo*,PlayState*);
void BgDyYoseizo_SetupDisappear(BgDyYoseizo*,PlayState*){}
void BgDyYoseizo_UpdatePosY(BgDyYoseizo*,PlayState*){}
void BgDyYoseizo_SpawnEffectsType(BgDyYoseizo*,PlayState*,s16){}
s32 SkelAnime_Update(SkelAnime*){return 0;}
s16 Animation_GetLastFrame(void*){return 50;}
void Animation_Change(SkelAnime*,AnimationHeader*,f32,f32,f32,u8,f32){}
void Magic_Fill(PlayState*){++magic;}
void Interface_ChangeHudVisibilityMode(u16 mode){CHECK(mode==HUD_VISIBILITY_HEARTS_MAGIC);++hud;}
u8 Item_Give(PlayState*,u8 id){given=id;return id;}
void Actor_Kill(Actor* a){a->update=NULL;}
Actor* Actor_Spawn(ActorContext*,PlayState*,s16 id,f32,f32,f32,s16,s16,s16,s16){if(id==ACTOR_DOOR_WARP1)++warps;return NULL;}
Actor* Actor_SpawnAsChild(ActorContext*,Actor*,PlayState*,s16 id,f32,f32,f32,s16,s16,s16,s16){CHECK(id==ACTOR_EN_EX_ITEM);++spawned;return spawnFails?NULL:&item.actor;}
int main(){
    play.actorCtx.actorLists[ACTORCAT_PLAYER].head=&player.actor;
    CsCmdActorCue cue={}; play.csCtx.actorCues[0]=&cue;
    play.sceneId=SCENE_GREAT_FAIRYS_FOUNTAIN_MAGIC;
    BgDyYoseizo fairy={}; fairy.curAnimLastFrame=50;
    cue.id=9;BgDyYoseizo_Reward_GiveReward(&fairy,&play);
    CHECK(!gSaveContext.save.info.playerData.isMagicAcquired);
    cue.id=10;BgDyYoseizo_Reward_GiveReward(&fairy,&play);
    CHECK(gSaveContext.save.info.playerData.isMagicAcquired && gSaveContext.magicFillTarget==0x30);
    CHECK(gSaveContext.healthAccumulator==0x140 && fairy.energyRefilled && hud==1);
    gSaveContext.healthAccumulator=0;BgDyYoseizo_Reward_GiveReward(&fairy,&play);
    CHECK(gSaveContext.healthAccumulator==0); // source one-time refill latch
    cue.id=19;BgDyYoseizo_Reward_GiveReward(&fairy,&play);BgDyYoseizo_Reward_GiveReward(&fairy,&play);
    CHECK(warps==1 && fairy.unk304);
    play.sceneId=SCENE_GREAT_FAIRYS_FOUNTAIN_SPELLS;
    fairy={};fairy.curAnimLastFrame=50;
    cue.id=15;spawnFails=true;BgDyYoseizo_Reward_GiveReward(&fairy,&play);
    CHECK(!fairy.hasSpawnedItem && given==0);
    spawnFails=false;BgDyYoseizo_Reward_GiveReward(&fairy,&play);
    CHECK(fairy.hasSpawnedItem && given==ITEM_DINS_FIRE && spawned==2);
    CHECK(gSaveContext.save.info.itemGetInf[ITEMGETINF_INDEX_SPELLS]&ITEMGETINF_MASK(ITEMGETINF_DINS_FIRE));
    BgDyYoseizo_Reward_GiveReward(&fairy,&play);CHECK(spawned==2 && fairy.item->scale==FXL(.3f));
    cue.id=17;BgDyYoseizo_Reward_GiveReward(&fairy,&play);CHECK(fairy.item==NULL);
    OotCoreSave mirror={};OotCoreHost host={};
    host.magic_request=CommitMagic;host.health_change=CommitHealth;host.play_sfx=CommitSfx;
    gSaveContext.save.info.playerData.health=12;gSaveContext.save.info.playerData.healthCapacity=48;
    OotCore_CommitRewards(&mirror,&host);
    CHECK(capacity==1 && healed==4 && chimes==1 && gSaveContext.healthAccumulator==0x13c);
    mirror.magic_level=capacity;capacity=0;
    OotCore_CommitRewards(&mirror,&host);CHECK(capacity==0 && healed==8);
    gSaveContext.save.info.playerData.isDoubleMagicAcquired=true;
    gSaveContext.save.info.playerData.isDoubleDefenseAcquired=true;
    OotCore_CommitRewards(&mirror,&host);CHECK(capacity==2 && defense==1);
    gSaveContext.save.info.playerData.health=46;
    OotCore_CommitRewards(&mirror,&host);
    CHECK(gSaveContext.save.info.playerData.health==48 && gSaveContext.healthAccumulator==0);
    printf("Source fairy magic/spell reward, failed allocation and repeat latches pass\n");
}
