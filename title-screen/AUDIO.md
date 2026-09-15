# US 1.2 title music

The active path is `build_title_audio.py` → `TITLE_PCM.RAW`,
`TITLE_LEVELS.RAW`, `title_score.h` → `title_player.c`.
It plays individual notes live on the Saturn SCSP. The WAV preview is a
diagnostic output, not a recording used by the game.

## Sources

The input ROM is the verified compressed US 1.2 image with MD5
`57a9719ad547c516342e1a15d5c28c3d`. A fresh ZeldaRET extraction is under
`build/audio-source/extracted/`. No US 1.1 extraction or fan MIDI is an input.
The MIDI in `../audio-comparison/` remains an informal comparison reference.
`audio_manifest.json` records sample/sequence hashes, tempo changes, sample
tuning, memory usage, and omitted opcodes.

Relevant original implementation:

- `oot/src/audio/internal/seqplayer.c`: delays, gates and velocity.
- `oot/src/audio/internal/effects.c`: live channel gain, squared volume and
  envelope targets.
- `oot/src/audio/internal/heap.c`: envelope time scale and release-rate table.
- Fresh `Soundfont_6.xml`: instrument ranges, envelope points and releases.

## Regenerate

From the project root in PowerShell:

```powershell
python title-screen/tools/extract_title_source.py --oot-root D:/Workspace-Claude/game-decomps/n64/oot --out title-screen/build/audio-source/segments
wsl -e bash -lc 'cd /mnt/d/Workspace-Claude/game-decomps/n64/oot && PYTHONDONTWRITEBYTECODE=1 .venv/bin/python3 tools/extract_audio.py -v ntsc-1.2 -b /mnt/d/Workspace-Claude/saturn-homebrew/dosei-legend/title-screen/build/audio-source/segments -o /mnt/d/Workspace-Claude/saturn-homebrew/dosei-legend/title-screen/build/audio-source/extracted --read-xml'
python title-screen/tools/build_title_audio.py --preview audio-comparison/title-us12-rebuild.wav
& C:/msys64/usr/bin/bash.exe -lc 'source ~/.yaul.env && cd /d/Workspace-Claude/saturn-homebrew/dosei-legend/title-screen && make'
python title-screen/tools/test_title_audio.py
```

The extraction writes only within this project's build directory. The first
script validates the ROM checksum before unpacking audio/code segments.
The second uses the decomp's existing Linux virtual environment and sampleconv.

## Playback design

- Seven signed, big-endian 16-bit samples. Filtered downsampling fits all of
  them in 480,046 bytes, starting at sound RAM offset 0x1000. Every loop has
  four guard samples so interpolation cannot read a neighboring instrument.
- An explicit SCSP key-off precedes every retrigger. A tiny 68000 idle
  program replaces Ponesound; the SH2 owns the slot registers.
- Sound RAM/register writes use 16-bit accesses. Gain uses SCSP total-level
  attenuation, with full direct-send level.
- Updates run in vblank, independently of rendering. PAL advances the 60 Hz
  score using a fractional counter; NTSC advances once per vblank.
- Note gates integrate the whole tempo map, including changes during a
  note. Channel volume updates throughout the note, then freezes for release.
  Velocity, channel gain, and envelope targets are squared.
- First pass: 77.9024 seconds. The 10.9133-second intro plays once.
  Later passes repeat the remaining 66.9891 seconds.

Hardware references: [SEGA loop/key control](https://www.infochunk.com/saturn/segahtml_en/hard/scsp/hon/p04_21.htm),
[total-level control](https://www.infochunk.com/saturn/segahtml_en/hard/scsp/hon/p04_24.htm),
and [SNDOFF timing bulletin](https://antime.kapsi.fi/sega/files/ST-TECH-51.pdf).

## Limits and validation

This is a melodic reconstruction, not a bit-exact N64 mixer. Reverb, vibrato
automation, and filters are not implemented. The generator reports these;
unexpected opcodes fail. Pan uses approximate SCSP attenuation steps.
Envelope/volume updates are quantized to video frames. The last four frames
fade at the loop boundary, then remaining tails stop before repeating.

The software preview uses equal-power pan and unquantized pitch, so it is
not an exact SCSP emulator. Its full-track peak was 0.4164 of full scale,
with no clipping. Tests cover pitch range, tempo-crossing gates, envelope
time scale, full sequence interpretation, loop guards, and linked assets.
User audition confirmed the rebuilt title music as "PERFECT" on 2026-09-15.
The playback platform was not specified; real-hardware verification remains
unconfirmed. Compilation alone does not establish audio fidelity.

Two isolated Kronos capture attempts failed to reach audio initialization:
no capture WAV or OpenAL log was produced. The helper
`tools/capture_title_audio.ps1` records only the emulator's OpenAL output,
not a microphone, and keeps its settings in `build/emulator-audio-test/`.
Its failure here is not evidence of either correct or incorrect game audio.

Legacy `make_title_samples.py`, `make_title_sequence.py`, `title_samples.h`,
`title_sequence.h`, and Ponesound files remain for historical comparison but
are outside the active build. Older audio notes describe that retired path.
