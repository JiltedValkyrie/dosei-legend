/* US 1.2 visual room mesh. CD data stays in low RAM; textures live in VDP1. */
/* libyaul gates assertions on DEBUG, including file/VRAM bounds checks. */
#ifndef DEBUG
#define DEBUG 1
#endif
#include <yaul.h>
#include <assert.h>
#include <stdlib.h>
#include <string.h>
#include "kokiri_scene.h"
#include "kokiri_collision.h"
#include "kokiri_clip.h"
#include "kokiri_camera.h"
#include "frame_probe.h"

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
        assert(kokiri_collision_spawn(&camera));
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
                uint32_t width = ((faces[i].size >> 8) & 63) * 8;
                assert(faces[i].texture + width * (faces[i].size & 255) / 2 <= scene->texture_bytes);
                assert(faces[i].clut + 32 <= scene->texture_bytes);
        }
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
        fix16_mat33_t rotation;
        fix16_mat33_y_rotation_create(angle, &rotation);
        fix16_t ps, pc;
        fix16_sincos((angle_t)pitch, &ps, &pc);
        for (uint32_t i = 0; i < scene->vertices; i++) {
                fix16_vec3_t local, rotated;
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
                }
        }

        uint32_t visible_count = 0;
        for (uint32_t i = 0; i < scene->faces; i++) {
                const face_t *face = &faces[i];
                if (projected[face->vertices[0]].outcode & projected[face->vertices[1]].outcode &
                    projected[face->vertices[2]].outcode) continue;
                order[visible_count].index = i;
                order[visible_count++].depth = depths[face->vertices[0]] + depths[face->vertices[1]] + depths[face->vertices[2]];
        }
        frame_probe_stage(0x40);
        sort_faces(visible_count);
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
                } else n = kokiri_clip_frustum(input, polygon, &changed);
                if (n < 3) continue;
                /* A fan of quads covers clipped polygons without dropping corners. */
                for (int first = 1; first < n-1; first += 2) {
                        clip_vertex_t clipped[4] = {polygon[0], polygon[first], polygon[first+1],
                            polygon[first+2 < n ? first+2 : first+1]};
                        int16_vec2_t p[4];
                        for (int j = 0; j < 4; j++) {
                                if (safe) p[j] = projected[face->vertices[j]].p;
                                else {
                                        p[j].x = 160 + kokiri_project_offset(clipped[j].x, clipped[j].z);
                                        p[j].y = 120 - kokiri_project_offset(clipped[j].y, clipped[j].z);
                                }
                        }
                        int32_t area = 0;
                        for (int j = 0; j < 4; j++) area += p[j].x*p[(j+1)%4].y-p[j].y*p[(j+1)%4].x;
                        if (!area || ((face->flags & 2) && area <= 0)) continue;
                        assert(count < COMMAND_CAPACITY-1);
                        vdp1_cmdt_t *cmd = &commands->cmdts[count++];
                        memset(cmd, 0, sizeof(*cmd));
                        vdp1_cmdt_distorted_sprite_set(cmd);
                        vdp1_cmdt_draw_mode_t mode = { .raw = 0 };
                        mode.end_code_disable = true;
                        mode.pre_clipping_disable = true;
                        mode.mesh_enable = (face->flags & 1) != 0;
                        vdp1_cmdt_draw_mode_set(cmd, mode);
                        vdp1_cmdt_color_mode1_set(cmd, texture_base + face->clut);
                        if (changed) {
                                assert(clip_tiles < CLIP_TILES);
                                uint8_t tile[CLIP_TILE_BYTES] __aligned(4);
                                const uint8_t *source = (const uint8_t *)scene + scene->texture_offset + face->texture;
                                kokiri_clip_texture(source, face->size & 255, clipped, tile);
                                vdp1_vram_t dest = texture_base + scene->texture_bytes + clip_tiles++*CLIP_TILE_BYTES;
                                memcpy((void *)dest, tile, sizeof(tile));
                                vdp1_cmdt_char_base_set(cmd, dest);
                                vdp1_cmdt_char_size_set(cmd, CLIP_TILE_SIZE, CLIP_TILE_SIZE);
                        } else {
                                vdp1_cmdt_char_base_set(cmd, texture_base + face->texture);
                                vdp1_cmdt_char_size_set(cmd, ((face->size >> 8) & 63) * 8, face->size & 255);
                        }
                        vdp1_cmdt_vtx_set(cmd, p);
                }
        }

        memset(&commands->cmdts[count], 0, sizeof(vdp1_cmdt_t));
        vdp1_cmdt_end_set(&commands->cmdts[count]);
        commands->count = count + 1;
        frame_probe_stage(0x50);
        vdp1_sync_cmdt_list_put(commands, 0);
        frame_probe_stage(0x60);
        vdp1_sync_render();
        frame_probe_stage(0x70);
        vdp1_sync();
        vdp1_sync_wait();
}
