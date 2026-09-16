/* US 1.2 visual room mesh. CD data stays in low RAM; textures live in VDP1. */
/* DEBUG is optional. Required initialization must run without assertions. */
#include <yaul.h>
#include <assert.h>
#include <stdlib.h>
#include <string.h>
#include "kokiri_scene.h"
#include "kokiri_collision.h"
#include "kokiri_clip.h"
#include "kokiri_camera.h"
#include "frame_probe.h"
#include "perf_bench.h"

typedef struct {
        uint32_t magic, version, vertices, faces, vertex_offset, face_offset;
        uint32_t texture_offset, texture_bytes, total_bytes;
        int32_t center[3];
        uint32_t radius, commands, collision_offset, collision_count;
} header_t;
typedef struct { int16_t x, y, z; } vertex_t;
typedef struct {
        uint16_t vertices[4];
        uint32_t texture, clut;
        uint16_t size, flags;
} face_t;
typedef struct { uint32_t index; int32_t depth; } order_t;
typedef struct { int16_vec2_t p; unsigned outcode; bool safe; } projected_t;
static const header_t *scene;
static const vertex_t *vertices;
static const face_t *faces;
static int32_t *depths;
static clip_vertex_t *view;
static projected_t *projected;
#define CLIP_TILES 256
#define CLIP_TILE_SIZE 16
#define CLIP_TILE_BYTES 128
#define COMMAND_CAPACITY 3072
static camera_position_t camera;
static int32_t pitch;

static order_t *order;
static vdp1_cmdt_list_t *commands;
static vdp1_vram_t texture_base;
static angle_t angle;
/* Draw distance. Keep triangles that cross into the near field: large floor
 * polygons can have a far average depth while still reaching the camera.
 * Only triangles wholly beyond a threshold are culled or mesh-faded. */
static int32_t far_z, fade_z;
/* Capacity refusals since boot. Displayed by frame_probe on row 0. */
static uint16_t overflow_commands, overflow_tiles;
/* Texture staging experiment. The scene blob lives in LWRAM; statics land in
 * HWRAM (linker script: ram ORIGIN 0x06004000). The resampler reads scattered
 * texels with reuse, so each source tile is copied here once immediately
 * before resampling and read from HWRAM thereafter. 512 bytes covers the
 * largest source tile (32x32 at 4bpp); 16x16 tiles use 128 of it. The copy is
 * inside the measured texture span because it is part of this strategy's
 * cost, not an artifact of measuring it. */
#define TEXTURE_STAGE_BYTES 512
/* Control switch for the staging experiment. Build with
 * -DTEXTURE_STAGE_DISABLE=1 to read sources straight from LWRAM again, so the
 * staged and unstaged builds can be compared under the SAME profiler. */
/* Default OFF. Measured against a same-profiler control: no frame-time gain,
 * and its texture/clip means were worse (texture 191E vs 187A control,
 * clip/emit 2ACC vs 2A32). Build -DTEXTURE_STAGE_DISABLE=0 to re-enable. */
/* Ablation switches. Both deliberately change behaviour and must never be
 * enabled in a shipping build; they answer "what is the frame made of". */
#ifndef ABLATE_TEXTURE
#define ABLATE_TEXTURE 0
#endif
/* Wireframe ablation: polyline instead of polygon. Same command count, same
 * four vertices, same CPU path - only VDP1 fill is removed. Comparing it
 * against the flat-polygon build isolates fill cost from everything else.
 * Implies ABLATE_TEXTURE. */
#ifndef ABLATE_WIREFRAME
#define ABLATE_WIREFRAME 0
#endif
#if ABLATE_WIREFRAME
#undef ABLATE_TEXTURE
#define ABLATE_TEXTURE 1
#endif
#ifndef TEXTURE_STAGE_DISABLE
#define TEXTURE_STAGE_DISABLE 1
#endif
/* Early-cull experiment: reject faces by conservative object-space bounds
 * against the existing view frustum BEFORE the vertex loop, then transform
 * only the vertices those survivors reference.
 *
 * MEASURED AND REJECTED (fixed pose, same profiler, acceptance passed):
 *   frame 6616 -> 6616 (no change), vertex 1908 -> 1B2E (worse),
 *   facecull 032C -> 017F, sort 042C -> 017F, clip/emit 2A32 -> 2A1D.
 *   Projected vertices 024E -> 0178 (590 -> 376, ~36% fewer).
 * Fewer transformed vertices, but overall CPU roughly flat: the sphere test
 * runs over 2,060 faces to save work on 1,268 vertices, and there are more
 * faces than vertices. Command counts also differed slightly (00F8 vs
 * 00F7/00F9), so visual equivalence was NOT established - the profiler
 * verdict checks measurement validity, not drawn output.
 * Kept behind a default-off flag as a recorded negative result. */
#ifndef EARLY_CULL
#define EARLY_CULL 0
#endif
static uint8_t texture_stage[TEXTURE_STAGE_BYTES] __aligned(4) __unused;
#if EARLY_CULL
/* Per-face bounding SPHERE in object space, built once at init. A sphere is
 * rotation invariant, so the camera-space test needs only the transformed
 * centre plus the original radius - no per-face corner transforms. An AABB
 * would stop being axis-aligned once rotated, and transforming 8 corners per
 * face would cost more than the vertex work it saves. */
typedef struct { int16_t centre[3]; int32_t radius; } face_sphere_t;
static face_sphere_t *face_spheres;
/* Marks for vertices referenced by surviving faces, and the survivor list. */
static uint8_t *vertex_needed;
static uint16_t *survivors;
static uint32_t survivor_count;
#endif

static void sort_faces(uint32_t visible_count)
{
        /* Shell sort has bounded storage and is available without libc qsort. */
        for (uint32_t gap = visible_count / 2; gap; gap /= 2) {
                for (uint32_t i = gap; i < visible_count; i++) {
                        order_t value = order[i];
                        uint32_t j = i;
                        while (j >= gap && order[j-gap].depth < value.depth) {
                                order[j] = order[j-gap];
                                j -= gap;
                        }
                        order[j] = value;
                }
        }
}

void kokiri_scene_init(void)
{
        cdfs_config_default_set();
        cdfs_filelist_entry_t *entries = cdfs_entries_alloc(-1);
        assert(entries);
        cdfs_filelist_t list;
        cdfs_filelist_init(&list, entries, -1);
        cdfs_filelist_root_read(&list);
        uint32_t bytes = 0;
        for (uint32_t i = 0; i < list.entries_count; i++) {
                if (entries[i].type != CDFS_ENTRY_TYPE_FILE || strcmp(entries[i].name, "FOREST.BIN")) continue;
                bytes = entries[i].size;
                assert(bytes >= sizeof(header_t) && bytes < 0x100000 - 2048);
                int result __unused = cd_block_sectors_read(entries[i].starting_fad, (void *)LWRAM(0), bytes);
                assert(result == 0);
                break;
        }
        cdfs_entries_free(entries);
        assert(bytes);
        const uint8_t *data = (const uint8_t *)LWRAM(0);
        scene = (const header_t *)data;
        assert(scene->magic == 0x4B465231 && scene->version == 2 && scene->total_bytes == bytes);
        assert(scene->vertices < 65536 && scene->faces < 10000 && scene->radius > 0 && scene->radius < 16000);
        far_z = (int32_t)scene->radius * 6 / 10;
        fade_z = far_z - far_z / 4;
        assert(scene->vertex_offset == 64 && scene->face_offset >= 64 + scene->vertices * sizeof(vertex_t));
        assert(scene->texture_offset >= scene->face_offset + scene->faces * sizeof(face_t));
        assert(scene->texture_offset <= bytes && scene->texture_bytes == bytes - scene->texture_offset);
        assert(scene->commands == scene->faces + 3 && COMMAND_CAPACITY * 32 + scene->texture_bytes + CLIP_TILES*CLIP_TILE_BYTES + 32 < 0x80000);
        vertices = (const vertex_t *)(data + scene->vertex_offset);
        faces = (const face_t *)(data + scene->face_offset);
        assert(scene->collision_offset >= scene->face_offset + scene->faces*sizeof(face_t));
        assert(scene->collision_count > 0 && scene->collision_count < 10000);
        assert(scene->collision_offset + scene->collision_count*sizeof(collision_triangle_t) <= scene->texture_offset);
        kokiri_collision_init((const collision_triangle_t *)(data+scene->collision_offset), scene->collision_count);
        /* assert() removes its expression entirely in the release SDK.
         * Always spawn, and stop if no safe starting position exists. */
        if (!kokiri_collision_spawn(&camera)) abort();
        view = malloc(scene->vertices * sizeof(*view));
        projected = malloc(scene->vertices * sizeof(*projected));
        depths = malloc(scene->vertices * sizeof(*depths));
        order = malloc(scene->faces * sizeof(*order));
        commands = vdp1_cmdt_list_alloc(COMMAND_CAPACITY);
        assert(view && projected && depths && order && commands);
        vdp1_vram_partitions_set(COMMAND_CAPACITY, scene->texture_bytes + CLIP_TILES*CLIP_TILE_BYTES, 0, 0);
        vdp1_vram_partitions_t partitions;
        vdp1_vram_partitions_get(&partitions);
        texture_base = (vdp1_vram_t)partitions.texture_base;
        memcpy((void *)texture_base, data + scene->texture_offset, scene->texture_bytes);
        for (uint32_t i = 0; i < scene->faces; i++) {
                for (int j = 0; j < 4; j++) assert(faces[i].vertices[j] < scene->vertices);
                assert(faces[i].size == 0x0210 || faces[i].size == 0x0420);
                uint32_t width __unused = ((faces[i].size >> 8) & 63) * 8;
                assert(faces[i].texture + width * (faces[i].size & 255) / 2 <= scene->texture_bytes);
                assert(faces[i].clut + 32 <= scene->texture_bytes);
        }
#if EARLY_CULL
        face_spheres = malloc(scene->faces * sizeof(*face_spheres));
        vertex_needed = malloc(scene->vertices * sizeof(*vertex_needed));
        survivors = malloc(scene->faces * sizeof(*survivors));
        assert(face_spheres && vertex_needed && survivors);
        for (uint32_t i = 0; i < scene->faces; i++) {
                int32_t lo[3], hi[3];
                for (int k = 0; k < 3; k++) { lo[k] = 32767; hi[k] = -32768; }
                for (int j = 0; j < 3; j++) {
                        const vertex_t *v = &vertices[faces[i].vertices[j]];
                        const int32_t c[3] = { v->x, v->y, v->z };
                        for (int k = 0; k < 3; k++) {
                                if (c[k] < lo[k]) lo[k] = c[k];
                                if (c[k] > hi[k]) hi[k] = c[k];
                        }
                }
                int32_t centre[3];
                for (int k = 0; k < 3; k++) centre[k] = (lo[k] + hi[k]) / 2;
                /* Radius: max distance from centre to any vertex. Use the
                 * Manhattan bound, which is >= Euclidean, keeping the sphere
                 * conservative without a square root at init. */
                int32_t radius = 0;
                for (int j = 0; j < 3; j++) {
                        const vertex_t *v = &vertices[faces[i].vertices[j]];
                        const int32_t c[3] = { v->x, v->y, v->z };
                        int32_t d = 0;
                        for (int k = 0; k < 3; k++) {
                                int32_t e = c[k] - centre[k];
                                d += e < 0 ? -e : e;
                        }
                        if (d > radius) radius = d;
                }
                for (int k = 0; k < 3; k++) face_spheres[i].centre[k] = (int16_t)centre[k];
                face_spheres[i].radius = radius;
        }
#endif
        vdp2_sprite_priority_set(0, 3);
        vdp1_env_t env;
        vdp1_env_default_init(&env);
        env.erase_points[1].y = 239;
        env.erase_color = RGB1555(0, 0, 0, 0);
        vdp1_env_set(&env);
        /* This scene can take multiple video fields to draw. AUTO restarts
         * plotting each field and does not wait for actual draw completion;
         * that races our command and clipped-texture updates. Variable mode
         * plots on explicit submission and waits for completion before swap. */
        vdp1_sync_interval_set(-1);
        memset(commands->cmdts, 0, COMMAND_CAPACITY * sizeof(vdp1_cmdt_t));
        vdp1_cmdt_system_clip_coord_set(&commands->cmdts[0]);
        const int16_vec2_t clip = INT16_VEC2_INITIALIZER(319, 239);
        vdp1_cmdt_vtx_system_clip_coord_set(&commands->cmdts[0], clip);
        vdp1_cmdt_local_coord_set(&commands->cmdts[1]);
        const int16_vec2_t origin = INT16_VEC2_INITIALIZER(0, 0);
        vdp1_cmdt_vtx_local_coord_set(&commands->cmdts[1], origin);
}

void kokiri_camera_sincos(uint16_t yaw, int32_t *sine, int32_t *cosine)
{
        fix16_sincos((angle_t)yaw, sine, cosine);
}

void kokiri_scene_camera_update(const smpc_peripheral_digital_t *pad, bool title_visible)
{
        uint16_t yaw = angle;
        kokiri_camera_update(&camera, &yaw, &pitch, pad->pressed.raw, title_visible);
        angle = (angle_t)yaw;
}

void kokiri_scene_update_and_draw(void)
{
        frame_probe_stage(0x30);
        PERF_SPAN_BEGIN(PERF_SPAN_VERTEX);
        fix16_mat33_t rotation;
        fix16_mat33_y_rotation_create(angle, &rotation);
        fix16_t ps, pc;
        fix16_sincos((angle_t)pitch, &ps, &pc);
#if EARLY_CULL
        /* Pass 1: reject faces whose bounding sphere lies wholly outside a
         * frustum plane, and mark the vertices the survivors reference. The
         * cost of this pass and of marking is inside PERF_SPAN_VERTEX, so it
         * is charged against the saving it is meant to produce. */
        memset(vertex_needed, 0, scene->vertices);
        survivor_count = 0;
        for (uint32_t i = 0; i < scene->faces; i++) {
                const face_sphere_t *sp = &face_spheres[i];
                fix16_vec3_t lc, rc;
                lc.x = fix16_int32_from(sp->centre[0] - camera.x);
                lc.y = fix16_int32_from(sp->centre[1] - camera.y);
                lc.z = fix16_int32_from(sp->centre[2] - camera.z);
                fix16_mat33_vec3_mul(&rotation, &lc, &rc);
                const int32_t cx = fix16_int32_to(rc.x);
                const int32_t cy0 = fix16_int32_to(rc.y);
                const int32_t cz0 = fix16_int32_to(rc.z);
                const int32_t cy = (int32_t)(((int64_t)cy0*pc - (int64_t)cz0*ps)/65536);
                const int32_t cz = (int32_t)(((int64_t)cz0*pc + (int64_t)cy0*ps)/65536);
                const int32_t r = sp->radius;
                /* Conservative plane tests. Each plane is linear, so shifting
                 * the centre distance by the radius scaled by the plane's
                 * coefficient magnitude bounds the whole sphere. Reject only
                 * when the entire sphere is on the outside. */
                bool outside = (cz + r < NEAR_Z);
                if (!outside) outside = (cx*240 + cz*160 + r*400 < 0);
                if (!outside) outside = (cz*159 - cx*240 + r*399 < 0);
                if (!outside) outside = (cz*120 - cy*240 + r*360 < 0);
                if (!outside) outside = (cz*119 + cy*240 + r*359 < 0);
                if (outside) continue;
                survivors[survivor_count++] = (uint16_t)i;
                vertex_needed[faces[i].vertices[0]] = 1;
                vertex_needed[faces[i].vertices[1]] = 1;
                vertex_needed[faces[i].vertices[2]] = 1;
        }
        for (uint32_t i = 0; i < scene->vertices; i++) {
                if (!vertex_needed[i]) { projected[i].outcode = 0x1F; projected[i].safe = false; continue; }
                fix16_vec3_t local, rotated;
#else
        for (uint32_t i = 0; i < scene->vertices; i++) {
                fix16_vec3_t local, rotated;
#endif
                local.x = fix16_int32_from(vertices[i].x - camera.x);
                local.y = fix16_int32_from(vertices[i].y - camera.y);
                local.z = fix16_int32_from(vertices[i].z - camera.z);
                fix16_mat33_vec3_mul(&rotation, &local, &rotated);
                int32_t x = fix16_int32_to(rotated.x), y = fix16_int32_to(rotated.y), z = fix16_int32_to(rotated.z);
                int32_t py = (int32_t)(((int64_t)y*pc - (int64_t)z*ps)/65536);
                int32_t pz = (int32_t)(((int64_t)z*pc + (int64_t)y*ps)/65536);
                view[i] = (clip_vertex_t){x, py, pz, 0, 0};
                depths[i] = pz;
                projected[i].outcode = kokiri_clip_outcode(view[i]);
                projected[i].safe = false;
                if (pz >= NEAR_Z) {
                        /* Project shared vertices once. Ordinary screen-edge
                         * crossings keep the original tile and VDP1 clips
                         * pixels. Bound offscreen coordinates to limit both
                         * VDP1 work and signed command-coordinate range. */
                        int32_t sx = 160 + kokiri_project_offset(x, pz);
                        int32_t sy = 120 - kokiri_project_offset(py, pz);
                        if (sx >= -160 && sx <= 479 && sy >= -120 && sy <= 359) {
                                projected[i].p.x = sx;
                                projected[i].p.y = sy;
                                projected[i].safe = true;
                        }
                        PERF_COUNT_ADD(PERF_COUNT_PROJECTED, 1);
                }
        }
        PERF_SPAN_END(PERF_SPAN_VERTEX);

        PERF_SPAN_BEGIN(PERF_SPAN_FACECULL);
        uint32_t visible_count = 0;
#if EARLY_CULL
        for (uint32_t s = 0; s < survivor_count; s++) {
                const uint32_t i = survivors[s];
                const face_t *face = &faces[i];
#else
        for (uint32_t i = 0; i < scene->faces; i++) {
                const face_t *face = &faces[i];
#endif
                if (projected[face->vertices[0]].outcode & projected[face->vertices[1]].outcode &
                    projected[face->vertices[2]].outcode) continue;
                const int32_t depth0 = depths[face->vertices[0]];
                const int32_t depth1 = depths[face->vertices[1]];
                const int32_t depth2 = depths[face->vertices[2]];
                if (depth0 > far_z && depth1 > far_z && depth2 > far_z) continue;
                int32_t depth_sum = depth0 + depth1 + depth2;
                order[visible_count].index = i;
                order[visible_count++].depth = depth_sum;
        }
        PERF_SPAN_END(PERF_SPAN_FACECULL);
        PERF_COUNT_ADD(PERF_COUNT_VISIBLE, visible_count);
        frame_probe_stage(0x40);
        PERF_SPAN_BEGIN(PERF_SPAN_SORT);
        sort_faces(visible_count);
        PERF_SPAN_END(PERF_SPAN_SORT);
        frame_probe_stage(0x48);
        PERF_SPAN_BEGIN(PERF_SPAN_CLIPEMIT);
        uint32_t count = 2, clip_tiles = 0;
        for (uint32_t i = 0; i < visible_count; i++) {
                const face_t *face = &faces[order[i].index];
                clip_vertex_t polygon[12];
                bool changed = false;
                clip_vertex_t input[3] = {view[face->vertices[0]], view[face->vertices[1]], view[face->vertices[2]]};
                const bool safe = projected[face->vertices[0]].safe &&
                    projected[face->vertices[1]].safe && projected[face->vertices[2]].safe;
                int n;
                if (safe) {
                        memcpy(polygon, input, sizeof(input));
                        n = 3;
                } else {
                        PERF_SPAN_BEGIN(PERF_SPAN_FRUSTUM);
                        n = kokiri_clip_frustum(input, polygon, &changed);
                        PERF_SPAN_END(PERF_SPAN_FRUSTUM);
                        PERF_COUNT_ADD(PERF_COUNT_FRUSTUM_CALLS, 1);
                }
                if (n < 3) continue;
                /* A fan of quads covers clipped polygons without dropping corners. */
                for (int first = 1; first < n-1; first += 2) {
                        clip_vertex_t clipped[4] = {polygon[0], polygon[first], polygon[first+1],
                            polygon[first+2 < n ? first+2 : first+1]};
                        int16_vec2_t p[4];
                        for (int j = 0; j < 4; j++) {
                                if (safe) p[j] = projected[face->vertices[j < 3 ? j : 2]].p;
                                else {
                                        p[j].x = 160 + kokiri_project_offset(clipped[j].x, clipped[j].z);
                                        p[j].y = 120 - kokiri_project_offset(clipped[j].y, clipped[j].z);
                                }
                        }
                        int32_t area = 0;
                        for (int j = 0; j < 4; j++) area += p[j].x*p[(j+1)%4].y-p[j].y*p[(j+1)%4].x;
                        if (!area || ((face->flags & 2) && area <= 0)) continue;
                        /* Checked before allocation, not asserted: with DEBUG
                         * off an assert here compiles away and the write runs
                         * off the end of the command list. Counted and
                         * reported so dropped geometry is never silent. */
                        if (count >= COMMAND_CAPACITY-1) {
                                overflow_commands++;
                                PERF_COUNT_ADD(PERF_COUNT_OVF_COMMANDS, 1);
                                goto emit_done;
                        }
                        vdp1_cmdt_t *cmd = &commands->cmdts[count++];
                        memset(cmd, 0, sizeof(*cmd));
#if ABLATE_TEXTURE
                        /* Ablation: flat-shaded polygon. A polygon primitive
                         * carries a solid colour and reads no character data
                         * at all, so both the resampler and all texture
                         * fetching are removed. Rendered output is untextured
                         * by design; never ship this. Note this also changes
                         * VDP1's work, so a frame-time delta is NOT a pure CPU
                         * measurement. */
#if ABLATE_WIREFRAME
                        vdp1_cmdt_polyline_set(cmd);
#else
                        vdp1_cmdt_polygon_set(cmd);
#endif
                        vdp1_cmdt_draw_mode_t mode = { .raw = 0 };
#else
                        vdp1_cmdt_distorted_sprite_set(cmd);
                        vdp1_cmdt_draw_mode_t mode = { .raw = 0 };
#endif
                        mode.end_code_disable = true;
                        mode.pre_clipping_disable = true;
                        mode.mesh_enable = (face->flags & 1) != 0 ||
                            (depths[face->vertices[0]] > fade_z &&
                             depths[face->vertices[1]] > fade_z &&
                             depths[face->vertices[2]] > fade_z);
                        vdp1_cmdt_draw_mode_set(cmd, mode);
#if ABLATE_TEXTURE
                        /* Vary colour per face so geometry stays legible. */
                        vdp1_cmdt_color_set(cmd,
                            RGB1555(1, (order[i].index * 7) & 31,
                                       (order[i].index * 13) & 31,
                                       (order[i].index * 3) & 31));
#else
                        vdp1_cmdt_color_mode1_set(cmd, texture_base + face->clut);
#endif
                        /* Per-quad decision. `changed` is per-face, so
                         * clearing it here would also suppress resampling -
                         * and the counter - for this face's remaining fan
                         * pieces. Every affected command is counted instead. */
                        bool use_scratch = changed;
                        if (changed && clip_tiles >= CLIP_TILES) {
                                /* Out of scratch tiles: draw the unclipped
                                 * tile rather than write past the partition.
                                 * This maps the original triangle tile onto
                                 * clipped vertices, so the UVs are wrong - a
                                 * visible artifact, counted, and it fails a
                                 * benchmark run. */
                                overflow_tiles++;
                                PERF_COUNT_ADD(PERF_COUNT_OVF_TILES, 1);
                                use_scratch = false;
                        }
#if ABLATE_TEXTURE
                        (void)use_scratch;
#else
                        if (use_scratch) {
                                uint8_t tile[CLIP_TILE_BYTES] __aligned(4);
                                const uint8_t *source = (const uint8_t *)scene + scene->texture_offset + face->texture;
                                const unsigned source_size = face->size & 255;
                                /* 4bpp: size*size texels, two per byte. */
                                const unsigned source_bytes = source_size * source_size / 2;
                                PERF_SPAN_BEGIN(PERF_SPAN_TEXTURE);
                                if (!TEXTURE_STAGE_DISABLE &&
                                    source_bytes <= TEXTURE_STAGE_BYTES) {
                                        memcpy(texture_stage, source, source_bytes);
                                        source = texture_stage;
                                }
                                kokiri_clip_texture(source, source_size, clipped, tile);
                                PERF_SPAN_END(PERF_SPAN_TEXTURE);
                                vdp1_vram_t dest = texture_base + scene->texture_bytes + clip_tiles++*CLIP_TILE_BYTES;
                                memcpy((void *)dest, tile, sizeof(tile));
                                vdp1_cmdt_char_base_set(cmd, dest);
                                vdp1_cmdt_char_size_set(cmd, CLIP_TILE_SIZE, CLIP_TILE_SIZE);
                        } else {
                                vdp1_cmdt_char_base_set(cmd, texture_base + face->texture);
                                vdp1_cmdt_char_size_set(cmd, ((face->size >> 8) & 63) * 8, face->size & 255);
                        }
#endif
                        vdp1_cmdt_vtx_set(cmd, p);
                }
        }
emit_done:
        PERF_SPAN_END(PERF_SPAN_CLIPEMIT);
        PERF_COUNT_ADD(PERF_COUNT_COMMANDS, count - 2);
        PERF_COUNT_ADD(PERF_COUNT_TILES, clip_tiles);
        frame_probe_overflow(overflow_commands, overflow_tiles);

        memset(&commands->cmdts[count], 0, sizeof(vdp1_cmdt_t));
        vdp1_cmdt_end_set(&commands->cmdts[count]);
        commands->count = count + 1;
        frame_probe_stage(0x50);
        PERF_SPAN_BEGIN(PERF_SPAN_UPLOAD);
        vdp1_sync_cmdt_list_put(commands, 0);
        PERF_SPAN_END(PERF_SPAN_UPLOAD);
        frame_probe_stage(0x60);
        PERF_SPAN_BEGIN(PERF_SPAN_RENDER);
        vdp1_sync_render();
        PERF_SPAN_END(PERF_SPAN_RENDER);
        frame_probe_stage(0x70);
        PERF_SPAN_BEGIN(PERF_SPAN_VDP1WAIT);
        vdp1_sync();
        vdp1_sync_wait();
        PERF_SPAN_END(PERF_SPAN_VDP1WAIT);
        frame_probe_stage(0x78);
}
