/*
** Kokiri Forest scene loader for the isolated Jo Engine / SGL viewer.
**
** The geometry tables (POINT/POLYGON/ATTR) are generated into
** generated/kokiri_scene.c by tools/build_sgl_scene.py. This file uploads the
** 4bpp texture tiles and their CLUTs into VDP1 VRAM and patches each ATTR's
** texno/colno to point at what was uploaded.
**
** VDP1 VRAM budget (jo/sega_saturn.h): the user area starts at offset 0x10000
** and runs for JO_VDP1_USER_AREA_SIZE (0x71D38 = 466232 bytes). The
** framebuffers live outside it, at JO_VDP1_FB. 313 KB of pixels plus 56 KB of
** CLUTs fits resident, so no tile streaming is needed.
*/

#include <jo/jo.h>

#include "kokiri_scene.h"
#include "kokiri_sgl.h"

/* Pixel blob is staged on the CD rather than compiled in: as a C array it
** would add ~313 KB to the ELF. */
#define KOKIRI_PIXEL_FILE   "KOKIRI.TEX"
#define KOKIRI_SUBMISSION_COUNT  2

static void         *kokiri_pixel_vram;
static void         *kokiri_clut_vram;
static unsigned int  kokiri_vram_used;
static PDATA         kokiri_submissions[KOKIRI_SUBMISSION_COUNT];

/* SGL addresses sprite character data in 8-byte units. */
#define VRAM_UNITS(bytes)   ((bytes) >> 3)

bool                kokiri_scene_load(void)
{
    unsigned char   *vram = (unsigned char *)JO_VDP1_VRAM
                            + JO_VDP1_TEXTURE_DEF_BASE_ADDRESS;
    unsigned int     need = KOKIRI_PIXEL_BYTES + sizeof(kokiri_cluts);
    char            *pixels;
    int              length;
    unsigned int     i;

    if (need > JO_VDP1_USER_AREA_SIZE)
    {
        jo_core_error("scene needs %d VDP1 bytes, user area is %d",
                      (int)need, (int)JO_VDP1_USER_AREA_SIZE);
        return (false);
    }

    /* Read straight into VDP1 VRAM. Passing a buffer to
    ** jo_fs_read_file_ptr() avoids jo_malloc()'ing a 313 KB staging copy,
    ** which would nearly exhaust the 384 KB pool this build configures. */
    kokiri_pixel_vram = vram;
    length = 0;
    pixels = jo_fs_read_file_ptr(KOKIRI_PIXEL_FILE, kokiri_pixel_vram, &length);
    if (pixels == JO_NULL)
    {
        jo_core_error("cannot read %s", KOKIRI_PIXEL_FILE);
        return (false);
    }
    if (length < KOKIRI_PIXEL_BYTES)
    {
        jo_core_error("%s is %d bytes, expected %d",
                      KOKIRI_PIXEL_FILE, length, (int)KOKIRI_PIXEL_BYTES);
        return (false);
    }

    /* CLUTs sit directly behind the pixels. jo_fs_read_file_ptr() also writes
    ** a NUL at stream[fsize], i.e. the first CLUT byte; this upload overwrites
    ** it, so the extra byte is harmless (it is inside the budget checked
    ** above, which counts pixels + CLUTs). */
    kokiri_clut_vram = vram + KOKIRI_PIXEL_BYTES;
    jo_dma_copy((void *)kokiri_cluts, kokiri_clut_vram, sizeof(kokiri_cluts));
    kokiri_vram_used = need;

    /* Publish one SGL TEXTURE entry per tile. __jo_sprite_def is the table
    ** handed to slInitSystem() in jo_core_init_vdp(), so an ATTR texno is just
    ** an index into it. Entry 0 is reserved by Jo, hence the +1 bias. */
    for (i = 0; i < KOKIRI_TILE_COUNT; ++i)
    {
        jo_texture_definition   *texture = &__jo_sprite_def[i + 1];
        unsigned int             addr = JO_VDP1_TEXTURE_DEF_BASE_ADDRESS
                                        + kokiri_tiles[i].offset;

        texture->width = kokiri_tiles[i].width;
        texture->height = kokiri_tiles[i].height;
        texture->adr = (unsigned short)VRAM_UNITS(addr);
        texture->size = JO_MULT_BY_32(kokiri_tiles[i].width & 0x1f8)
                        | kokiri_tiles[i].height;
    }

    /* Point every polygon at its uploaded tile and CLUT. The converter stored
    ** a 0-based tile index in texno; rebias it and fill in colno, which is
    ** only knowable once the CLUTs have a VRAM address. */
    for (i = 0; i < KOKIRI_POLYGON_COUNT; ++i)
    {
        ATTR            *attr = &kokiri_pdata.attbl[i];
        unsigned int     tile = attr->texno;
        unsigned int     clut = (unsigned int)kokiri_clut_vram
                                + tile * sizeof(kokiri_cluts[0]);

        attr->texno = (unsigned short)(tile + 1);
        attr->colno = (unsigned short)VRAM_UNITS(clut - JO_VDP1_VRAM);
    }

    /* SGL 3.02j's fixed work area accepts at most 1800 polygons in one input
    ** list. The scene has 2060, so preserve every face by presenting two
    ** persistent views over the shared point/polygon/attribute tables. */
    for (i = 0; i < KOKIRI_SUBMISSION_COUNT; ++i)
    {
        unsigned int first = i * ((KOKIRI_POLYGON_COUNT + 1) / 2);
        unsigned int count = KOKIRI_POLYGON_COUNT - first;

        if (count > (KOKIRI_POLYGON_COUNT + 1) / 2)
            count = (KOKIRI_POLYGON_COUNT + 1) / 2;
        kokiri_submissions[i] = kokiri_pdata;
        kokiri_submissions[i].pltbl += first;
        kokiri_submissions[i].attbl += first;
        kokiri_submissions[i].nbPolygon = count;
    }
    return (true);
}

unsigned int        kokiri_scene_vram_used(void)
{
    return (kokiri_vram_used);
}

void                kokiri_scene_draw(void)
{
    unsigned int    i;

    for (i = 0; i < KOKIRI_SUBMISSION_COUNT; ++i)
        slPutPolygon(&kokiri_submissions[i]);
}

/*
** END OF FILE
*/
