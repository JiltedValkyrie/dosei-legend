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
** sized for the largest set the format allows, checked at load time. */
#define SCENE_COLLISION_MAX   2048  /* triangles; spot04 has 1692 */
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
#define SCENE_COLLISION_INDEX_BYTES (16 * 1024)
static void                 *collision_index;
bool                         scene_collision_indexed;

/* World copies of actor-owned (DynaPoly) collision live in the cart's fixed
** carve (ram_cart.h), never the work-RAM arena jo_malloc would fill first. */
static bool                  dyna_ready;

/* SAVE_SCENE_* -> index into the scene table. The save records where the
** player is by the id the flag store uses, not by table position, so a scene
** can be inserted into the table without invalidating saved files. */
unsigned int    scene_flow_index_for_save(unsigned int save_scene)
{
    unsigned int i;

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

/* Read one scene's collision file into the shared buffer. */
static bool     collision_load(unsigned int scene)
{
    char        name[] = "S0.COL";
    void       *data;
    int         length = 0;
    uint32_t    need;

    if (scene >= ASSET_ID_LIMIT)
        return (false);
    name[1] = asset_name_digit(scene);
    data = jo_fs_read_file(name, &length);
    if (!data || length <= 0) {
        if (data) jo_free(data);
        return (false);
    }
    need = bg_mesh_bytes((const uint8_t *)data, (uint32_t)length);
    if (!need || need > SCENE_COLLISION_BYTES) {
        /* Refuse rather than truncate: half a scene's collision would let Link
        ** walk through walls in ways that look like a physics bug. */
        jo_free(data);
        return (false);
    }
    if (!collision_buffer) {
        collision_buffer = jo_malloc(SCENE_COLLISION_BYTES);
        if (!collision_buffer) { jo_free(data); return (false); }
    }
    if (!bg_mesh_decode((const uint8_t *)data, (uint32_t)length,
                        collision_buffer, SCENE_COLLISION_BYTES,
                        &collision_mesh) ||
        collision_mesh.triangle_count > SCENE_COLLISION_MAX) {
        jo_free(data);
        return (false);
    }
    jo_free(data);
    bg_scene_set(&collision_mesh);
    /* Actors own their dyna collision and are gone with the old scene. */
    if (!dyna_ready) {
        bg_dyna_init(ram_cart_fixed(RAM_CART_DYNA_OFFSET, RAM_CART_DYNA_BYTES),
                     RAM_CART_DYNA_BYTES);
        dyna_ready = true;
    }
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

bool            scene_flow_load(unsigned int scene, unsigned int spawn)
{
    const scene_entry_t *entry;

    if (scene >= SCENE_COUNT)
        return (false);
    entry = &scene_entries[scene];
    if (!collision_load(scene))
        return (false);
    if (entry->image) {
        /* A prerendered interior: one backdrop on VDP2, no geometry at all. */
        if (!kokiri_scene_load_backdrop(scene, 0))
            return (false);
    } else {
        if (!kokiri_scene_load_bank(scene, 0))
            return (false);
    }
    /* Area SFX follow the scene. A failed bank load leaves those sounds
    ** silent rather than blocking the scene. */
    action_audio_set_area(entry->sfx_bank);
    minimap_scene(entry->save_scene);
    current_scene = scene;
    loaded = true;
    door_armed = false;
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
    unsigned int i;

    if (!loaded)
        return (-1);
    for (i = 0; i < SCENE_DOOR_COUNT; ++i) {
        const scene_door_t *door = &scene_doors[i];
        int32_t             drop;

        if (door->scene != current_scene)
            continue;
        drop = y - door->y;
        if (drop < 0) drop = -drop;
        if (drop > SCENE_DOOR_HEIGHT)
            continue;
        if (inside_triangle(door, x, z))
            return (door_armed ? (int)i : -1);
    }
    /* Clear of every doorway: the next one Link steps onto may fire. */
    door_armed = true;
    return (-1);
}

/*
** END OF FILE
*/
