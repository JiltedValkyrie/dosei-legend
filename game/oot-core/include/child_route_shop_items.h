/* Generated from source EnGirlA and z_draw; tools/build_shop_sprites.py. */
#ifndef CHILD_ROUTE_SHOP_ITEMS_H
#define CHILD_ROUTE_SHOP_ITEMS_H
#include "item.h"
#include "assets/objects/object_gi_arrow/object_gi_arrow.h"
#include "assets/objects/object_gi_bomb_1/object_gi_bomb_1.h"
#include "assets/objects/object_gi_bomb_2/object_gi_bomb_2.h"
#include "assets/objects/object_gi_clothes/object_gi_clothes.h"
#include "assets/objects/object_gi_egg/object_gi_egg.h"
#include "assets/objects/object_gi_fire/object_gi_fire.h"
#include "assets/objects/object_gi_fish/object_gi_fish.h"
#include "assets/objects/object_gi_gerudomask/object_gi_gerudomask.h"
#include "assets/objects/object_gi_ghost/object_gi_ghost.h"
#include "assets/objects/object_gi_golonmask/object_gi_golonmask.h"
#include "assets/objects/object_gi_heart/object_gi_heart.h"
#include "assets/objects/object_gi_insect/object_gi_insect.h"
#include "assets/objects/object_gi_ki_tan_mask/object_gi_ki_tan_mask.h"
#include "assets/objects/object_gi_liquid/object_gi_liquid.h"
#include "assets/objects/object_gi_longsword/object_gi_longsword.h"
#include "assets/objects/object_gi_milk/object_gi_milk.h"
#include "assets/objects/object_gi_nuts/object_gi_nuts.h"
#include "assets/objects/object_gi_rabit_mask/object_gi_rabit_mask.h"
#include "assets/objects/object_gi_redead_mask/object_gi_redead_mask.h"
#include "assets/objects/object_gi_seed/object_gi_seed.h"
#include "assets/objects/object_gi_shield_1/object_gi_shield_1.h"
#include "assets/objects/object_gi_shield_2/object_gi_shield_2.h"
#include "assets/objects/object_gi_skj_mask/object_gi_skj_mask.h"
#include "assets/objects/object_gi_soldout/object_gi_soldout.h"
#include "assets/objects/object_gi_soul/object_gi_soul.h"
#include "assets/objects/object_gi_stick/object_gi_stick.h"
#include "assets/objects/object_gi_truth_mask/object_gi_truth_mask.h"
#include "assets/objects/object_gi_zoramask/object_gi_zoramask.h"

static u32 ChildRouteShop_ItemKey(s16 gid) {
    switch (gid) {
        case GID_DEKU_NUTS: return (u32)(uintptr_t)gGiNutDL | (0u << 20);
        case GID_ARROWS_10: return (u32)(uintptr_t)gGiArrowMediumDL | (0u << 20);
        case GID_ARROWS_30: return (u32)(uintptr_t)gGiArrowMediumDL | (1u << 20);
        case GID_BOMB: return (u32)(uintptr_t)gGiBombDL | (0u << 20);
        case GID_DEKU_STICK: return (u32)(uintptr_t)gGiStickDL | (0u << 20);
        case GID_FISH: return (u32)(uintptr_t)gGiFishDL | (0u << 20);
        case GID_BOTTLE_POTION_RED: return (u32)(uintptr_t)gGiRedPotColorDL | (0u << 20);
        case GID_BOTTLE_POTION_GREEN: return (u32)(uintptr_t)gGiRedPotColorDL | (1u << 20);
        case GID_BOTTLE_POTION_BLUE: return (u32)(uintptr_t)gGiRedPotColorDL | (2u << 20);
        case GID_SWORD_BIGGORON: return (u32)(uintptr_t)gGiBiggoronSwordDL | (0u << 20);
        case GID_SHIELD_HYLIAN: return (u32)(uintptr_t)gGiHylianShieldDL | (0u << 20);
        case GID_SHIELD_DEKU: return (u32)(uintptr_t)gGiDekuShieldDL | (0u << 20);
        case GID_TUNIC_GORON: return (u32)(uintptr_t)gGiGoronCollarColorDL | (0u << 20);
        case GID_TUNIC_ZORA: return (u32)(uintptr_t)gGiGoronCollarColorDL | (1u << 20);
        case GID_RECOVERY_HEART: return (u32)(uintptr_t)gGiRecoveryHeartDL | (0u << 20);
        case GID_BOTTLE_MILK_FULL: return (u32)(uintptr_t)gGiMilkBottleContentsDL | (0u << 20);
        case GID_EGG: return (u32)(uintptr_t)gGiEggMaterialDL | (0u << 20);
        case GID_BOMBCHU: return (u32)(uintptr_t)gGiBombchuDL | (0u << 20);
        case GID_DEKU_SEEDS: return (u32)(uintptr_t)gGiSeedDL | (0u << 20);
        case GID_MASK_KEATON: return (u32)(uintptr_t)gGiKeatonMaskDL | (0u << 20);
        case GID_MASK_SPOOKY: return (u32)(uintptr_t)gGiSpookyMaskDL | (0u << 20);
        case GID_MASK_SKULL: return (u32)(uintptr_t)gGiSkullMaskDL | (0u << 20);
        case GID_MASK_BUNNY_HOOD: return (u32)(uintptr_t)gGiBunnyHoodDL | (0u << 20);
        case GID_MASK_TRUTH: return (u32)(uintptr_t)gGiMaskOfTruthDL | (0u << 20);
        case GID_MASK_ZORA: return (u32)(uintptr_t)gGiZoraMaskDL | (0u << 20);
        case GID_MASK_GORON: return (u32)(uintptr_t)gGiGoronMaskDL | (0u << 20);
        case GID_MASK_GERUDO: return (u32)(uintptr_t)gGiGerudoMaskDL | (0u << 20);
        case GID_SOLDOUT: return (u32)(uintptr_t)gGiSoldOutDL | (0u << 20);
        case GID_BLUE_FIRE: return (u32)(uintptr_t)gGiBlueFireChamberstickDL | (0u << 20);
        case GID_BUG: return (u32)(uintptr_t)gGiBugsContainerDL | (0u << 20);
        case GID_BIG_POE: return (u32)(uintptr_t)gGiGhostContainerLidDL | (0u << 20);
        case GID_POE: return (u32)(uintptr_t)gGiGhostContainerLidDL | (1u << 20);
        case GID_FAIRY: return (u32)(uintptr_t)gGiFairyContainerBaseCapDL | (0u << 20);
        case GID_ARROWS_5: return (u32)(uintptr_t)gGiArrowMediumDL | (2u << 20);
        default: return 0;
    }
}
#endif
