#ifndef DOSEI_MESH_LOD_H
#define DOSEI_MESH_LOD_H
/*
** Per-mesh LOD rows from a room bank (KRM1 header[6], build_room_scene.py
** LOD_RECORD). Big-endian layout matches the SH-2 directly.
**
**   distance(Link, centre) - radius <  lod0_distance -> LOD0 (close-up set)
**   distance(Link, centre) - radius <  cull_distance -> LOD1 (original set)
**   otherwise                                        -> neither drawn
**
** Integers only (SH-2 has no FPU). Coordinates are quartered before squaring:
** a 16-bit world span quarters to <= 16384, so three squares stay < 2^31.
*/

typedef struct {
    short          centre[3];       /* source space, Y up */
    unsigned short radius;
    unsigned short lod0_distance;
    unsigned short cull_distance;
    unsigned char  lod1_object;     /* original geometry */
    unsigned char  lod0_object;     /* MESH_LOD_NONE when no close-up set */
    unsigned char  pad[2];
} mesh_lod_t;

typedef char mesh_lod_record_is_16_bytes[sizeof(mesh_lod_t) == 16 ? 1 : -1];

#define MESH_LOD_NONE   0xFFu
#define MESH_LOD_NEAR   0u
#define MESH_LOD_FAR    1u
#define MESH_LOD_CULLED 2u

static inline int mesh_lod_quarter(int position, int centre)
{
    int d = position - centre;
    if (d > 65535) d = 65535;
    if (d < -65535) d = -65535;
    return d >> 2;
}

static inline unsigned int mesh_lod_select(const mesh_lod_t *m, int x, int y, int z)
{
    int dx = mesh_lod_quarter(x, m->centre[0]);
    int dy = mesh_lod_quarter(y, m->centre[1]);
    int dz = mesh_lod_quarter(z, m->centre[2]);
    int d2 = dx * dx + dy * dy + dz * dz;
    int cull = ((int)m->cull_distance + (int)m->radius) >> 2;
    if (m->lod0_object != MESH_LOD_NONE) {
        int near = ((int)m->lod0_distance + (int)m->radius) >> 2;
        if (d2 < near * near) return MESH_LOD_NEAR;
    }
    return d2 < cull * cull ? MESH_LOD_FAR : MESH_LOD_CULLED;
}

#endif
