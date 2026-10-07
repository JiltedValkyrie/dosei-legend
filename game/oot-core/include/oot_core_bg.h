/*
 * Core collision API for the Saturn C side (Player migration, isolated: the
 * live blob does not export it yet). C callers keep shared/lib/collision's
 * bg_* functions; src/bg_core_shim.c implements them over this table, so the
 * C scene buffer, its index and the dyna carve can be retired.
 * Integer world units; feet positions; Y up.
 */
#ifndef OOT_CORE_BG_H
#define OOT_CORE_BG_H

#ifdef __cplusplus
extern "C" {
#endif

#define OOT_CORE_BG_VERSION 1u
#define OOT_CORE_BG_SCENE 50
#define OOT_CORE_BG_NONE 0xFF
#define OOT_CORE_BG_PROXIES 16       /* = BG_DYNA_MAX in the C library */
#define OOT_CORE_BG_PROXY_TRIS 128   /* all proxies together (static store) */

typedef struct OotCoreBgHit {
    short normal[3];          /* Q14, world space */
    unsigned short poly;      /* index in the OWNER's mesh */
    unsigned char bg_id;      /* OOT_CORE_BG_SCENE, proxy id, or OOT_CORE_BG_NONE */
    unsigned char ignore;     /* COLPOLY_IGNORE_* */
    unsigned char conveyor;   /* COLPOLY_IS_FLOOR_CONVEYOR */
    unsigned int data0, data1;
} OotCoreBgHit;

/* One proxy triangle: model-space vertices, surface index, ignore flags and
 * conveyor bit (the C library's bg_mesh_t info word layout). */
typedef struct OotCoreBgTri {
    short vertex[3][3];
    unsigned short info;      /* bits 0-7 surface, 8-10 ignore, 11 conveyor */
} OotCoreBgTri;

/* Scene data the C side reads directly (camera settings, water boxes).
 * water: decomp WaterBox array (same layout as bg_waterbox_t, written in
 * place by water_set). cameras: decomp BgCamInfo array (setting, count,
 * Vec3s* data). */
typedef struct OotCoreBgScene {
    const void* water;
    unsigned int water_count;
    const void* cameras;
    unsigned int camera_count;
} OotCoreBgScene;

typedef struct OotCoreBgApi {
    unsigned int version;
    int (*floor)(const int pos[3], unsigned ignore, OotCoreBgHit* hit);
    int (*wall)(int result[3], const int next[3], const int prev[3], int radius, int check_height,
                unsigned ignore, int skip_line, OotCoreBgHit* hit);
    int (*ceiling)(int* out_y, const int pos[3], int check_height, unsigned ignore, OotCoreBgHit* hit);
    int (*line)(const int a[3], const int b[3], int at[3], unsigned checks, unsigned ignore, OotCoreBgHit* hit);
    int (*water)(int x, int z, int* surface);
    int (*water_set)(unsigned index, int surface);
    void (*water_reset)(unsigned index);
    /* World-space vertices and plane of a hit poly. */
    int (*poly_vertices)(unsigned bg_id, unsigned poly, short out[3][3]);
    int (*poly_plane)(unsigned bg_id, unsigned poly, short normal[3], int* dist);
    /* DynaPoly proxies for C-owned props: returns id or OOT_CORE_BG_NONE. */
    /* tris: count elements of `stride` bytes, each starting with s16
     * vertex[3][3] (read in place); info: per-tri word or NULL. */
    unsigned (*dyna_register)(const void* tris, unsigned stride, const unsigned short* info, unsigned count,
                              const unsigned* surfaces, unsigned surface_count, unsigned transform);
    void (*dyna_set)(unsigned id, const int pos[3], unsigned short rot_y, int scale_q16);
    void (*dyna_enable)(unsigned id, int enabled);
    void (*dyna_remove)(unsigned id);
    /* Rider: move pos/yaw by the proxy's last-frame motion (source
     * DynaPolyActor_UpdateCarriedActorPos/RotY). */
    int (*dyna_carry)(unsigned id, int pos[3], unsigned short* yaw);
    /* Frame boundary (prev = cur) and lookup rebuild; the core's own Play
     * update does both, hosts/tests may call them explicitly. */
    void (*dyna_step)(void);
    void (*dyna_update)(void);
    int (*scene)(OotCoreBgScene* out);
    /* Scene exit: remove all proxies, forget saved water levels. */
    void (*reset)(void);
} OotCoreBgApi;

/* The core's table (oot_core_bg.cpp). */
const OotCoreBgApi* OotCoreBg_Api(void);

#ifdef __cplusplus
}
#endif
#endif
