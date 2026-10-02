#ifndef ASSET_NAMES_H
#define ASSET_NAMES_H
#include <stdbool.h>

/* Per-scene/room CD names use one base-36 character per id (0-9, A-Z), so
** "S0R0.MSH" style 8.3 names reach 36 scenes x 36 rooms. Mirrors
** tools/asset_names.py. */
#define ASSET_ID_LIMIT 36u

static inline char asset_name_digit(unsigned int value)
{
    return (char)(value < 10u ? '0' + value : 'A' + (value - 10u));
}

/* Scene ids reach 36*36: scene < 36 keeps "S<s>R<r>.EXT"; higher scenes
** use "Z<s1><s0>R<r>.EXT". room < 0 = scene file ("S<s>.EXT"/"Z<ss>.EXT").
** out holds at least 12 chars. Mirrors tools/asset_names.py. */
#define ASSET_SCENE_LIMIT (ASSET_ID_LIMIT * ASSET_ID_LIMIT)

static inline bool asset_scene_name(char *out, unsigned int scene, int room, const char *ext)
{
    char *p = out;
    if (scene >= ASSET_SCENE_LIMIT || room >= (int)ASSET_ID_LIMIT) return false;
    if (scene < ASSET_ID_LIMIT) { *p++ = 'S'; *p++ = asset_name_digit(scene); }
    else {
        *p++ = 'Z';
        *p++ = asset_name_digit(scene / ASSET_ID_LIMIT);
        *p++ = asset_name_digit(scene % ASSET_ID_LIMIT);
    }
    if (room >= 0) { *p++ = 'R'; *p++ = asset_name_digit((unsigned int)room); }
    *p++ = '.';
    while (*ext) *p++ = *ext++;
    *p = 0;
    return true;
}

#endif
