# Audio hitlist

Status snapshot for the title-screen audio work. See `README.md` in this
folder for how any of this works or why a fix was needed.

## Done, confirmed by ear (2026-09-15)

- [x] Ponesound driver boots and plays a static test tone (isolated the
      "no sound at all" bug down to a missing post-`SNDON` boot delay).
- [x] Real `NA_BGM_TITLE` sequence extracted from the decomp (not a
      pre-render) and played by a live SH2 sequencer over a 16-voice pool.
- [x] All 7 Soundfont 6 samples converted and resident in sound RAM
      (≈281 KB / 512 KB).
- [x] Signed-short pitchword overflow fixed (was corrupting ~45% of notes).
- [x] z64→MIDI note conversion fixed (was applied to range bounds but not
      to the actual per-note pitch value).
- [x] `bytes_per_blank` native-vs-transposed-rate bug fixed (was reading
      into neighbouring samples in the packed blob under transposition).
- [x] Channel volume automation applied (was previously ignored; the two
      `vol 127` "piano" channels drowned everything else).
- [x] Volume range corrected to the driver's real 0-7 (was sending 0-15).
- [x] Pan mapped to SCSP's attenuation convention (was collapsing centre to
      hard-left).
- [x] `gate` semantics corrected — it's a release fraction of `delay`, not
      a duration (notes were sounding roughly half as long as they should).
- [x] `notedv` gate-inheritance bug fixed (should zero gate, was carrying
      the previous note's).
- [x] Struck-instrument envelope decay approximated (linear fade over the
      soundfont's own envelope tick counts) — user-confirmed as the fix for
      "piano sounds like an air horn."
- [x] Note-off click/pop fixed via a short release ramp + smarter voice
      stealing (prefers mid-release/quietest voices over "soonest to end").
- [x] Timing cross-checked against a user-supplied fan MIDI — within 1% in
      real seconds once tempo/ticks-per-quarter differences are accounted
      for; confirmed no note is truncated at the loop seam.

User-confirmed state as of the last playtest: **"incredibly faithful
overall,"** popping resolved, volume balanced correctly.

## Open / not yet addressed

- [ ] **Real hardware playback unverified.** Everything so far is
      Kronos-only. Ponesound's actual M68K driver behavior, SCSP pan
      polarity, and general audio timing should be re-confirmed on the ODE
      once available — emulator agreement is not hardware agreement (see
      the project's general hitlist/README for this principle elsewhere in
      the repo).
- [ ] **Pan direction unconfirmed.** Derived from struct field comments
      only, no driver source. Low cost to fix (flip one branch in
      `_pan_to_dipan`) once it can actually be heard on hardware in stereo.
- [ ] **Envelope model is a linear approximation**, not the soundfont's real
      3-point envelope. Fine for this track; revisit if a future track's
      dynamics don't hold up under the simplification.
- [ ] **Velocity is linear, not velocity-squared** (`SQ(velocity)/SQ(127)`
      per the real engine). Currently sounds correct without it — flagged
      in case a future track's dynamic range feels off and this turns out
      to matter after all.
- [ ] **Intro pad replays every loop lap** instead of playing once at
      power-on. Inaudible in practice at a ~78s loop; would need player-side
      state (a one-shot-then-loop mode) to do properly. Not worth it unless
      it becomes audible on hardware for some reason.
- [ ] **Only one track is wired up.** The whole pipeline (`make_title_
      samples.py` / `make_title_sequence.py` / `title_player.c`) is
      currently hardcoded to Sequence 30 / Soundfont 6. Extending to other
      BGM tracks means at minimum: generalizing the soundfont-sample
      extraction beyond one font, and checking whether other sequences use
      aseq opcodes this converter doesn't yet handle (loops, conditional
      branches, `dyncall`/`dyntbl` — seq_30 uses none of these, so they're
      entirely unimplemented, not just untested).
- [ ] **No SFX playback path.** This is BGM-sequencer-only; the OoT sound
      effects the user also extracted (same WAV dump, non-`BANK_06_INSTR_`
      files, drums/percussion included) aren't part of this pipeline at
      all.
