# Claude Opus: floor covering Link. Exact handoff.

2026-09-18. User says stop experiments, restore textures, tell Claude what to do.
Overlap NOT fixed. Do not call any prototype below a working fix.

## Current user instruction

Restore original floor/water texture sampling. Keep original N64 primitive tint
and cutout alpha. Stop flat-shading workaround. Fix wrong visibility separately.
Use user's running Kronos as acceptance reference. No focus steal, global input,
desktop capture, closing user emulator, or silent disc replacement.

Normal build now excludes command-order prototype behind
`DOSEI_ACTOR_ORDER_PROBE` (undefined by default). No build option enables it.
Flat-colour helper remains parked: only explicit per-group `flat_shaded=True`
enables it. Normal imported groups do not set this flag.
Room streaming remains optional/unaccepted; default `STREAM_ROOMS=0`.

Root `game/build/game.iso` and `game-clean.iso` rebuild from restored textured
path. Build logs under `workspace/warp-audit/textures-restored*-build.log`.
Both rebuilds completed successfully. No probe defines in compile logs; actor
repair symbols absent from both maps. Normal RAM gap6032 bytes; clean8592 bytes.
Generated manifest has zero flat-shaded faces.
Old isolated discs under `workspace/warp-audit/game/build/` may still contain
failed experiments. Do not give those to user as a fix.

## Proven cause of failed fixes

SGL queues world and Link into one depth-sorted command list. Submitting Link
after world does NOT mean Link draws last. Original `SORT_CEN` uses one depth
per polygon; a large floor can paint across a nearer body part.

Exact bad reference:

- Camera `(651,71,234)`, yaw `17174`, pitch `-1820`.
- Link collision eye `(773,90,224)`, feet `(773,0,224)`, facing `50873`.
- Source face 497 contains feet origin.
- Adjacent opaque face 462 misses that origin by only **2.969 world units**.
- Translucent quad `[566,567]` misses origin by only **7.687 world units**.
- Posed body extends beyond that origin. Bind-pose footprint roughly
  X `760.5..785.7`, Z `207.9..240.3`.

Bad decal already a genuine convex quad:

```
(666,0,255), (707,0,399), (851,0,370), (814,0,223)
```

Its plane below Link; camera 71 units above. Quad conversion cannot alone fix
this example. Origin-in-floor test misses neighbouring faces crossing boots.

Evidence in ignored `workspace/warp-audit/`:

- `exact-before.png`: floor hides legs/boots.
- `floor-order-after.png`: broad floor `SORT_MAX` exposes boots, but changes
  water/rock ordering. Rejected as general fix.
- `floor-support-1.png`: origin-only `SORT_MAX` still cuts boot. Rejected.
- `flat-floor-check.png`: flat colour stops pattern warp, not overlap.
- `actor-order-diagnostic.png`: new prototype reports `moved 0`, `blocked 8`,
  `order error 500`. It did NOT repair this view.

Flat-colour experiment also erased decal cutouts at first. Source `[566,567]`
has **1654/4096 texels with alpha <64**. Forcing alpha255 made a whole checker
sheet. That regression was repaired, then default texture sampling restored.
Do not confuse restored alpha with solved polygon visibility.

## Parked prototype: what is actually implemented

Files:

- `src/actor_order.h`: tested monotone actor insertion-interval solver.
- `src/sgl_order_queue.h`: tested SGL 3.02j queue collector/rebuilder.
- `src/scene_actor_order.h`: UNACCEPTED runtime glue. Actual bad view fails.
- `tests/test_actor_order.py`, `tests/test_sgl_order_queue.py`: solver/queue tests.

Intended rule: keep every world/world pair and every Link/Link pair in original
order. Move only actor commands into legal slots among unchanged world commands.
Use emitted screen polygons for overlap and original world planes for side tests.
Same plane side as camera => world before actor. Opposite side => actor before
world. Ambiguous/intersecting pairs keep original relative order.

For actor command i and world rank j:

```
world before actor: lo[i] = max(lo[i], j+1)
actor before world: hi[i] = min(hi[i], j)
require nondecreasing actor insertion slots in [lo[i], hi[i]]
```

Solver validates whole solution before writing. If impossible, preserves original
queue. Error **500** means insertion constraints infeasible, not failed queue
discovery. Live test confirms callback reaches solver, but moves zero commands.
Reason for conflicting constraints NOT established yet. Coplanar soles retaining
wrong original order is a hypothesis, not a proven diagnosis.

SDK facts verified by local LIBSGL disassembly:

- Work-RAM command 36 bytes; GRDA at28, depth key at30, next pointer at32.
- With no Gouraud/light, ATTR.gstb copies raw into GRDA. Prototype tags world
  face i as i+1; Link face i as `0x8000 | (i+1)`.
- Queue callback through `slSlaveFunc` after Link submission runs FIFO after
  geometry, before `slSynch` builds DMA table.
- Keep queue accesses on same aliases SGL slave uses. Master-written context
  uses cache-through alias. Do not patch VDP1 VRAM while it draws.
- Sort heads:128 per window, then256 scratch. Equal-depth tie order matters;
  adapter reproduces two radix prepends. Rebuild validates exact membership.
- `slDispPolygon` is not a depth-override shortcut; its path is orthographic.

Known gaps / risks:

- Runtime glue still lacks completed host integration test. Pure helper tests
  do not prove actual projection, clipping, tag mapping, or callback correctness.
- SAT assumes convex emitted quads. Need convexity guard/conservative fallback.
- Plane test uses rounded geometry. Added planarity guard and below-feet guard
  for tiny two-unit floor-contact tolerance; tolerance remains approximation.
- Untagged fairies keep world order, but relation to moved Link is not constrained.
- Guards missing for world Gouraud/light if future asset modes change.
- Last flat-texture diagnostic `.bss` had only2864 bytes margin. Restoring full
  textures PLUS enabling these scratch buffers likely exceeds budget. Prototype
  disabled in normal builds for correctness and memory. Measure before enabling.
- Actual target frame cost of successful correction unknown: zero moved so far.

## What Claude must do next

1. Verify textured normal build and preserve it. Do not start by changing art,
   clipping, tessellation, controls, or room loading again.
2. Reproduce exact bad pose, then real walk/turn/jump. Confirm loaded image and
   source/generated-asset provenance. Background capture only.
3. Instrument first error500: record actor tag, conflicting `lo`/`hi`, both world
   tags/ranks, screen corners, signed plane distances, contact/ambiguity branch,
   and original slots. Map tags through current partitioned polygons back to
   manifest source IDs. Do not guess from tile ID alone; tiles are shared.
4. Save that actual command/geometry snapshot as a host integration fixture.
   Prove why the constraints conflict. Fix that exact case without discarding
   real front-wall/overhead constraints or changing world order casually.
5. If preserving world order makes a real visibility cycle impossible, report
   it. Correct solution then needs bounded geometry splitting/local reordering
   with proven constraints, not "Link always on top" or ignored safety checks.
6. Test adjacent floor, decal quad, boot contacts, slopes, jump/landing, wall in
   front, bridge overhead, water/cliff edges, and stationary-camera animation.
   Compare identical views and movement; check missing floor and refusal counters.
7. Measure RAM, command count, VRAM, and real moving frame time. Only promote
   normal no-probe images after visual acceptance. No auto-commit.

Latest restored-source host suite:224 discovered,223 passed,1 skipped
(generated room-bank test). This is NOT visual acceptance of overlap repair.
