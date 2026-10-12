#ifndef FOREST_VERTEX_PACK_H
#define FOREST_VERTEX_PACK_H

/* Build a bounded draw-only point list. Source points never move and hidden
 * polygons never get rewritten. Restore visible indices before the next cull.
 * Overflow leaves all source geometry untouched and uses the full bank. */
static unsigned __attribute__((noinline)) forest_gather_vertices_dual(const POINT *source, unsigned count,
    POLYGON *polys, unsigned visible, POINT *draw, unsigned capacity,
    POINT *spill, unsigned spill_capacity, POINT **selected,
    unsigned short *map, unsigned short *inverse)
{
    unsigned i, j, used = 0;
    unsigned limit = spill && spill_capacity > capacity ? spill_capacity : capacity;
    *selected = draw;
    for (i = 0; i < count; ++i) map[i] = 0xFFFF;
    for (i = 0; i < visible; ++i) for (j = 0; j < 4; ++j) {
        unsigned old = polys[i].Vertices[j];
        if (map[old] != 0xFFFF) continue;
        if (used == limit) return 0;
        map[old] = (unsigned short)used;
        inverse[used] = (unsigned short)old;
        ++used;
    }
    if (used > capacity) draw = spill;
    *selected = draw;
    for (i = 0; i < used; ++i) {
        unsigned old = inverse[i];
        draw[i][0] = source[old][0];
        draw[i][1] = source[old][1];
        draw[i][2] = source[old][2];
    }
    for (i = 0; i < visible; ++i) for (j = 0; j < 4; ++j)
        polys[i].Vertices[j] = map[polys[i].Vertices[j]];
    return used;
}

static unsigned forest_gather_vertices(const POINT *source, unsigned count,
    POLYGON *polys, unsigned visible, POINT *draw, unsigned capacity,
    unsigned short *map, unsigned short *inverse)
{
    POINT *selected;
    return forest_gather_vertices_dual(source, count, polys, visible, draw,
        capacity, 0, 0, &selected, map, inverse);
}

static void forest_restore_vertices(POLYGON *polys, unsigned visible,
                                    const unsigned short *inverse)
{
    unsigned i, j;
    for (i = 0; i < visible; ++i) for (j = 0; j < 4; ++j)
        polys[i].Vertices[j] = inverse[polys[i].Vertices[j]];
}

/* Compact the vertices referenced by the visible polygon prefix in-place.
 * Every polygon (including hidden ones) is remapped, so turning the camera
 * back restores exactly the same world. No vertices or polygons are removed.
 * map/inverse each hold vertex_count unsigned shorts. Runs only after depth,
 * culling and fog have finished; callers may reuse their depth/side scratch.
 * POINT and POLYGON are supplied by the SGL caller (or host fixture). */
/* Pack mode 1 is a Debug fallback; keep it out of the hot prepare body. */
static unsigned __attribute__((noinline, optimize("Os"))) forest_pack_vertices(POINT *points, unsigned vertex_count,
                                     POLYGON *polygons, unsigned polygon_count,
                                     unsigned visible, unsigned short *map,
                                     unsigned short *inverse)
{
    unsigned i, j, used = 0, moved = 0;
    /* Preserve the previous prefix order. Polygon order changes with culling;
     * rebuilding vertex order from first occurrence made even the same visible
     * set shuffle points and rewrite every hidden polygon on camera motion.
     * inverse is now a mark array; only holes in the desired prefix move. */
    for (i = 0; i < vertex_count; ++i) inverse[i] = 0;
    for (i = 0; i < visible; ++i)
        for (j = 0; j < 4; ++j) {
            unsigned old = polygons[i].Vertices[j];
            if (!inverse[old]) { inverse[old] = 1; ++used; }
        }
    for (i = 0; i < used; ++i) if (!inverse[i]) break;
    if (i == used) return used; /* same prefix: no map or geometry writes */
    for (j = 0; j < vertex_count; ++j) map[j] = (unsigned short)j;
    j = used;
    for (; i < used; ++i) {
            if (!inverse[i]) {
                unsigned k;
                while (!inverse[j]) ++j; /* each prefix hole has a marked tail */
                for (k = 0; k < 3; ++k) {
                    int32_t value = points[i][k];
                    points[i][k] = points[j][k];
                    points[j][k] = value;
                }
                map[i] = (unsigned short)j; map[j] = (unsigned short)i;
                ++j;
                moved = 1;
            }
        }
    if (moved)
        for (i = 0; i < polygon_count; ++i)
            for (j = 0; j < 4; ++j)
                polygons[i].Vertices[j] = map[polygons[i].Vertices[j]];
    return used;
}
#endif
