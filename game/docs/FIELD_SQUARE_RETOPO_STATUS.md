# Field square retopology: implementation status

## Current Clean promotion (2026-10-05)

Human requested the accepted central quads in Clean and wider Field coverage.
Selection is now `field-square-184`. `field_ground_grid.py` adds visual-only
1280-unit panels across large gently sloped outer ground; smaller faces, steep
walls, retained landmarks and the accepted central patch/fans stay separate.
152 outer source groups become 644 panels. UV/material boundaries and source
planes stay; integer rounding is at most half a unit per coordinate. Original
outer collision remains authoritative; central STM/COL/OOC pairing is unchanged.
These are clipped XZ cells, not a claim of exact in-plane squares everywhere.

512/768/896/1024 trials exceeded combined Link/owl/table limits. 1280 passes:
1249 Field polygons, 1732 vertices, 61 resident pieces, 1255 texture slots,
331776/445432 bytes including actor/effect reserves after the full asset bake.
Preflight used 331872 B with older actor tiles. Final report:
`build/generated/field_stream_report.json`; build: `build/field-clean-link-final.log`.
Latest Clean follow-up passes, .bss0x06083DA0, 608 B below SGL
(`build/field-orbit-fix.log`). Two Link-centred dither panels add6 vertices and
2 polygons; combined Field/Link/owl/haze fits2424/2500 vertices and2475/2600
polygons. Dark sky is human-accepted; new band's look remains unverified.
Cached sky helpers use
Os/shared colour mixing to fit; heaps and actor capacities are preserved.
47 focused host checks pass. ISO Field/COL/OOC/program bytes match staging;
all CUE tracks exist. Integer-only sky helper disassembly is inspected.
Human still checks seams, near/far transitions,
texture stretching and runtime cost. Fine 184-unit cells across the entire map
do not fit current limits; full uniform-density conversion remains unfinished.

## Earlier isolated evidence

Claude, 2026-10-05. Implements [FIELD_SQUARE_RETOPO_PLAN.md](FIELD_SQUARE_RETOPO_PLAN.md)
offline and in isolated images. Kept in its own file because Astra was editing
the plan at the same time. Includes the fixes for Astra's collision review
(node branch, normal quantization, curb seams).

**Astra runtime update:** both original images failed to allocate their complete
SAR0.STM contiguously. The loader now reads identical geometry and pixels into
two bounded allocations. Four loader host tests plus eight stream and one music
CD test pass. Both WSL rebuilds pass; new SGL margin is 9152 B. Original images
are saved under each run's `before-loader-fix/`.

184 loaded and completed the matched poses and the extended boundary walks
(x=0, z3500 north past7100; z6500 south past2800). Two 90-step walks took 5.781 s
versus saved P3 4.735 s and TR 7.265-7.312 s. These are emulator wall times.
The human reports most ground looks good, with remaining stretch near z7067.
256 loaded and captured all eleven poses, then the human closed the emulator
near the last northbound leg (confirmed; not a crash). The resumed run completed
both full boundary walks. Two 256 90-step walks took 5.657/5.703 s; static render
was 29.19/29.33 frames/s. Evidence: `r2-256/verification/r2-256-loader-boundary/`
and `r2-256/verification/r2-256-loader-v1/performance.json`.
No all-route hole/seam claim. Usual Clean/Debug, original TR checkpoint and main
layout selection remain unchanged. 184 loader-only image is additionally saved
in `before-clock/` while source clock integration is built separately.

The human's latest feedback accepts the central patch's appearance ("VERY nice").
The reported north stretch at (6,67,7067) is source1029/obj23; the castle approach
at (0,0,2940) is the shared edge of sources602/612. These remain outside the patch.
The good (0,181,6178) view is on patched sources743/744. Acceptance is local,
not a claim that every Field face, wall, collision boundary or performance cost
has been accepted. Extension pricing is offline only; no extra geometry built.

## Geometry

**Patch.** Visual sources 738-746 (the obj17 fan) and 613 (obj13) are
collision polys 589-597 and 436. Vertex sets and winding match exactly. All of
them are surface 5, ignore 0, conveyor 0. Bound: 10 source faces (limit 16),
with no distant growth.

**Panels.** The panels are the ten source triangles themselves. Heights, LOD2
sampling and the coplanar road overlays therefore keep their planes. The
largest distance of a new vertex from its source plane is 0.56 units (integer
rounding).

**Topology: one shared XZ square grid, clipped at the ridges.**
- **Grid placement.** A grid vertex sits on the fan centre (0,5100). Grid
  columns lie on the x = 0 and x = ±1472 ridges.
- **Cells.** A cell wholly inside one panel is one planar quad. Its XZ
  footprint is an exact grid square; on the slope it is a parallelogram.
- **Not true squares.** Measured at 184: sides differ by up to 4.4% and
  corners are up to 4.3° off 90°. This does **not** meet the plan's in-plane
  square criterion. Exact squares cannot share a grid across differently
  sloped panels. A panel sloping in both X and Z cannot hold axis-aligned
  in-plane squares that meet the next panel; see the rejected attempt below.
  The human now accepts the central patch's appearance; this does not change
  the measured distinction between true in-plane squares and near-squares.
- **Snapping.** Grid vertices within 0.2 cell of a ridge or corner snap onto it,
  so no needles form.
- **Shared vertices.** Vertices are keyed by integer XZ. Result: 0 T-junctions
  inside the patch, and the area equals the source within rounding.

**Outline.**
- Grid crossings on the outline are replaced by points about 425 apart. The
  points include the curb lip vertex (1472,400,4330) that already sat on the
  edge.
- The strip next to the outline is re-triangulated.
- Every outside face on the outline, or collinear with it, is fanned to the
  same points in its own plane with its own UVs and flags (visual only):
  - six ground faces;
  - the curb risers 748 and 750;
  - the walls 782 and 1039;
  - two decal or partner faces.
- Ground fans keep angles of at least about 5.5°. The fans of the thin curb
  and wall strips go down to 0.33°; those faces are 40-unit-tall strips 1700
  long already.
- Collision outside the patch is untouched.

**Rejected first attempt.** Exact squares in each panel's own plane, aligned
to one edge. Every fan spoke forced ragged seams: at 256 only 48 of 224 pieces
were squares, and the outside fans had needles of 0.5°. Evidence is in
`build/square-retopo/preview/rejected-per-plane/`.

## Prices

From `tools/field_retopo.py`; outputs in `build/square-retopo/preview/`
(`top-*.png`, `view-*.png`, `geometry.json`, `budget.json`).

| Cell | Squares / ridge cuts / band | Net visual faces | SA.COL tris (max 2321) | Worst tri angle |
|---|---|---:|---:|---:|
| 368 | 11 / 52 / 43 | +128 | 1747 | 20.0° |
| 256 | 49 / 100 / 50 | +221 | 1897 | 11.1° (1 listed) |
| **184** | 125 / 152 / 64 | +363 | 2139 | 2.8° (3 listed) |
| 128 | 340 / 233 / 112 | +707 | 2741: **over the cap** | 2.2° |

The plan's hypothesis was 128. It does not fit the collision bank, so 184,
the nearest size that fits, is primary, and 256 is the cheaper fallback.

**Depth at Astra's six recorded SGL matrices** (focal 240, measured from the
captures):
- **Original faces.** Most cross the near plane. Near-crossing area at the
  close and walk poses: 44,000-60,000 px of the 76,800-px screen.
- **184.** Median far/near depth 1.22-1.97. Near-crossing area 0-19,700 px.
- **256.** Median 1.29-2.39. Near-crossing area 0-24,500 px.
- **Caveat.** Screen area is a risk measure, not proof of holes.

## Real bake

`--budget` runs the production convert, pieces and sweep for both normal and
owl modes.

| | Worst polys / verts | Slots | VRAM of 445,432 |
|---|---|---:|---:|
| baseline | 721 / 1157 | 717 | 268,000 |
| 256 | 858 / 1299 | 888 | 316,256 |
| 184 | 993 / 1440 | 1003 | 334,272 |

**Freeze check.** Every STM face was compared (corners, attributes, texels)
across all 116 pieces. The only differences are:
- the 10 patch faces;
- the 12 fanned faces, 6 of which had been rejoined into quads with a partner;
- those 6 partners, now drawn alone at the parent's tile density;
- the new faces.

Unrelated faces: 0. LOD2 pieces are unchanged.

**Piece assignment.** New faces belong to the cell they lie in, not their
parent's cell. The sweep covers that.

**Tiles.** Square power-of-two tiles at 1.5 px or more per source texel (16×16
for 184 cells). They sample each parent's own UV mapping, so the grass texture
and the 613/746 UV seam are kept. Retopo faces keep the parent's far-floor sort
0x66.

## Collision

**Shape.** The collision uses the same welded integer surface: each quad is two
triangles split on its 0-2 diagonal. Replaced polys keep their slots; the rest
are appended.

**Normals.** One rule, used by both backends:
- the Q15 normal comes from the integer triangle;
- SA.COL stores round(q15/2);
- SA.OOC gets q15 exactly through COLPOLY_SNORMAL literals;
- dist comes from the Q15 normal.

A host test decodes both outputs, checking slots, vertices and the normal rule.

**Node pool.** Field BgCheck takes the **spot** branch (0xF000, 16x4x16); the
earlier "0xB798" label was wrong. Capacity is computed from Saturn sizeof values
(sh-elf g++, target flags):
- CollisionContext 8068 B;
- StaticLookup 6, SSNode 4, CollisionPoly 16, Vec3s 6.

capacity = (0xF000 - (6144 + polys + 4000 + 8192 + 3072 + 8068)) / 4

Nodes used were counted with real z_bgcheck on each image's built SA.cpp:

| | Polys | Node capacity | Used | Spare |
|---|---:|---:|---:|---:|
| base | 1579 | 7596 | 4280 | 3316 |
| 256 | 1897 | 7516 | 4873 | 2643 |
| 184 | 2139 | 7456 | 5162 | 2294 |

Every static node is written once, inside BgCheck_Allocate, from fixed data. A
count below capacity therefore means no write goes past the table; this check
runs before any target write. The dynamic node pool (1000) and THA 0x30000 are
unchanged.

**C `bg_floor` sweep over the patch** (11,384 points on a 37-unit grid):
- No floor is lost anywhere.
- Height stays within 2 units everywhere.
- The surface is identical except at 5 points. There a coplanar road overlay
  already lay within 2 units, and rounding now decides the tie. The effect is
  the footstep sound only.

## Pipeline and checks

- **Layout key.** `patches` (`spot00_room_0/retopo/<name>` → room sha256 plus
  bundle).
- **Bundle.** A content-addressed `patch.json` holding geometry, fans,
  collision, and source and collision hashes.
- **Variants.** `field-square-184` and `field-square-256`.
- **Pairing.** `build.sh` refuses a disc whose STM, COL and OOC records name
  different bundles.
- **Host tests.**
  - `tests/test_field_retopo.py`: 12 tests, including the floor sweep.
  - `tools/tests` layout and map-workshop tests: 29.
  - field stream and workshop quad tests.
- **Isolated images.** `build/square-retopo/r2-184/`, `r2-256/` are copies of
  the working tree with only `selection.json` and the mailbox hooks changed.
  They use a full WSL dev build with `OOT_CORE=1`. Results: see Build log
  below.

## Runtime comparison still needed

This is for Astra or the human, in the visible configured GUI:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File game/tools/control_probe/launch.ps1 -Run game/build/square-retopo/r2-184
$env:CONTROL_RUN='game/build/square-retopo/r2-184'
python game/tools/control_probe/compare_square.py --folder r2-184-v1
python game/tools/control_probe/performance_tr.py --folder r2-184-v1 --modes 0,0
```

**Pairing.** Pair the captures with the checkpoint's `verification/m0-*` (P3
plain SGL) and `m2-*` (TR) at the same poses. The walks along x = 0 cross
every 33/34 boundary in both directions.

**Further checks.**
- Child height.
- Wall, ceiling, slope, landing and projectile checks.

**Acceptance requires all of:**
- a continuous floor;
- no new cracks or falls;
- the camera staying above ground;
- reduced swim;
- the 90-step walk measured against 4.735 s (P3) and 7.27-7.31 s (TR).

If 184 costs too much, repeat with r2-256.

## Build log

Both images are full WSL `OOT_CORE=1` dev builds of the working tree. The only
differences from the tree are `selection.json` and the mailbox hooks.

| | r2-184 | r2-256 |
|---|---|---|
| Build | 447 s, exit 0 | 496 s, exit 0 |
| Pairing | stm/col/ooc agree, bundle 09944ed9... | stm/col/ooc agree, bundle d5ae2def... |
| SAR0.STM | 570,708 B | 539,580 B |
| SA.COL | 81,916 B, 2139 tris | 72,720 B, 1897 tris |
| SA.OOC | 50,836 B | 46,236 B |
| .bss end | 0x06081a20, 9696 B below SGL | same |

The baseline SA.COL is 60,636 B and SA.OOC 40,128 B. SA.OOC stays inside the
0x40000 scene-collision carve, and SA.COL inside the runtime COL buffer (2321-tri
sizing). The C code is identical to main plus Astra's audited mailbox hooks, so
there is no new runtime math.

**Host checks on each image's own SA.COL:**
- test_player_camera + test_oot_follow: 55 pass, including the recorded Field
  turn.
- test_field_retopo: 12 pass at 184, and 12 pass at 256 (`RETOPO_SIZE=256`).
  The C floor sweep finds 5 overlay ties at both sizes.

**Untouched images.** The usual game-clean.iso is 8c24b1b9... (equals the P0
baseline). The checkpoint game.iso is 49bbf734... (equals checkpoint.json). The
Debug game.iso is unchanged since 11:51.

**Launch.** Visible GUI runtime evidence and remaining interrupted comparison are recorded above.
