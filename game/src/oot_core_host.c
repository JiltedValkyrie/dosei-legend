#include "oot_core_host.h"
#ifdef DOSEI_OOT_CORE
#include <jo/jo.h>
#include "action_audio.h"
#include "demo.h"
#include "frame_timer.h"
#include "gameplay.h"
#include "kokiri_sgl.h"
#include "ram_cart.h"
#include "ram_low.h"
#include "save_state.h"

/* Decomp SceneId values (include/tables/scene_table.h) for scenes with a
** scene blob (tools/oot_core_import.py SCENE_COLLISION). */
#define OOT_SCENE_KOKIRI_FOREST 0x55

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
    default: return item; /* not in the C save yet: not given */
    }
    if (!save_item_give(give)) return item;
    gameplay.rupees = (uint8_t)save_state.rupees; /* HUD counter */
    return 0xFF;
}

/* Health_ChangeBy: 1/16 heart units; nonzero = still alive. */
static int host_health_change(short amount)
{
    if (amount >= 0) save_heal((unsigned int)amount);
    else save_damage((unsigned int)-amount);
    return save_state.health != 0;
}

static const OotCoreHost host = { host_sfx, host_give_item, host_health_change };

static OotCoreBench bench;
/* Last decomp update (Actor_UpdateAll etc.), microseconds. */
static unsigned int update_us;
static bool loaded;
static bool playing;
static unsigned int step_phase;

/* Read a disc file into a cache-through cart carve: zero the carve first
** (.bss is not in the file), refuse a file larger than the carve. */
static bool load_carve(const char *name, unsigned int offset, unsigned int bytes)
{
    unsigned char *carve = (unsigned char *)ram_cart_fixed(offset, bytes);
    jo_file probe;
    int length;
    unsigned int i;
    if (!carve || !jo_fs_open(&probe, name)) return false;
    length = probe.size;
    jo_fs_close(&probe);
    if (length <= 0 || length > (int)bytes) return false;
    for (i = 0; i < bytes; ++i) carve[i] = 0;
    return jo_fs_read_file_ptr(name, carve, &length) != JO_NULL;
}

bool oot_core_boot(void)
{
    /* Boot progress on row 20: a hang leaves the last marker on screen. */
    jo_printf(0, 20, "oc 1 load ");
    loaded = load_carve("OOTCORE.BIN", RAM_CART_OOTCORE_OFFSET, RAM_CART_OOTCORE_BYTES) &&
             load_carve("SPT04COL.BIN", RAM_CART_SCENECOL_OFFSET, RAM_CART_SCENECOL_BYTES);
    /* Code and data are used through the cached aliases: drop stale lines. */
    slCashPurge();
    loaded = loaded && ENTRY->magic == OOT_CORE_MAGIC && ENTRY->version == OOT_CORE_VERSION &&
             (unsigned int)ENTRY->end <= OOT_CORE_LOAD_ADDR + RAM_CART_OOTCORE_BYTES &&
             ENTRY->play_bytes() <= RAM_LOW_OOTPLAY_BYTES;
    if (!loaded) {
        jo_printf(0, 20, "oc load failed     ");
        return false;
    }
    jo_printf(0, 20, "oc 2 init  ");
    ENTRY->init(&host);
    jo_printf(0, 20, "oc 3 bench ");
    ENTRY->bench(&bench, frame_timer_ticks, frame_timer_ticks_to_us);
    jo_printf(0, 20, "                    ");
    return true;
}

/* C Link -> player proxy: demo_link is the eye, OoT pos is the feet.
** World units are OoT units (1:1). */
static void sync_player(void)
{
    ENTRY->set_player(demo_link.x, demo_link.y - DEMO_LINK_EYE_HEIGHT, demo_link.z,
                      (short)demo_link_yaw);
}

void oot_core_frame(void)
{
    if (!loaded) return;
    if (save_state.scene_id != SAVE_SCENE_KOKIRI_FOREST) {
        playing = false;
        return;
    }
    if (!playing) {
        playing = ENTRY->play_init(RAM_LOW(RAM_LOW_OOTPLAY_OFFSET), RAM_LOW_OOTPLAY_BYTES,
                                   OOT_SCENE_KOKIRI_FOREST, (const void *)OOT_SCENECOL_ADDR,
                                   (int)kokiri_scene_room(),
                                   (short)demo_link.x, (short)(demo_link.y - DEMO_LINK_EYE_HEIGHT),
                                   (short)demo_link.z, (short)demo_link_yaw) != 0;
        step_phase = 0;
        if (!playing) return;
    }
    sync_player();
    {
        OotCoreSave mirror;
        mirror.health = save_state.health;
        mirror.health_capacity = save_state.health_capacity;
        mirror.rupees = save_state.rupees;
        mirror.stick_owned = save_state.stick_owned;
        mirror.stick_ammo = save_state.stick_ammo;
        mirror.nut_owned = save_state.nut_owned;
        mirror.nut_ammo = save_state.nut_ammo;
        mirror.slingshot_owned = save_state.slingshot;
        mirror.seed_ammo = save_state.ammo_seeds;
        ENTRY->set_save(&mirror);
    }
    ENTRY->set_room((int)kokiri_scene_room());
    {
        int32_t base[3], tip[3];
        int live = gameplay_sword_active() && gameplay_blade_points(base, tip);
        ENTRY->set_sword(live, (const int *)base, (const int *)tip);
    }
    /* Decomp actors are written for 20 Hz; gameplay steps run at 30 Hz. */
    step_phase += 2;
    if (step_phase >= 3) {
        step_phase -= 3;
        unsigned int t0 = frame_timer_ticks();
        ENTRY->update();
        update_us = frame_timer_ticks_to_us(frame_timer_ticks() - t0);
    }
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
