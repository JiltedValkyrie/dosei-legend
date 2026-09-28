/* En_Karebaba draw (EnKarebaba_Draw) from DEKUBABA.BIN (tools/build_dekubaba.py).
** Flat-colour VDP1 polygons, no textures, no VRAM. Points are model units x
** 0.01, so a part is scaled by (its source scale / 0.01). */
#include <jo/jo.h>
#include "karebaba.h"
#include "kokiri_sgl.h"
#include "ram_cart.h"
#include "demo.h"

#define PARTS           6       /* head, stem top/middle/base, leaves, stick */
#define PART_HEAD       0
#define PART_LEAVES     4
#define PART_STICK      5
#define DRAW_FAR        1500

typedef struct {
    PDATA           pdata;
    POINT          *frames;         /* frame_count x points */
    unsigned int    frame_count;
} baba_part_t;

static baba_part_t  parts[PARTS];
static bool         ready;
static const ATTR   flat = ATTRIBUTE(Dual_Plane, SORT_CEN | UseNearClip, 0, 0,
                                     No_Gouraud, CL32KRGB | ECdis, sprPolygon, No_Option);

static unsigned int be16(const unsigned char *p) { return (unsigned int)(p[0] << 8 | p[1]); }

/* Carve the file, then POLYGON/ATTR tables after it, all in the cart. */
bool            karebaba_draw_load(void)
{
    unsigned char *cart = (unsigned char *)ram_cart_fixed(RAM_CART_DEKUBABA_OFFSET,
                                                          RAM_CART_DEKUBABA_BYTES);
    unsigned char *p, *end, *heap;
    unsigned int i, k, n;
    int length = 0;
    ready = false;
    if (!cart || !jo_fs_read_file_ptr("DEKUBABA.BIN", cart, &length) || length < 8 ||
        cart[0] != 'K' || cart[1] != 'B' || cart[2] != 'B' || cart[3] != '1' ||
        be16(cart + 6) != PARTS)
        return false;
    p = cart + 8;
    end = cart + length;
    heap = cart + ((length + 3) & ~3);
    for (i = 0; i < PARTS; ++i) {
        unsigned int points = be16(p), polys = be16(p + 2), frames = be16(p + 4);
        POLYGON *pl;
        ATTR *at;
        p += 6;
        if (p + polys * 10 + (unsigned int)frames * points * 12 > end ||
            heap + polys * (sizeof(POLYGON) + sizeof(ATTR)) >
            cart + RAM_CART_DEKUBABA_BYTES)
            return false;
        pl = (POLYGON *)heap;
        heap += polys * sizeof(POLYGON);
        at = (ATTR *)heap;
        heap += polys * sizeof(ATTR);
        for (k = 0; k < polys; ++k, p += 8) {
            pl[k].norm[0] = 0; pl[k].norm[1] = 0; pl[k].norm[2] = 65536;
            for (n = 0; n < 4; ++n)
                pl[k].Vertices[n] = (Uint16)be16(p + n * 2);
            at[k] = flat;
        }
        for (k = 0; k < polys; ++k, p += 2)
            at[k].colno = (Uint16)be16(p);
        /* POINTs are big-endian FIXED already: the SH-2 reads them in place. */
        parts[i].frames = (POINT *)p;
        parts[i].frame_count = frames;
        p += (unsigned int)frames * points * 12;
        parts[i].pdata.pntbl = parts[i].frames;
        parts[i].pdata.nbPoint = points;
        parts[i].pdata.pltbl = pl;
        parts[i].pdata.nbPolygon = polys;
        parts[i].pdata.attbl = at;
    }
    ready = true;
    return true;
}

static void     submit(unsigned int part, unsigned int frame)
{
    baba_part_t *s = &parts[part];
    s->pdata.pntbl = s->frames + (frame % s->frame_count) * s->pdata.nbPoint;
    kokiri_submit_pdata(&s->pdata);
}

static FIXED    k_of(int scale)             /* (scale / 20000) / 0.01, FIXED */
{
    return (FIXED)((int32_t)scale * 65536 / 200);
}

void            kokiri_babas_draw(void)
{
    unsigned int i, s;
    if (!ready) return;
    for (i = 0; i < karebaba_count(); ++i) {
        const karebaba_t *b = karebaba_at(i);
        int x = b->pos_q8[0] >> 8, y = b->pos_q8[1] >> 8, z = b->pos_q8[2] >> 8;
        int dx = b->home[0] - demo_camera.x, dz = b->home[2] - demo_camera.z;
        bool grow = b->action == KAREBABA_GROW || b->action == KAREBABA_REGROW;
        if (dx > DRAW_FAR || dx < -DRAW_FAR || dz > DRAW_FAR || dz < -DRAW_FAR)
            continue;
        if (b->action == KAREBABA_DROP) {
            /* Blinks for the last 40: drawn when params > 40 or odd. Actor
            ** matrix: world + yOffset 1000 x 0.03, shape.rot, scale 0.03,
            ** then Matrix_Translate(0, 0, 200). */
            if (b->timer > 40 || (b->timer & 1)) {
                jo_3d_push_matrix();
                jo_3d_translate_matrix(x, -(y + 30), z);
                slRotY((ANGLE)b->rot_y);
                slRotX((ANGLE)(0u - b->rot_x));
                slScale(k_of(b->scale), k_of(b->scale), k_of(b->scale));
                slTranslate(0, 0, 2 * 65536);
                submit(PART_STICK, 0);
                jo_3d_pop_matrix();
            }
        } else if (b->action != KAREBABA_DEAD) {
            /* Head: SkelAnime_DrawOpa under the actor matrix. */
            jo_3d_push_matrix();
            jo_3d_translate_matrix(x, -y, z);
            slRotY((ANGLE)b->rot_y);
            slRotX((ANGLE)(0u - b->rot_x));
            slScale(k_of(b->scale), k_of(b->scale), k_of(b->scale));
            submit(PART_HEAD, (unsigned int)(b->frame_q8 >> 8));
            jo_3d_pop_matrix();
            /* Stem: translate(world) * scale * rotZYX, then -2000 z per
            ** section; params x 0.0005 while growing, else 0.01. */
            jo_3d_push_matrix();
            jo_3d_translate_matrix(x, -y, z);
            {
                FIXED k = grow ? (FIXED)(b->timer * 65536 / 20) : 65536;
                slScale(k, k, k);
            }
            slRotY((ANGLE)b->rot_y);
            slRotX((ANGLE)(0u - b->rot_x));
            for (s = 0; s < (b->action == KAREBABA_DYING ? 2u : 3u); ++s) {
                slTranslate(0, 0, -20 * 65536);
                submit(1 + s, 0);
            }
            jo_3d_pop_matrix();
        }
        /* Base leaves at home (scale 0.01 except while Grow). */
        jo_3d_push_matrix();
        jo_3d_translate_matrix(b->home[0], -b->home[1], b->home[2]);
        if (b->action == KAREBABA_GROW) {
            FIXED k = (FIXED)(b->timer * 65536 / 20);
            slScale(k, k, k);
        }
        submit(PART_LEAVES, 0);
        if (b->action == KAREBABA_DYING) {
            /* RotateZYX(-0x4000, rot.y - home.rot.y, 0) + gDekuBabaStemBaseDL */
            slRotY((ANGLE)b->rot_y);
            slRotX((ANGLE)0x4000);
            submit(3, 0);
        }
        jo_3d_pop_matrix();
    }
}
