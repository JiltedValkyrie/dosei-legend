#ifndef DOSEI_ENVIRONMENT_SKY_H
#define DOSEI_ENVIRONMENT_SKY_H

/* Cached background refresh, not the geometry hot path. Avoid duplicating
 * RGB-channel arithmetic at every gradient call under the SDK's -O3/LTO. */
#pragma GCC push_options
#pragma GCC optimize("Os")

/* Offline source-image colours, exact source schedule boundaries. The visual
 * gradient is an approximation. All runtime arithmetic is bounded 32-bit.
 * Caller owns cutscene overrides, scene/weather selection and black fades.
 * Do not mark these inline: the SDK uses -fkeep-inline-functions and would
 * retain unused copies of every helper/table in each caller. */
typedef struct {
    unsigned short start, end;
    unsigned char change, first, second;
} environment_sky_entry_t;
typedef char environment_sky_entry_size[sizeof(environment_sky_entry_t) == 8 ? 1 : -1];
#include "environment_sky_data.h"

static __attribute__((unused, noinline)) unsigned short environment_sky_mix(unsigned short a, unsigned short b,
                                                unsigned int weight)
{
    unsigned int shift, colour = 0x8000u;
    if (weight > 255u) weight = 255u;
    for (shift = 0; shift <= 10u; shift += 5u)
        colour |= ((((a >> shift) & 31u) * (255u - weight) +
                    ((b >> shift) & 31u) * weight + 127u) / 255u) << shift;
    return (unsigned short)colour;
}

static __attribute__((unused)) void environment_sky_select(unsigned int time, unsigned int config,
                                         unsigned int *first, unsigned int *second,
                                         unsigned int *blend)
{
    unsigned int i;
    const environment_sky_entry_t *entry;
    time &= 65535u;
    if (config >= 4u) config = 0;
    entry = &environment_sky_schedule[config][8];
    for (i = 0; i < 9u; ++i) {
        const environment_sky_entry_t *candidate = &environment_sky_schedule[config][i];
        if (time >= candidate->start && (time < candidate->end || candidate->end == 65535u)) {
            entry = candidate;
            break;
        }
    }
    *blend = (time - entry->start) * 255u / (entry->end - entry->start);
    if (config == 3u) {
        /* CUTSCENE_MAP loads holy0/holy1 once. Its schedule indices 8..11
         * do not select textures; Environment_UpdateSkybox only uses blend. */
        *first = 8u;
        *second = 9u;
        if (!entry->change) *blend = 0;
    } else {
        *first = entry->first;
        *second = entry->second;
        if (!entry->change) *blend = *blend < 128u ? 255u : 0;
    }
}

static __attribute__((unused)) unsigned short environment_sky_top_indices(unsigned int first,
                                                        unsigned int second,
                                                        unsigned int blend)
{
    if (first >= ENVIRONMENT_SKY_COLOURS) first = 1u;
    if (second >= ENVIRONMENT_SKY_COLOURS) second = first;
    return environment_sky_mix(environment_sky_sources[first], environment_sky_sources[second], blend);
}

static __attribute__((unused)) unsigned short environment_sky_top(unsigned int time, unsigned int config)
{
    unsigned int first, second, blend;
    environment_sky_select(time, config, &first, &second, &blend);
    return environment_sky_top_indices(first, second, blend);
}

/* Metadata getter: original skybox id [7:0], config [15:8], disabled bit16,
 * source light mode [31:24]. Panoramas render through their existing backend;
 * NONE/UNSET and a disabled sky must not invent a daytime outdoor sky. */
static __attribute__((unused)) unsigned short environment_sky_theme_top(unsigned int time, unsigned int metadata)
{
    unsigned int identity = metadata & 255u;
    if (metadata & 0x10000u) return 0x8000u;
    if (identity == 1u) /* SKYBOX_NORMAL_SKY */
        return environment_sky_top(time, (metadata >> 8) & 255u);
    if (identity == 3u) /* SKYBOX_OVERCAST_SUNSET: fixed vr_cloud2 */
        return environment_sky_sources[6];
    if (identity == 5u) /* SKYBOX_CUTSCENE_MAP: fixed holy0/holy1 pair */
        return environment_sky_top(time, 3u);
    return 0x8000u;
}

static __attribute__((unused)) unsigned short environment_sky_floor(unsigned int scene)
{
    return scene < ENVIRONMENT_SKY_SCENES ? environment_sky_ground[scene] : 0xCF7Bu;
}

/* Source base-scene dawn/day/dusk/night fog. Approximate smooth six-hour
 * interpolation; static-light rooms have four identical entries. */
static __attribute__((unused)) unsigned short environment_map_colour(unsigned scene, unsigned time)
{
    unsigned phase=time&65535u, a=phase>>14;
    if (scene>=ENVIRONMENT_SKY_SCENES) return environment_sky_floor(scene);
    /* At midnight use night (3), at noon day (1). */
    a=(a+3u)&3u;
    return environment_sky_mix(environment_map_fog[scene][a],
        environment_map_fog[scene][(a+1u)&3u],(phase&16383u)>>6);
}
static __attribute__((unused)) unsigned short environment_map_floor(unsigned scene,unsigned time)
{
    return environment_sky_mix(environment_sky_floor(scene),environment_map_colour(scene,time),192);
}
static __attribute__((unused)) unsigned short environment_haze_colour(unsigned scene,unsigned time)
{
    return environment_sky_mix(environment_map_floor(scene,time),0x8000u,192);
}
static __attribute__((unused)) unsigned short environment_map_top(unsigned scene,unsigned time,unsigned metadata)
{
    unsigned id=metadata&255u;
    unsigned short fog=environment_map_colour(scene,time);
    if (!(metadata&0x10000u) && id==0x1du) return environment_sky_mix(fog,0x8000u,96);
    if (id!=1u || (metadata&0x10000u)) return environment_sky_theme_top(time,metadata);
    return environment_sky_mix(environment_sky_theme_top(time,metadata),fog,64);
}

/* Normalize the caller's output row to 0..239, including interlaced output.
 * Compute top/floor once per refresh; cache on these colours to avoid a table
 * rewrite when time changes without crossing an RGB555 colour boundary. */
static __attribute__((unused)) unsigned short environment_sky_gradient(unsigned int row,
                                                     unsigned short top,
                                                     unsigned short floor)
{
    if (row >= 120u) return floor;
    return environment_sky_mix(top, floor, row * 255u / 120u);
}

/* Shared map horizon veil: four broad colour steps behind world geometry.
 * The line-colour screen costs no VDP1 polygons, textures or sprite slots. */
static __attribute__((unused)) unsigned short environment_field_horizon(unsigned int row,
                                                      unsigned short top,
                                                      unsigned short floor)
{
    if (row < 72u) return environment_sky_gradient(row, top, floor);
    if (row >= 160u) return floor;
    unsigned short dark = environment_sky_mix(floor, 0x8000u, 192u);
    if (row < 84u) return environment_sky_mix(environment_sky_gradient(72u, top, floor), dark, 85u);
    if (row < 96u) return environment_sky_mix(environment_sky_gradient(72u, top, floor), dark, 170u);
    if (row < 108u) return dark;
    if (row < 120u) return environment_sky_mix(dark, floor, 64u);
    return environment_sky_mix(dark, floor, 64u + (row - 120u) * 191u / 40u);
}

static __attribute__((unused)) unsigned short environment_sky_colour_indices(unsigned int row, unsigned int scene,
                                                           unsigned int first, unsigned int second,
                                                           unsigned int blend)
{
    return environment_sky_gradient(row, environment_sky_top_indices(first, second, blend),
                                    environment_sky_floor(scene));
}

static __attribute__((unused)) unsigned short environment_sky_colour(unsigned int row, unsigned int scene,
                                                   unsigned int time, unsigned int config)
{
    return environment_sky_gradient(row, environment_sky_top(time, config), environment_sky_floor(scene));
}

#pragma GCC pop_options
#endif
