/* Scene-owned fixed code. Overlay entries stay internal, so decomp never
 * allocates, relocates or frees a pack as an N64 overlay. */
#include "oot_prelude.h"
#include "ultra64.h"
#include "actor.h"
#include "effect.h"
#include "play_state.h"
#include "path.h"
#include "bgcheck.h"
#include "z_actor_dlftbls.h"
#include "oot_actor_pack.h"
#include "oot_scene_blob.h"
#include "oot_core_host.h"

extern PlayState* gOotCorePlay;
extern "C" char oot_core_text_start[], oot_core_text_end[];
static const OotActorPackHeader* sPack;
extern const OotCoreHost* gOotCoreHost;
#ifndef OOT_CORE_LOAD_ADDR
#define OOT_CORE_LOAD_ADDR 0x02760000u
#endif
#ifndef OOT_SCENECOL_ADDR
#define OOT_SCENECOL_ADDR 0x02730000u
#endif
#ifndef OOT_SCENECOL_MAX_BYTES
#define OOT_SCENECOL_MAX_BYTES 0x40000u
#endif
#ifndef OOT_PACK_UNCACHED_ALIAS
#define OOT_PACK_UNCACHED_ALIAS 0x20000000u
#endif

static int pack_code(const OotActorPackHeader* h, const void* pointer, int core) {
    uintptr_t p = (uintptr_t)pointer;
    if (!p) return true; /* optional actor callbacks */
    if (p & 1u) return false;
    if (p >= h->link_base + h->text_offset &&
        p - (h->link_base + h->text_offset) < h->text_bytes) return true;
    return core && p >= (uintptr_t)oot_core_text_start && p < (uintptr_t)oot_core_text_end;
}

static int pack_profiles(const OotActorPackHeader* h) {
    const u8* base = (const u8*)h;
    for (u32 kind = 0; kind < 2; ++kind) {
        const OotActorPackProfile* rows = (const OotActorPackProfile*)
            (base + (kind ? h->effects_offset : h->actors_offset));
        u32 count = kind ? h->effect_count : h->actor_count;
        for (u32 i = 0; i < count; ++i) {
            u32 id = rows[i].id, pointer = rows[i].profile;
            u32 size = kind ? sizeof(EffectSsProfile) : sizeof(ActorProfile);
            if (id >= (kind ? EFFECT_SS_TYPE_MAX : ACTOR_ID_MAX) || (pointer & 3u) ||
                pointer < h->link_base + h->text_offset + h->text_bytes ||
                !OotActorPack_Range(pointer - h->link_base, 1, size, h->ctors_offset)) return false;
            for (u32 j = 0; j < i; ++j) if (rows[j].id == id) return false;
            if (kind) {
                const EffectSsProfile* profile = (const EffectSsProfile*)(uintptr_t)pointer;
                if (gEffectSsOverlayTable[id].profile || profile->type != id || !profile->init ||
                    !pack_code(h, (const void*)profile->init, true)) return false;
            } else {
                const ActorProfile* profile = (const ActorProfile*)(uintptr_t)pointer;
                if (gActorOverlayTable[id].profile || gActorOverlayTable[id].numLoaded ||
                    (u32)profile->id >= ACTOR_ID_MAX || profile->category >= ACTORCAT_MAX ||
                    profile->instanceSize < sizeof(Actor) || profile->instanceSize > 0x20000u ||
                    !pack_code(h, (const void*)profile->init, true) ||
                    !pack_code(h, (const void*)profile->destroy, true) ||
                    !pack_code(h, (const void*)profile->update, true) ||
                    !pack_code(h, (const void*)profile->draw, true)) return false;
            }
        }
    }
    return true;
}

int OotCore_PackBind(void* image, unsigned int bytes, unsigned int core_crc) {
    OotActorPackHeader* h = (OotActorPackHeader*)image;
    if (gOotCorePlay || sPack || !h || bytes < sizeof(*h) ||
        h->link_base != (uintptr_t)image ||
        !OotActorPack_HeaderValid(h, bytes, OOT_SCENECOL_ADDR, OOT_SCENECOL_MAX_BYTES, 0, core_crc) ||
        OotActorPack_Crc(image, bytes, true) != h->crc || !pack_profiles(h)) return false;
    const u32* ctors = (const u32*)((u8*)image + h->ctors_offset);
    for (u32 i = 0; i < h->ctor_count; ++i) {
        if (!ctors[i] || !pack_code(h, (const void*)(uintptr_t)ctors[i], false)) return false;
    }
    /* All validation completes before mutable state, callbacks or publication. */
    for (u32 i = h->bss_offset; i < h->memory_bytes; ++i) ((u8*)image)[i] = 0;
    for (u32 i = 0; i < h->ctor_count; ++i) ((void (*)(void))(uintptr_t)ctors[i])();
    if (!pack_profiles(h)) return false;
    for (u32 kind = 0; kind < 2; ++kind) {
        const OotActorPackProfile* rows = (const OotActorPackProfile*)
            ((u8*)image + (kind ? h->effects_offset : h->actors_offset));
        u32 count = kind ? h->effect_count : h->actor_count;
        for (u32 i = 0; i < count; ++i) {
            if (kind) {
                EffectSsOverlay* entry = &gEffectSsOverlayTable[rows[i].id];
                entry->vramStart = entry->vramEnd = entry->loadedRamAddr = NULL;
                entry->profile = (EffectSsProfile*)(uintptr_t)rows[i].profile;
            } else {
                ActorOverlay* entry = &gActorOverlayTable[rows[i].id];
                entry->vramStart = entry->vramEnd = entry->loadedRamAddr = NULL;
                entry->profile = (ActorProfile*)(uintptr_t)rows[i].profile;
                entry->numLoaded = 0;
            }
        }
    }
    sPack = h;
    return true;
}

int OotCore_PackRelease(void) {
    /* play_destroy owns all callbacks and counts. Never trust a refcount alone:
     * effects, actor action functions and collider tables also refer to code. */
    if (gOotCorePlay) return false;
    if (!sPack) return true;
    const u8* base = (const u8*)sPack;
    const OotActorPackProfile* actors = (const OotActorPackProfile*)(base + sPack->actors_offset);
    const OotActorPackProfile* effects = (const OotActorPackProfile*)(base + sPack->effects_offset);
    for (u32 i = 0; i < sPack->actor_count; ++i) {
        if (gActorOverlayTable[actors[i].id].numLoaded) return false;
    }
    for (u32 i = 0; i < sPack->actor_count; ++i) gActorOverlayTable[actors[i].id].profile = NULL;
    for (u32 i = 0; i < sPack->effect_count; ++i) gEffectSsOverlayTable[effects[i].id].profile = NULL;
    sPack = NULL;
    return true;
}

static int scene_range(const void* pointer, u32 count, u32 stride, u32 align, u32 bytes) {
    uintptr_t p = (uintptr_t)pointer;
    if (!pointer) return count == 0;
    return !(p & (align - 1u)) && p >= OOT_SCENECOL_ADDR &&
        p - OOT_SCENECOL_ADDR <= bytes &&
        OotActorPack_Range(p - OOT_SCENECOL_ADDR, count, stride, bytes);
}

static int scene_valid(const OotSceneBlob* blob, u32 bytes) {
    if (blob->format != OOT_SCENE_BLOB_FORMAT || blob->num_rooms > OOT_SCENE_MAX_ROOMS ||
        blob->num_layers > bytes / sizeof(OotSceneLayer) ||
        (blob->num_rooms && !blob->num_layers) || blob->num_objects > 16 ||
        !scene_range(blob->objects, blob->num_objects, 2, 2, bytes) ||
        !scene_range(blob->layers, blob->num_rooms * blob->num_layers, sizeof(OotSceneLayer), 4, bytes) ||
        !scene_range(blob->paths, blob->num_path_layers, sizeof(OotSceneLayer), 4, bytes) ||
        !scene_range(blob->transitions, blob->num_transition_layers, sizeof(OotSceneLayer), 4, bytes)) return false;
    for (u32 i = 0; i < blob->num_transition_layers; ++i) {
        const OotSceneLayer* row = &blob->transitions[i];
        if (row->num_actors > 255 ||
            !scene_range(row->actors, row->num_actors, 16, 2, bytes)) return false;
    }
    for (u32 i = 0; i < blob->num_rooms * blob->num_layers; ++i) {
        const OotSceneLayer* row = &blob->layers[i];
        if (!scene_range(row->actors, row->num_actors, sizeof(ActorEntry), 2, bytes)) return false;
    }
    for (u32 i = 0; i < blob->num_path_layers; ++i) {
        const OotSceneLayer* row = &blob->paths[i];
        /* Older OOCs have zero count; validate at least their first Path.
         * Current importer records full array counts in the formerly unused word. */
        u32 count = row->num_actors ? row->num_actors : (row->actors ? 1u : 0u);
        if (!scene_range(row->actors, count, sizeof(Path), 4, bytes)) return false;
        const Path* paths = (const Path*)row->actors;
        for (u32 j = 0; j < count; ++j)
            if (!scene_range(paths[j].points, paths[j].count, sizeof(Vec3s), 2, bytes)) return false;
    }
    if (blob->col_header) {
        if (!scene_range(blob->col_header, 1, sizeof(CollisionHeader), 4, bytes)) return false;
        const CollisionHeader* col = (const CollisionHeader*)blob->col_header;
        if (!scene_range(col->vtxList, col->numVertices, sizeof(Vec3s), 2, bytes) ||
            !scene_range(col->polyList, col->numPolygons, sizeof(CollisionPoly), 2, bytes) ||
            !scene_range(col->waterBoxes, col->numWaterBoxes, sizeof(WaterBox), 2, bytes) ||
            !scene_range(col->surfaceTypeList, col->numPolygons ? 1 : 0, sizeof(SurfaceType), 4, bytes) ||
            !scene_range(col->bgCamList, col->bgCamList ? 1 : 0, sizeof(BgCamInfo), 4, bytes)) return false;
    }
    return true;
}

/* Cold scene IO/validation lives in the cart core, where there is code space.
 * The host owns CD operations/cache purge; all pointers published here use the
 * cached alias. Nothing is published on a partial read or failed admission. */
int OotCore_SceneLoad(unsigned int scene, const char* name, unsigned int core_crc,
                      const void* const** objects, unsigned int* count) {
    static const char hex[] = "0123456789ABCDEF";
    static const void* loaded_objects[16];
    u8* carve = (u8*)(OOT_SCENECOL_ADDR | OOT_PACK_UNCACHED_ALIAS);
    const OotSceneBlob* blob = (const OotSceneBlob*)OOT_SCENECOL_ADDR;
    OotActorPackHeader h;
    char pack_name[12];
    u32 used, limit = OOT_SCENECOL_MAX_BYTES, i;
    int length, pack_bytes;
    *objects = NULL; *count = 0;
    if (!gOotCoreHost || !gOotCoreHost->scene_file || !OotCore_PackRelease()) return -1;
    length = gOotCoreHost->scene_file(name, NULL, 0);
    if (!length) return 0; /* legacy scene without an OOC */
    if (length < (int)sizeof(*blob) || (u32)length > limit) return -1;
    for (i = 0; i < limit; ++i) carve[i] = 0;
    if (gOotCoreHost->scene_file(name, carve, length) != length) return -1;
    if (!scene_valid(blob, length)) return -1;
    used = ((u32)length + 15u) & ~15u;
    for (i = 0; i < sizeof(pack_name) - 1 && name[i]; ++i) pack_name[i] = name[i];
    if (i < 4 || name[i]) return -1;
    pack_name[i] = 0; pack_name[i - 2] = 'A'; pack_name[i - 1] = 'P';
    pack_bytes = gOotCoreHost->scene_file(pack_name, NULL, 0);
    if (pack_bytes < 0) return -1;
    if (pack_bytes) {
        if (pack_bytes < (int)sizeof(h) ||
            gOotCoreHost->scene_file(pack_name, &h, sizeof(h)) != sizeof(h) ||
            h.scene != scene || (h.flags & OOT_ACTOR_PACK_TEST) ||
            !OotActorPack_HeaderValid(&h, pack_bytes, OOT_SCENECOL_ADDR,
                                     OOT_SCENECOL_MAX_BYTES, used, core_crc)) return -1;
        limit -= h.memory_bytes;
    }
    for (i = 0; i < blob->num_objects; ++i) {
        u32 id = blob->objects[i];
        char file[] = "O000.OOB";
        file[1] = hex[(id >> 8) & 15]; file[2] = hex[(id >> 4) & 15]; file[3] = hex[id & 15];
        loaded_objects[i] = NULL;
        length = gOotCoreHost->scene_file(file, NULL, 0);
        if (length <= 0) { if (pack_bytes) return -1; else continue; }
        if (used > limit || (u32)length > limit - used ||
            (((u32)length + 15u) & ~15u) > limit - used) return -1;
        if (gOotCoreHost->scene_file(file, carve + used, length) != length) return -1;
        loaded_objects[i] = (const void*)(uintptr_t)(OOT_SCENECOL_ADDR + used);
        used += ((u32)length + 15u) & ~15u;
    }
    if (pack_bytes) {
        if (gOotCoreHost->scene_file(pack_name, carve + limit, pack_bytes) != pack_bytes ||
            !OotCore_PackBind((void*)(uintptr_t)(OOT_SCENECOL_ADDR + limit), pack_bytes, core_crc)) return -1;
    }
    *objects = loaded_objects; *count = blob->num_objects;
    return 1;
}
