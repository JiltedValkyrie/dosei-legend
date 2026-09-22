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
#include "navi_score.h"
#include "deku_tree_score.h"

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

/*
** The opening cutscenes' cues, named by the cutscenes' own CS_START_SEQ
** commands. These are one-pass cues rather than area themes, so they loop from
** the top: a beat that outlives its cue repeats instead of falling silent.
**
** The nightmare's fanfare (NA_BGM_OPENING_GANON, sequence 35) is not here: it
** uses percussion, which tools/build_cutscene_audio.py cannot bake yet. The
** cutscene player leaves the current score alone for a bank it has not got,
** rather than substituting an unrelated one.
*/
const music_bank_t music_bank_navi = {
    "CSNAVI.PCM", "CSNAVI.LVL",
    (const music_pcm_t *)navi_pcm, (const music_trigger_t *)navi_triggers,
    NAVI_TRIGGER_COUNT, NAVI_FRAMES, NAVI_LOOP_FRAME, NAVI_VOICES,
    NAVI_SAMPLE_BASE, NAVI_PCM_BYTES, NAVI_LEVEL_BYTES
};

const music_bank_t music_bank_deku_tree = {
    "CSDEKU.PCM", "CSDEKU.LVL",
    (const music_pcm_t *)deku_tree_pcm,
    (const music_trigger_t *)deku_tree_triggers,
    DEKU_TREE_TRIGGER_COUNT, DEKU_TREE_FRAMES, DEKU_TREE_LOOP_FRAME,
    DEKU_TREE_VOICES, DEKU_TREE_SAMPLE_BASE, DEKU_TREE_PCM_BYTES,
    DEKU_TREE_LEVEL_BYTES
};
