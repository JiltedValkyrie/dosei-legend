/*
 * See title_player.h. This is a fixed-size voice pool over Ponesound's
 * pcmCtrl slots: every sample the theme uses is bulk-loaded into sound RAM
 * once at init, and each note-on claims whichever pool slot is free (or, if
 * none are, the one closest to finishing) rather than modelling the
 * original 5 sequencer channels 1:1. That is a real simplification - the
 * original engine can have more notes ringing at once than TITLE_PLAYER_
 * VOICE_COUNT - but it comfortably covers this track's actual peak
 * polyphony (documented in tools/make_title_sequence.py's header comment)
 * and keeps the player itself simple.
 *
 * All per-note pitch math and instrument/range resolution already happened
 * host-side (see title_sequence.h) - this file just feeds precomputed
 * (sample_index, rate) pairs to the SCSP.
 *
 * ## Voice stealing has to actually stop a voice before reusing it
 *
 * When every voice is busy, a new note has to steal one. The instrument
 * that never needs to (the single-line flute/lead, INST_1 - one voice's
 * worth of polyphony, essentially never contested) plays perfectly cleanly
 * throughout. Every instrument that steals voices often - the piano
 * especially, since its fading level makes it the most common steal
 * target - progressively degrades into noise the longer playback runs.
 * That pattern rules out a per-note cosmetic glitch: reconfiguring a
 * voice's hiAddrBits/playsize/LSA while the SCSP is still actively reading
 * the OLD sample through it does not just click once, it leaves that
 * hardware voice's internal playback state corrupted in a way that does
 * not self-heal - it keeps reading garbage on every subsequent loop
 * through whatever memory its position pointer landed on mid-write.
 *
 * The fix is to actually stop a stolen voice (sh2_permit=0) and leave it
 * stopped for a couple of real frames - giving the M68K driver, which
 * polls this struct asynchronously on its own vblank schedule rather than
 * ours, an actual chance to process the stop - before writing any new
 * address/pitch/playsize data into that slot. Doing the kill and the
 * restart in the same SH2 burst (tried first) is not enough: the driver
 * never gets a chance to observe the intermediate off state at all.
 */

#include "title_player.h"
#include "ponesound.h"
#include "title_samples.h"
#include "title_sequence.h"

#include <stdbool.h>
#include <string.h>

extern uint8_t asset_title_samples[];
extern uint8_t asset_title_samples_end[];

#define VOICE_COUNT 16

/* Sound RAM offset the sample blob is bulk-copied to - same convention as
 * Ponesound's own PCM_LOAD_OFFSET (just past the driver's reserved area). */
#define SAMPLE_BASE_OFFSET (0x408 + DRV_SYS_END + 0x20)

/*
 * Ponesound's per-voice `volume` feeds the SCSP's direct send level, which
 * is 3 bits - 0-7, not 0-15 (ponesound.c's own loader comments 7 as "max
 * volume"). Sending the 0-15 that a naive velocity scale produces pushes
 * every loud note past the top of the range.
 */
#define VOICE_VOLUME_MAX 7

/*
 * Frames spent ramping a voice to silence before actually keying it off.
 * Cutting sh2_permit while the waveform is mid-cycle leaves a step
 * discontinuity, which is audible as a click on every note end; the
 * soundfont's own envelopes have Release stages for exactly this reason.
 * Short enough not to audibly lengthen notes.
 */
#define VOICE_RELEASE_FRAMES 4

/*
 * Frames a stolen voice sits fully stopped (sh2_permit=0, no other fields
 * touched yet) before it's safe to reconfigure - see the file header.
 * 2 frames is a guess at "definitely more than one vblank has passed for
 * the driver to have polled and processed the stop", not a measured
 * minimum; cheap to raise if a hardware/real-driver test ever shows stolen
 * voices still glitching.
 */
#define VOICE_KILL_SETTLE_FRAMES 2

typedef struct {
        bool     active;        /* currently configured and sounding */
        bool     pending;       /* killed, waiting out the settle period to restart */
        uint8_t  settle_left;   /* frames left before a pending voice restarts */
        title_note_event_t pending_ev; /* note to start once settle_left hits 0 */

        uint16_t end_frame;
        uint16_t start_frame;
        uint16_t decay;   /* frames to fade to silence; 0 = holds level */
        uint8_t  level;   /* 0-127 at note-on, before decay is applied */
        uint8_t  release_left;  /* frames left in the release ramp; 0 = not releasing */
        uint8_t  release_level; /* level when the release began */
} voice_state_t;

static voice_state_t _voices[VOICE_COUNT];
static uint16_t _frame;
static uint16_t _event_cursor;

static uint8_t _current_level(int slot);
static void _voice_note_on(int slot, const title_note_event_t *ev);

/*
 * z64 pan (0 = hard left, 64 = centre, 127 = hard right) -> the SCSP's
 * direct pan field, which is attenuation-based rather than positional: bit
 * 4 selects which side to attenuate and bits 3-0 how much, with 0 meaning
 * no attenuation at all (centre). Feeding it a raw 0-15 from `pan >> 3`
 * meant a centred note still came out attenuated hard to one side.
 *
 * If the side bit turns out to be the other way round on real hardware the
 * result is simply mirrored stereo, which is why this isn't worth agonising
 * over until it can be heard on hardware.
 */
static uint8_t
_pan_to_dipan(uint8_t pan)
{
        if (pan == 64) {
                return 0;
        }

        if (pan < 64) {
                return 0x10 | (uint8_t)(((64 - pan) * 15) / 64);
        }

        return (uint8_t)(((pan - 64) * 15) / 63);
}

/*
 * Dispatches one note event to a voice. Three cases:
 *   1. A truly free voice (not active, not mid-settle): configure and play
 *      immediately.
 *   2. Nothing free: pick a voice to steal (prefer one already mid-release,
 *      else whichever is currently quietest), stop it now, and defer the
 *      actual reconfiguration - see the file header for why.
 *   3. Every voice is either active or already mid-settle from a previous
 *      steal: drop the note. Rare, and inaudible against the rest of the
 *      mix - corrupted playback is not.
 */
static void
_trigger_note(const title_note_event_t *ev)
{
        for (int i = 0; i < VOICE_COUNT; i++) {
                if ((!_voices[i].active) && (!_voices[i].pending)) {
                        _voice_note_on(i, ev);
                        return;
                }
        }

        int slot = -1;

        for (int i = 0; i < VOICE_COUNT; i++) {
                if (_voices[i].active && (!_voices[i].pending) &&
                    (_voices[i].release_left != 0)) {
                        slot = i;
                        break;
                }
        }

        if (slot < 0) {
                for (int i = 0; i < VOICE_COUNT; i++) {
                        if ((!_voices[i].active) || _voices[i].pending) {
                                continue;
                        }
                        if ((slot < 0) || (_current_level(i) < _current_level(slot))) {
                                slot = i;
                        }
                }
        }

        if (slot < 0) {
                return; /* every voice mid-settle already; drop this note */
        }

        m68k_com->pcmCtrl[slot].sh2_permit = 0;
        _voices[slot].active = false;
        _voices[slot].release_left = 0;
        _voices[slot].pending = true;
        _voices[slot].settle_left = VOICE_KILL_SETTLE_FRAMES;
        _voices[slot].pending_ev = *ev;
}

static void
_voice_note_on(int slot, const title_note_event_t *ev)
{
        const title_sample_t * const s = &title_samples[ev->sample_index];

        const uint32_t addr = SAMPLE_BASE_OFFSET + s->offset;
        const bool is_pal = (vdp2_tvmd_tv_standard_get() == VDP2_TVMD_TV_STANDARD_PAL);

        volatile _PCM_CTRL * const ctrl = &m68k_com->pcmCtrl[slot];

        ctrl->hiAddrBits = (uint16_t)(addr >> 16);
        ctrl->loAddrBits = (uint16_t)(addr & 0xFFFF);
        /*
         * pitchword is the SCSP hardware's own OCT/FNS pitch-shift, and is
         * the only thing that should vary with the note being played:
         * ev->rate is the TRANSPOSED target, computed host-side from
         * base_rate*2^((note-base_note)/12).
         *
         * bytes_per_blank paces the M68K driver's own bookkeeping against
         * how the sample data is actually laid out in sound RAM - it has to
         * use the sample's NATIVE base_rate, not the transposed one. Get
         * this wrong and the driver's read pacing desyncs from playsize/LSA
         * (which are fixed, real byte offsets into the bulk-loaded blob),
         * which can walk a voice past its own sample's end and into a
         * neighbouring one - i.e. exactly "the wrong instrument playing".
         */
        ctrl->pitchword = convert_bitrate_to_pitchword(ev->rate);
        ctrl->playsize = s->length;
        ctrl->LSA = s->loop_start;
        ctrl->bytes_per_blank = calculate_bytes_per_blank(s->base_rate, 1, is_pal);
        ctrl->bitDepth = PCM_TYPE_8BIT;
        ctrl->loopType = PCM_FWD_LOOP; /* every sample was trimmed to its loop end */
        ctrl->pan = _pan_to_dipan(ev->pan);
        ctrl->volume = (ev->level * VOICE_VOLUME_MAX) / 127;
        ctrl->sh2_permit = 1;

        _voices[slot].active = true;
        _voices[slot].pending = false;
        _voices[slot].end_frame = _frame + ev->duration_frames;
        _voices[slot].start_frame = _frame;
        _voices[slot].decay = ev->decay;
        _voices[slot].level = ev->level;
        _voices[slot].release_left = 0;
        _voices[slot].release_level = 0;
}

static void
_voice_note_off(int slot)
{
        m68k_com->pcmCtrl[slot].sh2_permit = 0; /* keys the voice's ICSR off */
        _voices[slot].active = false;
}

void
title_player_init(void)
{
        memcpy((void *)SCSP_RAM(SAMPLE_BASE_OFFSET), asset_title_samples,
            asset_title_samples_end - asset_title_samples);

        for (int i = 0; i < VOICE_COUNT; i++) {
                _voices[i].active = false;
                _voices[i].pending = false;
                _voices[i].end_frame = 0;
                _voices[i].release_left = 0;
        }

        _frame = 0;
        _event_cursor = 0;
}

/*
 * Level a voice should currently be at, ignoring release.
 *
 * INST_13/INST_14 are struck sounds whose soundfont envelopes fall to
 * silence (Env2/Env3), but their samples loop forever and both channels sit
 * at vol 127, so without an explicit fade they hold full level for the
 * whole note and bury the rest of the mix. This linear ramp is a crude
 * stand-in for the real 3-point envelope, but it's the difference between
 * "piano" and "air horn".
 */
static uint8_t
_current_level(int slot)
{
        const voice_state_t * const v = &_voices[slot];

        if (v->decay == 0) {
                return v->level;
        }

        const uint16_t elapsed = _frame - v->start_frame;
        if (elapsed >= v->decay) {
                return 0;
        }

        return (uint8_t)(((uint32_t)v->level * (v->decay - elapsed)) / v->decay);
}

static void
_voice_begin_release(int slot)
{
        _voices[slot].release_level = _current_level(slot);
        _voices[slot].release_left = VOICE_RELEASE_FRAMES;
}

void
title_player_update(void)
{
        for (int i = 0; i < VOICE_COUNT; i++) {
                voice_state_t * const v = &_voices[i];

                if (v->pending) {
                        v->settle_left--;
                        if (v->settle_left == 0) {
                                _voice_note_on(i, &v->pending_ev);
                        }
                        continue;
                }

                if (!v->active) {
                        continue;
                }

                if (v->release_left != 0) {
                        v->release_left--;
                        if (v->release_left == 0) {
                                _voice_note_off(i);
                        } else {
                                const uint32_t level =
                                    ((uint32_t)v->release_level * v->release_left) /
                                    VOICE_RELEASE_FRAMES;
                                m68k_com->pcmCtrl[i].volume =
                                    (level * VOICE_VOLUME_MAX) / 127;
                        }
                        continue;
                }

                const uint8_t level = _current_level(i);

                /* Start the release at the note's end, or as soon as a
                 * decaying voice has faded out - releasing an already-silent
                 * voice frees the slot instead of letting it hold one until
                 * end_frame and push real notes into voice stealing. */
                if ((v->end_frame == _frame) || ((v->decay != 0) && (level == 0))) {
                        _voice_begin_release(i);
                } else if (v->decay != 0) {
                        m68k_com->pcmCtrl[i].volume = (level * VOICE_VOLUME_MAX) / 127;
                }
        }

        while ((_event_cursor < TITLE_SEQUENCE_EVENT_COUNT) &&
               (title_sequence[_event_cursor].start_frame == _frame)) {
                _trigger_note(&title_sequence[_event_cursor]);
                _event_cursor++;
        }

        _frame++;
        if (_frame >= TITLE_SEQUENCE_LOOP_FRAMES) {
                /*
                 * A voice's end_frame/decay is an ABSOLUTE frame number, set
                 * at note-on and never revisited until it's reached. Wrapping
                 * _frame back to 0 does not make a still-active voice's stale
                 * end_frame reachable again for another entire lap - e.g. the
                 * last chord's notes, whose natural release runs right up to
                 * the loop boundary, would otherwise keep ringing on into the
                 * next lap instead of cutting off. Force every voice through
                 * the normal (click-free) release ramp right at the seam so
                 * no lap can bleed into the next one. Pending (mid-settle)
                 * voices are already stopped, so there's nothing to release.
                 */
                for (int i = 0; i < VOICE_COUNT; i++) {
                        if (_voices[i].active && (_voices[i].release_left == 0)) {
                                _voice_begin_release(i);
                        }
                }

                _frame = 0;
                _event_cursor = 0;
        }
}
