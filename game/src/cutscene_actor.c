/*
** The dream's riders. Contract and the memory argument are in the header.
*/

#include <jo/jo.h>
#include <stdint.h>
#include "cutscene_actor.h"
#include "kokiri_sgl.h"
#include "vdp1_layout.h"

/* KFR1 v2, as tools/build_link_model.py writes it:
**
**   0x00 magic 'KFR1', 0x04 version, 0x08 vertices, 0x0C faces,
**   0x10 vertex offset, 0x14 record offset, 0x18 texture offset,
**   0x1C texture bytes, 0x20 total, 0x24..0x2C centre, 0x30 radius,
**   0x34 polygon slots, 0x38 record end, 0x3C reserved.
**
** A record is >4HIIHH: four vertex ids, CLUT offset, pixel offset, the tile's
** packed size, and flags (bit 0 transparent, bit 1 cull).
*/
#define KFR1_MAGIC          0x4b465231u
#define KFR1_HEADER_BYTES   64
#define KFR1_RECORD_BYTES   20

static const char *const ACTOR_FILES[CUTSCENE_ACTOR_COUNT] = {
    "GANON.BIN", "ZELDA.BIN", "IMPA.BIN"
};

typedef struct
{
    bool     loaded;
    PDATA    pdata;
    POINT   *points;
    POLYGON *polygons;
    ATTR    *attributes;
    unsigned int sprite_base;
}               cutscene_actor_t;

static cutscene_actor_t actors[CUTSCENE_ACTOR_COUNT];
static bool             actors_ready;

static uint32_t read_be32(const unsigned char *p)
{
    return ((uint32_t)p[0] << 24) | ((uint32_t)p[1] << 16) |
           ((uint32_t)p[2] << 8) | p[3];
}

static uint16_t read_be16(const unsigned char *p)
{
    return (uint16_t)(((uint16_t)p[0] << 8) | p[1]);
}

static void free_actor(cutscene_actor_t *actor)
{
    if (actor->points)     jo_free(actor->points);
    if (actor->polygons)   jo_free(actor->polygons);
    if (actor->attributes) jo_free(actor->attributes);
    actor->points = (POINT *)0;
    actor->polygons = (POLYGON *)0;
    actor->attributes = (ATTR *)0;
    actor->loaded = false;
}

/*
** One rider: geometry into the cart, tiles into the bank's VDP1 space.
**
** Everything here is jo_malloc'd rather than static. Three riders are about
** 63 KB of tables, which does not fit below the SGL work area but is nothing
** against the 4 MB cart that src/ram_cart.c registers.
*/
static bool load_actor(cutscene_actor_t *actor, const char *file)
{
    unsigned char *data;
    const unsigned char *records;
    int            length = 0;
    unsigned int   vertices, faces, vertex_off, record_off, texture_off;
    unsigned int   texture_bytes, i;
    bool           ok = true;

    data = (unsigned char *)jo_fs_read_file(file, &length);
    if (!data)
        return (false);
    if (length < KFR1_HEADER_BYTES || read_be32(data) != KFR1_MAGIC) {
        jo_free(data);
        return (false);
    }
    vertices      = read_be32(data + 0x08);
    faces         = read_be32(data + 0x0C);
    vertex_off    = read_be32(data + 0x10);
    record_off    = read_be32(data + 0x14);
    texture_off   = read_be32(data + 0x18);
    texture_bytes = read_be32(data + 0x1C);
    if (!vertices || !faces ||
        record_off + faces * KFR1_RECORD_BYTES > (unsigned int)length ||
        texture_off + texture_bytes > (unsigned int)length) {
        jo_free(data);
        return (false);
    }

    actor->points     = (POINT *)jo_malloc(vertices * sizeof(POINT));
    actor->polygons   = (POLYGON *)jo_malloc(faces * sizeof(POLYGON));
    actor->attributes = (ATTR *)jo_malloc(faces * sizeof(ATTR));
    if (!actor->points || !actor->polygons || !actor->attributes) {
        free_actor(actor);
        jo_free(data);
        return (false);
    }

    /* The file stores the Y negation already, the way every other mesh here
    ** does, so the coordinates go straight in. */
    for (i = 0; i < vertices; ++i) {
        const unsigned char *p = data + vertex_off + i * 6;
        actor->points[i][X] = (FIXED)((int16_t)read_be16(p + 0)) << 16;
        actor->points[i][Y] = (FIXED)((int16_t)read_be16(p + 2)) << 16;
        actor->points[i][Z] = (FIXED)((int16_t)read_be16(p + 4)) << 16;
    }

    records = data + record_off;
    for (i = 0; i < faces && ok; ++i) {
        const unsigned char *r = records + i * KFR1_RECORD_BYTES;
        unsigned int pixel = read_be32(r + 12);
        unsigned int size  = read_be16(r + 16);
        unsigned int flags = read_be16(r + 18);
        unsigned int slot;
        unsigned int width = (size >> 8) * 8, height = size & 0xFF;

        actor->polygons[i].Vertices[0] = read_be16(r + 0);
        actor->polygons[i].Vertices[1] = read_be16(r + 2);
        actor->polygons[i].Vertices[2] = read_be16(r + 4);
        actor->polygons[i].Vertices[3] = read_be16(r + 6);
        /* SGL wants a normal per polygon; the models are flat shaded and lit
        ** by their own baked colours, so an up normal is enough and costs no
        ** per-face maths here. */
        actor->polygons[i].norm[X] = 0;
        actor->polygons[i].norm[Y] = toFIXED(1.0);
        actor->polygons[i].norm[Z] = 0;

        slot = kokiri_bank_tile_upload(data + texture_off + pixel,
                                       width, height);
        if (slot == KOKIRI_TILE_NONE) {
            ok = false;
            break;
        }
        actor->attributes[i].flag   = (flags & 2) ? Single_Plane : Dual_Plane;
        actor->attributes[i].sort   = SORT_CEN | UseNearClip;
        actor->attributes[i].texno  = (Uint16)slot;
        actor->attributes[i].atrb   = CL32KRGB | ECdis | SPdis;
        actor->attributes[i].colno  = 0;
        actor->attributes[i].gstb   = 0;
        actor->attributes[i].dir    = sprNoflip;
    }
    jo_free(data);
    if (!ok) {
        free_actor(actor);
        return (false);
    }

    actor->pdata.pntbl = actor->points;
    actor->pdata.nbPoint = (Sint32)vertices;
    actor->pdata.pltbl = actor->polygons;
    actor->pdata.attbl = actor->attributes;
    actor->pdata.nbPolygon = (Sint32)faces;
    actor->loaded = true;
    return (true);
}

bool cutscene_actors_load(void)
{
    unsigned int i;

    if (actors_ready)
        return (true);
    for (i = 0; i < CUTSCENE_ACTOR_COUNT; ++i) {
        if (!load_actor(&actors[i], ACTOR_FILES[i])) {
            /* All or none: a shot missing one rider but not the others would
            ** be harder to read than one missing all three. */
            cutscene_actors_free();
            return (false);
        }
    }
    actors_ready = true;
    return (true);
}

void cutscene_actors_free(void)
{
    unsigned int i;

    for (i = 0; i < CUTSCENE_ACTOR_COUNT; ++i)
        free_actor(&actors[i]);
    actors_ready = false;
}

bool cutscene_actors_ready(void)
{
    return (actors_ready);
}

void cutscene_actor_draw(cutscene_actor_id id, int32_t x, int32_t y, int32_t z,
                         uint16_t yaw)
{
    cutscene_actor_t *actor;

    if (id >= CUTSCENE_ACTOR_COUNT)
        return;
    actor = &actors[id];
    if (!actor->loaded)
        return;
    jo_3d_push_matrix();
    {
        /* Same convention as Link: the mesh carries its own Y negation, and
        ** the cue's yaw is binang where Jo's helper takes degrees. */
        jo_3d_translate_matrix(x, -y, z);
        jo_3d_rotate_matrix_y((yaw * 360) >> 16);
        kokiri_submit_pdata(&actor->pdata);
    }
    jo_3d_pop_matrix();
}

/*
** END OF FILE
*/
