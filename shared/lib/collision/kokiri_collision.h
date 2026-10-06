#ifndef KOKIRI_COLLISION_H
#define KOKIRI_COLLISION_H
#include <stdbool.h>
#include <stdint.h>
typedef struct { int32_t x, y, z; } camera_position_t;
typedef struct {
        int16_t vertex[3][3], normal[3], minimum[3], maximum[3];
} collision_triangle_t;
void kokiri_collision_init(const collision_triangle_t *triangles, uint32_t count);
/* Optional: build an XZ lookup grid in the caller's buffer so the queries visit
 * only nearby triangles. Returns false (and leaves the original full scan in
 * place) if the buffer is too small or the set is too large to index. Call
 * after kokiri_collision_init(); the buffer must outlive the collision data. */
bool kokiri_collision_index(void *buffer, uint32_t bytes);
bool kokiri_collision_clear(camera_position_t position);
bool kokiri_collision_floor(int32_t x, int32_t z, int32_t below, int32_t *height);
bool kokiri_collision_spawn(camera_position_t *position);
void kokiri_collision_move(camera_position_t *position, int32_t dx, int32_t dy, int32_t dz);
/* Move child Link using OoT-sized scene checks rather than the taller free
 * camera sphere. Position remains the existing floor+EYE_HEIGHT anchor. */
void kokiri_collision_move_actor(camera_position_t *position, int32_t dx,
        int32_t dy, int32_t dz);
/* Apply one 30 Hz gravity step. Velocity and sub-unit motion use Q8 fixed
 * point so OoT's 20 Hz gravity can be time-scaled without losing precision.
 * Returns true while standing on a floor. */
bool kokiri_collision_fall(camera_position_t *position, int32_t *velocity_q8,
        int32_t *remainder_q8);
/* Custom manual jump, not original OoT behavior. Accept only on actual ground. */
bool kokiri_collision_jump(const camera_position_t *position, int32_t *velocity_q8,
        int32_t *remainder_q8);

/*
 * World-collision contract (RECOMP_PLAN M1): OoT BgCheck queries that report
 * WHAT was hit -- polygon, owner, raw SurfaceType -- not just a height.
 *
 * Positions are FEET, in world units (OoT source space, Y up). The older
 * functions above keep their floor+90 eye anchor and their exact behaviour;
 * they now also see dynamic (actor-owned) collision, which changes nothing
 * while no actor registers any.
 *
 * Poly classes follow z_bgcheck.c: floor normal.y >= 0.5 (the runtime has
 * always used >=), ceiling normal.y < -0.8, everything else wall.
 */
typedef camera_position_t bg_vec_t;

#define BG_SCENE        50      /* BGCHECK_SCENE: static scene geometry */
#define BG_NONE         0xFF
#define BG_DYNA_MAX     16      /* dyna slots, ids 0..15 (< BG_SCENE) */
#define BG_Y_MIN        (-32000) /* BGCHECK_Y_MIN */

/* CollisionPoly ignore flags, flags_vIA >> 13 (COLPOLY_IGNORE_*). */
#define BG_IGNORE_CAMERA        1
#define BG_IGNORE_ENTITY        2
#define BG_IGNORE_PROJECTILES   4

/* D_80119D90 wall-type flags (WALL_FLAG_*). Never compare raw wall types. */
#define BG_WALL_FLAG_0          0x01
#define BG_WALL_FLAG_1          0x02
#define BG_WALL_FLAG_2          0x04
#define BG_WALL_FLAG_3          0x08
#define BG_WALL_CRAWLSPACE_1    0x10
#define BG_WALL_CRAWLSPACE_2    0x20
#define BG_WALL_CRAWLSPACE      (BG_WALL_CRAWLSPACE_1 | BG_WALL_CRAWLSPACE_2)
#define BG_WALL_FLAG_6          0x40

/* Poly classes a line test considers (BGCHECK_CHECK_*). */
#define BG_CHECK_WALL           0x01
#define BG_CHECK_FLOOR          0x02
#define BG_CHECK_CEILING        0x04
#define BG_CHECK_ALL            0x07
#define BG_CHECK_ONE_FACE       0x08

/* DynaPoly transform flags (DYNA_TRANSFORM_*). */
#define BG_DYNA_POS             0x01
#define BG_DYNA_ROT_Y           0x02

/* WaterBox, raw (bgcheck.h). properties: bgCam 0-7, light 8-12, room 13-18
 * (0x3F = every room), bit 19 disabled. */
typedef struct {
        int16_t x_min, y_surface, z_min, x_length, z_length;
        uint32_t properties;
} bg_waterbox_t;
#define BG_WATERBOX_ROOM(p)     (((p) >> 13) & 0x3F)
#define BG_WATERBOX_ROOM_ALL    0x3F
#define BG_WATERBOX_DISABLED    (1u << 19)
#define BG_WATERBOX_BGCAM(p)    ((p) & 0xFF)

/* BgCamInfo: setting, then `count` Vec3s starting at camera_vectors[first*3]. */
typedef struct { uint16_t setting; int16_t count; uint32_t first; } bg_camera_t;

/* One collision set: the scene's, or a dyna actor's untransformed mesh. */
typedef struct {
        const collision_triangle_t *triangles; uint32_t triangle_count;
        /* Per triangle: bits 0-7 surface index, 8-10 ignore flags, 11 floor
         * conveyor. NULL = every triangle uses surface 0 of nothing (all 0). */
        const uint16_t *info;
        const uint32_t *surfaces; uint32_t surface_count;   /* data0,data1 pairs */
        const bg_waterbox_t *water; uint32_t water_count;
        const bg_camera_t *cameras; uint32_t camera_count;
        const int16_t *camera_vectors; uint32_t camera_vector_count;
} bg_mesh_t;

/* What a query touched. */
typedef struct {
        int16_t normal[3];      /* Q14, world space */
        uint16_t poly;          /* index in its owner's mesh */
        uint8_t bg_id;          /* BG_SCENE, a dyna id, or BG_NONE */
        uint8_t ignore;         /* the poly's BG_IGNORE_* flags */
        uint8_t conveyor;       /* COLPOLY_IS_FLOOR_CONVEYOR */
        uint32_t data0, data1;  /* raw SurfaceType */
} bg_hit_t;

/* SurfaceType_Get* (z_bgcheck.c), bit for bit. */
static inline uint32_t bg_bgcam(const bg_hit_t *h)        { return h->data0 & 0xFF; }
static inline uint32_t bg_exit(const bg_hit_t *h)         { return h->data0 >> 8 & 0x1F; }
static inline uint32_t bg_floor_type(const bg_hit_t *h)   { return h->data0 >> 13 & 0x1F; }
static inline uint32_t bg_unk18(const bg_hit_t *h)        { return h->data0 >> 18 & 7; }
static inline uint32_t bg_wall_type(const bg_hit_t *h)    { return h->data0 >> 21 & 0x1F; }
static inline uint32_t bg_floor_property(const bg_hit_t *h) { return h->data0 >> 26 & 0xF; }
static inline uint32_t bg_is_soft(const bg_hit_t *h)      { return h->data0 >> 30 & 1; }
static inline uint32_t bg_horse_blocked(const bg_hit_t *h) { return h->data0 >> 31 & 1; }
static inline uint32_t bg_material(const bg_hit_t *h)     { return h->data1 & 0xF; }
static inline uint32_t bg_floor_effect(const bg_hit_t *h) { return h->data1 >> 4 & 3; }
static inline uint32_t bg_light(const bg_hit_t *h)        { return h->data1 >> 6 & 0x1F; }
static inline uint32_t bg_echo(const bg_hit_t *h)         { return h->data1 >> 11 & 0x3F; }
static inline uint32_t bg_hookshot(const bg_hit_t *h)     { return h->data1 >> 17 & 1; }
static inline uint32_t bg_conveyor_speed(const bg_hit_t *h) { return h->data1 >> 18 & 7; }
static inline uint32_t bg_conveyor_direction(const bg_hit_t *h) { return h->data1 >> 21 & 0x3F; }
static inline uint32_t bg_wall_damage(const bg_hit_t *h)  { return h->data1 >> 27 & 1; }
/* SurfaceType_GetWallFlags: D_80119D90[wallType]. */
uint32_t bg_wall_flags(const bg_hit_t *hit);
/* Math3D_UDistPlaneToPos: unsigned distance from `pos` to the plane of the
 * hit's polygon, world units rounded down; -1 if the polygon is gone. */
int32_t bg_poly_plane_distance(const bg_hit_t *hit, const bg_vec_t *pos);
/* CollisionPoly_GetVerticesByBgId: the hit polygon's world vertices. */
bool bg_poly_vertices(const bg_hit_t *hit, int16_t vertex[3][3]);

/* BGCHECKFLAG_WALL for Link. kokiri_collision_move_actor's horizontal step
 * runs the source's wall sphere; begin_step clears the record once per game
 * step, actor_wall reads it. *stepped = a horizontal step ran at all (an
 * integer step can be zero while speed is not). */
void kokiri_collision_actor_begin_step(void);
bool kokiri_collision_actor_wall(bool *stepped, bg_hit_t *hit);
/* PLAYER_STATE2_CRAWLING: wall radius 10 at 15, ceiling 30. */
void kokiri_collision_actor_set_crawl(bool crawling);
/* A step with no horizontal move: the sphere at rest (prev == pos). */
void kokiri_collision_actor_probe_still(const camera_position_t *position);

/* KBG2 file (build_scene_table.py collision_file) -> native mesh in `dest`.
 * Big-endian on disc; decoded field by field, so host tests read the real
 * file. bg_mesh_bytes: bytes `dest` needs, 0 if the file is not valid. */
uint32_t bg_mesh_bytes(const uint8_t *file, uint32_t length);
bool bg_mesh_decode(const uint8_t *file, uint32_t length, void *dest,
        uint32_t dest_bytes, bg_mesh_t *mesh);
/* The scene's static set. Replaces kokiri_collision_init; rebuild the index
 * afterwards. The mesh struct is copied, its arrays are not. */
void bg_scene_set(const bg_mesh_t *mesh);
const bg_mesh_t *bg_scene_mesh(void);

/* BgCheck_RaycastDownImpl for an entity (floors + ground-facing walls): the
 * highest surface strictly below pos->y at pos->x/z, static and dyna. isSoft
 * lowers it by 1 as the source does. Returns BG_Y_MIN on a miss. */
int32_t bg_floor(const bg_vec_t *pos, uint32_t ignore, bg_hit_t *hit);
/* BgCheck_CheckWallImpl: moving prev -> next, sphere `radius` at
 * `check_height` above the feet. Writes the pushed-out position to *result
 * (x/z; y only from the low-sweep floor case). skip_line = SphVsWall4. */
bool bg_wall(bg_vec_t *result, const bg_vec_t *next, const bg_vec_t *prev,
        int32_t radius, int32_t check_height, uint32_t ignore, bool skip_line,
        bg_hit_t *hit);
/* BgCheck_CheckCeilingImpl: a ceiling within check_height above pos. *out_y
 * is the highest feet y that clears it. */
bool bg_ceiling(int32_t *out_y, const bg_vec_t *pos, int32_t check_height,
        uint32_t ignore, bg_hit_t *hit);
/* BgCheck_CheckLineImpl: nearest crossing from a to b of the poly classes in
 * `checks` (BG_CHECK_*), 1-unit edge tolerance. *at = crossing point. */
bool bg_line(const bg_vec_t *a, const bg_vec_t *b, bg_vec_t *at,
        uint32_t checks, uint32_t ignore, bg_hit_t *hit);
/* BgCheck_GetWaterSurface: strict-inequality XZ bounds, infinite depth,
 * disabled boxes skipped, room must match or be 0x3F. */
bool bg_water_set_surface(uint32_t index, int32_t surface);
void bg_water_reset_surface(uint32_t index);
bool bg_water_surface(int32_t x, int32_t z, uint32_t room, int32_t *surface,
        const bg_waterbox_t **box);

/* DynaPoly. World-space copies of each registered mesh live in the caller's
 * buffer (cart RAM on the Saturn). An actor registers in Init and MUST call
 * bg_dyna_remove in Destroy, as OoT actors call DynaPoly_DeleteBgActor. */
void bg_dyna_init(void *buffer, uint32_t bytes);
/* DynaPoly_SetBgActor. Returns the id, or BG_NONE when slots/space run out. */
uint32_t bg_dyna_register(const bg_mesh_t *mesh, uint32_t transform);
/* Place the mesh: scale (Q16, actor scale) then rot_y then translate, as
 * DynaPoly_ExpandSRT does for these transform flags. */
void bg_dyna_set(uint32_t id, const bg_vec_t *pos, uint16_t rot_y, int32_t scale_q16);
/* COLLISION_DISABLED toggle (webs, opened doors). */
void bg_dyna_enable(uint32_t id, bool enabled);
void bg_dyna_remove(uint32_t id);
void bg_dyna_clear(void);
/* Once per game step before actors move (DynaPoly_UpdateBgActorTransforms):
 * the current transform becomes the previous one. */
void bg_dyna_step(void);
/* DynaPolyActor_TransformCarriedActor, per transform flag: POS moves the
 * rider's position by cur * inverse(prev) (translation, Y rotation, scale
 * since bg_dyna_step); ROT_Y turns *yaw only. True when a flag applied;
 * false for a removed or disabled slot. Registering never resets another
 * slot's previous transform. */
bool bg_dyna_carry(uint32_t id, bg_vec_t *pos, uint16_t *yaw);
uint32_t bg_dyna_triangles_used(void);
#endif
