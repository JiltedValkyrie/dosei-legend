#ifndef DOSEI_CDDA_H
#define DOSEI_CDDA_H

/*
** Red Book tracks (tools/build_cdda.py, write_cue.py). Track 01 is data.
** Playing one moves the drive off the data track: a file read during it
** stops the song (GFS seeks back), so play only when nothing streams.
**
** Rule (DOSEI-LEGEND-BIBLE.md, Red Book): only while the world is frozen --
** chest open (mini cutscene), cutscenes, first-stick get-item show (text box
** freezes the world), death/Game Over. Never in live play or combat.
*/
#define CDDA_TRACK_CHEST    2   /* NA_BGM_OPEN_TRE_BOX */
#define CDDA_TRACK_GAME_OVER 3  /* NA_BGM_GAME_OVER */
#define CDDA_TRACK_SMALL_ITEM 4 /* NA_BGM_SMALL_ITEM_GET */

void    cdda_play(int track);

#endif
