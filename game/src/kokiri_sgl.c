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
#include "asset_loading.h"
#include "asset_names.h"
#include "vdp1_draw_wait.h"
#include <stdint.h>
#include "frame_timer.h"

#include "kokiri_scene.h"
#include "scene_table.h"
#include "room_portal.h"
#include "link_scene.h"
#include "link_clips.h"
#include "kokiri_sgl.h"
#include "minimap.h"
#include "vdp1_layout.h"
static unsigned int texture_base = GAME_TEXTURE_BASE;
static unsigned int hit_table_offset, hit_filter;
void kokiri_hit_filter(unsigned level){hit_filter=level<=32?level:0;}
#define TEXTURE_CAPACITY (0x7fef8u - texture_base)
#define CUTSCENE_TEXTURE_BASE ((3750u * 32 + 8192 + 255) & ~255u)
#include "demo.h"
#include "ram_cart.h"
#include "ram_low.h"
#include "navi.h"
#include "cutscene.h"
#include "link_anim_state.h"
#include "kokiri_actors.h"
#include "gameplay.h"
#include "player_items.h"
#include "dungeon_doors.h"
#include "save_state.h"
#include "mesh_lod.h"
#include "field_stream.h"
#include "story_route.h"
#include "oot_core_host.h"

/* Original forest renderer: radius (4367) * 60%, halved for the room banks.
** The authored single-mesh scene spans the whole town in one list, so that
** halved distance cuts visible ground away in front of the camera; the build
** raises it through DOSEI_FOREST_FAR instead of hiding the choice here. */
#ifdef DOSEI_FOREST_FAR
#define FOREST_FAR_DEFAULT (DOSEI_FOREST_FAR)
#else
#define FOREST_FAR_DEFAULT (4367 * 6 / 10 / 2)
#endif
#define FIELD_FAR 9000
static int forest_far_current = FOREST_FAR_DEFAULT;
static unsigned char forest_scene;
#define FOREST_FAR (forest_far_current)
#define FOREST_FOG_END (forest_scene == 2 ? 1310 : FOREST_FAR)
#define FOREST_FOG_START (FOREST_FOG_END / 2)
/* Low RAM is not zeroed at boot: depths are written before each prep reads
 * them; mesh flags and fog sentinels are filled on every bank load. */
#define forest_depth ((short *)RAM_LOW(RAM_LOW_FOREST_DEPTH_OFFSET))
#define tile_depth ((short *)RAM_LOW(RAM_LOW_TILE_DEPTH_OFFSET))
#define tile_fog ((unsigned char *)RAM_LOW(RAM_LOW_TILE_FOG_OFFSET))
#define forest_mesh ((unsigned char *)RAM_LOW(RAM_LOW_FOREST_MESH_OFFSET))
typedef char forest_depth_fits[KOKIRI_VERTEX_COUNT * sizeof(short) <= RAM_LOW_FOREST_DEPTH_BYTES ? 1 : -1];
typedef char tile_depth_fits[KOKIRI_TILE_COUNT * sizeof(short) <= RAM_LOW_TILE_DEPTH_BYTES ? 1 : -1];
typedef char tile_fog_fits[KOKIRI_TILE_COUNT <= RAM_LOW_TILE_FOG_BYTES ? 1 : -1];
typedef char forest_mesh_fits[KOKIRI_POLYGON_COUNT <= RAM_LOW_FOREST_MESH_BYTES ? 1 : -1];
static unsigned char *forest_palette;
#ifdef KOKIRI_STREAM_ROOMS
static unsigned int forest_polygon_count, forest_vertex_count, forest_tile_count;
static unsigned int forest_object_count, forest_sprite_base;
static unsigned int resident_bytes, resident_sprites;
static int forest_room = -1;
static int requested_room;
static bool room_gameplay;
static unsigned char object_visible[KOKIRI_OBJECT_COUNT];
/* Per-mesh LOD rows live in a fixed cart carve (ram_cart.h). */
#define MESH_LOD_MAX (RAM_CART_MESH_LOD_BYTES / sizeof(mesh_lod_t))
static unsigned int forest_lod_count;
static mesh_lod_t *forest_lods;
static unsigned char lod_state[MESH_LOD_MAX], lod_state_applied[MESH_LOD_MAX];
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
#ifdef DOSEI_WARP_PROBE
/* Warp probe (measurement only, no rendering change).
**
** Two candidates are tracked per prep because the nearest polygon is not
** necessarily the one that warps: a face whose PROJECTED span is large for its
** depth stretches its texture most. The span estimate is world extent scaled
** by 256/nearest depth -- a ratio, not pixels; it only has to rank faces.
** Vertex ids are the stable identity: the partition swaps polygon slots, so an
** index cannot be followed through a turn. */
static int  warp_near_depth = 32767, warp_near_far, warp_near_extent;
static short warp_near_tile = -1;
static unsigned short warp_near_verts[4];
static int  warp_span_score, warp_span_depth, warp_span_far, warp_span_extent;
static short warp_span_tile = -1;
static unsigned short warp_span_verts[4];
#endif
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
#define fog_channel ((unsigned char (*)[17][32])RAM_LOW(RAM_LOW_FOG_CHANNEL_OFFSET))
typedef char fog_channel_fits[2*17*32 <= RAM_LOW_FOG_CHANNEL_BYTES ? 1 : -1];

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
                           (((attr->sort & 3u) == SORT_MAX) ? 2u : 0u) |
                           (((attr->dir & 7) != 4) ? 4u : 0u));
}

/* Pixel blobs are staged on the CD rather than compiled in: as C arrays they
** would add ~360 KB to the ELF. */
#define KOKIRI_PIXEL_FILE   "KOKIRI.TEX"
#define LINK_PIXEL_FILE     "LINK.TEX"
#define FAIRY_PIXEL_FILE    "FAIRY.RGB"
/* Get-item icons: the original inventory artwork, one 16x16 RGB555 sprite
** each. Held above Link while the get-item text shows, and floated over a
** closed chest as its stand-in until the En_Box model lands (FEAT-001). */
#define SWORD_PIXEL_FILE    "SWORD.RGB"
#define SHIELD_PIXEL_FILE   "SHIELD.RGB"
/* Pause grid art, at Kaleido's own EQUIP_GRID_QUAD_TEX_SIZE of 32. */
#define MENU_SWORD_FILE     "SWORDM.RGB"
#define MENU_SHIELD_FILE    "SHIELM.RGB"
#define MENU_EQUIP_FILE     "EQUIP.RGB"
#define MENU_TEX_SIZE       32
/* The real OoT message panel, gDefaultMessageBackgroundTex, converted by
** tools/build_demo_assets.py. Drawn behind cutscene text. */
#define MSGBOX_FILE         "MSGBOX.RGB"
/* Stored small and stretched by VDP1: the panel is a gradient, and VDP1
** VRAM is the binding constraint -- see tools/build_demo_assets.py. */
#define MSGBOX_WIDTH        32
#define MSGBOX_HEIGHT       16
#define MSGBOX_PIXEL_BYTES  (MSGBOX_WIDTH * MSGBOX_HEIGHT * 2)
/* OoT's own prompts: a triangle when another page follows, a square when the
** message ends. gMessageContinueTriangleTex / gMessageEndSquareTex. */
#define MSGNEXT_FILE        "MSGNEXT.RGB"
#define MSGEND_FILE         "MSGEND.RGB"
#define MSGMARK_SIZE        16
#define MSGMARK_PIXEL_BYTES (MSGMARK_SIZE * MSGMARK_SIZE * 2)
/* gLockOnReticleTriangleDL's one 64x64 triangle is rasterized into a compact
** 16px VDP1 corner. Four rotations form the source lock bracket. */
#define RETICLE_SIZE         16
#define RETICLE_PIXEL_BYTES  (RETICLE_SIZE * RETICLE_SIZE * 2)
#define MENU_PIXEL_BYTES    (MENU_TEX_SIZE * MENU_TEX_SIZE * 2)
#define FAIRY_WIDTH         16
#define FAIRY_HEIGHT        16
#define FAIRY_PIXEL_BYTES   (FAIRY_WIDTH * FAIRY_HEIGHT * 2)
#define FAIRY_COLMODE_RGB   5
/* En_Elf wings (tools/build_fairy.py): gFairyAnim's 10 frames of the four
** gFairyWing quads, posed offline, 16 POINTs a frame, in the cart. Flat
** 210,210,255 with MESHon: the dither hid the N64 wing texture anyway. */
#define FAIRY_FRAMES        10
#define FAIRY_MESH_FILE     "FAIRY.BIN"
#define FAIRY_MESH_BYTES    (FAIRY_FRAMES * 16 * 12)
/* gGlowCircleSmallDL: +-500 x 0.012 = 12 world units over the 16 texels.
** Three steps of its L -> SL cross-fade (FAIRY, FAIRYM, FAIRYS). */
#define FAIRY_GLOW_SCALE    49152
#define FAIRY_GLOW_STEPS    3

static unsigned int  vram_used;      /* bytes claimed in the VDP1 user area */
static unsigned int  sprite_next = 1;/* next free __jo_sprite_def slot; 0 is Jo's */
static unsigned int actor_vram_base, actor_sprite_base, actor_bank_generation;
unsigned int        kokiri_sprite_peak;  /* highest sprite_next seen */
static unsigned int  kokiri_rejected;
static unsigned int  kokiri_accepted_mask;
static unsigned int  submitted;
static unsigned int  fairy_sprite, fairy_glow[FAIRY_GLOW_STEPS], sparkle_sprite;
/* Navi's own glow slot (512 B VRAM), refilled from the cart copy of all
** nine glows (player / NPC / enemy x 3 breath steps) when her colour or
** breath step changes. Not fatal: without it she shares fairy_glow. */
static unsigned int  navi_glow_slot;
static unsigned char *navi_glow_pixels;     /* cart, [3][3][512] */
static unsigned int  navi_glow_shown = ~0u; /* set * 3 + step in the slot */
static bool          sparkle_ready;
static bool          fairy_wings_ready;
static POLYGON       fairy_faces[4] = {
    {{0, 0, 65536}, {0, 1, 2, 3}}, {{0, 0, 65536}, {4, 5, 6, 7}},
    {{0, 0, 65536}, {8, 9, 10, 11}}, {{0, 0, 65536}, {12, 13, 14, 15}},
};
#define FAIRY_WING_ATTR ATTRIBUTE(Dual_Plane, SORT_CEN | UseNearClip, 0, C_RGB(26, 26, 31), \
                                  No_Gouraud, CL32KRGB | MESHon | ECdis, sprPolygon, No_Option)
static ATTR          fairy_attrs[4] = {FAIRY_WING_ATTR, FAIRY_WING_ATTR,
                                       FAIRY_WING_ATTR, FAIRY_WING_ATTR};
static PDATA         fairy_meshes[FAIRY_FRAMES];
static unsigned int  grass_sprite;
static unsigned int  rupee_sprite[3], digit_sprite[10];
static unsigned int  drop_sprite[4];
static unsigned int  item_sprite[2];         /* 0 sword, 1 shield */
static unsigned int  menu_sprite[GP_SLOT_COUNT];
static unsigned int  menu_equip_sprite;
static unsigned int  msgbox_sprite;
static bool          msgbox_ready;
static unsigned int  msgmark_sprite[2];     /* 0 continue, 1 end */
static bool          msgmark_ready;
static unsigned int  reticle_sprite[KOKIRI_RETICLE_COUNT][4];
static bool          reticle_ready;

/* SGL addresses sprite character data in 8-byte units. */
#define VRAM_UNITS(bytes)   ((bytes) >> 3)

/*
** Upload one mesh's tiles and bind its polygons to them.
**
** `tiles` and `cluts` have identical layouts for every mesh, so the generated
** kokiri_tile type stands in for all of them.
*/
static unsigned char *opening_pixel_pool;
static int opening_pixel_pool_bytes;

static bool __attribute__((optimize("Os"))) mesh_load(const char *file, unsigned int pixel_bytes,
                              const kokiri_tile *tiles, unsigned int tile_count,
                              const unsigned short (*cluts)[16],
                              PDATA *pdata, unsigned int polygons, const void *cached_pixels)
{
    unsigned char   *base = (unsigned char *)JO_VDP1_VRAM
                            + texture_base;
    unsigned int     clut_bytes = tile_count * 32;
    unsigned char   *pixel_vram, *clut_vram;
    char            *loaded;
    int              length = 0;
    unsigned int     i, sprite_base = sprite_next;

    if (vram_used + pixel_bytes + clut_bytes > TEXTURE_CAPACITY)
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
    if (cached_pixels) {
        const unsigned int *offsets = cached_pixels;
        for (i = 0; i < tile_count; ++i) {
            if (offsets[i] > (unsigned int)opening_pixel_pool_bytes ||
                tiles[i].length > (unsigned int)opening_pixel_pool_bytes - offsets[i] ||
                tiles[i].offset > pixel_bytes || tiles[i].length > pixel_bytes - tiles[i].offset)
                return false;
            /* slDMACopy is async: never reprogram the channel mid-transfer.
            ** Kronos finishes DMA instantly; Mednafen/hardware do not. */
            slDMAWait();
            jo_dma_copy(opening_pixel_pool + offsets[i],
                        pixel_vram + tiles[i].offset, tiles[i].length);
        }
        slDMAWait();
        loaded = (char *)pixel_vram;
        length = pixel_bytes;
    } else {
        asset_loading(file);
        loaded = jo_fs_read_file_ptr(file, pixel_vram, &length);
        asset_loading_done();
    }
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
    slDMAWait();
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
    if (sprite_next > kokiri_sprite_peak) kokiri_sprite_peak = sprite_next;

    /* Point every polygon at its uploaded tile and CLUT. The converter stored a
    ** 0-based tile index in texno; rebias it into this mesh's slot range and
    ** fill in colno, which is only knowable once the CLUTs have a VRAM address. */
    for (i = 0; i < polygons; ++i)
    {
        ATTR            *attr = &pdata->attbl[i];
        if ((attr->dir & 7) == 4) continue; /* Flat face has no tile or CLUT. */
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
static bool __attribute__((optimize("Os"))) sprite_load_rect(const char *file, unsigned int *slot,
                                unsigned int width, unsigned int height, unsigned int bytes)
{
    unsigned char *pixel_vram = (unsigned char *)JO_VDP1_VRAM
                                + texture_base + vram_used;
    jo_texture_definition *texture;
    char *loaded;
    int length = 0;

    if (vram_used + bytes > TEXTURE_CAPACITY ||
        sprite_next >= JO_MAX_SPRITE)
        return false;
    asset_loading(file);
    loaded = jo_fs_read_file_ptr(file, pixel_vram, &length);
    asset_loading_done();
    if (!loaded || (unsigned int)length != bytes) return false;
    *slot = sprite_next++;
    if (sprite_next > kokiri_sprite_peak) kokiri_sprite_peak = sprite_next;
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

/* A resident 8-bit (colour bank) texture from memory: the minimap markers.
** Same budget and bookkeeping as sprite_load_rect, so relocation moves it. */
bool                kokiri_resident_sprite_8bit(const unsigned char *pixels,
                                                unsigned int width, unsigned int height,
                                                unsigned int *slot)
{
    unsigned char *pixel_vram = (unsigned char *)JO_VDP1_VRAM
                                + texture_base + vram_used;
    jo_texture_definition *texture;
    unsigned int bytes = width * height, i;

    if (vram_used + bytes > TEXTURE_CAPACITY || sprite_next >= JO_MAX_SPRITE ||
        (width & 7))
        return false;
    for (i = 0; i < bytes; i += 2)
        *(volatile unsigned short *)(pixel_vram + i) =
            (unsigned short)(pixels[i] << 8 | pixels[i + 1]);
    *slot = sprite_next++;
    if (sprite_next > kokiri_sprite_peak) kokiri_sprite_peak = sprite_next;
    texture = &__jo_sprite_def[*slot];
    texture->width = (unsigned short)width;
    texture->height = (unsigned short)height;
    texture->adr = (unsigned short)VRAM_UNITS((unsigned int)pixel_vram - JO_VDP1_VRAM);
    texture->size = JO_MULT_BY_32(width & 0x1f8) | height;
    __jo_sprite_pic[*slot].color_mode = COL_256;
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

static bool __attribute__((optimize("Os"))) fairy_load(void)
{
    unsigned int i;
    if (!billboard_load(FAIRY_PIXEL_FILE, &fairy_sprite) ||
        !billboard_load("FAIRYM.RGB", &fairy_glow[1]) ||
        !billboard_load("FAIRYS.RGB", &fairy_glow[2]))
        return false;
    fairy_glow[0] = fairy_sprite;
    {
        static const char *const names[9] = {
            "FAIRY.RGB", "FAIRYM.RGB", "FAIRYS.RGB",
            "FAIRYN0.RGB", "FAIRYN1.RGB", "FAIRYN2.RGB",
            "FAIRYE0.RGB", "FAIRYE1.RGB", "FAIRYE2.RGB" };
        unsigned char *cart = (unsigned char *)ram_cart_fixed(RAM_CART_NAVIGLOW_OFFSET,
                                                              9u * FAIRY_PIXEL_BYTES);
        bool ok = cart && billboard_load(FAIRY_PIXEL_FILE, &navi_glow_slot);
        for (i = 0; ok && i < 9; ++i) {
            int length = 0;
            ok = jo_fs_read_file_ptr(names[i], cart + i * FAIRY_PIXEL_BYTES, &length) &&
                 length == FAIRY_PIXEL_BYTES;
        }
        navi_glow_pixels = ok ? cart : (unsigned char *)0;
        navi_glow_shown = 0;                 /* the slot holds FAIRY.RGB */
    }
    /* Not fatal either: no sparkles is only a missing effect. */
    sparkle_ready = sprite_load_rect("SPARKLE.RGB", &sparkle_sprite, 8, 8, 8 * 8 * 2);
    /* The wings are not fatal: without them the glow still draws. */
    {
        unsigned char *mesh = (unsigned char *)ram_cart_fixed(RAM_CART_FAIRY_OFFSET,
                                                              RAM_CART_FAIRY_BYTES);
        int length = 0;
        fairy_wings_ready = mesh &&
            jo_fs_read_file_ptr(FAIRY_MESH_FILE, mesh, &length) &&
            length == FAIRY_MESH_BYTES;
        if (fairy_wings_ready) {
            for (i = 0; i < FAIRY_FRAMES; ++i) {
                fairy_meshes[i].pntbl = (POINT *)(mesh + i * 16 * 12);
                fairy_meshes[i].nbPoint = 16;
                fairy_meshes[i].pltbl = fairy_faces;
                fairy_meshes[i].nbPolygon = 4;
                fairy_meshes[i].attbl = fairy_attrs;
            }
        }
    }
    if (!sprite_load("GRASS.RGB", &grass_sprite, 32, 32 * 32 * 2))
        return false;
    if (!billboard_load("RUPEEG.RGB", &rupee_sprite[0]) ||
        !billboard_load("RUPEEB.RGB", &rupee_sprite[1]) ||
        !billboard_load("RUPEER.RGB", &rupee_sprite[2])) return false;
    for (i = 0; i < 10; ++i) {
        char file[] = "DIGIT0.RGB";
        file[5] = (char)('0' + i);
        if (!sprite_load_rect(file, &digit_sprite[i], 8, 16, 256)) return false;
    }
    if (!billboard_load("DROPHE.RGB", &drop_sprite[0]) ||
        !billboard_load("DROPNUT.RGB", &drop_sprite[1]) ||
        !billboard_load("DROPSTK.RGB", &drop_sprite[2]) ||
        !billboard_load("DROPSED.RGB", &drop_sprite[3])) return false;
    if (!billboard_load(SWORD_PIXEL_FILE, &item_sprite[0]) ||
        !billboard_load(SHIELD_PIXEL_FILE, &item_sprite[1]))
        return false;
    /* Pause grid: the same two items at 32x32 plus the real equipped outline. */
    if (!sprite_load(MENU_SWORD_FILE, &menu_sprite[GP_SLOT_SWORD],
                     MENU_TEX_SIZE, MENU_PIXEL_BYTES) ||
        !sprite_load(MENU_SHIELD_FILE, &menu_sprite[GP_SLOT_SHIELD],
                     MENU_TEX_SIZE, MENU_PIXEL_BYTES) ||
        !sprite_load(MENU_EQUIP_FILE, &menu_equip_sprite,
                     MENU_TEX_SIZE, MENU_PIXEL_BYTES))
        return false;
    /* The message panel is not fatal: without it the cutscene text still
    ** draws, just without a box behind it. */
    msgbox_ready = sprite_load_rect(MSGBOX_FILE, &msgbox_sprite, MSGBOX_WIDTH,
                                    MSGBOX_HEIGHT, MSGBOX_PIXEL_BYTES);
    msgmark_ready =
        sprite_load(MSGNEXT_FILE, &msgmark_sprite[0], MSGMARK_SIZE,
                    MSGMARK_PIXEL_BYTES) &&
        sprite_load(MSGEND_FILE, &msgmark_sprite[1], MSGMARK_SIZE,
                    MSGMARK_PIXEL_BYTES);
    {
        static const char *const files[KOKIRI_RETICLE_COUNT][4] = {
            {"RTEN00.RGB", "RTEN01.RGB", "RTEN02.RGB", "RTEN03.RGB"},
            {"RTNP00.RGB", "RTNP01.RGB", "RTNP02.RGB", "RTNP03.RGB"},
            {"RTPO00.RGB", "RTPO01.RGB", "RTPO02.RGB", "RTPO03.RGB"},
            {"RTAI00.RGB", "RTAI01.RGB", "RTAI02.RGB", "RTAI03.RGB"}
        };
        reticle_ready = true;
        for (i = 0; i < KOKIRI_RETICLE_COUNT; ++i)
            for (unsigned corner = 0; corner < 4; ++corner)
                reticle_ready = reticle_ready && sprite_load_rect(files[i][corner],
                    &reticle_sprite[i][corner], RETICLE_SIZE, RETICLE_SIZE,
                    RETICLE_PIXEL_BYTES);
    }
    return true;
}

#ifdef KOKIRI_STREAM_ROOMS
typedef struct { void *mesh, *pixels; int mesh_bytes, pixel_bytes; } opening_cache_t;
static opening_cache_t opening_cache[10];

void kokiri_opening_cache_free(void)
{
    unsigned int i;
    if (opening_pixel_pool) jo_free(opening_pixel_pool);
    opening_pixel_pool = 0;
    opening_pixel_pool_bytes = 0;
    for (i = 0; i < 10; ++i) {
        if (opening_cache[i].mesh) jo_free(opening_cache[i].mesh);
        if (opening_cache[i].pixels) jo_free(opening_cache[i].pixels);
        opening_cache[i].mesh = opening_cache[i].pixels = 0;
    }
}

bool __attribute__((optimize("Os"))) kokiri_opening_cache_load(void)
{
    unsigned int i;
    kokiri_opening_cache_free();
    asset_loading("NAVIPOOL.TEX");
    opening_pixel_pool = jo_fs_read_file_ptr("NAVIPOOL.TEX", 0, &opening_pixel_pool_bytes);
    if (!opening_pixel_pool) return false;
    for (i = 0; i < 10; ++i) {
        char mesh[] = "S2R0.MSH", pixels[] = "S2R0.MAP";
        mesh[3] = pixels[3] = asset_name_digit(i);
        asset_loading(mesh);
        opening_cache[i].mesh = jo_fs_read_file_ptr(mesh, 0, &opening_cache[i].mesh_bytes);
        asset_loading(pixels);
        opening_cache[i].pixels = jo_fs_read_file_ptr(pixels, 0, &opening_cache[i].pixel_bytes);
        if (!opening_cache[i].mesh || !opening_cache[i].pixels) {
            kokiri_opening_cache_free();
            jo_core_error("Opening cache does not fit RAM cart");
            return false;
        }
    }
    asset_loading_done();
    return true;
}

static bool room_read(jo_file *file, void *target, unsigned int bytes,
                      const unsigned char **cached)
{
    if (*cached) {
        unsigned int i;
        unsigned int *dst = target;
        const unsigned int *src = (const unsigned int *)*cached;
        if (bytes & 3) return false; /* All KRM1 sections are word-aligned. */
        for (i = 0; i < bytes / 4; ++i) dst[i] = src[i];
        *cached += bytes;
        return true;
    }
    return jo_fs_read_next_bytes(file, (char *)target, bytes) == (int)bytes;
}

/* One bank per (scene, room): S<scene>R<room>.MSH/.TEX on the disc.
**
** The names carry the scene now because the slice has more than one. Only a
** ROOM_SHAPE_TYPE_NORMAL scene has banks at all -- OoT's interiors are
** prerendered backdrops with no geometry, so they have none. */
static bool __attribute__((optimize("Os"))) room_load_bank(unsigned int scene, unsigned int room);
static void relocate_resident(unsigned int next_base);
static void field_stream_free(void);

/* True while a prerendered interior's backdrop is on screen. The geometry
** draw is skipped entirely then: an interior HAS no geometry, and the resident
** bank still holds whatever forest room was loaded last. */
static bool backdrop_active;

bool kokiri_scene_backdrop_active(void)
{
    return (backdrop_active);
}

/* Screen priority. jo_core_set_screens_order gives its first argument
** priority 7, the front, and decrements. Text stays in front either way.
**
**   world:    NBG0 text, NBG1, sprites   -- the title artwork overlays the
**             forest, which is what the attract flight needs.
**   interior: NBG0 text, sprites, NBG1   -- the backdrop is the room, so Link
**             and everything else must draw OVER it.
*/
static void screens_for_backdrop(bool interior)
{
    /* Braces are required, not style: jo_core_set_screens_order is a macro
    ** whose definition ends in a semicolon (jo/core.h:191), so a braceless
    ** `if (x) MACRO(); else` expands with a stray empty statement that closes
    ** the if and orphans the else. */
    if (interior) {
        jo_core_set_screens_order(JO_NBG0_SCREEN, JO_NBG2_SCREEN,
                                  JO_SPRITE_SCREEN, JO_NBG1_SCREEN,
                                  JO_RBG0_SCREEN, JO_NBG3_SCREEN);
    } else {
        jo_core_set_screens_order(JO_NBG0_SCREEN, JO_NBG2_SCREEN,
                                  JO_NBG1_SCREEN, JO_SPRITE_SCREEN,
                                  JO_RBG0_SCREEN, JO_NBG3_SCREEN);
    }
    minimap_priorities();       /* NBG2 minimap at 6, its markers above */
}

/* The backdrop shares NBG1 with the title artwork -- they are never both on
** screen -- so whichever was uploaded last is what NBG1 holds. demo.c reloads
** the title image when it returns to the title for that reason. */
bool __attribute__((optimize("Os"))) kokiri_scene_load_backdrop(unsigned int scene, unsigned int room)
{
    /* An interior reuses the Field's tile pools: stop streaming into them. */
    field_stream_free();
    relocate_resident(GAME_TEXTURE_BASE);
    char        name[12];
    jo_img      image;
    int         bytes = 0;

    if (!asset_scene_name(name, scene, (int)room, "RGB") || !kokiri_bank_allocate()) return false;
    asset_loading(name);
    /* Whole image in one CD read, then one VDP2 upload. */
    image.data = (jo_color *)ram_cart_load_scratch(name, &bytes);
    asset_loading_done();
    if (!image.data || bytes != 320 * 240 * 2) return false;
    image.width = 320; image.height = 240;
    jo_clear_background(0);
    jo_set_background_sprite(&image, 0, 0);
    vram_used = resident_bytes;
    sprite_next = resident_sprites;
    actor_vram_base = vram_used;
    actor_sprite_base = sprite_next;
    ++actor_bank_generation;
    backdrop_active = true;
    screens_for_backdrop(true);
    return true;
}

bool __attribute__((optimize("Os"))) kokiri_scene_load_bank(unsigned int scene, unsigned int room)
{
    if (backdrop_active) {
        backdrop_active = false;
        /* Wipe the picture, not just switch the layer off. NBG1 retains
        ** whatever was uploaded, so the interior would otherwise flash over
        ** the forest for any frame where the layer is briefly enabled -- and
        ** NBG1 is enabled again the moment the title screen appears. */
        jo_clear_background(0);
        screens_for_backdrop(false);
    }
    return room_load_bank(scene, room);
}

static void invalidate_equipped(void);

/* The nightmare needs more VDP1 commands than a forest frame. Move the
 * resident textures above that command region before loading its actor bank.
 * Gameplay restores its own compact layout, keeping every forest tile. */
static void relocate_resident(unsigned int next_base)
{
    volatile unsigned short *vram = (volatile unsigned short *)JO_VDP1_VRAM;
    int delta = (int)next_base - (int)texture_base;
    unsigned int i;
    if (!delta) return;
    if (delta > 0) {
        for (i = resident_bytes / 2; i > 0; --i)
            vram[next_base / 2 + i - 1] = vram[texture_base / 2 + i - 1];
    } else {
        for (i = 0; i < resident_bytes / 2; ++i)
            vram[next_base / 2 + i] = vram[texture_base / 2 + i];
    }
    for (i = 1; i < resident_sprites; ++i) {
        __jo_sprite_def[i].adr += delta / 8;
        if (__jo_sprite_pic[i].data)
            __jo_sprite_pic[i].data = (unsigned char *)__jo_sprite_pic[i].data + delta;
    }
    for (i = 0; i < (unsigned int)link_pdata.nbPolygon; ++i)
        link_pdata.attbl[i].colno += delta / 8;
    texture_base = next_base;
    invalidate_equipped();
}

/* ---- Hyrule Field distance streaming (field_stream.h, KRM2) ----------------
** One cart block holds the whole Field. Swaps run only while VDP1 is idle:
** freed tiles return to their bucket, new tiles upload into fixed slots, then
** the room tables are rebuilt from the resident pieces in group order. */
static unsigned char *field_blob;
static const field_header_t *field_head;
static const field_bucket_t *field_buckets;
static const field_tile_t *field_tiles;
static const unsigned short (*field_cluts)[16];
static const field_piece_t *field_pieces;
static const unsigned char *field_pool;
static uint16_t *field_tile_slot, *field_current, *field_want, *field_stack;
static unsigned char *field_tile_ref;
static field_slots_t field_slots;
static unsigned int field_bucket_vram[FIELD_MAX_BUCKETS];  /* VRAM offset of a bucket's first slot */
static unsigned char *field_clut_vram;
static bool field_active, field_owl;
static unsigned int field_tick, field_overflow, field_swaps;

static void field_stream_free(void)
{
    if (field_blob) jo_free(field_blob);
    if (field_tile_slot) jo_free(field_tile_slot);
    if (field_tile_ref) jo_free(field_tile_ref);
    if (field_current) jo_free(field_current);
    if (field_want) jo_free(field_want);
    if (field_stack) jo_free(field_stack);
    field_blob = 0; field_tile_slot = field_current = field_want = field_stack = 0;
    field_tile_ref = 0;
    field_active = false;
}

static const uint16_t *field_refs(const field_piece_t *p)
{
    return (const uint16_t *)(field_blob + p->data + p->points * sizeof(POINT) +
                              p->polys * (sizeof(POLYGON) + sizeof(ATTR)));
}

/* Every offset, count and index the streamer will follow, checked once. */
static bool __attribute__((optimize("Os"))) field_validate(unsigned int length)
{
    const field_header_t *h = field_head;
    unsigned int i, j, k, at;
    if (length < sizeof(*h) || h->magic != FIELD_STREAM_MAGIC ||
        h->version != FIELD_STREAM_VERSION || h->total != length ||
        !h->pieces || h->pieces > 255 || !h->groups || h->groups > h->pieces ||
        h->buckets > FIELD_MAX_BUCKETS || !h->slots || h->slots > KOKIRI_TILE_COUNT ||
        h->max_points > KOKIRI_VERTEX_COUNT || h->max_polys > KOKIRI_POLYGON_COUNT ||
        h->max_pieces > KOKIRI_OBJECT_COUNT || h->tiles > 0xFFFE)
        return false;
    at = sizeof(*h) + h->buckets * sizeof(field_bucket_t) + h->tiles * sizeof(field_tile_t) +
         h->tiles * 32 + h->pieces * sizeof(field_piece_t);
    if (at > h->pool_offset || h->pool_offset > length ||
        h->pixel_bytes != length - h->pool_offset)
        return false;
    for (i = 0, k = 0; i < h->buckets; ++i) {
        if (field_buckets[i].size > 0x8000u || (field_buckets[i].size & 7)) return false;
        k += field_buckets[i].slots;
    }
    if (k != h->slots) return false;
    for (i = 0; i < h->tiles; ++i) {
        const field_tile_t *t = &field_tiles[i];
        if (t->bucket >= h->buckets || t->length > field_buckets[t->bucket].size ||
            t->offset > h->pixel_bytes || t->length > h->pixel_bytes - t->offset ||
            (t->length & 3) || !t->width || !t->height)
            return false;
    }
    for (i = 0; i < h->pieces; ++i) {
        const field_piece_t *p = &field_pieces[i];
        const POLYGON *poly;
        const ATTR *attr;
        const uint16_t *refs;
        unsigned int end;
        if (p->group >= h->groups || p->data < at || (p->data & 3)) return false;
        end = p->data + p->points * sizeof(POINT) + p->polys * (sizeof(POLYGON) + sizeof(ATTR)) +
              p->refs * 2;
        if (end > h->pool_offset || p->points > h->max_points || p->polys > h->max_polys)
            return false;
        poly = (const POLYGON *)(field_blob + p->data + p->points * sizeof(POINT));
        attr = (const ATTR *)(poly + p->polys);
        refs = field_refs(p);
        for (j = 0; j < p->refs; ++j) if (refs[j] >= h->tiles) return false;
        for (j = 0; j < p->polys; ++j) {
            for (k = 0; k < 4; ++k) if (poly[j].Vertices[k] >= p->points) return false;
            if ((attr[j].dir & 7) == 4) continue;
            for (k = 0; k < p->refs && refs[k] != attr[j].texno; ++k) {}
            if (k == p->refs) return false;   /* face tile missing from its piece */
        }
    }
    return true;
}

static void field_upload(unsigned int tile, unsigned int slot)
{
    const field_tile_t *t = &field_tiles[tile];
    unsigned int bucket = t->bucket;
    unsigned int addr = field_bucket_vram[bucket] +
                        (slot - field_slots.first[bucket]) * field_buckets[bucket].size;
    volatile unsigned short *clut = (volatile unsigned short *)(field_clut_vram + slot * 32);
    jo_texture_definition *texture = &__jo_sprite_def[forest_sprite_base + slot];
    unsigned int i;
    slDMAWait(); /* async DMA: one transfer at a time */
    jo_dma_copy((void *)(field_pool + t->offset), (void *)(JO_VDP1_VRAM + addr), t->length);
    for (i = 0; i < 16; ++i) {
        clut[i] = field_cluts[tile][i];
        kokiri_cluts[slot][i] = field_cluts[tile][i];
    }
    kokiri_tiles[slot].width = t->width;
    kokiri_tiles[slot].height = t->height;
    kokiri_tiles[slot].offset = addr;
    kokiri_tiles[slot].length = t->length;
    texture->width = t->width;
    texture->height = t->height;
    texture->adr = (unsigned short)VRAM_UNITS(addr);
    texture->size = JO_MULT_BY_32(t->width & 0x1f8) | t->height;
    tile_fog[slot] = 255;
}

/* Copy resident pieces into the room tables, in group order. */
static void __attribute__((optimize("O2"))) field_rebuild(void)
{
    unsigned int g, v = 0, p = 0, o = 0, i;
    for (g = 0; g < field_head->groups; ++g) {
        const field_piece_t *piece;
        const POINT *points;
        const POLYGON *polys;
        const ATTR *attrs;
        unsigned int c = field_current[g];
        if (c == FIELD_NONE) continue;
        piece = &field_pieces[c];
        if (v + piece->points > KOKIRI_VERTEX_COUNT || p + piece->polys > KOKIRI_POLYGON_COUNT ||
            o >= KOKIRI_OBJECT_COUNT) {
            ++field_overflow;     /* the bake proves this unreachable; never write past */
            continue;
        }
        points = (const POINT *)(field_blob + piece->data);
        polys = (const POLYGON *)(points + piece->points);
        attrs = (const ATTR *)(polys + piece->polys);
        for (i = 0; i < piece->points; ++i) {
            kokiri_pdata.pntbl[v + i][0] = points[i][0];
            kokiri_pdata.pntbl[v + i][1] = points[i][1];
            kokiri_pdata.pntbl[v + i][2] = points[i][2];
        }
        for (i = 0; i < piece->polys; ++i) {
            POLYGON *q = &kokiri_pdata.pltbl[p + i];
            ATTR *a = &kokiri_pdata.attbl[p + i];
            *q = polys[i];
            q->Vertices[0] += v; q->Vertices[1] += v;
            q->Vertices[2] += v; q->Vertices[3] += v;
            *a = attrs[i];
            if ((a->dir & 7) != 4) {
                unsigned int slot = field_tile_slot[a->texno];
                a->texno = (unsigned short)(forest_sprite_base + slot);
                a->colno = (unsigned short)VRAM_UNITS((unsigned int)(field_clut_vram + slot * 32) -
                                                      JO_VDP1_VRAM);
            }
            kokiri_objects[p + i] = (unsigned char)o;
            forest_mesh[p + i] = forest_face_flags(p + i);
        }
        for (i = 0; i < 3; ++i) {
            kokiri_bounds[o].minimum[i] = piece->bounds[i];
            kokiri_bounds[o].maximum[i] = piece->bounds[3 + i];
        }
        v += piece->points; p += piece->polys; ++o;
    }
    forest_vertex_count = kokiri_pdata.nbPoint = v;
    forest_polygon_count = kokiri_pdata.nbPolygon = p;
    forest_object_count = o;
    forest_prepared = false;
}

/* Release leaving pieces' tiles, then acquire entering ones, then rebuild.
** A piece whose tile cannot get a slot is dropped (the bake rules it out). */
static void field_apply(void)
{
    unsigned int g, j;
    for (g = 0; g < field_head->groups; ++g) {
        unsigned int c = field_current[g];
        const uint16_t *refs;
        if (c == FIELD_NONE || c == field_want[g]) continue;
        refs = field_refs(&field_pieces[c]);
        for (j = 0; j < field_pieces[c].refs; ++j) {
            unsigned int t = refs[j];
            if (field_tile_ref[t] && !--field_tile_ref[t]) {
                field_slot_free(&field_slots, field_tiles[t].bucket, field_tile_slot[t]);
                field_tile_slot[t] = FIELD_NONE;
            }
        }
        field_current[g] = FIELD_NONE;
    }
    for (g = 0; g < field_head->groups; ++g) {
        unsigned int w = field_want[g];
        const uint16_t *refs;
        if (w == FIELD_NONE || w == field_current[g]) continue;
        refs = field_refs(&field_pieces[w]);
        for (j = 0; j < field_pieces[w].refs; ++j) {
            unsigned int t = refs[j];
            if (!field_tile_ref[t]) {
                unsigned int slot = field_slot_alloc(&field_slots, field_tiles[t].bucket);
                if (slot == FIELD_NONE) break;
                field_tile_slot[t] = (uint16_t)slot;
                field_upload(t, slot);
            }
            ++field_tile_ref[t];
        }
        if (j < field_pieces[w].refs) {
            /* Undo this piece's references; it stays out this swap. */
            while (j--) {
                unsigned int t = refs[j];
                if (!--field_tile_ref[t]) {
                    field_slot_free(&field_slots, field_tiles[t].bucket, field_tile_slot[t]);
                    field_tile_slot[t] = FIELD_NONE;
                }
            }
            ++field_overflow;
            continue;
        }
        field_current[g] = (uint16_t)w;
    }
    slDMAWait();
    field_rebuild();
    ++field_swaps;
}

static void field_position(int *x, int *z)
{
    *x = demo_link_active ? demo_link.x : demo_camera.x;
    *z = demo_link_active ? demo_link.z : demo_camera.z;
}

static bool __attribute__((optimize("Os"))) field_stream_load(unsigned int scene, unsigned int room)
{
    char name[] = "S0R0.STM";
    int length = 0;
    unsigned int i, at, pools = 0, required, capacity;
    int x, z;
    field_stream_free();
    name[1] = asset_name_digit(scene); name[3] = asset_name_digit(room);
    asset_loading(name);
    field_blob = (unsigned char *)jo_fs_read_file_ptr(name, 0, &length);
    asset_loading_done();
    if (!field_blob) { jo_core_error("%s does not fit RAM cart", name); return false; }
    field_head = (const field_header_t *)field_blob;
    at = sizeof(field_header_t);
    field_buckets = (const field_bucket_t *)(field_blob + at);
    at += field_head->buckets * sizeof(field_bucket_t);
    field_tiles = (const field_tile_t *)(field_blob + at);
    at += field_head->tiles * sizeof(field_tile_t);
    field_cluts = (const unsigned short (*)[16])(field_blob + at);
    at += field_head->tiles * 32;
    field_pieces = (const field_piece_t *)(field_blob + at);
    if (length <= 0 || (field_head->buckets <= FIELD_MAX_BUCKETS && !field_validate((unsigned int)length)) ||
        field_head->buckets > FIELD_MAX_BUCKETS) {
        field_stream_free();
        jo_core_error("%s is malformed", name);
        return false;
    }
    field_pool = field_blob + field_head->pool_offset;
    for (i = 0; i < field_head->buckets; ++i)
        pools += field_buckets[i].size * field_buckets[i].slots;
    relocate_resident(GAME_TEXTURE_BASE);
    capacity = 0x7fef8u - GAME_TEXTURE_BASE;
    required = resident_bytes + pools + field_head->slots * 32;
    if (required > capacity || resident_sprites + field_head->slots > JO_MAX_SPRITE) {
        field_stream_free();
        jo_core_error("%s: VRAM %d/%d, sprites %d/%d", name, (int)required, (int)capacity,
                      (int)(resident_sprites + field_head->slots), (int)JO_MAX_SPRITE);
        return false;
    }
    field_tile_slot = jo_malloc(field_head->tiles * sizeof(uint16_t));
    field_tile_ref = jo_malloc(field_head->tiles);
    field_current = jo_malloc(field_head->groups * sizeof(uint16_t));
    field_want = jo_malloc(field_head->groups * sizeof(uint16_t));
    field_stack = jo_malloc(field_head->slots * sizeof(uint16_t));
    if (!field_tile_slot || !field_tile_ref || !field_current || !field_want || !field_stack ||
        !field_slots_init(&field_slots, field_buckets, field_head->buckets, field_stack,
                          field_head->slots)) {
        field_stream_free();
        jo_core_error("%s: no RAM for stream tables", name);
        return false;
    }
    for (i = 0; i < field_head->tiles; ++i) { field_tile_slot[i] = FIELD_NONE; field_tile_ref[i] = 0; }
    for (i = 0; i < field_head->groups; ++i) field_current[i] = FIELD_NONE;
    vram_used = resident_bytes;
    sprite_next = resident_sprites;
    forest_sprite_base = sprite_next;
    at = texture_base + vram_used;
    for (i = 0; i < field_head->buckets; ++i) {
        field_bucket_vram[i] = at;
        at += field_buckets[i].size * field_buckets[i].slots;
    }
    field_clut_vram = (unsigned char *)JO_VDP1_VRAM + at;
    forest_palette = field_clut_vram;
    vram_used += pools + field_head->slots * 32;
    sprite_next += field_head->slots;
    if (sprite_next > kokiri_sprite_peak) kokiri_sprite_peak = sprite_next;
    forest_tile_count = field_head->slots;
    for (i = 0; i < forest_tile_count; ++i) tile_fog[i] = 255;
    forest_lods = (mesh_lod_t *)ram_cart_fixed(RAM_CART_MESH_LOD_OFFSET, RAM_CART_MESH_LOD_BYTES);
    forest_lod_count = 0;
    field_active = true;
    field_owl = story_route_owl_active();
    field_position(&x, &z);
    field_choose(field_pieces, field_head->pieces, field_current, field_want,
                 field_head->groups, x, z, (int)field_head->hysteresis, field_owl);
    field_apply();
    forest_room = (int)room;
    requested_room = (int)room;
    forest_scene = (unsigned char)scene;
    forest_far_current = (int)field_head->far;
    actor_vram_base = vram_used;
    actor_sprite_base = sprite_next;
    ++actor_bank_generation;
    return true;
}

/* Per frame: re-choose every 4th frame or on an owl change; swap when VDP1 is
** idle. A busy VDP1 just retries next frame, like a room-bank swap. */
static void field_stream_step(void)
{
    int x, z;
    bool owl;
    if (!field_active || forest_scene != SCENE_SPOT00) return;
    owl = story_route_owl_active();
    if (owl == field_owl && (++field_tick & 3)) return;
    field_position(&x, &z);
    if (!field_choose(field_pieces, field_head->pieces, field_current, field_want,
                      field_head->groups, x, z, (int)field_head->hysteresis, owl))
        { field_owl = owl; return; }
    if (!vdp1_wait_for_draw_end()) return;
    field_owl = owl;
    field_apply();
}

unsigned int kokiri_field_stream_stat(unsigned int which)
{
    switch (which) {
    case 0: return field_active ? forest_object_count : 0;
    case 1: return field_swaps;
    case 2: return field_overflow;
    default: return field_owl;
    }
}

static bool __attribute__((optimize("Os"))) room_load_bank(unsigned int scene, unsigned int room)
{
    unsigned int header[8], expected, i;
    if (field_active) field_stream_free();
    if (scene == SCENE_SPOT00 && room == 0) {
        if (!kokiri_bank_allocate()) return false;
        return field_stream_load(scene, room);
    }
    char mesh_name[12], pixel_name[12];
    jo_file file;
    bool ok;
    if (!asset_scene_name(mesh_name, scene, (int)room, "MSH") ||
        !asset_scene_name(pixel_name, scene, (int)room, "TEX") || !kokiri_bank_allocate()) return false;
    const unsigned char *cached = scene == 2 && room < 10 ? opening_cache[room].mesh : 0;
    bool from_cache = cached != 0;
    int mesh_bytes = from_cache ? opening_cache[room].mesh_bytes : 0;
    if (!from_cache) {
        /* Whole .MSH in one CD read; then parse it like the opening cache. */
        asset_loading(mesh_name);
        cached = (const unsigned char *)ram_cart_load_scratch(mesh_name, &mesh_bytes);
        asset_loading_done();
        if (!cached) return false;
    }
    if (mesh_bytes < (int)sizeof(header) || !room_read(&file, header, sizeof(header), &cached))
        return false;
    expected = 32 + header[1]*12 + header[2]*32 + header[3]*44 +
               ((header[2]+3)&~3u) + header[5]*24 + header[6]*sizeof(mesh_lod_t);
    /* A bank with no tiles is flat shaded: every face carries its own colour
    ** in its ATTR and there is no pixel file at all. The dream's Hyrule Field
    ** is built that way, so header[3] of zero is a kind of bank, not a
    ** malformed one. */
    if (header[0] != 0x4b524d31 || !header[1] || !header[2] ||
        header[1] > KOKIRI_VERTEX_COUNT || header[2] > KOKIRI_POLYGON_COUNT ||
        header[3] > KOKIRI_TILE_COUNT || header[4] > KOKIRI_PIXEL_BYTES ||
        header[5] > KOKIRI_OBJECT_COUNT || header[6] > MESH_LOD_MAX ||
        (header[6] && !ram_cart_fixed(RAM_CART_MESH_LOD_OFFSET, RAM_CART_MESH_LOD_BYTES)) ||
        (unsigned int)mesh_bytes != expected ||
        (from_cache && (unsigned int)opening_cache[room].pixel_bytes != header[3]*4)) {
        return false;
    }
    /* Check the destination layout, before relocating or overwriting a bank.
    ** Report capacity failures separately from malformed files. */
    {
        unsigned int capacity = 0x7fef8u - (scene == KOKIRI_FIELD_SCENE ?
                                  CUTSCENE_TEXTURE_BASE : GAME_TEXTURE_BASE);
        unsigned int required = resident_bytes + header[4] + header[3]*32;
        if (required > capacity || resident_sprites + header[3] > JO_MAX_SPRITE) {
            jo_core_error("%s: VRAM %d/%d, sprites %d/%d", mesh_name,
                          (int)required, (int)capacity,
                          (int)(resident_sprites + header[3]), (int)JO_MAX_SPRITE);
            return false;
        }
    }
    ok = room_read(&file, kokiri_pdata.pntbl, header[1]*sizeof(POINT), &cached) &&
         room_read(&file, kokiri_pdata.pltbl, header[2]*sizeof(POLYGON), &cached) &&
         room_read(&file, kokiri_pdata.attbl, header[2]*sizeof(ATTR), &cached) &&
         room_read(&file, kokiri_tiles, header[3]*sizeof(kokiri_tile), &cached) &&
         room_read(&file, kokiri_cluts, header[3]*32, &cached) &&
         room_read(&file, kokiri_objects, (header[2]+3)&~3u, &cached) &&
         room_read(&file, kokiri_bounds, header[5]*sizeof(kokiri_object), &cached);
    forest_lods = (mesh_lod_t *)ram_cart_fixed(RAM_CART_MESH_LOD_OFFSET, RAM_CART_MESH_LOD_BYTES);
    forest_lod_count = 0;
    if (ok && header[6])
        ok = room_read(&file, forest_lods, header[6]*sizeof(mesh_lod_t), &cached);
    for (i = 0; ok && i < header[6]; ++i)
        ok = forest_lods[i].lod1_object < header[5] &&
             (forest_lods[i].lod0_object == MESH_LOD_NONE ||
              forest_lods[i].lod0_object < header[5]);
    if (!ok) return false;
    forest_lod_count = header[6];
    relocate_resident(scene == KOKIRI_FIELD_SCENE ? CUTSCENE_TEXTURE_BASE : GAME_TEXTURE_BASE);
    /* Every bank replaces the same forest slots; Link/fairies stay resident. */
    vram_used = resident_bytes;
    sprite_next = resident_sprites;
    forest_sprite_base = sprite_next;
    /* Nothing to upload for a flat bank: its ATTRs already hold their colours
    ** and mesh_load() would only patch texno/colno over them. */
    if (header[3] &&
        !mesh_load(pixel_name,header[4],kokiri_tiles,header[3],
                   (const unsigned short (*)[16])kokiri_cluts,&kokiri_pdata,header[2],
                   from_cache ? opening_cache[room].pixels : 0))
        return false;
    forest_vertex_count = kokiri_pdata.nbPoint = header[1];
    forest_polygon_count = kokiri_pdata.nbPolygon = header[2];
    forest_tile_count = header[3]; forest_object_count = header[5];
    for (i=0;i<forest_polygon_count;++i)
        forest_mesh[i] = forest_face_flags(i);
    for (i=0;i<forest_tile_count;++i) tile_fog[i] = 255;
    forest_prepared = false;
    forest_room = (int)room;
    requested_room = (int)room;
    forest_scene = (unsigned char)scene;
    forest_far_current = scene == KOKIRI_FIELD_SCENE ? FIELD_FAR :
                         (scene == 2 || scene>=20 ? 2620 : FOREST_FAR_DEFAULT);
    actor_vram_base = vram_used;
    actor_sprite_base = sprite_next;
    ++actor_bank_generation;
    return true;
}
#endif

bool __attribute__((optimize("Os"))) kokiri_scene_load(void)
{
    forest_prepared = false;
    forest_fog_init();
#ifndef KOKIRI_STREAM_ROOMS
    if (!mesh_load(KOKIRI_PIXEL_FILE, KOKIRI_PIXEL_BYTES, kokiri_tiles,
                   KOKIRI_TILE_COUNT, kokiri_cluts, &kokiri_pdata,
                   KOKIRI_POLYGON_COUNT, 0))
        return (false);
#endif
    {
        /* Link's POLYGON/ATTR tables are cold (equipment changes copy them),
        ** so they live on the cart, not in work RAM. */
        unsigned char *mesh = (unsigned char *)ram_cart_fixed(RAM_CART_LINKMESH_OFFSET,
                                                              RAM_CART_LINKMESH_BYTES);
        int length = 0;
        typedef char link_mesh_fits_carve[LINK_MESH_BYTES <= RAM_CART_LINKMESH_BYTES ? 1 : -1];
        jo_file probe;
        /* jo_fs_read_file_ptr writes the whole file: refuse a disc file that
        ** would overrun the carve (it once clobbered Navi glow/LOD/DEKUBABA). */
        if (jo_fs_open(&probe, LINK_MESH_FILE)) {
            int size = probe.size;
            jo_fs_close(&probe);
            if (size > (int)RAM_CART_LINKMESH_BYTES) {
                jo_core_error("%s is %d B, cart carve %d B", LINK_MESH_FILE,
                              size, (int)RAM_CART_LINKMESH_BYTES);
                return (false);
            }
        }
        if (!mesh || !jo_fs_read_file_ptr(LINK_MESH_FILE, mesh, &length) ||
            length != (int)LINK_MESH_BYTES)
            return (false);
        link_pdata.pltbl = (POLYGON *)mesh;
        link_pdata.attbl = (ATTR *)(mesh + LINK_POLYGON_COUNT * sizeof(POLYGON));
    }
    {
        /* Tile descriptors + CLUTs: read here only (LINKTEX.BIN, cart). */
        unsigned char *tex = (unsigned char *)ram_cart_fixed(RAM_CART_LINKTEX_OFFSET,
                                                             RAM_CART_LINKTEX_BYTES);
        int length = 0;
        if (!tex || LINK_TEX_BYTES > RAM_CART_LINKTEX_BYTES ||
            !jo_fs_read_file_ptr(LINK_TEX_FILE, tex, &length) ||
            length != (int)LINK_TEX_BYTES ||
            !mesh_load(LINK_PIXEL_FILE, LINK_PIXEL_BYTES, (const kokiri_tile *)tex,
                       LINK_TILE_COUNT,
                       (const unsigned short (*)[16])(tex + LINK_TILE_COUNT * sizeof(link_tile)),
                       &link_pdata, LINK_POLYGON_COUNT, 0))
            return (false);
    }
    if (!fairy_load()) return (false);
    (void)karebaba_draw_load();
    /* Immutable 16 red + 16 blue RGB-offset tables, shared by all actors.
     * Stored in the resident allocation so scene/cutscene relocation carries
     * them with textures; never use the SDK's overlapping 0x70000 scratch. */
    hit_table_offset=vram_used;
    if(vram_used+256>TEXTURE_CAPACITY)return false;
    {
        volatile unsigned short *table=(volatile unsigned short *)(JO_VDP1_VRAM+texture_base+vram_used);
        unsigned i,j;
        for(i=0;i<32;++i){
            unsigned k=i%16+1,lo=16-k,hi=k==16?31:16+k;
            unsigned colour=i<16?C_RGB(hi,lo,lo):C_RGB(lo,lo,hi);
            for(j=0;j<4;++j)table[i*4+j]=colour;
        }
        vram_used+=256;
    }
    /* Minimap markers are resident too (before the first bank). */
    if (!minimap_init()) return (false);
#ifdef KOKIRI_STREAM_ROOMS
    resident_bytes = vram_used;
    resident_sprites = sprite_next;
    /* Kokiri Forest for now: it is the only scene with mesh banks. Link's
    ** house is a prerendered backdrop and needs the VDP2 path instead, which
    ** is the next piece of work. */
    return room_load_bank(SCENE_SPOT04, 0);
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
    /* Field streaming follows the camera through cutscenes too: it never
    ** loads another bank, it only reshuffles the Field's own pieces. */
    field_stream_step();
    /* A cutscene owns the resident bank. Room streaming follows Link through
    ** the forest's portals, and during the dream it would happily load a
    ** Kokiri room straight over the Hyrule Field bank the cutscene asked for.
    ** Link is not walking anywhere during a cutscene, so there is nothing to
    ** stream for. */
    if (cutscene_is_playing()) { room_gameplay = false; return true; }
    if (!demo_link_active || demo_title_is_visible() || backdrop_active || forest_scene == 4) { room_gameplay = false; return true; }
    if (!room_gameplay) { target = forest_room; room_gameplay = true; }
    dungeon_doors_constrain(&demo_link.x,&demo_link.z,demo_link.y-DEMO_LINK_EYE_HEIGHT);
    for (i=0;i<KOKIRI_PORTAL_COUNT;++i) {
        const kokiri_portal *p = &kokiri_portals[i];
        int32_t sine,cosine;
        int dx = demo_link.x-p->x, dz = demo_link.z-p->z;
        int dy = demo_link.y-DEMO_LINK_EYE_HEIGHT-p->y;
        int side, depth, portal_side;
        if (p->scene != forest_scene) continue;
        if (forest_room != p->front && forest_room != p->back) continue;
        kokiri_camera_sincos(p->yaw,&sine,&cosine);
        side = (int)(((int64_t)dx*cosine-(int64_t)dz*sine)>>16);
        depth = (int)(((int64_t)dx*sine+(int64_t)dz*cosine)>>16);
        /* Original invisible tunnel volume; the central 100-unit band keeps
         * tiny movements from repeatedly swapping CD banks. */
        portal_side = p->kind>=8 ?
            (dungeon_door_open(i) ? room_portal_side(0,side,dy,depth) : -1) :
            room_portal_side(p->kind, side, dy, depth);
        if (portal_side >= 0)
            target = portal_side == 0 ? p->front : p->back;
    }
    requested_room = target;
    if (target != forest_room) {
        /* Wait for the in-flight draw without resubmitting it on every retry.
         * A timed-out draw leaves the bank untouched for the next callback. */
        if (!vdp1_wait_for_draw_end()) return true;
        if (!room_load_bank(forest_scene, (unsigned int)target)) return false;
        save_room_changed(save_state.scene_id);
        player_items_room_changed();
        return true;
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

unsigned int        kokiri_scene_vram_percent(void)
{
    unsigned int allocated = texture_base + vram_used + (0x80000u - 0x7fef8u);
    return allocated >= 0x80000u ? 100u : allocated * 100u / 0x80000u;
}

static void         submit(PDATA *pdata, unsigned int bit)
{
    /* slPutPolygon returns FALSE when SGL cannot accept the list, e.g. the
    ** frame's polygon or vertex budget is exhausted. Ignoring it is how a
    ** partially drawn scene could look complete, so every refusal is recorded. */
    unsigned i;
    if(hit_filter)for(i=0;i<(unsigned)pdata->nbPolygon;++i){
        pdata->attbl[i].atrb|=CL_Gouraud;
        pdata->attbl[i].gstb=(texture_base+hit_table_offset)/8+hit_filter-1;
    }
    if (slPutPolygon(pdata) == FALSE)
        ++kokiri_rejected;
    else
    {
        kokiri_accepted_mask |= bit;
        submitted += pdata->nbPolygon;
    }
    /* These imported meshes use No_Gouraud. Restore shared attributes after
     * SGL copied the command, so the next instance/room never inherits tint. */
    if(hit_filter)for(i=0;i<(unsigned)pdata->nbPolygon;++i){
        pdata->attbl[i].atrb&=~CL_Gouraud;pdata->attbl[i].gstb=No_Gouraud;
    }
}

#include "link_equipment.h"
/* Low Work RAM (ram_low.h): 16.6 KB off high work RAM. Filled before any
** submit (equipped_mask starts invalid), so boot garbage is never read. */
#define equipped_polygons   ((POLYGON *)RAM_LOW(RAM_LOW_EQUIP_POLY_OFFSET))
#define equipped_attributes ((ATTR *)RAM_LOW(RAM_LOW_EQUIP_ATTR_OFFSET))
typedef char equip_poly_fits[LINK_VISIBLE_POLYGONS * sizeof(POLYGON) <=
                             RAM_LOW_EQUIP_POLY_BYTES ? 1 : -1];
typedef char equip_attr_fits[LINK_VISIBLE_POLYGONS * sizeof(ATTR) <=
                             RAM_LOW_EQUIP_ATTR_BYTES ? 1 : -1];
static unsigned int equipped_count;
static unsigned int equipped_mask = 255;
static void invalidate_equipped(void) { equipped_mask = 255; }

static void link_part(unsigned int first, unsigned int count)
{
    static const ATTR tunics[2]={
        ATTRIBUTE(Dual_Plane,SORT_CEN|UseNearClip,0,C_RGB(0,0,31),No_Gouraud,CL32KRGB|ECdis,sprPolygon,No_Option),
        ATTRIBUTE(Dual_Plane,SORT_CEN|UseNearClip,0,C_RGB(25,0,0),No_Gouraud,CL32KRGB|ECdis,sprPolygon,No_Option)};
    unsigned int i;
    for (i = 0; i < count; ++i) {
        equipped_polygons[equipped_count] = link_pdata.pltbl[first+i];
        equipped_attributes[equipped_count++] = save_state.tunic>0 && save_state.tunic<=2 &&
            (link_tunic_faces[(first+i)/8]&(1u<<((first+i)%8))) ? tunics[save_state.tunic-1] : link_pdata.attbl[first+i];
    }
}

#ifdef DOSEI_WARP_PROBE
int kokiri_warp_probe(unsigned int field)
{
    switch (field) {
    case 0: return warp_near_depth;
    case 1: return warp_near_far;
    case 2: return warp_near_extent;
    case 3: return warp_near_tile;
    case 4: return warp_near_verts[0];
    case 5: return warp_near_verts[1];
    case 6: return warp_span_score;
    case 7: return warp_span_depth;
    case 8: return warp_span_far;
    case 9: return warp_span_extent;
    case 10: return warp_span_tile;
    case 11: return warp_span_verts[0];
    case 12: return warp_span_verts[1];
    default: return 0;
    }
}
#endif

#ifdef KOKIRI_STREAM_ROOMS
/* Fill lod_state from Link's feet (camera when Link is inactive); true when
** any mesh changed level since the last prepared frame. */
static bool forest_lod_changed(void)
{
    unsigned int i;
    bool changed = false;
    int x = demo_camera.x, y = demo_camera.y, z = demo_camera.z;
    if (demo_link_active) {
        x = demo_link.x; y = demo_link.y - DEMO_LINK_EYE_HEIGHT; z = demo_link.z;
    }
    for (i = 0; i < forest_lod_count; ++i) {
        unsigned char state = (unsigned char)mesh_lod_select(&forest_lods[i], x, y, z);
        lod_state[i] = state;
        changed |= state != lod_state_applied[i];
    }
    return changed;
}
#endif

void                kokiri_scene_draw(void)
{
    unsigned int i, j, visible = forest_polygon_count;
    int32_t sine, cosine;
    frame_timer_begin(FRAME_PHASE_PREP);
    if (forest_scene == 4) {
        /* Original pre-rendered house panorama, centred on the eye just as
         * Skybox_Draw does. Large radius sorts the art behind Link/Navi. */
        kokiri_rejected = 0;
        kokiri_accepted_mask = 0;
        submitted = 0;
        frame_timer_end(FRAME_PHASE_PREP);
        jo_3d_push_matrix();
        jo_3d_translate_matrix(demo_camera.x, -demo_camera.y, demo_camera.z);
        submit(&kokiri_pdata, 1u);
        jo_3d_pop_matrix();
        return;
    }
    /* Geometry/fog depend on the camera. Unaccepted actor-order experiments
     * are excluded from normal builds. */
    if (forest_prepared && prepared_x == demo_camera.x &&
        prepared_y == demo_camera.y && prepared_z == demo_camera.z &&
        prepared_yaw == demo_yaw && prepared_pitch == demo_pitch
#ifdef KOKIRI_STREAM_ROOMS
        && !forest_lod_changed()
#endif
        ) {
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
    forest_lod_changed();
    for (i = 0; i < forest_lod_count; ++i) {
        const mesh_lod_t *m = &forest_lods[i];
        unsigned int state = lod_state[i];
        lod_state_applied[i] = (unsigned char)state;
        if (state != MESH_LOD_FAR) object_visible[m->lod1_object] = 0;
        if (m->lod0_object != MESH_LOD_NONE)
            object_visible[m->lod0_object] = state == MESH_LOD_NEAR;
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
#ifdef DOSEI_WARP_PROBE
    warp_near_depth = 32767; warp_near_tile = -1;
    warp_span_score = 0; warp_span_tile = -1;
#endif
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
            if (forest_scene == 2 && (forest_mesh[i] & 4)) {
                const unsigned short *v = kokiri_pdata.pltbl[i].Vertices;
                int low_x = 32767, high_x = -32768;
                int low_z = 32767, high_z = -32768;
                int dx, dz;
                for (j = 0; j < 4; ++j) {
                    int x = kokiri_pdata.pntbl[v[j]][0] >> 16;
                    int z = kokiri_pdata.pntbl[v[j]][2] >> 16;
                    if (x < low_x) low_x = x;
                    if (x > high_x) high_x = x;
                    if (z < low_z) low_z = z;
                    if (z > high_z) high_z = z;
                }
                dx = demo_camera.x < low_x ? low_x - demo_camera.x :
                     demo_camera.x > high_x ? demo_camera.x - high_x : 0;
                dz = demo_camera.z < low_z ? low_z - demo_camera.z :
                     demo_camera.z > high_z ? demo_camera.z - high_z : 0;
                if ((int64_t)dx * dx + (int64_t)dz * dz > 1310 * 1310 ||
                    nearest >= FOREST_FOG_END) {
                    attr->dir = (attr->dir & ~7u) | 4;
                    attr->atrb = (attr->atrb & ~0x38u) | CL32KRGB;
                    attr->colno = C_RGB(27, 27, 19);
                } else {
                    attr->dir = (attr->dir & ~7u) | 2;
                    attr->atrb = (attr->atrb & ~0x38u) | (1 << 3);
                    attr->colno = (unsigned short)VRAM_UNITS(
                        (unsigned int)(forest_palette + tile * 32) - JO_VDP1_VRAM);
                }
            }
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
            if (tile < forest_tile_count && (attr->dir & 7) != 4 &&
                nearest < tile_depth[tile]) tile_depth[tile] = nearest;
#ifdef DOSEI_WARP_PROBE
            {
                const unsigned short *v = kokiri_pdata.pltbl[i].Vertices;
                int extent = 0, axis, corner, range = 32767;
                for (axis = 0; axis < 3; ++axis) {
                    int low = kokiri_pdata.pntbl[v[0]][axis] >> 16, high = low;
                    for (corner = 1; corner < 4; ++corner) {
                        int value = kokiri_pdata.pntbl[v[corner]][axis] >> 16;
                        if (value < low) low = value;
                        if (value > high) high = value;
                    }
                    if (high - low > extent) extent = high - low;
                }
                /* True distance to the eye, not the forward component.
                ** Ranking on depth alone promoted faces standing far to the
                ** side whose forward distance happened to be tiny, which is
                ** not what the near view shows. */
                for (corner = 0; corner < 4; ++corner) {
                    int dx = (kokiri_pdata.pntbl[v[corner]][0] >> 16) - demo_camera.x;
                    int dy = -(kokiri_pdata.pntbl[v[corner]][1] >> 16) - demo_camera.y;
                    int dz = (kokiri_pdata.pntbl[v[corner]][2] >> 16) - demo_camera.z;
                    int ax = dx < 0 ? -dx : dx, ay = dy < 0 ? -dy : dy;
                    int az = dz < 0 ? -dz : dz, hi, mid, lo, estimate;
                    hi = ax > ay ? ax : ay; if (az > hi) hi = az;
                    lo = ax < ay ? ax : ay; if (az < lo) lo = az;
                    mid = ax + ay + az - hi - lo;
                    /* Cheap integer length: max + (mid+lo)/3, within a few
                    ** percent and monotonic, which is all a ranking needs. */
                    estimate = hi + (mid + lo) / 3;
                    if (estimate < range) range = estimate;
                }
                if (farthest < 0) range = 32767;
                if (range < warp_near_depth) {
                    warp_near_depth = range; warp_near_far = nearest;
                    warp_near_extent = extent; warp_near_tile = (short)tile;
                    warp_near_verts[0]=v[0]; warp_near_verts[1]=v[1];
                    warp_near_verts[2]=v[2]; warp_near_verts[3]=v[3];
                }
                if (range > 0 && range < 32767 && nearest < FOREST_FAR) {
                    int score = extent * 256 / range;
                    if (score > warp_span_score) {
                        warp_span_score = score; warp_span_depth = range;
                        warp_span_far = nearest; warp_span_extent = extent;
                        warp_span_tile = (short)tile;
                        warp_span_verts[0]=v[0]; warp_span_verts[1]=v[1];
                        warp_span_verts[2]=v[2]; warp_span_verts[3]=v[3];
                    }
                }
            }
#endif
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
        else if (tile_depth[i] >= FOREST_FOG_END) amount = 16;
        else amount = (tile_depth[i] - FOREST_FOG_START) * 16 /
                      (FOREST_FOG_END - FOREST_FOG_START);
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
        slRotY((ANGLE)yaw);
        if (cutscene_is_playing() && cutscene_id() == CUTSCENE_NIGHTMARE) {
            /* OoT's camera/cues use Actor_Init's 0.01 model scale. Gameplay
             * normalizes Link to 60 units and grounds him; undo that here.
             * Otherwise the bridge fly-by enters the enlarged head. */
            const FIXED native_scale = (FIXED)(4294967296ULL /
                                              (100u * LINK_ANIM_SCALE_Q16));
            slScale(native_scale, native_scale, native_scale);
            jo_3d_translate_matrix(-LINK_ANIM_SHIFT_X, LINK_ANIM_SHIFT_Y,
                                    -LINK_ANIM_SHIFT_Z);
        }
        unsigned visible_gear = player_items_stick() ? gameplay.equipped & ~GP_SWORD : gameplay.equipped;
        if (equipped_mask != (visible_gear | (save_state.tunic<<8))) {
            equipped_count = 0;
            link_part(LINK_BODY_FIRST, LINK_BODY_COUNT);
            if (visible_gear & GP_SWORD) {
                link_part(LINK_LEFT_SWORD_FIRST, LINK_LEFT_SWORD_COUNT);
                link_part(LINK_SHEATH_FIRST, LINK_SHEATH_COUNT);
            } else link_part(LINK_LEFT_EMPTY_FIRST, LINK_LEFT_EMPTY_COUNT);
            if (gameplay.equipped & GP_SHIELD)
                link_part(LINK_RIGHT_SHIELD_FIRST, LINK_RIGHT_SHIELD_COUNT);
            else link_part(LINK_RIGHT_EMPTY_FIRST, LINK_RIGHT_EMPTY_COUNT);
            equipped_mask = visible_gear | (save_state.tunic<<8);
        }
        /* One submission: submitting each variant separately would transform
         * the full POINT table repeatedly and exhaust SGL's vertex work area. */
        {
            PDATA equipped = link_pdata;
            equipped.pltbl = equipped_polygons;
            equipped.attbl = equipped_attributes;
            equipped.nbPolygon = equipped_count;
#ifdef LINK_BASE_VERTICES
            /* The first-person arm's vertices are the tail; never transform
             * them for the third-person body. */
            equipped.nbPoint = LINK_BASE_VERTICES;
#endif
            if(!cutscene_is_playing() && gameplay.hurt_flash_timer && !gameplay.dead){
                int32_t sn,cs;kokiri_camera_sincos(gameplay.hurt_flash_phase,&sn,&cs);
                kokiri_hit_filter(1+(unsigned)((cs+65536)*15/131072));
            }
            submit(&equipped, 2u);
            kokiri_hit_filter(0);
        }
    }
    jo_3d_pop_matrix();
#ifdef DOSEI_ACTOR_ORDER_PROBE
    actor_order_queue();
#endif
}

/* Player_OverrideLimbDrawGameplayFirstPerson, child with the slingshot: only
 * the near right shoulder and the stretched slingshot arm draw. The posed head
 * focus (link_anim_focus) is pinned to the first-person camera's focus, and
 * the model turns by the view yaw and pitch, so the arm holds its place in the
 * frame as OoT's does. (x, y, z) is that world focus. The caller poses the
 * aim clip with link_anim_first_person(true). */
void                kokiri_link_draw_first_person(int x, int y, int z, int yaw, int pitch)
{
#ifdef LINK_FP_SLING_FIRST
    int32_t focus[3];
    PDATA arm = link_pdata;
    link_anim_focus(focus);
    equipped_count = 0;
    link_part(LINK_FP_SHOULDER_FIRST, LINK_FP_SHOULDER_COUNT);
    link_part(LINK_FP_SLING_FIRST, LINK_FP_SLING_COUNT);
    invalidate_equipped();          /* the body list is rebuilt next draw */
    arm.pltbl = equipped_polygons;
    arm.attbl = equipped_attributes;
    arm.nbPolygon = equipped_count;
    jo_3d_push_matrix();
    jo_3d_translate_matrix(x, -y, z);
    slRotY((ANGLE)yaw);
    slRotX((ANGLE)pitch);
    /* POINT tables carry Y negated; focus is +Y up. */
    slTranslate(-focus[0], focus[1], -focus[2]);
    submit(&arm, 2u);
    jo_3d_pop_matrix();
#else
    (void)x; (void)y; (void)z; (void)yaw; (void)pitch;
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

static void         fairy_draw(int x, int y, int z, uint16_t yaw, unsigned int tick,
                               unsigned int phase, const unsigned int *glow,
                               unsigned int colour);
static uint16_t     fairy_turn(uint16_t yaw, int32_t *last_x, int32_t *last_z,
                               int32_t x, int32_t z);
static uint16_t     fairy_yaw[KOKIRI_NPC_COUNT];
static int32_t      fairy_last[KOKIRI_NPC_COUNT][2];

void                kokiri_fairies_draw(unsigned int tick)
{
    unsigned int i;
    if (!gameplay_npcs_present())
        return;
    for (i = 0; i < KOKIRI_NPC_COUNT; ++i) {
        unsigned int angle = tick * (97 + i * 3) + i * 6011;
        if (!gameplay_npc_present(i))
            continue;
        int x = (int)gameplay_npc_x(i) + fairy_wave(angle, 18);
        int y = kokiri_npcs[i].y + 58 + fairy_wave(angle * 2 + 9000, 9);
        int z = (int)gameplay_npc_z(i) + fairy_wave(angle + 16384, 14);
        int32_t sine, cosine;
        kokiri_camera_sincos(demo_yaw, &sine, &cosine);
        if ((((int64_t)(x - demo_camera.x) * sine +
              (int64_t)(z - demo_camera.z) * cosine) >> 16) > FOREST_FAR)
            continue;

        fairy_yaw[i] = fairy_turn(fairy_yaw[i], &fairy_last[i][0], &fairy_last[i][1], x, z);
        fairy_draw(x, y, z, fairy_yaw[i], tick, i * 3u, fairy_glow, 0);
    }
}

/* One En_Elf: the posed wings in 3D (gFairyAnim frame, one a 30 Hz step)
** turned to its heading, then the glow billboard, pulsed as
** EnElf_OverrideLimbDraw: scale (sin(timer * 0x1000) * 0.1 + 1). */
static void         fairy_draw(int x, int y, int z, uint16_t yaw, unsigned int tick,
                               unsigned int phase, const unsigned int *glow,
                               unsigned int colour)
{
    FIXED pos[5];
    SPR_ATTR attr = SPR_ATTRIBUTE(0, No_Palet, No_Gouraud, ECdis,
                                  sprNoflip | FUNC_Sprite);
    unsigned int step = tick / 2u + phase;
    if (fairy_wings_ready) {
        jo_3d_push_matrix();
        jo_3d_translate_matrix(x, -y, z);
        slRotY((ANGLE)yaw);
        kokiri_submit_pdata(&fairy_meshes[step % FAIRY_FRAMES]);
        jo_3d_pop_matrix();
    }
    pos[0] = x * 65536;
    pos[1] = -y * 65536;
    pos[2] = z * 65536;
    pos[3] = pos[4] = FAIRY_GLOW_SCALE +
        slMulFX(FAIRY_GLOW_SCALE / 10, slSin((ANGLE)(step * 0x1000u)));
    /* EnElf_Draw: envAlpha = (timer * 50) & 0x1FF, folded to a triangle;
    ** timer counts 20 Hz updates, so x2/3 per step. 0 = big L, 255 = SL. */
    {
        unsigned int env = (step * 100u / 3u) & 0x1FFu;
        if (env > 255u) env = 511u - env;
        unsigned int breath = env * FAIRY_GLOW_STEPS / 256u;
        if (glow) {
            attr.texno = (Uint16)glow[breath];
        } else {
            /* Navi: refill her one slot only when the picture changes. */
            unsigned int want = colour * FAIRY_GLOW_STEPS + breath;
            if (want != navi_glow_shown) {
                const uint16_t *src = (const uint16_t *)(navi_glow_pixels + want * FAIRY_PIXEL_BYTES);
                volatile uint16_t *dst = (volatile uint16_t *)__jo_sprite_pic[navi_glow_slot].data;
                unsigned int k;
                for (k = 0; k < FAIRY_PIXEL_BYTES / 2; ++k) dst[k] = src[k];
                navi_glow_shown = want;
            }
            attr.texno = (Uint16)navi_glow_slot;
        }
    }
    attr.atrb |= (FAIRY_COLMODE_RGB & 7) << 3;
    if (slPutSprite(pos, &attr, 0) == FALSE) ++kokiri_rejected;
}

/* EnElf shape.rot.y: Math_SmoothStepToS toward the travel heading (scale 5,
** max 0x1000 a frame; 0x400 floor). Heading from the position change. */
static uint16_t     fairy_turn(uint16_t yaw, int32_t *last_x, int32_t *last_z,
                               int32_t x, int32_t z)
{
    int32_t dx = x - *last_x, dz = z - *last_z, turn, step;
    *last_x = x;
    *last_z = z;
    if (dx * dx + dz * dz < 1)
        return yaw;
    turn = (int32_t)(int16_t)(uint16_t)(kokiri_camera_facing(dx, dz) - yaw);
    step = turn / 5;
    if (step > 0x1000) step = 0x1000;
    if (step < -0x1000) step = -0x1000;
    if (step > -0x400 && step < 0x400)
        step = turn > 0x400 ? 0x400 : turn < -0x400 ? -0x400 : turn;
    return (uint16_t)(yaw + step);
}

/* Navi in gameplay. Her position is En_Elf's, stepped in src/navi.c. */
void                kokiri_navi_draw(int x, int y, int z)
{
    static int32_t last_x, last_z;
    static uint16_t yaw;
    unsigned int i;
    unsigned int colour = navi_colour();     /* attention_colour_t */
    yaw = fairy_turn(yaw, &last_x, &last_z, x, z);
    /* NPC 1, ENEMY 2; PLAYER and OTHER (green, no set yet) draw white/blue. */
    if (colour > 2u) colour = 0;
    fairy_draw(x, y, z, yaw, demo_world_clock(), 0,
               navi_glow_pixels ? (const unsigned int *)0 : fairy_glow, colour);
    /* EffectSsKiraKira: a 28-unit quad x scale 1000 / 10000 = 2.8 units
    ** over 8 texels, billboarded and turned by its yaw. */
    for (i = 0; sparkle_ready && i < NAVI_SPARKLES; ++i) {
        FIXED pos[5];
        SPR_ATTR attr = SPR_ATTRIBUTE(0, No_Palet, No_Gouraud, ECdis,
                                      sprNoflip | FUNC_Sprite);
        int32_t p[3];
        uint16_t spin;
        unsigned int life;
        if (!navi_sparkle(i, p, &spin, &life))
            continue;
        pos[0] = p[0] * 65536;
        pos[1] = -p[1] * 65536;
        pos[2] = p[2] * 65536;
        pos[3] = pos[4] = 22938;
        attr.texno = (Uint16)sparkle_sprite;
        attr.atrb |= (FAIRY_COLMODE_RGB & 7) << 3;
        if (slPutSprite(pos, &attr, (ANGLE)spin) == FALSE) ++kokiri_rejected;
    }
}

/* One resident sparkle texture as a world billboard; scale is units per texel. */
static void         world_sparkle(int32_t x, int32_t y, int32_t z, FIXED scale, ANGLE spin)
{
    FIXED pos[5];
    SPR_ATTR attr = SPR_ATTRIBUTE(0, No_Palet, No_Gouraud, ECdis,
                                  sprNoflip | FUNC_Sprite);
    pos[0] = x * 65536;
    pos[1] = -y * 65536;
    pos[2] = z * 65536;
    pos[3] = pos[4] = scale;
    attr.texno = (Uint16)sparkle_sprite;
    attr.atrb |= (FAIRY_COLMODE_RGB & 7) << 3;
    if (slPutSprite(pos, &attr, spin) == FALSE) ++kokiri_rejected;
}

static void         item_billboard(unsigned int sprite, int x, int y, int z)
{
    FIXED pos[5];
    SPR_ATTR attr = SPR_ATTRIBUTE(0, No_Palet, No_Gouraud, ECdis,
                                  sprNoflip | FUNC_Sprite);
    int32_t sine, cosine;
    kokiri_camera_sincos(demo_yaw, &sine, &cosine);
    if ((((int64_t)(x - demo_camera.x) * sine +
          (int64_t)(z - demo_camera.z) * cosine) >> 16) > FOREST_FAR)
        return;
    pos[0] = x * 65536;
    pos[1] = -y * 65536;
    pos[2] = z * 65536;
    pos[3] = pos[4] = 2 * 65536;
    attr.texno = (Uint16)sprite;
    attr.atrb |= (FAIRY_COLMODE_RGB & 7) << 3;
    if (slPutSprite(pos, &attr, 0) == FALSE) ++kokiri_rejected;
}

void kokiri_drop_draw(unsigned int item, int x, int y, int z, unsigned int tick)
{
    unsigned int sprite;
    if (item == 254) {
        fairy_draw(x, y + 15, z, 0, tick, 0, fairy_glow, 0);
        return;
    }
    if (item <= 2) sprite = rupee_sprite[item];
    else if (item == 3) sprite = drop_sprite[0];
    else if (item == 12) sprite = drop_sprite[1];
    else if (item == 13) sprite = drop_sprite[2];
    else if (item == 16) sprite = drop_sprite[3];
    else return;
    item_billboard(sprite, x, y, z);
}

/* Item held up during get-item text; chests use original animated models. */
void                kokiri_items_draw(unsigned int tick)
{
    if (!demo_chest_opening() && gameplay.get_item && gameplay.get_item != GP_GET_CONTAINER && gameplay.get_item != GP_GET_CHEST_ITEM) {
        unsigned int sprite = gameplay.get_item == GP_SWORD ? item_sprite[0] :
            gameplay.get_item == GP_SHIELD ? item_sprite[1] :
            gameplay.get_item == GP_GET_NUT ? drop_sprite[1] :
            gameplay.get_item == GP_GET_STICK ? drop_sprite[2] : drop_sprite[0];
        item_billboard(sprite, demo_link.x,
                       demo_link.y - DEMO_LINK_EYE_HEIGHT + 70, demo_link.z);
    }
}

#include "boulder_mesh.h"

/* Maze boulder: faceted sphere matching the collision radius.
 * Still a stand-in until gRollingRockDL is imported (BUG-031). */
void                kokiri_boulder_draw(void)
{
    int32_t x, y, z, sine, cosine;
    if (!gameplay_boulder_body(kokiri_scene_room(), &x, &y, &z))
        return;
    kokiri_camera_sincos(demo_yaw, &sine, &cosine);
    if ((((int64_t)(x - demo_camera.x) * sine +
          (int64_t)(z - demo_camera.z) * cosine) >> 16) > FOREST_FAR)
        return;
    jo_3d_push_matrix();
    jo_3d_translate_matrix((int)x, (int)-y, (int)z);
    kokiri_submit_pdata(&boulder_mesh);
    jo_3d_pop_matrix();
}

/* Compact flat item geometry: no texture upload or new sprite slots. The
 * source hand model and nut burst particles remain presentation follow-ups. */
static POINT item_points[8];
static POLYGON item_polys[] = {
    {{0,0,0},{0,1,2,3}}, {{0,0,0},{4,5,6,7}}
};
static ATTR item_attrs[] = {
    ATTRIBUTE(Dual_Plane, SORT_CEN | UseNearClip, 0, C_RGB(20,12,4), No_Gouraud, CL32KRGB | ECdis, sprPolygon, No_Option),
    ATTRIBUTE(Dual_Plane, SORT_CEN | UseNearClip, 0, C_RGB(16,9,3), No_Gouraud, CL32KRGB | ECdis, sprPolygon, No_Option)
};
static PDATA item_mesh = {item_points,8,item_polys,2,item_attrs};
static void item_rod(const int32_t a[3], const int32_t b[3], int width)
{
    unsigned i, axis;
    for (i=0;i<8;++i) {
        const int32_t *p = (i%4 >= 2) ? b : a;
        for (axis=0;axis<3;++axis) item_points[i][axis] = p[axis] * (axis==1 ? -65536 : 65536);
        item_points[i][i<4 ? 0 : 2] += ((i%4==0 || i%4==3) ? -width : width)*65536;
    }
    kokiri_submit_pdata(&item_mesh);
}

/* Small flat flame silhouette pending the source scrolling effect import.
 * Separate attributes leave stick/projectile colours unchanged. No VRAM. */
void kokiri_flame_draw(int32_t x,int32_t y,int32_t z,unsigned tick)
{
    static POINT points[8];
    static ATTR attrs[]={
        ATTRIBUTE(Dual_Plane,SORT_CEN | UseNearClip,0,C_RGB(31,12,1),No_Gouraud,CL32KRGB | ECdis,sprPolygon,No_Option),
        ATTRIBUTE(Dual_Plane,SORT_CEN | UseNearClip,0,C_RGB(31,27,5),No_Gouraud,CL32KRGB | ECdis,sprPolygon,No_Option)
    };
    static PDATA mesh={points,8,item_polys,2,attrs};
    unsigned i;int32_t sn,cs;
    kokiri_camera_sincos(demo_yaw,&sn,&cs);
    for(i=0;i<8;++i) {
        int k=i%4,width=i<4?7:4,height=i<4?22+(tick%4):14;
        int side=k==1?-width:k==3?width:0;
        points[i][X]=x*65536+side*cs;
        points[i][Y]=-(y+(k==0?height:k==2?-5:5))*65536;
        points[i][Z]=z*65536-side*sn;
    }
    kokiri_submit_pdata(&mesh);
}

/* M2c nutsball test: the boulder's sphere scaled to the ball's radius. */
void                kokiri_nut_draw(void)
{
    int32_t x, y, z;
    unsigned i;
    if (player_items_stick()) {
        int32_t base[3], tip[3];
        if (gameplay_blade_points(base, tip)) {
            item_rod(base, tip, 1);
            if(player_items_burning())kokiri_flame_draw(tip[0],tip[1],tip[2],demo_world_clock());
        }
    }
    /* En_Arrow ARROW_SEED draws gEffSparklesDL (28-unit quad) at scale
     * 0.01*50: a 14-unit white billboard spun by gameplayFrames*4000. The 8
     * texel sparkle sprite at 1.75 units per texel is that size. A thrown
     * nut keeps the brown rod. Impact: the same sparkle, larger, fading. */
    for (i = 0; i < PLAYER_SHOTS; ++i) {
        int32_t a[3], b[3];
        unsigned item = player_items_body(i, &x, &y, &z);
        if (!item) continue;
        if (item == PLAYER_ITEM_SEED && sparkle_ready) {
            world_sparkle(x, y, z, 114688, (ANGLE)(demo_world_clock() * 4000u));
            continue;
        }
        a[0]=b[0]=x; a[2]=b[2]=z; a[1]=y-2; b[1]=y+2;
        item_rod(a,b,2);
    }
    {
        unsigned left = player_items_impact(&x, &y, &z);
        if (left && sparkle_ready)
            world_sparkle(x, y, z, 65536 + (int)left * 24576, (ANGLE)(left * 9000u));
    }
    if (!gameplay_nut_body(&x, &y, &z))
        return;
    jo_3d_push_matrix();
    jo_3d_translate_matrix((int)x, (int)-(y + GP_NUT_HEIGHT / 2), (int)z);
    slScale(GP_NUT_RADIUS * 65536 / 2 / GP_BOULDER_RADIUS,
            GP_NUT_RADIUS * 65536 / 2 / GP_BOULDER_RADIUS,
            GP_NUT_RADIUS * 65536 / 2 / GP_BOULDER_RADIUS);
    kokiri_submit_pdata(&boulder_mesh);
    jo_3d_pop_matrix();
}

/* Room of the bank actually loaded (any scene, streaming or not). */
unsigned int kokiri_bank_room(void)
{
    return forest_room < 0 ? 0 : (unsigned int)forest_room;
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
    attr.texno = (Uint16)rupee_sprite[value == 20 ? 2 : value == 5 ? 1 : 0];
    attr.atrb |= (FAIRY_COLMODE_RGB & 7) << 3;
    if (slPutSprite(pos, &attr, 0) == FALSE) ++kokiri_rejected;
}

#ifdef DOSEI_OOT_CORE
/* Decomp En_Item00 drops and floor rupees (ACTORCAT_MISC), drawn with the
** C pickup billboards until the Phase 2 draw shim. ITEM00 type = params. */
#define OOT_ACTOR_EN_ITEM00 0x0015
#define OOT_ACTOR_EN_KUSA   0x0125
static OotCoreActorView core_view[24];

static void core_drops_draw(unsigned int tick)
{
    int i, n = oot_core_view(8 /* ACTORCAT_MISC */, core_view, 24);
    for (i = 0; i < n; ++i) {
        const OotCoreActorView *a = &core_view[i];
        int dx = a->x - demo_camera.x, dz = a->z - demo_camera.z;
        if (a->id != OOT_ACTOR_EN_ITEM00 || !(a->flags & OOT_CORE_VIEW_DRAWN)) continue;
        if (dx * dx + dz * dz > FOREST_FAR * FOREST_FAR) continue;
        kokiri_drop_draw((unsigned int)(a->params & 0xFF), a->x, a->y + 14, a->z, tick);
    }
}

static void core_grass_draw(void)
{
    int i, n = oot_core_view(6 /* ACTORCAT_PROP */, core_view, 24);
    for (i = 0; i < n; ++i) {
        const OotCoreActorView *a = &core_view[i];
        int32_t dx = a->x - demo_camera.x, dz = a->z - demo_camera.z;
        FIXED pos[5];
        SPR_ATTR attr = SPR_ATTRIBUTE(0, No_Palet, No_Gouraud, ECdis,
                                      sprNoflip | FUNC_Sprite);
        if (a->id != OOT_ACTOR_EN_KUSA || (a->flags & OOT_CORE_VIEW_GRASS_CUT) ||
            !(a->flags & OOT_CORE_VIEW_DRAWN)) continue;
        if (dx * dx + dz * dz > FOREST_FAR * FOREST_FAR) continue;
        pos[0] = a->x * 65536;
        pos[1] = -(a->y + 20) * 65536;
        pos[2] = a->z * 65536;
        pos[3] = 98304;
        pos[4] = 81920;
        attr.texno = (Uint16)grass_sprite;
        attr.atrb |= (FAIRY_COLMODE_RGB & 7) << 3;
        if (slPutSprite(pos, &attr, 0) == FALSE) ++kokiri_rejected;
    }
}
#endif

void kokiri_rupees_draw(unsigned int tick)
{
    unsigned int i;
#ifdef DOSEI_OOT_CORE
    if (oot_core_owns_kokiri_props()) {
        core_drops_draw(tick);
        for (i = 0; i < KOKIRI_WONDER_COUNT; ++i) {
            const kokiri_wonder_t *w = &kokiri_wonders[i];
            if (gameplay.wonder_drop[i])
                rupee_world(w->x,w->y,w->z,w->room,gameplay.wonder_drop[i],gameplay.wonder_age[i],tick);
        }
        return;
    }
#endif
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
    for (i = 0; i < KOKIRI_WONDER_COUNT; ++i) {
        const kokiri_wonder_t *w = &kokiri_wonders[i];
        if (gameplay.wonder_drop[i])
            rupee_world(w->x,w->y,w->z,w->room,gameplay.wonder_drop[i],gameplay.wonder_age[i],tick);
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
    /* SGL SpriteEntry rejects z <= screen_distance >> display level; sit
     * just past it, ahead of every visible world polygon. */
    pos[2] = kokiri_hud_depth(1) * 65536;
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
#ifdef DOSEI_OOT_CORE
    if (oot_core_owns_kokiri_props()) { core_grass_draw(); return; }
#endif
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
    pos[0] = ((FIXED)(x) * 65536);
    pos[1] = ((FIXED)(y) * 65536);
    pos[2] = ((FIXED)(-KOKIRI_MENU_PLANE) * 65536);
    pos[3] = ((FIXED)(side) * 65536) / MENU_TEX_SIZE;
    pos[4] = ((FIXED)(side) * 65536) / MENU_TEX_SIZE;
    attr.texno = (Uint16)sprite;
    attr.atrb |= (FAIRY_COLMODE_RGB & 7) << 3;
    if (slPutSprite(pos, &attr, 0) == FALSE) ++kokiri_rejected;
}

/*
** The message panel behind cutscene text.
**
** Same screen-space trick as the pause quads: at z = -KOKIRI_MENU_PLANE one
** world unit is one screen pixel, so the rectangle is given in pixels and
** nothing in the world can sort in front of it.
**
** The VDP2 text layer draws over the sprite layer, so the text lands on top of
** this without any ordering work. A dithered fill of '#' glyphs was tried
** first, on the text layer itself; it looked like what it was.
*/
/* HUD sprites sit just past SGL's near rejection (screen distance >>
 * KOKIRI_ZDSP_LEVEL) of the LIVE projection: first person 290, owl, backdrop
 * and cutscene views differ. */
int                 kokiri_hud_depth(int above)
{
    return (int)(demo_screen_distance() >> KOKIRI_ZDSP_LEVEL) + above;
}

static FIXED        hud_sprite_depth(int above)
{
    return (FIXED)(kokiri_hud_depth(above) * 65536);
}

void                kokiri_message_box_draw(int x, int y, int width, int height)
{
    FIXED    pos[5];
    SPR_ATTR attr = SPR_ATTRIBUTE(0, No_Palet, No_Gouraud, ECdis,
                                  sprNoflip | FUNC_Sprite);

    if (!msgbox_ready)
        return;
    /* slDispSprite ignores the world matrix and takes screen-centred
    ** coordinates, exactly as the rupee HUD does, so the box is positioned in
    ** plain screen pixels. kokiri_hud_depth sorts it ahead of the world without
    ** tripping SGL's near rejection; see rupee_hud_sprite. */
    pos[0] = (x - JO_TV_WIDTH_2) * 65536;
    pos[1] = (y - JO_TV_HEIGHT_2) * 65536;
    /* SGL rejects a sprite nearer than screen_distance >> display level.
    ** Gameplay, Link's house backdrop, first person and cutscene shots each
    ** set their own distance; follow the active shot's near plane. */
    pos[2] = hud_sprite_depth(3);
    pos[3] = (width * 65536) / MSGBOX_WIDTH;
    pos[4] = (height * 65536) / MSGBOX_HEIGHT;
    attr.texno = (Uint16)msgbox_sprite;
    attr.atrb |= (FAIRY_COLMODE_RGB & 7) << 3;
    attr.atrb |= MESHon;
#ifdef DOSEI_HIRES
    /* Screen-space sprites bypass the world's vertical scale. */
    pos[1] = (y * 2 - JO_TV_HEIGHT_2) * 65536;
    pos[4] = (height * 2 * 65536) / MSGBOX_HEIGHT;
    if (slDispSpriteHV(pos, &attr, 1) == FALSE) ++kokiri_rejected;
#else
    /* Unequal X/Y scales require HV; slDispSprite uses X for both axes. */
    if (slDispSpriteHV(pos, &attr, 1) == FALSE) ++kokiri_rejected;
#endif
}

/* The prompt at the bottom of a box: OoT's triangle when another page follows,
** its square when the message ends. Same screen-space path as the panel. */
void                kokiri_message_mark_draw(int x, int y, bool last_page)
{
    FIXED    pos[5];
    SPR_ATTR attr = SPR_ATTRIBUTE(0, No_Palet, No_Gouraud, ECdis,
                                  sprNoflip | FUNC_Sprite);

    if (!msgmark_ready)
        return;
    pos[0] = (x - JO_TV_WIDTH_2) * 65536;
    pos[1] = (y - JO_TV_HEIGHT_2) * 65536;
    /* One nearer than the panel, so it lands on top of it. */
    pos[2] = hud_sprite_depth(2);
    pos[3] = pos[4] = 32768; /* Eight pixels fit the padded bottom row. */
    attr.texno = (Uint16)msgmark_sprite[last_page ? 1 : 0];
    attr.atrb |= (FAIRY_COLMODE_RGB & 7) << 3;
#ifdef DOSEI_HIRES
    pos[1] = (y * 2 - JO_TV_HEIGHT_2) * 65536;
    pos[4] = 65536;
    if (slDispSpriteHV(pos, &attr, 1) == FALSE) ++kokiri_rejected;
#else
    if (slDispSprite(pos, &attr, 0) == FALSE) ++kokiri_rejected;
#endif
}

static void         reticle_corner_draw(unsigned int sprite, int x, int y)
{
    FIXED pos[5];
    SPR_ATTR attr = SPR_ATTRIBUTE(0, No_Palet, No_Gouraud, ECdis,
                                  sprNoflip | FUNC_Sprite);
    pos[0] = (x - JO_TV_WIDTH_2) * 65536;
    pos[1] = (y - JO_TV_HEIGHT_2) * 65536;
    pos[2] = hud_sprite_depth(1);
    pos[3] = pos[4] = 65536;
    attr.texno = (Uint16)sprite;
    attr.atrb |= (FAIRY_COLMODE_RGB & 7) << 3;
#ifdef DOSEI_HIRES
    pos[1] = (y * 2 - JO_TV_HEIGHT_2) * 65536;
    pos[4] = 2 * 65536;
    if (slDispSpriteHV(pos, &attr, 1) == FALSE) ++kokiri_rejected;
#else
    if (slDispSprite(pos, &attr, 0) == FALSE) ++kokiri_rejected;
#endif
}

void                kokiri_lock_reticle_draw(int x, int y, unsigned kind)
{
    if (!reticle_ready || kind >= KOKIRI_RETICLE_COUNT)
        return;
    /* The first-person aim marker frames the exact screen centre tightly. */
    int d = kind == KOKIRI_RETICLE_AIM ? 10 : 17;
    reticle_corner_draw(reticle_sprite[kind][0], x - d, y - d);
    reticle_corner_draw(reticle_sprite[kind][1], x + d, y - d);
    reticle_corner_draw(reticle_sprite[kind][2], x + d, y + d);
    reticle_corner_draw(reticle_sprite[kind][3], x - d, y + d);
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

/*
** Upload one tile into the resident bank's VDP1 space and take a sprite slot.
**
** For meshes that are not banks and not resident: the dream's riders, whose
** textures belong to the shot rather than to the game. They land above
** resident_bytes, so the next room_load_bank() reclaims them by resetting
** vram_used, exactly as a bank swap reclaims the previous bank's tiles.
**
** KOKIRI_TILE_NONE when the texture area or the sprite table is full, which
** the caller must treat as a failed load rather than draw with a wrong slot.
*/
/* Only the textureless nightmare bank may release its transient textures. */
void kokiri_cutscene_tiles_reset(void)
{
#ifdef KOKIRI_STREAM_ROOMS
    vram_used = resident_bytes;
    sprite_next = resident_sprites;
#endif
}

unsigned int kokiri_actor_bank_generation(void) { return actor_bank_generation; }
void kokiri_actor_tiles_reset(void)
{
#ifdef KOKIRI_STREAM_ROOMS
    vram_used = actor_vram_base;
    sprite_next = actor_sprite_base;
#endif
}

unsigned int        kokiri_bank_tile_upload(const void *pixels,
                                            const void *clut,
                                            unsigned int width,
                                            unsigned int height,
                                            unsigned int *colno)
{
#ifdef KOKIRI_STREAM_ROOMS
    unsigned int   bytes = width * height / 2;   /* 4bpp */
    unsigned int   clut_bytes = 32;              /* 16 entries of 15-bit RGB */
    unsigned char *vram = (unsigned char *)JO_VDP1_VRAM + texture_base
                          + vram_used;
    jo_texture_definition *texture;
    unsigned int   slot, i;

    if (!width || !height ||
        vram_used + bytes + clut_bytes > TEXTURE_CAPACITY ||
        sprite_next >= JO_MAX_SPRITE)
        return (KOKIRI_TILE_NONE);
    {
        const unsigned char *source = (const unsigned char *)pixels;

        for (i = 0; i < bytes; ++i)
            vram[i] = source[i];
    }
    /* The CLUT goes directly behind its tile, as mesh_load() places a bank's.
    ** A 4bpp tile is meaningless without it: uploading pixels alone leaves the
    ** hardware reading whatever palette happened to be at colno, which is what
    ** made the riders come out in the wrong colours entirely. */
    {
        const unsigned char *source = (const unsigned char *)clut;

        for (i = 0; i < clut_bytes; ++i)
            vram[bytes + i] = source[i];
    }
    slot = sprite_next++;
    if (sprite_next > kokiri_sprite_peak) kokiri_sprite_peak = sprite_next;
    texture = &__jo_sprite_def[slot];
    texture->width = (unsigned short)width;
    texture->height = (unsigned short)height;
    texture->adr = (unsigned short)VRAM_UNITS((unsigned int)vram
                                              - JO_VDP1_VRAM);
    texture->size = JO_MULT_BY_32(width & 0x1f8) | height;
    __jo_sprite_pic[slot].color_mode = COL_16;
    __jo_sprite_pic[slot].data = vram;
    if (colno)
        *colno = VRAM_UNITS((unsigned int)(vram + bytes) - JO_VDP1_VRAM);
    vram_used += bytes + clut_bytes;
    return (slot);
#else
    (void)pixels; (void)clut; (void)width; (void)height; (void)colno;
    return (KOKIRI_TILE_NONE);
#endif
}

/* RGB555 tile into the same actor bank (interior occlusion masks): pixels
** are big-endian 15-bit colour, MSB set = opaque, 0x0000 = transparent. */
unsigned int        kokiri_bank_rgb_upload(const void *pixels,
                                           unsigned int width,
                                           unsigned int height)
{
#ifdef KOKIRI_STREAM_ROOMS
    unsigned int   bytes = width * height * 2;
    unsigned char *vram = (unsigned char *)JO_VDP1_VRAM + texture_base
                          + vram_used;
    const unsigned char *source = (const unsigned char *)pixels;
    jo_texture_definition *texture;
    unsigned int   slot, i;

    if (!width || !height || (width & 7) ||
        vram_used + bytes > TEXTURE_CAPACITY || sprite_next >= JO_MAX_SPRITE)
        return (KOKIRI_TILE_NONE);
    for (i = 0; i < bytes; ++i)
        vram[i] = source[i];
    slot = sprite_next++;
    if (sprite_next > kokiri_sprite_peak) kokiri_sprite_peak = sprite_next;
    texture = &__jo_sprite_def[slot];
    texture->width = (unsigned short)width;
    texture->height = (unsigned short)height;
    texture->adr = (unsigned short)VRAM_UNITS((unsigned int)vram - JO_VDP1_VRAM);
    texture->size = JO_MULT_BY_32(width & 0x1f8) | height;
    __jo_sprite_pic[slot].color_mode = COL_32K;
    __jo_sprite_pic[slot].data = vram;
    vram_used += bytes;
    return (slot);
#else
    (void)pixels; (void)width; (void)height;
    return (KOKIRI_TILE_NONE);
#endif
}

void                kokiri_submit_pdata(PDATA *pdata)
{
    submit(pdata, 8u);
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

/* Cutscene fairy and Environment_DrawRain's camera-local precipitation. */
void kokiri_cutscene_effects_draw(void)
{
    unsigned int i, count = cutscene_rain_count();
    if (cutscene_hides_scene()) return;
    if (cutscene_actor_channel_visible(8)) {
        /* Keep the scripted position, but use the same wings, world scale
         * and breathing glow as gameplay Navi instead of the old bare orb.
         * Opening cues always use her neutral colour, not a stale lock tint. */
        static uint16_t yaw;
        static int32_t last_x, last_z;
        int x = cutscene_actor_channel_x(8);
        int y = cutscene_actor_channel_y(8);
        int z = cutscene_actor_channel_z(8);
        yaw = fairy_turn(yaw, &last_x, &last_z, x, z);
        fairy_draw(x, y, z, yaw, demo_clock(), 0, fairy_glow, 0);
    }
    if (count) {
        /* Original raindrop triangle (gameplay_keep/gRaindropVtx), scaled
         * 0.4,1.2,0.4. Saturn mesh approximates the translucent source. */
        /* slPutPolygon queues table pointers for the slave SH-2; it does
         * not copy these tables before returning. Keep them alive through
         * slSynch, including the final drop submitted before this returns. */
        static POINT points[3] = {{0,-2516582,0},{-26214,-2516582,0},{-26214,2516582,0}};
        static POLYGON polygon = {{0,0,65536},{0,1,2,2}};
        static ATTR attr = ATTRIBUTE(Dual_Plane, SORT_CEN, 0,
                              C_RGB(18,31,31), No_Gouraud,
                              CL32KRGB | MESHon | ECdis, sprPolygon, UseNearClip);
        static PDATA data = {points,3,&polygon,1,&attr};
        int32_t sy, cy, sp, cp;
        uint32_t random = cutscene_frame() * 1664525u + 1013904223u;
        kokiri_camera_sincos(demo_yaw, &sy, &cy);
        kokiri_camera_sincos(demo_pitch, &sp, &cp);
        for (i = 0; i < count; ++i) {
            int x, y, z;
            random = random * 1664525u + 1013904223u;
            x = demo_camera.x + (int)(((int64_t)sy * cp * 50) >> 32) + (int)(random % 100) - 70;
            random = random * 1664525u + 1013904223u;
            y = demo_camera.y + (int)(((int64_t)sp * 50) >> 16) + (int)(random % 100) - 70;
            random = random * 1664525u + 1013904223u;
            z = demo_camera.z + (int)(((int64_t)cy * cp * 50) >> 32) + (int)(random % 100) - 70;
            slPushMatrix();
            slTranslate(x * 65536, -y * 65536, z * 65536);
            slRotY((ANGLE)demo_yaw);
            submit(&data, 0);
            slPopMatrix();
        }
    }
}

/* Four untextured, mesh-transparent ribbon segments. Persistent storage:
 * SGL consumes submitted geometry after the draw callback returns. */
static POINT trail_points[10];
static uint8_t trail_valid[5];
static POLYGON trail_faces[4];
#define TRAIL_ATTR ATTRIBUTE(Dual_Plane, SORT_CEN, 0, C_RGB(24,28,31), \
                            No_Gouraud, CL32KRGB | MESHon | ECdis, \
                            sprPolygon, UseNearClip)
static ATTR trail_attrs[4] = {TRAIL_ATTR, TRAIL_ATTR, TRAIL_ATTR, TRAIL_ATTR};
static PDATA trail_data = {trail_points, 10, trail_faces, 0, trail_attrs};

#define TRAIL_FIXED(v) ((FIXED)((int32_t)(v) * 65536))
void link_anim_trail_update(int x, int y, int z, int yaw, bool active)
{
    unsigned int i, axis, end;
    FIXED sine = slSin((ANGLE)yaw), cosine = slCos((ANGLE)yaw);
    int32_t blade[2][3];
    if (active) link_anim_blade(blade);
    for (i = 4; i > 0; --i) {
        trail_valid[i] = trail_valid[i - 1];
        for (end = 0; end < 2; ++end)
            for (axis = 0; axis < 3; ++axis)
                trail_points[i * 2 + end][axis] = trail_points[(i - 1) * 2 + end][axis];
    }
    trail_valid[0] = active;
    if (active) for (end = 0; end < 2; ++end) {
        const int32_t *local = blade[end];
        trail_points[end][0] = TRAIL_FIXED(x) + slMulFX(cosine, local[0]) + slMulFX(sine, local[2]);
        trail_points[end][1] = -TRAIL_FIXED(y) - local[1];
        trail_points[end][2] = TRAIL_FIXED(z) - slMulFX(sine, local[0]) + slMulFX(cosine, local[2]);
    }
    trail_data.nbPolygon = 0;
    for (i = 0; i < 4; ++i) if (trail_valid[i] && trail_valid[i + 1]) {
        POLYGON *face = &trail_faces[trail_data.nbPolygon++];
        face->norm[0] = 0; face->norm[1] = 0; face->norm[2] = 65536;
        face->Vertices[0] = i * 2;
        face->Vertices[1] = i * 2 + 1;
        face->Vertices[2] = i * 2 + 3;
        face->Vertices[3] = i * 2 + 2;
    }
}

void link_anim_trail_draw(void)
{
    if (trail_data.nbPolygon) kokiri_submit_pdata(&trail_data);
}

void link_anim_trail_reset(void)
{
    unsigned int i;
    for (i = 0; i < 5; ++i) trail_valid[i] = 0;
    trail_data.nbPolygon = 0;
}
