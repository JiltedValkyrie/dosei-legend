# Title screen audio — NA_BGM_TITLE on Saturn

Real-time sequencer playback of the OoT title theme (`NA_BGM_TITLE` /
`Sequence_30`) on Saturn hardware via the SCSP, driven by the community
"Ponesound" M68K sound driver. Lives under `title-screen/`: no pre-rendered
audio, no redbook track — the actual sequence data is parsed from the
decomp, instrument samples are the real soundfont, and an SH2 player walks
a flattened note-event table and drives Ponesound voices per note.

## Why this approach

Three options were on the table: pre-render the whole theme to one mixed
loop, stream it as redbook audio, or interpret the real sequence data live.
The user chose the live sequencer specifically — more work, but reusable for
every other track later, and true to how the original engine actually plays
the song rather than a fixed recording of one performance of it.

## Pipeline

```
seq_30.seq (decomp disassembly)  ──┐
aseq.h (PITCH_ defines)            ├──► tools/make_title_sequence.py ──► title_sequence.h
Soundfont_6.xml (envelopes)        │         (needs title_samples.h already generated)
title_samples.h ────────────────────┘

SampleBank_0 WAVs (smpl chunks)  ──► tools/make_title_samples.py ──► title_samples.h
                                                                  └─► assets/TITLE_SMP.RAW
```

Both generators are plain host-side Python (no build-system integration —
rerun by hand after editing, then rebuild). Output is C headers with `static
const` tables, plus one binary asset (the sample blob) picked up via
`BUILTIN_ASSETS` in the Makefile.

### `tools/make_title_samples.py`

Converts the 7 distinct samples Soundfont 6 references (instruments 1, 10,
11, 13, 14 — 10/11 and 13/14 share sample sets) from the decomp's per-sample
WAVs (`extracted/ntsc-1.1/assets/audio/samples/SampleBank_0/SampleNNN.wav`)
into one packed 8-bit blob:

- Each WAV's `smpl` chunk gives the MIDI root note and loop start/end
  directly (all loops here are infinite sustain) — no need to re-derive
  tuning from the N64 tuning formula.
- Native sample rates are **not uniform** (32000/22050/16000 Hz all appear)
  and are kept as-is per sample; only a sample that would exceed Ponesound's
  u16 frame-count limit gets downsampled, and only by as much as needed
  (one sample, ~5%).
- Every sample is trimmed to its own loop end (nothing past it is ever
  reachable) before the 16-bit → signed-8-bit conversion.
- Output: `assets/TITLE_SMP.RAW` (≈281 KB of the SCSP's 512 KB sound RAM,
  driver reserves the first 47 KB) + `title_samples.h` (per-sample
  offset/length/loop/rate/note, plus a program → sample-lo/norm/hi + note
  range table mirroring the soundfont's split-sample instruments).

### `tools/make_title_sequence.py`

A small interpreter over the decomp's own human-readable disassembly of
`Audioseq[0x18AE0:0x19BE0]` (`extracted/ntsc-1.1/assets/audio/sequences/
seq_30.seq`) — chosen over re-parsing raw bytecode because the disassembly
already carries correct section boundaries and symbolic names
(`PITCH_*`, `SF6_INST_*`).

**Three-level VM**, matching the real z64 audio engine's structure:
- **SEQ**: owns the tempo map (17 changes across the loop — this piece does
  real rubato, not a fixed BPM) and dispatches `ldchan` to spawn channels.
- **CHAN**: sets per-channel instrument/pan/volume (heavily automated — see
  below) and dispatches `ldlayer` to spawn layers.
- **LAYER**: where notes actually live (`notedvg`/`notedv`/`notevg`).

`call`/`end` are real subroutine calls at CHAN and LAYER level (a handful of
short repeated riffs, e.g. `CHAN_1071` is a volume-swell figure called from
multiple places) — handled with an explicit return-address stack.

**The whole sequence (intro + main loop) is treated as one repeating unit.**
The real engine plays a ~0.6s intro once, then loops forever on the single
`jump SEQ_0027`. Modelling "play once, then loop a different region" needs
player-side state for no real benefit here — replaying a 0.6s pad once every
~78s lap is inaudible. So the generator just walks start-to-jump as one
loop body.

**Everything player-facing is pre-resolved host-side**, because the SH2
build has no `pow()`/libm:
- `(program, note)` → `(sample_index, playback_rate_hz)`, using the
  program's split-sample note ranges and `base_rate * 2^((note-base_note)/12)`.
- `note` values from `PITCH_*` tokens are z64 note numbers and are converted
  to MIDI (`(21 + z64) % 128`) at parse time, so every downstream consumer
  (range bounds, base notes) is uniformly in MIDI space.
- Channel volume × note velocity → one 0-127 "level", sampled at each note's
  own tick from that channel's complete volume automation (see below).
- `gate`/`delay` → actual sounding duration in frames (see below).
- Output: `title_sequence.h` — one `static const` array of
  `{start_frame, duration_frames, sample_index, rate, level, pan, decay}`,
  plus `TITLE_SEQUENCE_LOOP_FRAMES` (the wrap point, in 60Hz frames).

## Things that are *not* obvious from the aseq bytecode

These were each real bugs, found by ear (with an assist from a fan MIDI
transcription the user supplied) and confirmed against
`src/audio/internal/seqplayer.c` in the decomp:

- **`gate` is not a duration.** It's the *trailing release portion*, in
  1/256ths of `delay`: `gateDelay = (gateTime * delay) >> 8`, and the note
  releases once `layer->delay` (which counts *down*) reaches `gateDelay`. So
  sounding length is `delay - ((gate * delay) >> 8)`, not `gate` itself.
  Using `gate` directly as sounding time roughly halved every note.
- **`notedv` zeroes `gateTime`**, it does not inherit the previous note's
  gate (only `notevg` inherits `delay`, not gate). A prior version of the
  converter carried gate forward for `notedv` too.
- **Channel volume is heavily automated and matters a lot.** The sequence
  does continuous swells (`vol` + `cdelay` runs, plus the shared `CHAN_1071`
  subroutine) and two channels (13/14, the "piano") never set `vol` in the
  loop body at all — they inherit `vol 127` from the one-time intro. Naive
  per-instrument velocity-only playback made those two channels drown
  everything else. Fixed with a two-phase channel walk: phase 1 builds the
  channel's complete volume timeline (a channel script can keep automating
  volume long after the `ldlayer` that spawned a given layer); phase 2
  replays layers against the finished timeline so each note samples the
  channel volume in effect *at that note's own tick*.
- **Several intro channels call `ldlayer` *before* `instr`/`pan`** with zero
  delay in between (e.g. `CHAN_007A`: ldlayer, ..., `instr SF6_INST_1`, all
  at the same instant). In the real engine only `delay`/`cdelay` advance the
  clock, so all zero-duration setup within one instant takes effect before
  any note actually sounds. Layers are queued and only actually spawned
  right before the next `delay`/`cdelay` or at end-of-script, using
  whatever program/pan is current by then — otherwise several layers came
  out with no instrument assigned at all.
- **Program/pan/volume are per-hardware-channel-slot state**, not
  per-channel-script state. Every loop-body channel (`CHAN_017F` etc.) never
  sets `instr` itself; it relies on whatever the intro channel loaded into
  that same slot number left behind. Threaded across `ldchan` calls via a
  `slot → (program, pan, vol)` dict.
- **Two struck instruments need an explicit fade.** Soundfont 6's envelopes
  Env2/Env3 (instruments 13/14) decay to silence over 229/298 ticks, but
  their samples loop forever and the channels sit at `vol 127` — without an
  approximated decay ramp they hold full level for the whole note. A linear
  per-frame fade using the envelope's own tick count was "the difference
  between piano and air horn" per direct user feedback.

## Saturn-side player (`title_player.c`)

A fixed 16-voice pool over Ponesound's `pcmCtrl` slots — deliberately *not*
a 1:1 model of the original 5 sequencer channels, since the real engine can
have more notes ringing than that at once but this track's actual peak
polyphony fits comfortably in 16. All per-note sample data (bulk-loaded once
at init) and pitch are pre-resolved; the player just:

1. Each frame, releases any voice whose `end_frame` has arrived, and applies
   the linear decay ramp to any decaying voice still sounding.
2. Consumes all events whose `start_frame` matches the current frame,
   claiming a voice for each (free first, then a mid-release voice, then the
   quietest active one — never blindly the soonest-to-end, since stealing a
   voice mid-release is itself audible).
3. Wraps `_frame`/the event cursor back to 0 at `TITLE_SEQUENCE_LOOP_FRAMES`.

### Ponesound gotchas found along the way (not sequence-data bugs — driver
### API bugs, applicable to Ponesound generally)

- **The sound CPU needs ~30 frames to boot after `SNDON`** before its
  command table pointer (`m68k_com->pcmCtrl`) is valid. Writing to it
  earlier scribbles through an uninitialised pointer — silent playback
  apart from one chunk's worth of pop. The stock example gets away without
  this wait (single static sample, different timing luck); the sequencer
  does not.
- **`convert_bitrate_to_pitchword`'s upstream signature takes a signed
  `short`.** Upstream only ever feeds one fixed sample rate, so 32767 was
  never a real ceiling for them. A sequencer routinely asks for transposed
  rates above that — 100 of 221 note events did — which overflowed to
  negative and indexed `logtbl[]` out of bounds via `PCM_CALC_OCT`. Garbage
  pitch on ~45% of notes. Fixed by widening the parameter to `int` in this
  project's copy of `ponesound.c`/`.h`.
- **`bytes_per_blank` must use the sample's *native* rate, not the
  transposed playback rate.** It paces the M68K driver's own bookkeeping
  against how the sample data is laid out in sound RAM (`playsize`/`LSA`
  are fixed byte offsets into the bulk blob); `pitchword` alone should
  control the audible transposition via SCSP hardware OCT/FNS. Feeding the
  transposed rate into both desynced the driver's pacing from the real loop
  boundaries — heard as the wrong instrument/pitch playing.
- **Per-voice `volume` is 0-7 (3-bit), not 0-15.** `ponesound.c`'s own
  loader comments `7` as "max volume"; a naive 0-127 → 0-15 scale pushed
  every loud note past the top of the real range.
- **SCSP `pan` is attenuation-based, not positional.** 0 = no attenuation
  (centre); the high bit selects which side to attenuate, the low bits how
  much. A naive `pan >> 3` meant a centred note (z64 pan 64) came out
  attenuated hard to one side instead of centred.
- **Hard `sh2_permit = 0` on note-off clicks.** Cutting the voice while its
  waveform is mid-cycle is a step discontinuity. A short (4-frame) linear
  release ramp before the actual key-off removes it; voice-stealing was
  also changed to never grab a voice mid-release (that's a click too) and
  to prefer the quietest active voice over "whichever ends soonest" when
  the pool is genuinely full.

## Validation against a reference

A user-supplied fan MIDI transcription of the theme was useful for
comparison, but **is not authoritative** — it's someone's transcription by
ear, not decomp-derived. It served its purpose (its note range immediately
made the signed-short pitchword overflow obvious) but its octave/channel
choices shouldn't be trusted as ground truth. One comparison worth noting
as *validated*, not disputed: naively comparing quarter-note counts (93 vs
97) looked like a discrepancy, but the two transcriptions use different
tempos and ticks-per-quarter — converted to real seconds using this
project's actual extracted tempo automation (17 changes) vs. the
reference's fixed 74 BPM, the two land within 1% of each other (77.90s vs
78.65s). No note is truncated at the loop seam either (checked
programmatically: last event ends exactly at the wrap frame).

## Known simplifications / not modelled

- **Velocity is linear, not velocity-squared.** The real engine computes
  amplitude via `velocitySquare = SQ(velocity)/SQ(127)` (see
  `seqplayer.c`). Not applied here since the balance was confirmed correct
  by ear without it — revisit only if a future track's dynamics feel off.
- **Envelope approximation is linear decay-to-zero**, not the soundfont's
  real 3-point envelope (attack/hold/decay with a separate release rate).
  Good enough for a decorative background loop; a truly accurate envelope
  would need per-frame ADSR-style state on top of what's here.
- **Pan direction (which SCSP bit means which side) is unverified on real
  hardware.** Derived from the pcmCtrl struct's field comments alone (no
  driver source available); if it's backwards the result is simply
  mirrored stereo, cheap to flip once confirmed.
- **The ~0.6s intro pad replays every loop lap** rather than playing once —
  see "one repeating unit" above.
