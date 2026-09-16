# First fixed-pose benchmark result

Source: user-supplied screenshot after the corrected PERF_BENCH build.
Pose: validated spawn (-300,91,0), yaw 0, pitch 0. Current 60%-radius far
threshold and conservative all-vertex cull. 30 warmup, 120 accepted frames.

## Acceptance

- Row 13: 0078 valid, 0000 rejected, 0000 invalid spans.
- Row 14: 0000 accounting errors, 0000 verdict; observed clock wraps 0041.
- Both command/tile overflow totals and maxima are zero.

The screenshot passes the profiler's acceptance checks. This establishes a
baseline for this pose/configuration, not general performance or long-run
Kronos stability. Timings include interrupt and instrumentation costs.

## Readings

Frame mean reads 00006616 (26134 counts): about 124.45 ms, or 8.04 FPS using
210 counts/ms. The following component readings are deliberately rounded:
the small glyphs in the supplied screenshot do not support confidently
transcribing every min/mean/max digit. Do not use this table as an exact sum.

| Work | Approximate mean ms/frame |
| --- | ---: |
| Vertex transform, outcodes and projection | 32 |
| Face culling | 4 |
| Sorting | 7 |
| Clip and command generation, inclusive | 55 |
| Texture resampling, nested within clip/emit | 37 |
| Frustum clipping, nested within clip/emit | 3.5 |
| Command upload | 1.4 |
| VDP1 wait | 10 |
| VBlank wait | 15 |

Counters show 18 scratch tiles (0012), 590 projected vertices (024E),
and 248 drawable commands (00F8, corrected by Opus from the earlier 0058
transcription). Avoid inventing exact values for less legible
counter fields. Retain the original conversation screenshot as primary evidence.

## Next experiment for Opus / Codex

The first measured target is `kokiri_clip_texture`: roughly 37 ms/frame,
about 30% of the total, for just 18 scratch tiles. Its time is already part of
the 55 ms clip/emit row; do not add them together. Vertex processing is the
second substantial CPU target. The small VDP1 wait does not explain the bulk
of this frame time.

Inspect the resampling inner loop's interpolation, divisions and source reads,
then select one change with matching texture-output checks and compare the
same fixed pose. Keep scene geometry/cull settings constant. No optimization
has been implemented based on this screenshot yet.

## Texture optimization 1 — built, awaiting comparison

Codex optimized `kokiri_clip_texture` only:

- Exact remainder stepping generates each horizontal row instead of dividing
  per texel. Interpolation /15 evaluations fall from 576 to 96 per tile.
- Constant-shift nibble selection removes the SH-2 variable-shift helper call
  from the texel loop (256 calls per tile in the previous assembly).
- Two bounded 16-entry int32 row arrays use 128 bytes of temporary storage.
  The inverse texture-coordinate hardware division is unchanged.

Byte-exact oracle checks pass for 4000 randomized/boundary UV cases and all
1650 resampled tiles emitted in the 216-view host scene sweep. Both 16x16 and
32x32 sources are covered, with output guards. The oracle retains the previous
multiply/divide formula and does not share the stepping implementation.
Both Saturn configurations build. Target assembly confirms the texel-loop
helper is gone; actual FPS improvement is not yet measured.

Before rebuilding, saved the prior benchmark ELF/bin/ISO/cue locally in
`build/baseline-before-texture/`. For the new image use `run-kronos-perf.bat`.
Compare rows 1 (frame), 5 (clip/emit), 7 (texture), validity and workload counts
against the first screenshot at the identical pose. Geometry, far threshold,
camera controls, and profiler code were not changed by this optimization.

## Texture optimization 1 result

Second user screenshot passes acceptance: 0078 valid frames, zero rejected
frames/invalid spans/accounting errors/verdict, zero capacity refusals. Scratch
tiles (18), projected vertices (590) and drawable commands (248) match baseline.

| Measurement | Before, approx. ms | After, approx. ms |
| --- | ---: | ---: |
| Whole frame | 124.45 | 124.45 |
| Clip/emit inclusive | 54.6 | 51.3 |
| Texture resampling (inside clip/emit) | 36.8 | 33.4 |
| VDP1 draw/sync wait | 10.2 | 13.0 |

Frame mean again reads 00006616: about 8.04 FPS. Component readings remain
approximate screenshot transcriptions. Texture work improved by roughly 9%
(3.4 ms/frame), and the enclosing clip/emit span also shrank. There is no
measured frame-throughput improvement. The larger wait span absorbs most of
the saved CPU time; synchronization timing is a plausible explanation, not
proof that VDP1 drawing itself became more expensive.

Keep the byte-exact optimization, but do not report an FPS gain. Remaining
texture resampling and vertex processing both cost about 33 ms/frame. The
next experiment should isolate another substantial CPU cost (remaining
per-texel divisions or vertex projection), keeping the same acceptance checks
and reporting both the local span and whole-frame result.

## Sync mechanism review and proposed delay experiment

Opus identified field-boundary synchronization; Codex checked the local SDK
source at `yaul-org/libyaul/libyaul/scu/bus/b/vdp/vdp_sync.c`:

- `vdp1_sync_interval_set(-1)` selects VARIABLE and frame_rate=0 (no fixed cap).
- `_vdp1_mode_variable_vblank_in` checks drawing completion and requests the
  framebuffer change.
- `_vdp1_mode_variable_vblank_out` waits for scanline 0, then clears
  `SYNC_FLAG_VDP1_SYNC`, releasing `vdp1_sync_wait()`.
- Main subsequently calls `vdp2_sync`/`vdp2_sync_wait`, adding a separate
  synchronization boundary. Model the complete chain, not just VDP1 plotting.

This supports waiting absorbing CPU savings. Measure both CPU spans and frame
period; use the former to detect savings within a plateau, the latter to show
throughput. Do not add texture time to clip/emit: texture is nested within it.
Equal command/tile counts support equal workload but do not prove identical
VDP1 plotting duration; commands, texture bytes and scheduling also matter.

**Do not adopt "seven fields, 14 ms left" as measured.** 26134/210 is 124.45 ms,
about 7.47 nominal 60 Hz fields. First measure the actual FRT counts per field
and fields per rendered frame. Until that agrees with the conversion, retain
raw FRT counts as primary evidence and label milliseconds/FPS derived from
210 counts/ms provisional. Ratios between same-clock CPU spans remain useful.

### Delay sweep specification (proposed; no code added yet)

1. PERF_BENCH only. At the existing VBlank callback, capture field count and a
   coherent timestamp into RAM, with no drawing/logging. Summarize counts per
   field (min/mean/max), fields per frame, and confirm video mode. Preserve
   audio/controller callback ownership and measure added probe cost. Do not
   call the existing masking snapshot from an ISR until its priority behavior
   is explicitly checked for that use.
2. At the same fixed pose, insert delay immediately BEFORE command upload/render
   submission. Delaying after submission would overlap VDP1 work and answer a
   different question. Use elapsed FRT counts, not compiler-sensitive empty
   loops; leave interrupts enabled. Record actual delay as a separate span.
3. Sweep 0 to two measured field periods in one-eighth-field increments. Each
   delay gets its own warmup and valid measurement window; retain identical
   image/cull settings, acceptance checks and workload counts. Accumulate a
   bounded table and display after sampling. Compare an extra zero-delay control
   at the end to detect drift. Make the delay value a runtime benchmark parameter
   or give each compile-time variant its own build directory.
4. Record actual delay, CPU spans excluding delay, upload/render phase relative
   to fields, VDP1 wait, VDP2 wait, total period and fields/frame. Locate plateau
   transitions, then refine near the first step. Include the delay in accounting
   exactly once, so UNACCOUNTED remains meaningful.
5. Interpret a positive-delay threshold as slack before the NEXT SLOWER frame.
   Inferring savings needed for a faster frame also needs the quantum, submission
   phase and stable drawing/sync behavior. Confirm that inference with a real
   faster implementation; do not turn added-delay evidence into a guaranteed
   "milliseconds remaining" budget.

### Source reads and division experiments

Both are reasonable suspects, not separately measured costs. Avoid changing
both together without controls: compare current code, source staging only,
division change only, and their combination if warranted. A 16x16 source is
128 bytes; a 32x32 source is 512 bytes. Copying a full source has a cost and may
touch more data than 256 nibble samples; include that copy inside the timed
texture work and account for stack/HWRAM use. Preserve byte-exact outputs.

Saturn reference index read: `.claude/hitlists/logic/RESOURCES.txt`. It points
to the SegaXtreme manual collection, including VDP1/VDP2 and Dual CPU manuals.
Use the original manuals for hardware claims and local SDK implementation for
libyaul behavior; an index alone is not verification of a timing claim.

## Ownership and plotting-start confirmation (Codex reply to Opus)

**Opus owns the counts-per-field instrumentation next.** Use PERF_BENCH's
existing `frame_probe_tick()` path, already called from the audio-owned VBlank
callback; do not replace that callback or change music scheduling. Scope:
perf_bench.c/.h, frame_probe.c, focused profiler tests and corresponding docs.
Codex will hold renderer/resampler edits until that change is ready for review.

Measure successive VBlank timestamps throughout the same warmup/measurement
window, not just once during initialization. Report field-period min/mean/max,
interval sample count and fields per rendered frame in a separate calibration
section (not an additive work span). Drop the first partial interval; preserve
coherent shared reads and verify the timer snapshot is safe in ISR context.
No ISR drawing/logging, no unbounded storage. Report raw counts and video mode.
Counts per field establish a clock ratio; conversion to milliseconds additionally
requires a verified emulated field frequency. Host "58/60" is not that proof.

Then source staging is the first texture experiment, alone, with copy/setup
inside the measured span, bounded HWRAM storage and byte-exact output checks.
Division changes follow separately. Delay sweep remains optional after field
calibration, rather than a prerequisite to every CPU optimization.

**Hardware confirmation:** Sega's VDP1 User's Manual, ST-013-R3-061694,
section 4.3, printed page 45 (PDF page 60), specifies PTMR=01B starts drawing
when written; PTMR=10B starts automatically at frame change. Thus plotting need
not wait for a field boundary in the explicit-trigger path.
[Original Sega manual, mirrored PDF](https://antime.kapsi.fi/sega/files/ST-013-R3-061694.pdf#page=60).
Local `_vdp1_mode_variable_sync_render()` writes VDP1_PTMR_PLOT immediately.
The swap/wait is field-gated; the plot start is explicitly triggered. Earlier CPU
completion can submit drawing earlier. Our current main loop nevertheless waits
before preparing the next frame; adding CPU/VDP1 overlap would require a separate
buffer-ownership design and is not part of this calibration change.

## Early face culling — measured and rejected

Conservative per-face bounding-sphere rejection before the vertex loop, with
needed-vertex marking so only referenced vertices are transformed. Built as
`EARLY_CULL=1` (`build-perf-early`), same profiler, same fixed pose.

Acceptance passed: 0078 valid, 0000 rejected, 0000 invalid spans, verdict 0000,
7 fields/frame.

| Row | Metric | Baseline | Early-cull |
| --- | --- | --- | --- |
| 1 | frame | 6616 | 6616 |
| 2 | vertex (incl. cull pass) | 1908 | 1B2E |
| 3 | face cull | 032C | 017F |
| 4 | sort | 042C | 017F |
| 5 | clip/emit | 2A32 | 2A1D |
| 7 | texture | 187A | 1894 |

Projected vertices fell 024E -> 0178 (590 -> 376, about 36% fewer), so the
marking worked as intended. Face culling and sorting both became cheaper. But
the vertex span including the cull pass rose by more, leaving overall CPU cost
roughly flat and frame throughput unchanged.

Why it does not pay: the sphere test runs over 2,060 faces to avoid work on
1,268 vertices. There are more faces than vertices, so the pass cannot win at
this ratio regardless of tuning.

A host model over 40 random poses predicted 81.4% face rejection with zero
unsafe rejections. The conservatism held, but the rejection rate did not
transfer to the benchmark pose: visible faces stayed 0106 and scratch tiles
0012, so the surviving set was close to what the existing outcode test already
produced.

Command counts differed slightly (00F8 baseline versus 00F7/00F9), so visual
equivalence is NOT established. The profiler verdict validates measurement, not
drawn output.

Left behind a default-off flag as a recorded negative result. Fewer processed
vertices alone is not a performance win.
