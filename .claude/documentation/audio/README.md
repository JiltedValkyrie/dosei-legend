# Current title audio handoff

Updated 2026-09-15. The earlier US 1.1/Ponesound notes here were superseded.

Read [the root handoff](../../../CLAUDE.md) first, then
[current audio documentation](../../../title-screen/docs/AUDIO.md).

- Use the verified **US 1.2** ROM and a fresh `ntsc-1.2` extraction.
- Runtime: `title-screen/src/audio/title_music.c` and `title_player.c`.
- Generator: `title-screen/tools/build_title_audio.py`.
- Generated tables/manifests: `title-screen/assets/generated/`.
- Seven signed 16-bit PCM samples occupy 480,046 bytes, with loop guards.
- SH-2 drives SCSP registers directly; Ponesound and its old converters were removed.
- Live channel gain, squared velocity/envelope targets, integrated tempo changes,
  and a one-time intro are implemented. Do not reapply the old linear-velocity,
  repeated-intro, or Ponesound voice-settling assumptions.
- Music advances in VBlank independently of scene FPS. User approved this rebuild
  as "PERFECT". Real-hardware validation remains unconfirmed.
- Fan MIDI is an informal comparison, not authoritative timing or pitch data.

[Current work list](HITLIST.md) | [Archived review](../../../title-screen/docs/history/AUDIO_REVIEW.md)
