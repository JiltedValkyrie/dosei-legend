/*
** SCSP score player: bank-agnostic, with fading switches between banks.
**
** A "bank" is one score plus its sample set: a PCM file staged on the CD, a
** per-frame envelope file, and the generated trigger/sample tables. Banks are
** declared wherever the game keeps its content (see music_banks.h); nothing in
** this module knows which tracks exist.
**
** Only one bank can be resident at a time. A Saturn has 512 KB of sound RAM
** and these banks are ~240 KB each at the same sample base, so switching means
** fading out, stopping the voices and overwriting sound RAM in place. That is
** what music_fade_to() starts and music_service() finishes.
*/

#ifndef VIEWER_MUSIC_H
#define VIEWER_MUSIC_H

#include <stdbool.h>
#include <stdint.h>
/* Tail reserved for resident action PCM; music never writes beyond this. */
#define MUSIC_SAMPLE_LIMIT 0x50000   /* banks ~319 KB at 0x1000 (+33% music budget) */

/* Layouts the generated score headers already use, so their tables can be
 * pointed at directly rather than copied. */
typedef struct { uint32_t offset; uint16_t loop_start, loop_end; } music_pcm_t;
typedef struct { uint16_t frame; uint8_t slot, sample; uint16_t pitch; uint8_t pan, channel; }
    music_trigger_t;
/* Source channel controls; no CD reads and no extra SCSP voices. */
void music_source_singing(unsigned int voice, unsigned int melody, bool alone);
void music_source_spatial(unsigned int volume, unsigned int pan);
bool music_fanfare_busy(void);

typedef struct {
    const char            *pcm_file;      /* sample bank, staged on the CD */
    const char            *level_file;    /* per-frame envelopes */
    const music_pcm_t     *pcm;
    const music_trigger_t *triggers;
    unsigned int           trigger_count;
    unsigned int           frames;        /* score length */
    unsigned int           loop_frame;    /* where the score resumes at the end */
    unsigned int           voices;
    unsigned int           sample_base;   /* byte offset into sound RAM */
    unsigned int           pcm_bytes;
    unsigned int           level_bytes;
}                          music_bank_t;

/** @brief Load @p bank and start playing it. Installs the vblank driver. */
bool music_init(const music_bank_t *bank);
/* Optional caller-owned temporary buffer: loads boot PCM in one CD request.
 * Capacity includes jo_fs_read_file_ptr's trailing byte; not retained. */
bool music_init_with_scratch(const music_bank_t *bank, void *scratch, unsigned int capacity);
/* Resident musical phrases. Selector runs at the phrase boundary in VBlank;
 * it must use integer state only, with no allocation or file I/O. */
void music_set_sections(const music_bank_t *bank,const unsigned short (*ranges)[2],
                        unsigned count,unsigned (*next)(unsigned));

/** @brief Fade the current bank out, swap to @p bank, and fade it back in.
 *
 *  The swap itself is streamed by music_service(); this only starts it.
 *  @param fade_frames vblanks for each half of the fade, 0 for an instant cut.
 *  @return false if a switch is already running or @p bank is already playing.
 */
bool music_fade_to(const music_bank_t *bank, unsigned int fade_frames);

/** @brief Fade the current bank out and stay silent.
 *
 *  A scene or cutscene beat can genuinely have no music -- the opening's sleep
 *  layer is sfx-only -- and leaving the previous theme playing is wrong.
 *  @return false if a switch is already running or nothing is playing.
 */
bool music_silence(unsigned int fade_frames);

/** @brief Main-thread half of a switch: streams the incoming bank into sound
 *  RAM a few chunks per frame. Call once per rendered frame. Never call from a
 *  vblank callback -- it reads the CD and allocates. */
void music_service(void);
/* One-shot score completion; resume is serviced on main thread, never VBlank. */
void music_once(const music_bank_t *one_shot,const music_bank_t *resume);
/* Dynamic tables remain pinned through one-shot playback and resumption. */
bool music_bank_referenced(const music_bank_t *bank);
/* Pause ducking: half amplitude (-6 dB), composed with fades; SFX unchanged. */
void music_menu_duck(bool enabled);

/* CD-DA owns the music mix: immediate mute, then a 0.5 s VBlank restore.
 * Composes with bank fades and menu ducking; does not touch SFX/CD sends. */
void music_cdda_mute(bool enabled);
/* Source main-BGM volume (0..127), fading over source 20 Hz frames. */
void music_source_volume(unsigned int volume, unsigned int frames);
void music_source_tempo(unsigned int ratio_q8); /* affects note/envelope clock, not PCM pitch */
unsigned int music_vblank_count(void);

/** @brief The bank currently playing, or NULL before music_init(). */
const music_bank_t *music_current(void);

/** @brief True while a switch is fading or streaming. */
bool music_busy(void);
/* Main thread only: relinquish CD read-ahead before another file access.
 * Resumed by music_service; false means the CD could not be released. */
bool music_yield_cd(void);

/** @brief True if a switch failed; the player is left silent and idle. */
bool music_failed(void);

/** @brief Vblanks the last completed switch took, end to end. 0 if none. */
unsigned int music_transition_frames(void);

/** @brief Vblanks from the switch request to the new bank actually playing. */
unsigned int music_audible_frames(void);

/** @brief Longest gap in vblanks between service calls during the last switch,
 *  i.e. the worst frame stall the streaming load caused. */
unsigned int music_worst_stall(void);

/** @brief Completed switches since init. */
unsigned int music_swap_count(void);

/** @brief Score frames advanced since init; a liveness counter. */
unsigned int music_ticks(void);

#endif
