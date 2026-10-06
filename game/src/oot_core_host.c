#include "oot_core_host.h"
#ifdef DOSEI_OOT_CORE
/* Glue, not per-vertex work: size over speed (work RAM). */
#pragma GCC optimize("Os")
#include <jo/jo.h>
#include "action_audio.h"
#include "recomp.h"
#include "frame_timer.h"
#include "gameplay.h"
#include "game_mode.h"
#include "kokiri_sgl.h"
#include "asset_names.h"
#include "scene_flow.h"
#include "ram_cart.h"
#include "ram_low.h"
#include "save_state.h"
#include "oot_scene_blob.h"
#include "actor_mesh.h"
#include "npc_draw.h"
#include "collide.h"
#include "kokiri_collision.h"
#include "player_items.h"
#include <stdlib.h>
#include <string.h>
/* Generic decomp NPCs as baked sprites (tools/build_npc_sprites.py --generic,
** blob OOT_CORE_FLAG_NPC_SPRITES): no Actor_Draw, no limb matrices. */
#define CORE_SPRITES 1
#include "npc_sprite.h"
static const struct { unsigned short object; unsigned char limbs; unsigned int anim; unsigned char file; }
core_sprite_rows[] = {
#include "../build/oot-core/generic_sprites.h"
};
#define CORE_SPRITE_ROWS (sizeof core_sprite_rows / sizeof core_sprite_rows[0])
#define CORE_SPRITE_SLOTS 8
#define CORE_SPRITE_HEAP_PERCENT 85   /* leave heap for the rest of the scene */
#define CORE_MESHES_MAX 40
/* Decomp actor ids (actor_table.h) of Link's tools. */
#define ACTOR_EN_BOM     0x0010
#define ACTOR_EN_ARROW   0x0016
#define ACTOR_EN_BOOM    0x0032
#define ACTOR_ARMS_HOOK  0x0066
#define ACTOR_EN_BOM_CHU 0x00DA
enum { TOOL_ARW, TOOL_BOM, TOOL_CHU, TOOL_BOO, TOOL_HKT, TOOL_HKC, TOOL_BGS, TOOL_MIR,
       TOOL_IRB, TOOL_HOB, TOOL_EXP, TOOL_COUNT };
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

static void core_draw_init(void)
{
    memset(CORE_DRAW, 0, sizeof *CORE_DRAW);
}


#define ENTRY ((const OotCoreEntry *)OOT_CORE_LOAD_ADDR)

/* ---- OotCoreHost: decomp -> C backends ---- */
static void host_sfx(unsigned short sfx_id, int x, int y, int z)
{
    (void)x; (void)y; (void)z;
    action_audio_decomp_sfx(sfx_id);
}

/* Decomp ItemId (include/item.h) -> C save item. */
static unsigned char host_give_item(unsigned char item)
{
    save_item_t give;
    switch (item) {
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
    case 0x1A: give = SAVE_ITEM_BOTTLE_MILK_FULL; break; /* Talon's first bottle */
    case 0x82: give = SAVE_ITEM_MILK; break;            /* cow/Talon refill */
    default: return item; /* not in the C save yet: not given */
    }
    if (!save_item_give(give)) return item;
    gameplay.rupees = save_state.rupees; /* HUD counter */
    return 0xFF;
}

/* Health_ChangeBy: 1/16 heart units; nonzero = still alive. */
static int host_health_change(short amount)
{
    if (amount >= 0) save_heal((unsigned int)amount);
    else save_damage((unsigned int)-amount);
    return save_state.health != 0;
}

static void host_rupees_change(short amount)
{
    int r = (int)save_state.rupees + amount;
    unsigned int cap = save_wallet_capacity();
    save_state.rupees = (uint16_t)(r < 0 ? 0 : (unsigned int)r > cap ? cap : (unsigned int)r);
    gameplay.rupees = save_state.rupees;
}

static const OotCoreHost host = { host_sfx, host_give_item, host_health_change,
                                  frame_timer_ticks, frame_timer_ticks_to_us, host_rupees_change };

static OotCoreBench bench;
/* Last decomp update (Actor_UpdateAll etc.), microseconds. */
static unsigned int update_us;
static bool loaded;
static bool playing;
/* Scene index the play state belongs to (or whose blob is missing/failed):
** a failed scene is not retried every frame. */
static unsigned int play_scene = 0xFFFFu;
static unsigned int step_phase;
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
    loaded = load_carve("OOTCORE.BIN", RAM_CART_OOTCORE_OFFSET, RAM_CART_OOTCORE_BYTES);
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
    ENTRY->init(&host);
    {
        /* ROM message text (NESMSG.BIN): z_message DMAs from it. */
        int bytes = load_carve("NESMSG.BIN", RAM_CART_MSGDATA_OFFSET, RAM_CART_MSGDATA_BYTES);
        if (bytes) ENTRY->set_text(ram_cart_fixed(RAM_CART_MSGDATA_OFFSET, RAM_CART_MSGDATA_BYTES),
                                   (unsigned int)bytes);
    }
    jo_printf(0, 20, "oc 3 bench ");
    ENTRY->bench(&bench, frame_timer_ticks, frame_timer_ticks_to_us);
    jo_printf(0, 20, "                    ");
    return true;
}

/* C Link -> player proxy: recomp_link is the eye, OoT pos is the feet.
** World units are OoT units (1:1). */
static void sync_player(void)
{
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
void oot_core_session_reset(unsigned int skybox_time)
{
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
        memcpy(mirror.player_name, "Link    ", 8); /* no file name in the C save */
        mirror.generic_scene = save_scene >= SAVE_SCENE_COUNT;
        ENTRY->set_save(&mirror);
        core_skybox_reset = 0;
    }
}

/* <scene>.OOC (asset_scene_name, like the room banks) into the scene carve,
** then each data object it lists (O<id>.OOB) packed after it. Objects are
** used through the cached alias like the blob. */
#define SCENE_OBJECTS_MAX 16
static const void *scene_objects[SCENE_OBJECTS_MAX];
static unsigned int scene_object_count;

static bool load_scene_blob(unsigned int scene)
{
    static const char hex[] = "0123456789ABCDEF";
    char name[12];
    const OotSceneBlob *blob = (const OotSceneBlob *)OOT_SCENECOL_ADDR;
    unsigned char *carve = (unsigned char *)ram_cart_fixed(RAM_CART_SCENECOL_OFFSET, RAM_CART_SCENECOL_BYTES);
    unsigned int used, i;
    int length;
    scene_object_count = 0;
    if (!asset_scene_name(name, scene, -1, "OOC")) return false;
    length = load_carve(name, RAM_CART_SCENECOL_OFFSET, RAM_CART_SCENECOL_BYTES);
    if (!length) return false;
    slCashPurge();
    /* Blob linked for another carve address: its pointers are garbage. */
    if (blob->col_header && (unsigned int)blob->col_header - OOT_SCENECOL_ADDR >= RAM_CART_SCENECOL_BYTES) return false;
    used = ((unsigned int)length + 15u) & ~15u;
    for (i = 0; i < blob->num_objects && i < SCENE_OBJECTS_MAX; ++i) {
        unsigned int id = blob->objects[i];
        char file[] = "O000.OOB";
        jo_file probe;
        file[1] = hex[(id >> 8) & 15]; file[2] = hex[(id >> 4) & 15]; file[3] = hex[id & 15];
        scene_objects[i] = 0;
        if (GFS_NameToId((Sint8 *)file) < 0 || !jo_fs_open(&probe, file)) continue;
        length = probe.size;
        jo_fs_close(&probe);
        if (length <= 0 || used + (unsigned int)length > RAM_CART_SCENECOL_BYTES ||
            !jo_fs_read_file_ptr(file, carve + used, &length)) continue;
        scene_objects[i] = (const void *)((unsigned int)(carve + used) & ~0x20000000u);
        used += ((unsigned int)length + 15u) & ~15u;
    }
    scene_object_count = i;
    slCashPurge();
    return true;
}

/* ---- Phase 2 draw shim: prebuilt meshes for the decomp's draw items ---- */

static void sprites_reset(void)
{
    unsigned int r;
    for (r = 0; r < CORE_SPRITE_ROWS; ++r) {
        if (core_sprite[r]) jo_free(core_sprite[r]);
        core_sprite[r] = 0;
        core_sprite_tried[r] = 0;
    }
    core_sprite_reserved = 0;
    memset(&sprite_stats, 0, sizeof sprite_stats);
}

/* Reconcile after an actual actor step, including later same-room spawns.
 * Existing sheets stay owned until room teardown. Each unavailable file is
 * attempted once per room, so an absent bake never creates a per-frame CD loop. */
static bool sprites_refresh(void)
{
    static const char hex[] = "0123456789ABCDEF";
    const OotCoreNpcView *v;
    int n = ENTRY->npc_view(&v), k;
    unsigned int r, pass, count = 0;
    bool changed = false;
    for (pass = 0; pass < 2; ++pass)
    for (r = 0; r < CORE_SPRITE_ROWS; ++r) {
        char file[] = "G00000.SPR";
        int length = 0;
        jo_file probe;
        if (core_sprite[r] || core_sprite_tried[r]) continue;
        /* One compatible sheet per object/skeleton, not every animation in
         * its library. Unused Ingo clips must not crowd later NPCs out. */
        unsigned int resident;
        for(resident=0;resident<CORE_SPRITE_ROWS;++resident)
            if(core_sprite[resident] && core_sprite_rows[resident].object==core_sprite_rows[r].object &&
               core_sprite_rows[resident].limbs==core_sprite_rows[r].limbs)break;
        if(resident<CORE_SPRITE_ROWS)continue;
        for (k = 0; k < n; ++k)
            if (v[k].object == core_sprite_rows[r].object &&
                (pass || core_sprite_rows[r].anim == (v[k].anim & 0xFFFFFFu))) break;
        if (k == n) continue;
        core_sprite_tried[r] = 1;
        file[1] = hex[(core_sprite_rows[r].object >> 8) & 15];
        file[2] = hex[(core_sprite_rows[r].object >> 4) & 15];
        file[3] = hex[core_sprite_rows[r].object & 15];
        file[4] = hex[core_sprite_rows[r].file >> 4];
        file[5] = hex[core_sprite_rows[r].file & 15];
        if (GFS_NameToId((Sint8 *)file) < 0 || !jo_fs_open(&probe, file)) continue;
        length = probe.size;
        jo_fs_close(&probe);
        if (length < 0x34) continue;
        /* Jo appends a NUL after the file, even for aligned SPR packets. */
        core_sprite[r] = (unsigned char *)jo_malloc((unsigned int)length + 1u);
        if (core_sprite[r] && jo_memory_usage_percent() > CORE_SPRITE_HEAP_PERCENT) {
            jo_free(core_sprite[r]); core_sprite[r] = 0;
        }
        if (core_sprite[r] &&
            (!jo_fs_read_file_ptr(file, core_sprite[r], &length) ||
             !npc_sprite_valid(core_sprite[r], (unsigned int)length))) {
            jo_free(core_sprite[r]); core_sprite[r] = 0;
        }
        if (core_sprite[r]) changed = true;
    }
    sprite_stats.actors = sprite_stats.missing = sprite_stats.fallback = 0;
    for (k = 0; k < n; ++k) {
        unsigned int found = 0, exact = 0;
        if (!v[k].object) continue; /* native C-owned views have no sprite package */
        ++sprite_stats.actors;
        for (r = 0; r < CORE_SPRITE_ROWS; ++r)
            if (core_sprite[r] && core_sprite_rows[r].object == v[k].object &&
                (!v[k].limbs || core_sprite_rows[r].limbs + 1u == v[k].limbs)) {
                found = 1;
                if (core_sprite_rows[r].anim == (v[k].anim & 0xFFFFFFu)) exact = 1;
            }
        if (found) { ++count; if (!exact) ++sprite_stats.fallback; }
        else ++sprite_stats.missing;
    }
    if (count > CORE_SPRITE_SLOTS) count = CORE_SPRITE_SLOTS;
    /* Retain room capacity when an actor disappears; camera visibility and
     * temporary deaths never reset the shared bank. */
    if (count > core_sprite_reserved) { core_sprite_reserved = count; changed = true; }
    return changed;
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
typedef struct {
    unsigned int key;
    uint32_t id;
    collision_triangle_t *tri;
    bg_mesh_t mesh;
} core_dyna_t;
static core_dyna_t core_dyna[OOT_CORE_DYNA_VIEWS_MAX];

static void core_dyna_drop(core_dyna_t *d, bool remove)
{
    if (remove && d->id != BG_NONE) bg_dyna_remove(d->id);
    if (d->tri) jo_free(d->tri);
    memset(d, 0, sizeof(*d));
}

static void core_dyna_reset(void)
{
    unsigned int i;
    /* scene_flow already cleared bg_dyna for the new scene */
    for (i = 0; i < OOT_CORE_DYNA_VIEWS_MAX; ++i) if (core_dyna[i].key) core_dyna_drop(&core_dyna[i], false);
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
        "ITMHKT.SPR", "ITMHKC.SPR", "ITMBGS.SPR", "ITMMIR.SPR", "ITMIRB.SPR", "ITMHOB.SPR", "ITMEXP.SPR" };
    bool adult = !save_state.link_age;
    unsigned int i;
    bool bomb = save_inventory_item(2) != 0xff, chu = save_inventory_item(8) != 0xff;
    bool hook = adult && save_inventory_item(9) != 0xff;
    bool need[TOOL_COUNT] = {
        adult && save_inventory_item(3) != 0xff, bomb, chu, !adult && save_inventory_item(12) != 0xff,
        hook, hook, false, false, false, false, bomb || chu }; /* held gear is Link's mesh */
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

static void tools_draw(void)
{
    const OotCoreToolView *v;
    int n = playing ? ENTRY->tool_view(&v) : 0, i;
    int32_t a[3], b[3];
    npc_sprite_shadow_off = 1;
    for (i = 0; i < n; ++i) {
        unsigned int band = pitch_band(v[i].pitch);
        switch (v[i].id) {
        case ACTOR_EN_ARROW: tool_put(TOOL_ARW, band, v[i].x, v[i].y, v[i].z, v[i].yaw); break;
        case ACTOR_EN_BOM:
            if (v[i].params) tool_put(TOOL_EXP, recomp_world_clock() / 2, v[i].x, v[i].y, v[i].z, 0);
            else { npc_sprite_shadow_off = v[i].held; tool_put(TOOL_BOM, 0, v[i].x, v[i].y, v[i].z, v[i].yaw);
                   npc_sprite_shadow_off = 1; }
            break;
        case ACTOR_EN_BOM_CHU: tool_put(TOOL_CHU, 0, v[i].x, v[i].y, v[i].z, v[i].yaw); break;
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

/* C enemies and props take the decomp tools' hits through the C contact
 * pass: one AT cylinder per live tool, with the tool's source dmgFlags. */
void oot_core_tool_register(void)
{
    const OotCoreToolView *v;
    int n = playing ? ENTRY->tool_view(&v) : 0, i;
    for (i = 0; i < n; ++i) {
        collider_t *c = &CORE_DRAW->tool_at[i];
        int r = v[i].radius ? v[i].radius : 6;
        if (!v[i].dmg || v[i].held) continue;
        memset(c, 0, sizeof *c);
        c->shape = COLSHAPE_CYLINDER;
        c->x = v[i].x; c->y = v[i].y - r; c->z = v[i].z;
        c->radius = (int16_t)r; c->height = (int16_t)(2 * r);
        c->at_type = AT_TYPE_PLAYER;
        c->at_dmg = v[i].dmg;
        c->at_damage = v[i].id == ACTOR_EN_BOM ? 4 : 2;
        c->ac_flags = COL_OUTSIDE_ACTOR;
        c->tag = (uint16_t)(0x7200 + i);
        c->attack_id = (uint16_t)(0x7200 + v[i].id);
        collide_set_at(c);
    }
}

/* C-button tool use by inventory slot. Ammo and magic (sMagicArrowCosts
 * 4/4/8) are C save state and are spent only when the actor spawned. */
bool oot_core_tool_use(unsigned int slot, const int32_t origin[3], uint16_t yaw, int16_t pitch)
{
    unsigned int item = save_inventory_item(slot), ammo = slot, cost = 0;
    int io[6];
    if (!playing || item == 0xff || CORE_DRAW->tool_bits & OOT_CORE_TOOL_HOLDING) return false;
    if (slot == 4 || slot == 10 || slot == 16) {
        ammo = 3;
        cost = slot == 16 ? 8 : 4;
        if (save_state.source_magic < cost) return false;
    }
    if ((ammo == 2 || ammo == 3 || ammo == 8) && !save_state.source_ammo[ammo]) return false;
    io[0] = (int)item; io[1] = origin[0]; io[2] = origin[1]; io[3] = origin[2];
    io[4] = yaw; io[5] = pitch;
    if (!ENTRY->tool(OOT_CORE_TOOL_USE, io)) return false;
    if (ammo == 2 || ammo == 3 || ammo == 8) --save_state.source_ammo[ammo];
    save_state.source_magic = (uint8_t)(save_state.source_magic - cost);
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

/* Arms_Hook pulling Link: this 30 Hz step's share of the 20 Hz velocity, Q8. */
bool oot_core_tool_pull(int32_t step_q8[3])
{
    unsigned int k;
    if (!playing || !(CORE_DRAW->tool_bits & OOT_CORE_TOOL_PULLING)) return false;
    for (k = 0; k < 3; ++k) step_q8[k] = CORE_DRAW->tool_pull[k] * 2 / 3;
    return true;
}

static void load_meshes(void)
{
    static const char hex[] = "0123456789ABCDEF";
    const OotCoreMeshKey *keys;
    int n = ENTRY->mesh_list(&keys), i;
    for (i = 0; i < (int)core_mesh_count; ++i) { actor_mesh_free(core_mesh[i]); core_mesh[i] = 0; }
    core_mesh_count = 0;
    for (i = 0; i < n && core_mesh_count < CORE_MESHES_MAX; ++i) {
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
        if (GFS_NameToId((Sint8 *)file) < 0) continue;
        core_mesh[core_mesh_count] = actor_mesh_load_static(file);
        if (!core_mesh[core_mesh_count]) continue;
        core_mesh_key[core_mesh_count] = *k;
        core_mesh_ready[core_mesh_count] = 0;
        core_mesh_count++;
    }
    sprites_reset();
    sprites_refresh();
    tools_load();
    npc_draw_reupload();
}

/* From world_props_draw_upload, after the bank reset: a mesh that does not
** fit is skipped (not drawn), never an error. */
void oot_core_meshes_upload(void)
{
    unsigned int i;
    for (i = 0; i < core_mesh_count; ++i)
        core_mesh_ready[i] = playing && actor_mesh_upload(core_mesh[i]);
#ifdef CORE_SPRITES
    {   /* slots sized for the scene's biggest cel; draw rebinds per sheet */
        const unsigned char *big = 0;
        unsigned int r, best = 0;
        sprite_stats.slots = 0;
        for (r = 0; r < CORE_SPRITE_ROWS; ++r) {
            const unsigned char *s = core_sprite[r];
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
    const OotCoreNpcView *v;
    int n = oot_core_npcs(&v), k;
    unsigned int r, used = 0;
    for (k = 0; k < n && used < CORE_SPRITE_SLOTS; ++k) {
        unsigned int chosen = CORE_SPRITE_ROWS;
        int dx = v[k].x - recomp_camera.x, dz = v[k].z - recomp_camera.z;
        if (!v[k].anim || !(v[k].flags & OOT_CORE_VIEW_DRAWN) ||
            dx < -2000 || dx > 2000 || dz < -2000 || dz > 2000) continue;
        for (r = 0; r < CORE_SPRITE_ROWS; ++r)
            if (core_sprite[r] && core_sprite_rows[r].object == v[k].object &&
                /* SkelAnime includes the root translation joint; the baked
                 * SkeletonHeader counts only actual limbs. */
                (!v[k].limbs || core_sprite_rows[r].limbs + 1u == v[k].limbs)) {
                if (chosen == CORE_SPRITE_ROWS) chosen = r;
                if (core_sprite_rows[r].anim == (v[k].anim & 0xFFFFFFu)) { chosen = r; break; }
            }
        if (chosen < CORE_SPRITE_ROWS &&
            npc_sprite_visible(core_sprite[chosen], v[k].x, v[k].y, v[k].z))
            npc_sprite_draw(core_sprite[chosen], &core_sprite_inst[used++], v[k].frame,
                            v[k].x, v[k].y, v[k].z, v[k].yaw);
    }
}
#endif

/* From world_props_draw: one prebuilt mesh per decomp draw item. */
void oot_core_meshes_draw(void)
{
    sprites_draw();
    tools_draw();
    const OotCoreDrawItem *items;
    int n = playing ? ENTRY->draw_items(&items) : 0, i;
    unsigned int m;
    for (i = 0; i < n; ++i) {
        const OotCoreDrawItem *it = &items[i];
        int dx = it->x - recomp_camera.x, dz = it->z - recomp_camera.z;
        if (dx < -2000 || dx > 2000 || dz < -2000 || dz > 2000) continue;
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
    unsigned short press = (unsigned short)((in->interact ? 0x8000u : 0u) | (in->cancel ? 0x4000u : 0u));
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

void oot_core_frame(const gameplay_input_t *in)
{
    unsigned int scene = scene_flow_scene();
    /* A panorama's bank room identifies its artwork, not an OoT actor room. */
    int room = scene_flow_is_interior() ? 0 : (int)kokiri_bank_room();
    if (!loaded || gameplay_is_paused()) return;
    if (scene != play_scene) {
        playing = false;
        sprites_reset();
        tools_free();
        core_dyna_reset();
        play_scene = scene;
        meshes_room = -1;
        if (!load_scene_blob(scene)) return;
        mirror_save(); /* age/time/flags before play_init picks the layer */
        playing = ENTRY->play_init(RAM_LOW(RAM_LOW_OOTPLAY_OFFSET), RAM_LOW_OOTPLAY_BYTES,
                                   scene_flow_entry()->oot_scene, (const void *)OOT_SCENECOL_ADDR,
                                   room,
                                   (short)recomp_link.x, (short)(recomp_link.y - RECOMP_LINK_EYE_HEIGHT),
                                   (short)recomp_link.z, (short)recomp_link_yaw) != 0;
        if (playing) {
            ENTRY->set_objects(scene_objects, scene_object_count);
#ifdef CORE_SPRITES
            ENTRY->set_flags(OOT_CORE_FLAG_NPC_SPRITES);
#endif
            /* Room actors do not exist yet. Actor_UpdateAll spawns/initializes
             * them on the first 20 Hz step; only then can npc_view name sheets. */
        }
        step_phase = 0;
    }
    if (!playing) return;
    sync_player();
    ENTRY->set_camera((short)recomp_yaw);
    send_input(in);
    mirror_save();
    ENTRY->set_room(room);
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
        unsigned int t0 = frame_timer_ticks();
        {
            int32_t hand[3];
            if (gameplay_link_point(18, hand)) ENTRY->tool(OOT_CORE_TOOL_HAND, (int *)hand);
        }
        ENTRY->update();
        core_dyna_sync();
        CORE_DRAW->tool_bits = (unsigned int)ENTRY->tool(OOT_CORE_TOOL_STATE, CORE_DRAW->tool_pull);
        update_us = frame_timer_ticks_to_us(frame_timer_ticks() - t0);
        if (meshes_room != room) {
            meshes_room = room;
            load_meshes();
        } else if (sprites_refresh()) npc_draw_reupload();
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
int oot_core_npcs(const OotCoreNpcView **out) { return playing ? ENTRY->npc_view(out) : 0; }
int oot_core_prop(short id, int x, int z) { return playing ? ENTRY->prop_query(id, x, z) : -1; }
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
    return playing ? ENTRY->transition_request(consume) : -1;
}
bool oot_core_ocarina_start(void) { return playing && ENTRY->ocarina(1) != 0; }
unsigned int oot_core_ocarina_state(void) { return playing ? ENTRY->ocarina(0) : 0; }
unsigned int oot_core_ocarina_note(void) { return playing ? ENTRY->ocarina(2) : 0; }
unsigned int oot_core_ocarina_song(void) { return playing ? ENTRY->ocarina(3) : 0; }
bool oot_core_ocarina_sun_allowed(void) { return playing && ENTRY->ocarina(4) != 0; }
bool oot_core_ocarina_sun_start(void) { return playing && ENTRY->ocarina(5) != 0; }
void oot_core_scene_restart(void) { playing = false; play_scene = ~0u; }

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

bool oot_core_is_loaded(void) { return loaded; }
bool oot_core_is_playing(void) { return playing; }
const OotCoreBench *oot_core_bench_result(void) { return &bench; }
unsigned int oot_core_update_us(void) { return update_us; }
int oot_core_actors(int category) { return playing ? ENTRY->actor_count(category) : 0; }
int oot_core_view(int category, OotCoreActorView *out, int max)
{
    return playing ? ENTRY->actor_view(category, out, max) : 0;
}
#endif
