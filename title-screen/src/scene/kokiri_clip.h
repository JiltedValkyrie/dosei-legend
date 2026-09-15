#ifndef KOKIRI_CLIP_H
#define KOKIRI_CLIP_H
#include <stdbool.h>
#include <stdint.h>
#define NEAR_Z 20
typedef struct { int32_t x, y, z, b, c; } clip_vertex_t;
int kokiri_clip_frustum(const clip_vertex_t input[3], clip_vertex_t out[12], bool *changed);
unsigned kokiri_clip_outcode(clip_vertex_t p);
int32_t kokiri_project_offset(int32_t coordinate, int32_t z);
/* Resample a clipped quad from its original triangle's 4bpp baked tile. */
void kokiri_clip_texture(const uint8_t *source, unsigned size,
    const clip_vertex_t quad[4], uint8_t tile[128]);
#endif
