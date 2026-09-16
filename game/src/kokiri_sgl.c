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

#include "kokiri_scene.h"
#include "link_scene.h"
#include "kokiri_sgl.h"
#include "vdp1_layout.h"
#include "demo.h"
#include "link_anim_state.h"

/* Original forest renderer: radius (4367) * 60%. Requested visibility is
 * half of that range. Keep crossing polygons using their nearest vertex. */
#define FOREST_FAR (4367 * 6 / 10 / 2)
#define FOREST_FOG_START (FOREST_FAR / 2)
static short forest_depth[KOKIRI_VERTEX_COUNT];
static short tile_depth[KOKIRI_TILE_COUNT];
static unsigned char tile_fog[KOKIRI_TILE_COUNT];
static unsigned char forest_mesh[KOKIRI_POLYGON_COUNT];
static unsigned char *forest_palette;

/* Pixel blobs are staged on the CD rather than compiled in: as C arrays they
** would add ~360 KB to the ELF. */
#define KOKIRI_PIXEL_FILE   "KOKIRI.TEX"
#define LINK_PIXEL_FILE     "LINK.TEX"
#define FAIRY_PIXEL_FILE    "FAIRY.RGB"
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

static bool         fairy_load(void)
{
    unsigned char *pixel_vram = (unsigned char *)JO_VDP1_VRAM
                                + GAME_TEXTURE_BASE + vram_used;
    jo_texture_definition *texture;
    char *loaded;
    int length = 0;

    if (vram_used + FAIRY_PIXEL_BYTES > GAME_TEXTURE_BYTES ||
        sprite_next >= JO_MAX_SPRITE)
        return false;
    loaded = jo_fs_read_file_ptr(FAIRY_PIXEL_FILE, pixel_vram, &length);
    if (!loaded || length != FAIRY_PIXEL_BYTES) return false;
    fairy_sprite = sprite_next++;
    texture = &__jo_sprite_def[fairy_sprite];
    texture->width = FAIRY_WIDTH;
    texture->height = FAIRY_HEIGHT;
    texture->adr = (unsigned short)VRAM_UNITS((unsigned int)pixel_vram
                                              - JO_VDP1_VRAM);
    texture->size = JO_MULT_BY_32(FAIRY_WIDTH & 0x1f8) | FAIRY_HEIGHT;
    __jo_sprite_pic[fairy_sprite].color_mode = COL_32K;
    __jo_sprite_pic[fairy_sprite].data = pixel_vram;
    vram_used += FAIRY_PIXEL_BYTES;
    return true;
}

bool                kokiri_scene_load(void)
{
    if (!mesh_load(KOKIRI_PIXEL_FILE, KOKIRI_PIXEL_BYTES, kokiri_tiles,
                   KOKIRI_TILE_COUNT, kokiri_cluts, &kokiri_pdata,
                   KOKIRI_POLYGON_COUNT))
        return (false);
    if (!mesh_load(LINK_PIXEL_FILE, LINK_PIXEL_BYTES,
                   (const kokiri_tile *)link_tiles, LINK_TILE_COUNT,
                   link_cluts, &link_pdata, LINK_POLYGON_COUNT))
        return (false);
    if (!fairy_load()) return (false);
    {
        unsigned int i;
        for (i = 0; i < KOKIRI_POLYGON_COUNT; ++i)
            forest_mesh[i] = (kokiri_pdata.attbl[i].atrb & MESHon) != 0;
        for (i = 0; i < KOKIRI_TILE_COUNT; ++i) tile_fog[i] = 255;
    }
    return (true);
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

void                kokiri_scene_draw(void)
{
    unsigned int i, j, visible = KOKIRI_POLYGON_COUNT;
    int32_t sine, cosine;
    kokiri_camera_sincos(demo_yaw, &sine, &cosine);
    for (i = 0; i < KOKIRI_VERTEX_COUNT; ++i) {
        int x = (kokiri_pdata.pntbl[i][0] >> 16) - demo_camera.x;
        int z = (kokiri_pdata.pntbl[i][2] >> 16) - demo_camera.z;
        forest_depth[i] = (short)(((int64_t)x * sine + (int64_t)z * cosine) >> 16);
    }
    for (i = 0; i < KOKIRI_TILE_COUNT; ++i) tile_depth[i] = FOREST_FAR;
    /* Partition in place: polygons and attributes stay paired, with no second
     * full mesh allocation and only one SGL vertex transformation per frame. */
    for (i = 0; i < visible;) {
        int nearest = 32767;
        for (j = 0; j < 4; ++j) {
            int depth = forest_depth[kokiri_pdata.pltbl[i].Vertices[j]];
            if (depth < nearest) nearest = depth;
        }
        if (nearest > FOREST_FAR) {
            POLYGON polygon = kokiri_pdata.pltbl[i];
            ATTR attr = kokiri_pdata.attbl[i];
            unsigned char mesh = forest_mesh[i];
            --visible;
            kokiri_pdata.pltbl[i] = kokiri_pdata.pltbl[visible];
            kokiri_pdata.attbl[i] = kokiri_pdata.attbl[visible];
            forest_mesh[i] = forest_mesh[visible];
            kokiri_pdata.pltbl[visible] = polygon;
            kokiri_pdata.attbl[visible] = attr;
            forest_mesh[visible] = mesh;
        } else {
            ATTR *attr = &kokiri_pdata.attbl[i];
            unsigned int tile = attr->texno - 1;
            if (nearest < tile_depth[tile]) tile_depth[tile] = nearest;
            attr->atrb &= ~MESHon;
            if (forest_mesh[i] || nearest > FOREST_FAR * 7 / 8)
                attr->atrb |= MESHon;
            ++i;
        }
    }
    /* Shared tiles use the nearest referencing surface to avoid fogging a
     * nearby floor simply because the same tile occurs on a distant wall. */
    for (i = 0; i < KOKIRI_TILE_COUNT; ++i) {
        int amount = (tile_depth[i] - FOREST_FOG_START) * 16 /
                     (FOREST_FAR - FOREST_FOG_START);
        volatile unsigned short *palette =
            (volatile unsigned short *)(forest_palette + i * 32);
        if (amount < 0) amount = 0;
        if (amount > 16) amount = 16;
        if (tile_fog[i] == amount) continue;
        tile_fog[i] = (unsigned char)amount;
        for (j = 0; j < 16; ++j) {
            unsigned short source = kokiri_cluts[i][j];
            int r = source & 31, g = (source >> 5) & 31, b = (source >> 10) & 31;
            if (!source) { palette[j] = 0; continue; }
            r += (27 - r) * amount / 16;
            g += (27 - g) * amount / 16;
            b += (19 - b) * amount / 16;
            palette[j] = (unsigned short)(0x8000 | r | (g << 5) | (b << 10));
        }
    }
    kokiri_rejected = 0;
    kokiri_accepted_mask = 0;
    submitted = 0;
    kokiri_pdata.nbPolygon = visible;
    submit(&kokiri_pdata, 1u);
    kokiri_pdata.nbPolygon = KOKIRI_POLYGON_COUNT;
}

void                kokiri_link_draw(int x, int y, int z, int yaw)
{
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
        submit(&link_pdata, 2u);
    }
    jo_3d_pop_matrix();
}

typedef struct { short x, y, z; } fairy_home_t;

/* Base child-day actor list: the Kokiri children plus Mido and Saria. Their
 * bodies are intentionally absent for now; fairies mark their eventual homes. */
static const fairy_home_t fairy_homes[] = {
    {-292,   0, -430}, {  45,   0, -272}, {-608, 120, 1022},
    {-1472,-80, -294}, { 669,   0,  521}, { 853, 100, -311},
    {-678,   1, -179}, { -10, 180,  -22}, {1522,   0,  105},
    {  18, -80,  873},
};

static int          fairy_wave(unsigned int angle, int amplitude)
{
    return (int)(((int64_t)slSin((ANGLE)angle) * amplitude) >> 16);
}

void                kokiri_fairies_draw(unsigned int tick)
{
    unsigned int i;
    for (i = 0; i < sizeof(fairy_homes) / sizeof(fairy_homes[0]); ++i) {
        unsigned int angle = tick * (97 + i * 3) + i * 6011;
        FIXED pos[5];
        SPR_ATTR attr = SPR_ATTRIBUTE(0, No_Palet, No_Gouraud, ECdis,
                                      sprNoflip | FUNC_Sprite);
        int x = fairy_homes[i].x + fairy_wave(angle, 18);
        int y = fairy_homes[i].y + 58 + fairy_wave(angle * 2 + 9000, 9);
        int z = fairy_homes[i].z + fairy_wave(angle + 16384, 14);
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

/*
** END OF FILE
*/
