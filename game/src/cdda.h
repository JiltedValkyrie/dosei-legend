#ifndef DOSEI_CDDA_H
#define DOSEI_CDDA_H
#include <stdbool.h>

/*
** Red Book tracks (tools/build_cdda.py, write_cue.py). Track 01 is data.
** Playing one moves the drive off the data track: a file read during it
** stops the song (GFS seeks back), so play only when nothing streams.
**
** Rule (DOSEI-LEGEND-BIBLE.md, Red Book): only while the world is frozen --
** chest open (mini cutscene), cutscenes, first-stick get-item show (text box
** freezes the world), heart-container get-item (fanfare holds the world),
** death/Game Over. Never in live play or combat.
*/
/*
** Track numbers and names are generated from assets/audio/cdda_tracks.json by
** tools/build_cdda.py. Importing a track needs no driver changes. The song
** dictionary resolves its stable name through CDDA_TRACK_<NAME> on each build.
*/
#include "cdda_tracks.h"

/* Driver API for music_songs.c. Gameplay uses music_play(NA_BGM_...), not tracks.
 * Any audio track on the disc; out-of-range requests are ignored. */
void    cdda_play(int track);
/* Main thread: wait for pending music loads, then monitor actual CD status. */
void    cdda_service(void);
bool    cdda_busy(void);

#endif
