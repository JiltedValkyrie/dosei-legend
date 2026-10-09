/*
 * Core collision queries and C-prop DynaPoly proxies for the Saturn C side
 * (Player migration phase 2: OotCoreEntry.bg_api, live with CORE_COLLISION).
 *
 * Same contract as shared/lib/collision/kokiri_collision.h (feet positions,
 * world units, hit = owner-local poly, owner, raw SurfaceType), answered by
 * the real z_bgcheck on the core's CollisionContext. src/bg_core_shim.c
 * implements the C bg_* functions over OotCoreBg_Api(). Once every C caller
 * goes through it, the C scene buffer, its index and the dyna carve go away.
 * Integer world units in and out; Fx stays inside the core.
 */
#include "oot_prelude.h"
#include "ultra64.h"
#include "actor.h"
#include "bgcheck.h"
#include "play_state.h"
#include "z_math.h"
#include "oot_core_bg.h"
#include "zelda_arena.h"

/* z_bgcheck.c local raycast flags (not in a header). */
#define BGCHECK_RAYCAST_DOWN_CHECK_FLOORS (1 << 2)
#define BGCHECK_RAYCAST_DOWN_CHECK_WALLS_SIMPLE (1 << 3)
#define BGCHECK_RAYCAST_DOWN_CHECK_GROUND_ONLY (1 << 4)
/* z_bgcheck.c local SphVsFirstPoly flags. */
#define BGCHECK_IGNORE_NONE 0
#define BGCHECK_IGNORE_CEILING (1 << 0)
#define PROXY_TRANSFORM_POS 0x01   /* = BG_DYNA_POS */
#define PROXY_TRANSFORM_ROT_Y 0x02 /* = BG_DYNA_ROT_Y */

f32 BgCheck_RaycastDownImpl(PlayState* play, CollisionContext* colCtx, u16 xpFlags, CollisionPoly** outPoly,
                            s32* outBgId, Vec3f* pos, Actor* actor, u32 downChkFlags, f32 chkDist);
s32 BgCheck_CheckWallImpl(CollisionContext* colCtx, u16 xpFlags, Vec3f* posResult, Vec3f* posNext, Vec3f* posPrev,
                          f32 radius, CollisionPoly** outPoly, s32* outBgId, Actor* actor, f32 checkHeight, u8 argA);
s32 BgCheck_CheckCeilingImpl(CollisionContext* colCtx, u16 xpFlags, f32* outY, Vec3f* pos, f32 checkHeight,
                             CollisionPoly** outPoly, s32* outBgId, Actor* actor);
s32 BgCheck_CheckLineImpl(CollisionContext* colCtx, u16 xpFlags1, u16 xpFlags2, Vec3f* posA, Vec3f* posB,
                          Vec3f* posResult, CollisionPoly** outPoly, s32* outBgId, Actor* actor, f32 chkDist,
                          u32 bccFlags);
s32 BgCheck_SphVsFirstPolyImpl(CollisionContext* colCtx, u16 xpFlags, CollisionPoly** outPoly, s32* outBgId,
                               Vec3f* center, f32 radius, Actor* actor, u16 bciFlags);
s32 BgCheck_GetWaterSurface(PlayState* play, CollisionContext* colCtx, f32 x, f32 z, f32* outWaterSurface,
                            WaterBox** outWaterBox);
u32 SurfaceType_GetData(CollisionContext* colCtx, CollisionPoly* poly, s32 bgId, s32 dataIdx);
void DynaPolyActor_UpdateCarriedActorPos(CollisionContext* colCtx, s32 bgId, Actor* carriedActor);
void DynaPolyActor_UpdateCarriedActorRotY(CollisionContext* colCtx, s32 bgId, Actor* carriedActor);

static Vec3f vec(const int* p) {
    Vec3f v;
    v.x = p[0];
    v.y = p[1];
    v.z = p[2];
    return v;
}

static CollisionPoly* poly_of(CollisionContext* colCtx, u32 bgId, u32 poly) {
    if (bgId == OOT_CORE_BG_SCENE) {
        return poly < colCtx->colHeader->numPolygons ? &colCtx->colHeader->polyList[poly] : 0;
    }
    if (bgId >= BG_ACTOR_MAX || !(colCtx->dyna.bgActorFlags[bgId] & BGACTOR_IN_USE) ||
        poly >= colCtx->dyna.bgActors[bgId].colHeader->numPolygons) {
        return 0;
    }
    return &colCtx->dyna.polyList[colCtx->dyna.bgActors[bgId].dynaLookup.polyStartIndex + poly];
}

static void fill(CollisionContext* colCtx, CollisionPoly* poly, s32 bgId, OotCoreBgHit* hit) {
    if (hit == 0) {
        return;
    }
    if (poly == 0) {
        hit->bg_id = OOT_CORE_BG_NONE;
        return;
    }
    for (int i = 0; i < 3; i++) {
        s32 n = (&poly->normal.x)[i];
        hit->normal[i] = (s16)((n * 16384) / 32767);   /* Q15-ish unit -> Q14 */
    }
    /* C contract: index within the OWNER's mesh. Dyna polys live in one
     * shared pool; each BgActor's mesh starts at its polyStartIndex. */
    if (bgId == BGCHECK_SCENE) {
        hit->poly = (u16)(poly - colCtx->colHeader->polyList);
    } else {
        hit->poly = (u16)((poly - colCtx->dyna.polyList) - colCtx->dyna.bgActors[bgId].dynaLookup.polyStartIndex);
    }
    hit->bg_id = (u8)(bgId == BGCHECK_SCENE ? OOT_CORE_BG_SCENE : bgId);
    hit->ignore = (u8)((poly->flags_vIA >> 13) & 7);
    hit->conveyor = (u8)(COLPOLY_VTX_CHECK_FLAGS_ANY(poly->flags_vIB, COLPOLY_IS_FLOOR_CONVEYOR) != 0);
    hit->data0 = SurfaceType_GetData(colCtx, poly, bgId, 0);
    hit->data1 = SurfaceType_GetData(colCtx, poly, bgId, 1);
}

extern "C" {

/* bg_floor: entity raycast down (floors + ground-facing walls), static and dyna. */
int OotCoreBg_Floor(CollisionContext* colCtx, const int* pos, unsigned ignore, OotCoreBgHit* hit) {
    Vec3f p = vec(pos);
    CollisionPoly* poly = 0;
    s32 bgId = BGCHECK_SCENE;
    u32 flags = (ignore & OOT_CORE_BG_FLOOR_ONLY)
                    ? BGCHECK_RAYCAST_DOWN_CHECK_FLOORS
                    : BGCHECK_RAYCAST_DOWN_CHECK_WALLS_SIMPLE | BGCHECK_RAYCAST_DOWN_CHECK_FLOORS |
                          BGCHECK_RAYCAST_DOWN_CHECK_GROUND_ONLY;
    f32 y = BgCheck_RaycastDownImpl(NULL, colCtx, (u16)(ignore & 7), &poly, &bgId, &p, NULL, flags, FXL(1.0f));
    fill(colCtx, poly, bgId, hit);
    return (int)y;
}

/* bg_wall: sphere `radius` at check_height above the feet, prev -> next. */
int OotCoreBg_Wall(CollisionContext* colCtx, int* result, const int* next, const int* prev, int radius,
                   int checkHeight, unsigned ignore, int skipLine, OotCoreBgHit* hit) {
    Vec3f r, n = vec(next), pr = vec(prev);
    CollisionPoly* poly = 0;
    s32 bgId = BGCHECK_SCENE;
    s32 got = BgCheck_CheckWallImpl(colCtx, (u16)ignore, &r, &n, &pr, (f32)radius, &poly, &bgId, NULL,
                                    (f32)checkHeight, skipLine ? 1 : 0);
    result[0] = (int)r.x;
    result[1] = (int)r.y;
    result[2] = (int)r.z;
    fill(colCtx, got ? poly : 0, bgId, hit);
    return got != 0;
}

/* bg_ceiling: a ceiling within check_height; *outY = highest clear feet y. */
int OotCoreBg_Ceiling(CollisionContext* colCtx, int* outY, const int* pos, int checkHeight, unsigned ignore,
                      OotCoreBgHit* hit) {
    Vec3f p = vec(pos);
    f32 y = p.y;
    CollisionPoly* poly = 0;
    s32 bgId = BGCHECK_SCENE;
    s32 got = BgCheck_CheckCeilingImpl(colCtx, (u16)ignore, &y, &p, (f32)checkHeight, &poly, &bgId, NULL);
    *outY = (int)y;
    fill(colCtx, got ? poly : 0, bgId, hit);
    return got != 0;
}

/* bg_line: nearest crossing a -> b of the classes in `checks` (bit 0 wall,
 * 1 floor, 2 ceiling, 3 one face), dyna included. */
int OotCoreBg_Line(CollisionContext* colCtx, const int* a, const int* b, int* at, unsigned checks, unsigned ignore,
                   OotCoreBgHit* hit) {
    Vec3f pa = vec(a), pb = vec(b), out;
    CollisionPoly* poly = 0;
    s32 bgId = BGCHECK_SCENE;
    s32 got = BgCheck_CheckLineImpl(colCtx, (u16)ignore, COLPOLY_IGNORE_NONE, &pa, &pb, &out, &poly, &bgId, NULL,
                                    FXL(1.0f), (checks & 0xF) | (1 << 4));
    if (got) {
        at[0] = (int)out.x;
        at[1] = (int)out.y;
        at[2] = (int)out.z;
    }
    fill(colCtx, got ? poly : 0, bgId, hit);
    return got != 0;
}

/* bg_water_surface for the current room. */
int OotCoreBg_Water(PlayState* play, int x, int z, int* surface) {
    f32 y;
    WaterBox* box;
    if (!BgCheck_GetWaterSurface(play, &play->colCtx, (f32)x, (f32)z, &y, &box)) {
        return 0;
    }
    *surface = (int)y;
    return 1;
}

}

/* ------------------------------------------------------------------ table */
extern PlayState* gOotCorePlay;   /* oot_core_api.cpp; tests define their own */
static PlayState* sBgPlay;

extern "C" void OotCoreBg_SetPlay(PlayState* play) {
    sBgPlay = play;
}

static PlayState* play_of(void) {
    return sBgPlay ? sBgPlay : gOotCorePlay;
}

/* Scene collision present: between scenes every query misses. */
static PlayState* live(void) {
    PlayState* play = play_of();
    return play && play->colCtx.colHeader ? play : 0;
}

static int api_floor(const int pos[3], unsigned ignore, OotCoreBgHit* hit) {
    PlayState* play = live();
    if (!play) { fill(0, 0, 0, hit); return BGCHECK_Y_MIN; }
    return OotCoreBg_Floor(&play->colCtx, pos, ignore, hit);
}
static int api_wall(int result[3], const int next[3], const int prev[3], int radius, int checkHeight,
                    unsigned ignore, int skipLine, OotCoreBgHit* hit) {
    PlayState* play = live();
    if (!play) {
        result[0] = next[0]; result[1] = next[1]; result[2] = next[2];
        fill(0, 0, 0, hit);
        return 0;
    }
    return OotCoreBg_Wall(&play->colCtx, result, next, prev, radius, checkHeight, ignore, skipLine, hit);
}
static int api_ceiling(int* outY, const int pos[3], int checkHeight, unsigned ignore, OotCoreBgHit* hit) {
    PlayState* play = live();
    if (!play) { *outY = pos[1]; fill(0, 0, 0, hit); return 0; }
    return OotCoreBg_Ceiling(&play->colCtx, outY, pos, checkHeight, ignore, hit);
}
static int api_line(const int a[3], const int b[3], int at[3], unsigned checks, unsigned ignore,
                    OotCoreBgHit* hit) {
    PlayState* play = live();
    if (!play) { fill(0, 0, 0, hit); return 0; }
    return OotCoreBg_Line(&play->colCtx, a, b, at, checks, ignore, hit);
}
static int api_water(int x, int z, int* surface) {
    PlayState* play = live();
    return play ? OotCoreBg_Water(play, x, z, surface) : 0;
}
static int api_sphere(const int center[3], int radius, unsigned ignore, int skipCeilings) {
    PlayState* play = live();
    if (!play) return 0;
    Vec3f c = vec(center);
    CollisionPoly* poly = 0;
    s32 bgId = BGCHECK_SCENE;
    return BgCheck_SphVsFirstPolyImpl(&play->colCtx, (u16)ignore, &poly, &bgId, &c, (f32)radius, NULL,
                                      skipCeilings ? BGCHECK_IGNORE_CEILING : BGCHECK_IGNORE_NONE) != 0;
}
static unsigned api_frame(void) {
    PlayState* play = play_of();
    return play ? (unsigned)play->state.frames : 0;
}
static int api_ready(void) {
    return live() != 0;
}

/* Water level changes (puzzles): the first set saves the authored surface. */
#define WATER_SAVED_MAX 64
static s16 sWaterOrig[WATER_SAVED_MAX];
static u8 sWaterSaved[WATER_SAVED_MAX];

static int api_water_set(unsigned index, int surface) {
    PlayState* play = live();
    CollisionHeader* h = play ? play->colCtx.colHeader : 0;
    if (!h || index >= h->numWaterBoxes || index >= WATER_SAVED_MAX) {
        return 0;
    }
    if (!sWaterSaved[index]) {
        sWaterOrig[index] = h->waterBoxes[index].ySurface;
        sWaterSaved[index] = 1;
    }
    h->waterBoxes[index].ySurface = (s16)surface;
    return 1;
}
static void api_water_reset(unsigned index) {
    PlayState* play = live();
    CollisionHeader* h = play ? play->colCtx.colHeader : 0;
    if (h && index < h->numWaterBoxes && index < WATER_SAVED_MAX && sWaterSaved[index]) {
        h->waterBoxes[index].ySurface = sWaterOrig[index];
        sWaterSaved[index] = 0;
    }
}

static int api_poly_vertices(unsigned bgId, unsigned poly, short out[3][3]) {
    PlayState* play = live();
    if (!play) return 0;
    CollisionContext* col = &play->colCtx;
    CollisionPoly* p = poly_of(col, bgId, poly);
    if (!p) {
        return 0;
    }
    Vec3s* vtx = bgId == OOT_CORE_BG_SCENE ? col->colHeader->vtxList : col->dyna.vtxList;
    u16 idx[3] = { (u16)COLPOLY_VTX_INDEX(p->flags_vIA), (u16)COLPOLY_VTX_INDEX(p->flags_vIB), p->vIC };
    for (int i = 0; i < 3; i++) {
        out[i][0] = vtx[idx[i]].x;
        out[i][1] = vtx[idx[i]].y;
        out[i][2] = vtx[idx[i]].z;
    }
    return 1;
}

static int api_poly_plane(unsigned bgId, unsigned poly, short normal[3], int* dist) {
    PlayState* play = live();
    CollisionPoly* p = play ? poly_of(&play->colCtx, bgId, poly) : 0;
    if (!p) {
        return 0;
    }
    normal[0] = p->normal.x;
    normal[1] = p->normal.y;
    normal[2] = p->normal.z;
    *dist = p->dist;
    return 1;
}

/* --------------------------------------------------------------- proxies */
/* A C-owned prop becomes a real DynaPoly BgActor: its mesh is converted once
 * into a CollisionHeader in this static store, and a host-owned proxy actor
 * carries the C transform. Proxy id = the core bgId (what hits report). */
typedef struct Proxy {
    DynaPolyActor actor;
    CollisionHeader header;
    u16 triStart, triCount, surfStart, surfCount;
    u8 used, transform;
} Proxy;

#define PROXY_SURFACES 64
/* OOT_CORE_BG_PROXIES objects only (a full DynaPolyActor each); sProxyOf
 * maps a core bgId to its object (index + 1, 0 = not a proxy). */
static Proxy sProxies[OOT_CORE_BG_PROXIES];
static u8 sProxyOf[BG_ACTOR_MAX];
static Vec3s sProxyVtx[OOT_CORE_BG_PROXY_TRIS * 3];
static CollisionPoly sProxyPoly[OOT_CORE_BG_PROXY_TRIS];
static SurfaceType sProxySurf[PROXY_SURFACES];

static void ProxyUpdate(Actor*, PlayState*) {
    /* Never NULL: DynaPoly_UpdateContext deletes actors whose update is NULL. */
}

/* First fit in [0, cap) between ranges of live proxies. */
static int fit(u32 count, u32 cap, int surfaces, u32* start) {
    u32 cursor = 0;
    for (;;) {
        int next = -1;
        for (int i = 0; i < OOT_CORE_BG_PROXIES; i++) {
            if (!sProxies[i].used) continue;
            u32 s = surfaces ? sProxies[i].surfStart : sProxies[i].triStart;
            u32 n = surfaces ? sProxies[i].surfCount : sProxies[i].triCount;
            if (n && s >= cursor && (next < 0 || s < (surfaces ? sProxies[next].surfStart : sProxies[next].triStart))) {
                next = i;
            }
        }
        u32 end = next < 0 ? cap : (surfaces ? sProxies[next].surfStart : sProxies[next].triStart);
        if (end - cursor >= count) {
            *start = cursor;
            return 1;
        }
        if (next < 0) return 0;
        cursor = surfaces ? sProxies[next].surfStart + sProxies[next].surfCount
                          : sProxies[next].triStart + sProxies[next].triCount;
    }
}

static u32 isqrt(u32 v) {
    u32 r = 0, bit = 1u << 30;
    while (bit > v) bit >>= 2;
    while (bit) {
        if (v >= r + bit) { v -= r + bit; r = (r >> 1) + bit; } else { r >>= 1; }
        bit >>= 2;
    }
    return r;
}

/* tris: `count` elements of `stride` bytes, each starting with s16
 * vertex[3][3] (the C library's collision_triangle_t is read in place, no
 * copy). info: per-triangle surface/ignore/conveyor word (NULL = 0). */
static unsigned api_dyna_register(const void* tris, unsigned stride, const unsigned short* info, unsigned count,
                                  const unsigned* surfaces, unsigned surfaceCount, unsigned transform) {
    PlayState* play = live();
    u32 triStart, surfStart = 0;
    if (!play || count == 0 || count > OOT_CORE_BG_PROXY_TRIS || !fit(count, OOT_CORE_BG_PROXY_TRIS, 0, &triStart) ||
        (surfaceCount && !fit(surfaceCount, PROXY_SURFACES, 1, &surfStart))) {
        return OOT_CORE_BG_NONE;
    }
    Vec3s* vtx = &sProxyVtx[triStart * 3];
    CollisionPoly* polys = &sProxyPoly[triStart];
    s16 mn[3] = { 0x7FFF, 0x7FFF, 0x7FFF }, mx[3] = { -0x7FFF, -0x7FFF, -0x7FFF };
    for (u32 t = 0; t < count; t++) {
        const s16 (*sv)[3] = (const s16 (*)[3])((const u8*)tris + t * stride);
        u32 srcInfo = info ? info[t] : 0;
        for (int v = 0; v < 3; v++) {
            vtx[t * 3 + v].x = sv[v][0];
            vtx[t * 3 + v].y = sv[v][1];
            vtx[t * 3 + v].z = sv[v][2];
            for (int a = 0; a < 3; a++) {
                if (sv[v][a] < mn[a]) mn[a] = sv[v][a];
                if (sv[v][a] > mx[a]) mx[a] = sv[v][a];
            }
        }
        /* Model-space plane (DynaPoly recomputes it in world space). */
        s32 ax = sv[1][0] - sv[0][0], ay = sv[1][1] - sv[0][1],
            az = sv[1][2] - sv[0][2];
        s32 bx = sv[2][0] - sv[0][0], by = sv[2][1] - sv[0][1],
            bz = sv[2][2] - sv[0][2];
        s32 cx = ay * bz - az * by, cy = az * bx - ax * bz, cz = ax * by - ay * bx;
        while (cx > 0x7FFF || cx < -0x7FFF || cy > 0x7FFF || cy < -0x7FFF || cz > 0x7FFF || cz < -0x7FFF) {
            cx /= 2; cy /= 2; cz /= 2;
        }
        u32 mag = isqrt((u32)(cx * cx) + (u32)(cy * cy) + (u32)(cz * cz));
        CollisionPoly* p = &polys[t];
        p->type = (u16)(srcInfo & 0xFF);
        p->flags_vIA = (u16)((t * 3 + 0) | (((srcInfo >> 8) & 7) << 13));
        p->flags_vIB = (u16)((t * 3 + 1) | ((srcInfo >> 11) & 1 ? (COLPOLY_IS_FLOOR_CONVEYOR << 13) : 0));
        p->vIC = (u16)(t * 3 + 2);
        p->normal.x = mag ? (s16)(cx * 32767 / (s32)mag) : 0;
        p->normal.y = mag ? (s16)(cy * 32767 / (s32)mag) : 0x7FFF;
        p->normal.z = mag ? (s16)(cz * 32767 / (s32)mag) : 0;
        p->dist = (s16)(-(p->normal.x * sv[0][0] + p->normal.y * sv[0][1] + p->normal.z * sv[0][2]) / 32767);
    }
    for (u32 s = 0; s < surfaceCount; s++) {
        sProxySurf[surfStart + s].data[0] = surfaces[s * 2];
        sProxySurf[surfStart + s].data[1] = surfaces[s * 2 + 1];
    }
    Proxy tmp = {};
    tmp.header.minBounds.x = mn[0]; tmp.header.minBounds.y = mn[1]; tmp.header.minBounds.z = mn[2];
    tmp.header.maxBounds.x = mx[0]; tmp.header.maxBounds.y = mx[1]; tmp.header.maxBounds.z = mx[2];
    tmp.header.numVertices = (u16)(count * 3);
    tmp.header.vtxList = vtx;
    tmp.header.numPolygons = (u16)count;
    tmp.header.polyList = polys;
    tmp.header.surfaceTypeList = surfaceCount ? &sProxySurf[surfStart] : 0;
    /* The core needs the header at its final address: find the slot first. */
    s32 bgId = -1;
    for (int i = 0; i < BG_ACTOR_MAX; i++) {
        if (!(play->colCtx.dyna.bgActorFlags[i] & BGACTOR_IN_USE)) { bgId = i; break; }
    }
    int slot = -1;
    for (int i = 0; i < OOT_CORE_BG_PROXIES; i++) {
        if (!sProxies[i].used) { slot = i; break; }
    }
    if (bgId < 0 || slot < 0 || sProxyOf[bgId]) {
        return OOT_CORE_BG_NONE;
    }
    Proxy* px = &sProxies[slot];
    *px = tmp;
    px->actor.actor.update = ProxyUpdate;
    px->actor.actor.scale.x = 1;
    px->actor.actor.scale.y = 1;
    px->actor.actor.scale.z = 1;
    s32 got = DynaPoly_SetBgActor(play, &play->colCtx.dyna, &px->actor.actor, &px->header);
    if (got != bgId) {                      /* DynaPoly picks the same first free slot */
        *px = Proxy();
        return OOT_CORE_BG_NONE;
    }
    px->actor.bgId = got;
    px->triStart = (u16)triStart;
    px->triCount = (u16)count;
    px->surfStart = (u16)surfStart;
    px->surfCount = (u16)surfaceCount;
    px->transform = (u8)transform;
    /* Core riders (Player, actors) read the real DynaPolyActor flags via
     * DynaPolyActor_TransformCarriedActor: BG_DYNA_POS/ROT_Y = DYNA_TRANSFORM_*. */
    px->actor.transformFlags = (u8)(transform & (DYNA_TRANSFORM_POS | DYNA_TRANSFORM_ROT_Y));
    px->used = 1;
    sProxyOf[got] = (u8)(slot + 1);
    return (unsigned)got;
}

static Proxy* proxy(unsigned id) {
    return id < BG_ACTOR_MAX && sProxyOf[id] ? &sProxies[sProxyOf[id] - 1] : 0;
}

static void api_dyna_set(unsigned id, const int pos[3], unsigned short rotY, int scaleQ16) {
    Proxy* px = proxy(id);
    if (!px) return;
    Actor* a = &px->actor.actor;
    a->world.pos.x = pos[0];
    a->world.pos.y = pos[1];
    a->world.pos.z = pos[2];
    a->shape.rot.y = (s16)rotY;
    a->world.rot.y = (s16)rotY;
#ifdef OOT_CORE_HWFLOAT
    f32 s = (f32)scaleQ16 / 65536.0f;
#else
    f32 s = Fx::raw(scaleQ16);      /* Q16.16 is Fx's raw format */
#endif
    a->scale.x = s;
    a->scale.y = s;
    a->scale.z = s;
}

static void api_dyna_enable(unsigned id, int enabled) {
    PlayState* play = live();
    if (!play || !proxy(id)) return;
    if (enabled) {
        DynaPoly_EnableCollision(play, &play->colCtx.dyna, id);
    } else {
        DynaPoly_DisableCollision(play, &play->colCtx.dyna, id);
    }
}

static void api_dyna_remove(unsigned id) {
    PlayState* play = live();
    Proxy* px = proxy(id);
    if (!px) return;
    if (play) DynaPoly_DeleteBgActor(play, &play->colCtx.dyna, id);
    px->used = 0;
    px->triCount = 0;
    px->surfCount = 0;
    sProxyOf[id] = 0;
}

s32 DynaPolyActor_TransformCarriedActor(CollisionContext* colCtx, s32 bgId, Actor* carriedActor);

/* C rider: the same path core riders take (DynaPolyActor_TransformCarriedActor
 * reads the real transformFlags). Any live BgActor: proxies and real core
 * DynaPolyActors (buildings, platforms, the Kakariko gallery). */
static int api_dyna_carry(unsigned id, int pos[3], unsigned short* yaw) {
    PlayState* play = live();
    if (!play || id >= BG_ACTOR_MAX || !(play->colCtx.dyna.bgActorFlags[id] & BGACTOR_IN_USE)) return 0;
    Actor rider = {};
    rider.world.pos.x = pos[0];
    rider.world.pos.y = pos[1];
    rider.world.pos.z = pos[2];
    rider.shape.rot.y = yaw ? (s16)*yaw : 0;
    rider.world.rot.y = rider.shape.rot.y;
    if (!DynaPolyActor_TransformCarriedActor(&play->colCtx, (s32)id, &rider)) return 0;
    pos[0] = (int)rider.world.pos.x;
    pos[1] = (int)rider.world.pos.y;
    pos[2] = (int)rider.world.pos.z;
    if (yaw) *yaw = (unsigned short)rider.shape.rot.y;
    return 1;
}

/* Scene exit: drop every proxy and the water bookkeeping together. The new
 * scene's BgCheck_Allocate rebuilds the core context; nothing survives. */
static void api_reset(void) {
    PlayState* play = play_of();
    for (int i = 0; i < BG_ACTOR_MAX; i++) {
        if (sProxyOf[i] && play && (play->colCtx.dyna.bgActorFlags[i] & BGACTOR_IN_USE)) {
            DynaPoly_DeleteBgActor(play, &play->colCtx.dyna, i);
        }
        sProxyOf[i] = 0;
    }
    for (int i = 0; i < OOT_CORE_BG_PROXIES; i++) {
        sProxies[i] = Proxy();
    }
    /* Restore authored levels: the scene blob may stay resident across exit. */
    for (int i = 0; i < WATER_SAVED_MAX; i++) {
        api_water_reset((unsigned)i);
    }
}

static void api_dyna_step(void) {
    PlayState* play = live();
    if (play) DynaPoly_UpdateBgActorTransforms(play, &play->colCtx.dyna);
}

static void api_dyna_update(void) {
    PlayState* play = live();
    if (play) DynaPoly_UpdateContext(play, &play->colCtx.dyna);
}

static int api_scene(OotCoreBgScene* out) {
    PlayState* play = live();
    CollisionHeader* h = play ? play->colCtx.colHeader : 0;
    if (!h) return 0;
    out->water = h->waterBoxes;
    out->water_count = h->numWaterBoxes;
    out->cameras = h->bgCamList;
    u32 cams = 0;
    /* BgCamInfo has no count: bgCam indices come from surfaces; count the
     * highest index any static poly's surface names. */
    for (u32 i = 0; i < h->numPolygons; i++) {
        u32 cam = SurfaceType_GetData(&play->colCtx, &h->polyList[i], BGCHECK_SCENE, 0) & 0xFF;
        if (h->bgCamList && cam + 1 > cams) cams = cam + 1;
    }
    out->camera_count = cams;
    return 1;
}

static CollisionHeader sFastHeader;
static CollisionHeader* sCartHeader;
static void* sFastBlock;

static void copy16(void* to, const void* from, u32 bytes) {
    u16* d = (u16*)to;
    const u16* f = (const u16*)from;
    for (u32 i = 0; i < bytes / 2; i++) d[i] = f[i];
}

void OotCoreBg_FastReset(void) {
    sCartHeader = NULL;
    sFastBlock = NULL;
}

static int api_fast_data(int mode) {
    PlayState* play = play_of();
    CollisionContext* col;
    if (play == NULL || play->colCtx.colHeader == NULL) return 0;
    col = &play->colCtx;
    if (col->colHeader != &sFastHeader) sCartHeader = col->colHeader;
    if (mode < 0) return col->colHeader == &sFastHeader;
    if (mode == 0 || sCartHeader == NULL) {
        if (sCartHeader != NULL) col->colHeader = sCartHeader;
        return 0;
    }
    if (sFastBlock == NULL) {
        CollisionHeader* h = sCartHeader;
        u32 surfaces = 0, i, vb, pb, sb, maxFree, freeBytes, allocBytes;
        u8* p;
        for (i = 0; i < h->numPolygons; i++) {
            if (h->polyList[i].type + 1u > surfaces) surfaces = h->polyList[i].type + 1u;
        }
        vb = ALIGN16(h->numVertices * sizeof(Vec3s));
        pb = ALIGN16(h->numPolygons * sizeof(CollisionPoly));
        sb = ALIGN16(surfaces * sizeof(SurfaceType));
        ZeldaArena_GetSizes(&maxFree, &freeBytes, &allocBytes);
        if (h->surfaceTypeList == NULL || maxFree < vb + pb + sb + 0x18000u) return 0;
        p = (u8*)ZeldaArena_Malloc(vb + pb + sb);
        if (p == NULL) return 0;
        sFastHeader = *h;
        sFastHeader.vtxList = (Vec3s*)p;
        sFastHeader.polyList = (CollisionPoly*)(p + vb);
        sFastHeader.surfaceTypeList = (SurfaceType*)(p + vb + pb);
        copy16(sFastHeader.vtxList, h->vtxList, h->numVertices * sizeof(Vec3s));
        copy16(sFastHeader.polyList, h->polyList, h->numPolygons * sizeof(CollisionPoly));
        copy16(sFastHeader.surfaceTypeList, h->surfaceTypeList, surfaces * sizeof(SurfaceType));
        sFastBlock = p;
    }
    col->colHeader = &sFastHeader;
    return 1;
}

static const OotCoreBgApi sApi = {
    OOT_CORE_BG_VERSION, api_floor, api_wall, api_ceiling, api_line, api_water, api_water_set,
    api_water_reset, api_poly_vertices, api_poly_plane, api_dyna_register, api_dyna_set, api_dyna_enable,
    api_dyna_remove, api_dyna_carry, api_dyna_step, api_dyna_update, api_scene, api_reset,
    api_sphere, api_frame, api_ready, api_fast_data,
};

extern "C" const OotCoreBgApi* OotCoreBg_Api(void) {
    return &sApi;
}
