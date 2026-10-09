/*
 * bg_* collision API over the core's real z_bgcheck (Player migration phase
 * 2). Built with CORE_COLLISION instead of shared/lib/collision/
 * kokiri_collision.c; bg_core_link.c supplies the kokiri_collision_* Link
 * wrappers over these functions.
 *
 * Same signatures and contract as kokiri_collision.h, so C callers do not
 * change. Storage the C library needed goes away: no scene triangle buffer,
 * no XZ index, no dyna carve (bg_dyna_init ignores its buffer). C props are
 * real core DynaPoly BgActors (oot_core_bg.cpp proxies); rider motion is the
 * source DynaPolyActor_UpdateCarriedActorPos/RotY.
 *
 * Proxy changes take effect at the next query (lookup rebuilt once, lazily),
 * matching the C library, where bg_dyna_set updated the world copy at once.
 * Frame boundary: the core's Actor_UpdateAll makes current transforms
 * previous (bg_core_shim_frame_owner(true)); bg_dyna_step then only flushes.
 * A rider is carried once per core step: C steps between core steps would
 * apply the same delta again.
 * Before the scene's core collision exists every query misses.
 */
#include <stdbool.h>
#include <stdint.h>
#include <string.h>

#include "bg_core_shim.h"

static const OotCoreBgApi *api;
static bool dyna_dirty;
static uint8_t shim_owned[64];      /* core bgIds (< BG_ACTOR_MAX 50) registered here */
static uint16_t shim_tris[64];
/* Last transform/enable per proxy: props re-send unchanged values every frame,
 * and each change costs a whole DynaPoly_UpdateContext. valid 0 = unknown. */
typedef struct { int32_t pos[3], scale; uint16_t rot; uint8_t valid, enabled; } shim_xf_t;
static shim_xf_t shim_xf[64];

/* One owner of the DynaPoly frame boundary (prev = cur). In the game the
 * core's Play update owns it (core_owns = true): bg_dyna_step then only
 * flushes pending proxy changes, so rider deltas are never consumed twice.
 * Host tests drive frames themselves (core_owns = false). */
static bool core_owns_frames;
static unsigned carried_frame;
static bool scene_view_valid;

void bg_core_shim_set_api(const OotCoreBgApi *core)
{
        api = core;
        dyna_dirty = true;
}

void bg_core_shim_frame_owner(bool core_owns)
{
        core_owns_frames = core_owns;
}

/* Scene exit: shim ownership, core proxy slots and water bookkeeping reset
 * together. Call before the next scene's collision is installed. */
void bg_core_shim_scene_reset(void)
{
        if (api) api->reset();
        carried_frame = 0;
        scene_view_valid = false;
        memset(shim_owned, 0, sizeof shim_owned);
        memset(shim_tris, 0, sizeof shim_tris);
        memset(shim_xf, 0, sizeof shim_xf);
        dyna_dirty = true;
}

/* Diagnostics: host queries and dyna rebuilds since the last read. */
static uint32_t shim_queries, shim_rebuilds;
void bg_core_shim_counts(uint32_t *queries, uint32_t *rebuilds)
{
        *queries = shim_queries; *rebuilds = shim_rebuilds;
        shim_queries = shim_rebuilds = 0;
}

/* Async core update (oot_core_host.c): a host query while the slave runs
 * Actor_UpdateAll would read lists it is rebuilding. Refuse and count. */
static uint32_t shim_busy_hits;
uint32_t bg_core_shim_busy_hits(void) { uint32_t n = shim_busy_hits; shim_busy_hits = 0; return n; }
/* Weak: host tests link the shim without oot_core_host.c. */
extern bool oot_core_async_busy(void) __attribute__((weak));
#define SHIM_BUSY() (oot_core_async_busy && oot_core_async_busy() ? (++shim_busy_hits, 1) : 0)

static void flush(void)
{
        ++shim_queries;
        if (dyna_dirty && api) {
                ++shim_rebuilds;
                api->dyna_update();
                dyna_dirty = false;
        }
}

static void to_hit(const OotCoreBgHit *k, bg_hit_t *h)
{
        if (!h) return;
        h->normal[0] = k->normal[0];
        h->normal[1] = k->normal[1];
        h->normal[2] = k->normal[2];
        h->poly = k->poly;
        h->bg_id = k->bg_id;
        h->ignore = k->ignore;
        h->conveyor = k->conveyor;
        h->data0 = k->data0;
        h->data1 = k->data1;
}

static void to_int(const bg_vec_t *v, int out[3])
{
        out[0] = v->x;
        out[1] = v->y;
        out[2] = v->z;
}

int32_t bg_floor(const bg_vec_t *pos, uint32_t ignore, bg_hit_t *hit)
{
        int p[3];
        OotCoreBgHit k;
        int32_t y;
        if (SHIM_BUSY()) {
                if (hit) { hit->bg_id = BG_NONE; hit->data0 = hit->data1 = 0; }
                return BG_Y_MIN;
        }
        flush();
        to_int(pos, p);
        memset(&k, 0, sizeof k);
        y = api ? api->floor(p, ignore, &k) : BG_Y_MIN;
        if (y == BG_Y_MIN) {            /* C contract: miss clears owner and surface only */
                if (hit) { hit->bg_id = BG_NONE; hit->data0 = hit->data1 = 0; }
                return BG_Y_MIN;
        }
        to_hit(&k, hit);
        return y;
}

bool bg_wall(bg_vec_t *result, const bg_vec_t *next, const bg_vec_t *prev,
        int32_t radius, int32_t check_height, uint32_t ignore, bool skip_line,
        bg_hit_t *hit)
{
        int n[3], p[3], r[3];
        OotCoreBgHit k;
        bool got;
        if (SHIM_BUSY()) {
                *result = *next;
                if (hit) hit->bg_id = BG_NONE;
                return false;
        }
        flush();
        to_int(next, n);
        to_int(prev, p);
        memset(&k, 0, sizeof k);
        if (hit) hit->bg_id = BG_NONE;  /* C contract: set before the test */
        r[0] = n[0]; r[1] = n[1]; r[2] = n[2];
        got = api && api->wall(r, n, p, radius, check_height, ignore, skip_line, &k) != 0;
        result->x = r[0];
        result->y = r[1];
        result->z = r[2];
        if (got) to_hit(&k, hit);
        return got;
}

bool bg_ceiling(int32_t *out_y, const bg_vec_t *pos, int32_t check_height,
        uint32_t ignore, bg_hit_t *hit)
{
        int p[3], y;
        OotCoreBgHit k;
        bool got;
        if (SHIM_BUSY()) return false;
        flush();
        to_int(pos, p);
        memset(&k, 0, sizeof k);
        got = api && api->ceiling(&y, p, check_height, ignore, &k) != 0;
        if (!got) return false;         /* C contract: miss leaves outputs alone */
        *out_y = y;
        to_hit(&k, hit);
        return true;
}

bool bg_line(const bg_vec_t *a, const bg_vec_t *b, bg_vec_t *at,
        uint32_t checks, uint32_t ignore, bg_hit_t *hit)
{
        int pa[3], pb[3], r[3] = { 0, 0, 0 };
        OotCoreBgHit k;
        bool got;
        if (SHIM_BUSY()) return false;
        flush();
        to_int(a, pa);
        to_int(b, pb);
        memset(&k, 0, sizeof k);
        got = api && api->line(pa, pb, r, checks, ignore, &k) != 0;
        if (!got) return false;         /* C contract: miss leaves outputs alone */
        if (at) {
                at->x = r[0];
                at->y = r[1];
                at->z = r[2];
        }
        to_hit(&k, hit);
        return true;
}

/* D_80119D90 (z_bgcheck.c): wall type -> WALL_FLAG_*; types 8..31 are 0. */
static const uint8_t wall_type_flags[8] = {
        0, BG_WALL_FLAG_0, BG_WALL_FLAG_0 | BG_WALL_FLAG_1,
        BG_WALL_FLAG_0 | BG_WALL_FLAG_2, BG_WALL_FLAG_3,
        BG_WALL_CRAWLSPACE_1, BG_WALL_CRAWLSPACE_2, BG_WALL_FLAG_6,
};

uint32_t bg_wall_flags(const bg_hit_t *hit)
{
        uint32_t type = bg_wall_type(hit);
        return type < 8 ? wall_type_flags[type] : 0;
}

/* |plane distance| of pos from the hit poly, -1 if the poly is gone. */
int32_t bg_poly_plane_distance(const bg_hit_t *hit, const bg_vec_t *pos)
{
        short n[3];
        int dist;
        int32_t d;
        flush();
        if (!api || !api->poly_plane(hit->bg_id, hit->poly, n, &dist)) return -1;
        /* n is Q15 unit (32767); positions stay below 32768: fits 32 bits per
         * term pair, divide each term to keep the sum in range. */
        d = n[0] * pos->x / 32767 + n[1] * pos->y / 32767 + n[2] * pos->z / 32767 + dist;
        return d < 0 ? -d : d;
}

bool bg_poly_vertices(const bg_hit_t *hit, int16_t vertex[3][3])
{
        short v[3][3];
        int i, k;
        flush();
        if (!api || !api->poly_vertices(hit->bg_id, hit->poly, v)) return false;
        for (i = 0; i < 3; i++)
                for (k = 0; k < 3; k++)
                        vertex[i][k] = v[i][k];
        return true;
}

/* ---- scene data view: water boxes and bgCam settings, no triangles ---- */
typedef struct { uint16_t setting; int16_t count; const int16_t *data; } core_bgcam_t;
#define SHIM_CAMERAS 64
static bg_mesh_t scene_view;
static bg_camera_t scene_cameras[SHIM_CAMERAS];
/* scene_view_valid: built once per scene (it scans every poly). */

const bg_mesh_t *bg_scene_mesh(void)
{
        OotCoreBgScene s;
        const core_bgcam_t *cams;
        const int16_t *base = 0, *top = 0;
        uint32_t i, n;
        if (scene_view_valid) return &scene_view;
        if (!api || !api->scene(&s)) return 0;
        memset(&scene_view, 0, sizeof scene_view);
        scene_view.water = (const bg_waterbox_t *)s.water;
        scene_view.water_count = s.water_count;
        cams = (const core_bgcam_t *)s.cameras;
        n = s.camera_count < SHIM_CAMERAS ? s.camera_count : SHIM_CAMERAS;
        /* camera_vectors + first*3: rebase every data pointer on the lowest. */
        for (i = 0; i < n; i++) {
                if (cams[i].data && (!base || cams[i].data < base)) base = cams[i].data;
                if (cams[i].data && cams[i].data + cams[i].count * 3 > top)
                        top = cams[i].data + cams[i].count * 3;
        }
        for (i = 0; i < n; i++) {
                scene_cameras[i].setting = cams[i].setting;
                scene_cameras[i].count = cams[i].data ? cams[i].count : 0;
                scene_cameras[i].first = cams[i].data ? (uint32_t)((cams[i].data - base) / 3) : 0;
        }
        scene_view.cameras = scene_cameras;
        scene_view.camera_count = n;
        scene_view.camera_vectors = base;
        scene_view.camera_vector_count = base ? (uint32_t)((top - base) / 3) : 0;
        scene_view_valid = true;
        return &scene_view;
}

/* The core owns the scene: loading/indexing the C copy is a no-op. */
void bg_scene_set(const bg_mesh_t *mesh) { (void)mesh; dyna_dirty = true; }
bool kokiri_collision_index(void *buffer, uint32_t bytes) { (void)buffer; (void)bytes; return true; }
/* Water boxes are read from the core scene directly. */
void bg_water_bind(const bg_waterbox_t *water, uint32_t count) { (void)water; (void)count; }

int bg_core_fast_data(int mode)
{
        return api && api->version >= 3u && api->fast_data ? api->fast_data(mode) : 0;
}

bool bg_core_ready(void)
{
        return api && api->ready();
}

bool bg_core_sphere(const bg_vec_t *pos, int32_t radius, uint32_t ignore, bool skip_ceilings)
{
        int p[3];
        if (SHIM_BUSY()) return false;
        flush();
        to_int(pos, p);
        return api && api->sphere(p, radius, ignore, skip_ceilings) != 0;
}

int32_t bg_core_floor_class(const bg_vec_t *pos, uint32_t ignore)
{
        return bg_floor(pos, ignore | OOT_CORE_BG_FLOOR_ONLY, 0);
}

bool bg_water_surface(int32_t x, int32_t z, uint32_t room, int32_t *surface,
        const bg_waterbox_t **box)
{
        OotCoreBgScene s;
        const bg_waterbox_t *w;
        uint32_t i;
        if (SHIM_BUSY() || !api || !api->scene(&s)) return false;
        w = (const bg_waterbox_t *)s.water;
        for (i = 0; i < s.water_count; i++) {
                uint32_t r = BG_WATERBOX_ROOM(w[i].properties);
                if (r != room && r != BG_WATERBOX_ROOM_ALL) continue;
                if (w[i].properties & BG_WATERBOX_DISABLED) continue;
                if (w[i].x_min < x && x < w[i].x_min + w[i].x_length &&
                    w[i].z_min < z && z < w[i].z_min + w[i].z_length) {
                        *surface = w[i].y_surface;
                        if (box) *box = &w[i];
                        return true;
                }
        }
        return false;
}

bool bg_water_set_surface(uint32_t index, int32_t surface)
{
        return api && api->water_set(index, surface) != 0;
}

void bg_water_reset_surface(uint32_t index)
{
        if (api) api->water_reset(index);
}

/* ---- DynaPoly proxies ---- */
void bg_dyna_init(void *buffer, uint32_t bytes)
{
        (void)buffer;   /* no carve: the core's DynaPoly pool holds the copies */
        (void)bytes;
        bg_dyna_clear();
}

uint32_t bg_dyna_register(const bg_mesh_t *mesh, uint32_t transform)
{
        uint32_t id;
        if (!api || !mesh || mesh->triangle_count == 0) return BG_NONE;
        /* The core reads triangles, info and surfaces in place (no copy). */
        id = api->dyna_register(mesh->triangles, sizeof(collision_triangle_t), mesh->info,
                                mesh->triangle_count, (const unsigned *)mesh->surfaces,
                                mesh->surface_count, transform);
        if (id == OOT_CORE_BG_NONE || id >= sizeof shim_owned) return BG_NONE;
        shim_owned[id] = 1;
        shim_tris[id] = mesh->triangle_count;
        memset(&shim_xf[id], 0, sizeof shim_xf[id]);
        dyna_dirty = true;
        return id;
}

void bg_dyna_set(uint32_t id, const bg_vec_t *pos, uint16_t rot_y, int32_t scale_q16)
{
        int p[3];
        shim_xf_t *x = id < sizeof shim_owned ? &shim_xf[id] : 0;
        if (!api) return;
        if (x && x->valid & 1 && x->pos[0] == pos->x && x->pos[1] == pos->y &&
            x->pos[2] == pos->z && x->rot == rot_y && x->scale == scale_q16)
                return;
        to_int(pos, p);
        api->dyna_set(id, p, rot_y, scale_q16);
        if (x) {
                x->pos[0] = pos->x; x->pos[1] = pos->y; x->pos[2] = pos->z;
                x->rot = rot_y; x->scale = scale_q16; x->valid |= 1;
        }
        dyna_dirty = true;
}

void bg_dyna_enable(uint32_t id, bool enabled)
{
        shim_xf_t *x = id < sizeof shim_owned ? &shim_xf[id] : 0;
        if (!api) return;
        if (x && x->valid & 2 && x->enabled == enabled) return;
        api->dyna_enable(id, enabled);
        if (x) { x->enabled = enabled; x->valid |= 2; }
        dyna_dirty = true;
}

void bg_dyna_remove(uint32_t id)
{
        if (id >= sizeof shim_owned || !shim_owned[id]) return;
        if (api) api->dyna_remove(id);
        shim_owned[id] = 0;
        shim_tris[id] = 0;
        dyna_dirty = true;
}

void bg_dyna_clear(void)
{
        uint32_t id;
        for (id = 0; id < sizeof shim_owned; id++)
                if (shim_owned[id]) bg_dyna_remove(id);
}

void bg_dyna_step(void)
{
        flush();
        if (api && !core_owns_frames) api->dyna_step();
}

bool bg_dyna_carry(uint32_t id, bg_vec_t *pos, uint16_t *yaw)
{
        int p[3];
        unsigned short y = yaw ? *yaw : 0;
        bool moved;
        if (!api) return false;
        flush();
        if (core_owns_frames) {
                /* The delta is the last core step's motion: apply it once. */
                unsigned frame = api->frame();
                if (frame == carried_frame) return false;
                carried_frame = frame;
        }
        to_int(pos, p);
        moved = api->dyna_carry(id, p, yaw ? &y : 0) != 0;
        pos->x = p[0];
        pos->y = p[1];
        pos->z = p[2];
        if (yaw) *yaw = y;
        return moved;
}

uint32_t bg_dyna_triangles_used(void)
{
        uint32_t id, n = 0;
        for (id = 0; id < sizeof shim_owned; id++) n += shim_tris[id];
        return n;
}
