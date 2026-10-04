/*
** The dream's riders. Contract and the memory argument are in the header.
*/

#include <jo/jo.h>
#include "ram_cart.h"
#include "asset_loading.h"
#include <stdint.h>
#include "cutscene_actor.h"
#include "cutscene.h"
#include "kokiri_sgl.h"
#include "vdp1_layout.h"
#include "demo.h"
#include "actor_mesh.h"
#include "npc_pose.h"
#include "npc_sprite.h"
#include "vdp1_draw_wait.h"

/* KFR1 v2, as tools/build_link_model.py writes it:
**
**   0x00 magic 'KFR1', 0x04 version, 0x08 vertices, 0x0C faces,
**   0x10 vertex offset, 0x14 record offset, 0x18 texture offset,
**   0x1C texture bytes, 0x20 total, 0x24..0x2C centre, 0x30 radius,
**   0x34 polygon slots, 0x38 record end, 0x3C reserved.
**
** A record is >4HIIHH: four vertex ids, then the tile's PIXEL address and its
** CLUT address, its packed size, and flags (bit 0 transparent, bit 1 cull).
**
** The order is easy to get backwards and costs a whole model when you do. A
** tile is written CLUT first and pixels after, so write_model() stores
** `offset + 32` -- past the 32-byte palette -- as the first of the pair and
** the tile's own start as the second. The first is therefore the pixels and
** the second is the CLUT, not the other way round.
*/
#define KFR1_MAGIC          0x4b465231u
#define KFR1_HEADER_BYTES   64
#define KFR1_RECORD_BYTES   20

static const char *const ACTOR_FILES[CUTSCENE_ACTOR_COUNT] = {
    "GANON.SPR", "ZELDA.SPR", "IMPA.SPR", "HZELDA.SPR", "HGANON.SPR", "BRIDGE.BIN", "CHAINS.BIN", "GATEFIRE.BIN"
};

typedef struct actor_mesh
{
    bool     loaded;
    unsigned char *animation;
    unsigned char *model_data;
    unsigned char *tracking;
    unsigned char *scroll;
    unsigned int scroll_frame;
    unsigned int ticks;
    unsigned int poses;
    PDATA    pdata;
    POINT   *points;
    POLYGON *polygons;
    ATTR    *attributes;
    unsigned int sprite_base;
}               cutscene_actor_t;

static cutscene_actor_t actors[CUTSCENE_ACTOR_COUNT];
static bool             actors_ready;
static unsigned int     resident_mask, resident_generation;
static unsigned char *actor_sprites[CUTSCENE_ACTOR_BRIDGE];
static npc_sprite_inst_t actor_sprite_inst[CUTSCENE_ACTOR_BRIDGE];

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
    if (actor->tracking) jo_free(actor->tracking);
    if (actor->scroll) jo_free(actor->scroll);
    actor->scroll = 0;
    actor->tracking = 0;
    if (actor->model_data) jo_free(actor->model_data);
    actor->model_data = 0;
    if (actor->animation) jo_free(actor->animation);
    actor->animation = 0;
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
static bool __attribute__((optimize("Os"))) load_actor(cutscene_actor_t *actor, const char *file, bool animated)
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
    if (!vertices || !faces || vertices > 2500 || faces > 2000 ||
        vertex_off > (unsigned int)length || vertices * 6 > (unsigned int)length - vertex_off ||
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

    /* KFR1 keeps the model in its own space, +Y up, and does NOT bake the
    ** negation a scene bank does -- link_anim.c:240 negates Link's Y every
    ** time it poses him, for the same reason. Copying it straight through
    ** stood the riders on their heads. */
    for (i = 0; i < vertices; ++i) {
        const unsigned char *p = data + vertex_off + i * 6;
        actor->points[i][X] = (FIXED)((int16_t)read_be16(p + 0)) << 16;
        actor->points[i][Y] = -((FIXED)((int16_t)read_be16(p + 2)) << 16);
        actor->points[i][Z] = (FIXED)((int16_t)read_be16(p + 4)) << 16;
    }

    records = data + record_off;
    for (i = 0; i < faces && ok; ++i) {
        const unsigned char *r = records + i * KFR1_RECORD_BYTES;
        unsigned int pixel = read_be32(r + 8);
        unsigned int clut  = read_be32(r + 12);
        unsigned int size  = read_be16(r + 16);
        unsigned int flags = read_be16(r + 18);
        unsigned int slot = 0, colno = 0;
        unsigned int width = (size >> 8) * 8, height = size & 0xFF;

        actor->polygons[i].Vertices[0] = read_be16(r + 0);
        actor->polygons[i].Vertices[1] = read_be16(r + 2);
        actor->polygons[i].Vertices[2] = read_be16(r + 4);
        actor->polygons[i].Vertices[3] = read_be16(r + 6);
        /* Baked texture colours carry the lighting. Dual_Plane below means
         * this placeholder normal is not used for backface rejection. */
        actor->polygons[i].norm[X] = 0;
        actor->polygons[i].norm[Y] = toFIXED(1.0);
        actor->polygons[i].norm[Z] = 0;

        if (pixel > texture_bytes || width * height / 2 > texture_bytes - pixel ||
            clut > texture_bytes || 32 > texture_bytes - clut || !width || !height ||
            actor->polygons[i].Vertices[0] >= vertices ||
            actor->polygons[i].Vertices[1] >= vertices ||
            actor->polygons[i].Vertices[2] >= vertices ||
            actor->polygons[i].Vertices[3] >= vertices) {
            ok = false;
            break;
        }
        /* Vertex tracks deform every face. The constant normal above cannot
         * perform backface rejection: it culled entire riders in low-angle
         * shots. As with animated Link, draw both sides until normals are
         * reconstructed from the posed triangles. */
        actor->attributes[i].flag   = Dual_Plane;
        /* ATTRIBUTE(..., sprNoflip, ...) distributes the packed texture flag
         * into sort, not dir. Preserve that when filling ATTR by hand. */
        actor->attributes[i].sort   = SORT_CEN | UseNearClip | UseTexture | UsePalette;
        actor->attributes[i].texno  = (Uint16)slot;
        /* 4bpp colour-lookup tiles, exactly as the bank path uploads: the
        ** colour mode selects CL16Look and colno names the CLUT just placed
        ** behind the pixels. CL32KRGB here read the tile as raw RGB and the
        ** riders came out as noise. */
        actor->attributes[i].atrb   = CL16Look | ECdis | ((flags & 1) ? 0 : SPdis);
        actor->attributes[i].colno  = (Uint16)colno;
        actor->attributes[i].gstb   = 0;
        actor->attributes[i].dir    = sprNoflip & 0x3f;
    }
    if (!ok) {
        jo_free(data);
        free_actor(actor);
        return (false);
    }

    actor->model_data = data;
    actor->pdata.pntbl = actor->points;
    actor->pdata.nbPoint = (Sint32)vertices;
    actor->pdata.pltbl = actor->polygons;
    actor->pdata.attbl = actor->attributes;
    actor->pdata.nbPolygon = (Sint32)faces;
    if (animated) {
        char animation_file[13];
        unsigned int n = 0, pose_bytes;
        while (file[n] && file[n] != '.' && n < 8) { animation_file[n] = file[n]; ++n; }
        animation_file[n++] = '.'; animation_file[n++] = 'A';
        animation_file[n++] = 'N'; animation_file[n++] = 'M'; animation_file[n] = 0;
        asset_loading(animation_file);
        actor->animation = (unsigned char *)jo_fs_read_file(animation_file, &length);
        if (!actor->animation || length < 16 || read_be32(actor->animation) != 0x43564131u ||
            read_be32(actor->animation + 4) != vertices) {
            free_actor(actor); return false;
        }
        actor->poses = read_be32(actor->animation + 8);
        actor->ticks = read_be32(actor->animation + 12);
        if (!actor->poses || actor->poses > 1024 || !actor->ticks || actor->ticks > 1024) {
            free_actor(actor); return false;
        }
        pose_bytes = actor->poses * vertices * 6;
        if ((unsigned int)length != 16 + actor->ticks * 2 + pose_bytes) {
            free_actor(actor); return false;
        }
        for (n = 0; n < actor->ticks; ++n)
            if (read_be16(actor->animation + 16 + n * 2) >= actor->poses) {
                free_actor(actor); return false;
            }
    }
    actor->loaded = true;
    return (true);
}

bool cutscene_actors_load(void)
{
    unsigned int i;

    if (actors_ready)
        return (true);
    for (i = 0; i < CUTSCENE_ACTOR_COUNT; ++i) {
        asset_loading(ACTOR_FILES[i]);
        if (i < CUTSCENE_ACTOR_BRIDGE) {
            actor_sprites[i] = npc_sprite_load(ACTOR_FILES[i]);
            if (actor_sprites[i]) continue;
        } else if (load_actor(&actors[i], ACTOR_FILES[i], false)) continue;
        {
            /* All or none: a shot missing one rider but not the others would
            ** be harder to read than one missing all three. */
            cutscene_actors_free();
            return (false);
        }
    }
    if (actors[CUTSCENE_ACTOR_GATE_FIRE].pdata.nbPoint != 4 ||
        actors[CUTSCENE_ACTOR_GATE_FIRE].pdata.nbPolygon != 32) {
        cutscene_actors_free();
        return false;
    }
    actors_ready = true;
    return (true);
}

void cutscene_actors_free(void)
{
    unsigned int i;

    for (i = 0; i < CUTSCENE_ACTOR_COUNT; ++i) {
        if (i < CUTSCENE_ACTOR_BRIDGE) {
            if (actor_sprites[i]) jo_free(actor_sprites[i]);
            actor_sprites[i] = 0;
        } else free_actor(&actors[i]);
    }
    actors_ready = false;
    resident_mask = 0;
}

bool cutscene_actors_ready(void)
{
    return (actors_ready);
}

static bool upload_actor(cutscene_actor_t *actor)
{
    actor->scroll_frame = ~0u;
    const unsigned char *data = actor->model_data;
    unsigned int i, texture_off = read_be32(data + 0x18);
    const unsigned char *records = data + read_be32(data + 0x14);
    for (i = 0; i < (unsigned int)actor->pdata.nbPolygon; ++i) {
        const unsigned char *r = records + i * KFR1_RECORD_BYTES;
        unsigned int pixel = read_be32(r + 8), clut = read_be32(r + 12);
        unsigned int size = read_be16(r + 16), slot, colno = 0;
        unsigned int width = (size >> 8) * 8, height = size & 255;
        /* Reuse the converter's tiles, including their CLUTs. */
        {
            unsigned int previous;
            for (previous = 0; !actor->scroll && previous < i; ++previous) {
                const unsigned char *old = records + previous * KFR1_RECORD_BYTES;
                if (read_be32(old + 8) == pixel && read_be32(old + 12) == clut &&
                    read_be16(old + 16) == size)
                    break;
            }
            if (!actor->scroll && previous < i) {
                slot = actor->attributes[previous].texno;
                colno = actor->attributes[previous].colno;
            } else {
                slot = kokiri_bank_tile_upload(data + texture_off + pixel,
                                       data + texture_off + clut,
                                       width, height, &colno);
            }
        }
        if (slot == KOKIRI_TILE_NONE) {
            return false;
        }
        actor->attributes[i].texno = (Uint16)slot;
        actor->attributes[i].colno = (Uint16)colno;
    }
    return true;
}

/* KTS1: 32 original UV-offset frames, one 16x16 CLUT tile per face. */
bool __attribute__((optimize("Os"))) actor_mesh_load_scroll(actor_mesh_t *mesh,const char *file)
{
    int bytes;unsigned int faces,i;
    if(!mesh) return false;
    if(mesh->scroll) jo_free(mesh->scroll);
    mesh->scroll=(unsigned char *)jo_fs_read_file(file,&bytes);
    faces=mesh->scroll && bytes>=12 ? read_be32(mesh->scroll+8) : 0;
    if(!mesh->scroll || bytes<12 || read_be32(mesh->scroll)!=0x4B545331u ||
       read_be32(mesh->scroll+4)!=32 || !faces || faces>(unsigned int)mesh->pdata.nbPolygon ||
       (unsigned int)bytes!=12+faces*4+32*faces*160) {
        if(mesh->scroll) jo_free(mesh->scroll);
        mesh->scroll=0;return false;
    }
    for(i=0;i<faces;++i) {
        unsigned int face=read_be32(mesh->scroll+12+i*4);
        unsigned int records=read_be32(mesh->model_data+0x14);
        if(face>=(unsigned int)mesh->pdata.nbPolygon ||
           read_be16(mesh->model_data+records+face*KFR1_RECORD_BYTES+16)!=0x0210) {
            jo_free(mesh->scroll);mesh->scroll=0;return false;
        }
    }
    mesh->scroll_frame=~0u;return true;
}
void actor_mesh_scroll(actor_mesh_t *mesh,unsigned int frame)
{
    unsigned int i,k,faces;
    const unsigned char *data;
    if(!mesh || !mesh->scroll || mesh->scroll_frame==(frame&31)) return;
    if(!vdp1_wait_for_draw_end()) return; /* retain old frame until safe */
    frame &=31;
    faces=read_be32(mesh->scroll+8);
    data=mesh->scroll+12+faces*4+frame*faces*160;
    for(i=0;i<faces;++i,data+=160) {
        unsigned int face=read_be32(mesh->scroll+12+i*4);
        volatile uint16_t *palette_out=(volatile uint16_t *)((unsigned char *)JO_VDP1_VRAM+mesh->attributes[face].colno*8);
        volatile uint16_t *pixels=(volatile uint16_t *)((unsigned char *)JO_VDP1_VRAM+
            __jo_sprite_def[mesh->attributes[face].texno].adr*8);
        for(k=0;k<16;++k) palette_out[k]=read_be16(data+k*2);
        for(k=0;k<64;++k) pixels[k]=read_be16(data+32+k*2);
    }
    mesh->scroll_frame=frame;
}

actor_mesh_t * __attribute__((optimize("Os"))) actor_mesh_load(const char *file)
{
    char name[] = "NPC00.TRK";
    int bytes;
    unsigned int flags, i;
    actor_mesh_t *mesh = jo_malloc(sizeof(*mesh));
    if (!mesh) return 0;
    *mesh = (actor_mesh_t){0};
    if (!load_actor(mesh, file, true)) { jo_free(mesh); return 0; }
    name[3] = file[3]; name[4] = file[4];
    mesh->tracking = (unsigned char *)jo_fs_read_file(name, &bytes);
    flags = ((unsigned int)mesh->pdata.nbPoint + 3) & ~3u;
    if (!mesh->tracking || bytes < 16 || read_be32(mesh->tracking) != 0x4e545232u ||
        read_be32(mesh->tracking + 4) != (unsigned int)mesh->pdata.nbPoint ||
        read_be32(mesh->tracking + 8) != mesh->ticks ||
        (read_be32(mesh->tracking + 12) != 576 && read_be32(mesh->tracking + 12) != 768) ||
        (unsigned int)bytes != 16 + flags + mesh->ticks * 54) {
        actor_mesh_free(mesh); return 0;
    }
    for (i = 0; i < (unsigned int)mesh->pdata.nbPoint; ++i)
        if (mesh->tracking[16+i] > 3) { actor_mesh_free(mesh); return 0; }
    return mesh;
}

/*
** Swap the clip on a mesh that is already loaded and uploaded.
**
** Saria's greeting poses are the same model as her idle -- same skeleton, same
** vertices, same 78 texture tiles -- and differ only in which animation plays.
** Loading them as separate meshes cost three more uploads of identical tiles,
** which is what filled the VDP1 bank and starved the world props at 99% VRAM.
** Only the .ANM and .TRK change here; points, polygons, attributes and the
** uploaded tiles are left exactly as they are, so nothing re-uploads.
**
** The vertex count is what makes this safe: a clip built for a different
** skeleton fails the CVA1/NTR2 checks and the old clip is kept, rather than
** posing the mesh with someone else's motion.
*/
bool __attribute__((optimize("Os"))) actor_mesh_swap_clip(actor_mesh_t *mesh, const char *stem)
{
    char name[13];
    const unsigned char *staged;
    unsigned char *animation = 0, *tracking = 0;
    unsigned int vertices, poses, ticks, flags, n, stem_len = 0;
    int length = 0, anim_length;

    if (!mesh || !mesh->loaded || !mesh->animation) return false;
    vertices = (unsigned int)mesh->pdata.nbPoint;
    while (stem[stem_len] && stem_len < 8) { name[stem_len] = stem[stem_len]; ++stem_len; }
    name[stem_len] = '.'; name[stem_len+1] = 'A';
    name[stem_len+2] = 'N'; name[stem_len+3] = 'M'; name[stem_len+4] = 0;
    asset_loading(name);
    /* Stage in the cart scratch: a clip can be 224 KB, and holding it next
    ** to the old one needed a contiguous block the heap no longer had. */
    staged = (const unsigned char *)ram_cart_load_scratch(name, &length);
    if (!staged || length < 16 || read_be32(staged) != 0x43564131u ||
        read_be32(staged + 4) != vertices)
        goto reject;
    poses = read_be32(staged + 8);
    ticks = read_be32(staged + 12);
    if (!poses || poses > 1024 || !ticks || ticks > 1024 ||
        (unsigned int)length != 16 + ticks * 2 + poses * vertices * 6)
        goto reject;
    for (n = 0; n < ticks; ++n)
        if (read_be16(staged + 16 + n * 2) >= poses) goto reject;
    anim_length = length;

    name[stem_len+1] = 'T'; name[stem_len+2] = 'R'; name[stem_len+3] = 'K';
    asset_loading(name);
    tracking = (unsigned char *)jo_fs_read_file(name, &length);
    flags = (vertices + 3) & ~3u;
    if (!tracking || length < 16 || read_be32(tracking) != 0x4e545232u ||
        read_be32(tracking + 4) != vertices || read_be32(tracking + 8) != ticks ||
        (read_be32(tracking + 12) != 576 && read_be32(tracking + 12) != 768) ||
        (unsigned int)length != 16 + flags + ticks * 54)
        goto reject;
    for (n = 0; n < vertices; ++n)
        if (tracking[16 + n] > 3) goto reject;

    jo_free(mesh->animation);
    mesh->animation = 0;
    animation = (unsigned char *)jo_malloc(anim_length);
    if (!animation) {
        /* Old clip is gone: drop the mesh's motion rather than pose garbage. */
        jo_free(tracking);
        jo_free(mesh->tracking);
        mesh->tracking = 0;
        mesh->loaded = false;
        asset_loading_done();
        return false;
    }
    for (n = 0; n < (unsigned int)anim_length; n += 4)
        *(unsigned int *)(animation + n) = *(const unsigned int *)(staged + n);
    jo_free(mesh->tracking);
    mesh->animation = animation;
    mesh->tracking = tracking;
    mesh->poses = poses;
    mesh->ticks = ticks;
    asset_loading_done();
    return true;

reject:
    if (animation) jo_free(animation);
    if (tracking) jo_free(tracking);
    asset_loading_done();
    return false;
}

/* Animated prop: original baked clip, no NPC head/torso tracking. */
actor_mesh_t *actor_mesh_load_animated(const char *file)
{
    actor_mesh_t *mesh = jo_malloc(sizeof(*mesh));
    if (!mesh) return 0;
    *mesh = (actor_mesh_t){0};
    if (!load_actor(mesh, file, true)) { jo_free(mesh); return 0; }
    return mesh;
}

/* A static KFR1 prop (no clip, no tracking): tools/build_shop_props.py. */
actor_mesh_t *actor_mesh_load_static(const char *file)
{
    actor_mesh_t *mesh = jo_malloc(sizeof(*mesh));
    if (!mesh) return 0;
    *mesh = (actor_mesh_t){0};
    if (!load_actor(mesh, file, false)) { jo_free(mesh); return 0; }
    return mesh;
}

void actor_mesh_draw_static(actor_mesh_t *mesh, int32_t x, int32_t y, int32_t z,
                            uint16_t yaw)
{
    if (!mesh || !mesh->loaded) return;
    jo_3d_push_matrix();
    jo_3d_translate_matrix(x, -y, z);
    slRotY((ANGLE)yaw);
    kokiri_submit_pdata(&mesh->pdata);
    jo_3d_pop_matrix();
}

void actor_mesh_draw_transform(actor_mesh_t *mesh,int32_t x,int32_t y,int32_t z,
    uint16_t yaw,uint16_t pitch,uint16_t roll,int32_t scale)
{
    if(!mesh || !mesh->loaded)return;
    jo_3d_push_matrix();jo_3d_translate_matrix(x,-y,z);
    slRotY((ANGLE)yaw);slRotZ((ANGLE)roll);slRotX((ANGLE)pitch);
    slScale(scale,scale,scale);kokiri_submit_pdata(&mesh->pdata);jo_3d_pop_matrix();
}

/* Y is flipped between OoT and SGL space, which mirrors rotations about X
** and Z (F*Rx(a)*F = Rx(-a)); Y rotations keep their sign, as in
** actor_mesh_draw_static. */
void actor_mesh_draw_euler(actor_mesh_t *mesh, int32_t x, int32_t y, int32_t z,
    int16_t yaw, int16_t pitch, int16_t roll, int32_t sx, int32_t sy, int32_t sz)
{
    if (!mesh || !mesh->loaded) return;
    jo_3d_push_matrix();
    jo_3d_translate_matrix(x, -y, z);
    slRotY((ANGLE)yaw);
    slRotX((ANGLE)(int16_t)-pitch);
    slRotZ((ANGLE)(int16_t)-roll);
    slScale(sx, sy, sz);
    kokiri_submit_pdata(&mesh->pdata);
    jo_3d_pop_matrix();
}

bool actor_mesh_draw_skinned(actor_mesh_t *mesh, const unsigned char *skin,
                             const int32_t *mats, unsigned int count)
{
    unsigned int i, n;
    const unsigned char *slot, *local;
    if (!mesh || !mesh->loaded || !skin || !mats || read_be32(skin) != 0x534B4E31u) return false;
    n = read_be32(skin + 4);
    if (n != (unsigned int)mesh->pdata.nbPoint || read_be32(skin + 8) > count) return false;
    slot = skin + 12;
    local = slot + ((n + 1) & ~1u);
    for (i = 0; i < n; ++i, local += 6) {
        const int32_t *m = mats + slot[i] * 12;
        int32_t lx = (int16_t)read_be16(local), ly = (int16_t)read_be16(local + 2),
                lz = (int16_t)read_be16(local + 4);
        mesh->points[i][X] = m[0] * lx + m[1] * ly + m[2] * lz + m[9];
        mesh->points[i][Y] = -(m[3] * lx + m[4] * ly + m[5] * lz + m[10]);
        mesh->points[i][Z] = m[6] * lx + m[7] * ly + m[8] * lz + m[11];
    }
    jo_3d_push_matrix();
    kokiri_submit_pdata(&mesh->pdata);
    jo_3d_pop_matrix();
    return true;
}

void actor_mesh_free(actor_mesh_t *mesh)
{
    if (mesh) { free_actor(mesh); jo_free(mesh); }
}

bool actor_mesh_upload(actor_mesh_t *mesh)
{
    return mesh && upload_actor(mesh);
}

void actor_mesh_draw(actor_mesh_t *mesh, unsigned int frame,
                     int32_t x, int32_t y, int32_t z, uint16_t yaw,
                     const int16_t head_rot[9], const int16_t torso_rot[9],
                     int32_t focus[3])
{
    unsigned int i, pose;
    int16_t basis[9], origin[3], torso_basis[9], torso_origin[3];
    int32_t pivot;
    const unsigned char *p;
    if (!mesh || !mesh->loaded) return;
    frame %= mesh->ticks;
    if (mesh->tracking) {
    p = mesh->tracking + 16 + (((unsigned int)mesh->pdata.nbPoint + 3) & ~3u) + frame * 54;
    for (i = 0; i < 9; ++i) {
        basis[i] = (int16_t)read_be16(p + i*2);
        torso_basis[i] = (int16_t)read_be16(p + 30 + i*2);
    }
    for (i = 0; i < 3; ++i) {
        origin[i] = (int16_t)read_be16(p + 18 + i*2);
        focus[i] = (int16_t)read_be16(p + 24 + i*2);
        torso_origin[i] = (int16_t)read_be16(p + 48 + i*2);
    }
    pivot = read_be32(mesh->tracking + 12);
    /* Head override first (inner limb), then the torso subtree's. */
    if (head_rot) npc_limb_transform(focus, basis, origin, pivot, head_rot);
    if (torso_rot) npc_limb_transform(focus, torso_basis, torso_origin, 0, torso_rot);
    }
    pose = read_be16(mesh->animation + 16 + frame * 2);
    p = mesh->animation + 16 + mesh->ticks * 2 + pose * mesh->pdata.nbPoint * 6;
    for (i = 0; i < (unsigned int)mesh->pdata.nbPoint; ++i, p += 6) {
        int32_t v[3] = { (int16_t)read_be16(p), (int16_t)read_be16(p+2), (int16_t)read_be16(p+4) };
        if (head_rot && mesh->tracking && (mesh->tracking[16+i] & 1))
            npc_limb_transform(v, basis, origin, pivot, head_rot);
        if (torso_rot && (mesh->tracking[16+i] & 2))
            npc_limb_transform(v, torso_basis, torso_origin, 0, torso_rot);
        mesh->points[i][X] = v[0] * 1024;
        mesh->points[i][Y] = -v[1] * 1024;
        mesh->points[i][Z] = v[2] * 1024;
    }
    jo_3d_push_matrix();
    jo_3d_translate_matrix(x, -y, z);
    slRotY((ANGLE)yaw);
    kokiri_submit_pdata(&mesh->pdata);
    jo_3d_pop_matrix();
}

/* Sprite cels and static bridge props stay resident for this room generation. */
void cutscene_actors_prepare(void)
{
    unsigned int i, generation = kokiri_actor_bank_generation();
    if (!actors_ready || cutscene_hides_scene()) return;
    if (resident_mask && resident_generation == generation) return;
    kokiri_cutscene_tiles_reset();
    resident_mask = 0;
    for (i = 0; i < CUTSCENE_ACTOR_COUNT; ++i) {
        bool ok = i < CUTSCENE_ACTOR_BRIDGE ?
            npc_sprite_upload(actor_sprites[i], &actor_sprite_inst[i]) : upload_actor(&actors[i]);
        if (!ok) {
            jo_core_error("Cutscene texture bank full: %s", ACTOR_FILES[i]);
            return;
        }
    }
    resident_generation = generation;
    resident_mask = (1u << CUTSCENE_ACTOR_COUNT) - 1u;
}

void cutscene_actor_draw(cutscene_actor_id id, int32_t x, int32_t y, int32_t z,
                         uint16_t yaw)
{
    cutscene_actor_t *actor;

    if (id >= CUTSCENE_ACTOR_COUNT)
        return;
    if (!(resident_mask & (1u << id))) return;
    if (id < CUTSCENE_ACTOR_BRIDGE) {
        unsigned char *sheet = actor_sprites[id];
        unsigned int frame = cutscene_frame(), ticks = read_be16(sheet + 12);
        if (frame >= ticks) frame = ticks - 1;
        npc_sprite_draw(sheet, &actor_sprite_inst[id], frame, x, y, z, yaw);
        return;
    }
    actor = &actors[id];
    if (!actor->loaded)
        return;
    if (!(resident_mask & (1u << id))) return;
    jo_3d_push_matrix();
    {
        /* Same convention as Link: the mesh carries its own Y negation, and
        ** the cue's yaw is binang where Jo's helper takes degrees. */
        jo_3d_translate_matrix(x, -y, z);
        slRotY((ANGLE)yaw);
        if (id == CUTSCENE_ACTOR_BRIDGE)
            slRotX((ANGLE)(0u - cutscene_bridge_angle()));
        if (id == CUTSCENE_ACTOR_CHAINS) {
            int bridge = cutscene_bridge_angle();
            int steps = bridge < -10200 ? 0 : (bridge + 10200) / 120 + 1;
            int chain = -4064 + steps * 48;
            slRotX((ANGLE)(0u - (chain < 0 ? chain : 0)));
        }
        kokiri_submit_pdata(&actor->pdata);
    }
    jo_3d_pop_matrix();
}

/*
** END OF FILE
*/

/* Original BgSpot00Hanebasi_DrawTorches: both fire bases are fixed in world
 * space, scale .008, billboard yaw camera+0x8000. Only nightmare calls this.
 * Prebaked phases select the two scrolling source textures at 20 Hz. */
void cutscene_gate_fire_draw(void)
{
    cutscene_actor_t *fire = &actors[CUTSCENE_ACTOR_GATE_FIRE];
    unsigned int i;
    if (!fire->loaded || !(resident_mask & (1u << CUTSCENE_ACTOR_GATE_FIRE))) return;
    for (i = 0; i < 2; ++i) {
        unsigned int phase = (((cutscene_frame() + i) * 5u) & 127u) / 4u;
        static PDATA frames[2];
        PDATA *frame = &frames[i];
        *frame = fire->pdata;
        frame->pltbl = fire->polygons + phase;
        frame->attbl = fire->attributes + phase;
        frame->nbPolygon = 1;
        jo_3d_push_matrix();
        jo_3d_translate_matrix(i ? -260 : 260, -128, 690);
        slRotY((ANGLE)(demo_yaw + 0x8000u));
        kokiri_submit_pdata(frame);
        jo_3d_pop_matrix();
    }
}
