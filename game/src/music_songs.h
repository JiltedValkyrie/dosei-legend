#ifndef DOSEI_MUSIC_SONGS_H
#define DOSEI_MUSIC_SONGS_H
#include "music.h"
#include "song_ids.h"

/* Gameplay names songs, never physical CD tracks. CD callers must freeze the world. */
bool music_play(oot_song_t song);
bool music_play_fade(oot_song_t song, unsigned int frames);
/* Startup and timed bank cues use the same dictionary. NULL for CD/unknown songs. */
const music_bank_t *music_song_bank(oot_song_t song);
/* songs.json has a route (bank or CD) for this song. */
bool music_song_routed(oot_song_t song);
#endif
