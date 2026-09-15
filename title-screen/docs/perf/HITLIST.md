# Performance hitlist

Working list for the 4-10 FPS problem. Ordered by payoff per unit of risk, not
by how interesting the change is.

## Status of the numbers

The 7 FPS figure came from the frame/tick counters in
[`frame_probe.c`](../../src/debug/frame_probe.c): `frames` increments per
completed render, `ticks` per VBlank-in. Frames divided by ticks, times 60, is
the frame rate. That part is real.

Per-stage timing now exists (item 0), but **its readings are historical and
confounded - see the warning on the run table below.** The split between CPU
time and VDP1 draw/wait time is still not established. No item in this
document is currently supported by a valid measurement of its own cost; the
rankings below come from reading the code.

A corrected instrument now exists: build with `make PERF_BENCH=1` for a
fixed-pose profiler (validated spawn, no auto-rotation, no drawing inside the
measured window, 120 frames after warmup, min/mean/max per span plus geometry
counters). See [PLAN.md](PLAN.md) for usage, the display layout, the agreed
design, and the review that invalidated the first round of numbers.

**No baseline has been captured with it yet.** Do not optimize against the
figures below.

## 0. Measure the stage split

**Implemented.** `frame_probe_time_init()` calls `cpu_frt_init(CPU_FRT_CLOCK_DIV_128)`
once from `user_init()` in [`main.c`](../../src/main.c). Every
`frame_probe_stage()` call now also timestamps itself via
`cpu_frt_count_get()`; [`frame_probe.c`](../../src/debug/frame_probe.c) keeps a
fixed ring of the stage ids that fire each frame and, on each call, displays
the FRT delta since the previous one as a 4-digit hex value.

Two new stage markers were added to get the segments the table below needs:
`0x48` in [`kokiri_scene.c`](../../src/scene/kokiri_scene.c) between
`sort_faces()` and the clip/emit loop, and `0x78` right after
`vdp1_sync_wait()`.

On screen (row 0 is the existing stage/frames/ticks/EDSR/COPR readout, which
is unchanged):

| Row | Column (left to right) | Segment | Stage ids |
| --- | --- | --- | --- |
| 1 | 1 | Title input + press-start blink | 0x10 -> 0x20 |
| 1 | 2 | Camera update | 0x20 -> 0x30 |
| 1 | 3 | Vertex transform + outcode + cull | 0x30 -> 0x40 |
| 1 | 4 | Face sort | 0x40 -> 0x48 |
| 1 | 5 | Clip + command emit | 0x48 -> 0x50 |
| 2 | 1 | Command list upload | 0x50 -> 0x60 |
| 2 | 2 | VDP1 render issue | 0x60 -> 0x70 |
| 2 | 3 | VDP1 draw + wait | 0x70 -> 0x78 |
| 2 | 4 | Tail of draw call | 0x78 -> 0x80 |
| 2 | 5 | VBlank wait (`vdp2_sync`/`_wait`) into next frame | 0x80 -> next 0x10 |

Values are raw DIV_128 FRT counts, not milliseconds. `CPU_FRT_NTSC_320_128_COUNT_1MS`
(0x00D2 = 210) is the conversion: `ms = count / 210`. A 7 FPS frame is about
143 ms, i.e. roughly 30000 counts (0x7530) spread across all ten segments -
comfortably inside the 16-bit counter's ~312 ms wraparound span, so no segment
can overflow on its own.

Read the values with [`run-kronos.bat`](../../run-kronos.bat) and the title
still visible (the probe writes into NBG0's own bitmap, so hiding the title
also hides the readout).

**Results: HISTORICAL ONLY - NOT VALID FOR BEFORE/AFTER COMPARISON.**

The raw counts are preserved below as a record of what was observed. Every
conclusion drawn from them has been withdrawn. Two independent confounds:

1. **Runs B and C rendered from a broken camera.** Removing forced `DEBUG`
   deleted the `assert(kokiri_collision_spawn(&camera))` expression, so B and C
   spawned at `(0,0,0)` inside ground collision. Run A executed spawn. The
   three runs are not the same scene, let alone the same pose.
2. **Single frames off an auto-rotating camera.** Visible face count swings
   with view direction, so run-to-run deltas are dominated by camera angle.

Additional defects in the instrument itself: the timed spans include the
probe's own drawing and interrupt time, the 16-bit FRT wraps at about 312 ms
(a hang yields a plausible-looking wrong number), and a screenshot can mix
values from adjacent frames because each segment updates as its own marker
executes.

Raw hex counts, row 1 then row 2, in on-screen column order:

| Run | Row 1 (segments 1-5) | Row 2 (segments 6-10) | Total counts | ~ms | Kronos VDP1 FPS |
| --- | --- | --- | --- | --- | --- |
| A: baseline (DEBUG forced on, no draw distance) | `0002 0002 203A 06A3 2C45` | `0235 0002 0E10 0002 00F0` | 25695 | 122 | 09 |
| B: item 1 done (DEBUG off) | `00D1 00D2 1FE4 0597 27AC` | `00F4 00D2 0680 00D3 0DFB` | 26078 | 124 | 08 |
| C: item 2 done, far_z = 100% radius | `0001 0002 2083 0CA6 2940` | `0112 0001 08E0 0002 0DF0` | 28241 | 134 | 07 |

**Withdrawn conclusions.** These were previously stated as findings and are
now retracted:

- that clip+emit and transform are established as the two dominant costs;
- that the frame is roughly 90% CPU-bound and VDP1 is therefore a minor cost;
- that segment 3 is fixed cost proven unreachable by draw distance;
- any per-vertex cycle figure (the earlier ~880 used the 352-mode 28.6 MHz
  clock; the FRT constant in use implies 26.88 MHz, so ~824 - and it rests on
  a void baseline regardless).

They may well turn out to be true. They are not established by the table
above. Re-derive them from the `PERF_BENCH` baseline.

Run C used `far_z = scene->radius` (100%), then was retuned to 30%. That cut
made nearby floor polygons disappear because whole triangles were rejected by
their average depth. The current correction uses 60% and rejects or fades only
triangles whose three vertices are all beyond the threshold. No segment reading
has been taken yet at the corrected 60% setting.

## 1. Stop shipping assertions

**Regression correction:** removing DEBUG also removed the entire
`assert(kokiri_collision_spawn(&camera))` expression. The release scene started
at `(0,0,0)` inside ground collision, explaining stuck movement and the floor
view. Spawn now runs outside assert with an explicit failure check. Earlier
floor diagnoses based only on distance culling missed this confirmed cause.

**Done.** The forced `#define DEBUG 1` at the top of
[`kokiri_scene.c`](../../src/scene/kokiri_scene.c) is removed (pass `DEBUG=1`
on the `make` command line if the crash asserts are needed again). One
load-time-only local (`width` in the face-validation loop, used solely inside
an `assert`) needed `__unused` to stop warning once `assert` compiled away.

It kept `assert(count < COMMAND_CAPACITY-1)` live inside the per-command emit
loop and turned on libyaul internal bounds checks in the `vdp1_cmdt_*` setters
and VRAM writes - on the hottest path in the renderer.

**Measured effect: unknown. The earlier claim is withdrawn.** Run A -> B was
previously read as a small win concentrated on VDP1 wait (segment 8
0x0E10 -> 0x0680). That comparison is void: run B also spawned at `(0,0,0)`
inside collision because this very change deleted the spawn call, so A and B
are different scenes. No speedup from disabling `DEBUG` has been demonstrated.
Re-measure under `PERF_BENCH` with the spawn fix in place.

**Caveat, and it is a real one.** Those asserts were added for the unresolved
intermittent SH-2 invalid-opcode crash that [DEBUGGING.md](../DEBUGGING.md)
tracks, and stability is still unproven. Disabling `DEBUG` speeds the renderer
up *and* removes the diagnostics that would explain the next crash - if it
recurs now, there is no assert trail to point at it. Watch for it.

## 2. Draw distance + dithered fog

**Done and corrected**, in [`kokiri_scene.c`](../../src/scene/kokiri_scene.c). Two new
statics, `far_z` and `fade_z`, set in `kokiri_scene_init()` from
`scene->radius`:

```c
far_z = (int32_t)scene->radius * 6 / 10;
fade_z = far_z - far_z / 4;                /* dither starts at 75% of far_z */
```

**Z reject**: a face is dropped only when all three vertices exceed `far_z`.
Testing average depth was wrong for large floor triangles that reach from under
the camera into the distance.

**Fade dither**: a face is distance-dithered only when all three vertices exceed
`fade_z`, preserving the near portion of large polygons.

**Tuning history:** started at 100%, then moved to 30%. Visual testing showed
30% was too short and exposed the whole-triangle average-depth bug. It is now
60%, with conservative all-vertex tests. Re-measure and tune by eye from here.

## 3. Fold pitch into the rotation matrix

Lines 162-163 of the transform loop:

```c
int32_t py = (int32_t)(((int64_t)y*pc - (int64_t)z*ps)/65536);
int32_t pz = (int32_t)(((int64_t)z*pc + (int64_t)y*ps)/65536);
```

**Rationale corrected - the original justification was false.** This entry
previously claimed SH-2 has no 64-bit multiply and that each of these is a
libgcc call. Wrong. The generated assembly for this file contains `dmuls.l`
(the SH-2 32x32 -> 64 signed multiply) and **zero** `__muldi3`/`__divdi3`
references; the `/65536` becomes shift and `xtrct` sequences. Verified by
grepping `build/*kokiri_scene.s`.

What composing pitch into the `fix16_mat33_t` (built one line above via
`fix16_mat33_y_rotation_create`) actually saves is 4 `dmuls.l` plus their
sign-correction and shift sequences per vertex, folded into the
`fix16_mat33_vec3_mul` already being called. A modest per-vertex saving, not
hundreds of cycles.

**Not pixel-identical, contrary to the earlier claim.** The current code
rounds yaw-transformed coordinates to int32 *before* applying pitch;
composition moves where rounding happens. Expect small coordinate and
projection differences, and check clipping boundaries specifically.

Re-justify against the `PERF_BENCH` baseline before implementing.

## 4. Cheaper outcodes

`kokiri_clip_outcode` runs five `plane_distance` calls per vertex, each with two
multiplies, across all 1,268 vertices - before any face has been rejected.

Options, cheapest first:

- Skip outcode work entirely for vertices already past the item-2 far plane.
- Hoist the near-plane test (`plane == 0` is a bare compare) and skip the four
  multiply-heavy side planes for vertices that fail near-Z anyway.
- The side-plane constants (240, 160, 159, 120, 119) are fixed; these can be
  shifts and adds rather than general multiplies.

## 5. Replace the per-frame shell sort

`sort_faces` shell-sorts up to ~2,060 entries every frame with a data-dependent
number of passes. The sort only approximates painter order - exact ordering is
not required, and is not achieved anyway, since per-face depth is the sum of
three vertex depths.

Bucket by depth into a fixed number of bins and concatenate: one pass, no
comparisons, bounded work. Accuracy is comparable for this scene.

Pairs well with item 2 - the far plane also shrinks the input to the sort.

## 6. Put the slave SH-2 to work

The second 28 MHz SH-2 is entirely idle. With no AI, no NPCs and no player
character competing for it, the headroom is free, which makes this the largest
single CPU win available.

The vertex transform loop is the natural candidate: a flat, independent map over
`vertices[]` into `view[]`, `depths[]` and `projected[]`, with no cross-vertex
dependency. Split the range in half, run both, join before the face loop.
`cpu_dual_slave_set` / `cpu_dual_slave_notify` are the libyaul entry points.

Constraints to respect: the slave needs its own stack (`IP_SLAVE_STACK_ADDR` is
already `0x06001E00` in the Makefile).

**Corrected:** an earlier version of this entry claimed the hardware divider is
a single shared unit that only one CPU may own at a time. That is wrong. The
`cpu_divu_*` functions address DIVU through `CPU_IOREG_BASE`, the SH-2 on-chip
peripheral space, which is per-CPU - the same mechanism as the FRT, which
libyaul documents as initializing on either master or slave. Each CPU has its
own divider. The constraint does not exist; do not design around it.

## 7. Merge coplanar triangle pairs into quads

This is the item that started the discussion, and the framing needs correcting:
**the geometry is already quads.** `tools/build_kokiri_scene.py` line 327 packs
`*ids, ids[2]` - the fourth vertex duplicates the third. VDP1 has no triangle
primitive; it only draws quads, so every triangle already ships as a degenerate
four-corner distorted sprite. There is no per-primitive overhead left to remove
by "converting triangles to quads."

The genuine win is different and larger: merge *coplanar triangle pairs* into
single real quads, halving command count and VDP1 setup for the merged faces.

The obstacle is texturing. The A/B/C/C tile scheme bakes per-triangle UVs
(`kokiri_clip_texture` maps `b = u*(1-v)`, `c = v` over a triangle), and a
merged quad needs a coherent four-corner UV instead. That is a host-side
converter change plus a renderer change to the UV path - real work, real
payoff, but not a quick fix, which is why it sits below the cheap items.

Do this after item 0 has confirmed VDP1 is actually a bottleneck. If the frame
is CPU-bound, halving VDP1 commands buys much less than it looks like it should.

## 8. Overlap CPU and VDP1

End of `kokiri_scene_update_and_draw`:

```c
vdp1_sync_render();
frame_probe_stage(0x70);
vdp1_sync();
vdp1_sync_wait();
```

This fully serializes the two processors: the SH-2 idles while VDP1 draws, then
VDP1 idles while the SH-2 transforms the next frame. Double-buffering the
command list would overlap them, and if item 0 shows both stages are
substantial, the theoretical gain approaches the smaller of the two.

**Last on the list deliberately.** The comment at lines 122-126 records that
`vdp1_sync_interval_set(-1)` and this explicit serialization were chosen
*because* AUTO mode restarts plotting each field without waiting for draw
completion, which raced the command and clipped-texture updates. Reintroducing
overlap reintroduces exactly that class of race, against an intermittent crash
that is still unexplained. Touch this only with stability established and the
profile in hand.

## Correctness bug found while reading (not a perf item)

[`kokiri_scene.c`](../../src/scene/kokiri_scene.c) line 213, in the fast path:

```c
if (safe) p[j] = projected[face->vertices[j]].p;
```

`j` runs 0..3 over the *clipped polygon*, but indexes `face->vertices[j]` - the
*original face* - and ignores `first` entirely. It is correct today only by
coincidence: `safe` implies `n == 3`, so the loop runs once with `first == 1`,
and `face->vertices[3]` happens to equal `ids[2]` because the converter
duplicates the third vertex. Any change that lets a `safe` polygon carry more
than three vertices - including several items above - will silently produce
wrong geometry.

Fix this before starting items 2-7, independently of any optimization.

## Suggested order

~~0 (measure)~~ done -> bug fix above -> ~~1~~ done -> ~~2~~ done -> 3 -> 4 -> 5 -> 6 -> 7 -> 8

**Not done yet:** everything from item 3 onward. The line-213 safe-path index
bug is fixed. Segments 3 (transform) and 5 (clip+emit) are still the two largest by
a wide margin in every run so far - that is what makes 3 and 4 the next real
targets, ahead of the sort/slave-CPU/quad-merge/overlap items further down.

Re-measure after each. The point of item 0 is to stop guessing; if the profile
contradicts this ordering, follow the profile.
