/*
** Runtime skinning for child Link.
**
** Why pose at runtime instead of baking frames: one POINT table is 12 bytes a
** vertex, so Link's 329 vertices cost ~3.9 KB. The link-time boundary check
** leaves about 9.4 KB of .bss below SGL's work area, so two baked frames would
** exhaust it. Baked per-frame limb *rotations* are const instead, and there is
** exactly one posed POINT table, rewritten in place when the frame changes.
**
** The per-frame clip tables (~57 KB) are read from LINKANIM.BIN into cart RAM
** by link_anim_load(); only host builds link them as .rodata. Rotations are
** kept at full 16-bit binang precision.
**
** Cost control: the skeleton is walked once per frame to build 21 limb
** matrices (21 rotations), then each vertex is one matrix-vector product.
** That is far cheaper than the per-vertex Euler evaluation a naive version
** would do, and it is only redone when the clip frame actually advances.
**
** Conventions this file must preserve, all established by the existing
** pipeline (see build_sgl_scene.py and kokiri_sgl.c):
**   - POINT Y is negated. The Y flip is baked at the rendering boundary so the
**     modelview matrix stays a pure translation; the skinner applies the same
**     negation rather than reintroducing a runtime reflection.
**   - POLYGON normals stay at bind-pose values, so generated animated Link
**     uses Dual_Plane. Single_Plane uses those stale normals for backface
**     rejection and opens holes as limbs rotate. No runtime lighting uses them.
**   - The model is grounded and centred at build time; the same integer shift
**     is reapplied here so a posed frame lands where the bind pose did.
*/

#include <jo/jo.h>
#include <stdint.h>

#include "link_clips.h"
#include "link_scene.h"
#include "link_anim_state.h"

/* 3x3 rotation plus translation, in the model's own units. Rotations are
** FIXED (16.16); origins stay integer model units until the final scale. */
typedef struct
{
    FIXED   m[3][3];
    int32_t origin[3];
}           limb_matrix_t;

static limb_matrix_t limb_matrices[LINK_LIMB_COUNT];

#ifdef LINK_FRAMES_FROM_DISC
/* Per-frame tables live in cart RAM, read from LINKANIM.BIN at boot. Same
** indexing as the host arrays in link_clips.c. Disc data is big-endian, the
** SH-2's own order, so the file body is used in place. */
/* Not static: link_anim_state.c reads roots for the hang's root motion. */
const int16_t (*link_root)[3];
const int16_t (*link_rotations)[LINK_LIMB_COUNT * 3];

static uint32_t read_be32(const unsigned char *p)
{
    return ((uint32_t)p[0] << 24) | ((uint32_t)p[1] << 16) |
           ((uint32_t)p[2] << 8) | p[3];
}

bool            link_anim_load(void)
{
    static const unsigned int roots = LINK_FRAME_COUNT * 3;
    static const unsigned int rotations = LINK_FRAME_COUNT * LINK_LIMB_COUNT * 3;
    unsigned char   *data;
    uint32_t        digest = 0x811C9DC5u;   /* FNV-1a, frames_digest() */
    unsigned int    i;
    int             length = 0;

    if (link_root)
        return (true);
    data = (unsigned char *)jo_fs_read_file("LINKANIM.BIN", &length);
    if (!data)
        return (false);
    if (length != (int)(16 + (roots + rotations) * 2) ||
        data[0] != 'L' || data[1] != 'A' || data[2] != 'N' || data[3] != '1' ||
        read_be32(data + 4) != LINK_FRAME_COUNT ||
        read_be32(data + 8) != LINK_LIMB_COUNT ||
        read_be32(data + 12) != LINK_FRAMES_DIGEST) {
        jo_free(data);
        return (false);
    }
    /* Bind the file to THIS executable: digest this ELF's own clip layout,
    ** then every body byte in order, and compare with the digest the
    ** generator compiled in. A same-shape file from another build fails. */
    for (i = 0; i < LINK_CLIP_COUNT; ++i) {
        const uint8_t layout[4] = {
            (uint8_t)(link_clips[i].first >> 8), (uint8_t)link_clips[i].first,
            (uint8_t)(link_clips[i].count >> 8), (uint8_t)link_clips[i].count };
        unsigned int k;
        for (k = 0; k < 4; ++k)
            digest = (digest ^ layout[k]) * 0x01000193u;
    }
    for (i = 16; i < (unsigned int)length; ++i)
        digest = (digest ^ data[i]) * 0x01000193u;
    if (digest != LINK_FRAMES_DIGEST) {
        jo_free(data);
        return (false);
    }
    link_root = (const int16_t (*)[3])(data + 16);
    link_rotations = (const int16_t (*)[LINK_LIMB_COUNT * 3])(data + 16 + roots * 2);
    return (true);
}
#else
bool            link_anim_load(void)
{
    return (true);
}
#endif

/* The frame currently resident in link_points, so an unchanged frame costs
** nothing. -1 forces the first pose. */
static int      posed_frame = -1;
static unsigned int posed_fraction;

/* SGL's fixed multiply uses the SH-2 32x32->64 instruction. Keep it here.
** The measured ~97 ms regression was the runtime toFIXED conversions below,
** not evidence that every int64 multiply calls libgcc: the forest depth loop
** compiles its int64 products to native dmuls.l as well. Inspect target code. */
#define FIXED_MUL(a, b)  slMulFX((a), (b))
/* SGL's toFIXED macro multiplies by 65536.0: runtime integers therefore
 * become SOFTWARE DOUBLE calls on SH-2. These coordinates are integers in
 * signed 16-bit range; multiplication is exact and defined for negative
 * values too (unlike a signed left shift). Constants still use toFIXED. */
#define INTEGER_FIXED(a) ((FIXED)((int32_t)(a) * 65536))

static void     matrix_multiply(FIXED out[3][3], const FIXED a[3][3],
                                const FIXED b[3][3])
{
    unsigned int    row;
    unsigned int    col;

    for (row = 0; row < 3; ++row)
        for (col = 0; col < 3; ++col)
            out[row][col] = FIXED_MUL(a[row][0], b[0][col])
                          + FIXED_MUL(a[row][1], b[1][col])
                          + FIXED_MUL(a[row][2], b[2][col]);
}

/*
** Binang Euler triple -> matrix, composed Z then Y then X.
**
** This is OoT's own order (z_player_lib.c poses limbs ZYX), and it has to match
** build_link_model.py:rotation_matrix() exactly, or the baked bind pose and the
** runtime pose disagree and Link's limbs twist.
*/
static void     rotation_matrix(FIXED out[3][3], const int16_t rot[3])
{
    ANGLE           ax = (ANGLE)(uint16_t)rot[0];
    ANGLE           ay = (ANGLE)(uint16_t)rot[1];
    ANGLE           az = (ANGLE)(uint16_t)rot[2];
    FIXED           sx = slSin(ax);
    FIXED           cx = slCos(ax);
    FIXED           sy = slSin(ay);
    FIXED           cy = slCos(ay);
    FIXED           sz = slSin(az);
    FIXED           cz = slCos(az);
    FIXED           zy[3][3];
    FIXED           rx[3][3];
    FIXED           ry[3][3];
    FIXED           rz[3][3];

    rx[0][0] = toFIXED(1); rx[0][1] = 0;   rx[0][2] = 0;
    rx[1][0] = 0;          rx[1][1] = cx;  rx[1][2] = -sx;
    rx[2][0] = 0;          rx[2][1] = sx;  rx[2][2] = cx;

    ry[0][0] = cy;         ry[0][1] = 0;   ry[0][2] = sy;
    ry[1][0] = 0;          ry[1][1] = toFIXED(1); ry[1][2] = 0;
    ry[2][0] = -sy;        ry[2][1] = 0;   ry[2][2] = cy;

    rz[0][0] = cz;         rz[0][1] = -sz; rz[0][2] = 0;
    rz[1][0] = sz;         rz[1][1] = cz;  rz[1][2] = 0;
    rz[2][0] = 0;          rz[2][1] = 0;   rz[2][2] = toFIXED(1);

    matrix_multiply(zy, rz, ry);
    matrix_multiply(out, zy, rx);
}

/*
** Compose every limb's matrix for one frame.
**
** Mirrors build_link_model.py:walk_skeleton() and SkelAnime's hierarchical
** draw: each limb translates by its jointPos expressed in the parent's frame,
** then rotates. Limb 0 uses the animation's root translation instead of its
** own jointPos. The recursion there is rewritten as an explicit stack walk;
** the sibling/child links are a tree of 21 nodes, so the stack is tiny and
** bounded, and this avoids recursion on the SH-2's small stack.
*/
static void     pose_skeleton(const int16_t *root, const int16_t *rotations)
{
    /* Each entry is a limb whose parent matrix is already composed. */
    uint8_t         pending[LINK_LIMB_COUNT];
    uint8_t         parent_of[LINK_LIMB_COUNT];
    unsigned int    count = 0;
    unsigned int    at = 0;
    unsigned int    i;

    for (i = 0; i < LINK_LIMB_COUNT; ++i)
        parent_of[i] = 0xFF;
    pending[count++] = 0;

    while (at < count)
    {
        uint8_t         index = pending[at++];
        const link_limb_t *limb = &link_limbs[index];
        limb_matrix_t   *out = &limb_matrices[index];
        uint8_t         parent = parent_of[index];
        int32_t         offset[3];
        unsigned int    axis;
        uint8_t         child;
        uint8_t         sibling;

        if (index == 0)
        {
            offset[0] = root[0];
            offset[1] = root[1];
            offset[2] = root[2];
        }
        else
        {
            offset[0] = limb->pos.x;
            offset[1] = limb->pos.y;
            offset[2] = limb->pos.z;
        }

        if (parent == 0xFF)
        {
            /* Limb 0: the animation's root translation, no parent rotation. */
            FIXED   local[3][3];

            for (axis = 0; axis < 3; ++axis)
                out->origin[axis] = offset[axis];
            rotation_matrix(local, &rotations[index * 3]);
            for (axis = 0; axis < 3; ++axis)
            {
                out->m[axis][0] = local[axis][0];
                out->m[axis][1] = local[axis][1];
                out->m[axis][2] = local[axis][2];
            }
        }
        else
        {
            const limb_matrix_t *up = &limb_matrices[parent];
            FIXED           local[3][3];

            /* Place the joint in the parent's frame, then rotate within it. */
            for (axis = 0; axis < 3; ++axis)
                out->origin[axis] = up->origin[axis]
                    + (FIXED_MUL(up->m[axis][0], INTEGER_FIXED(offset[0]))
                     + FIXED_MUL(up->m[axis][1], INTEGER_FIXED(offset[1]))
                     + FIXED_MUL(up->m[axis][2], INTEGER_FIXED(offset[2]))) / 65536;
            rotation_matrix(local, &rotations[index * 3]);
            matrix_multiply(out->m, up->m, local);
        }

        /* Queue children and siblings with their parent recorded. A sibling
        ** shares this limb's parent; a child's parent is this limb. */
        child = limb->child;
        if (child != 0xFF && child < LINK_LIMB_COUNT)
        {
            parent_of[child] = index;
            pending[count++] = child;
        }
        sibling = limb->sibling;
        if (sibling != 0xFF && sibling < LINK_LIMB_COUNT && count < LINK_LIMB_COUNT)
        {
            parent_of[sibling] = parent;
            pending[count++] = sibling;
        }
    }
}

/*
** Transform every skinned vertex by its owning limb and write link_points.
**
** The build-time chain was: pose -> scale to world units -> ground/centre.
** The same order is reproduced here, in integer model units until the scale,
** so a posed frame sits exactly where the baked bind pose did. Y is negated
** last, matching the baked POINT convention.
*/
static void     skin_vertices(void)
{
    unsigned int    i;

    for (i = 0; i < LINK_SKIN_VERTICES; ++i)
    {
        const limb_matrix_t *m = &limb_matrices[link_vertex_limb[i]];
        const link_vec3_t   *local = &link_vertex_local[i];
        int32_t             posed[3];
        unsigned int        axis;

        for (axis = 0; axis < 3; ++axis)
            posed[axis] = m->origin[axis]
                + (FIXED_MUL(m->m[axis][0], INTEGER_FIXED(local->x))
                 + FIXED_MUL(m->m[axis][1], INTEGER_FIXED(local->y))
                 + FIXED_MUL(m->m[axis][2], INTEGER_FIXED(local->z))) / 65536;

        /* Integer model * Q16 scale is ALREADY fixed world position. Keep its
         * fraction: shifting down and back up collapses small face triangles
         * and makes silhouettes jump by a whole world unit while animating. */
        link_points[i][X] = posed[0] * LINK_ANIM_SCALE_Q16
                           + INTEGER_FIXED(LINK_ANIM_SHIFT_X);
        link_points[i][Y] = -(posed[1] * LINK_ANIM_SCALE_Q16
                            + INTEGER_FIXED(LINK_ANIM_SHIFT_Y));
        link_points[i][Z] = posed[2] * LINK_ANIM_SCALE_Q16
                           + INTEGER_FIXED(LINK_ANIM_SHIFT_Z);
    }
}

void            link_anim_pose(unsigned int clip, unsigned int frame,
                               unsigned int fraction)
{
    const link_clip_t   *entry;
    unsigned int        absolute;
    unsigned int        next, i;
    int16_t             root[3], rotations[LINK_LIMB_COUNT * 3];

    if (clip >= LINK_CLIP_COUNT)
        clip = LINK_CLIP_IDLE;
#ifdef LINK_FRAMES_FROM_DISC
    if (!link_root)
        return;                     /* link_anim_load failed; boot refuses */
#endif
    entry = &link_clips[clip];
    if (entry->count == 0)
        return;
    absolute = entry->first + (frame % entry->count);
    /* No quantisation here.
    **
    ** An earlier revision masked the low bits of `fraction` hoping to hit this
    ** cache more often. It saved nothing: link_anim_state.c advances
    ** phase_ninths by 6 per step, i.e. two thirds of a source frame, so
    ** fraction only ever takes 0, 85 or 170. Every step already lands on a
    ** different (frame, fraction) pair, and a 32-step mask merges none of
    ** them -- measured at 30 misses over 30 updates both with and without it.
    **
    ** The cost is real but it is the CADENCE, not the phase resolution. Making
    ** this cache hit would mean re-posing less often than the animation
    ** actually advances, which is a visible change, not an optimisation.
    */
    fraction &= 255;
    if ((int)absolute == posed_frame && fraction == posed_fraction)
        return;                     /* already resident; skinning is the cost */
    posed_frame = (int)absolute;
    posed_fraction = fraction;
    next = absolute + 1;
    if (next >= entry->first + entry->count)
        next = (clip == LINK_CLIP_FALL || clip == LINK_CLIP_LANDING ||
                clip == LINK_CLIP_ROLL || clip == LINK_CLIP_JUMP ||
                clip == LINK_CLIP_RUN_JUMP || clip == LINK_CLIP_RUN_JUMP_END ||
                clip == LINK_CLIP_STEP100 || clip == LINK_CLIP_STEP150 ||
                clip == LINK_CLIP_JUMP250 || clip == LINK_CLIP_HANG_FALL ||
                clip == LINK_CLIP_CLIMB_HOLD || clip == LINK_CLIP_FALL_UP ||
                clip == LINK_CLIP_CLIMB_UP || clip == LINK_CLIP_CLIMB_UP_FREE ||
                clip == LINK_CLIP_SWIM_ENTER || clip == LINK_CLIP_SWIM_FALL ||
                clip == LINK_CLIP_DIVE_START || clip == LINK_CLIP_DIVE_END ||
                link_clip_pinned[clip])
               ? absolute : entry->first;
    for (i = 0; i < 3; ++i)
        root[i] = link_root[absolute][i] +
            (link_root[next][i] - link_root[absolute][i]) * (int)fraction / 256;
    if (link_clip_pinned[clip]) {
        /* AnimMovement clip: its root moves the actor (link_anim_state.c),
        ** the drawn root stays at baseTransl as a child draws it. Without
        ** UPDATE_Y (2) the clip's own y is drawn. */
        root[0] = LINK_PINNED_ROOT_X;
        if (link_clip_pinned[clip] == 1)
            root[1] = LINK_PINNED_ROOT_Y;
        root[2] = LINK_PINNED_ROOT_Z;
    }
    for (i = 0; i < LINK_LIMB_COUNT * 3; ++i) {
        /* Interpolate across the short side of the 16-bit angle wrap. */
        int32_t delta = (uint16_t)(link_rotations[next][i] - link_rotations[absolute][i]);
        if (delta > 32767) delta -= 65536;
        rotations[i] = (int16_t)(link_rotations[absolute][i] + delta * (int)fraction / 256);
    }
    pose_skeleton(root, rotations);
    skin_vertices();
}

void            link_anim_reset(void)
{
    posed_frame = -1;
}

/* OoT PLAYER_LIMB_L_HAND is 0x10; imported limb indices start at zero.
 * z_player_lib.c Kokiri sword: base (0,400,0), tip (3000,400,0). */
void link_anim_blade(int32_t out[2][3])
{
    const limb_matrix_t *hand = &limb_matrices[15];
    unsigned int end, axis;
    for (end = 0; end < 2; ++end) {
        for (axis = 0; axis < 3; ++axis) {
            int32_t model = hand->origin[axis] +
                (FIXED_MUL(hand->m[axis][0], INTEGER_FIXED(end ? 3000 : 0)) +
                 FIXED_MUL(hand->m[axis][1], INTEGER_FIXED(400))) / 65536;
            out[end][axis] = model * LINK_ANIM_SCALE_Q16;
        }
        out[end][0] += INTEGER_FIXED(LINK_ANIM_SHIFT_X);
        out[end][1] += INTEGER_FIXED(LINK_ANIM_SHIFT_Y);
        out[end][2] += INTEGER_FIXED(LINK_ANIM_SHIFT_Z);
    }
}
