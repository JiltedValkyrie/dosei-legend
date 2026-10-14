/* Execute the actual generated view service with source actor layouts. */
#include "oot_prelude.h"
#include "actor.h"
#include "play_state.h"
#include "save.h"
#include "oot_core_api.h"
#include "overlays/actors/ovl_En_Horse_Normal/z_en_horse_normal.h"
#include "overlays/actors/ovl_En_Hy/z_en_hy.h"
#include "overlays/actors/ovl_En_Zf/z_en_zf.h"
#include "overlays/actors/ovl_En_Cs/z_en_cs.h"
#include "overlays/actors/ovl_En_G_Switch/z_en_g_switch.h"
#include "overlays/actors/ovl_Demo_Effect/z_demo_effect.h"
#include "child_common_keys.h"
#include "gfx.h"

extern "C" int oot_pack_npc_view(PlayState*,Actor*,OotCoreNpcView*,unsigned,const SaveContext*);
extern "C" int printf(const char*,...);

/* The service only publishes these opaque keys; no geometry gets evaluated. */
Gfx gGoronDL_00BD80[1],gGoronDL_00C140[1],gHeishiKingGuardDL[1];
Gfx gGoldenGoddessAuraDL[1],gGoldenGoddessBodyDL[1];
Gfx object_efc_star_field_DL_000DE0[1],object_kingdodongo_DL_01D950[1];
Gfx gEnNySpikeDL[1],gEnNyRockBodyDL[1],gBusinessScrubDekuNutDL[1],gDekuNutsDekuNutDL[1];
Gfx gSkulltulaTokenDL[1],gSkullKidNeedleDL[1];

Gfx gGiArrowMediumDL[1],gGiBiggoronSwordDL[1],gGiBlueFireChamberstickDL[1],gGiBombDL[1],gGiBombchuDL[1],gGiBugsContainerDL[1],gGiBunnyHoodDL[1],gGiDekuShieldDL[1],gGiEggMaterialDL[1],gGiFairyContainerBaseCapDL[1],gGiFishDL[1],gGiGerudoMaskDL[1],gGiGhostContainerLidDL[1],gGiGoronCollarColorDL[1],gGiGoronMaskDL[1],gGiHylianShieldDL[1],gGiKeatonMaskDL[1],gGiMaskOfTruthDL[1],gGiMilkBottleContentsDL[1],gGiNutDL[1],gGiRecoveryHeartDL[1],gGiRedPotColorDL[1],gGiSeedDL[1],gGiSkullMaskDL[1],gGiSoldOutDL[1],gGiSpookyMaskDL[1],gGiStickDL[1],gGiZoraMaskDL[1];

f32 Math_SinS(s16 angle) {
    return angle==0x4000 ? 1 : angle==(s16)0xC000 ? -1 : 0;
}
f32 Math_CosS(s16 angle) { return Math_SinS((s16)(angle+0x4000)); }

static int fail;
#define CHECK(c) do { if (!(c)) {printf("view check failed line %d: %s\n",__LINE__,#c);++fail;} } while(0)
static void draw(Actor*,PlayState*) {}
static void actor(Actor* a,int id) {
    a->id=id;a->draw=draw;a->scale.x=a->scale.y=a->scale.z=FXL(0.01f);
    a->world.pos.x=10;a->world.pos.y=20;a->world.pos.z=30;a->shape.yOffset=100;
}

int main() {
    static PlayState play;
    static SaveContext save;
    OotCoreNpcView rows[3]={};
    rows[2].id=-123;
    EnHorseNormal horse={};actor(&horse.actor,ACTOR_EN_HORSE_NORMAL);
    horse.spriteCloneEnabled=1;horse.spriteClonePos={100,200,300};horse.spriteCloneYaw=0x1000;
    CHECK(oot_pack_npc_view(&play,&horse.actor,rows,0,&save)==0);
    CHECK(oot_pack_npc_view(&play,&horse.actor,rows,1,&save)==1);
    CHECK(oot_pack_npc_view(&play,&horse.actor,rows,2,&save)==2);
    CHECK(rows[0].x==10 && rows[0].y==20 && rows[1].x==100 && rows[1].y==200 && rows[1].yaw==0x1000);
    CHECK(rows[0].scale_x>=255 && rows[0].scale_x<=256 && rows[2].id==-123);

    EnHy hy={};actor(&hy.actor,ACTOR_EN_HY);hy.actor.params=3;hy.modelOffset.z=1000;
    CHECK(oot_pack_npc_view(&play,&hy.actor,rows,2,&save)==1);
    CHECK((rows[0].anim>>20)==sChildHylianVariants[3] && rows[0].z>=39 && rows[0].z<=40);
    EnZf zf={};actor(&zf.actor,ACTOR_EN_ZF);zf.alpha=98;zf.actor.colorFilterTimer=10;zf.actor.colorFilterParams=0x4000;
    CHECK(oot_pack_npc_view(&play,&zf.actor,rows,2,&save)==1 && rows[0].alpha==98 && rows[0].tint==8);
    EnCs boy={};actor(&boy.actor,ACTOR_EN_CS);
    CHECK(oot_pack_npc_view(&play,&boy.actor,rows,2,&save)==1 && !(rows[0].anim&(1u<<20)));
    save.save.info.itemGetInf[ITEMGETINF_3A>>4]|=1u<<(ITEMGETINF_3A&15);
    CHECK(oot_pack_npc_view(&play,&boy.actor,rows,2,&save)==1 && (rows[0].anim&(1u<<20)));

    EnGSwitch target={};actor(&target.actor,ACTOR_EN_G_SWITCH);target.type=ENGSWITCH_TARGET_RUPEE;target.broken=1;
    CHECK(oot_pack_npc_view(&play,&target.actor,rows,2,&save)==-1);
    target.broken=0;target.colorIdx=2;
    CHECK(oot_pack_npc_view(&play,&target.actor,rows,2,&save)==1 && rows[0].object==0xfff);
    DemoEffect god={};actor(&god.actor,ACTOR_DEMO_EFFECT);god.actor.params=DEMO_EFFECT_GOD_LGT_DIN;
    CHECK(oot_pack_npc_view(&play,&god.actor,rows,1,&save)==1);
    CHECK(oot_pack_npc_view(&play,&god.actor,rows,2,&save)==2 && rows[2].id==-123);
    CHECK(rows[0].skeleton==(u32)(uintptr_t)gGoldenGoddessAuraDL && rows[1].skeleton==(u32)(uintptr_t)gGoldenGoddessBodyDL);
    Actor unknown={};actor(&unknown,ACTOR_EN_BOX);
    CHECK(oot_pack_npc_view(&play,&unknown,rows,2,&save)==0);
    printf("NPC view source fixture: %d failures\n",fail);
    return fail!=0;
}
