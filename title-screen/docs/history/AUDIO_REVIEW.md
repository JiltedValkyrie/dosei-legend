# Title music review — 2026-09-15

**Archived pre-rebuild investigation; not current implementation guidance.**
The user approved the replacement US 1.2 direct SCSP music as "PERFECT".
Current audio documentation is [../AUDIO.md](../AUDIO.md); current project
status is in [../DEBUGGING.md](../DEBUGGING.md). File paths, line numbers,
no-commit observations, and next steps below describe the old snapshot only.

Scope: investigate the reported piano turning into crashing-wave noise after
the first chord. Production source and disc image were not changed. Playback
has not been reproduced or heard by Codex; the cause of the early noise is
not yet confirmed.

## Confirmed findings

### Normal voice reuse bypasses the stop safeguard

`title-screen/title_player.c:231` clears `sh2_permit` and immediately marks
the voice inactive. `_trigger_note` at line 145 can then reconfigure it and
set permission back to 1 in the same update. The asynchronous sound CPU may
never observe the stop. The two-frame settle applies only to stolen voices.

A host simulation of the current 221 events and the player's decay/release
rules found same-update reuse at frames 1170, 1381, 1968, 2178, 2368, 2374,
2756, 4070, and 4123. First occurrence: 19.5 seconds at 60 updates/second.
Another 10 reuses leave only one update between stop and restart.

This is a real synchronization gap, but does not explain onset at the second
chord (frame 350, approximately 5.83 seconds). Do not call it the confirmed
cause of that symptom.

Suggested correction: treat every retired voice as unavailable until the
driver acknowledges its release. Upstream uses `icsr_target == -1` to mark
an unassigned voice; verify that contract against the shipped driver before
using it. A stop request alone is not an acknowledgement.

### The existing voice-stealing diagnosis is unsupported by this sequence

Simulating the entire first pass gives a peak of 9 occupied voices and zero
steals with the 16-voice pool. Consequently, increasing
`VOICE_KILL_SETTLE_FRAMES` will not affect that pass. The header's claim that
the piano frequently steals voices is inconsistent with the current data.

## Checks completed

- Reconverted all seven source WAVs in memory using the current converter:
  byte-for-byte match with `assets/TITLE_SMP.RAW`.
- Compared that blob with the sample region in `build/title-screen.bin`
  using its symbol addresses: byte-for-byte match.
- Blob length is 287,679 bytes. Sound RAM placement ends at offset 0x523E7,
  within the 512 KiB capacity. This checks static placement, not runtime
  overwrites.
- Read the player, conversion tools, startup, renderer, local audio notes,
  and relevant Kronos SCSP code.
- Git has no commits and the project files are untracked, so there is no
  committed working version available for regression comparison.

## Driver-source caveat

Upstream source: https://github.com/ponut64/SCSP_poneSound/blob/master/PROJ/main.c

Its looping PCM path does not use `bytes_per_blank`; its current volume
handling also differs from this project's documented 0–7 convention.
Do not change either parameter based on current upstream alone: the bundled
8,732-byte driver has not been matched to an upstream revision.

Bundled `SDRV.BIN` SHA-256:
`340C0BEA107D4319BEEA7BA94E7654F859B281B923A26BB93B75757F02FF9FF5`

## Next diagnostic step

Confirm whether onset is near the second chord or nearer 20 seconds, and
whether the target is Kronos or hardware. For early onset, inspect sound RAM
and active SCSP sample addresses/loop bounds across the first two chords,
and match the bundled driver to source. Preserve the current image for an
A/B comparison; distinguish the proven reuse gap from the unresolved early
noise before making more timing or envelope changes.
