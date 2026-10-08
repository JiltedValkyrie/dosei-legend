/* Original water controller actions with deterministic engine I/O. */
#include "oot_prelude.h"
#include "play_state.h"
#include "z_bg_mizu_water.h"
#include "one_point_cutscene.h"
#include "rumble.h"
#include "z_lib.h"
extern "C" int printf(const char*, ...);
extern "C" void abort(void);
#define CHECK(x) do { if (!(x)) { printf("line %d: %s\n", __LINE__, #x); abort(); } } while (0)
static PlayState play;
static CollisionHeader collision;
static WaterBox boxes[25];
static u32 switches;
static int cutscenes, closed;
u32 BgMizuWater_GetWaterLevelActionIndex(s16, PlayState*);
void BgMizuWater_SetWaterBoxesHeight(WaterBox*, s16);
void BgMizuWater_WaitForAction(BgMizuWater*, PlayState*);
void BgMizuWater_ChangeWaterLevel(BgMizuWater*, PlayState*);
s32 Flags_GetSwitch(PlayState*, s32 flag) { return (switches >> flag) & 1; }
void Flags_UnsetSwitch(PlayState*, s32 flag) { switches &= ~(1u << flag); }
s16 OnePointCutscene_Init(PlayState*, s16 id, s16 timer, Actor*, s16 camera) {
    CHECK(id == 3120 && timer <= -101 && timer >= -103 && camera == CAM_ID_MAIN);
    ++cutscenes; return CAM_ID_NONE;
}
void Message_CloseTextbox(PlayState*) { ++closed; }
void Rumble_Request(FxSq, u8, u8, u8) {}
void Actor_PlaySfx_FlaggedCentered2(Actor*, u16) {}
s32 Math_StepToF(f32* value, f32 target, f32 step) {
    if (*value < target) { *value += step; if (*value > target) *value = target; }
    else { *value -= step; if (*value < target) *value = target; }
    return *value == target;
}
static void finish(BgMizuWater* water) {
    int ticks=0;
    while (water->actionFunc == BgMizuWater_ChangeWaterLevel) {
        CHECK(++ticks < 1000);
        water->actionFunc(water, &play);
    }
    CHECK(water->actor.world.pos.y == water->targetY);
}
int main(void) {
    collision.waterBoxes=boxes; collision.numWaterBoxes=25;
    play.colCtx.colHeader=&collision;
    switches=(1u<<28)|(1u<<29)|(1u<<30);
    CHECK(BgMizuWater_GetWaterLevelActionIndex(-1,&play)==3);
    CHECK(BgMizuWater_GetWaterLevelActionIndex(28,&play)==2);
    switches=1u<<30;
    CHECK(BgMizuWater_GetWaterLevelActionIndex(30,&play)==0);
    for (int i=0;i<25;++i) boxes[i].ySurface=1234;
    BgMizuWater water={}; water.baseY=WATER_TEMPLE_WATER_F3_Y;
    water.actor.world.pos.y=WATER_TEMPLE_WATER_F1_Y;
    water.actor.params=28; switches=(1u<<28)|(1u<<29);
    BgMizuWater_WaitForAction(&water,&play);
    CHECK(water.targetY==WATER_TEMPLE_WATER_F2_Y && switches==(1u<<29) && cutscenes==1);
    BgMizuWater_ChangeWaterLevel(&water,&play);
    CHECK(water.actor.world.pos.y == -10 && boxes[22].ySurface == -10);
    finish(&water);
    CHECK(closed==1);
    const u32 changed=(1u<<2)|(1u<<3)|(1u<<5)|(1u<<7)|(1u<<12)|(1u<<20)|(1u<<21)|(1u<<22);
    for (int i=0;i<25;++i) CHECK(boxes[i].ySurface==((changed>>i)&1 ? 445 : 1234));
    switches|=1u<<30; BgMizuWater_WaitForAction(&water,&play);
    BgMizuWater_ChangeWaterLevel(&water,&play);
    CHECK(water.actor.world.pos.y==450);
    switches|=1u<<28; /* Source accepts a new level request while moving. */
    finish(&water);
    CHECK(water.actor.world.pos.y==WATER_TEMPLE_WATER_F1_Y && switches==(1u<<28) && closed==2);
    const int indices[]={6,8,16}, rises[]={85,110,160};
    for (int i=0;i<3;++i) {
        BgMizuWater local={}; local.type=i+2; local.switchFlag=7;
        local.baseY=100; local.actor.world.pos.y=100;
        switches=1u<<7; BgMizuWater_WaitForAction(&local,&play);
        BgMizuWater_ChangeWaterLevel(&local,&play);
        CHECK(local.actor.world.pos.y==101 && boxes[indices[i]].ySurface==101);
        finish(&local); CHECK(boxes[indices[i]].ySurface==100+rises[i]);
        switches=0; BgMizuWater_WaitForAction(&local,&play); finish(&local);
        CHECK(boxes[indices[i]].ySurface==100 && closed==2);
    }
    printf("Water source actions pass: levels, switch replacement, all 25 boxes, local rise/fall.\n");
    return 0;
}
