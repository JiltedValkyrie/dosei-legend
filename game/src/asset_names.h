#ifndef ASSET_NAMES_H
#define ASSET_NAMES_H

/* Per-scene/room CD names use one base-36 character per id (0-9, A-Z), so
** "S0R0.MSH" style 8.3 names reach 36 scenes x 36 rooms. Mirrors
** tools/asset_names.py. */
#define ASSET_ID_LIMIT 36u

static inline char asset_name_digit(unsigned int value)
{
    return (char)(value < 10u ? '0' + value : 'A' + (value - 10u));
}

#endif
