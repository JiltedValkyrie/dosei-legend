# Kokiri Forest music — handoff for Opus

Separate SCSP-ready arrangement of the existing local US 1.2 Kokiri Forest
sequence (`seq_60.seq`, soundfont 15). No fan MIDI or substitute composition.
The source mapping is `NA_BGM_KOKIRI` / sequence 60 in the local ZeldaRET
`include/tables/sequence_table.h`.

## Files

- `KOKIRI_PCM.RAW`: big-endian signed 16-bit mono sample bank, 480,082 bytes.
- `KOKIRI_LEVELS.RAW`: frame-major SCSP total-level envelopes, 73,896 bytes.
- `kokiri_score.h`: sample descriptors and 597 timestamped note triggers;
  same field layout as the title score, distinct `kokiri_`/`KOKIRI_` names.
- `manifest.json`: source hashes, timings, samples, memory sizes and omissions.
- Listen locally: `../../generated/kokiri-preview.wav` (generated/ignored).

60 Hz score, 3,079 frames, 24 voices. At the end, stop all voices, seek the
trigger cursor to frame **497**, and resume there. Intro is approximately
8.276 seconds; the repeating portion is approximately 43.034 seconds.
The preview contains the intro and one pass, not a loop-boundary acceptance test.

## Integration — intentionally left to Opus

No active `main.c`, `recomp.c`, makefile, build script, or music player was changed
by this audio task. Keep title music on the title screen; load this bank for
forest gameplay when ready to wire the transition.

1. Stage the raw files under distinct ISO names, e.g. `FOREST.PCM` and
   `FOREST.LVL`. Do not overwrite the existing title assets.
2. Generalize the music player's score descriptor and file-size validation.
   The current hardcoded title bank size **480046 is wrong for this bank**;
   use `KOKIRI_PCM_BYTES` (480082), `KOKIRI_LEVEL_BYTES`, and the generated limits.
3. Disable score updates and key off/mute before replacing sound RAM or freeing
   the current envelopes. Load the replacement with the existing word-write,
   small-staging-buffer approach. Re-enable playback only after a complete load.
   Never read CD or allocate memory in a vblank callback. Avoid registering a
   second simultaneous player callback during track changes.
4. These banks **cannot coexist in 512 KB sound RAM**. Replace the title bank;
   free its 112,176-byte envelope allocation before loading this 73,896-byte one.
   Loading the whole PCM bank into the application's heap is not viable either.
5. Keep recomp/input time independent of score time. Title re-entry requires
   loading the title bank back; exact restart/resume behavior is a gameplay choice.

PCM plus the 4 KB sound-CPU boot area occupies 484,178 of 524,288 bytes.
The title player's same SCSP slot programming and pitch fields apply.

## Rebuild / verification

From repository root:

```powershell
python game/tools/build_kokiri_audio.py --preview game/generated/kokiri-preview.wav
python -m unittest discover -s game/tests -p test_kokiri_audio.py
python -m unittest discover -s title-screen/tests -p test_title_audio.py
```

Requires the existing extraction under
`title-screen/build/audio-source/extracted/assets/audio`. `--source` overrides it.
The builder shares title export helpers; extensions cover font selection,
fresh-start sequence IO/branches, layer transposition and instrument base-note
overrides. Tests compare regenerated title PCM, envelopes and triggers byte/value
for byte/value against the existing assets: unchanged. All three Kokiri tests
and six existing title-audio tests passed.

This is an arrangement, not bit-exact N64 playback: reverb/vibrato omitted,
PCM downsampled for memory, 60 Hz volume envelopes, quantized SCSP pitch/pan,
four-frame fade at wrap and restarted voices. Preview peak is about 0.477 full
scale, with no clipping. The preview is a host reference, not emulator capture;
in-engine playback, subjective listening quality and repeated-loop transitions
still need acceptance. Opus's concurrent Link/control changes were left alone.
