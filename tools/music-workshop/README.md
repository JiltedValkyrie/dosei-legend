# Music workshop

Browse every piece of music in the US 1.2 extraction, listen to one on the PC,
and bake it into a workspace revision or directly replace an existing game bank.

Launch with `open-music-workshop.bat`. Needs Python with Tkinter; no Pillow.

Open **Help > User guide** or press **F1** for the offline, searchable manual.
It covers every control, a first bake, troubleshooting and manual game integration.
The same [user guide](USER_GUIDE.md) can be read or shared without running the app.

## What it does

- Lists all 105 sequences with their `NA_BGM_*` names, the soundfont each one
  declares, its own loop label, and whether the game already ships it.
- **Inspect** interprets and bakes a sequence on the host and reports duration,
  frames, note and trigger counts, PCM bytes against the sample budget, and
  peak voices against the 24 SCSP voices. Anything over a limit turns red; it
  is reported, not silently corrected.
- **Preview WAV** writes a stereo host render and opens it in your player.
- **Generate to** selects Workspace revision or Title, Kokiri Forest, Navi
  cutscene, Deku Tree cutscene, Nightmare cutscene, Link's house or Kokiri Shop.
  Game targets overwrite the matching source PCM, levels, header and manifest
  immediately, without another confirmation. Runtime filenames and C symbols
  are selected automatically; Bank name is used for workspace exports or named CD songs.
  Rebuild Clean to update the disc. House/shop exports live in the tracked
  `game/assets/audio/interiors/` folder and override automatic baking on builds.
- **CD-DA track (Red Book)** adds the selected sequence to
  `game/assets/audio/cdda_tracks.json` and re-renders every track. A new entry
  takes the next free track number and gets a `CDDA_TRACK_<NAME>` define in the
  generated `build/generated/cdda_tracks.h`; reusing an existing name replaces
  that track in place. Choose the intended **Game song** before clicking
  **Generate / Publish**: audio and its CD route are saved together. Game BANK
  destinations also publish their audio and the selected song route together.
  **Save song mapping** remains available for assigning existing audio without
  rendering. Rebuild Clean after publishing.
  Gameplay calls `music_play(NA_BGM_GAME_OVER)` (or another stable song ID).
  `game/assets/audio/songs.json` routes IDs to BANK/CD, while cdda_tracks.json
  maps named CD songs to physical tracks. Reordering the disc changes neither
  gameplay calls nor dictionary routes. Current area/title/timed-bank callers
  require BANK; CD remains limited to the frozen-world fanfare/death callers.
- **Generate / Publish** with Workspace revision writes a fresh folder into
  `workspace/music/<NAME>/<timestamp>-<id>/` containing:

  | File | Contents |
  |---|---|
  | `<NAME>_PCM.RAW` | big-endian signed 16-bit mono sample bank, loaded at sound RAM `0x1000` |
  | `<NAME>_LEVELS.RAW` | frame-major SCSP total-level envelope bytes (`frames x voices`, 255 = silence) |
  | `<name>_score.h` | the same generated header shape as the shipping builders |
  | `<name>_manifest.json` | sequence sha256, counts, budgets and the limitations list |
  | `preview.wav` | host render, for listening only |

The blank override fields use whatever the sequence itself declares. Fill one in
to hand-tune a single bake: soundfont id, loop label, sample budget, voice
count, and whether to keep the sequence's own intro/loop point instead of
looping from the top.

**Check all** tries every sequence and fills the "Bakes?" column, so you can see
what is usable before picking one. It takes a few minutes and writes nothing;
`--survey` prints the same list from the command line.

## Only about half the music can be baked today

As of 2026-09-29, **51 of the 105 sequences bake**. The rest stop on something
`shared/tools/build_title_audio.py` has no SCSP counterpart for, and it refuses
rather than quietly producing wrong music:

| Reason | Sequences |
|---|---|
| `rldchan` (loads a channel from another sequence) | 22 |
| `bend` (pitch bend) | 12 |
| `combfilter`, `volexp`, `reverbidx` | 6 |
| split-range instruments, envelope/soundfont mismatches | 12 |
| infinite envelope release | 2 |

The tool names the exact blocker per sequence. Lifting one means teaching the
shared interpreter that opcode, which is real work on the audio pipeline and a
deliberate decision — this tool will not guess at it.

## What this does NOT do

- Preview WAV always writes to the workspace. Generate writes to the selected
  destination; game targets replace existing music. Use Git to review/revert.
- It does not add a new SCSP scene/music slot or build an ISO. Existing targets
  are wired already; adding a new streamed bank requires the code/build steps in
  the guide. A new CD-DA track is the exception: it needs no code change, only a
  `cdda_play(CDDA_TRACK_<NAME>)` call wherever you want it to play.
- A CD-DA track is plain 44.1 kHz stereo PCM and is not held to the SCSP voice
  or sample budgets, but it is big: roughly 10 MB per minute of disc space.
  Playing one also moves the drive off the data track, so it must only run
  while the world is frozen (DOSEI-LEGEND-BIBLE.md, Red Book).
- Preview and Generate bake the settings captured when clicked; edits made
  during an operation apply to the next operation, not the running export.
- It is not a new audio engine. All interpreting, soundfont loading, baking,
  resampling and previewing is done by `shared/tools/build_title_audio.py`, the
  same code the shipping builders use, so a bank from here has the same shape
  as `build_kokiri_audio.py` or `build_cutscene_audio.py` would produce.
- The WAV preview is a host render of the generated data. It is not emulator or
  hardware capture, and it does not prove the bank plays correctly on target.
- There is no reverb, vibrato or filtering; the SCSP player has no counterpart
  for those opcodes. They are listed per bank rather than dropped silently.

## Source material

The extraction is found through `tools/launcher/project_config.py`, preferring
`<oot_decomp>/extracted/ntsc-1.2/assets/audio` and falling back to
`shared/build/audio-source/extracted/assets/audio`. If neither exists the tool
says so; the extraction steps are in `legacy/libyaul/docs/AUDIO.md`.

Offline tool. Floating point is fine here; none of this runs on the SH-2.
