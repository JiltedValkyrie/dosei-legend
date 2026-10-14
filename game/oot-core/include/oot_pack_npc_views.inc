/* Scene-owned read-only sprite snapshots. Generated filtering removes absent actors.
 * Actor/play/save and output memory stay owned by the resident core.
 */
#include "oot_prelude.h"
#include "ultra64.h"
#include "actor.h"
#include "array_count.h"
#include "message.h"
#include "message_data_fmt.h"
#include "play_state.h"
#include "player.h"
#include "z_lib.h"
#include "save.h"
#include "effect.h"
#include "overlays/actors/ovl_En_Ko/z_en_ko.h"
#include "overlays/actors/ovl_En_Md/z_en_md.h"
#include "overlays/actors/ovl_En_Kanban/z_en_kanban.h"
#include "oot_sign_visual.h"
#include "oot_core_api.h"
#include "overlays/actors/ovl_En_In/z_en_in.h"
#include "overlays/actors/ovl_En_Ma1/z_en_ma1.h"
#include "overlays/actors/ovl_En_Ma2/z_en_ma2.h"
#include "overlays/actors/ovl_En_Ta/z_en_ta.h"
#include "overlays/actors/ovl_En_Niw/z_en_niw.h"
#include "overlays/actors/ovl_En_Cow/z_en_cow.h"
#include "overlays/actors/ovl_En_Horse_Link_Child/z_en_horse_link_child.h"
#include "overlays/actors/ovl_En_Horse_Normal/z_en_horse_normal.h"
#include "overlays/actors/ovl_En_Skb/z_en_skb.h"
#include "overlays/actors/ovl_En_Peehat/z_en_peehat.h"
#include "overlays/actors/ovl_En_Po_Field/z_en_po_field.h"
#include "overlays/actors/ovl_En_Sb/z_en_sb.h"
#include "overlays/actors/ovl_En_Weiyer/z_en_weiyer.h"
#include "overlays/actors/ovl_En_Tite/z_en_tite.h"
#include "overlays/actors/ovl_En_Firefly/z_en_firefly.h"
#include "overlays/actors/ovl_En_Ny/z_en_ny.h"
#include "assets/objects/object_ny/object_ny.h"
#include "overlays/actors/ovl_En_Go2/z_en_go2.h"
#include "overlays/actors/ovl_En_Du/z_en_du.h"
#include "overlays/actors/ovl_En_Sa/z_en_sa.h"
#include "overlays/actors/ovl_En_Owl/z_en_owl.h"
#include "overlays/actors/ovl_En_Zl4/z_en_zl4.h"
#include "overlays/actors/ovl_Demo_Im/z_demo_im.h"
#include "overlays/actors/ovl_En_Viewer/z_en_viewer.h"
#include "overlays/actors/ovl_En_Heishi2/z_en_heishi2.h"
#include "overlays/actors/ovl_En_Heishi1/z_en_heishi1.h"
#include "overlays/actors/ovl_En_Heishi3/z_en_heishi3.h"
#include "overlays/actors/ovl_En_Daiku_Kakariko/z_en_daiku_kakariko.h"
#include "overlays/actors/ovl_En_Niw_Lady/z_en_niw_lady.h"
#include "overlays/actors/ovl_En_Dodojr/z_en_dodojr.h"
#include "overlays/actors/ovl_En_Dodongo/z_en_dodongo.h"
#include "overlays/actors/ovl_En_Am/z_en_am.h"
#include "overlays/actors/ovl_En_Zf/z_en_zf.h"
#include "overlays/actors/ovl_En_Shopnuts/z_en_shopnuts.h"
#include "overlays/actors/ovl_En_Dns/z_en_dns.h"
#include "overlays/actors/ovl_En_Kakasi2/z_en_kakasi2.h"
#include "overlays/actors/ovl_En_Vm/z_en_vm.h"
#include "overlays/actors/ovl_En_Sw/z_en_sw.h"
#include "overlays/actors/ovl_En_Wf/z_en_wf.h"
#include "overlays/actors/ovl_En_Dekunuts/z_en_dekunuts.h"
#include "assets/objects/object_dekunuts/object_dekunuts.h"
#include "assets/objects/object_st/object_st.h"
#include "overlays/actors/ovl_En_Ossan/z_en_ossan.h"
#include "overlays/actors/ovl_En_GirlA/z_en_girla.h"
#include "child_route_shop_items.h"
#include "child_common_keys.h"
#include "overlays/actors/ovl_En_Ex_Item/z_en_ex_item.h"
#include "overlays/actors/ovl_Item_Etcetera/z_item_etcetera.h"
#include "overlays/actors/ovl_En_Ex_Ruppy/z_en_ex_ruppy.h"
#include "overlays/actors/ovl_En_G_Switch/z_en_g_switch.h"
#include "overlays/actors/ovl_En_Syateki_Man/z_en_syateki_man.h"
#include "overlays/actors/ovl_En_Bom_Bowl_Man/z_en_bom_bowl_man.h"
#include "overlays/actors/ovl_En_Takara_Man/z_en_takara_man.h"
#include "child_minigame_views.inc"
#include "assets/objects/object_skj/object_skj.h"
#include "overlays/actors/ovl_En_Cs/z_en_cs.h"
#include "overlays/actors/ovl_En_Mm/z_en_mm.h"
#include "overlays/actors/ovl_En_Skj/z_en_skj.h"
#include "overlays/actors/ovl_En_Dog/z_en_dog.h"
#include "overlays/actors/ovl_En_Gm/z_en_gm.h"
#include "overlays/actors/ovl_En_Ssh/z_en_ssh.h"
#include "overlays/actors/ovl_En_Sth/z_en_sth.h"
#include "overlays/actors/ovl_En_Tk/z_en_tk.h"
#include "overlays/actors/ovl_En_Hy/z_en_hy.h"
#include "overlays/actors/ovl_En_Heishi4/z_en_heishi4.h"
#include "overlays/actors/ovl_En_Hs2/z_en_hs2.h"
#include "overlays/actors/ovl_En_Ani/z_en_ani.h"
#include "overlays/actors/ovl_En_Tg/z_en_tg.h"
#include "overlays/actors/ovl_En_Toryo/z_en_toryo.h"
#include "overlays/actors/ovl_En_Syateki_Niw/z_en_syateki_niw.h"
#include "overlays/actors/ovl_En_Guest/z_en_guest.h"
#include "oot_core_shop.h"
#include "overlays/actors/ovl_Boss_Dodongo/z_boss_dodongo.h"
#include "overlays/actors/ovl_En_Bdfire/z_en_bdfire.h"
#include "overlays/actors/ovl_En_Fire_Rock/z_en_fire_rock.h"
#include "overlays/actors/ovl_En_Encount2/z_en_encount2.h"
#include "overlays/actors/ovl_Demo_Effect/z_demo_effect.h"
#include "overlays/actors/ovl_Bg_Dy_Yoseizo/z_bg_dy_yoseizo.h"
#include "assets/objects/object_god_lgt/object_god_lgt.h"
#include "assets/objects/object_efc_star_field/object_efc_star_field.h"
#include "assets/objects/object_kingdodongo/object_kingdodongo.h"
#include "assets/objects/object_oF1d_map/object_oF1d_map.h"
#include "assets/objects/object_sd/object_sd.h"
#include "assets/objects/object_shopnuts/object_shopnuts.h"
#include "z_actor_dlftbls.h"

static const SkelAnime* GenericNpc_Skel(Actor* a) {
    switch (a->id) {
        case ACTOR_BG_DY_YOSEIZO: return &((BgDyYoseizo*)a)->skelAnime;
        case ACTOR_EN_IN: return &((EnIn*)a)->skelAnime;
        case ACTOR_EN_MA1: return &((EnMa1*)a)->skelAnime;
        case ACTOR_EN_MA2: return &((EnMa2*)a)->skelAnime;
        case ACTOR_EN_TA: return &((EnTa*)a)->skelAnime;
        case ACTOR_EN_NIW: return &((EnNiw*)a)->skelAnime;
        case ACTOR_EN_COW: return &((EnCow*)a)->skelAnime;
        case ACTOR_EN_HORSE_LINK_CHILD: return &((EnHorseLinkChild*)a)->skin.skelAnime;
        case ACTOR_EN_HORSE_NORMAL: return &((EnHorseNormal*)a)->skin.skelAnime;
        case ACTOR_EN_SKB: return &((EnSkb*)a)->skelAnime;
        case ACTOR_EN_PEEHAT: return &((EnPeehat*)a)->skelAnime;
        case ACTOR_EN_PO_FIELD: return &((EnPoField*)a)->skelAnime;
        case ACTOR_EN_SB: return &((EnSb*)a)->skelAnime;
        case ACTOR_EN_WEIYER: return &((EnWeiyer*)a)->skelAnime;
        case ACTOR_EN_TITE: return &((EnTite*)a)->skelAnime;
        case ACTOR_EN_FIREFLY: return &((EnFirefly*)a)->skelAnime;
        case ACTOR_EN_GO2: return &((EnGo2*)a)->skelAnime;
        case ACTOR_EN_DU: return &((EnDu*)a)->skelAnime;
        case ACTOR_EN_SA: return &((EnSa*)a)->skelAnime;
        case ACTOR_EN_WF: return &((EnWf*)a)->skelAnime;
        case ACTOR_EN_DEKUNUTS: return &((EnDekunuts*)a)->skelAnime;
        case ACTOR_EN_OWL: return ((EnOwl*)a)->curSkelAnime;
        case ACTOR_EN_ZL4: return &((EnZl4*)a)->skelAnime;
        case ACTOR_DEMO_IM: return &((DemoIm*)a)->skelAnime;
        case ACTOR_EN_VIEWER: return &((EnViewer*)a)->skin.skelAnime;
        case ACTOR_EN_HEISHI2: return &((EnHeishi2*)a)->skelAnime;
        case ACTOR_EN_HEISHI1: return &((EnHeishi1*)a)->skelAnime;
        case ACTOR_EN_HEISHI3: return &((EnHeishi3*)a)->skelAnime;
        case ACTOR_EN_DAIKU_KAKARIKO: return &((EnDaikuKakariko*)a)->skelAnime;
        case ACTOR_EN_NIW_LADY: return &((EnNiwLady*)a)->skelAnime;
        case ACTOR_EN_DODOJR: return &((EnDodojr*)a)->skelAnime;
        case ACTOR_EN_DODONGO: return &((EnDodongo*)a)->skelAnime;
        case ACTOR_EN_AM: return &((EnAm*)a)->skelAnime;
        case ACTOR_EN_ZF: return &((EnZf*)a)->skelAnime;
        case ACTOR_EN_SHOPNUTS: return &((EnShopnuts*)a)->skelAnime;
        case ACTOR_EN_DNS: return &((EnDns*)a)->skelAnime;
        case ACTOR_EN_KAKASI2: return &((EnKakasi2*)a)->skelAnime;
        case ACTOR_EN_VM: return &((EnVm*)a)->skelAnime;
        case ACTOR_EN_SW: return &((EnSw*)a)->skelAnime;
        case ACTOR_EN_OSSAN: return &((EnOssan*)a)->skelAnime;
        case ACTOR_EN_HY: return &((EnHy*)a)->skelAnime;
        case ACTOR_EN_HEISHI4: return &((EnHeishi4*)a)->skelAnime;
        case ACTOR_EN_HS2: return &((EnHs2*)a)->skelAnime;
        case ACTOR_EN_ANI: return &((EnAni*)a)->skelAnime;
        case ACTOR_EN_TG: return &((EnTg*)a)->skelAnime;
        case ACTOR_EN_TORYO: return &((EnToryo*)a)->skelAnime;
        case ACTOR_EN_SYATEKI_NIW: return &((EnSyatekiNiw*)a)->skelAnime;
        case ACTOR_EN_GUEST: return &((EnGuest*)a)->skelAnime;
        case ACTOR_EN_SYATEKI_MAN: return &((EnSyatekiMan*)a)->skelAnime;
        case ACTOR_EN_BOM_BOWL_MAN: return &((EnBomBowlMan*)a)->skelAnime;
        case ACTOR_EN_TAKARA_MAN: return &((EnTakaraMan*)a)->skelAnime;
        case ACTOR_EN_CS: return &((EnCs*)a)->skelAnime;
        case ACTOR_EN_MM: return &((EnMm*)a)->skelAnime;
        case ACTOR_EN_SKJ: return &((EnSkj*)a)->skelAnime;
        case ACTOR_EN_DOG: return &((EnDog*)a)->skelAnime;
        case ACTOR_EN_GM: return &((EnGm*)a)->skelAnime;
        case ACTOR_EN_SSH: return &((EnSsh*)a)->skelAnime;
        case ACTOR_EN_STH: return &((EnSth*)a)->skelAnime;
        case ACTOR_EN_TK: return &((EnTk*)a)->skelAnime;
        default: return NULL;
    }
}

#define gSaveContext (*save)
extern "C" int oot_pack_npc_view(PlayState* play, Actor* actor, OotCoreNpcView* views,
                                  unsigned capacity, const SaveContext* save) {
    if (!capacity) return 0;
    OotCoreNpcView* v=views;
    const SkelAnime* skel;
    unsigned n=0;
    s32 itemView=ChildMinigame_ItemView(actor,play,v);
    if (itemView) return itemView;
    do {
        if (1 && (NPC_IN_PACK(ACTOR_EN_GIRLA) && actor->id == ACTOR_EN_GIRLA)) {
            const EnGirlA* stock = (const EnGirlA*)actor;
            u32 key = stock->isInitialized ? ChildRouteShop_ItemKey(stock->giDrawId) : 0;
            if (!key) continue;
            v->tint = stock->isSelected ? 8 : 0;
            v->mats = NULL; v->mat_count = 0; v->skin = 0;
            v->id = actor->id; v->params = actor->params;
            v->x = (s32)actor->world.pos.x;
            v->y = (s32)(actor->world.pos.y + actor->shape.yOffset * actor->scale.y);
            v->z = (s32)actor->world.pos.z;
            v->yaw = (u16)(actor->shape.rot.y + stock->yRotation);
            v->head_x = v->head_y = v->torso_x = v->torso_y = 0;
            v->frame = 0; v->alpha = 255;
            v->flags = actor->draw && !stock->isInvisible ? OOT_CORE_VIEW_DRAWN : 0;
            v->object = (u16)play->objectCtx.slots[actor->objectSlot].id;
            v->limbs = 0; v->anim = key; v->skeleton = key & ~0x00f00000u;
            /* Stock is baked at its source 0.25 actor scale. */
            v->scale_x = (u16)(int)(actor->scale.x * 1024);
            v->scale_y = (u16)(int)(actor->scale.y * 1024);
            n++;
            continue;
        } else if (1 && (NPC_IN_PACK(ACTOR_DEMO_EFFECT) && actor->id == ACTOR_DEMO_EFFECT) &&
                   (actor->params & 255) >= DEMO_EFFECT_GOD_LGT_DIN &&
                   (actor->params & 255) <= DEMO_EFFECT_GOD_LGT_FARORE) {
            const DemoEffect* god = (const DemoEffect*)actor;
            *v = {};
            v->id = actor->id; v->params = actor->params;
            v->x = (s32)actor->world.pos.x; v->y = (s32)actor->world.pos.y; v->z = (s32)actor->world.pos.z;
            v->yaw = actor->shape.rot.y; v->alpha = 255;
            v->flags = actor->draw ? OOT_CORE_VIEW_DRAWN : 0;
            if (play->csCtx.state != CS_STATE_IDLE && play->csCtx.actorCues[god->cueChannel] &&
                play->csCtx.actorCues[god->cueChannel]->id == 2) v->flags = 0;
            v->object = (u16)play->objectCtx.slots[actor->objectSlot].id;
            v->skeleton = v->anim = (u32)(uintptr_t)gGoldenGoddessAuraDL;
            v->skin = god->godLgt.type;
            v->scale_x = (u16)(int)(actor->scale.x * 2560);
            v->scale_y = (u16)(int)(actor->scale.y * 2560);
            n++;
            if (n < capacity) {
                views[n] = *v;
                v = &views[n++];
                v->skeleton = v->anim = (u32)(uintptr_t)gGoldenGoddessBodyDL;
                v->skin = 0; v->frame = god->godLgt.rotation;
            }
            continue;
        } else if (1 && (NPC_IN_PACK(ACTOR_EN_FIRE_ROCK) && actor->id == ACTOR_EN_FIRE_ROCK)) {
            const EnFireRock* rock = (const EnFireRock*)actor;
            if (rock->type == FIRE_ROCK_CEILING_SPOT_SPAWNER) continue;
            *v = {};
            v->id = actor->id; v->params = actor->params;
            v->x = (s32)(actor->world.pos.x + rock->relativePos.x);
            v->y = (s32)(actor->world.pos.y + rock->relativePos.y);
            v->z = (s32)(actor->world.pos.z + rock->relativePos.z);
            v->yaw = actor->shape.rot.y; v->alpha = 255;
            v->flags = actor->draw ? OOT_CORE_VIEW_DRAWN : 0;
            v->object = (u16)play->objectCtx.slots[actor->objectSlot].id;
            v->skeleton = v->anim = (u32)(uintptr_t)object_efc_star_field_DL_000DE0;
            /* Static recipe uses the common 0.01 offline model scale. */
            v->scale_x = (u16)(int)(actor->scale.x * 25600);
            v->scale_y = (u16)(int)(actor->scale.y * 25600);
            n++; continue;
        } else if (1 && (NPC_IN_PACK(ACTOR_EN_BDFIRE) && actor->id == ACTOR_EN_BDFIRE)) {
            const EnBdfire* fire = (const EnBdfire*)actor;
            v->mats = NULL; v->mat_count = 0; v->skin = 0; v->tint = 0;
            v->id = actor->id; v->params = actor->params;
            v->x = (s32)actor->world.pos.x; v->y = (s32)actor->world.pos.y;
            v->z = (s32)actor->world.pos.z; v->yaw = 0;
            v->head_x = v->head_y = v->torso_x = v->torso_y = 0;
            v->frame = fire->unk_156 & 7;
            v->alpha = (u8)(s32)fire->unk_18C;
            v->flags = actor->draw ? OOT_CORE_VIEW_DRAWN : 0;
            v->object = (u16)play->objectCtx.slots[actor->objectSlot].id;
            v->limbs = 0;
            v->skeleton = v->anim = (u32)(uintptr_t)object_kingdodongo_DL_01D950;
            v->scale_x = (u16)(int)(actor->scale.x * 256);
            v->scale_y = (u16)(int)(actor->scale.y * 256);
            n++;
            continue;
        } else if (1 &&
                   ((NPC_IN_PACK(ACTOR_EN_NY) && actor->id == ACTOR_EN_NY) || (NPC_IN_PACK(ACTOR_EN_SI) && actor->id == ACTOR_EN_SI) || (NPC_IN_PACK(ACTOR_EN_SKJNEEDLE) && actor->id == ACTOR_EN_SKJNEEDLE) ||
                    ((NPC_IN_PACK(ACTOR_EN_NUTSBALL) && actor->id == ACTOR_EN_NUTSBALL) && actor->params == 2))) {
            /* Skeleton-less Spikes: two object DLs key the baked sheet.
             * Variant follows EnNy_Draw: rock, metal, metal + spikes out. */
            const EnNy* ny = (const EnNy*)actor;
            const ActorProfile* profile = actor->overlayEntry ? actor->overlayEntry->profile : NULL;
            unsigned variant = (NPC_IN_PACK(ACTOR_EN_NY) && actor->id == ACTOR_EN_NY) ?
                (ny->unk_1E0 > 0.25f ? 2 : ny->unk_1D8 > ny->unk_1D4 ? 1 : 0) : 0;
            v->tint = 0;
            v->mats = NULL;
            v->mat_count = 0;
            v->skin = 0;
            v->id = actor->id;
            v->params = actor->params;
            v->x = (s32)actor->world.pos.x;
            v->y = (s32)actor->world.pos.y;
            if ((NPC_IN_PACK(ACTOR_EN_NUTSBALL) && actor->id == ACTOR_EN_NUTSBALL)) v->y += (int)(actor->shape.yOffset * actor->scale.y);
            v->z = (s32)actor->world.pos.z;
            v->yaw = (u16)actor->shape.rot.y;
            v->head_x = v->head_y = v->torso_x = v->torso_y = 0;
            v->frame = 0;
            v->alpha = 255;
            /* Death swaps Draw to the rock-fragment effect: no body sprite. */
            v->flags = (actor->draw != NULL && ((NPC_IN_PACK(ACTOR_EN_NUTSBALL) && actor->id == ACTOR_EN_NUTSBALL) || (NPC_IN_PACK(ACTOR_EN_SI) && actor->id == ACTOR_EN_SI) || (NPC_IN_PACK(ACTOR_EN_SKJNEEDLE) && actor->id == ACTOR_EN_SKJNEEDLE) ||
                       (profile && actor->draw == profile->draw))) ? OOT_CORE_VIEW_DRAWN : 0;
            v->object = (u16)play->objectCtx.slots[actor->objectSlot].id;
            v->limbs = 0;
            v->anim = (u32)(uintptr_t)gEnNySpikeDL | (variant << 20);
            v->skeleton = (u32)(uintptr_t)gEnNyRockBodyDL;
            if ((NPC_IN_PACK(ACTOR_EN_NUTSBALL) && actor->id == ACTOR_EN_NUTSBALL))
                v->skeleton = v->anim = (u32)(uintptr_t)(actor->params==2 ? gBusinessScrubDekuNutDL : gDekuNutsDekuNutDL);
            if ((NPC_IN_PACK(ACTOR_EN_SI) && actor->id == ACTOR_EN_SI))
                v->skeleton = v->anim = (u32)(uintptr_t)gSkulltulaTokenDL;
            if ((NPC_IN_PACK(ACTOR_EN_SKJNEEDLE) && actor->id == ACTOR_EN_SKJNEEDLE))
                v->skeleton = v->anim = (u32)(uintptr_t)gSkullKidNeedleDL;
            v->scale_x = (u16)(int)(actor->scale.x * 25600);
            v->scale_y = (u16)(int)(actor->scale.y * 25600);
            if (actor->colorFilterTimer)
                v->tint = (actor->colorFilterParams & 0x4000) ? 8 : 24;
            n++;
            continue;
        } else if (1 && (skel = GenericNpc_Skel(actor)) != NULL) {
            /* Generic NPC as a host sprite: object + animation + frame. */
            v->scale_x = v->scale_y = 256;
            v->tint = 0;
            v->mats = NULL;
            v->mat_count = 0;
            v->skin = 0;
            v->id = actor->id;
            v->params = actor->params;
            v->x = (s32)actor->world.pos.x;
            v->y = (s32)actor->world.pos.y;
            v->z = (s32)actor->world.pos.z;
            v->yaw = (u16)actor->shape.rot.y;
            v->head_x = v->head_y = v->torso_x = v->torso_y = 0;
            v->frame = (u16)(s32)skel->curFrame;
            v->alpha = 255;
            v->flags = (actor->draw != NULL) ? OOT_CORE_VIEW_DRAWN : 0;
            v->object = (u16)play->objectCtx.slots[actor->objectSlot].id;
            v->limbs = skel->limbCount;
            v->anim = (u32)(uintptr_t)skel->animation;
            v->skeleton = (u32)(uintptr_t)skel->skeleton;
            if ((NPC_IN_PACK(ACTOR_DEMO_IM) && actor->id == ACTOR_DEMO_IM)) {
                const DemoIm* impa = (const DemoIm*)actor;
                if (!impa->drawConfig) v->flags = 0;
                if (impa->drawConfig == 2) v->alpha = impa->alpha;
            }
            if ((NPC_IN_PACK(ACTOR_EN_VIEWER) && actor->id == ACTOR_EN_VIEWER) &&
                (!((EnViewer*)actor)->isVisible || play->csCtx.state == CS_STATE_IDLE || !play->csCtx.actorCues[1]))
                v->flags = 0;
            if ((NPC_IN_PACK(ACTOR_EN_HY) && actor->id == ACTOR_EN_HY) || (NPC_IN_PACK(ACTOR_EN_GUEST) && actor->id == ACTOR_EN_GUEST) || (NPC_IN_PACK(ACTOR_EN_HEISHI4) && actor->id == ACTOR_EN_HEISHI4) ||
                (NPC_IN_PACK(ACTOR_EN_HS2) && actor->id == ACTOR_EN_HS2) || (NPC_IN_PACK(ACTOR_EN_ANI) && actor->id == ACTOR_EN_ANI) || (NPC_IN_PACK(ACTOR_EN_TG) && actor->id == ACTOR_EN_TG) ||
                (NPC_IN_PACK(ACTOR_EN_TORYO) && actor->id == ACTOR_EN_TORYO) || (NPC_IN_PACK(ACTOR_EN_SYATEKI_NIW) && actor->id == ACTOR_EN_SYATEKI_NIW)) {
                v->scale_x = (u16)(int)(actor->scale.x * 25600);
                v->scale_y = (u16)(int)(actor->scale.y * 25600);
                v->y += (int)(actor->shape.yOffset * actor->scale.y);
                if ((NPC_IN_PACK(ACTOR_EN_GUEST) && actor->id == ACTOR_EN_GUEST)) v->anim |= CHILD_GUEST_VARIANT << 20;
                if ((NPC_IN_PACK(ACTOR_EN_HY) && actor->id == ACTOR_EN_HY)) {
                    unsigned type = actor->params & 0x7F;
                    if (type < 21) v->anim |= sChildHylianVariants[type] << 20;
                    /* Source Draw's local modelOffset, rotated with the body. */
                    const Vec3f* offset = &((EnHy*)actor)->modelOffset;
                    f32 s = Math_SinS(actor->shape.rot.y), c = Math_CosS(actor->shape.rot.y);
                    v->x += (int)((offset->x*c + offset->z*s) * actor->scale.x);
                    v->y += (int)(offset->y * actor->scale.y);
                    v->z += (int)((offset->z*c - offset->x*s) * actor->scale.z);
                }
            }
            if ((NPC_IN_PACK(ACTOR_EN_HORSE_LINK_CHILD) && actor->id == ACTOR_EN_HORSE_LINK_CHILD) || (NPC_IN_PACK(ACTOR_EN_HORSE_NORMAL) && actor->id == ACTOR_EN_HORSE_NORMAL)) {
                int scale = (NPC_IN_PACK(ACTOR_EN_HORSE_LINK_CHILD) && actor->id == ACTOR_EN_HORSE_LINK_CHILD) ? 51200 : 25600;
                /* Multiply two small fixed values: 51200 itself exceeds Q16. */
                v->scale_x = (u16)(int)((actor->scale.x * 200) * (scale / 200));
                v->scale_y = (u16)(int)((actor->scale.y * 200) * (scale / 200));
                v->y += (int)(actor->shape.yOffset * actor->scale.y);
                if ((NPC_IN_PACK(ACTOR_EN_HORSE_NORMAL) && actor->id == ACTOR_EN_HORSE_NORMAL)) {
                    const EnHorseNormal* horse = (const EnHorseNormal*)actor;
                    if (horse->spriteCloneEnabled && n + 1 < capacity) {
                        OotCoreNpcView* clone = &views[++n];
                        *clone = *v;
                        clone->x = (int)horse->spriteClonePos.x;
                        clone->y = (int)horse->spriteClonePos.y + (int)(actor->shape.yOffset * actor->scale.y);
                        clone->z = (int)horse->spriteClonePos.z;
                        clone->yaw = (u16)horse->spriteCloneYaw;
                    }
                }
            }
            if ((NPC_IN_PACK(ACTOR_BG_DY_YOSEIZO) && actor->id == ACTOR_BG_DY_YOSEIZO) || (NPC_IN_PACK(ACTOR_EN_ZL4) && actor->id == ACTOR_EN_ZL4) || (NPC_IN_PACK(ACTOR_DEMO_IM) && actor->id == ACTOR_DEMO_IM) || (NPC_IN_PACK(ACTOR_EN_VIEWER) && actor->id == ACTOR_EN_VIEWER) ||
                (NPC_IN_PACK(ACTOR_EN_OWL) && actor->id == ACTOR_EN_OWL) || (NPC_IN_PACK(ACTOR_EN_GO2) && actor->id == ACTOR_EN_GO2) || (NPC_IN_PACK(ACTOR_EN_DU) && actor->id == ACTOR_EN_DU) || (NPC_IN_PACK(ACTOR_EN_SA) && actor->id == ACTOR_EN_SA) ||
                (NPC_IN_PACK(ACTOR_EN_HEISHI2) && actor->id == ACTOR_EN_HEISHI2) || (NPC_IN_PACK(ACTOR_EN_HEISHI1) && actor->id == ACTOR_EN_HEISHI1) || (NPC_IN_PACK(ACTOR_EN_HEISHI3) && actor->id == ACTOR_EN_HEISHI3) || (NPC_IN_PACK(ACTOR_EN_DAIKU_KAKARIKO) && actor->id == ACTOR_EN_DAIKU_KAKARIKO) ||
                (NPC_IN_PACK(ACTOR_EN_NIW_LADY) && actor->id == ACTOR_EN_NIW_LADY) || (NPC_IN_PACK(ACTOR_EN_DODOJR) && actor->id == ACTOR_EN_DODOJR) ||
                (NPC_IN_PACK(ACTOR_EN_DODONGO) && actor->id == ACTOR_EN_DODONGO) || (NPC_IN_PACK(ACTOR_EN_AM) && actor->id == ACTOR_EN_AM) ||
                (NPC_IN_PACK(ACTOR_EN_ZF) && actor->id == ACTOR_EN_ZF) || (NPC_IN_PACK(ACTOR_EN_SHOPNUTS) && actor->id == ACTOR_EN_SHOPNUTS) ||
                (NPC_IN_PACK(ACTOR_EN_DNS) && actor->id == ACTOR_EN_DNS) || (NPC_IN_PACK(ACTOR_EN_KAKASI2) && actor->id == ACTOR_EN_KAKASI2) || (NPC_IN_PACK(ACTOR_EN_OSSAN) && actor->id == ACTOR_EN_OSSAN) ||
                (NPC_IN_PACK(ACTOR_EN_VM) && actor->id == ACTOR_EN_VM) || (NPC_IN_PACK(ACTOR_EN_SW) && actor->id == ACTOR_EN_SW) || (NPC_IN_PACK(ACTOR_EN_WF) && actor->id == ACTOR_EN_WF) || (NPC_IN_PACK(ACTOR_EN_DEKUNUTS) && actor->id == ACTOR_EN_DEKUNUTS) ||
                (NPC_IN_PACK(ACTOR_EN_DOG) && actor->id == ACTOR_EN_DOG) || (NPC_IN_PACK(ACTOR_EN_GM) && actor->id == ACTOR_EN_GM) || (NPC_IN_PACK(ACTOR_EN_SSH) && actor->id == ACTOR_EN_SSH) ||
                (NPC_IN_PACK(ACTOR_EN_STH) && actor->id == ACTOR_EN_STH) || (NPC_IN_PACK(ACTOR_EN_TK) && actor->id == ACTOR_EN_TK) ||
                (NPC_IN_PACK(ACTOR_EN_CS) && actor->id == ACTOR_EN_CS) || (NPC_IN_PACK(ACTOR_EN_MM) && actor->id == ACTOR_EN_MM) || (NPC_IN_PACK(ACTOR_EN_SKJ) && actor->id == ACTOR_EN_SKJ) ||
                (NPC_IN_PACK(ACTOR_EN_SYATEKI_MAN) && actor->id == ACTOR_EN_SYATEKI_MAN) || (NPC_IN_PACK(ACTOR_EN_BOM_BOWL_MAN) && actor->id == ACTOR_EN_BOM_BOWL_MAN) || (NPC_IN_PACK(ACTOR_EN_TAKARA_MAN) && actor->id == ACTOR_EN_TAKARA_MAN)) {
                v->scale_x = (u16)(int)(actor->scale.x * 25600);
                v->scale_y = (u16)(int)(actor->scale.y * 25600);
                v->y += (int)(actor->shape.yOffset * actor->scale.y);
                if ((NPC_IN_PACK(ACTOR_EN_OWL) && actor->id == ACTOR_EN_OWL) && (((EnOwl*)actor)->actionFlags & 2))
                    v->anim |= 1u << 20; /* offline upside-down head */
                if (actor->colorFilterTimer)
                    v->tint = (actor->colorFilterParams & 0x4000) ? 8 : 24;
                if ((NPC_IN_PACK(ACTOR_EN_GO2) && actor->id == ACTOR_EN_GO2)) {
                    const EnGo2* goron = (const EnGo2*)actor;
                    if (goron->spriteDrawMode == 1) v->anim = (u32)(uintptr_t)gGoronDL_00BD80;
                    if (goron->spriteDrawMode == 2) v->anim = (u32)(uintptr_t)gGoronDL_00C140;
                }
                if ((NPC_IN_PACK(ACTOR_EN_HEISHI2) && actor->id == ACTOR_EN_HEISHI2) &&
                    (((EnHeishi2*)actor)->type == 6 || ((EnHeishi2*)actor)->type == 9))
                    v->anim = (u32)(uintptr_t)gHeishiKingGuardDL;
                if ((NPC_IN_PACK(ACTOR_EN_DAIKU_KAKARIKO) && actor->id == ACTOR_EN_DAIKU_KAKARIKO))
                    v->anim |= (unsigned)(actor->params & 3) << 20;
                if ((NPC_IN_PACK(ACTOR_EN_ZF) && actor->id == ACTOR_EN_ZF)) v->alpha = ((EnZf*)actor)->alpha;
                if ((NPC_IN_PACK(ACTOR_EN_SA) && actor->id == ACTOR_EN_SA)) v->alpha = ((EnSa*)actor)->alpha;
                if ((NPC_IN_PACK(ACTOR_EN_SW) && actor->id == ACTOR_EN_SW) && ((actor->params >> 13) & 7)) v->anim |= 1u << 20;
                if ((NPC_IN_PACK(ACTOR_EN_VM) && actor->id == ACTOR_EN_VM)) v->yaw += ((EnVm*)actor)->headRotY;
                if ((NPC_IN_PACK(ACTOR_EN_GM) && actor->id == ACTOR_EN_GM)) v->anim |= 9u << 20;
                if ((NPC_IN_PACK(ACTOR_EN_SYATEKI_MAN) && actor->id == ACTOR_EN_SYATEKI_MAN) ||
                    ((NPC_IN_PACK(ACTOR_EN_BOM_BOWL_MAN) && actor->id == ACTOR_EN_BOM_BOWL_MAN) && ((EnBomBowlMan*)actor)->eyeTexIndex)) v->anim |= 1u << 20;
                if (((NPC_IN_PACK(ACTOR_EN_HEISHI2) && actor->id == ACTOR_EN_HEISHI2) && ((EnHeishi2*)actor)->type == 5 && GET_INFTABLE(INFTABLE_77)) ||
                    ((NPC_IN_PACK(ACTOR_EN_CS) && actor->id == ACTOR_EN_CS) && GET_ITEMGETINF(ITEMGETINF_3A)) ||
                    ((NPC_IN_PACK(ACTOR_EN_MM) && actor->id == ACTOR_EN_MM) && GET_ITEMGETINF(ITEMGETINF_3B)) ||
                    ((NPC_IN_PACK(ACTOR_EN_SKJ) && actor->id == ACTOR_EN_SKJ) && GET_ITEMGETINF(ITEMGETINF_39))) v->anim |= 1u << 20;
                if ((NPC_IN_PACK(ACTOR_EN_SKJ) && actor->id == ACTOR_EN_SKJ)) v->alpha = ((EnSkj*)actor)->alpha;
                if ((NPC_IN_PACK(ACTOR_EN_DOG) && actor->id == ACTOR_EN_DOG)) v->anim |= (unsigned)(actor->params & 1) << 20;
                if ((NPC_IN_PACK(ACTOR_EN_SSH) && actor->id == ACTOR_EN_SSH) && actor->params == 0) v->anim |= 1u << 20;
                if ((NPC_IN_PACK(ACTOR_EN_STH) && actor->id == ACTOR_EN_STH)) v->anim = v->skeleton | (unsigned)(8 + actor->params) << 20;
                if ((NPC_IN_PACK(ACTOR_EN_OSSAN) && actor->id == ACTOR_EN_OSSAN) && (actor->params == OSSAN_TYPE_KOKIRI ||
                    actor->params == OSSAN_TYPE_GORON || actor->params == OSSAN_TYPE_ZORA))
                    v->anim |= 8u << 20; /* keeper animation object, shared body archive */
            }
            if ((NPC_IN_PACK(ACTOR_EN_SKB) && actor->id == ACTOR_EN_SKB) || (NPC_IN_PACK(ACTOR_EN_PEEHAT) && actor->id == ACTOR_EN_PEEHAT) || (NPC_IN_PACK(ACTOR_EN_PO_FIELD) && actor->id == ACTOR_EN_PO_FIELD) ||
                (NPC_IN_PACK(ACTOR_EN_SB) && actor->id == ACTOR_EN_SB) || (NPC_IN_PACK(ACTOR_EN_WEIYER) && actor->id == ACTOR_EN_WEIYER) ||
                (NPC_IN_PACK(ACTOR_EN_TITE) && actor->id == ACTOR_EN_TITE) || (NPC_IN_PACK(ACTOR_EN_FIREFLY) && actor->id == ACTOR_EN_FIREFLY)) {
                v->scale_x = (u16)(int)(actor->scale.x * 25600);
                v->scale_y = (u16)(int)(actor->scale.y * 25600);
                v->y += (int)(actor->shape.yOffset * actor->scale.y);
                if (actor->colorFilterTimer)
                    v->tint = (actor->colorFilterParams & 0x4000) ? 8 : 24;
                if ((NPC_IN_PACK(ACTOR_EN_WEIYER) && actor->id == ACTOR_EN_WEIYER)) v->alpha = actor->shape.shadowAlpha;
                /* Baked sheets: Tektite 1 = blue textures; Keese 0 = normal
                 * body with eyes (ice Keese too), 1 = fire body without eyes. */
                if ((NPC_IN_PACK(ACTOR_EN_TITE) && actor->id == ACTOR_EN_TITE) && actor->params == TEKTITE_BLUE)
                    v->anim |= 1u << 20;
                if ((NPC_IN_PACK(ACTOR_EN_FIREFLY) && actor->id == ACTOR_EN_FIREFLY)) {
                    if (((EnFirefly*)actor)->bodyElementalType != 0) /* source enum NORMAL */
                        v->anim |= 1u << 20;
                    /* Source DrawXlu drops every limb unless the Lens is on. */
                    if ((actor->flags & ACTOR_FLAG_REACT_TO_LENS) && !play->actorCtx.lensActive)
                        v->flags = 0;
                }
                if ((NPC_IN_PACK(ACTOR_EN_SKB) && actor->id == ACTOR_EN_SKB) && (((EnSkb*)actor)->breakFlags & 2))
                    v->anim |= 1u << 20; /* source headless state */
                if ((NPC_IN_PACK(ACTOR_EN_PO_FIELD) && actor->id == ACTOR_EN_PO_FIELD)) {
                    EnPoField* poe = (EnPoField*)actor;
                    unsigned variant = actor->params == 1 ? 1 : 0;
                    v->alpha = poe->lightColor.a;
                    if (actor->category == ACTORCAT_MISC) {
                        variant = actor->gravity < 0 ? 2 : actor->params == 1 ? 4 : 3;
                        if (variant == 2) v->alpha = 255;
                    }
                    v->anim |= variant << 20;
                }
            }
            n++;
            continue;

        }
    } while (false);
    return n;
}
#undef gSaveContext
