# Audio work list

Updated 2026-09-15. See [current audio reference](../../../title-screen/docs/AUDIO.md)
and [project handoff](../../../CLAUDE.md). This list replaces the Ponesound-era list.

## Completed

- [x] Re-extracted US 1.2 Sequence 30 / Soundfont 6 and rebuilt live SCSP playback.
- [x] Seven signed 16-bit samples, loop guards, explicit key-off before retrigger.
- [x] Tempo-aware gates, live channel volume, squared gains, one-time intro.
- [x] Video-clock scheduling independent of scene draw rate.
- [x] User approved the rebuilt music; six audio regression tests pass.
- [x] Moved runtime into `src/audio`, generated files into `assets/generated`,
      and tests into `tests` under `title-screen`.

## Remaining

- [ ] Real Saturn validation, including stereo pan and loop transitions.
- [ ] Reverb, vibrato automation, and filters if required for greater fidelity.
- [ ] Generalize beyond Sequence 30 / Soundfont 6 when another track is requested.
- [ ] Implement a separate SFX playback path when gameplay needs it.

The active priority is scene stability/performance, not another audio rebuild.
The latest reorganized scene run did not crash, following an earlier 7 FPS
invalid-opcode failure. Its cause remains unconfirmed; see
[debugging evidence](../../../title-screen/docs/DEBUGGING.md).
