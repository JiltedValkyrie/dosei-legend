#pragma GCC optimize("Os") /* Cold text/load paths: scarce work RAM. */
/*
** Scene loading and the doors between scenes. Contract in scene_flow.h.
*/

#include <jo/jo.h>
#include "scene_flow.h"
#include "minimap.h"
#include "asset_names.h"
#include "action_audio.h"
#include "kokiri_sgl.h"
#include "kokiri_collision.h"
#include "ram_cart.h"
#include "actor_sys.h"
#include "npc_draw.h"
#include "tree_mouth.h"
#include "story_route.h"
#include "dungeon_doors.h"
#include "vdp1_draw_wait.h"
#include "oot_core_host.h"
#include "music_area.h"
#include "save_state.h"
#include "oot_follow.h"

static unsigned int current_scene;
static bool         loaded;
/* A doorway cannot fire until Link has stepped OFF every door triangle since
** the last transition. Without this, arriving on a spawn that overlaps the
** doorway you just came through sends you straight back, forever -- and the
** forest spawn outside Link's house sits right beside that very door. The
** original has the same requirement: you leave the exit polygon before it can
** trigger again. */
static bool         door_armed;

/* Collision for the loaded scene: S<n>.COL (KBG2) decoded into one buffer --
** triangles, per-triangle surface info, raw SurfaceTypes, water boxes and
** bgCams. Reused across scenes so a transition does not fragment the arena;
** sized to this scene's complete decoded data. New storage is admitted before
** replacing the old world; small scenes release the larger scene's storage. */
#ifndef CORE_COLLISION
#define SCENE_COLLISION_MAX   5096  /* largest retail source scene: ganontika */
#define SCENE_COLLISION_BYTES \
    (SCENE_COLLISION_MAX * (36 + 2) + 256 * 8 + 64 * 16 + 64 * 8 + 512 * 6)
static void                 *collision_buffer;
static bg_mesh_t             collision_mesh;

/* XZ lookup grid, so a movement query visits only nearby triangles instead of
** all 1692. It MUST be rebuilt after every bg_scene_set(): the index
** describes one particular triangle set, and a scene change replaces that set.
** Leaving a stale index behind is both wrong and slow -- it was why movement
** crawled after walking in and out of the house. Allocated once and reused,
** because the buffer has to outlive the collision data it indexes. */
#define SCENE_COLLISION_INDEX_BYTES (20 * 1024) /* retail maximum 19,774 B */
static void                 *collision_index;
bool                         scene_collision_indexed;

/* World copies of actor-owned (DynaPoly) collision live in the cart's fixed
** carve (ram_cart.h), never the work-RAM arena jo_malloc would fill first. */
static bool                  dyna_ready;
#else
/* CORE_COLLISION: the core scene (oot_core_scene_enter) is the only world;
** no C scene copy, index or dyna carve. */
bool                         scene_collision_indexed = true;
#endif

/* SAVE_SCENE_* -> index into the scene table. The save records where the
** player is by the id the flag store uses, not by table position, so a scene
** can be inserted into the table without invalidating saved files. */
unsigned int    scene_flow_index_for_save(unsigned int save_scene)
{
    unsigned int i;

    if(save_scene>=SAVE_SCENE_COUNT && save_state.source_scene<124)
        for(i=0;i<SCENE_COUNT;++i)
            if(scene_entries[i].oot_scene==save_state.source_scene)return i;
    for (i = 0; i < SCENE_COUNT; ++i)
        if (scene_entries[i].save_scene == save_scene)
            return (i);
    return (0);
}

unsigned int    scene_flow_scene(void)
{
    return (current_scene);
}

const scene_entry_t *scene_flow_entry(void)
{
    return (&scene_entries[current_scene < SCENE_COUNT ? current_scene : 0]);
}

bool            scene_flow_is_interior(void)
{
    return (loaded && scene_flow_entry()->image != 0);
}

/* Play_SetViewpoint: source house panoramas toggle against their locked JPEG.
 * The shop has FIXED_SHOP_VIEWPOINT and never accepts the toggle. */
bool scene_flow_pivot(void)
{
    return scene_flow_is_interior() && !kokiri_scene_backdrop_active();
}

bool scene_flow_toggle_view(void)
{
    bool pivot = scene_flow_pivot(), ok;
    if (!scene_flow_is_interior() || current_scene == SCENE_KOKIRI_SHOP ||
        scene_flow_entry()->panorama == 255)
        return false;
    if (!vdp1_wait_for_draw_end()) return false;
    ok = pivot ? kokiri_scene_load_backdrop(current_scene, 0) :
                 kokiri_scene_load_bank(STORY_BANK_PANORAMA, scene_flow_entry()->panorama);
    if (!ok) {
        /* A partial read can replace pixels. Restore the whole old view. */
        ok = pivot ? kokiri_scene_load_bank(STORY_BANK_PANORAMA, scene_flow_entry()->panorama) :
                     kokiri_scene_load_backdrop(current_scene, 0);
        if (!ok) jo_core_error("Interior view reload failed");
        return false;
    }
    return true;
}

/* Play_SetShopBrowsingViewpoint: talking to EnOssan switches the Kokiri
 * Shop to its pivot view (SKYBOX_KOKIRI_SHOP, bank 4) and back afterwards. */
bool scene_flow_shop_browse(bool on)
{
    bool ok;
    if (!scene_flow_is_interior() || current_scene != SCENE_KOKIRI_SHOP ||
        on == scene_flow_pivot())
        return false;
    if (!vdp1_wait_for_draw_end()) return false;
    ok = on ? kokiri_scene_load_bank(STORY_BANK_PANORAMA, scene_flow_entry()->panorama) :
              kokiri_scene_load_backdrop(current_scene, 0);
    if (!ok) {
        ok = on ? kokiri_scene_load_backdrop(current_scene, 0) :
                  kokiri_scene_load_bank(STORY_BANK_PANORAMA, scene_flow_entry()->panorama);
        if (!ok) jo_core_error("Shop view reload failed");
        return false;
    }
    return true;
}

const scene_spawn_t *scene_flow_spawn(unsigned int scene, unsigned int spawn)
{
    const scene_entry_t *entry;

    if (scene >= SCENE_COUNT)
        scene = 0;
    entry = &scene_entries[scene];
    if (spawn >= entry->spawns)
        spawn = 0;
    return (&scene_spawns[entry->first_spawn + spawn]);
}

#ifdef CORE_COLLISION
/* Actors own their dyna collision and are gone with the old scene; their
** core proxies are removed while the old PlayState still exists. */
static bool collision_load(unsigned int scene)
{
    (void)scene;
    tree_mouth_reset();dungeon_doors_reset();
    actor_sys_scene_unload();
    bg_dyna_clear();
    return (true);
}
#else
/* Read one scene's collision file into the shared buffer. */
static bool __attribute__((optimize("Os"))) collision_load(unsigned int scene)
{
    char        name[12];
    const void *data;
    void       *next_buffer, *old_buffer;
    bg_mesh_t   next_mesh;
    int         length = 0;
    uint32_t    need;

    if (!asset_scene_name(name, scene, -1, "COL"))
        return (false);
    /* The scene-load scratch is already reserved and larger than any COL.
     * Avoid a second whole-file heap allocation while two worlds overlap. */
    data = ram_cart_load_scratch(name, &length);
    if (!data || length <= 0) {
        return (false);
    }
    need = bg_mesh_bytes((const uint8_t *)data, (uint32_t)length);
    if (!need || need > SCENE_COLLISION_BYTES) {
        /* Refuse rather than truncate: half a scene's collision would let Link
        ** walk through walls in ways that look like a physics bug. */
        return (false);
    }
    next_buffer = jo_malloc(need);
    if (!next_buffer) return (false);
    if (!bg_mesh_decode((const uint8_t *)data, (uint32_t)length,
                        next_buffer, need, &next_mesh) ||
        next_mesh.triangle_count > SCENE_COLLISION_MAX) {
        jo_free(next_buffer);
        return (false);
    }
    old_buffer = collision_buffer;
    collision_buffer = next_buffer;
    collision_mesh = next_mesh;
    bg_scene_set(&collision_mesh);
    if (old_buffer) jo_free(old_buffer);
    /* Actors own their dyna collision and are gone with the old scene. */
    if (!dyna_ready) {
        bg_dyna_init(ram_cart_fixed(RAM_CART_DYNA_OFFSET, RAM_CART_DYNA_BYTES),
                     RAM_CART_DYNA_BYTES);
        dyna_ready = true;
    }
    tree_mouth_reset();dungeon_doors_reset();
    actor_sys_scene_unload();
    bg_dyna_clear();
    if (!collision_index)
        collision_index = jo_malloc(SCENE_COLLISION_INDEX_BYTES);
    /* Rebuild for THIS scene's triangles. Failure is survivable: the queries
    ** fall back to the original full scan, which is slower but correct. */
    scene_collision_indexed = collision_index &&
        kokiri_collision_index(collision_index, SCENE_COLLISION_INDEX_BYTES);
    return (true);
}
#endif

bool __attribute__((optimize("Os"))) scene_flow_load(unsigned int scene, unsigned int spawn)
{
    const scene_entry_t *entry;

    if (scene >= SCENE_COUNT)
        return (false);
    entry = &scene_entries[scene];
    if (scene_flow_spawn(scene, spawn)->room >= entry->rooms) return false;
    story_route_free();
    npc_draw_free();
    if (!kokiri_link_set_age(save_state.link_age == 0))
        return false;
    oot_follow_set_adult(save_state.link_age == 0);
    if (!collision_load(scene))
        return (false);
    /* Old core archives must not overlap the next scene's native models and
     * animation banks (Ranch SPR2 + Gohma exceeds the existing heap). */
    oot_core_scene_unload();
    music_area_trim();
    if (entry->image) {
        /* A prerendered interior: one backdrop on VDP2, no geometry at all. */
        /* Houses with source pivot cameras start on their panorama bank;
        ** fixed-view rooms and shops retain the original JPEG view. */
        unsigned int room = scene_flow_spawn(scene, spawn)->room;
        if (!(scene == SCENE_KOKIRI_SHOP || entry->panorama == 255 ?
              kokiri_scene_load_backdrop(scene, room) : kokiri_scene_load_bank(STORY_BANK_PANORAMA, entry->panorama)))
            return (false);
    } else {
        if (!kokiri_scene_load_bank(scene, scene_flow_spawn(scene, spawn)->room))
            return (false);
    }
    /* Area SFX follow the scene. A failed bank load leaves those sounds
    ** silent rather than blocking the scene. */
    action_audio_set_field(scene == SCENE_SPOT00);
    if (!action_audio_set_area(entry->sfx_bank) && scene == SCENE_SPOT00) {
        jo_core_error("Field sound bank load failed");
        return false;
    }
    minimap_scene(entry->save_scene);
    current_scene = scene;
    loaded = true;
    door_armed = false;
    if (!story_route_load(entry->save_scene) || !npc_draw_load(entry->save_scene)) {
        jo_core_error("NPC model load failed: scene %u", entry->save_scene);
        return false;
    }
#ifdef CORE_COLLISION
    /* Spawn placement and C props query collision right after this returns. */
    if (!oot_core_scene_enter(scene, spawn))
        return false;
#else
    oot_core_scene_restart();
#endif
    return (true);
}

/* Is (x,z) inside the triangle? Integer edge-sign test: a point is inside when
** it is on the same side of all three edges. Doorways are small, and the
** coordinates are well inside 16 bits, so the cross products fit a 32-bit int
** without the 64-bit maths the SH-2 would pay for. */
static bool     inside_triangle(const scene_door_t *door, int32_t x, int32_t z)
{
    int32_t     sign = 0;
    unsigned int i;

    for (i = 0; i < 3; ++i) {
        unsigned int j = (i + 1) % 3;
        int32_t ax = door->x[i], az = door->z[i];
        int32_t bx = door->x[j], bz = door->z[j];
        int32_t cross = (bx - ax) * (z - az) - (bz - az) * (x - ax);
        if (cross == 0)
            continue;               /* exactly on the edge: not disqualifying */
        if (sign == 0)
            sign = cross > 0 ? 1 : -1;
        else if ((cross > 0 ? 1 : -1) != sign)
            return (false);
    }
    return (true);
}

int             scene_flow_door_at(int32_t x, int32_t y, int32_t z)
{
    /* 2026-10-09 speed: the door table holds every scene's exits (1356) and
    ** this runs every game step; walk only the current scene's entries.
    ** Same tests in the same order. */
    static uint16_t     scene_list[128];
    static unsigned int scene_list_count;
    static unsigned int scene_list_for = ~0u;
    static bool         scene_list_overflow;
    unsigned int i, k;

    if (!loaded)
        return (-1);
    if (scene_list_for != current_scene) {
        scene_list_for = current_scene;
        scene_list_count = 0;
        scene_list_overflow = false;
        for (i = 0; i < SCENE_DOOR_COUNT; ++i) {
            if (scene_doors[i].scene != current_scene) continue;
            if (scene_list_count == 128) { scene_list_overflow = true; break; }
            scene_list[scene_list_count++] = (uint16_t)i;
        }
    }
    for (k = 0; scene_list_overflow ? k < SCENE_DOOR_COUNT : k < scene_list_count; ++k) {
        const scene_door_t *door;
        int32_t             drop;
        i = scene_list_overflow ? k : scene_list[k];
        door = &scene_doors[i];

        if (door->scene != current_scene || oot_core_scene_layer()>=32 ||
            !(door->layers&(1u<<oot_core_scene_layer())))
            continue;
        drop = y - door->y;
        if (drop < 0) drop = -drop;
        if (drop > SCENE_DOOR_HEIGHT)
            continue;
        if (inside_triangle(door, x, z))
            return (door_armed && dungeon_doors_exit_allowed(x,y,z) ? (int)i : -1);
    }
    /* Clear of every doorway: the next one Link steps onto may fire. */
    door_armed = true;
    return (-1);
}

/*
** END OF FILE
*/
