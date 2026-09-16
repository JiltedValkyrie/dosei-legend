/*
** SCSP score player: bank-agnostic, with fading switches between banks.
**
** A "bank" is one score plus its sample set: a PCM file staged on the CD, a
** per-frame envelope file, and the generated trigger/sample tables. Banks are
** declared wherever the game keeps its content (see music_banks.h); nothing in
** this module knows which tracks exist.
**
** Only one bank can be resident at a time. A Saturn has 512 KB of sound RAM
** and these banks are ~480 KB each at the same sample base, so switching means
** fading out, stopping the voices and overwriting sound RAM in place. That is
** what music_fade_to() starts and music_service() finishes.
*/

#ifndef VIEWER_MUSIC_H
#define VIEWER_MUSIC_H

#include <stdbool.h>
#include <stdint.h>

/* Layouts the generated score headers already use, so their tables can be
 * pointed at directly rather than copied. */
typedef struct { uint32_t offset; uint16_t loop_start, loop_end; } music_pcm_t;
typedef struct { uint16_t frame; uint8_t slot, sample; uint16_t pitch; uint8_t pan; }
    music_trigger_t;

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

/** @brief Fade the current bank out, swap to @p bank, and fade it back in.
 *
 *  The swap itself is streamed by music_service(); this only starts it.
 *  @param fade_frames vblanks for each half of the fade, 0 for an instant cut.
 *  @return false if a switch is already running or @p bank is already playing.
 */
bool music_fade_to(const music_bank_t *bank, unsigned int fade_frames);

/** @brief Main-thread half of a switch: streams the incoming bank into sound
 *  RAM a few chunks per frame. Call once per rendered frame. Never call from a
 *  vblank callback -- it reads the CD and allocates. */
void music_service(void);

/** @brief The bank currently playing, or NULL before music_init(). */
const music_bank_t *music_current(void);

/** @brief True while a switch is fading or streaming. */
bool music_busy(void);

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
