#include <jo/jo.h>
#include "cdda.h"

/* CDC_CdPlay one track once (jo_audio_play_cd_track without the audio module). */
void    cdda_play(int track)
{
    CdcPly  ply;

    CDC_PLY_STYPE(&ply) = CDC_PTYPE_TNO;
    CDC_PLY_STNO(&ply) = track;
    CDC_PLY_SIDX(&ply) = 1;
    CDC_PLY_ETYPE(&ply) = CDC_PTYPE_TNO;
    CDC_PLY_ETNO(&ply) = track;
    CDC_PLY_EIDX(&ply) = 99;
    CDC_PLY_PMODE(&ply) = CDC_PM_DFL;
    CDC_CdPlay(&ply);
}
