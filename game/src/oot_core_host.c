#include "oot_core_host.h"
#ifdef DOSEI_OOT_CORE
#include <jo/jo.h>
#include "demo.h"
#include "frame_timer.h"
#include "ram_cart.h"
#include "ram_low.h"
#include "save_state.h"

/* Decomp SceneId values (include/tables/scene_table.h) for scenes with a
** collision blob (tools/oot_core_import.py SCENE_COLLISION). */
#define OOT_SCENE_KOKIRI_FOREST 0x55

#define ENTRY ((const OotCoreEntry *)OOT_CORE_LOAD_ADDR)

static OotCoreBench bench;
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
    ENTRY->init(NULL);
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
                                   (short)demo_link.x, (short)(demo_link.y - DEMO_LINK_EYE_HEIGHT),
                                   (short)demo_link.z, (short)demo_link_yaw) != 0;
        step_phase = 0;
        if (!playing) return;
    }
    sync_player();
    /* Decomp actors are written for 20 Hz; gameplay steps run at 30 Hz. */
    step_phase += 2;
    if (step_phase >= 3) {
        step_phase -= 3;
        ENTRY->update();
    }
}

bool oot_core_is_loaded(void) { return loaded; }
bool oot_core_is_playing(void) { return playing; }
const OotCoreBench *oot_core_bench_result(void) { return &bench; }
int oot_core_actors(int category) { return playing ? ENTRY->actor_count(category) : 0; }
#endif
