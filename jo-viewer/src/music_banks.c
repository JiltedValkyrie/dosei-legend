/*
** Bank definitions. Both generated score headers declare the same sample and
** trigger layouts, which is what lets the player point straight at their
** tables instead of copying them; the casts below rely on that and would break
** loudly if a future score changed shape.
*/

#include <jo/jo.h>
#include "music_banks.h"
#include "title_score.h"
#include "kokiri_score.h"

/* The title score's generated header does not export its sample-bank size;
** this is the figure its loader has always validated against. */
#define TITLE_PCM_BYTES 480046

const music_bank_t music_bank_title = {
    "TITLE.PCM", "TITLE.LVL",
    (const music_pcm_t *)title_pcm, (const music_trigger_t *)title_triggers,
    TITLE_TRIGGER_COUNT, TITLE_FRAMES, TITLE_LOOP_FRAME, TITLE_VOICES,
    TITLE_SAMPLE_BASE, TITLE_PCM_BYTES, TITLE_FRAMES * TITLE_VOICES
};

const music_bank_t music_bank_kokiri = {
    "FOREST.PCM", "FOREST.LVL",
    (const music_pcm_t *)kokiri_pcm, (const music_trigger_t *)kokiri_triggers,
    KOKIRI_TRIGGER_COUNT, KOKIRI_FRAMES, KOKIRI_LOOP_FRAME, KOKIRI_VOICES,
    KOKIRI_SAMPLE_BASE, KOKIRI_PCM_BYTES, KOKIRI_LEVEL_BYTES
};
