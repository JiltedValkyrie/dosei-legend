/*
** Mesh loader for the isolated Jo Engine / SGL viewer.
**
** The geometry tables (POINT/POLYGON/ATTR) are generated into
** generated/<name>_scene.c by tools/build_sgl_scene.py. This file uploads each
** mesh's 4bpp texture tiles and their CLUTs into VDP1 VRAM and patches every
** ATTR's texno/colno to point at what was uploaded.
**
** Two meshes share the VDP1 texture area and the SGL sprite table: the forest
** and Link. They are uploaded back to back through the same path, so the only
** per-mesh state is where each one's tiles and sprite slots start.
**
** Generated vdp1_layout.h reserves commands below GAME_TEXTURE_BASE and
** ends textures at Jo's physical user-area end. The SDK's nominal size does
** not agree with its start/end addresses; do not use it as a capacity check.
** The framebuffers are separate, at JO_VDP1_FB.
*/

#include <jo/jo.h>
#include <stdint.h>
#include "frame_timer.h"

#include "kokiri_scene.h"
#include "link_scene.h"
#include "kokiri_sgl.h"
#include "vdp1_layout.h"
#include "demo.h"
#include "link_anim_state.h"
#include "kokiri_actors.h"
#include "gameplay.h"

/* Original forest renderer: radius (4367) * 60%. Requested visibility is
 * half of that range. Keep crossing polygons using their nearest vertex. */
#define FOREST_FAR (4367 * 6 / 10 / 2)
#define FOREST_FOG_START (FOREST_FAR / 2)
static short forest_depth[KOKIRI_VERTEX_COUNT];
static short tile_depth[KOKIRI_TILE_COUNT];
static unsigned char tile_fog[KOKIRI_TILE_COUNT];
static unsigned char forest_mesh[KOKIRI_POLYGON_COUNT];
static unsigned char *forest_palette;
#ifdef KOKIRI_STREAM_ROOMS
static unsigned int forest_polygon_count, forest_vertex_count, forest_tile_count;
static unsigned int forest_object_count, forest_sprite_base;
static unsigned int resident_bytes, resident_sprites;
static int forest_room = -1;
static int requested_room;
static bool room_gameplay;
static unsigned char object_visible[KOKIRI_OBJECT_COUNT];
#else
#define forest_polygon_count KOKIRI_POLYGON_COUNT
#define forest_vertex_count KOKIRI_VERTEX_COUNT
#define forest_tile_count KOKIRI_TILE_COUNT
#define forest_sprite_base 1
#endif
/*
** Identity of the closest DISTANCE-stippled polygon seen this prep.
**
** Deliberately records facts, not a verdict. An earlier version claimed a
** stippled polygon that looks huge must be a bug, on the reasoning that huge
** means close and stipple means far. Both halves are wrong: a large polygon
** can be far away and still cover much of the screen, and an AUTHORED stipple
** is the artist's flag and is legitimate at any depth. Only the distance test
** can be wrong, so only distance-stippled polygons are tracked here, and the
** polygon's own near/far extent is recorded so a large-but-far surface is
** distinguishable from a genuinely close one.
**
** The tile index alone is not enough to identify the surface: tiles are shared
** between polygons, which is the whole point of the shared-tile fog handling.
*/
static int mesh_near_depth = 32767;       /* its nearest vertex */
static int mesh_near_far = 32767;         /* its farthest vertex: extent */
static short mesh_near_tile = -1;
static short mesh_near_polygon = -1;      /* index into the ORIGINAL table */
static unsigned short mesh_near_verts[4];
static bool mesh_near_authored;
static bool forest_prepared;
/* True when this frame reused the prepared list instead of rebuilding it. The
** depth/partition/fog timers are then STALE -- they hold the last rebuild's
** figures -- and must not be read as this frame's work. */
static bool forest_reused;
static int prepared_x, prepared_y, prepared_z, prepared_pitch;
#ifdef DOSEI_ACTOR_ORDER_PROBE
static void actor_order_prepare(int x, int y, int z, int yaw);
static void actor_order_queue(void);
#endif
static unsigned short prepared_yaw;
static unsigned int prepared_visible;
static unsigned char fog_channel[2][17][32];

static void forest_fog_init(void)
{
    unsigned int amount, channel;
    for (amount = 0; amount <= 16; ++amount)
        for (channel = 0; channel < 32; ++channel) {
            int c = (int)channel, a = (int)amount;
            fog_channel[0][amount][channel] = (unsigned char)(c + (27-c)*a/16);
            fog_channel[1][amount][channel] = (unsigned char)(c + (19-c)*a/16);
        }
}

/*
** Per-face flags kept beside the ATTR table, because prep rewrites both the
** MESHon bit and the sort key every rebuild and cannot read back what the
** converter authored. Bit 0: the face's own screen-door stipple. Bit 1: the
** converter keyed it SORT_MAX as a large up-facing floor.
*/
static unsigned char forest_face_flags(unsigned int i)
{
    const ATTR *attr = &kokiri_pdata.attbl[i];
    return (unsigned char)(((attr->atrb & MESHon) != 0) |
                           (((attr->sort & 3u) == SORT_MAX) ? 2u : 0u));
}

/* Pixel blobs are staged on the CD rather than compiled in: as C arrays they
** would add ~360 KB to the ELF. */
#define KOKIRI_PIXEL_FILE   "KOKIRI.TEX"
#define LINK_PIXEL_FILE     "LINK.TEX"
#define FAIRY_PIXEL_FILE    "FAIRY.RGB"
/* Gear pickup icons: the original inventory artwork, one 16x16 RGB555 sprite
** each. A billboard, not a chest actor -- it costs 512 bytes of VDP1 VRAM and
** no polygons, where a chest would need a second imported model. */
#define SWORD_PIXEL_FILE    "SWORD.RGB"
#define SHIELD_PIXEL_FILE   "SHIELD.RGB"
/* Pause grid art, at Kaleido's own EQUIP_GRID_QUAD_TEX_SIZE of 32. */
#define MENU_SWORD_FILE     "SWORDM.RGB"
#define MENU_SHIELD_FILE    "SHIELM.RGB"
#define MENU_EQUIP_FILE     "EQUIP.RGB"
#define MENU_TEX_SIZE       32
#define MENU_PIXEL_BYTES    (MENU_TEX_SIZE * MENU_TEX_SIZE * 2)
#define FAIRY_WIDTH         16
#define FAIRY_HEIGHT        16
#define FAIRY_PIXEL_BYTES   (FAIRY_WIDTH * FAIRY_HEIGHT * 2)
#define FAIRY_COLMODE_RGB   5

static unsigned int  vram_used;      /* bytes claimed in the VDP1 user area */
static unsigned int  sprite_next = 1;/* next free __jo_sprite_def slot; 0 is Jo's */
static unsigned int  kokiri_rejected;
static unsigned int  kokiri_accepted_mask;
static unsigned int  submitted;
static unsigned int  fairy_sprite;
static unsigned int  grass_sprite;
static unsigned int  rupee_sprite[2], digit_sprite[10];
static unsigned int  pickup_sprite[KOKIRI_PICKUP_COUNT];
static unsigned int  menu_sprite[GP_SLOT_COUNT];
static unsigned int  menu_equip_sprite;

/* SGL addresses sprite character data in 8-byte units. */
#define VRAM_UNITS(bytes)   ((bytes) >> 3)

/*
** Upload one mesh's tiles and bind its polygons to them.
**
** `tiles` and `cluts` have identical layouts for every mesh, so the generated
** kokiri_tile type stands in for all of them.
*/
static bool         mesh_load(const char *file, unsigned int pixel_bytes,
                              const kokiri_tile *tiles, unsigned int tile_count,
                              const unsigned short (*cluts)[16],
                              PDATA *pdata, unsigned int polygons)
{
    unsigned char   *base = (unsigned char *)JO_VDP1_VRAM
                            + GAME_TEXTURE_BASE;
    unsigned int     clut_bytes = tile_count * 32;
    unsigned char   *pixel_vram, *clut_vram;
    char            *loaded;
    int              length = 0;
    unsigned int     i, sprite_base = sprite_next;

    if (vram_used + pixel_bytes + clut_bytes > GAME_TEXTURE_BYTES)
    {
        jo_core_error("%s needs %d more VDP1 bytes, %d used of %d", file,
                      (int)(pixel_bytes + clut_bytes), (int)vram_used,
                      (int)GAME_TEXTURE_BYTES);
        return (false);
    }
    if (sprite_base + tile_count > JO_MAX_SPRITE)
    {
        jo_core_error("%s needs sprite slots %d..%d, JO_MAX_SPRITE is %d", file,
                      (int)sprite_base, (int)(sprite_base + tile_count),
                      (int)JO_MAX_SPRITE);
        return (false);
    }

    /* Read straight into VDP1 VRAM. Passing a buffer to jo_fs_read_file_ptr()
    ** avoids jo_malloc()'ing a staging copy of the whole blob. */
    pixel_vram = base + vram_used;
    loaded = jo_fs_read_file_ptr(file, pixel_vram, &length);
    if (loaded == JO_NULL)
    {
        jo_core_error("cannot read %s", file);
        return (false);
    }
    if ((unsigned int)length < pixel_bytes)
    {
        jo_core_error("%s is %d bytes, expected %d", file, length,
                      (int)pixel_bytes);
        return (false);
    }

    /* CLUTs sit directly behind the pixels. jo_fs_read_file_ptr() also writes a
    ** NUL at stream[fsize], i.e. the first CLUT byte; this upload overwrites it,
    ** and the budget checked above already counts both. */
    clut_vram = pixel_vram + pixel_bytes;
    if (pdata == &kokiri_pdata) forest_palette = clut_vram;
    jo_dma_copy((void *)cluts, clut_vram, clut_bytes);
    vram_used += pixel_bytes + clut_bytes;

    /* Publish one SGL TEXTURE entry per tile. __jo_sprite_def is the table
    ** handed to slInitSystem() in jo_core_init_vdp(), so an ATTR texno is just
    ** an index into it. */
    for (i = 0; i < tile_count; ++i)
    {
        jo_texture_definition   *texture = &__jo_sprite_def[sprite_base + i];
        unsigned int             addr = (unsigned int)(pixel_vram + tiles[i].offset)
                                        - JO_VDP1_VRAM;

        texture->width = tiles[i].width;
        texture->height = tiles[i].height;
        texture->adr = (unsigned short)VRAM_UNITS(addr);
        texture->size = JO_MULT_BY_32(tiles[i].width & 0x1f8) | tiles[i].height;
    }
    sprite_next += tile_count;

    /* Point every polygon at its uploaded tile and CLUT. The converter stored a
    ** 0-based tile index in texno; rebias it into this mesh's slot range and
    ** fill in colno, which is only knowable once the CLUTs have a VRAM address. */
    for (i = 0; i < polygons; ++i)
    {
        ATTR            *attr = &pdata->attbl[i];
        unsigned int     tile = attr->texno;
        unsigned int     clut = (unsigned int)(clut_vram + tile * 32);

        attr->texno = (unsigned short)(sprite_base + tile);
        attr->colno = (unsigned short)VRAM_UNITS(clut - JO_VDP1_VRAM);
    }
    return (true);
}

/* Upload one 16x16 RGB555 billboard and hand back its sprite slot.
** Shared by the fairies and the gear pickups: same size, same colour mode,
** same budget check, so there is one place that can get the VRAM wrong. */
static bool         sprite_load_rect(const char *file, unsigned int *slot,
                                unsigned int width, unsigned int height, unsigned int bytes)
{
    unsigned char *pixel_vram = (unsigned char *)JO_VDP1_VRAM
                                + GAME_TEXTURE_BASE + vram_used;
    jo_texture_definition *texture;
    char *loaded;
    int length = 0;

    if (vram_used + bytes > GAME_TEXTURE_BYTES ||
        sprite_next >= JO_MAX_SPRITE)
        return false;
    loaded = jo_fs_read_file_ptr(file, pixel_vram, &length);
    if (!loaded || (unsigned int)length != bytes) return false;
    *slot = sprite_next++;
    texture = &__jo_sprite_def[*slot];
    texture->width = (unsigned short)width;
    texture->height = (unsigned short)height;
    texture->adr = (unsigned short)VRAM_UNITS((unsigned int)pixel_vram
                                              - JO_VDP1_VRAM);
    texture->size = JO_MULT_BY_32(width & 0x1f8) | height;
    __jo_sprite_pic[*slot].color_mode = COL_32K;
    __jo_sprite_pic[*slot].data = pixel_vram;
    vram_used += bytes;
    return true;
}

static bool sprite_load(const char *file, unsigned int *slot,
                        unsigned int side, unsigned int bytes)
{
    return sprite_load_rect(file, slot, side, side, bytes);
}

static bool         billboard_load(const char *file, unsigned int *slot)
{
    return sprite_load(file, slot, FAIRY_WIDTH, FAIRY_PIXEL_BYTES);
}

static bool         fairy_load(void)
{
    unsigned int i;
    if (!billboard_load(FAIRY_PIXEL_FILE, &fairy_sprite))
        return false;
    if (!sprite_load("GRASS.RGB", &grass_sprite, 32, 32 * 32 * 2))
        return false;
    if (!billboard_load("RUPEEG.RGB", &rupee_sprite[0]) ||
        !billboard_load("RUPEEB.RGB", &rupee_sprite[1])) return false;
    for (i = 0; i < 10; ++i) {
        char file[] = "DIGIT0.RGB";
        file[5] = (char)('0' + i);
        if (!sprite_load_rect(file, &digit_sprite[i], 8, 16, 256)) return false;
    }
    /* Pickup order matches kokiri_pickups[], which the converter emits in the
    ** PICKUPS order: sword first, then shield. */
    for (i = 0; i < KOKIRI_PICKUP_COUNT; ++i) {
        const char *file = (kokiri_pickups[i].item == GP_SWORD)
                           ? SWORD_PIXEL_FILE : SHIELD_PIXEL_FILE;
        if (!billboard_load(file, &pickup_sprite[i]))
            return false;
    }
    /* Pause grid: the same two items at 32x32 plus the real equipped outline. */
    if (!sprite_load(MENU_SWORD_FILE, &menu_sprite[GP_SLOT_SWORD],
                     MENU_TEX_SIZE, MENU_PIXEL_BYTES) ||
        !sprite_load(MENU_SHIELD_FILE, &menu_sprite[GP_SLOT_SHIELD],
                     MENU_TEX_SIZE, MENU_PIXEL_BYTES) ||
        !sprite_load(MENU_EQUIP_FILE, &menu_equip_sprite,
                     MENU_TEX_SIZE, MENU_PIXEL_BYTES))
        return false;
    return true;
}

#ifdef KOKIRI_STREAM_ROOMS
static bool room_read(jo_file *file, void *target, unsigned int bytes)
{
    return jo_fs_read_next_bytes(file, (char *)target, bytes) == (int)bytes;
}

static bool room_load(unsigned int room)
{
    unsigned int header[8], expected, i;
    char mesh_name[] = "R0.MSH", pixel_name[] = "R0.TEX";
    jo_file file;
    bool ok;
    if (room > 2) return false;
    mesh_name[1] += room; pixel_name[1] += room;
    if (!jo_fs_open(&file, mesh_name)) return false;
    if (!room_read(&file, header, sizeof(header))) { jo_fs_close(&file); return false; }
    expected = 32 + header[1]*12 + header[2]*32 + header[3]*44 +
               ((header[2]+3)&~3u) + header[5]*24;
    if (header[0] != 0x4b524d31 || !header[1] || !header[2] || !header[3] ||
        header[1] > KOKIRI_VERTEX_COUNT || header[2] > KOKIRI_POLYGON_COUNT ||
        header[3] > KOKIRI_TILE_COUNT || header[4] > KOKIRI_PIXEL_BYTES ||
        header[5] > KOKIRI_OBJECT_COUNT || (unsigned int)file.size != expected ||
        resident_bytes + header[4] + header[3]*32 > GAME_TEXTURE_BYTES ||
        resident_sprites + header[3] > JO_MAX_SPRITE) {
        jo_fs_close(&file); return false;
    }
    ok = room_read(&file, kokiri_pdata.pntbl, header[1]*sizeof(POINT)) &&
         room_read(&file, kokiri_pdata.pltbl, header[2]*sizeof(POLYGON)) &&
         room_read(&file, kokiri_pdata.attbl, header[2]*sizeof(ATTR)) &&
         room_read(&file, kokiri_tiles, header[3]*sizeof(kokiri_tile)) &&
         room_read(&file, kokiri_cluts, header[3]*32) &&
         room_read(&file, kokiri_objects, (header[2]+3)&~3u) &&
         room_read(&file, kokiri_bounds, header[5]*sizeof(kokiri_object));
    jo_fs_close(&file);
    if (!ok) return false;
    /* Every bank replaces the same forest slots; Link/fairies stay resident. */
    vram_used = resident_bytes;
    sprite_next = resident_sprites;
    forest_sprite_base = sprite_next;
    if (!mesh_load(pixel_name,header[4],kokiri_tiles,header[3],
                   (const unsigned short (*)[16])kokiri_cluts,&kokiri_pdata,header[2]))
        return false;
    forest_vertex_count = kokiri_pdata.nbPoint = header[1];
    forest_polygon_count = kokiri_pdata.nbPolygon = header[2];
    forest_tile_count = header[3]; forest_object_count = header[5];
    for (i=0;i<forest_polygon_count;++i)
        forest_mesh[i] = forest_face_flags(i);
    for (i=0;i<forest_tile_count;++i) tile_fog[i] = 255;
    forest_prepared = false;
    forest_room = (int)room;
    return true;
}
#endif

bool                kokiri_scene_load(void)
{
    forest_prepared = false;
    forest_fog_init();
#ifndef KOKIRI_STREAM_ROOMS
    if (!mesh_load(KOKIRI_PIXEL_FILE, KOKIRI_PIXEL_BYTES, kokiri_tiles,
                   KOKIRI_TILE_COUNT, kokiri_cluts, &kokiri_pdata,
                   KOKIRI_POLYGON_COUNT))
        return (false);
#endif
    if (!mesh_load(LINK_PIXEL_FILE, LINK_PIXEL_BYTES,
                   (const kokiri_tile *)link_tiles, LINK_TILE_COUNT,
                   link_cluts, &link_pdata, LINK_POLYGON_COUNT))
        return (false);
    if (!fairy_load()) return (false);
#ifdef KOKIRI_STREAM_ROOMS
    resident_bytes = vram_used;
    resident_sprites = sprite_next;
    return room_load(0);
#else
    {
        unsigned int i;
        for (i = 0; i < KOKIRI_POLYGON_COUNT; ++i)
            forest_mesh[i] = forest_face_flags(i);
        for (i = 0; i < KOKIRI_TILE_COUNT; ++i) tile_fog[i] = 255;
    }
    return (true);
#endif
}

bool kokiri_scene_update(void)
{
#ifdef KOKIRI_STREAM_ROOMS
    unsigned int i;
    int target = requested_room;
    if (!demo_link_active || demo_title_is_visible()) { room_gameplay = false; return true; }
    if (!room_gameplay) { target = 0; room_gameplay = true; }
    for (i=0;i<KOKIRI_PORTAL_COUNT;++i) {
        const kokiri_portal *p = &kokiri_portals[i];
        int32_t sine,cosine;
        int dx = demo_link.x-p->x, dz = demo_link.z-p->z;
        int dy = demo_link.y-DEMO_LINK_EYE_HEIGHT-p->y;
        int side, depth;
        if (forest_room != p->front && forest_room != p->back) continue;
        kokiri_camera_sincos(p->yaw,&sine,&cosine);
        side = (int)(((int64_t)dx*cosine-(int64_t)dz*sine)>>16);
        depth = (int)(((int64_t)dx*sine+(int64_t)dz*cosine)>>16);
        /* Original invisible tunnel volume; the central 100-unit band keeps
         * tiny movements from repeatedly swapping CD banks. */
        if (dy > -50 && dy < 200 && side > -200 && side < 200 &&
            ((depth > 50 && depth < 100) || (depth < -50 && depth > -100)))
            target = depth < 0 ? p->front : p->back;
    }
    requested_room = target;
    if (target != forest_room) {
        /* Do not overwrite texture RAM while VDP1 still reads last frame.
         * Defer until draw end instead of spinning inside the game callback. */
        if (!(JO_VDP1_EDSR & 2)) return true;
        return room_load((unsigned int)target);
    }
#endif
    return true;
}

int                 kokiri_scene_mesh_near_depth(void)
{
    return mesh_near_depth;
}

int                 kokiri_scene_mesh_near_tile(void)
{
    return mesh_near_tile;
}

bool                kokiri_scene_mesh_near_authored(void)
{
    return mesh_near_authored;
}

int                 kokiri_scene_mesh_near_far(void)
{
    return mesh_near_far;
}

int                 kokiri_scene_mesh_near_polygon(void)
{
    return mesh_near_polygon;
}

unsigned short      kokiri_scene_mesh_near_vertex(unsigned int corner)
{
    return mesh_near_verts[corner & 3];
}

bool                kokiri_scene_reused(void)
{
    return forest_reused;
}

unsigned int        kokiri_scene_vram_used(void)
{
    return (vram_used);
}

static void         submit(PDATA *pdata, unsigned int bit)
{
    /* slPutPolygon returns FALSE when SGL cannot accept the list, e.g. the
    ** frame's polygon or vertex budget is exhausted. Ignoring it is how a
    ** partially drawn scene could look complete, so every refusal is recorded. */
    if (slPutPolygon(pdata) == FALSE)
        ++kokiri_rejected;
    else
    {
        kokiri_accepted_mask |= bit;
        submitted += pdata->nbPolygon;
    }
}

#include "link_equipment.h"
static POLYGON equipped_polygons[LINK_VISIBLE_POLYGONS];
static ATTR equipped_attributes[LINK_VISIBLE_POLYGONS];
static unsigned int equipped_count;
static unsigned int equipped_mask = 255;

static void link_part(unsigned int first, unsigned int count)
{
    unsigned int i;
    for (i = 0; i < count; ++i) {
        equipped_polygons[equipped_count] = link_pdata.pltbl[first+i];
        equipped_attributes[equipped_count++] = link_pdata.attbl[first+i];
    }
}

void                kokiri_scene_draw(void)
{
    unsigned int i, j, visible = forest_polygon_count;
    int32_t sine, cosine;
    frame_timer_begin(FRAME_PHASE_PREP);
    /* Geometry/fog depend on the camera. Unaccepted actor-order experiments
     * are excluded from normal builds. */
    if (forest_prepared && prepared_x == demo_camera.x &&
        prepared_y == demo_camera.y && prepared_z == demo_camera.z &&
        prepared_yaw == demo_yaw && prepared_pitch == demo_pitch) {
        visible = prepared_visible;
        forest_reused = true;
        goto prepared;
    }
    forest_reused = false;
    frame_timer_begin(FRAME_PHASE_DEPTH);
    kokiri_camera_sincos(demo_yaw, &sine, &cosine);
#ifdef KOKIRI_STREAM_ROOMS
    for (i=0;i<forest_object_count;++i) {
        const kokiri_object *b = &kokiri_bounds[i];
        int dx = b->minimum[0] > demo_camera.x ? b->minimum[0]-demo_camera.x :
                 b->maximum[0] < demo_camera.x ? demo_camera.x-b->maximum[0] : 0;
        int dz = b->minimum[2] > demo_camera.z ? b->minimum[2]-demo_camera.z :
                 b->maximum[2] < demo_camera.z ? demo_camera.z-b->maximum[2] : 0;
        object_visible[i] = (int64_t)dx*dx+(int64_t)dz*dz <= FOREST_FAR*FOREST_FAR;
    }
#endif
    for (i = 0; i < forest_vertex_count; ++i) {
        int x = (kokiri_pdata.pntbl[i][0] >> 16) - demo_camera.x;
        int z = (kokiri_pdata.pntbl[i][2] >> 16) - demo_camera.z;
        forest_depth[i] = (short)(((int64_t)x * sine + (int64_t)z * cosine) >> 16);
    }
    frame_timer_end(FRAME_PHASE_DEPTH);
    frame_timer_begin(FRAME_PHASE_PARTITION);
    for (i = 0; i < forest_tile_count; ++i) tile_depth[i] = 32767;
    mesh_near_depth = 32767;
    mesh_near_far = 32767;
    mesh_near_tile = -1;
    mesh_near_polygon = -1;
    /* Two-ended partition. Skip rejected tails without copying them; swap
     * only a rejected front with an accepted tail. Unlike front compaction,
     * one newly rejected polygon cannot shift the entire accepted suffix.
     * An unchanged view needs ZERO polygon/attribute copies. */
    for (i = 0; i < visible;) {
        int nearest, farthest;
        /* One pass over the four corners, unrolled.
         *
         * The SH7604 does have a 4 KB unified cache, but the working set here
         * does not fit it: the POLYGON table alone is ~40 KB and is walked
         * linearly every frame, and forest_depth[] is indexed by vertex id, so
         * the second lookup scatters. What this removes is the inner loop's
         * own overhead and the repeated indirection through
         * pltbl[i].Vertices[j], on a loop that runs per polygon per frame. */
        {
            const unsigned short *corner = kokiri_pdata.pltbl[i].Vertices;
            int d0 = forest_depth[corner[0]], d1 = forest_depth[corner[1]];
            int d2 = forest_depth[corner[2]], d3 = forest_depth[corner[3]];
            nearest = d0 < d1 ? d0 : d1;
            if (d2 < nearest) nearest = d2;
            if (d3 < nearest) nearest = d3;
            farthest = d0 > d1 ? d0 : d1;
            if (d2 > farthest) farthest = d2;
            if (d3 > farthest) farthest = d3;
        }
        /* Cull behind the camera as well as beyond the draw distance.
        **
        ** The depth test alone only removed distant polygons: anything behind
        ** the camera has a negative depth, so `nearest` was very negative and
        ** it survived. The entire rear hemisphere within range was therefore
        ** transformed and submitted every frame for SGL to reject. Using the
        ** FARTHEST vertex keeps any polygon with a vertex still in front,
        ** including one straddling the camera plane. */
        if (farthest < 0 || nearest > FOREST_FAR
#ifdef KOKIRI_STREAM_ROOMS
            || !object_visible[kokiri_objects[i]]
#endif
        ) {
            do {
                --visible;
                if (i == visible) break;
                {
                    const unsigned short *corner = kokiri_pdata.pltbl[visible].Vertices;
                    int d0 = forest_depth[corner[0]], d1 = forest_depth[corner[1]];
                    int d2 = forest_depth[corner[2]], d3 = forest_depth[corner[3]];
                    nearest = d0 < d1 ? d0 : d1;
                    if (d2 < nearest) nearest = d2;
                    if (d3 < nearest) nearest = d3;
                    farthest = d0 > d1 ? d0 : d1;
                    if (d2 > farthest) farthest = d2;
                    if (d3 > farthest) farthest = d3;
                }
            } while (farthest < 0 || nearest > FOREST_FAR
#ifdef KOKIRI_STREAM_ROOMS
                     || !object_visible[kokiri_objects[visible]]
#endif
            );
            if (i == visible) break;
            {
                POLYGON polygon = kokiri_pdata.pltbl[i];
                ATTR attr = kokiri_pdata.attbl[i];
                unsigned char mesh = forest_mesh[i];
                kokiri_pdata.pltbl[i] = kokiri_pdata.pltbl[visible];
                kokiri_pdata.attbl[i] = kokiri_pdata.attbl[visible];
                forest_mesh[i] = forest_mesh[visible];
                kokiri_pdata.pltbl[visible] = polygon;
                kokiri_pdata.attbl[visible] = attr;
                forest_mesh[visible] = mesh;
#ifdef KOKIRI_STREAM_ROOMS
                { unsigned char object = kokiri_objects[i];
                  kokiri_objects[i] = kokiri_objects[visible]; kokiri_objects[visible] = object; }
#endif
            }
        }
        {
            ATTR *attr = &kokiri_pdata.attbl[i];
            unsigned int tile = attr->texno - forest_sprite_base;
            /* SGL sorts on one depth per polygon. A big ground quad reaching
            ** away from the eye has a CENTRE depth nearer than the actor
            ** standing on it, so it painted over Link's legs. The converter
            ** marked large up-facing faces SORT_MAX (bit 1 of forest_mesh);
            ** keyed on their far corner they fall behind whatever stands on
            ** them. A marked plane at or above the eye keeps SORT_CEN: a deck
            ** seen from below must still be able to occlude him. Baked Y is
            ** negated, so world height is -y. */
            if (forest_mesh[i] & 2) {
                int plane = -(kokiri_pdata.pntbl[
                                  kokiri_pdata.pltbl[i].Vertices[0]][1] >> 16);
                attr->sort = (attr->sort & ~3u) |
                             (plane < demo_camera.y - 8 ? SORT_MAX : SORT_CEN);
            } else
                attr->sort = (attr->sort & ~3u) | SORT_CEN;
#ifdef DOSEI_ACTOR_ORDER_PROBE
            /* Only the parked command-order experiment consumes this tag. */
            attr->gstb = (unsigned short)(i + 1);
#endif
            if (nearest < tile_depth[tile]) tile_depth[tile] = nearest;
            attr->atrb &= ~MESHon;
            if ((forest_mesh[i] & 1) || nearest > FOREST_FAR * 7 / 8)
                attr->atrb |= MESHon;
            /* Record the closest DISTANCE-stippled polygon, with enough to
             * identify it: vertex ids pin the exact surface where a shared
             * tile cannot, and near/far together say whether it is a small
             * close polygon or a large one reaching into the distance. No
             * judgement is applied here -- authored stipple is excluded
             * because it is legitimate at any depth, and everything else is
             * left for the capture to explain. */
            if ((attr->atrb & MESHon) && !(forest_mesh[i] & 1) &&
                nearest < mesh_near_depth) {
                const unsigned short *v = kokiri_pdata.pltbl[i].Vertices;
                mesh_near_depth = nearest;
                mesh_near_far = farthest;
                mesh_near_tile = (short)tile;
                mesh_near_polygon = (short)i;
                mesh_near_verts[0] = v[0]; mesh_near_verts[1] = v[1];
                mesh_near_verts[2] = v[2]; mesh_near_verts[3] = v[3];
                mesh_near_authored = (forest_mesh[i] & 1) != 0;
            }
            ++i;
        }
    }
    frame_timer_end(FRAME_PHASE_PARTITION);
    frame_timer_begin(FRAME_PHASE_FOG);
    /* Shared tiles use the nearest referencing surface to avoid fogging a
     * nearby floor simply because the same tile occurs on a distant wall. */
    for (i = 0; i < forest_tile_count; ++i) {
        int amount;
        const unsigned char *rg, *blue;
        volatile unsigned short *palette =
            (volatile unsigned short *)(forest_palette + i * 32);
        /* Invisible tiles retain their last palette. Recompute on re-entry,
         * not twice (full fog then visible fog) whenever they cross a plane. */
        if (tile_depth[i] == 32767) continue;
        /* Most tiles are either unused/far or fully clear. Avoid signed
         * division for those, preserving the exact original fog steps. */
        if (tile_depth[i] <= FOREST_FOG_START) amount = 0;
        else if (tile_depth[i] >= FOREST_FAR) amount = 16;
        else amount = (tile_depth[i] - FOREST_FOG_START) * 16 /
                      (FOREST_FAR - FOREST_FOG_START);
        if (tile_fog[i] == amount) continue;
        tile_fog[i] = (unsigned char)amount;
        rg = fog_channel[0][amount];
        blue = fog_channel[1][amount];
        for (j = 0; j < 16; ++j) {
            unsigned short source = kokiri_cluts[i][j];
            int r = source & 31, g = (source >> 5) & 31, b = (source >> 10) & 31;
            if (!source) { palette[j] = 0; continue; }
            r = rg[r];
            g = rg[g];
            b = blue[b];
            palette[j] = (unsigned short)(0x8000 | r | (g << 5) | (b << 10));
        }
    }
    frame_timer_end(FRAME_PHASE_FOG);
    forest_prepared = true;
    prepared_x = demo_camera.x; prepared_y = demo_camera.y;
    prepared_z = demo_camera.z; prepared_yaw = demo_yaw;
    prepared_pitch = demo_pitch; prepared_visible = visible;
prepared:
    kokiri_rejected = 0;
    kokiri_accepted_mask = 0;
    submitted = 0;
    kokiri_pdata.nbPolygon = visible;
    frame_timer_end(FRAME_PHASE_PREP);
    submit(&kokiri_pdata, 1u);
    kokiri_pdata.nbPolygon = forest_polygon_count;
}

void                kokiri_link_draw(int x, int y, int z, int yaw)
{
#ifdef DOSEI_ACTOR_ORDER_PROBE
    actor_order_prepare(x, y, z, yaw);
#endif
    /* The converter bakes the Y negation into every POINT table, so world
    ** coordinates reach this matrix as (x, -y, z) -- the same convention the
    ** camera translation in main.c already uses. The caller's yaw is binang;
    ** Jo's matrix helpers take degrees. */
    /* link_points is already posed: demo_update() does it as part of the 30 Hz
    ** step, not here. Skinning mid-draw competed with the field and flickered
    ** the screen edges. */
    jo_3d_push_matrix();
    {
        jo_3d_translate_matrix(x, -y, z);
        jo_3d_rotate_matrix_y((yaw * 360) >> 16);
        if (equipped_mask != gameplay.equipped) {
            equipped_count = 0;
            link_part(LINK_BODY_FIRST, LINK_BODY_COUNT);
            if (gameplay.equipped & GP_SWORD) {
                link_part(LINK_LEFT_SWORD_FIRST, LINK_LEFT_SWORD_COUNT);
                link_part(LINK_SHEATH_FIRST, LINK_SHEATH_COUNT);
            } else link_part(LINK_LEFT_EMPTY_FIRST, LINK_LEFT_EMPTY_COUNT);
            if (gameplay.equipped & GP_SHIELD)
                link_part(LINK_RIGHT_SHIELD_FIRST, LINK_RIGHT_SHIELD_COUNT);
            else link_part(LINK_RIGHT_EMPTY_FIRST, LINK_RIGHT_EMPTY_COUNT);
            equipped_mask = gameplay.equipped;
        }
        /* One submission: submitting each variant separately would transform
         * the full POINT table repeatedly and exhaust SGL's vertex work area. */
        {
            PDATA equipped = link_pdata;
            equipped.pltbl = equipped_polygons;
            equipped.attbl = equipped_attributes;
            equipped.nbPolygon = equipped_count;
            submit(&equipped, 2u);
        }
    }
    jo_3d_pop_matrix();
#ifdef DOSEI_ACTOR_ORDER_PROBE
    actor_order_queue();
#endif
}

/* Base child-day actor list: the eight Kokiri children plus Mido and Saria.
 * kokiri_npcs[] is generated by tools/build_actors.py straight from the US 1.2
 * room actor lists, so identity, position and facing are the original ones and
 * no coordinate here is authored. Their bodies do not exist yet; the fairies
 * still mark each home until the NPC models land. */
static int          fairy_wave(unsigned int angle, int amplitude)
{
    return (int)(((int64_t)slSin((ANGLE)angle) * amplitude) >> 16);
}

void                kokiri_fairies_draw(unsigned int tick)
{
    unsigned int i;
    for (i = 0; i < KOKIRI_NPC_COUNT; ++i) {
        unsigned int angle = tick * (97 + i * 3) + i * 6011;
        FIXED pos[5];
        SPR_ATTR attr = SPR_ATTRIBUTE(0, No_Palet, No_Gouraud, ECdis,
                                      sprNoflip | FUNC_Sprite);
        int x = kokiri_npcs[i].x + fairy_wave(angle, 18);
        int y = kokiri_npcs[i].y + 58 + fairy_wave(angle * 2 + 9000, 9);
        int z = kokiri_npcs[i].z + fairy_wave(angle + 16384, 14);
        int32_t sine, cosine;
        kokiri_camera_sincos(demo_yaw, &sine, &cosine);
        if ((((int64_t)(x - demo_camera.x) * sine +
              (int64_t)(z - demo_camera.z) * cosine) >> 16) > FOREST_FAR)
            continue;

        pos[0] = toFIXED(x);
        pos[1] = toFIXED(-y);
        pos[2] = toFIXED(z);
        pos[3] = toFIXED(1);
        pos[4] = toFIXED(1);
        attr.texno = (Uint16)fairy_sprite;
        attr.atrb |= (FAIRY_COLMODE_RGB & 7) << 3;
        if (slPutSprite(pos, &attr, 0) == FALSE) ++kokiri_rejected;
    }
}

void                kokiri_pickups_draw(unsigned int tick)
{
    unsigned int i;
    for (i = 0; i < KOKIRI_PICKUP_COUNT; ++i) {
        const kokiri_pickup_t *pickup = &kokiri_pickups[i];
        unsigned int angle = tick * 140 + i * 21845;
        FIXED pos[5];
        SPR_ATTR attr = SPR_ATTRIBUTE(0, No_Palet, No_Gouraud, ECdis,
                                      sprNoflip | FUNC_Sprite);
        int x = pickup->x;
        /* Float it clear of the grass and bob, so a pickup lying on a busy
        ** ground texture still reads as an object rather than a decal. */
        int y = pickup->y + 46 + fairy_wave(angle, 7);
        int z = pickup->z;
        int32_t sine, cosine;
        if (gameplay_pickup_taken(i))
            continue;
        kokiri_camera_sincos(demo_yaw, &sine, &cosine);
        if ((((int64_t)(x - demo_camera.x) * sine +
              (int64_t)(z - demo_camera.z) * cosine) >> 16) > FOREST_FAR)
            continue;

        pos[0] = toFIXED(x);
        pos[1] = toFIXED(-y);
        pos[2] = toFIXED(z);
        /* Twice the fairy's size: these are the one thing the player is being
        ** asked to go and find. */
        pos[3] = toFIXED(2);
        pos[4] = toFIXED(2);
        attr.texno = (Uint16)pickup_sprite[i];
        attr.atrb |= (FAIRY_COLMODE_RGB & 7) << 3;
        if (slPutSprite(pos, &attr, 0) == FALSE) ++kokiri_rejected;
    }
}

unsigned int kokiri_scene_room(void)
{
#ifdef KOKIRI_STREAM_ROOMS
    return forest_room < 0 ? 0 : (unsigned int)forest_room;
#else
    return 0;
#endif
}

static void rupee_world(int x, int y, int z, unsigned int room,
                        unsigned int value, unsigned int age, unsigned int tick)
{
    int dx = x - demo_camera.x, dz = z - demo_camera.z;
    FIXED pos[5];
    SPR_ATTR attr = SPR_ATTRIBUTE(0, No_Palet, No_Gouraud, ECdis,
                                  sprNoflip | FUNC_Sprite);
#ifdef KOKIRI_STREAM_ROOMS
    if (room != (unsigned int)forest_room) return;
#endif
    if (dx * dx + dz * dz > FOREST_FAR * FOREST_FAR) return;
    /* Source icon as a 24px billboard. New grass drops hop for half a second. */
    y += 14;
    if (age < GP_DROP_DELAY) y += (int)(age * (GP_DROP_DELAY - age)) / 2;
    else { int bob = (int)((tick >> 1) & 15); y += bob < 8 ? bob : 15 - bob; }
    pos[0] = x * 65536; pos[1] = -y * 65536; pos[2] = z * 65536;
    pos[3] = pos[4] = 98304;
    attr.texno = (Uint16)rupee_sprite[value == 5 ? 1 : 0];
    attr.atrb |= (FAIRY_COLMODE_RGB & 7) << 3;
    if (slPutSprite(pos, &attr, 0) == FALSE) ++kokiri_rejected;
}

void kokiri_rupees_draw(unsigned int tick)
{
    unsigned int i;
    for (i = 0; i < KOKIRI_RUPEE_COUNT; ++i) {
        const kokiri_rupee_t *r = &kokiri_rupees[i];
        if (!gameplay_rupee_taken(i))
            rupee_world(r->x,r->y,r->z,r->room,r->value,GP_DROP_DELAY,tick);
    }
    for (i = 0; i < KOKIRI_GRASS_COUNT; ++i) {
        const kokiri_prop_t *g = &kokiri_grass[i];
        if (gameplay.grass_rupee[i])
            rupee_world(g->x,g->y,g->z,g->room,gameplay.grass_rupee[i],gameplay.grass_age[i],tick);
    }
}

static void rupee_hud_sprite(unsigned int sprite, int x, int width)
{
    FIXED pos[5];
    SPR_ATTR attr = SPR_ATTRIBUTE(0, No_Palet, No_Gouraud, ECdis,
                                  sprNoflip | FUNC_Sprite);
    /* slDispSprite ignores the world matrix. Coordinates are screen-centred. */
    pos[0] = (x - JO_TV_WIDTH_2 + width/2) * 65536;
    pos[1] = (206 - JO_TV_HEIGHT_2 + 8) * 65536;
    /* SGL SpriteEntry rejects z <= screen_distance >> display_level.
     * Gameplay uses 240 and Jo initializes level 3: near = 30, not zero.
     * Depth 31 gives sort key 1, ahead of the world, without near rejection. */
    pos[2] = 31 * 65536;
    pos[3] = pos[4] = 65536;
    attr.texno = (Uint16)sprite;
    attr.atrb |= (FAIRY_COLMODE_RGB & 7) << 3;
#ifdef DOSEI_HIRES
    /* Screen-space sprites bypass the world's vertical scale. */
    pos[1] = (206 * 2 - JO_TV_HEIGHT_2 + 16) * 65536;
    pos[4] = 2 * 65536;
    if (slDispSpriteHV(pos, &attr, 1) == FALSE) ++kokiri_rejected;
#else
    if (slDispSprite(pos, &attr, 0) == FALSE) ++kokiri_rejected;
#endif
}

void kokiri_rupee_hud_draw(void)
{
    if (gameplay_is_talking()) return; /* dialogue owns the lower screen */
    rupee_hud_sprite(rupee_sprite[0], 26, 16);
    rupee_hud_sprite(digit_sprite[gameplay.rupees / 10], 42, 8);
    rupee_hud_sprite(digit_sprite[gameplay.rupees % 10], 50, 8);
}

void                kokiri_grass_draw(void)
{
    unsigned int i;
    for (i = 0; i < KOKIRI_GRASS_COUNT; ++i) {
        const kokiri_prop_t *grass = &kokiri_grass[i];
        int32_t dx = grass->x - demo_camera.x;
        int32_t dz = grass->z - demo_camera.z;
        FIXED pos[5];
        SPR_ATTR attr = SPR_ATTRIBUTE(0, No_Palet, No_Gouraud, ECdis,
                                      sprNoflip | FUNC_Sprite);
        if (gameplay_grass_cut(i)) continue;
#ifdef KOKIRI_STREAM_ROOMS
        if (grass->room != forest_room) continue;
#endif
        if (dx * dx + dz * dz > FOREST_FAR * FOREST_FAR) continue;
        /* 48x40 world units, centre raised by half-height: base on authored
         * floor, not hovering like pickups. Integer-only runtime conversion. */
        pos[0] = (int32_t)grass->x * 65536;
        pos[1] = -(int32_t)(grass->y + 20) * 65536;
        pos[2] = (int32_t)grass->z * 65536;
        pos[3] = 98304;
        pos[4] = 81920;
        attr.texno = (Uint16)grass_sprite;
        attr.atrb |= (FAIRY_COLMODE_RGB & 7) << 3;
        if (slPutSprite(pos, &attr, 0) == FALSE) ++kokiri_rejected;
    }
}

/*
** Pause equipment grid, laid out with Kaleido Scope's own numbers.
**
** z_kaleido_scope.h: EQUIP_GRID_CELL_WIDTH/HEIGHT are 32 and
** EQUIP_GRID_QUAD_TEX_SIZE is 32, and z_kaleido_scope.c builds the rows from
** y = (EQUIP_TYPE_MAX * CELL_HEIGHT) / 2 - 6, stepping down one cell per equip
** type -- swords on row 0, shields on row 1, which is the order the slots are
** in here. The original reserves the left column for upgrades; the slice has
** none, so its equips start at the same column the real grid's do.
**
** These are flat screen sprites over the frozen world, which is how the
** original draws them too: textured quads, not a background layer.
*/
#define KOKIRI_MENU_PLANE   240     /* main.c SCREEN_DISTANCE */
#define EQUIP_CELL          32
#define EQUIP_QUAD_MARGIN   2
#define EQUIP_ROWS          2
#define EQUIP_COLUMN_X      (-EQUIP_CELL)
#define EQUIP_ORIGIN_Y      ((EQUIP_ROWS * EQUIP_CELL) / 2 - 6)

static void         menu_quad(unsigned int sprite, int x, int y, int side)
{
    FIXED pos[5];
    SPR_ATTR attr = SPR_ATTRIBUTE(0, No_Palet, No_Gouraud, ECdis,
                                  sprNoflip | FUNC_Sprite);
    /* Screen-space quad. At z = -screen distance one world unit is one screen
    ** pixel, so Kaleido's pixel grid transfers unchanged, and nothing in the
    ** world can sort in front of it. */
    pos[0] = toFIXED(x);
    pos[1] = toFIXED(y);
    pos[2] = toFIXED(-KOKIRI_MENU_PLANE);
    pos[3] = toFIXED(side) / MENU_TEX_SIZE;
    pos[4] = toFIXED(side) / MENU_TEX_SIZE;
    attr.texno = (Uint16)sprite;
    attr.atrb |= (FAIRY_COLMODE_RGB & 7) << 3;
    if (slPutSprite(pos, &attr, 0) == FALSE) ++kokiri_rejected;
}

void                kokiri_menu_draw(void)
{
    unsigned int slot;
    if (!gameplay_is_paused())
        return;
    for (slot = 0; slot < GP_SLOT_COUNT; ++slot) {
        uint8_t item = gameplay_slot_item(slot);
        int x = EQUIP_COLUMN_X;
        int y = EQUIP_ORIGIN_Y - (int)slot * EQUIP_CELL;
        if (!(gameplay.owned & item))
            continue;               /* nothing owned, nothing to draw */
        menu_quad(menu_sprite[slot], x, y,
                  EQUIP_CELL - 2 * EQUIP_QUAD_MARGIN);
        /* The real EQUIPPED marker sits over the equipped quad. */
        if (gameplay.equipped & item)
            menu_quad(menu_equip_sprite, x, y, EQUIP_CELL);
    }
}

unsigned int        kokiri_scene_accepted_mask(void)
{
    return (kokiri_accepted_mask);
}

unsigned int        kokiri_scene_rejected(void)
{
    return (kokiri_rejected);
}

unsigned int        kokiri_scene_submitted(void)
{
    return (submitted);
}

#ifdef DOSEI_ACTOR_ORDER_PROBE
#include "scene_actor_order.h"
#endif
