/*
 * bg_* collision API over the core's real z_bgcheck (Player migration,
 * isolated: NOT in the makefile SRCS; links instead of
 * shared/lib/collision/kokiri_collision.c's bg_* once callers are ported).
 *
 * Same signatures and contract as kokiri_collision.h, so C callers do not
 * change. Storage the C library needed goes away: no scene triangle buffer,
 * no XZ index, no dyna carve (bg_dyna_init ignores its buffer). C props are
 * real core DynaPoly BgActors (oot_core_bg.cpp proxies); rider motion is the
 * source DynaPolyActor_UpdateCarriedActorPos/RotY.
 *
 * Proxy changes take effect at the next query (lookup rebuilt once, lazily),
 * matching the C library, where bg_dyna_set updated the world copy at once.
 * Frame boundary: bg_dyna_step makes current transforms previous. Once the
 * core's Play update owns that boundary, the host must stop calling it (one
 * owner only, or rider deltas are lost) - integration item.
 */
#include <stdbool.h>
#include <stdint.h>
#include <string.h>

#include "kokiri_collision.h"
#include "oot_core_bg.h"

static const OotCoreBgApi *api;
static bool dyna_dirty;
static uint8_t shim_owned[64];      /* core bgIds (< BG_ACTOR_MAX 50) registered here */
static uint16_t shim_tris[64];

/* One owner of the DynaPoly frame boundary (prev = cur). In the game the
 * core's Play update owns it (core_owns = true): bg_dyna_step then only
 * flushes pending proxy changes, so rider deltas are never consumed twice.
 * Host tests drive frames themselves (core_owns = false). */
static bool core_owns_frames;

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
        api->reset();
        memset(shim_owned, 0, sizeof shim_owned);
        memset(shim_tris, 0, sizeof shim_tris);
        dyna_dirty = true;
}

static void flush(void)
{
        if (dyna_dirty) {
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
        flush();
        to_int(pos, p);
        memset(&k, 0, sizeof k);
        y = api->floor(p, ignore, &k);
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
        flush();
        to_int(next, n);
        to_int(prev, p);
        memset(&k, 0, sizeof k);
        if (hit) hit->bg_id = BG_NONE;  /* C contract: set before the test */
        got = api->wall(r, n, p, radius, check_height, ignore, skip_line, &k) != 0;
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
        flush();
        to_int(pos, p);
        memset(&k, 0, sizeof k);
        got = api->ceiling(&y, p, check_height, ignore, &k) != 0;
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
        flush();
        to_int(a, pa);
        to_int(b, pb);
        memset(&k, 0, sizeof k);
        got = api->line(pa, pb, r, checks, ignore, &k) != 0;
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
        if (!api->poly_plane(hit->bg_id, hit->poly, n, &dist)) return -1;
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
        if (!api->poly_vertices(hit->bg_id, hit->poly, v)) return false;
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

const bg_mesh_t *bg_scene_mesh(void)
{
        OotCoreBgScene s;
        const core_bgcam_t *cams;
        const int16_t *base = 0, *top = 0;
        uint32_t i, n;
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
        return &scene_view;
}

/* The core owns the scene: loading/indexing the C copy is a no-op. */
void bg_scene_set(const bg_mesh_t *mesh) { (void)mesh; dyna_dirty = true; }
bool kokiri_collision_index(void *buffer, uint32_t bytes) { (void)buffer; (void)bytes; return true; }

bool bg_water_surface(int32_t x, int32_t z, uint32_t room, int32_t *surface,
        const bg_waterbox_t **box)
{
        OotCoreBgScene s;
        const bg_waterbox_t *w;
        uint32_t i;
        if (!api->scene(&s)) return false;
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
        return api->water_set(index, surface) != 0;
}

void bg_water_reset_surface(uint32_t index)
{
        api->water_reset(index);
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
        if (!mesh || mesh->triangle_count == 0) return BG_NONE;
        /* The core reads triangles, info and surfaces in place (no copy). */
        id = api->dyna_register(mesh->triangles, sizeof(collision_triangle_t), mesh->info,
                                mesh->triangle_count, (const unsigned *)mesh->surfaces,
                                mesh->surface_count, transform);
        if (id == OOT_CORE_BG_NONE || id >= sizeof shim_owned) return BG_NONE;
        shim_owned[id] = 1;
        shim_tris[id] = mesh->triangle_count;
        dyna_dirty = true;
        return id;
}

void bg_dyna_set(uint32_t id, const bg_vec_t *pos, uint16_t rot_y, int32_t scale_q16)
{
        int p[3];
        to_int(pos, p);
        api->dyna_set(id, p, rot_y, scale_q16);
        dyna_dirty = true;
}

void bg_dyna_enable(uint32_t id, bool enabled)
{
        api->dyna_enable(id, enabled);
        dyna_dirty = true;
}

void bg_dyna_remove(uint32_t id)
{
        if (id >= sizeof shim_owned || !shim_owned[id]) return;
        api->dyna_remove(id);
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
        if (!core_owns_frames) api->dyna_step();
}

bool bg_dyna_carry(uint32_t id, bg_vec_t *pos, uint16_t *yaw)
{
        int p[3];
        unsigned short y = yaw ? *yaw : 0;
        bool moved;
        flush();
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
