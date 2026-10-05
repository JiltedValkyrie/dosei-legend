#pragma GCC optimize("Os") /* small logic: size over speed (work RAM) */
#ifdef __GNUC__
#pragma GCC optimize ("Os")
#endif
#include "music_songs.h"
#include "music_banks.h"
#include "cdda.h"

typedef struct {
    unsigned short song, track;
    const music_bank_t *bank;
} song_route_t;

/* Small read-only dictionary; no heap or mutable playback state. */
static const song_route_t routes[] = {
#define SONG_BANK(id, bank) { id, 0, &music_bank_##bank },
#define SONG_CD(id, track) { id, track, 0 },
#include "song_routes.inc"
#undef SONG_BANK
#undef SONG_CD
};

static const song_route_t *route_for(oot_song_t song)
{
    unsigned int i;
    for (i = 0; i < sizeof(routes) / sizeof(routes[0]); ++i)
        if (routes[i].song == song) return &routes[i];
    return 0;
}

bool music_play_fade(oot_song_t song, unsigned int frames)
{
    const song_route_t *route = route_for(song);
    if (!route) return false;
    if (route->track) {
        cdda_play(route->track);
        return true;
    }
    return music_fade_to(route->bank, frames);
}

bool music_play(oot_song_t song)
{
    return music_play_fade(song, 0);
}

bool music_song_routed(oot_song_t song)
{
    return route_for(song) != 0;
}

const music_bank_t *music_song_bank(oot_song_t song)
{
    const song_route_t *route = route_for(song);
    return route ? route->bank : 0;
}
