#include "oot_core_host.h"
#include "ui_preferences.h"
#ifdef DOSEI_OOT_CORE
/* Glue, not per-vertex work: size over speed (work RAM). */
#pragma GCC optimize("Os")
#include <jo/jo.h>
#include "action_audio.h"
#include "oot_core_audio.h"
/* Source sequence ids (include/tables/sequence_table.h); host has no enum. */
#define NA_BGM_NATURE_AMBIENCE 1u
#define NA_BGM_TIMED_MINI_GAME 108u
#include "music_songs.h"
#include "music_area.h"
#include "music.h"
#include "cdda.h"
#include "health_hud.h"
#include "recomp.h"
#include "frame_timer.h"
#include "perf_sub.h"
#include "gameplay.h"
#include "game_mode.h"
#include "kokiri_sgl.h"
#include "kokiri_actors.h"
#include "asset_names.h"
#include "scene_flow.h"
#include "ram_cart.h"
#include "ram_low.h"
#include "save_state.h"
#include "oot_scene_blob.h"
#include "oot_actor_pack.h"
#include "actor_mesh.h"
#include "npc_draw.h"
#include "collide.h"
#include "kokiri_collision.h"
#ifdef CORE_COLLISION
#include "bg_core_shim.h"
#endif
#include "player_items.h"
#include "world_props.h"
#include "player_attack.h"
#include <stdlib.h>
#include <string.h>
/* Generic decomp NPCs as baked sprites (tools/build_npc_sprites.py --generic,
** blob OOT_CORE_FLAG_NPC_SPRITES): no Actor_Draw, no limb matrices. */
#define CORE_SPRITES 1
#include "npc_sprite.h"
#include "host_cold.h"
/* Read only after boot loads HOSTCOLD.BIN (host_cold.h). */
HOST_COLD static const OotCoreSpriteLibrary
core_sprite_rows[] = {
#include "../build/oot-core/generic_sprites.h"
    { 0xfff, 0, 0 }, /* source get-item atlas, selected per scene */
};
#define CORE_SPRITE_ROWS (sizeof core_sprite_rows / sizeof core_sprite_rows[0])
#define CORE_SPRITE_SLOTS 32 /* Field parents, larvae and Stalchildren; existing bank/carve */
#define CORE_SPRITE_HEAP_PERCENT 85   /* leave heap for the rest of the scene */
#define CORE_MESHES_MAX 40
/* Decomp actor ids (actor_table.h) of Link's tools. */
#define ACTOR_EN_BOM     0x0010
#define ACTOR_EN_ARROW   0x0016
#define ACTOR_EN_BOOM    0x0032
#define ACTOR_ARMS_HOOK  0x0066
#define ACTOR_EN_BOM_CHU 0x00DA
#define ACTOR_ARROW_FIRE 0x010A /* Arrow_Fire/Ice/Light: EnArrow's elemental child */
#define ACTOR_ARROW_LIGHT 0x010C
enum { TOOL_ARW, TOOL_BOM, TOOL_CHU, TOOL_BOO, TOOL_HKT, TOOL_HKC, TOOL_BGS, TOOL_MIR,
       TOOL_IRB, TOOL_HOB, TOOL_EXP, TOOL_AIM, TOOL_MAG, TOOL_COUNT };
/* Existing owner records share the already reserved draw-state carve. This
 * moves no collision payload and adds no heap/carve reservation. */
typedef struct {
    unsigned int key;
    uint32_t id;
    collision_triangle_t *tri;
    bg_mesh_t mesh;
} core_dyna_t;
typedef struct {
    unsigned char *sprite[CORE_SPRITE_ROWS]; /* sheets remain on the cart heap */
    unsigned char tried[CORE_SPRITE_ROWS];
    npc_sprite_inst_t inst[CORE_SPRITE_SLOTS];
    unsigned int reserved;
    oot_core_sprite_stats_t stats;
    actor_mesh_t *mesh[CORE_MESHES_MAX];
    OotCoreMeshKey mesh_key[CORE_MESHES_MAX];
    unsigned char mesh_ready[CORE_MESHES_MAX];
    unsigned int mesh_count;
    /* Link's tools: sheets by TOOL_*, one VDP1 slot each, C contact mirrors. */
    unsigned char *tool_sheet[TOOL_COUNT];
    unsigned char tool_tried[TOOL_COUNT];
    npc_sprite_inst_t tool_inst[TOOL_COUNT];
    collider_t tool_at[OOT_CORE_TOOL_VIEWS_MAX];
    int tool_pull[6];
    unsigned int tool_bits;
    OotCoreCutsceneCameraView cutscene_camera;
    OotCoreShopView shop;
    OotCoreTimerView timer;
    signed char timer_column, timer_row;
    unsigned char timer_shown;
    int cutscene_distance;
    POINT letterbox_points[8];
    PDATA letterbox_data;
    POINT beam_points[4];
    PDATA beam_data;
    core_dyna_t dyna[OOT_CORE_DYNA_VIEWS_MAX];
    unsigned int audio_queue[8]; /* command:16, argument:16; slave writes, master drains */
    unsigned int audio_count;
    const music_bank_t* resume_bank;
    unsigned short resume_sequence, source_sequence;
} core_draw_state_t;
#if defined(__sh__)
typedef char core_draw_low_fits[sizeof(core_draw_state_t) <= RAM_LOW_OOTDRAW_BYTES ? 1 : -1];
#define CORE_DRAW ((core_draw_state_t *)RAM_LOW(RAM_LOW_OOTDRAW_OFFSET))
#else
static core_draw_state_t core_draw_storage;
#define CORE_DRAW (&core_draw_storage)
#endif
#define core_sprite (CORE_DRAW->sprite)
#define core_sprite_tried (CORE_DRAW->tried)
#define core_sprite_inst (CORE_DRAW->inst)
#define core_sprite_reserved (CORE_DRAW->reserved)
#define sprite_stats (CORE_DRAW->stats)
#define core_mesh (CORE_DRAW->mesh)
#define core_mesh_key (CORE_DRAW->mesh_key)
#define core_mesh_ready (CORE_DRAW->mesh_ready)
#define core_mesh_count (CORE_DRAW->mesh_count)
#define core_dyna (CORE_DRAW->dyna)

static void core_draw_init(void)
{
    memset(CORE_DRAW, 0, sizeof *CORE_DRAW);
    CORE_DRAW->resume_sequence=CORE_DRAW->source_sequence=0xffffu;
}


#define ENTRY_RAW ((const OotCoreEntry *)OOT_CORE_LOAD_ADDR)
#if defined(PLAYER_SOURCE) && !defined(DOSEI_NO_SLAVE_JOBS)
#define OOT_CORE_ASYNC 1
#endif
#ifdef OOT_CORE_ASYNC
/* Async core update (2026-10-09): the slave SH-2 runs Actor_UpdateAll while
 * the master draws. SH-2 caches are write-through but not coherent: the
 * slave purges before it starts, the master after the join, and flags the
 * other CPU polls are read and written cache-through. */
#define UNCACHED(v) (*(volatile __typeof__(v) *)((uintptr_t)&(v) | 0x20000000u))
static unsigned char async_busy;
static unsigned int async_violations;
#ifndef DOSEI_CLEAN_TEST
static unsigned int async_violation_line;
#endif
static inline const OotCoreEntry *entry_checked(
#ifndef DOSEI_CLEAN_TEST
    unsigned int line
#else
    void
#endif
)
{
    if (UNCACHED(async_busy)) {
        ++async_violations;   /* host entered the core mid-update */
#ifndef DOSEI_CLEAN_TEST
        async_violation_line = line;
#endif
    }
    return ENTRY_RAW;
}
#ifndef DOSEI_CLEAN_TEST
#define ENTRY (entry_checked(__LINE__))
#else
#define ENTRY (entry_checked())
#endif
#define ASYNC_BUSY() (UNCACHED(async_busy) != 0)
/* Core callbacks that touch hardware (sound) or fail fatally are queued while
 * the slave runs and replayed by the master at the join. */
#define SFX_QUEUE 32
static unsigned short sfx_queue[SFX_QUEUE];
/* Draw-phase snapshot (2026-10-09 scheduling): the slave updates the core
 * from the start of the draw, so the master draws the core's actors from
 * copies taken just before the kick (oot_core_async_kick). */
#define SNAP_NPC_MAX 32
#define SNAP_VIEW_MAX 24
#ifdef __sh__
/* Low RAM: master writes before the kick and reads while drawing. */
#define snap_npc ((OotCoreNpcView *)RAM_LOW(RAM_LOW_SNAP_NPC_OFFSET))
typedef char snap_npc_fits[sizeof(OotCoreNpcView) * SNAP_NPC_MAX
                           <= RAM_LOW_SNAP_NPC_BYTES ? 1 : -1];
#else
static OotCoreNpcView snap_npc[SNAP_NPC_MAX];
#endif
static int snap_sign_parts[KOKIRI_SIGN_COUNT];
static OotCoreDrawItem snap_items[OOT_CORE_DRAW_ITEMS_MAX];
#ifdef __sh__
/* Low RAM, master-only like snap_npc: filled before the kick, read while drawing. */
#define snap_view ((OotCoreActorView (*)[SNAP_VIEW_MAX])RAM_LOW(RAM_LOW_SNAP_VIEW_OFFSET))
#define snap_tools ((OotCoreToolView *)RAM_LOW(RAM_LOW_SNAP_VIEW_OFFSET + \
                    2 * SNAP_VIEW_MAX * sizeof(OotCoreActorView)))
typedef char snap_view_fits[2 * SNAP_VIEW_MAX * sizeof(OotCoreActorView) +
                            OOT_CORE_TOOL_VIEWS_MAX * sizeof(OotCoreToolView)
                            <= RAM_LOW_SNAP_VIEW_BYTES ? 1 : -1];
#else
static OotCoreToolView snap_tools[OOT_CORE_TOOL_VIEWS_MAX];
static OotCoreActorView snap_view[2][SNAP_VIEW_MAX];   /* ACTORCAT_PROP, ACTORCAT_MISC */
#endif
static int snap_npc_n, snap_items_n, snap_tools_n, snap_view_n[2], snap_effect_n;
static unsigned int sfx_queued;
static unsigned int deferred_fatal[4];
#else
#define ENTRY ENTRY_RAW
#define ASYNC_BUSY() 0
#endif

/* ---- OotCoreHost: decomp -> C backends ---- */
static void host_sfx_now(unsigned short sfx_id)
{
#ifdef PLAYER_SOURCE
    /* Real Player movement: NA_SE_PL_WALK_* (0x800 + surface), NA_SE_PL_JUMP*
     * (0x810), NA_SE_PL_LAND* (0x820) -> the host's step/jump samples. */
    if (sfx_id >= 0x800 && sfx_id < 0x830) {
        action_audio_events(sfx_id >= 0x810 && sfx_id < 0x820 ? GP_EVENT_JUMP : GP_EVENT_FOOTSTEP);
        return;
    }
#endif
    action_audio_decomp_sfx(sfx_id);
}

static void host_sfx(unsigned short sfx_id, int x, int y, int z)
{
    (void)x; (void)y; (void)z;
#ifdef OOT_CORE_ASYNC
    if (ASYNC_BUSY()) {
        unsigned int n = UNCACHED(sfx_queued);
        if (n < SFX_QUEUE) {
            ((volatile unsigned short *)((uintptr_t)sfx_queue | 0x20000000u))[n] = sfx_id;
            UNCACHED(sfx_queued) = n + 1;
        }
        return;
    }
#endif
    host_sfx_now(sfx_id);
}

/* Profiling clock. The master's FRT extension is not the slave's to touch;
 * during an async update the core runs on the slave (the master never enters
 * it then), which extends its own FRT here. Both run at /128, same units. */
#ifdef OOT_CORE_ASYNC
static uint16_t slave_previous;
static unsigned int slave_extended;
static unsigned int slave_ticks(void)
{
    uint16_t now = frame_timer_frc();
    if (now < slave_previous) slave_extended += 0x10000u;
    slave_previous = now;
    return slave_extended + now;
}
#endif
static unsigned int host_ticks(void)
{
#ifdef OOT_CORE_ASYNC
    if (ASYNC_BUSY()) return slave_ticks();
#endif
    return frame_timer_ticks();
}

/* Decomp ItemId (include/item.h) -> C save item. */
#include "core_item_grants.inc"
static unsigned char host_give_item(unsigned char item)
{
    int extra = core_item_grants(item);
    if (extra >= 0) return extra ? 0xFF : item;
    /* z_parameter.c Item_Give branches for the child route. Source upgrade
     * field (gUpgradeShifts): bomb bag bits 3-5, strength bits 6-8. */
    static const uint8_t bomb_capacity[4] = { 0, 20, 30, 40 }; /* gUpgradeCapacities */
    static const uint8_t bomb_refill[4] = { 5, 10, 20, 30 };   /* sAmmoRefillCounts */
    unsigned int bag = (save_state.source_upgrades >> 3) & 7u, total;
    save_item_t give;
    switch (item) {
    /* ITEM_WEIRD_EGG..ITEM_CLAIM_CHECK: INV_CONTENT replaces the child
     * trade slot; C assignments follow the slot. */
    case 0x21: /* ITEM_WEIRD_EGG */
    case 0x23: /* ITEM_ZELDAS_LETTER */
        save_state.source_items[23] = item;
        return 0xFF;
    case 0x4D: /* ITEM_BOMB_BAG_20 */
        if (!bag) {
            save_state.source_upgrades = (save_state.source_upgrades & ~(7u << 3)) | (1u << 3);
            save_state.source_items[2] = 0x02; /* INV_CONTENT(ITEM_BOMB) */
            save_state.source_ammo[2] = bomb_capacity[1];
        } else if (save_state.source_ammo[2] < bomb_capacity[bag])
            ++save_state.source_ammo[2];
        return 0xFF;
    case 0x4E: /* ITEM_BOMB_BAG_30 */
    case 0x4F: /* ITEM_BOMB_BAG_40 */
        save_state.source_upgrades = (save_state.source_upgrades & ~(7u << 3)) |
                                     ((unsigned)(item - 0x4C) << 3);
        save_state.source_ammo[2] = bomb_capacity[item - 0x4C];
        return 0xFF;
    case 0x50: /* ITEM_STRENGTH_GORONS_BRACELET */
        save_state.source_upgrades = (save_state.source_upgrades & ~(7u << 6)) | (1u << 6);
        return 0xFF;
    case 0x8E: case 0x8F: case 0x90: case 0x91: /* ITEM_BOMBS_5..30 */
        total = save_state.source_ammo[2] + bomb_refill[item - 0x8E];
        save_state.source_ammo[2] = (uint8_t)(total > bomb_capacity[bag] ? bomb_capacity[bag] : total);
        return 0xFF;
    case 0x87: /* ITEM_RUPEE_PURPLE */
    case 0x88: /* ITEM_RUPEE_GOLD */
        total = save_state.rupees + (item == 0x87 ? 50u : 200u);
        save_state.rupees = (uint16_t)(total > save_wallet_capacity() ? save_wallet_capacity() : total);
        gameplay.rupees = save_state.rupees;
        return 0xFF;
    case 0x3E: give = SAVE_ITEM_SHIELD_DEKU; break;      /* ITEM_SHIELD_DEKU */
    case 0x72: give = SAVE_ITEM_HEART_CONTAINER; break;  /* ITEM_HEART_CONTAINER */
    /* Source Inventory_ReplaceItem at dawn: trade slots already persist in
     * source_items. C assignments point at a slot, so its icon follows it. */
    case 0x22: /* ITEM_CHICKEN: SLOT_TRADE_CHILD, ITEM_WEIRD_EGG */
        if (save_state.source_items[23] != 0x21) return item;
        save_state.source_items[23] = item;
        return 0xFF;
    case 0x2E: /* ITEM_POCKET_CUCCO: SLOT_TRADE_ADULT, ITEM_POCKET_EGG */
        if (save_state.source_items[22] != 0x2D) return item;
        save_state.source_items[22] = item;
        return 0xFF;
    case 0x00: give = SAVE_ITEM_DEKU_STICK; break;      /* ITEM_DEKU_STICK */
    case 0x01: give = SAVE_ITEM_DEKU_NUT; break;        /* ITEM_DEKU_NUT */
    case 0x83: give = SAVE_ITEM_RECOVERY_HEART; break;  /* ITEM_RECOVERY_HEART */
    case 0x84: give = SAVE_ITEM_RUPEE_GREEN; break;     /* ITEM_RUPEE_GREEN */
    case 0x85: give = SAVE_ITEM_RUPEE_BLUE; break;      /* ITEM_RUPEE_BLUE */
    case 0x86: give = SAVE_ITEM_RUPEE_RED; break;       /* ITEM_RUPEE_RED */
    case 0x8A: give = SAVE_ITEM_DEKU_STICKS_5; break;   /* ITEM_DEKU_STICKS_5 */
    case 0x8C: give = SAVE_ITEM_DEKU_NUTS_5; break;     /* ITEM_DEKU_NUTS_5 */
    case 0x8D: give = SAVE_ITEM_DEKU_NUTS_10; break;    /* ITEM_DEKU_NUTS_10 */
    case 0x58: give = SAVE_ITEM_SEEDS_5; break;         /* ITEM_DEKU_SEEDS (+5) */
    case 0x14: give = SAVE_ITEM_BOTTLE_EMPTY; break;
    case 0x20: give = SAVE_ITEM_BOTTLE_POE; break;
    case 0x1E: give = SAVE_ITEM_BOTTLE_BIG_POE; break;
    case 0x1A: give = SAVE_ITEM_BOTTLE_MILK_FULL; break; /* Talon's first bottle */
    case 0x82: give = SAVE_ITEM_MILK; break;            /* cow/Talon refill */
    default: return item; /* not in the C save yet: not given */
    }
    if (!save_item_give(give)) return item;
    gameplay.rupees = save_state.rupees; /* HUD counter */
    return 0xFF;
}

/* Health_ChangeBy: 1/16 heart units. Negative actor calls queue the C reaction;
 * report the pending result now, including dodge/double defense, so a lethal
 * source call does not incorrectly report survival before C consumes it. */
static int host_health_change(short amount)
{
#ifdef PLAYER_SOURCE
    /* z_parameter Health_ChangeBy on the C save (the one owner): the real
     * Player plays its own damage reaction and i-frames. */
    if (amount >= 0) save_heal((unsigned int)amount);
    else {
        unsigned int damage = (unsigned int)-(int)amount;
        if (save_state.source_double_defense) damage >>= 1;
        save_state.health = save_state.health > damage ? save_state.health - damage : 0;
    }
    return save_state.health != 0;
#endif
    if (amount >= 0) save_heal((unsigned int)amount);
    else if (!gameplay.intangible && !gameplay.hurt_pending && !gameplay.dead) {
        /* Actor-origin damage shares C Link's next-step reaction/i-frames. */
        gameplay.hurt_pending = 1;
        gameplay.hurt_damage = (unsigned int)-(int)amount;
        gameplay.hurt_yaw = recomp_link_yaw;
        gameplay.hurt_speed = 0;
        gameplay.hurt_effect = gameplay.hurt_large = gameplay.hurt_core = 0;
    }
    if (amount < 0 && gameplay.hurt_pending && !gameplay.invulnerable) {
        unsigned int damage = gameplay.hurt_damage;
        if (save_state.source_double_defense) damage = (damage >> 1) + (damage & 1);
        return save_state.health > damage;
    }
    return save_state.health != 0;
}

static void host_player_combat(OotCoreCombatState *out)
{
    unsigned int flags = player_attack_damage_flags(gameplay.attack_id);
    bool jump = flags == DMG_JUMP_KOKIRI;
    bool spin = flags == DMG_SPIN_KOKIRI;
    memset(out, 0, sizeof *out);
    out->flags = (gameplay.shielding ? OOT_COMBAT_SHIELD : 0) |
        ((gameplay.intangible || gameplay.hurt_pending) ? OOT_COMBAT_INTANGIBLE : 0) |
        (gameplay.invulnerable ? OOT_COMBAT_DODGE : 0) |
        (gameplay.dead || gameplay_blocks_world() ? OOT_COMBAT_DISABLED : 0) |
        (gameplay.face_locked ? OOT_COMBAT_LOCKED : 0);
    out->shield = save_state.equip_shield;
    out->swing = gameplay.swing_count;
    out->damage = 1;
    if (!save_state.link_age) {
        bool giant = save_state.equip_sword == EQUIP_VALUE_SWORD_BIGGORON;
        flags = jump ? (giant ? DMG_JUMP_GIANT : DMG_JUMP_MASTER) :
            spin ? (giant ? DMG_SPIN_GIANT : DMG_SPIN_MASTER) :
                   (giant ? DMG_SLASH_GIANT : DMG_SLASH_MASTER);
        out->damage = giant ? 4 : 2;
    }
    if (jump) out->damage *= 2;
    if (player_items_stick()) { flags = DMG_DEKU_STICK; out->damage = jump ? 4 : 2; }
    out->damage_flags = flags ? flags : DMG_SLASH_KOKIRI;
}

static int host_player_hit(const OotCorePlayerHit *hit)
{
    if (!hit || gameplay.dead || gameplay_is_paused()) return 0;
    if (hit->flags & OOT_HIT_GUARD) {
        gameplay.guard_pending = true;
        gameplay.events |= GP_EVENT_GUARD;
        return 1;
    }
    if (gameplay.hurt_pending) return 0;
    if (gameplay.intangible && !(hit->flags & OOT_HIT_LARGE)) return 0;
    gameplay.hurt_pending = 1;
    gameplay.hurt_damage = gameplay.intangible ? 0 : hit->damage;
    gameplay.hurt_yaw = hit->yaw;
    gameplay.hurt_speed = hit->speed_q16;
    gameplay.hurt_effect = hit->effect;
    gameplay.hurt_large = (hit->flags & OOT_HIT_LARGE) != 0;
    gameplay.hurt_core = 1;
    return 1;
}

static void host_rupees_change(short amount)
{
    int r = (int)save_state.rupees + amount;
    unsigned int cap = save_wallet_capacity();
    save_state.rupees = (uint16_t)(r < 0 ? 0 : (unsigned int)r > cap ? cap : (unsigned int)r);
    gameplay.rupees = save_state.rupees;
}

#ifdef PLAYER_SOURCE
/* Inventory_ChangeAmmo on the C save: source ItemId -> its ammo counter.
 * Capacities: the C save's own (seeds) or the source cap of 99. */
static void host_ammo_change(unsigned char item, short amount)
{
    static const unsigned char bomb_cap[4] = {0,20,30,40};
    static const unsigned char bow_cap[4] = {0,30,40,50};
    static const unsigned char stick_cap[4] = {0,10,20,30};
    static const unsigned char nut_cap[4] = {0,20,30,40};
    uint8_t *ammo = 0;
    int value, cap = 99;
    switch (item) {
    case 0x00: ammo = &save_state.stick_ammo;
        cap = stick_cap[save_state.stick_upgrade & 3]; break;
    case 0x01: ammo = &save_state.nut_ammo;
        cap = nut_cap[save_state.nut_upgrade & 3]; break;
    case 0x06: case 0x58: ammo = &save_state.ammo_seeds;        /* ITEM_SLINGSHOT/SEEDS */
        cap = (int)save_seed_capacity(); break;
    case 0x02: ammo = &save_state.source_ammo[2];
        cap = bomb_cap[(save_state.source_upgrades >> 3) & 3]; break;
    case 0x03: ammo = &save_state.source_ammo[3];
        cap = bow_cap[save_state.source_upgrades & 3]; break;
    case 0x09: ammo = &save_state.source_ammo[8]; cap = 50; break; /* ITEM_BOMBCHU */
    case 0x10: ammo = &save_state.source_ammo[14]; break;       /* ITEM_MAGIC_BEAN */
    default: return;
    }
    value = (int)*ammo + amount;
    *ammo = (uint8_t)(value < 0 ? 0 : value > cap ? cap : value);
}

/* Magic_RequestChange through health_hud.c's meter (MAGIC_CONSUME_NOW is
 * what Player items use); OOT_CORE_MAGIC_FILL = Magic_Fill. */
static int host_magic_request(short amount, short type)
{
    if (type == OOT_CORE_MAGIC_ACQUIRE) {
        health_hud_magic_acquire((unsigned short)amount);
        return 1;
    }
    if (type == OOT_CORE_DEFENSE_ACQUIRE) {
        save_state.source_double_defense = 1;
        return 1;
    }
    if (type == OOT_CORE_MAGIC_FILL) {
        save_state.source_magic = (uint8_t)(save_state.source_magic_level >= 2 ? 96 :
                                            save_state.source_magic_level ? 48 : 0);
        return 1;
    }
    if (!save_state.source_magic_level) return 0;
    if (type == 5) {                                   /* MAGIC_ADD */
        unsigned int cap = save_state.source_magic_level >= 2 ? 96 : 48;
        unsigned int v = save_state.source_magic + (unsigned int)amount;
        save_state.source_magic = (uint8_t)(v > cap ? cap : v);
        return 1;
    }
    if (!health_hud_magic_idle() || !health_hud_magic_available((unsigned)amount)) {
        host_sfx(0x4806, 0, 0, 0);                     /* NA_SE_SY_ERROR */
        return 0;
    }
    return health_hud_magic_consume((unsigned)amount);
}

/* Inventory_UpdateBottleItem / Inventory_ConsumeFairy on the C bottles. */
static int host_bottle_update(unsigned char item, unsigned char button)
{
    unsigned int i;
    if (button == 0xFF) {                              /* consume a fairy */
        for (i = 0; i < 4; ++i)
            if (save_state.bottle_items[i] == 0x18) {  /* ITEM_BOTTLE_FAIRY */
                save_state.bottle_items[i] = 0x14;     /* ITEM_BOTTLE_EMPTY */
                return 1;
            }
        return 0;
    }
    if (button >= 1 && button <= 3) {
        unsigned int slot = save_c_item_inventory_slot(save_state.c_items[button < 3 ? 2 - button : 2]);
        if (slot >= 18 && slot <= 21) {               /* SLOT_BOTTLE_1..4 */
            if (save_state.bottle_items[slot - 18] == 0x1A && item == 0x14)
                item = 0x1F;                           /* milk full -> half */
            save_state.bottle_items[slot - 18] = item;
            return 1;
        }
    }
    return 0;
}

static void host_fatal(unsigned int code, unsigned int a, unsigned int b)
{
#ifdef OOT_CORE_ASYNC
    if (ASYNC_BUSY()) {   /* the slave cannot show an error: the join does */
        volatile unsigned int *f = (volatile unsigned int *)((uintptr_t)deferred_fatal | 0x20000000u);
        if (!f[0]) { f[1] = code; f[2] = a; f[3] = b; f[0] = 1; }
        return;
    }
#endif
    jo_core_error("oot-core fatal %08X %X %X", code, a, b);
}
#endif

static int host_scene_file(const char* name, void* data, unsigned int bytes)
{
    jo_file file;
    int length, got;
#ifdef OOT_CORE_ASYNC
    if (ASYNC_BUSY()) { host_fatal(0xA5F11E00u, 0, 0); return -1; }  /* no CD from the slave */
#endif
    if (GFS_NameToId((Sint8*)name) < 0) return 0;
    if (!jo_fs_open(&file, name)) return -1;
    length = file.size;
    if (!data) { jo_fs_close(&file); return length; }
    if (bytes > (unsigned int)length) { jo_fs_close(&file); return -1; }
    got = jo_fs_read_next_bytes(&file, data, bytes);
    jo_fs_close(&file);
    slCashPurge();
    return got;
}

static void* host_sprite_memory(void* memory, unsigned int bytes)
{
#ifdef OOT_CORE_ASYNC
    if (ASYNC_BUSY()) { host_fatal(0xA5A110C0u, 0, 0); return 0; }  /* jo heap is master-only */
#endif
    if (memory) { jo_free(((void**)memory)[-1]); return 0; }
    if (!bytes || bytes>~0u-15u-sizeof(void*)) return 0;
    void* raw=jo_malloc(bytes+15u+sizeof(void*));
    memory=raw ? (void*)(((uintptr_t)raw+sizeof(void*)+15u)&~(uintptr_t)15u) : 0;
    if (memory) ((void**)memory)[-1]=raw;
    if (memory && jo_memory_usage_percent()>CORE_SPRITE_HEAP_PERCENT) {
        jo_free(raw); return 0;
    }
    return memory;
}

static void host_audio_request(unsigned int command, unsigned int argument)
{
    unsigned int n = CORE_DRAW->audio_count;
    unsigned int request = (command << 16) | (argument & 0xffffu);
    /* Volume updates are a latest-value control, including when a CD cue
     * defers a bank change. Never fill the queue with the same fade target. */
    if (command == OOT_CORE_AUDIO_MAIN_VOLUME || command == OOT_CORE_AUDIO_SINGING ||
        command == OOT_CORE_AUDIO_SPATIAL) {
        unsigned int i;
        for (i = n; i; --i) {
            if ((CORE_DRAW->audio_queue[i - 1] >> 16) == command) {
                CORE_DRAW->audio_queue[i - 1] = request;
                return;
            }
        }
    }
    if (n && CORE_DRAW->audio_queue[n - 1] == request) return;
    if (n >= 8) { host_fatal(0x41554451u, command, argument); return; }
    CORE_DRAW->audio_queue[n] = request;
    CORE_DRAW->audio_count = n + 1;
}

/* Hardware and CD reads are master-only. Leave BGM requests queued while a
 * chest or reward owns the drive; consecutive fanfares queue in cdda.c. */
static void host_audio_service(void)
{
    unsigned int done = 0, n = CORE_DRAW->audio_count, i;
    /* Gain touches sound registers only. It remains safe during CD playback
     * and cannot sit behind a deferred file request for the whole cue. */
    for (i = 0; i < n; ++i) {
        unsigned int request = CORE_DRAW->audio_queue[i];
        if ((request >> 16) == OOT_CORE_AUDIO_MAIN_VOLUME)
            music_source_volume(request & 0x7f, (request & 0xffffu) >> 8);
        else if((request >> 16) == OOT_CORE_AUDIO_SINGING)
            music_source_singing(request & 0x7f,(request >> 8)&0x7f,(request & 0x8000)!=0);
        else if((request >> 16) == OOT_CORE_AUDIO_SPATIAL)
            music_source_spatial(request & 0x7f,(request >> 8)&0x7f);
        else if(((request >> 16)&0xffu) == OOT_CORE_AUDIO_SFX_PITCH)
            action_audio_decomp_sfx_pitch(request&0xffffu,request>>24);
        else CORE_DRAW->audio_queue[done++] = request;
    }
    n = done; done = 0;
    while (done < n) {
        unsigned int request = CORE_DRAW->audio_queue[done];
        unsigned int command = request >> 16, argument = request & 0xffffu;
        if (command == OOT_CORE_AUDIO_FANFARE) {
            /* CD routes can enqueue behind another cue. A source fanfare
             * without a CD route uses its bounded SCSP bank once, then
             * restores the previous theme with its tables still pinned. */
            if (music_song_routed((oot_song_t)argument)) music_play((oot_song_t)argument);
            else {
                if (cdda_busy() || music_busy() || music_fanfare_busy()) break;
                if (!music_area_fanfare(argument)) host_fatal(0x41554446u, argument, 0);
            }
        }
        else {
            if (cdda_busy() || music_fanfare_busy()) break;
            if (command == OOT_CORE_AUDIO_SEQUENCE || command == OOT_CORE_AUDIO_PUSH_SEQUENCE) {
                if (music_busy()) break;
                if (command == OOT_CORE_AUDIO_PUSH_SEQUENCE) {
                    CORE_DRAW->resume_sequence=music_area_current_sequence();
                    CORE_DRAW->resume_bank=CORE_DRAW->resume_sequence==0xffffu ? music_current() : 0;
                }
                music_source_tempo(256);
                if(argument==NA_BGM_NATURE_AMBIENCE)music_silence(0);
                else if (!music_play((oot_song_t)argument)) music_area_play(argument, 0);
                CORE_DRAW->source_sequence=argument;
            } else if (command == OOT_CORE_AUDIO_STOP) {
                if (music_busy()) break;
                music_silence(0);
            } else if (command == OOT_CORE_AUDIO_POP_SEQUENCE) {
                if (music_busy()) break;
                music_source_tempo(256);
                if (CORE_DRAW->resume_bank) music_fade_to(CORE_DRAW->resume_bank,0);
                else if(CORE_DRAW->resume_sequence!=0xffffu) music_area_play(CORE_DRAW->resume_sequence,0);
                CORE_DRAW->source_sequence=CORE_DRAW->resume_sequence;
                CORE_DRAW->resume_bank=0;CORE_DRAW->resume_sequence=0xffffu;
            } else if (command == OOT_CORE_AUDIO_TEMPO) {
                music_source_tempo(argument);
            } else if (command == OOT_CORE_AUDIO_MINIGAME_TEMPO) {
                if(CORE_DRAW->source_sequence==NA_BGM_TIMED_MINI_GAME) music_source_tempo(210*256/185);
            }
        }
        ++done;
    }
    for (i = done; i < n; ++i) CORE_DRAW->audio_queue[i - done] = CORE_DRAW->audio_queue[i];
    CORE_DRAW->audio_count = n - done;
}

static const OotCoreHost host = { host_sfx, host_give_item, host_health_change,
                                  host_ticks, frame_timer_ticks_to_us, host_rupees_change,
                                  host_player_combat, host_player_hit, host_scene_file, host_sprite_memory,
#ifdef PLAYER_SOURCE
                                  host_ammo_change, host_magic_request, host_bottle_update, host_fatal
#else
                                  0, 0, 0, 0
#endif
    , host_audio_request
};
static bool source_owl;
bool oot_core_owns_owl(void) { return source_owl; }

static OotCoreBench bench;
/* Last decomp update (Actor_UpdateAll etc.), microseconds. */
static unsigned int update_us;
static bool loaded;
static bool playing;
static bool scene_load_failed;
static unsigned int core_image_crc;
/* Scene index the play state belongs to (or whose blob is missing/failed):
** a failed scene is not retried every frame. */
static unsigned int play_scene = 0xFFFFu;
static unsigned int step_phase;
#ifdef OOT_CORE_ASYNC
static unsigned int core_due;        /* updates owed since the last kick */
#endif
static int meshes_room = -1; /* assets follow Actor_UpdateAll's deferred room spawn */

/* Read a disc file into a cache-through cart carve: zero the carve first
** (.bss is not in the file), refuse a file larger than the carve. Returns
** the file length, 0 on failure. GFS_NameToId first: a missing file is
** fatal inside jo_fs. */
static int load_carve(const char *name, unsigned int offset, unsigned int bytes)
{
    unsigned char *carve = (unsigned char *)ram_cart_fixed(offset, bytes);
    jo_file probe;
    int length;
    unsigned int i;
    if (!carve || GFS_NameToId((Sint8 *)name) < 0 || !jo_fs_open(&probe, name)) return 0;
    length = probe.size;
    jo_fs_close(&probe);
    if (length <= 0 || length > (int)bytes) return 0;
    for (i = 0; i < bytes; ++i) carve[i] = 0;
    return jo_fs_read_file_ptr(name, carve, &length) != JO_NULL ? length : 0;
}

bool oot_core_boot(void)
{
    core_draw_init(); /* Low RAM retains arbitrary bytes across boots. */
    /* Boot progress on row 20: a hang leaves the last marker on screen. */
    jo_printf(0, 20, "oc 1 load ");
    int core_file_bytes = load_carve("OOTCORE.BIN", RAM_CART_OOTCORE_OFFSET, RAM_CART_OOTCORE_BYTES);
    loaded = core_file_bytes != 0;
    /* Code and data are used through the cached aliases: drop stale lines. */
    slCashPurge();
    {
        /* Which check failed, for the boot line: f file, m magic, v version,
         * e blob end past the carve, p play block too big. */
        char why = !loaded ? 'f' : ENTRY->magic != OOT_CORE_MAGIC ? 'm' :
                   ENTRY->version != OOT_CORE_VERSION ? 'v' :
                   (unsigned int)ENTRY->end > OOT_CORE_LOAD_ADDR + RAM_CART_OOTCORE_BYTES ? 'e' :
                   ENTRY->play_bytes() > RAM_LOW_OOTPLAY_BYTES ? 'p' : 0;
        if (why) {
            jo_printf(0, 20, "oc load failed %c %x", why,
                      why == 'v' ? ENTRY->version : why == 'p' ? ENTRY->play_bytes() :
                      why == 'e' ? (unsigned int)ENTRY->end : 0u);
            loaded = false;
            return false;
        }
    }
    jo_printf(0, 20, "oc 2 init  ");
    core_image_crc = OotActorPack_Crc((const void*)OOT_CORE_LOAD_ADDR, core_file_bytes, 0);
    /* oot-core.ld .lowbss lives in Low RAM, which boot does not clear. */
    memset(RAM_LOW(RAM_LOW_OOTCORE_BSS_OFFSET), 0, RAM_LOW_OOTCORE_BSS_BYTES);
    ENTRY->init(&host);
#ifdef CORE_COLLISION
    /* One collision world: C bg_* queries answer from the core's z_bgcheck;
     * its Actor_UpdateAll owns the DynaPoly frame boundary. */
    bg_core_shim_set_api(ENTRY->bg_api());
    bg_core_shim_frame_owner(true);
#endif
    {
        /* ROM message text (NESMSG.BIN): z_message DMAs from it. */
        int bytes = load_carve("NESMSG.BIN", RAM_CART_MSGDATA_OFFSET, RAM_CART_MSGDATA_BYTES);
        if (bytes) ENTRY->set_text(ram_cart_fixed(RAM_CART_MSGDATA_OFFSET, RAM_CART_MSGDATA_BYTES),
                                   (unsigned int)bytes);
    }
#ifdef PLAYER_SOURCE
    {
        /* Real Player frames (tools/split_player_bank.py): the Saturn C
         * cutscene clips stay resident from boot. The common set loads at the
         * first scene load; demand groups per scene/pause. */
        static void *bank;
        int bytes = 0;
        jo_printf(0, 20, "oc 3 anim  ");
        if (!bank) bank = jo_fs_read_file("PLAYC.PFB", &bytes);
        if (!bank || !ENTRY->player_bank || !ENTRY->player_bank(bank, (unsigned int)bytes)) {
            jo_core_error("Player animation bank failed (%d bytes)", bytes);
            loaded = false;
            return false;
        }
    }
#endif
    jo_printf(0, 20, "oc 3 bench ");
    ENTRY->bench(&bench, frame_timer_ticks, frame_timer_ticks_to_us);
    jo_printf(0, 20, "                    ");
    return true;
}

/* A copied view is retained in the existing Low-RAM draw carve. Drawing and
 * projection never enter the live core while the slave is updating it. */
const OotCoreCutsceneCameraView* oot_core_cutscene_camera(void)
{
    return playing ? &CORE_DRAW->cutscene_camera : 0;
}

const OotCoreShopView* oot_core_shop_view(void)
{
    return playing ? &CORE_DRAW->shop : 0;
}

int oot_core_cutscene_screen_distance(void)
{
    return playing && CORE_DRAW->cutscene_camera.active ? CORE_DRAW->cutscene_distance : 0;
}

static void read_cutscene_camera(void)
{
    int fov, sine, cosine;
    ENTRY->cutscene_camera(&CORE_DRAW->cutscene_camera);
    ENTRY->shop_view(&CORE_DRAW->shop);
    ENTRY->timer_view(&CORE_DRAW->timer);
    if (!CORE_DRAW->cutscene_camera.active) { CORE_DRAW->cutscene_distance = 0; return; }
    fov = CORE_DRAW->cutscene_camera.fov_q8;
    if (fov < 10 * 256) fov = 10 * 256;
    if (fov > 170 * 256) fov = 170 * 256;
    /* Source vertical FOV: 120 / tan(fov / 2), in logical 240-line pixels. */
    kokiri_camera_sincos((uint16_t)(fov * 16 / 45), &sine, &cosine);
    CORE_DRAW->cutscene_distance = 120 * cosine / sine;
}

static void seed_cutscene_camera(void)
{
    OotCoreCutsceneCameraView view = {0};
    int sine, cosine, horizontal, distance = recomp_screen_distance();
    view.eye[0] = recomp_camera.x;view.eye[1] = recomp_camera.y;view.eye[2] = recomp_camera.z;
    kokiri_camera_sincos((uint16_t)recomp_pitch, &sine, &cosine);
    horizontal = cosine * 200 / 65536;
    view.at[1] = view.eye[1] - sine * 200 / 65536;
    kokiri_camera_sincos(recomp_yaw, &sine, &cosine);
    view.at[0] = view.eye[0] + sine * horizontal / 65536;
    view.at[2] = view.eye[2] + cosine * horizontal / 65536;
    view.fov_q8 = (unsigned)collide_heading(120, distance) * 720 / 256;
    ENTRY->camera_seed(&view);
}

void oot_core_cutscene_camera_apply(void)
{
    const OotCoreCutsceneCameraView* view = oot_core_cutscene_camera();
    int dx, dy, dz;
    if (!view || !view->active) return;
    recomp_camera.x = view->eye[0];
    recomp_camera.y = view->eye[1];
    recomp_camera.z = view->eye[2];
    dx = view->at[0] - view->eye[0];
    dy = view->at[1] - view->eye[1];
    dz = view->at[2] - view->eye[2];
    /* Whole-scene tracks can span more than sqrt(INT_MAX) world units. */
    while (dx < -16383 || dx > 16383 || dy < -16383 || dy > 16383 || dz < -16383 || dz > 16383) {
        dx /= 2; dy /= 2; dz /= 2;
    }
    recomp_yaw = collide_heading(dx, dz);
    recomp_pitch = -(int16_t)collide_heading(dy, collide_isqrt((uint32_t)(dx * dx + dz * dz)));
}

void oot_core_cutscene_letterbox_draw(void)
{
    static POLYGON polys[2] = {
        {{0,0,65536},{0,1,2,3}}, {{0,0,65536},{4,5,6,7}}
    };
    static ATTR attrs[2] = {
        ATTRIBUTE(Dual_Plane,SORT_CEN,0,C_RGB(0,0,0),No_Gouraud,ECdis|SPdis,sprPolygon,No_Option),
        ATTRIBUTE(Dual_Plane,SORT_CEN,0,C_RGB(0,0,0),No_Gouraud,ECdis|SPdis,sprPolygon,No_Option)
    };
    const OotCoreCutsceneCameraView* view = oot_core_cutscene_camera();
    int distance, depth, unit, i, size;
    if (!view || !view->letterbox) return;
    size = view->letterbox;
    distance = recomp_screen_distance();
    depth = (distance >> KOKIRI_ZDSP_LEVEL) + 1;
    unit = depth * 65536 / distance;
    /* Persistent points/data in the reserved draw carve: SGL may consume
     * geometry after this function returns. No textures or sprite slots. */
    for (i = 0; i < 8; ++i) {
        int inner = (i & 3) >= 2;
        int y = inner ? 120 - size : 121;
        if (i < 4) y = -y;
        CORE_DRAW->letterbox_points[i][0] = ((i & 3) == 0 || (i & 3) == 3 ? -161 : 161) * unit;
        CORE_DRAW->letterbox_points[i][1] = y * unit * (JO_TV_HEIGHT / 240);
        CORE_DRAW->letterbox_points[i][2] = depth * 65536;
    }
    CORE_DRAW->letterbox_data = (PDATA){ CORE_DRAW->letterbox_points,8,polys,2,attrs };
    slPushMatrix();
    slUnitMatrix(0);
    kokiri_submit_pdata(&CORE_DRAW->letterbox_data);
    slPopMatrix();
}

/* C Link -> player proxy: recomp_link is the eye, OoT pos is the feet.
** World units are OoT units (1:1). */
#ifdef PLAYER_SOURCE
/* Real Player: the core owns Link; the host reads him back once per update. */
OotCorePlayerView oot_core_player;
bool oot_core_player_valid;

/* recomp_link as last read: a later difference is a host move (spawn
** placement, story events, C pushes) that the Player must take. */
static camera_position_t read_link;
static uint16_t read_yaw;

static void read_player(void)
{
    int carry[7];
    read_cutscene_camera();
    int state = ENTRY->tool(OOT_CORE_TOOL_CARRY_READ, carry);
    world_props_core_read(state, carry);
    oot_core_player_valid = ENTRY->player_view(&oot_core_player) != 0;
    if (!oot_core_player_valid) return;
    recomp_link.x = oot_core_player.x;
    recomp_link.y = oot_core_player.y + RECOMP_LINK_EYE_HEIGHT;
    recomp_link.z = oot_core_player.z;
    recomp_link_yaw = (uint16_t)oot_core_player.yaw;
    read_link = recomp_link;
    read_yaw = recomp_link_yaw;
}

static void push_host_moves(void)
{
    if (!oot_core_player_valid || !ENTRY->player_warp) return;
    if (recomp_link.x == read_link.x && recomp_link.y == read_link.y &&
        recomp_link.z == read_link.z && recomp_link_yaw == read_yaw) return;
    ENTRY->player_warp(recomp_link.x, recomp_link.y - RECOMP_LINK_EYE_HEIGHT, recomp_link.z,
                       (short)recomp_link_yaw);
    read_link = recomp_link;
    read_yaw = recomp_link_yaw;
}

unsigned int oot_core_player_draw_us(void)
{
    return oot_core_player_valid ? oot_core_player.draw_us : 0;
}

void oot_core_player_resync(void)
{
    if (playing) read_player();
}

int oot_core_player_room_request(void)
{
    return oot_core_player_valid ? oot_core_player.room_request : -1;
}

void oot_core_player_damage(int damage)
{
    if (playing && ENTRY->player_damage) ENTRY->player_damage(damage);
}

bool oot_core_player_jump(void)
{
    return playing && ENTRY->player_jump && ENTRY->player_jump();
}

unsigned int oot_core_player_do_action(void)
{
    return oot_core_player_valid ? oot_core_player.do_action : OOT_CORE_DO_NONE;
}

void oot_core_carry_cancel(void)
{
    if (playing) ENTRY->tool(OOT_CORE_TOOL_CARRY_CANCEL, 0);
}
#endif

static void sync_player(void)
{
#ifdef PLAYER_SOURCE
    push_host_moves();
    {
        int carry[7];
        world_props_core_offer(carry);
        ENTRY->tool(OOT_CORE_TOOL_CARRY_OFFER, carry);
    }
    return;
#endif
    ENTRY->set_player(recomp_link.x, recomp_link.y - RECOMP_LINK_EYE_HEIGHT, recomp_link.z,
                      (short)recomp_link_yaw);
}

/* C save -> decomp mirror. Static: the blob keeps the pointer and copies
** flags back after each update. */
static unsigned short core_skybox_time;
static unsigned char core_skybox_reset = 2;
unsigned int oot_core_skybox_time(void) { return core_skybox_time; }
void oot_core_clock_reset(unsigned int skybox_time)
{
    /* Deferred until set_save: frontend choices may precede the first play. */
    core_skybox_time = (unsigned short)skybox_time;
    core_skybox_reset = 1;
}
#ifdef PLAYER_SOURCE
static void player_resident_release(void);
#endif
void oot_core_session_reset(unsigned int skybox_time)
{
    /* File/level select already installed the next C save. Detach the old
     * mirror before its actor destructors run, so cleanup cannot stamp old
     * scene words, inventory or clock into the newly selected file. */
    if (loaded) ENTRY->set_save(NULL);
    oot_core_scene_unload();
#ifdef PLAYER_SOURCE
    player_resident_release();   /* the next opening needs the room */
#endif
    oot_core_clock_reset(skybox_time);
    core_skybox_reset = 2;
}

static void mirror_save(void)
{
    {
        /* Static: the blob keeps the pointer and copies flags back after update. */
        static OotCoreSave mirror;
        unsigned int save_scene = scene_flow_entry()->save_scene;
        mirror.link_age = save_state.link_age;
        mirror.day_time = save_state.day_time;
        mirror.day_time_out = &save_state.day_time;
        mirror.skybox_time_out = &core_skybox_time;
        mirror.total_days = (unsigned int*)&save_state.total_days;
        mirror.bgs_day_count = (unsigned int*)&save_state.bgs_day_count;
        mirror.ocarina_game_round = &save_state.ocarina_game_round;
        mirror.entrance_index = save_state.source_entrance;
        mirror.skybox_time = core_skybox_time;
        mirror.reset_skybox_time = core_skybox_reset;
        mirror.time_blocked = gameplay_blocks_world() || gameplay.dead;
        /* Native dialogue/boss cinematics do not set the proxy Link's source
         * cs flags. Suppress only the hatch textbox while they own Link. */
        mirror.player_cutscene = game_mode() == GAME_MODE_CUTSCENE || gameplay.dead ||
            (mirror.time_blocked && !gameplay.paused);
        /* Play_Init: night outside 06:30..18:00, exact source boundaries. */
        mirror.night = mirror.day_time > 0xC000 || mirror.day_time < 0x4555;
        mirror.cutscene_index = save_state.cutscene_index;
        mirror.cutscene_index_out = &save_state.cutscene_index;
        mirror.skull_flags = save_state.skull_flags;
        mirror.skull_tokens_out = &save_state.source_tokens;
        mirror.event_chk_inf = save_state.event_chk_inf;
        mirror.item_get_inf = save_state.item_get_inf;
        mirror.inf_table = save_state.inf_table;
        mirror.scene_flags = save_scene < SAVE_SCENE_COUNT
            ? (unsigned long *)&save_state.scene[save_scene]
            : scene_flow_entry()->oot_scene < SAVE_SOURCE_SCENE_COUNT
                ? (unsigned long *)&save_state.generic_scene[scene_flow_entry()->oot_scene] : 0;
        mirror.health = save_state.health;
        mirror.health_capacity = save_state.health_capacity;
        mirror.rupees = save_state.rupees;
        mirror.stick_owned = save_state.stick_owned;
        mirror.stick_ammo = save_state.stick_ammo;
        mirror.nut_owned = save_state.nut_owned;
        mirror.nut_ammo = save_state.nut_ammo;
        mirror.slingshot_owned = save_state.slingshot;
        mirror.seed_ammo = save_state.ammo_seeds;
        mirror.owned_sword = save_state.owned_sword;
        mirror.owned_shield = save_state.owned_shield;
        mirror.equip_sword = save_state.equip_sword;
        mirror.equip_shield = save_state.equip_shield;
        mirror.fairy_ocarina = save_state.fairy_ocarina;
        mirror.stick_upgrade = save_state.stick_upgrade;
        mirror.nut_upgrade = save_state.nut_upgrade;
        mirror.deku_dungeon_items = save_state.deku_dungeon_items;
        mirror.skull_tokens = (unsigned short)save_skull_count();
        if (mirror.skull_tokens < save_state.source_tokens) mirror.skull_tokens = save_state.source_tokens;
        mirror.quest_items = (unsigned int *)&save_state.quest_items;
        mirror.dungeon_items = save_state.dungeon_items;
        mirror.dungeon_keys = (signed char *)save_state.dungeon_keys;
        mirror.bottle_items = save_state.bottle_items;
        mirror.inventory_items = save_state.source_items;
        mirror.inventory_ammo = save_state.source_ammo;
        mirror.inventory_equipment = save_state.source_equipment;
        mirror.inventory_upgrades = save_state.source_upgrades;
        mirror.magic_level = save_state.source_magic_level;
        mirror.magic = save_state.source_magic;
        mirror.double_defense = save_state.source_double_defense;
        mirror.boots = save_state.boots;
        {
            /* C 0 green, 1 blue, 2 red -> PLAYER_TUNIC_KOKIRI/ZORA/GORON. */
            static const unsigned char tunic[3] = { 0, 2, 1 };
            unsigned int i;
            mirror.tunic = tunic[save_state.tunic < 3 ? save_state.tunic : 0];
            for (i = 0; i < 3; ++i) {
                unsigned int slot = save_c_item_inventory_slot(save_state.c_items[i]);
                mirror.c_slots[i] = slot < 24 && save_inventory_slot_usable(slot) ? (unsigned char)slot : 0xFF;
            }
        }
        memcpy(mirror.player_name, "Link    ", 8); /* no file name in the C save */
        mirror.generic_scene = save_scene >= SAVE_SCENE_COUNT;
        ENTRY->set_save(&mirror);
        core_skybox_reset = 0;
    }
}

/* <scene>.OOC (asset_scene_name, like the room banks) into the scene carve,
** then each data object it lists (O<id>.OOB) packed after it. Objects are
** used through the cached alias like the blob. */
static const void *const *scene_objects;
static unsigned int scene_object_count;

static bool load_scene_blob(unsigned int scene)
{
    char name[12];
    int result;
    if (!asset_scene_name(name, scene, -1, "OOC")) return false;
    result = ENTRY->scene_load(scene, name, core_image_crc, &scene_objects, &scene_object_count);
    scene_load_failed = result < 0;
    return result > 0;
}
/* ---- Phase 2 draw shim: prebuilt meshes for the decomp's draw items ---- */

static void sprites_reset(void)
{
    unsigned int r;
    for (r = 0; r < CORE_SPRITE_ROWS; ++r) {
        if (core_sprite[r]) host_sprite_memory(core_sprite[r],0);
        core_sprite[r] = 0;
        core_sprite_tried[r] = 0;
    }
    core_sprite_reserved = 0;
    memset(&sprite_stats, 0, sizeof sprite_stats);
}

/* The destination layer's OOC objects cover every room of that layer,
 * including the current NPC recipes. All clips load before actors run;
 * same-room spawns never read the disc. */
static bool sprites_preload(const OotSceneBlob *blob, unsigned int layer)
{
    unsigned int count=ENTRY->sprite_preload(blob,core_sprite_rows,CORE_SPRITE_ROWS,
                                            core_sprite,&sprite_stats.missing,layer);
    core_sprite_reserved=count ? CORE_SPRITE_SLOTS : 0;
    return sprite_stats.missing==0;
}

static const unsigned char *sprites_clip(const OotCoreNpcView *view)
{
    unsigned int r;
    for (r=0;r<CORE_SPRITE_ROWS;++r)
        if (core_sprite_rows[r].object==view->object &&
            core_sprite_rows[r].skeleton==(view->skeleton&0xffffffu))
            return npc_sprite_archive_clip(core_sprite[r],view->anim);
    return 0;
}

/* Read-only diagnostics. No loading, fallback clip, slot growth or bank reset. */
static bool sprites_refresh(void)
{
    const OotCoreNpcView *v;
    int n=ENTRY->npc_view(&v), k;
    sprite_stats.actors = sprite_stats.missing = sprite_stats.fallback = 0;
    for (k = 0; k < n; ++k) {
        if (!v[k].object) continue; /* native C-owned views have no sprite package */
        ++sprite_stats.actors;
        if (!sprites_clip(&v[k])) ++sprite_stats.missing;
    }
    return false;
}

/* ---- Link's tools: decomp item actors (bridge_items.cpp), baked ITM*.SPR ----
** Sheets load for owned, age-usable tools when a room's assets load and stay
** until the scene changes; a missing or unaffordable sheet only hides that
** tool (the actor still plays). Pitch sheets keep 5 elevation bands as poses
** (tools/build_item_sprites.py). */
/* Decomp DynaPoly actors (Bg_Spot01_Objects2 buildings...) -> C bg_dyna, so
** C Link collides with the same source mesh. Converted once per actor into
** the cart heap; transform refreshed after every decomp update. Normals are
** the source's n / 32767 halved to Q14, as build_kokiri_scene does offline. */
#ifndef CORE_COLLISION
static void core_dyna_drop(core_dyna_t *d, bool remove)
{
    if (remove && d->id != BG_NONE) bg_dyna_remove(d->id);
    if (d->tri) jo_free(d->tri);
    memset(d, 0, sizeof(*d));
}

static void core_dyna_reset(void)
{
    unsigned int i;
    /* Frontend teardown can precede collision_load: detach each registration
     * before freeing its triangle storage. Removing an already-cleared id is safe. */
    for (i = 0; i < OOT_CORE_DYNA_VIEWS_MAX; ++i) if (core_dyna[i].key) core_dyna_drop(&core_dyna[i], true);
}

static int16_t q15_to_q14(int16_t n) { return (int16_t)(n >= 0 ? (n + 1) >> 1 : -((-n + 1) >> 1)); }

static bool core_dyna_add(core_dyna_t *d, const OotCoreDynaView *v)
{
    unsigned int i, k, j, surfaces = 0, bytes = v->num_polys * (sizeof(collision_triangle_t) + 2u);
    uint16_t *info;
    d->tri = (collision_triangle_t *)jo_malloc(bytes);
    if (!d->tri) return false;
    info = (uint16_t *)(d->tri + v->num_polys);
    for (i = 0; i < v->num_polys; ++i) {
        const unsigned short *p = v->polys + i * 8u;
        unsigned int idx[3] = { p[1] & 0x1FFFu, p[2] & 0x1FFFu, p[3] };
        collision_triangle_t *c = &d->tri[i];
        for (k = 0; k < 3; ++k) {
            const short *q = v->vertices + (idx[k] < v->num_vertices ? idx[k] : 0) * 3u;
            for (j = 0; j < 3; ++j) {
                c->vertex[k][j] = q[j];
                if (!k || q[j] < c->minimum[j]) c->minimum[j] = q[j];
                if (!k || q[j] > c->maximum[j]) c->maximum[j] = q[j];
            }
        }
        for (j = 0; j < 3; ++j) c->normal[j] = q15_to_q14((int16_t)p[4 + j]);
        info[i] = (uint16_t)((p[0] & 0xFFu) | ((p[1] >> 13) << 8) | (((p[2] >> 13) & 1u) << 11));
        if ((p[0] & 0xFFu) + 1u > surfaces) surfaces = (p[0] & 0xFFu) + 1u;
    }
    memset(&d->mesh, 0, sizeof(d->mesh));
    d->mesh.triangles = d->tri;
    d->mesh.triangle_count = v->num_polys;
    d->mesh.info = info;
    d->mesh.surfaces = v->surfaces;
    d->mesh.surface_count = v->surfaces ? surfaces : 0;
    d->id = bg_dyna_register(&d->mesh, v->transform & (BG_DYNA_POS | BG_DYNA_ROT_Y));
    if (d->id == BG_NONE) { jo_free(d->tri); d->tri = 0; return false; }
    d->key = v->key;
    return true;
}

static void core_dyna_sync(void)
{
    const OotCoreDynaView *v;
    int n = ENTRY->dyna_view(&v), i;
    unsigned int s;
    for (s = 0; s < OOT_CORE_DYNA_VIEWS_MAX; ++s) {
        if (!core_dyna[s].key) continue;
        for (i = 0; i < n && v[i].key != core_dyna[s].key; ++i) {}
        if (i == n) core_dyna_drop(&core_dyna[s], true);       /* actor gone */
    }
    for (i = 0; i < n; ++i) {
        core_dyna_t *d = 0, *free_slot = 0;
        for (s = 0; s < OOT_CORE_DYNA_VIEWS_MAX; ++s) {
            if (core_dyna[s].key == v[i].key) d = &core_dyna[s];
            else if (!core_dyna[s].key && !free_slot) free_slot = &core_dyna[s];
        }
        if (!d) {
            if (!free_slot || !v[i].num_polys || !core_dyna_add(free_slot, &v[i])) continue;
            d = free_slot;
        }
        {
            bg_vec_t pos = { v[i].x, v[i].y, v[i].z };
            bg_dyna_set(d->id, &pos, v[i].rot_y, v[i].scale_q16);
            bg_dyna_enable(d->id, v[i].enabled != 0);
        }
    }
}

#endif

static void tools_free(void)
{
    unsigned int i;
    for (i = 0; i < TOOL_COUNT; ++i) {
        if (CORE_DRAW->tool_sheet[i]) jo_free(CORE_DRAW->tool_sheet[i]);
        CORE_DRAW->tool_sheet[i] = 0;
        CORE_DRAW->tool_tried[i] = 0;
    }
    CORE_DRAW->tool_bits = 0;
}

static void tools_load(void)
{
    static const char names[TOOL_COUNT][11] = { "ITMARW.SPR", "ITMBOM.SPR", "ITMCHU.SPR", "ITMBOO.SPR",
        "ITMHKT.SPR", "ITMHKC.SPR", "ITMBGS.SPR", "ITMMIR.SPR", "ITMIRB.SPR", "ITMHOB.SPR", "ITMEXP.SPR", "ITMAIM.SPR", "ITMMAG.SPR" };
    bool adult = !save_state.link_age;
    unsigned int i;
    bool bomb = save_inventory_item(2) != 0xff, chu = save_inventory_item(8) != 0xff;
    bool hook = adult && save_inventory_item(9) != 0xff;
    bool need[TOOL_COUNT] = {
        adult && save_inventory_item(3) != 0xff, bomb, chu, !adult && save_inventory_item(12) != 0xff,
        hook, hook, false, false, false, false, bomb || chu, false, /* no first-person overlay */
        adult && (save_inventory_item(4) != 0xff || save_inventory_item(10) != 0xff ||
                  save_inventory_item(16) != 0xff) };
    for (i = 0; i < TOOL_COUNT; ++i) {
        unsigned char **sheet = &CORE_DRAW->tool_sheet[i];
        if (!need[i] || *sheet || CORE_DRAW->tool_tried[i] || GFS_NameToId((Sint8 *)names[i]) < 0) continue;
        CORE_DRAW->tool_tried[i] = 1;
        *sheet = npc_sprite_load(names[i]);
        if (*sheet && jo_memory_usage_percent() > CORE_SPRITE_HEAP_PERCENT) { jo_free(*sheet); *sheet = 0; }
    }
}

static unsigned int pitch_band(int pitch)
{
    int band = (pitch + 0x5000) / 0x2000;
    return band < 0 ? 0 : band > 4 ? 4 : (unsigned int)band;
}

static void __attribute__((noinline)) tool_put(unsigned int t, unsigned int frame, int x, int y, int z, uint16_t yaw)
{
    if (CORE_DRAW->tool_sheet[t])
        npc_sprite_draw(CORE_DRAW->tool_sheet[t], &CORE_DRAW->tool_inst[t], frame, x, y, z, yaw);
}

/* Arrow*_Draw's hit screen fill: the core writes a VDP2 colour offset per
 * channel into tool_pull[3..5] with each source-frame tool state. */
bool oot_core_hit_tint(int16_t rgb[3])
{
    rgb[0] = (int16_t)CORE_DRAW->tool_pull[3];
    rgb[1] = (int16_t)CORE_DRAW->tool_pull[4];
    rgb[2] = (int16_t)CORE_DRAW->tool_pull[5];
    return playing && (rgb[0] || rgb[1] || rgb[2]);
}

static void tools_draw(void)
{
    const OotCoreToolView *v;
    int n, i;
    int32_t a[3], b[3];
#ifdef OOT_CORE_ASYNC
    if (ASYNC_BUSY()) { v = snap_tools; n = playing ? snap_tools_n : 0; }
    else
#endif
    n = playing ? ENTRY->tool_view(&v) : 0;
    npc_sprite_shadow_off = 1;
    for (i = 0; i < n; ++i) {
        unsigned int band = pitch_band(v[i].pitch);
        switch (v[i].id) {
        case ACTOR_EN_ARROW: {
            /* EnArrow_Draw's EffectBlure tail, reduced: three trailing cels
             * every 16 units back along the last core step while in flight. */
            int k, dx = v[i].x - v[i].previous_x, dy = v[i].y - v[i].previous_y,
                dz = v[i].z - v[i].previous_z, len = abs(dx) + abs(dy) + abs(dz);
            /* The nocked world sprite fills the near camera. Hide only that
             * presentation; the source actor still owns release and flight. */
            if (v[i].held && recomp_first_person()) break;
            if (v[i].params == 9) { kokiri_seed_draw(v[i].x, v[i].y, v[i].z); break; } /* ARROW_SEED */
            tool_put(TOOL_ARW, band, v[i].x, v[i].y, v[i].z, v[i].yaw);
            if (!v[i].dmg || v[i].held || len < 16) break;
            for (k = 1; k <= 3 && 16 * k < len; ++k)
                tool_put(TOOL_ARW, band, v[i].x - dx * 16 * k / len, v[i].y - dy * 16 * k / len,
                         v[i].z - dz * 16 * k / len, v[i].yaw);
            break;
        }
        case ACTOR_EN_BOM:
            if (v[i].params) tool_put(TOOL_EXP, recomp_world_clock() / 2, v[i].x, v[i].y, v[i].z, 0);
            else { npc_sprite_shadow_off = v[i].held; tool_put(TOOL_BOM, 0, v[i].x, v[i].y, v[i].z, v[i].yaw);
                   npc_sprite_shadow_off = 1; }
            break;
        case ACTOR_EN_BOM_CHU: tool_put(TOOL_CHU, 0, v[i].x, v[i].y, v[i].z, v[i].yaw); break;
        case ACTOR_ARROW_FIRE: case ACTOR_ARROW_FIRE + 1: case ACTOR_ARROW_LIGHT: {
            /* ITMMAG pose element*4: glow in flight; Arrow*_Hit's 32-step
             * timer grows the burst; alpha is 0 below 8 and when faded. */
            unsigned int t = v[i].timer, frame = !t ? 0 : t >= 24 ? 1 : t >= 16 ? 2 : 3;
            if (v[i].flash < 35 || (t && t < 8)) break;
            tool_put(TOOL_MAG, v[i].params * 4u + frame, v[i].x, v[i].y, v[i].z, 0);
            break;
        }
        case ACTOR_EN_BOOM: tool_put(TOOL_BOO, 2, v[i].x, v[i].y, v[i].z, (uint16_t)(recomp_world_clock() * 0x2000u)); break;
        case ACTOR_ARMS_HOOK: {
            int k, steps;
            tool_put(TOOL_HKT, band, v[i].x, v[i].y, v[i].z, v[i].yaw);
            if (!gameplay_link_point(18, a)) break;
            /* Chain: one baked link every 8 units from the hand, at most 24. */
            steps = (abs(v[i].x - a[0]) + abs(v[i].y - a[1]) + abs(v[i].z - a[2])) / 8;
            if (steps > 24) steps = 24;
            for (k = 1; k < steps; ++k)
                tool_put(TOOL_HKC, band, a[0] + (v[i].x - a[0]) * k / steps, a[1] + (v[i].y - a[1]) * k / steps,
                         a[2] + (v[i].z - a[2]) * k / steps, v[i].yaw);
            break;
        }
        default: break;
        }
    }
    npc_sprite_shadow_off = 0;
}

/* C enemies and props consume source attack flags through their own damage
 * tables. Moving tools sweep the full core step (225 units for an arrow),
 * including host frames on which the 20 Hz core did not advance. */
void oot_core_tool_register(void)
{
    const OotCoreToolView *v;
    int n = playing ? ENTRY->tool_view(&v) : 0, i;
    for (i = 0; i < n; ++i) {
        collider_t *c = &CORE_DRAW->tool_at[i];
        int r = v[i].radius ? v[i].radius : 6;
        if (!v[i].dmg || v[i].held) continue;
        memset(c, 0, sizeof *c);
        c->shape = v[i].id == ACTOR_EN_BOM ? COLSHAPE_CYLINDER : COLSHAPE_CAPSULE;
        c->ax = v[i].previous_x; c->ay = v[i].previous_y; c->az = v[i].previous_z;
        c->bx = v[i].x; c->by = v[i].y; c->bz = v[i].z;
        c->x = v[i].x; c->y = v[i].y - (c->shape == COLSHAPE_CYLINDER ? r : 0); c->z = v[i].z;
        c->radius = (int16_t)r; c->height = (int16_t)(2 * r);
        c->at_type = AT_TYPE_PLAYER;
        c->at_dmg = v[i].dmg;
        c->at_damage = v[i].damage;
        c->ac_flags = COL_OUTSIDE_ACTOR;
        c->tag = 0x7200;
        c->attack_id = v[i].attack_id;
        collide_set_at(c);
    }
}

/* C-button tool use by inventory slot. Until real Player owns the save,
 * commit ammo/magic only after its source actor is admitted. Source
 * func_8083442C falls back to ARROW_NORMAL when magic cannot be consumed. */
bool oot_core_tool_use(unsigned int slot, const int32_t origin[3], uint16_t yaw, int16_t pitch)
{
    /* Slot 6 (slingshot) keeps the legacy owned flag and seed count. */
    unsigned int item = slot == 6 ? (save_state.slingshot && save_state.ammo_seeds ? 6u : 0xffu)
                                  : save_inventory_item(slot), ammo = slot, cost = 0;
    int io[6];
    if (!playing || item == 0xff || !save_inventory_slot_usable(slot) ||
        CORE_DRAW->tool_bits & OOT_CORE_TOOL_HOLDING) return false;
    if (slot == 4 || slot == 10 || slot == 16) {
        ammo = 3;
        cost = slot == 16 ? 8 : 4;
        if (save_inventory_item(3) == 0xff) return false;
        /* func_8083442C: no magic arrow while magicState is busy (the last
         * one's Arrow*_Destroy resets it); a failed request shoots normal. */
        if (!health_hud_magic_idle()) {
            action_audio_decomp_sfx(0x4806); /* NA_SE_SY_ERROR */
            return false;
        }
        if (!health_hud_magic_available(cost)) {
            if (save_state.source_magic_level) action_audio_decomp_sfx(0x4806);
            item = 3; /* ITEM_BOW -> ARROW_NORMAL, retaining the equipped arrow. */
            cost = 0;
        }
    }
    if ((ammo == 2 || ammo == 3 || ammo == 8) && !save_state.source_ammo[ammo]) return false;
    io[0] = (int)item; io[1] = origin[0]; io[2] = origin[1]; io[3] = origin[2];
    io[4] = yaw; io[5] = pitch;
    if (!ENTRY->tool(OOT_CORE_TOOL_USE, io)) return false;
    if (ammo == 2 || ammo == 3 || ammo == 8) --save_state.source_ammo[ammo];
    if (slot == 6) --save_state.ammo_seeds;
    if (cost) health_hud_magic_consume(cost); /* MAGIC_CONSUME_NOW: drains 2/frame */
    if (ammo == 2 || ammo == 8) CORE_DRAW->tool_bits |= OOT_CORE_TOOL_HOLDING;
    return true;
}

bool oot_core_tool_holding(void) { return playing && (CORE_DRAW->tool_bits & OOT_CORE_TOOL_HOLDING); }

bool oot_core_tool_throw(void)
{
    if (!oot_core_tool_holding()) return false;
    CORE_DRAW->tool_bits &= ~OOT_CORE_TOOL_HOLDING;
    return ENTRY->tool(OOT_CORE_TOOL_THROW, CORE_DRAW->tool_pull) != 0;
}

/* Source Actor_UpdatePos scales velocity by R_UPDATE_RATE/2 = 3/2.
 * A 30 Hz host step takes 2/3 of that 20 Hz displacement: exactly velocity. */
bool oot_core_tool_pull(int32_t step_q8[3])
{
    unsigned int k;
    if (!playing || !(CORE_DRAW->tool_bits & OOT_CORE_TOOL_PULLING)) return false;
    for (k = 0; k < 3; ++k) step_q8[k] = CORE_DRAW->tool_pull[k];
    return true;
}

static void meshes_free(void)
{
    unsigned int i;
    for (i = 0; i < core_mesh_count; ++i) {
        actor_mesh_free(core_mesh[i]);
        core_mesh[i] = 0;
        core_mesh_ready[i] = 0;
    }
    core_mesh_count = 0;
}

static void load_meshes(void)
{
    static const char hex[] = "0123456789ABCDEF";
    const OotCoreMeshKey *keys;
    int n = ENTRY->mesh_list(&keys), i;
    if(n<0 || n>CORE_MESHES_MAX){host_fatal(0x4d53484du,n,CORE_MESHES_MAX);return;}
    meshes_free();
    for (i = 0; i < n; ++i) {
        char file[] = "Q00000.MSH";
        const OotCoreMeshKey *k = &keys[i];
        if (k->kind == OOT_CORE_DRAW_KEEP) {
            file[0] = 'K'; file[1] = hex[(k->index >> 8) & 15];
            file[2] = hex[(k->index >> 4) & 15]; file[3] = hex[k->index & 15];
            file[4] = '.'; file[5] = 'M'; file[6] = 'S'; file[7] = 'H'; file[8] = 0;
        } else {
            file[1] = hex[(k->object >> 8) & 15]; file[2] = hex[(k->object >> 4) & 15];
            file[3] = hex[k->object & 15]; file[4] = hex[(k->index >> 4) & 15]; file[5] = hex[k->index & 15];
        }
        if (GFS_NameToId((Sint8 *)file) < 0){host_fatal(0x4d534846u,k->object,k->index);return;}
        core_mesh[core_mesh_count] = actor_mesh_load_static(file);
        if (!core_mesh[core_mesh_count]){host_fatal(0x4d53484cu,k->object,k->index);return;}
        core_mesh_key[core_mesh_count] = *k;
        core_mesh_ready[core_mesh_count] = 0;
        core_mesh_count++;
    }
    sprites_refresh();
    tools_load();
    npc_draw_reupload();
}

/* Required scene meshes must all fit the audited actor bank. */
void oot_core_meshes_upload(void)
{
    unsigned int i;
    for (i = 0; i < core_mesh_count; ++i) {
        core_mesh_ready[i] = playing && actor_mesh_upload(core_mesh[i]);
        if(playing && !core_mesh_ready[i]){
            host_fatal(0x4d534856u,core_mesh_key[i].object,core_mesh_key[i].index);return;
        }
    }
#ifdef CORE_SPRITES
    {   /* slots sized for the scene's biggest cel; draw rebinds per sheet */
        const unsigned char *big = 0;
        unsigned int r, best = 0;
        sprite_stats.slots = 0;
        for (r = 0; r < CORE_SPRITE_ROWS; ++r) {
            const unsigned char *s = npc_sprite_archive_largest(core_sprite[r]);
            unsigned int bytes = s ? (unsigned int)(s[4] << 8 | s[5]) * (unsigned int)(s[6] << 8 | s[7]) : 0;
            if (bytes > best) { best = bytes; big = s; }
        }
        for (i = 0; i < CORE_SPRITE_SLOTS; ++i) {
            if (!playing || i >= core_sprite_reserved || !big || !npc_sprite_upload(big, &core_sprite_inst[i]))
                core_sprite_inst[i].slot = NPC_SPRITE_SLOT_NONE;   /* bank full: not drawn */
            else ++sprite_stats.slots;
        }
        for (i = 0; i < TOOL_COUNT; ++i)
            if (!playing || !CORE_DRAW->tool_sheet[i] ||
                !npc_sprite_upload(CORE_DRAW->tool_sheet[i], &CORE_DRAW->tool_inst[i]))
                CORE_DRAW->tool_inst[i].slot = NPC_SPRITE_SLOT_NONE;
    }
#endif
}

#ifdef CORE_SPRITES
static void sprites_draw(void)
{
    /* Core NPC view is bounded to 32. Resolve each sample once, then protect
     * all resident hits before any miss may replace a cel needed later in
     * this draw. Static scratch avoids the small master stack. */
    static const unsigned char *requested[32];
    static unsigned samples[32];
    const OotCoreNpcView *v;
    int n = oot_core_npcs(&v), k;
    unsigned int pinned = 0;
    for (k = 0; k < n; ++k) {
        const unsigned char *clip;
        npc_sprite_inst_t *slot;
        unsigned int sample;
        unsigned locked = ~0u;
        int dx = v[k].x - recomp_camera.x, dz = v[k].z - recomp_camera.z;
        requested[k] = 0;
        if (!v[k].anim || !(v[k].flags & OOT_CORE_VIEW_DRAWN) ||
            dx < -2000 || dx > 2000 || dz < -2000 || dz > 2000) continue;
        clip=sprites_clip(&v[k]);
        if (!clip || !v[k].alpha || !npc_sprite_visible_scaled(clip,v[k].x,v[k].y,v[k].z,
                                                             v[k].scale_x,v[k].scale_y)) continue;
        sample=npc_sprite_cel(clip,v[k].frame,v[k].x,v[k].z,v[k].yaw);
        /* Soul sheets are billboards, not eight-way character poses. */
        if (v[k].object == 0x06d && ((v[k].anim >> 20) & 15u) >= 3u)
            sample=npc_sprite_cel(clip,v[k].frame,v[k].x,v[k].z,
                                 gameplay_facing(recomp_camera.x-v[k].x,recomp_camera.z-v[k].z));
        requested[k] = clip; samples[k] = sample;
        slot=npc_sprite_cache_claim(core_sprite_inst,CORE_SPRITE_SLOTS,&locked,clip,
                                   sample & 0xffffu); /* lookup only, no eviction */
        if (slot) pinned |= 1u << (unsigned)(slot - core_sprite_inst);
    }
    for (k = 0; k < n; ++k) {
        const unsigned char *clip = requested[k];
        npc_sprite_inst_t *slot;
        unsigned sample = samples[k];
        if (!clip) continue;
        /* Restore last_depth for near-plane sprite projection. */
        (void)npc_sprite_visible_scaled(clip,v[k].x,v[k].y,v[k].z,v[k].scale_x,v[k].scale_y);
        slot=npc_sprite_cache_claim(core_sprite_inst,CORE_SPRITE_SLOTS,&pinned,clip,sample & 0xffffu);
        if (!slot) { ++sprite_stats.missing; continue; }
        npc_sprite_draw_styled(clip,slot,sample,v[k].x,v[k].y,v[k].z,
                               v[k].scale_x,v[k].scale_y,v[k].alpha,v[k].tint);
    }
}
#endif

/* From world_props_draw: one prebuilt mesh per decomp draw item. */
static void source_beam_draw(const OotCoreEffectView* v)
{
    static POLYGON poly={{0,0,0},{0,1,2,3}};
    static ATTR attr=ATTRIBUTE(Dual_Plane,SORT_CEN|UseNearClip,0,C_RGB(20,22,31),No_Gouraud,
                               ECdis|SPdis,sprPolygon,No_Option);
    int32_t sn,cs;
    kokiri_camera_sincos(recomp_yaw,&sn,&cs);
    for(unsigned i=0;i<4;++i){
        int far=i==1||i==2;
        int side=i<2 ? v->regs[3] : -v->regs[3];
        CORE_DRAW->beam_points[i][X]=(far?v->regs[0]:v->x)*65536+side*cs;
        CORE_DRAW->beam_points[i][Y]=-(far?v->regs[1]:v->y)*65536;
        CORE_DRAW->beam_points[i][Z]=(far?v->regs[2]:v->z)*65536-side*sn;
    }
    CORE_DRAW->beam_data=(PDATA){CORE_DRAW->beam_points,4,&poly,1,&attr};
    kokiri_submit_pdata(&CORE_DRAW->beam_data);
}

static void effects_draw(void)
{
#ifdef __sh__
    typedef char effect_view_fits[sizeof(OotCoreEffectView)*OOT_CORE_EFFECT_VIEWS_MAX
                                  <= RAM_LOW_EFFECT_VIEW_BYTES ? 1 : -1];
    OotCoreEffectView *rows=RAM_LOW(RAM_LOW_EFFECT_VIEW_OFFSET);
#else
    OotCoreEffectView rows[OOT_CORE_EFFECT_VIEWS_MAX];
#endif
    unsigned omitted=0;
    int count;
#ifdef OOT_CORE_ASYNC
    if (ASYNC_BUSY()) count = playing ? snap_effect_n : 0;   /* rows written at the snapshot */
    else
#endif
    count=playing?ENTRY->effect_view(rows,OOT_CORE_EFFECT_VIEWS_MAX,&omitted):0;
    for(int i=0;i<count;++i){
        const OotCoreEffectView *v=&rows[i];
        if (v->type == OOT_CORE_EFFECT_DODONGO_LAVA) {
            kokiri_scene_dodongo_lava((unsigned short)v->regs[0]);
            continue;
        }
        if (v->type == OOT_CORE_EFFECT_BEAMOS_BEAM) {
            source_beam_draw(v);
            continue;
        }
        if (v->type == OOT_CORE_EFFECT_MINIGAME_SCORE) {
            kokiri_minigame_score_draw((unsigned short)v->regs[0]);
            continue;
        }
        unsigned radius=4,colour=C_RGB(24,22,18),dither=1;
        if(!npc_sprite_in_view(v->x,v->y,v->z,80))continue;
        switch(v->type){
        case 0x1e: /* Source moving 30/60/100 point popup, no render-owned timer. */
            kokiri_score_popup_draw(v->x,v->y,v->z,(unsigned short)v->regs[2],(unsigned short)v->regs[3]);
            continue;
        case 0x01: /* Sparkles. Source scale is percent of the 10-unit quad. */
            radius=v->regs[11]>0?(unsigned)v->regs[11]/10:0;
            goto prim_2;
        case 0x03: /* Bomb blast, Dodongo fire and death particles. */
        case 0x06:
        case 0x21:
            radius=v->regs[0]>0?(unsigned)v->regs[0]/10:0;
prim_2:
            colour=C_RGB(v->regs[2]>>3,v->regs[3]>>3,v->regs[4]>>3);
            if(v->regs[5]<=0)continue;
            dither=v->regs[5]<192;break;
        case 0x04: /* Blast ring / guard sparks. */
        case 0x05:
            radius=v->regs[9]>0?(unsigned)v->regs[9]/10:0;
            colour=C_RGB(v->regs[0]>>3,v->regs[1]>>3,v->regs[2]>>3);
            if(v->regs[3]<=0)continue;
            dither=v->regs[3]<192;break;
        case 0x07: radius=v->regs[0]>0?(unsigned)v->regs[0]/20:0;colour=C_RGB(31,31,31);break;
        case 0x09: /* Water ripple/splash. */
        case 0x0a:
            radius=v->regs[1]>0?(unsigned)v->regs[1]/10:0;
            colour=C_RGB(v->regs[3]>>3,v->regs[4]>>3,v->regs[5]>>3);
            if(v->regs[6]<=0)continue;
            dither=v->regs[6]<192;break;
        case 0x14: radius=v->life<8?(unsigned)(8-v->life):1;colour=C_RGB(31,31,20);dither=0;break;
        case 0x19: radius=v->regs[7]>0?(unsigned)v->regs[7]/20:0;break;
        case 0x1f: /* Source burning ring: life controls expansion/fade. */
            radius=v->regs[11]>0?(unsigned)v->regs[11]*(20u+(v->life>0?v->life:0))/400:0;
            colour=C_RGB(31,27,0);dither=v->life<15;break;
        case 0x1b:
            radius=v->regs[12]>0?(unsigned)v->regs[12]/10:0;
            colour=C_RGB(v->regs[4]>>3,v->regs[5]>>3,v->regs[6]>>3);
            if(v->regs[7]<=0)continue;
            dither=v->regs[11] ? v->life<9 : v->regs[7]<192;break;
        case 0x22:
            radius=v->regs[0]>0?(unsigned)v->regs[0]/10:0;colour=C_RGB(0,0,0);
            if(v->regs[5]<=0)continue;
            dither=v->regs[5]<192;break;
        case 0x24:
            radius=v->regs[2]>0?(unsigned)v->regs[2]/10:0;colour=C_RGB(24,29,29);
            if(v->regs[1]<=0)continue;
            dither=v->regs[1]<192;break;
        case OOT_CORE_EFFECT_MOUNTAIN_FRAGMENT:
        case OOT_CORE_EFFECT_DODONGO_EMBER:
            radius=(unsigned short)v->regs[0];
            colour=C_RGB(v->regs[1]>>3,v->regs[2]>>3,v->regs[3]>>3);
            dither=v->regs[4]<192;break;
        case 0x0b: /* Source lava bubble. */
            radius=(unsigned short)v->regs[1]/20;
            colour=C_RGB(v->regs[3]>>3,v->regs[4]>>3,v->regs[5]>>3);dither=v->regs[6]<192;break;
        case 0x13: /* Source lava splash / black smoke. */
            radius=(unsigned short)v->regs[11]/2;
            colour=C_RGB(v->regs[0]>>3,v->regs[1]>>3,0);dither=v->regs[2]<192;break;
        case 0x00: radius=v->regs[9]>0?(unsigned)v->regs[9]/4:1;break; /* Dust */
        case 0x0f: radius=v->regs[3]>0?(unsigned)v->regs[3]/2:1;dither=0;break;
        case 0x15: radius=v->regs[8]>0?(unsigned)v->regs[8]/8:1;colour=C_RGB(31,31,12);dither=0;break;
        case OOT_CORE_EFFECT_POE_FLAME:
        case 0x1d: kokiri_flame_draw(v->x,v->y,v->z,v->life);continue;
        case 0x20: radius=v->regs[0]>0?(unsigned)v->regs[0]/4:1;colour=C_RGB(31,17,4);break;
        default: continue;
        }
        kokiri_particle_draw(v->x,v->y,v->z,radius,colour,dither);
    }
}

void oot_core_meshes_draw(void)
{
    sprites_draw();
    tools_draw();
    effects_draw();
    const OotCoreDrawItem *items;
    int n, i;
#ifdef OOT_CORE_ASYNC
    if (ASYNC_BUSY()) { items = snap_items; n = playing ? snap_items_n : 0; }
    else
#endif
    n = playing ? ENTRY->draw_items(&items) : 0;
    unsigned int m;
    for (i = 0; i < n; ++i) {
        const OotCoreDrawItem *it = &items[i];
        /* Source primitive alpha, including zero-alpha legend light volumes.
         * Temporal coverage avoids an extra Saturn texture/material bank. */
        if(!it->alpha || ((recomp_world_clock()+(unsigned)i)&7u)>=(it->alpha+31u)/32u)continue;
        int dx = it->x - recomp_camera.x, dz = it->z - recomp_camera.z;
        if (dx < -2000 || dx > 2000 || dz < -2000 || dz > 2000) continue;
        /* Off-screen: skip SGL's transform of the whole mesh. 400 covers
         * the largest prop meshes (scaled). */
        if (!npc_sprite_in_view(it->x, it->y, it->z, 400)) continue;
        for (m = 0; m < core_mesh_count; ++m)
            if (core_mesh_ready[m] && core_mesh_key[m].kind == it->kind &&
                core_mesh_key[m].object == it->object && core_mesh_key[m].index == it->index) {
                actor_mesh_draw_euler(core_mesh[m], it->x, it->y, it->z, it->yaw, it->pitch,
                                      it->roll, it->sx, it->sy, it->sz);
                break;
            }
    }
}

/* Saturn pad -> N64 buttons the decomp reads (z_message, talk). The
** Saturn layout keeps A for A and B for B; the D-pad/stick menu step drives
** text choices as an N64 stick flick. */
static bool npc_text_opened;
static void send_input(const gameplay_input_t *in)
{
    /* Keep source chest/get-item animation running, but prevent dismissal
     * and movement until the complete disc cue releases the drive. */
    if (cdda_busy()) { ENTRY->set_input(0, 0, 0, 0); return; }
    unsigned short press = (unsigned short)((in->interact ? 0x8000u : 0u) | (in->cancel ? 0x4000u : 0u));
    if (CORE_DRAW->shop.flags & OOT_SHOP_CONTROL) {
        /* Source EnOssan accumulates both axes while its description box is
         * open. Ordinary message choices keep the menu-edge path below. */
        signed char sx = in->n64_stick_x, sy = in->n64_stick_y;
        if (!sx && in->menu_dx) sx = (signed char)(in->menu_dx < 0 ? -60 : 60);
        if (!sy && in->menu_dy) sy = (signed char)(in->menu_dy < 0 ? 60 : -60);
        if (npc_text_opened) { press = 0; npc_text_opened = false; }
        ENTRY->set_input(press, press, sx, sy);
        return;
    }
#ifdef PLAYER_SOURCE
    /* The real Player reads the whole controller. A text box or the Ocarina
     * keeps the menu-style mapping below (A/B/C presses, stick flicks). */
    if (!(ENTRY->ocarina(0) & 2u) && !(ENTRY->talk_state() & 1u) && !npc_text_opened &&
        !ENTRY->message_view()->active) {
        ENTRY->set_input(in->n64_held, in->n64_press, in->n64_stick_x, in->n64_stick_y);
        return;
    }
#endif
    if (ENTRY->ocarina(0) & 2u) {
        /* Ocarina owns the menu-style D-pad edges, including C+direction on
         * digital pads. Warp choices still use ordinary message navigation. */
        if (in->c_up || in->menu_dy < 0) press |= 0x0008;
        if (in->c_use == 1 || in->menu_dy > 0) press |= 0x0004;
        if (in->c_use == 2 || in->menu_dx < 0) press |= 0x0002;
        if (in->c_use == 3 || in->menu_dx > 0) press |= 0x0001;
    }
    if (npc_text_opened) { press=0; npc_text_opened=false; }
    ENTRY->set_input(press, press, 0, (signed char)(in->menu_step < 0 ? 60 : in->menu_step > 0 ? -60 : 0));
}

#ifdef PLAYER_SOURCE
#define PLAYER_GROUPS_TABLES
#include "player_groups.h"
/* Demand Player clip groups (tools/split_player_bank.py). Slots 0..7 hold
 * PG<name>.PFB, slot 8 the scene's cutscene pack PCS<id>.PFB (every shot
 * and branch, pinned until scene unload). Loaded behind the loading screen
 * or the pause menu only, never mid-action; Player_UseItem waits for a
 * missing item group (OotCore_PlayerItemReady). */
#define PLAYER_GROUP_SLOTS (PLAYER_GROUP_COUNT + 1)
static void *player_group_bank[PLAYER_GROUP_SLOTS];
static int player_group_bytes[PLAYER_GROUP_SLOTS];
/* PLAYRES.PFB: common clips, first scene load until the session reset (the
 * new-game opening runs before any scene with only PLAYC.PFB). */
static void *player_res;
static int player_res_bytes;

bool HOST_COLD_CODE __attribute__((optimize("Os"))) oot_core_player_resident(void)
{
    if (!loaded || player_res) return true;
    if (!(player_res = jo_fs_read_file("PLAYRES.PFB", &player_res_bytes)) ||
        !ENTRY->player_bank(player_res, (unsigned int)player_res_bytes)) {
        if (player_res) jo_free(player_res);
        player_res = 0;
        jo_core_error("PLAYRES.PFB: Player clips failed heap %d%%", jo_memory_usage_percent());
        return false;
    }
    return true;
}

static void HOST_COLD_CODE __attribute__((optimize("Os"))) player_resident_release(void)
{
    if (!player_res) return;
    ENTRY->player_bank_release(player_res, (unsigned int)player_res_bytes);
    jo_free(player_res);
    player_res = 0;
}

static void HOST_COLD_CODE __attribute__((optimize("Os"))) player_groups_release(void)
{
    unsigned int g;
    for (g = 0; g < PLAYER_GROUP_SLOTS; ++g) {
        if (!player_group_bank[g]) continue;
        ENTRY->player_bank_release(player_group_bank[g], (unsigned int)player_group_bytes[g]);
        jo_free(player_group_bank[g]);
        player_group_bank[g] = 0;
    }
    if (loaded) ENTRY->player_groups(0);
}

static unsigned int __attribute__((optimize("Os"))) player_groups_loaded(void)
{
    unsigned int g, mask = 0;
    for (g = 0; g < PLAYER_GROUP_COUNT; ++g)
        if (player_group_bank[g]) mask |= 1u << g;
    return mask;
}

/* Groups of the items on the C buttons (slots as mirror_save maps them). */
static unsigned int HOST_COLD_CODE __attribute__((optimize("Os"))) player_groups_items(void)
{
    unsigned int i, k, mask = 0;
    for (i = 0; i < 3; ++i) {
        unsigned int slot = save_c_item_inventory_slot(save_state.c_items[i]), item;
        if (slot >= 24) continue;
        item = save_state.source_items[slot];
        if (item >= PLAYER_GROUP_BOTTLE_FIRST && item <= PLAYER_GROUP_BOTTLE_LAST)
            mask |= 1u << PLAYER_GROUP_BOTTLE;
        for (k = 0; k < sizeof player_group_items / sizeof player_group_items[0]; ++k)
            if (player_group_items[k][0] == item) mask |= 1u << player_group_items[k][1];
    }
    return mask;
}

/* Scene needs: water, cutscene pack (bit 7), adult horse and fishing. */
static unsigned int HOST_COLD_CODE __attribute__((optimize("Os"))) player_groups_scene(unsigned int scene)
{
    unsigned int k, mask = scene < PLAYER_GROUP_SCENES ? player_group_scene[scene] : 0u;
    for (k = 0; k < sizeof player_group_horse_scenes; ++k)
        if (player_group_horse_scenes[k] == scene && save_state.link_age == 0)  /* LINK_AGE_ADULT */
            mask |= 1u << PLAYER_GROUP_HORSE;
    for (k = 0; k < sizeof player_group_fish_scenes; ++k)
        if (player_group_fish_scenes[k] == scene) mask |= 1u << PLAYER_GROUP_FISH;
    return mask;
}

static bool HOST_COLD_CODE __attribute__((optimize("Os"))) player_group_load(unsigned int slot, const char *name)
{
    int bytes = 0;
    void *bank;
    if (player_group_bank[slot]) return true;
    if (GFS_NameToId((Sint8 *)name) < 0 || !(bank = jo_fs_read_file(name, &bytes))) return false;
    if (!ENTRY->player_bank(bank, (unsigned int)bytes)) { jo_free(bank); return false; }
    player_group_bank[slot] = bank;
    player_group_bytes[slot] = bytes;
    return true;
}

static bool HOST_COLD_CODE __attribute__((optimize("Os"))) player_groups_load(unsigned int want, unsigned int scene)
{
    static const char hex[] = "0123456789ABCDEF";
    unsigned int g;
    bool ok = true;
    char pack[] = "PCS00.PFB";
    for (g = 0; g < PLAYER_GROUP_COUNT; ++g)
        if ((want >> g & 1u) && !player_group_load(g, player_group_files[g])) ok = false;
    pack[3] = hex[(scene >> 4) & 15];
    pack[4] = hex[scene & 15];
    if ((want & PLAYER_GROUP_CS_PACK) && !player_group_load(PLAYER_GROUP_COUNT, pack)) ok = false;
    ENTRY->player_groups(player_groups_loaded());
    return ok;
}

bool HOST_COLD_CODE __attribute__((optimize("Os"))) oot_core_player_groups_prepare(void)
{
    unsigned int want;
    if (!loaded || !playing) return true;
    want = player_groups_items() & ~player_groups_loaded();
    if (!want) return true;
    if (cdda_busy()) return false;   /* never read over a fanfare: close waits */
    oot_core_async_join();
    /* A failed load leaves that item waiting until the next scene load. */
    player_groups_load(want, scene_flow_entry()->oot_scene);
    return true;
}
#endif

void oot_core_scene_unload(void)
{
    oot_core_async_join();   /* never free a play state the slave is updating */
    playing = false;
    source_owl = false;
#ifdef CORE_COLLISION
    /* C proxies and raised water go with the PlayState that holds them. */
    bg_core_shim_scene_reset();
#else
    bg_water_bind(NULL, 0); /* borrowed OOC memory must not survive release */
#endif
    /* Keep source actors' code and objects valid through their destructors. */
    if (loaded) ENTRY->play_destroy();
    sprites_reset();
    tools_free();
#ifndef CORE_COLLISION
    core_dyna_reset();
#endif
    meshes_free();
#ifdef PLAYER_SOURCE
    player_groups_release();   /* after play_destroy: no Player consumer */
#endif
    if (loaded) ENTRY->pack_release();
    scene_objects = NULL;
    scene_object_count = 0;
    meshes_room = -1;
    oot_core_scene_restart();
}

/* Scene blob, sprite libraries and PlayState for `scene`; Player proxy at the
 * feet position. False leaves no PlayState (CORE_COLLISION: no collision). */
static bool scene_enter(unsigned int scene, unsigned int spawn, int room, int x, int y, int z, unsigned int yaw)
{
    unsigned int layer;
    oot_core_scene_unload();
    play_scene = scene;
    if (!load_scene_blob(scene)) {
        if (scene_load_failed) jo_printf(0, 20, "Actor pack load failed: %u", scene);
        return false;
    }
    /* age/time/flags before the layer choice: play_init picks the same
     * layer from the same mirror, so its sprites are the ones loaded. */
    mirror_save();
    layer = ENTRY->destination_layer(scene_flow_entry()->oot_scene);
    if (!sprites_preload((const OotSceneBlob *)OOT_SCENECOL_ADDR, layer)) {
        scene_load_failed = true;
        ENTRY->pack_release();
        /* OotCore_SpritePreload: count | object << 8 | row << 20 | reason << 28
         * (1 file, 2 heap, 3 read/validate). */
        jo_core_error("Sprite preload failed %08X heap %d%%", sprite_stats.missing,
                      jo_memory_usage_percent());
        return false;
    }
#ifdef PLAYER_SOURCE
    /* Scene/age/C-item Player clip groups before Player_Init can play one. */
    if (!player_groups_load(player_groups_scene(scene_flow_entry()->oot_scene) | player_groups_items(),
                            scene_flow_entry()->oot_scene)) {
        scene_load_failed = true;
        player_groups_release();
        ENTRY->pack_release();
        jo_core_error("Player clip groups failed heap %d%%", jo_memory_usage_percent());
        return false;
    }
#endif
    playing = ENTRY->play_init(RAM_LOW(RAM_LOW_OOTPLAY_OFFSET), RAM_LOW_OOTPLAY_BYTES,
                               scene_flow_entry()->oot_scene, (const void *)OOT_SCENECOL_ADDR,
                               room, spawn, (short)x, (short)y, (short)z, (short)yaw) != 0;
    if (playing && ENTRY->scene_layer() != layer) {
        /* Sprites and objects belong to one layer: never run another. */
        jo_core_error("Scene layer %u, sprites for %u", ENTRY->scene_layer(), layer);
        playing = false;
    }
    if (playing) {
        source_owl = ENTRY->actor_admitted(0x14d) != 0;
        ENTRY->set_objects(scene_objects, scene_object_count);
#ifdef PLAYER_SOURCE
        read_player();   /* spawn / respawn position is the Player's */
#endif
        ENTRY->set_flags(
#ifdef CORE_SPRITES
            OOT_CORE_FLAG_NPC_SPRITES |
#endif
            (scene_flow_is_interior() ? OOT_CORE_FLAG_FIXED_CAMERA : 0u));
        /* Sprite libraries are ready for every room of this layer. Actor
         * instances and static prop views appear on the first core step. */
    } else {
        scene_load_failed = true;
        ENTRY->play_destroy();
        ENTRY->pack_release();
    }
    step_phase = 0;
#ifdef OOT_CORE_ASYNC
    core_due = 0;   /* owed updates belonged to the previous play state */
#endif
    return playing;
}

#ifdef CORE_COLLISION
/* scene_flow_load, inside the loading screen: the core scene is the only
 * collision, so it must exist before C Link spawns or C props register. */
bool oot_core_scene_enter(unsigned int scene, unsigned int spawn)
{
    const scene_spawn_t *at = scene_flow_spawn(scene, spawn);
    int room = scene_flow_is_interior() ? 0 : (int)kokiri_bank_room();
    if (!loaded) return false;
    if (!scene_enter(scene, spawn, room, at->x, at->y, at->z, at->yaw)) {
        if (!scene_load_failed) jo_core_error("Scene %u has no core collision", scene);
        return false;
    }
    return true;
}
#endif

void oot_core_frame(const gameplay_input_t *in)
{
    unsigned int scene = scene_flow_scene();
    /* A panorama's bank room identifies its artwork, not an OoT actor room. */
    int room = scene_flow_is_interior() ? 0 : (int)kokiri_bank_room();
    if (!loaded || gameplay_is_paused()) return;
    host_audio_service();
    if (scene != play_scene) {
        scene_enter(scene, save_state.entrance, room, recomp_link.x, recomp_link.y - RECOMP_LINK_EYE_HEIGHT, recomp_link.z,
                    recomp_link_yaw);
    }
    if (!playing) {
        if (scene_load_failed) jo_printf(0, 20, "Scene load failed. Pause: reload");
        return;
    }
    sync_player();
    ENTRY->set_camera((short)recomp_yaw);
    seed_cutscene_camera();
    send_input(in);
    mirror_save();
    ENTRY->set_room(room);
#ifndef CORE_COLLISION
    {
        const void *water;
        unsigned count=ENTRY->water_boxes(&water);
        bg_water_bind((const bg_waterbox_t *)water,count);
    }
#endif
    {
        int32_t base[3], tip[3];
        bool have = gameplay_blade_points(base, tip);
        ENTRY->set_sword(have && gameplay_sword_active(), have ? (const int *)base : 0,
                         have ? (const int *)tip : 0);
    }
    /* Decomp actors are written for 20 Hz; gameplay steps run at 30 Hz. */
    step_phase += 2;
    if (step_phase >= 3) {
        step_phase -= 3;
#ifdef OOT_CORE_ASYNC
        /* Fast: runs on the slave at the start of the draw (oot_core_async_
         * kick), shown a frame later. Responsive: below, inside this step. */
        if (!ui_core_responsive()) {
            int32_t hand[3];
            if (gameplay_link_point(18, hand)) ENTRY->tool(OOT_CORE_TOOL_HAND, (int *)hand);
            if (core_due < 2) ++core_due;
            return;
        }
        core_due = 0;
#endif
        unsigned int t0 = frame_timer_ticks();
        {
            int32_t hand[3];
            if (gameplay_link_point(18, hand)) ENTRY->tool(OOT_CORE_TOOL_HAND, (int *)hand);
        }
        ENTRY->update();
        host_audio_service();
#ifndef CORE_COLLISION
        core_dyna_sync();
#endif
#ifdef PLAYER_SOURCE
        read_player();
#else
        read_cutscene_camera();
#endif
        CORE_DRAW->tool_bits = (unsigned int)ENTRY->tool(OOT_CORE_TOOL_STATE, CORE_DRAW->tool_pull);
        if (CORE_DRAW->tool_bits & OOT_CORE_TOOL_MAGIC_RESET) health_hud_magic_reset();
        health_hud_magic_update(); /* Magic_Update, once per source frame */
        update_us = frame_timer_ticks_to_us(frame_timer_ticks() - t0);
        if (!cdda_busy() && meshes_room != room) {
            meshes_room = room;
            load_meshes();
        } else if (!cdda_busy() && sprites_refresh()) npc_draw_reupload();
        {
            int dx, dz;   /* decomp actors pushing the player (En_Ko blockers) */
            ENTRY->player_push(&dx, &dz);
            recomp_link.x += dx;
            recomp_link.z += dz;
        }
    }
}

unsigned int oot_core_talk(void)
{
    return playing ? ENTRY->talk_state() | (ENTRY->message_view()->active ? 1u : 0u) : 0u;
}
int oot_core_npcs(const OotCoreNpcView **out)
{
#ifdef OOT_CORE_ASYNC
    if (ASYNC_BUSY()) { *out = snap_npc; return playing ? snap_npc_n : 0; }
#endif
    return playing ? ENTRY->npc_view(out) : 0;
}
int oot_core_prop(short id, int x, int z)
{
#ifdef OOT_CORE_ASYNC
    if (ASYNC_BUSY()) {
        unsigned i;
        /* Signs are the only host prop-query consumer. Never walk a live
         * actor list while the slave can spawn/kill actors in it. */
        if (playing && id == 0x0141)
            for (i = 0; i < KOKIRI_SIGN_COUNT; ++i)
                if (kokiri_signs[i].x == x && kokiri_signs[i].z == z)
                    return snap_sign_parts[i];
        return -1;
    }
#endif
    return playing ? ENTRY->prop_query(id, x, z) : -1;
}
const char *oot_core_debug_text(void) { return playing ? ENTRY->debug_text() : ""; }
const char *oot_core_debug_text2(void) { return playing ? ENTRY->debug_text2() : ""; }
const oot_core_sprite_stats_t *oot_core_sprite_stats(void) { return &sprite_stats; }
int oot_core_door_action(unsigned int kind, unsigned int flag, int front_side, bool commit)
{
    return playing ? ENTRY->door_action(kind, flag, front_side, commit) : 0xFF00;
}
unsigned int oot_core_scene_layer(void) { return playing ? ENTRY->scene_layer() : 0; }
unsigned int oot_core_destination_layer(unsigned int original_base_scene)
{
    return playing ? ENTRY->destination_layer(original_base_scene) : 0;
}
unsigned int oot_core_skybox_settings(void) { return playing ? ENTRY->skybox_settings() : 0; }
void oot_core_cancel_transition_time(void)
{
    if (loaded) ENTRY->cancel_transition_time();
}
int oot_core_transition_request(bool consume)
{
    return playing && !cdda_busy() ? ENTRY->transition_request(consume) : -1;
}
bool oot_core_ocarina_start(void) { return playing && ENTRY->ocarina(1) != 0; }
unsigned int oot_core_ocarina_state(void)
{
    /* Link's draw reads this mid-update: answer from the last master read. */
    static unsigned int cached;
    if (!ASYNC_BUSY()) cached = playing ? ENTRY->ocarina(0) : 0;
    return cached;
}
unsigned int oot_core_ocarina_note(void) { return playing ? ENTRY->ocarina(2) : 0; }
unsigned int oot_core_ocarina_song(void) { return playing ? ENTRY->ocarina(3) : 0; }
bool oot_core_ocarina_sun_allowed(void) { return playing && ENTRY->ocarina(4) != 0; }
bool oot_core_ocarina_sun_start(void) { return playing && ENTRY->ocarina(5) != 0; }
void oot_core_scene_restart(void) {
    playing = false;
    scene_load_failed = false;
    play_scene = ~0u;
}
bool oot_core_scene_failed(void) { return scene_load_failed; }

/* The decomp text box on the VDP2 text layer, in the C dialogue rows.
** VDP2 keeps text, so rows are reprinted only when the view changes and
** cleared once when the box closes. Returns true while it is up. */
#define OC_MSG_ROW 20
#define OC_MSG_ROWS (OOT_CORE_MSG_ROWS + 2)
unsigned int oot_core_npc_text(unsigned int command)
{
    unsigned result=playing ? ENTRY->npc_text(command) : 0;
    if ((command & 0x10000u) && result) npc_text_opened=true;
    return result;
}
bool oot_core_message_box(void)
{
    static unsigned short shown_serial;
    static bool was_active;
    /* z_message colour index -> Jo palette: white red green blue lightblue purple yellow black. */
    static const unsigned char colour_map[8] = { 0, 2, 3, 4, 4, 6, 4, 0 };
    const OotCoreMessageView *v = playing ? ENTRY->message_view() : 0;
    unsigned int r, c;
    if (!v || !v->active) {
        if (was_active)
            for (r = 0; r < OC_MSG_ROWS; ++r) jo_printf(0, OC_MSG_ROW + (int)r, "%-40s", "");
        was_active = false;
        return false;
    }
    kokiri_message_box_draw(160, OC_MSG_ROW * 8 + OC_MSG_ROWS * 4, 320, OC_MSG_ROWS * 8);
    if (!was_active || v->serial != shown_serial) {
        for (r = 0; r < OOT_CORE_MSG_ROWS; ++r) {
            int row = OC_MSG_ROW + 1 + (int)r;
            bool choice_row = v->choices && r + v->choices >= v->rows && r < v->rows;
            unsigned limit=OOT_CORE_MSG_COLS-(choice_row ? 2u : 0u);
            /* Replace padded runs directly; never blank visible text first. */
            jo_printf(0,row," ");
            jo_printf(39,row," ");
            if (choice_row) jo_printf(1,row,"%c ",r+v->choices-v->rows==v->choice ? '>' : ' ');
            for (c = 0; c < limit; ) {
                unsigned int start = c, colour = v->colour[r][c] & 7;
                while (c < limit && (v->colour[r][c] & 7) == colour) ++c;
                jo_printf_with_color(1 + (int)start + (choice_row ? 2 : 0), row, colour_map[colour],
                                     "%.*s", (int)(c - start), &v->text[r][start]);
                if (colour_map[colour] != 0) /* emphasis (z_message colour) is bold */
                    recomp_text_embolden(1 + (int)start + (choice_row ? 2 : 0), row,
                                         &v->text[r][start], c - start);
            }
        }
        jo_set_printf_color_index(JO_COLOR_INDEX_White);
        shown_serial = v->serial;
    }
    was_active = true;
    if (v->prompt)
        kokiri_message_mark_draw(160, (OC_MSG_ROW + OC_MSG_ROWS - 1) * 8 + 4,
                                 v->prompt == OOT_CORE_MSG_PROMPT_END);
    return true;
}

void oot_core_timer_draw(bool visible)
{
    const OotCoreTimerView* view=&CORE_DRAW->timer;
    int x=view->x/8,y=view->y/8;
    visible=visible && playing && view->state && view->seconds>=0;
    if(x<0)x=0;else if(x>35)x=35;
    if(y<0)y=0;else if(y>26)y=26;
    if(CORE_DRAW->timer_shown && (!visible || x!=CORE_DRAW->timer_column || y!=CORE_DRAW->timer_row))
        jo_printf(CORE_DRAW->timer_column,CORE_DRAW->timer_row,"     ");
    if(visible){
        jo_printf(x,y,"%02u:%02u",(unsigned)view->seconds/60,(unsigned)view->seconds%60);
        CORE_DRAW->timer_column=x;CORE_DRAW->timer_row=y;
    }
    CORE_DRAW->timer_shown=visible;
}

bool oot_core_is_loaded(void) { return loaded; }
bool oot_core_is_playing(void) { return playing; }
const OotCoreBench *oot_core_bench_result(void) { return &bench; }
unsigned int oot_core_update_us(void) { return update_us; }
int oot_core_actors(int category) { return playing ? ENTRY->actor_count(category) : 0; }
int oot_core_view(int category, OotCoreActorView *out, int max)
{
#ifdef OOT_CORE_ASYNC
    if (ASYNC_BUSY()) {
        int k = category == 6 ? 0 : category == 8 ? 1 : -1, n, i;
        if (k < 0 || !playing) return 0;
        n = snap_view_n[k] < max ? snap_view_n[k] : max;
        for (i = 0; i < n; ++i) out[i] = snap_view[k][i];
        return n;
    }
#endif
    return playing ? ENTRY->actor_view(category, out, max) : 0;
}
#endif

#ifdef OOT_CORE_ASYNC
/* ---- Second-CPU core update -------------------------------------------- */
typedef struct { unsigned int updates, done, us; } slave_box_t;
static slave_box_t slave_box;
#define BOX ((volatile slave_box_t *)((uintptr_t)&slave_box | 0x20000000u))
static unsigned int async_updates, async_overlap_us, async_join_us, async_kick_tick;
static unsigned int async_slave_us;
unsigned int oot_core_slave_job_us(void) { return async_slave_us; }

/* Slave side: only the core, nothing of the host but the queued callbacks. */
static void slave_job_body(void)
{
    /* The slave's own FRT. SGL leaves it at clock/8 (18 ms wrap); select
     * /128 (293 ms) so long updates keep their count. Timed per update. */
    unsigned int cks, i, n = BOX->updates, ticks = 0;
    frame_timer_slave_prescale();
    cks = *(volatile uint8_t *)0xFFFFFE16 & 3u;
    slCashPurge();                       /* the master wrote input/state */
    for (i = 0; i < n; ++i) {
        uint16_t t0 = frame_timer_frc();
        ENTRY_RAW->update();
        ticks += (uint16_t)(frame_timer_frc() - t0);
    }
    /* 28.64 MHz: 8 -> 0.279 us, 32 -> 1.117, 128 -> 4.47 (x1000 / 1000). */
    BOX->us = cks == 0 ? ticks * 279u / 1000u : cks == 1 ? ticks * 1117u / 1000u :
              ticks * 4470u / 1000u;
    BOX->done = 1;
}

/* slSlaveFunc entry: switch to the Low RAM stack, run, switch back. */
static void __attribute__((noinline)) slave_job(void *arg)
{
    void *top = (void *)(RAM_LOW_ADDRESS + RAM_LOW_SLAVE_STACK_OFFSET + RAM_LOW_SLAVE_STACK_BYTES);
    (void)arg;
    __asm__ volatile(
        "mov    r15,r1\n\t"
        "mov    %0,r15\n\t"
        "mov.l  r1,@-r15\n\t"
        "jsr    @%1\n\t"
        "nop\n\t"
        "mov.l  @r15,r15\n\t"
        :
        : "r"(top), "r"(slave_job_body)
        : "r0", "r1", "r2", "r3", "r4", "r5", "r6", "r7", "mach", "macl", "pr", "t", "memory");
}

bool oot_core_async_busy(void) { return ASYNC_BUSY(); }

/* Copies of everything the master draws from the core while the slave runs
 * (tools, effects, draw items, NPC sprites, grass and drops). */
static void snapshot_views(void)
{
#ifdef __sh__
    OotCoreEffectView *rows = RAM_LOW(RAM_LOW_EFFECT_VIEW_OFFSET);
#else
    static OotCoreEffectView rows[OOT_CORE_EFFECT_VIEWS_MAX];
#endif
    const OotCoreNpcView *nv;
    const OotCoreDrawItem *items;
    const OotCoreToolView *tv;
    unsigned int omitted = 0;
    int i, n;
    bool source_signs = save_state.scene_id == SAVE_SCENE_KOKIRI_FOREST &&
                        oot_core_owns_kokiri_npcs();
    /* C-owned signs never consume these views. Avoid twenty full source
     * actor-list walks before launching the core; retain snapshots if that
     * ownership changes later. Clear old views on every disabled pass. */
    for (i = 0; i < KOKIRI_SIGN_COUNT; ++i)
        snap_sign_parts[i] = source_signs ?
            ENTRY_RAW->prop_query(0x0141, kokiri_signs[i].x, kokiri_signs[i].z) : -1;
    n = ENTRY_RAW->npc_view(&nv);
    snap_npc_n = n < SNAP_NPC_MAX ? n : SNAP_NPC_MAX;
    for (i = 0; i < snap_npc_n; ++i) snap_npc[i] = nv[i];
    n = ENTRY_RAW->draw_items(&items);
    snap_items_n = n < OOT_CORE_DRAW_ITEMS_MAX ? n : OOT_CORE_DRAW_ITEMS_MAX;
    for (i = 0; i < snap_items_n; ++i) snap_items[i] = items[i];
    n = ENTRY_RAW->tool_view(&tv);
    snap_tools_n = n < OOT_CORE_TOOL_VIEWS_MAX ? n : OOT_CORE_TOOL_VIEWS_MAX;
    for (i = 0; i < snap_tools_n; ++i) snap_tools[i] = tv[i];
    snap_view_n[0] = ENTRY_RAW->actor_view(6, snap_view[0], SNAP_VIEW_MAX);
    snap_view_n[1] = ENTRY_RAW->actor_view(8, snap_view[1], SNAP_VIEW_MAX);
    snap_effect_n = ENTRY_RAW->effect_view(rows, OOT_CORE_EFFECT_VIEWS_MAX, &omitted);
}

void oot_core_async_kick(void)
{
    if (ASYNC_BUSY() || !playing || !core_due || gameplay_is_paused() || ui_core_responsive()) return;
    snapshot_views();
    async_updates = core_due;
    core_due = 0;
    BOX->updates = async_updates;
    BOX->done = 0;
    UNCACHED(sfx_queued) = 0;
    UNCACHED(async_busy) = 1;
    async_kick_tick = frame_timer_ticks();
    slSlaveFunc(slave_job, 0);
}

void oot_core_async_join(void)
{
    unsigned int t0, i, n;
    volatile unsigned int *f;
    if (!ASYNC_BUSY()) return;
    t0 = frame_timer_ticks();
    async_overlap_us = frame_timer_ticks_to_us(t0 - async_kick_tick);
    while (!BOX->done)
        if (frame_timer_ticks_to_us(frame_timer_ticks() - t0) > 250000u)
            jo_core_error("oot-core slave update did not finish");
    async_join_us = frame_timer_ticks_to_us(frame_timer_ticks() - t0);
    async_slave_us = BOX->us;
    PS_ACC(PS_WJOIN, async_join_us);
    PS_ACC(PS_SCORE, async_slave_us);
    slCashPurge();                       /* see the slave's writes */
    UNCACHED(async_busy) = 0;
    n = sfx_queued;
    for (i = 0; i < n && i < SFX_QUEUE; ++i) host_sfx_now(sfx_queue[i]);
    sfx_queued = 0;
    f = deferred_fatal;
    if (f[0]) { f[0] = 0; host_fatal(f[1], f[2], f[3]); }
    host_audio_service();
    /* Post-update work the synchronous path did after ENTRY->update(). */
    read_player();
    CORE_DRAW->tool_bits = (unsigned int)ENTRY->tool(OOT_CORE_TOOL_STATE, CORE_DRAW->tool_pull);
    if (CORE_DRAW->tool_bits & OOT_CORE_TOOL_MAGIC_RESET) health_hud_magic_reset();
    for (i = 0; i < async_updates; ++i) health_hud_magic_update(); /* once per source frame */
    update_us = async_join_us;
    {
        int room = scene_flow_is_interior() ? 0 : (int)kokiri_bank_room();
        if (!cdda_busy() && meshes_room != room) {
            meshes_room = room;
            load_meshes();
        } else if (!cdda_busy() && sprites_refresh()) npc_draw_reupload();
    }
    {
        int dx, dz;
        ENTRY->player_push(&dx, &dz);
        recomp_link.x += dx;
        recomp_link.z += dz;
    }
}

/* Read before stats clears the interval's violation count. No core entry. */
unsigned int oot_core_async_violation_line(void)
{
#ifndef DOSEI_CLEAN_TEST
    return async_violations ? async_violation_line : 0;
#else
    return 0;
#endif
}

void oot_core_async_stats(unsigned int out[5])
{
    uint32_t q = 0, r = 0;
    out[0] = async_updates;
    out[1] = async_overlap_us;
    out[2] = async_join_us;
    out[3] = async_violations;
#ifdef CORE_COLLISION
    out[4] = bg_core_shim_busy_hits();
#else
    out[4] = 0;
#endif
    async_violations = 0;
    (void)q; (void)r;
}
#else
unsigned int oot_core_slave_job_us(void) { return 0; }
void oot_core_async_kick(void) {}
void oot_core_async_join(void) {}
bool oot_core_async_busy(void) { return false; }
unsigned int oot_core_async_violation_line(void) { return 0; }
void oot_core_async_stats(unsigned int out[5]) { out[0] = out[1] = out[2] = out[3] = out[4] = 0; }
#endif
