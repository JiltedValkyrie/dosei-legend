#pragma GCC optimize("Os") /* small cold code: size over speed (work RAM) */
#ifdef __GNUC__
#pragma GCC optimize ("Os")
#endif
#include <SEGA_CDC.H>
#include "cdda.h"
#include "music.h"

static int requested_track, active_track;
static bool saw_play;
static unsigned int last_play_tick;
bool cdda_busy(void) {return requested_track!=0 || active_track!=0;}

/* CDC_CdPlay one track once (jo_audio_play_cd_track without the audio module). */
void    cdda_play(int track)
{
    /* Whatever the manifest put on the disc, not a fixed three. */
    if (track < CDDA_TRACK_FIRST || track > CDDA_TRACK_LAST) return;
    requested_track = track;
    cdda_service();
}

void cdda_service(void)
{
    CdcStat stat;
    unsigned int now = music_vblank_count(), status;
    if (requested_track && !music_busy()) {
        CdcPly ply = {0};
        int track = requested_track;
        requested_track = 0;

        CDC_PLY_STYPE(&ply) = CDC_PTYPE_TNO;
        CDC_PLY_STNO(&ply) = track;
        CDC_PLY_SIDX(&ply) = 1;
        /* The final track ends at the disc lead-out. Kronos resolves a track
         * end through the NEXT track's TOC entry, which is unused for the last
         * track; it then reports PLAY forever. The drive's default end is the
         * lead-out on both hardware and emulator. */
        CDC_PLY_ETYPE(&ply) = track == CDDA_TRACK_LAST ? CDC_PTYPE_DFL : CDC_PTYPE_TNO;
        CDC_PLY_ETNO(&ply) = track;
        CDC_PLY_EIDX(&ply) = 99;
        CDC_PLY_PMODE(&ply) = CDC_PM_DFL;
        music_cdda_mute(true);
        if (CDC_CdPlay(&ply) == CDC_ERR_OK) {
            active_track = track;
            saw_play = false;
            last_play_tick = now;
        } else if (!active_track) {
            music_cdda_mute(false);
        }
        return;
    }
    if (!active_track) return;
    if (CDC_GetCurStat(&stat) != CDC_ERR_OK) {
        if (now - last_play_tick < 120) return;
    } else {
        status = CDC_GET_STC(&stat);
        if (status == CDC_ST_PLAY && CDC_STAT_TNO(&stat) == active_track) {
            saw_play = true;
            last_play_tick = now;
            return;
        }
        /* Seek/startup responses are not the end of a newly requested track.
         * Once playback was seen, pause/standby or another track means done
         * (including a data read that interrupted the music). */
        if ((status == CDC_ST_BUSY || status == CDC_ST_SEEK || status == CDC_ST_RETRY ||
             (!saw_play && (status == CDC_ST_PAUSE || status == CDC_ST_PLAY ||
                            status == CDC_ST_STANDBY))) && now - last_play_tick < 120)
            return;
    }
    active_track = 0;
    music_cdda_mute(false);
}
