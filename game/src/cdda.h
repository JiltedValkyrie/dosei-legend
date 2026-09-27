#ifndef DOSEI_CDDA_H
#define DOSEI_CDDA_H

/*
** Red Book tracks (tools/build_cdda.py, write_cue.py). Track 01 is data.
** Playing one moves the drive off the data track: a file read during it
** stops the song (GFS seeks back), so play only when nothing streams.
*/
#define CDDA_TRACK_CHEST    2   /* NA_BGM_OPEN_TRE_BOX */

void    cdda_play(int track);

#endif
