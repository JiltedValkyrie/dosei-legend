#include "oot_core_host.h"
#ifdef DOSEI_OOT_CORE
/* Glue, not per-vertex work: size over speed (work RAM). */
#pragma GCC optimize("Os")
#include <jo/jo.h>
#include "action_audio.h"
#include "demo.h"
#include "frame_timer.h"
#include "gameplay.h"
#include "kokiri_sgl.h"
#include "asset_names.h"
#include "scene_flow.h"
#include "ram_cart.h"
#include "ram_low.h"
#include "save_state.h"
#include "oot_scene_blob.h"
#include "actor_mesh.h"
#include "npc_draw.h"
#include <string.h>


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
/* Scene index the play state belongs to (or whose blob is missing/failed):
** a failed scene is not retried every frame. */
static unsigned int play_scene = 0xFFFFu;
static unsigned int step_phase;

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
    /* Boot progress on row 20: a hang leaves the last marker on screen. */
    jo_printf(0, 20, "oc 1 load ");
    loaded = load_carve("OOTCORE.BIN", RAM_CART_OOTCORE_OFFSET, RAM_CART_OOTCORE_BYTES);
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

/* C Link -> player proxy: demo_link is the eye, OoT pos is the feet.
** World units are OoT units (1:1). */
static void sync_player(void)
{
    ENTRY->set_player(demo_link.x, demo_link.y - DEMO_LINK_EYE_HEIGHT, demo_link.z,
                      (short)demo_link_yaw);
}

/* C save -> decomp mirror. Static: the blob keeps the pointer and copies
** flags back after each update. */
static void mirror_save(void)
{
    {
        /* Static: the blob keeps the pointer and copies flags back after update. */
        static OotCoreSave mirror;
        unsigned int save_scene = scene_flow_entry()->save_scene;
        mirror.link_age = 1;   /* LINK_AGE_CHILD: the C game has no adult yet */
        mirror.night = 0;      /* C game has no day/night clock yet */
        mirror.day_time = 0x8000; /* noon */
        mirror.event_chk_inf = save_state.event_chk_inf;
        mirror.item_get_inf = save_state.item_get_inf;
        mirror.inf_table = save_state.inf_table;
        mirror.scene_flags = save_scene < SAVE_SCENE_COUNT
            ? (unsigned long *)&save_state.scene[save_scene] : 0;
        mirror.health = save_state.health;
        mirror.health_capacity = save_state.health_capacity;
        mirror.rupees = save_state.rupees;
        mirror.stick_owned = save_state.stick_owned;
        mirror.stick_ammo = save_state.stick_ammo;
        mirror.nut_owned = save_state.nut_owned;
        mirror.nut_ammo = save_state.nut_ammo;
        mirror.slingshot_owned = save_state.slingshot;
        mirror.seed_ammo = save_state.ammo_seeds;
        memcpy(mirror.player_name, "Link    ", 8); /* no file name in the C save */
        mirror.generic_scene = save_scene >= SAVE_SCENE_COUNT;
        ENTRY->set_save(&mirror);
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
#define CORE_MESHES_MAX 40
static actor_mesh_t *core_mesh[CORE_MESHES_MAX];
static OotCoreMeshKey core_mesh_key[CORE_MESHES_MAX];
static unsigned char core_mesh_ready[CORE_MESHES_MAX];
static unsigned int core_mesh_count;

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
    npc_draw_reupload();
}

/* From world_props_draw_upload, after the bank reset: a mesh that does not
** fit is skipped (not drawn), never an error. */
void oot_core_meshes_upload(void)
{
    unsigned int i;
    for (i = 0; i < core_mesh_count; ++i)
        core_mesh_ready[i] = playing && actor_mesh_upload(core_mesh[i]);
}

/* From world_props_draw: one prebuilt mesh per decomp draw item. */
void oot_core_meshes_draw(void)
{
    const OotCoreDrawItem *items;
    int n = playing ? ENTRY->draw_items(&items) : 0, i;
    unsigned int m;
    for (i = 0; i < n; ++i) {
        const OotCoreDrawItem *it = &items[i];
        int dx = it->x - demo_camera.x, dz = it->z - demo_camera.z;
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
static void send_input(const gameplay_input_t *in)
{
    unsigned short press = (unsigned short)((in->interact ? 0x8000u : 0u) | (in->cancel ? 0x4000u : 0u));
    ENTRY->set_input(press, press, 0, (signed char)(in->menu_step < 0 ? 60 : in->menu_step > 0 ? -60 : 0));
}

void oot_core_frame(const gameplay_input_t *in)
{
    unsigned int scene = scene_flow_scene();
    if (!loaded) return;
    if (scene != play_scene) {
        playing = false;
        play_scene = scene;
        if (!load_scene_blob(scene)) return;
        mirror_save(); /* age/time/flags before play_init picks the layer */
        playing = ENTRY->play_init(RAM_LOW(RAM_LOW_OOTPLAY_OFFSET), RAM_LOW_OOTPLAY_BYTES,
                                   scene_flow_entry()->oot_scene, (const void *)OOT_SCENECOL_ADDR,
                                   (int)kokiri_bank_room(),
                                   (short)demo_link.x, (short)(demo_link.y - DEMO_LINK_EYE_HEIGHT),
                                   (short)demo_link.z, (short)demo_link_yaw) != 0;
        if (playing) {
            ENTRY->set_objects(scene_objects, scene_object_count);
            load_meshes();
        }
        step_phase = 0;
    }
    if (!playing) return;
    sync_player();
    ENTRY->set_camera((short)demo_yaw);
    send_input(in);
    mirror_save();
    ENTRY->set_room((int)kokiri_bank_room());
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
        {
            int dx, dz;   /* decomp actors pushing the player (En_Ko blockers) */
            ENTRY->player_push(&dx, &dz);
            demo_link.x += dx;
            demo_link.z += dz;
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

/* The decomp text box on the VDP2 text layer, in the C dialogue rows.
** VDP2 keeps text, so rows are reprinted only when the view changes and
** cleared once when the box closes. Returns true while it is up. */
#define OC_MSG_ROW 20
#define OC_MSG_ROWS (OOT_CORE_MSG_ROWS + 2)
bool oot_core_message_box(void)
{
    static unsigned short shown_serial;
    static bool was_active;
    /* z_message colour index -> Jo palette: white red green blue lightblue purple yellow black. */
    static const unsigned char colour_map[8] = { 0, 2, 3, 5, 5, 6, 4, 1 };
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
            jo_printf(0, row, "%-40s", "");
            for (c = 0; c < OOT_CORE_MSG_COLS; ) {
                unsigned int start = c, colour = v->colour[r][c] & 7;
                while (c < OOT_CORE_MSG_COLS && (v->colour[r][c] & 7) == colour) ++c;
                jo_printf_with_color(1 + (int)start + (choice_row ? 2 : 0), row, colour_map[colour],
                                     "%.*s", (int)(c - start), &v->text[r][start]);
            }
            if (choice_row)
                jo_printf(1, row, "%c", r + v->choices - v->rows == v->choice ? '>' : ' ');
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
