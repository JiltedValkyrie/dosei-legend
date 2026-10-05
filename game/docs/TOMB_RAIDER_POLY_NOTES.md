# Tomb Raider (Saturn JP) polygon study and reviewed plan

Current status, 2026-10-05: human stopped renderer work after positive visual
feedback and requested [FIELD_SQUARE_RETOPO_PLAN.md](FIELD_SQUARE_RETOPO_PLAN.md).
That plan is written; new square topology/collision is not implemented. Astra's
local TR candidate and camera correction are saved in the complete runnable
`game/build/astra-control/checkpoint-2026-10-05/`. Eleven matched movement/view
pairs ran in the real visible Kronos GUI, Adult Yes / All Items Yes. Swim and
major missing-floor cases improve; measured walking costs about 54% more time.
See the final section for exact implementation, measurements and limitations.

The original P0/P1 work and Opus's standalone P3 patch below are historical;
their waiting-for-go and no-runtime-change statements do not describe Astra's
later implementation. Only the same local four-face patch was affected. Usual
Clean/Debug images and Opus's probe remain preserved. Main source contains the
camera correction; the renderer is isolated. No wider map retopology started.
Checkpoint: `807d1e07840df93b669b0147fcc645e5e2e771e3` identifies source;
preserved images/hashes and source provenance remain distinct.

## TR observations: Claude's static reading, not runtime proof

Source: personal disc, `0MAIN.BIN` loaded at 0x06004000. No successful TR run
(real-drive read failed). No disc data committed. Astra has not independently
reconstructed these routines; addresses below preserve Claude's evidence.

- Textured command 0x0002 (distorted sprite); flat command 0x0004 (polygon).
  There is no demonstrated hardware perspective correction. Small textures
  alone do not establish small faces or eliminate perspective swim.
- Inspected texture sizes: 32x32, 32x8, 32x16, 32x24 and 16x32, 4bpp LUT.
  Reported offline quadrant data: ROOMTINF/ROOMTQTR/ROOMTSUB in LEVEL*.SAT;
  quadrant upload at 0x06040F30. Do not call every quadrant 16x16 when source
  heights vary, or infer room geometry subdivision from texture subdivision.
- Reported triangle completion: `D = B + C - A`. For non-collinear A/B/C this
  constructs a parallelogram, not a degenerate triangle. Corner order and how
  the unwanted half is masked/omitted still need tracing.
- Vertex: int16 source; 32-byte working struct with camera coordinates,
  projected coordinates, outcode, gouraud and projected flag. Reported matrix:
  three `muls.w` products plus 32-bit translation. Projection: `q=z/k`,
  `sx=x/q`, `sy=y/q` through DIVU. Viewport 352x224, centre (176,112).
- Reported guard band: x [-128,480], y [-128,352]. Normal face path rejects
  any vertex below near (0x0603E39A); outcode AND rejects at 0x0603E382.
- Special types 0x21/0x24/0x25: near/guard clamping and 2x2 subdivision,
  at most two levels / 16 leaf cells per source face in the inspected path.
  Reported single-sprite predicate also requires front-facing and depth sum
  >0x10000000, besides `(OR outcodes & 0x5F)==0`. Thus **"only splits when a
  vertex is clamped" is not established**: trace depth-only and backface branch
  outcomes before treating that as the exact trigger. No screen-area test shown.
- Reported cell rules: reject offscreen or any z<1; remaining cells can use
  clamped coordinates. Helpers: test 0x06040864, midpoint 0x06040AC8,
  project/clamp 0x06040CA2 / 0x06040D18, vertex load 0x06041246.
  Dispatch paths: 0x0603FCAC / 0x0603FCE2 / 0x0603FDC4.
- Near global 0x06063B68 and focal global 0x06063B7C (set at 0x06039A64):
  runtime values/units unresolved. Reported 1700-command limit belongs to TR,
  not VDP1 hardware or this game's configured capacity.

Unknowns: actual room face sizes, which room types select each path, exact
split predicates, triangle masking, and visual benefit during movement.

## Repository review and corrections

1. SGL near handling already exists. `main.c` sets `slZdspLevel(3)` and the
   live `demo_screen_distance()`; 30 is only the 240-distance case. Both
   `build_sgl_scene.py` and the active binary exporter `build_room_scene.py`
   set `UseNearClip`. Those facts **do not prove** TR-equivalent rejection of
   every face with one near vertex, or prove current wedges fixed. Sega's
   [SGL supplement](https://docs.exodusemulator.com/Archives/SSDDV25/segahtml/sgl/sglr/hosoku/hosoku.htm)
   describes near clipping; its
   [SGL FAQ](https://docs.exodusemulator.com/Archives/SSDDV25/segahtml/faq/sgl/p01_10.htm)
   separately warns about XY overflow and discusses sort depth, subdivision
   and near clipping. Trace the affected installed SGL path before equating
   its behavior to a whole-face CPU cull. Raising safe-near risks floor holes;
   it is not a proved fix or a proved no-op.
2. `forest_depth[]` is yaw-only, using x/z and no pitch/Y. It is not camera z.
   Any later CPU near test must match the actual view transform and units.
   Existing int64 operations here are migration debt; add no wide runtime math.
3. Normal `slPutPolygon` input offers no per-corner screen clamp hook. A
   TR-equivalent clamp needs control of projected output; replacing the entire
   projection is not yet justified. Existing command-order inspection code is
   not proof that changing slave-owned coordinates would be safe.
4. `WARP_PROBE=1` enables measurement code, not a file logger. The existing
   HUD is hidden by `DOSEI_CLEAN_TEST`'s early return in `viewer_hud()`.
   `--clean WARP_PROBE=1` therefore does not provide visible probe rows.
   An isolated developer probe uses the diagnostic HUD; a Clean-equivalent
   overlay would need a separately authorized diagnostic-only change. Preserve
   OOT_CORE, scene assets, camera and renderer flags; record all mode differences.
5. Probe fields are weaker than their names/comments suggest:
   - `nr r` = minimum approximate eye-to-vertex range, not forward depth.
   - `nr f` = minimum yaw-only `forest_depth`, despite the name `warp_near_far`.
   - `e` = largest world-axis extent; `sp s` = extent*256/range, not pixels.
   - Only two vertex IDs are exposed; no source-face ID, four camera-space
     depths, projected corners, clip outcome, UV result or emitted command.
   Candidates can be offscreen or unrelated to the visible defect. Partitioning
   reorders faces, so a runtime array index alone is not a stable source ID.
   HUD refresh is about four times/second and is not a frame-synchronous trace.
6. Row 12 `sub` sums polygon counts for accepted calls through `submit()`;
   it is not a count of emitted VDP1 commands and is not necessarily forest-only.
   Other sprite paths and system commands must be counted separately.
   `rej=0` does not prove every face survived SGL or that command VRAM fits.
7. `field_walk_probe.py`, `BUG_FEATURE_LOG.md` and the failure document are
   absent from this tree. Recover the failure rules read-only with:
   `git show 536140e^:game/docs/FOREGROUND_WARP_FAILURE_2026-09-18.md`.
   Do not promise the removed helper as a usable current logging tool.
8. Decision rule is **triage, not diagnosis**, and causes may coexist:
   - **Wedge:** geometry stretches/flashes across the screen. Inspect the
     affected face's actual camera z, projection and emitted coordinates.
     `range < 30` is neither a required nor sufficient test for coordinate wrap.
   - **Swim:** silhouette stays plausible while texels slide/shear within the
     same surface as the camera moves. Large extent/span is a candidate hint;
     establish perspective/depth variation and exclude changing materials/UVs.
     Small geometry patches with correct UVs may reduce this; no guaranteed cure.
   - **Sort:** independently valid surfaces draw in the wrong overlap order
     (including walls/ground, not just Link's legs). Inspect command order and
     sort keys. Marked floors use SORT_MAX only below the eye; others use SORT_CEN.
   If the visible face cannot be tied to the probe, result is **unclassified**.
   Record scene/room, age, pose, camera yaw/pitch and visual timing. Collect the
   missing face/command evidence before choosing a renderer change.

## P3 budget review: conditional, not approved to fit

Offline subdivision already lives in `build_hybrid_scene.py`: `room_ground`,
`refine_room_ground`, and opt-in `DOSEI_SPLIT_TEST` / `DOSEI_SPLIT_DIVISIONS`.
`build_sgl_scene.py` is not the sole active room conversion path. Identify the
actual bad source face and its current children before adding another pass.
The existing selector matches source IDs across room conversions: isolate one
room and verify no other asset changes. Existing helpers are not visual proof.

Current staged room headers and `build/generated/rooms_manifest.json` give:

| Kokiri room | Room vertices / faces / tiles | Texture budget used, including residents | Spare beyond required 32 KiB |
|---|---:|---:|---:|
| 0 | 1756 / 1475 / 1297 | 411520 / 445432 bytes | 1144 bytes |
| 1 | 1558 / 1464 / 1426 | 410656 / 445432 bytes | 2008 bytes |
| 2 | 598 / 426 / 353 | Not retotalled here | Not claimed |

Rows 0/1 include the manifest's conservative max-age Link budget (704 faces,
385 vertices, 184 tiles, 16672 bytes), 65536 actor bytes/576 slots and 32192
runtime bytes/51 slots. Against combined table limits, rooms 0/1 leave 421/432
faces and 359/557 vertices. These are asset estimates, **not live command
headroom** or proof the current ISO contains these exact banks. The tiny extra
texture margin is a reason to try only an identified, preflighted face set.

- One unsplit quad -> 2x2 adds three faces and up to five unique vertices.
  Splitting k existing pieces adds 3k faces; two full levels add 15 faces and
  up to 21 vertices per original quad. Even a 16-cell local cap can exceed a
  whole-frame budget. Offline children cost storage/transforms beyond close views.
- `vdp1_budget.py` checks 2600 whole-table polygons, 2500 combined vertices,
  2400 sprite slots, and a 2200-polygon budget. Its 1354+520 frame estimate is
  historical, not a current populated-scene measurement.
- SGL build defaults are instead 3750 polygons / 3200 vertices. Generated
  `vdp1_layout.h` starts textures at 0x13300: 78,592 bytes, equivalent to 2456
  32-byte command slots including the 256-slot allowance. The larger SGL limit
  is **not** permission to write more commands into that reserved VRAM region.
  This mismatch must be accounted for before claiming subdivision headroom.
- Count full reachable actor/effect sets, both Link ages, shadows, HUD/system
  commands and relevant room/chunk overlap. Preserve command/texture separation,
  actor reserves, 32 KiB spare, tile/CLUT alignment and heap/SGL boundaries.
  Do not raise caps or silently lower unrelated texture density to make P3 fit.
- Each child needs the correct UV subregion. Reusing the full parent tile on
  each child repeats the image. SGL's
  [texture tutorial](https://www.infochunk.com/saturn/segahtml_en/sgl/sglt/prog/hon/p07_10.htm)
  describes splitting texture data when a texture spans polygons. Account for
  child tiles, palettes, alignment, lost deduplication and changed tile sizing;
  splitting cannot be assumed VRAM-neutral. Keep the parent appearance/density
  and source material policy fixed for the comparison.

## Revised sequence for Claude after human go

**P0:** Record checkpoint + dirty diff, exact compiler/build/probe flags,
active SGL path, mesh/texture/layout hashes and executable/image hashes.
Preserve a runnable baseline: CUE, ISO and **every referenced CD audio track**,
with working relative paths. The previous handoff reported a mounted-image
blocker; verify current image provenance instead of assuming commit == disc.

**P1:** `game/build/probe/` is a sound proposed destination; the usual Clean
disc stays unchanged. This review does not start a build. Isolate objects,
staging and generated assets too (prefer an isolated checkout); current
`build.sh` hardcodes output/verification paths, so merely copying a finished
Clean build there is not isolation. Keep the CUE's referenced tracks runnable.
Rebuild all define-dependent objects and run the matching SGL boundary check.
Current Clean code had only 16 bytes of reported high-WRAM margin; probe fit
is unknown. Never reduce heap/actor limits or remove guards to fit diagnostics.
Human alone launches Kronos, walks, turns and jumps near the affected floor/wall.
Use existing HUD for triage only; no automatic movement or claim of logged frames.
If evidence remains ambiguous, request a focused trace as the next separate step.

**P2, only for traced wedge:** Inspect live attributes, SGL near handling and
projected coordinates first. Test one justified correction; do not blindly
change display level/flags or use yaw-only CPU culling. Preserve floors and
occlusion while moving; any regression means revert that change immediately.

**P3, only for traced swim:** Offline split one identified face set in one room
first, using the existing importer and correct child UVs. Run budget preflight
before staging. Compare unchanged material/density/clip/sort policies; verify
actual child attributes because the size-based floor-sort rule can change when
faces shrink. Measure populated-view command use and target cost, then human
movement. A build passing does not prove either capacity at runtime or a fix.

**P4, parked:** Requires a separate review, evidence P2/P3 were insufficient,
safe projected-coordinate ownership and viable child texture representation.
Bound local splits and the total frame workload. No blanket authorization for
own projection, runtime grids, scratch texture repacking or material rewrites.

At each authorized implementation stage: proportional host checks, matching
target build/disassembly (no new wide or software-float math), human movement
gate, and current build/plan notes. Do not bundle phases or promote an unaccepted
experiment into the player disc. No builds/tests/runtime claims from this review.

## Correction to the 2026-09-18 failure summary

The failed work added a runtime 4x4 grid for up to three nearby ground surfaces,
scratch texture repacking and extra submissions on top of a material rewrite.
Scratch reservation changed the offline texture budget, spoiling the comparison.
Movement exposed missing-floor regions; it did not establish one isolated cause.
The lesson is not simply "16 cells is safe": that experiment already used 4x4.
The failure record's rule 6 governs image isolation; rule 7 governs visual
acceptance; rule 8 requires stopping/reverting regressions. Rollback retained
pre-existing SORT_MAX and offline subdivision redistribution. It neither restored
the old libyaul CPU clipper nor fixed the warp. Identify an exact revision/path
before proposing any future "original clipper" restoration.

## Execution status (Claude, 2026-10-05)

**P0 preservation done; source-to-image provenance incomplete.** `game/build/baseline-2026-10-05/`: Clean cue, iso, elf, map, tracks 02-06,
`SHA256.txt`, `MANIFEST.txt`. Checkpoint `807d1e0`. Evidence the Clean image matches that
tree: no source/tool/makefile/build.sh file is newer than `game-clean.iso` (built 2026-10-04 20:41).
This is an mtime check, not proof the image matches the checkpoint: old or stale
objects can predate the ISO too. The usual `game/build/game-clean.*` was not touched.

**P1 probe image built; human now supplied readable probe rows.** Isolated copy of `807d1e0` (git archive) in
`game/build/probe/oot-sat/` with its own objects (`build/obj`), staging (`build/cd`) and generated
assets. Flags: dev variant (no `--clean`), `OOT_CORE=1 WARP_PROBE=1`, `--quick`. Log:
`game/build/probe/build_log.txt`. Result: link OK, SGL boundary check OK
(`.bss ends 0x060838c0, 1856 bytes below the work area`; Clean log earlier showed different margins, so
do not compare them). Probe strings (`nr r%d`) present in the elf and iso.
Run: `game/build/probe/oot-sat/game/build/game.cue` (6 tracks, track hashes equal baseline).
Differences from Clean (all of `DOSEI_CLEAN_TEST` in source): debug HUD visible, minimap nut-launcher
marker, L+R+D-pad diagnostics chord. Plus `DOSEI_WARP_PROBE` rows 10-12. No renderer change.
Initial screenshots lacked probe rows. Human subsequently reached the other
HUD panel and supplied readable nr/sp/sub values; see the Field trace below.
Offline source-face association remains conditional on the reconstructed
resident set. No projected-command or visual fix acceptance yet.

Human steps: open that cue in Kronos, reach the bad floor/wall, walk/turn/jump, read HUD rows 9-12
at a bad frame, note scene/room, age, yaw/pitch, what it looked like. Ambiguous = unclassified (rule 8).

### Screenshot/conversation review (Astra, 2026-10-05)

Two supplied stills show wireframe and textured Hyrule Field, with very large
foreground faces and coarse/stretched ground texels. Views are not an exact
matched pose. This supports investigating face size/UV density, but does not
demonstrate temporal swim, absence of intermittent wrapping, or an uninvolved
near plane. Claude's statements "swim, not wedge", "slides as the camera moves"
and "near-plane cut isn't involved" exceed this evidence. Diagnosis remains
unclassified, with large-face mapping a candidate. P1 build is complete;
P1 causal tracing is not. Read-only source-face investigation is appropriate;
screenshots do not authorize or validate P3 renderer/asset changes.

The isolated probe source has two distinct diagnostics paths:
- `main.c:192` `diagnostic_overlay()` reads L+R directly and toggles its
  register/timing overlay after 60 ticks, including Clean. Thus "plain L+R
  does nothing by design" is incorrect. The bottom VRAM/CPU line is always
  drawn by this function and does not identify the running build.
- `player_input.c:245` implements the developer L+R+Down chord, delivered to
  `viewer_hud()` through `demo_diagnostics_toggled`. Probe rows are inside
  `if (!debug_visible)`, not the alternate viewer panel. Inspect the whole
  input-to-display path rather than infer visibility from the boolean's name.

The missing-readout step above is now resolved by the human's later screenshot.
Claude's offline face association follows below; correlating bad pixels with
the candidate and proving UV/capacity behavior remain open. Preserve the renderer
and normal Clean image. No code/build/emulator action in Astra's reviews.

## P1 trace: Field faces at Link 1192,418,4114 (Claude, 2026-10-05, offline, read-only)
Probe readout (human, Kronos, probe image): `nr r445 f454 e1597 t760 v675,676`, `sp s952 r457 f-1244 e1700 t709 v457,459`, `sub649`.
Meanings (probe src `kokiri_sgl.c` ~1717, 1789-1904): t = bank-relative streamed slot
(`texno - forest_sprite_base`), not the global sprite index or immutable source
tile/face ID. `field_rebuild()` maps source tiles to these slots. v = resident
vertex indices stable through polygon partitioning, but not through a changed
resident piece/LOD set: `field_rebuild()` repacks points in group order. Resident set reconstructed from SAR0.STM
bands + hysteresis: only consistent combo = group25 as LOD2 piece 83 (381 polys, 828 verts, 359 tiles). High confidence, not runtime-proven.
- Face A (nr): piece 42 face 9, quad, vertical curb riser x=1432, z 4330-5927, y 396-437. Tile 559 32x16. ~240 ahead of Link. Not under Link.
- Face B (sp): piece 33 face 6, triangle (0,0,3400)(1472,400,4250)(1472,0,2550). Tile 438 64x64 4bpp. Sort 0x66 (far-sort floor).
- Face under Link: piece 33 face 8, triangle (0,0,3400)(0,320,5100)(1472,400,4250). Tile 552 64x64. Sort 0x66.
Which face makes the bad pixels: NOT verified (camera pose inferred). Source N64 tri/converter path untraced.
No UVs stored: SGL maps whole tile to the 4 corners (tri = A,B,C,C).
Split price, face 33/8 alone: L1 = +3 faces/+3 verts, child extent <=850; L2 = +15 faces/+12 verts, <=425.
Neighbours 33/6, 34/5 would receive unmatched edge vertices with uniform midpoint
splitting of 33/8 alone. Texture estimate assumes four 32x32 or sixteen 16x16
child tiles replacing one 64x64 tile: aggregate pixel payload stays 2048 bytes;
net +3/+15 palettes cost +96/+480 bytes. This is a hypothetical per-face payload
estimate, NOT the measured change in the Field's bucket-reserved VRAM or slots.
Whole field: 1258 full faces; >400: 684, >800: 355, >1600: 88; all 194 LOD2 faces >800.
Budgets: bake sweep worst resident 721 polys/1157 verts; vdp1_budget 2200 poly; field plan 717 slots, 268000/445432 VRAM.
Per-position cost of a field-wide split not computed. P3 not started.

### Astra review of the offline match and split estimate

The identification usefully separates the long curb from the ground candidate.
Coordinates and uniqueness are Claude's offline reconstruction, not an
independently reproduced runtime association in this review. Keep a stable
piece/local-face key plus the exact ordered resident set/asset hash, four corner
indices, camera pose and source-tile identity; no globally stable `v` claim.

Triangle midpoint counts are consistent: 4 children add 3 faces/3 vertices;
16 children add 15 faces/12 vertices before neighbor closure/deduplication.
850/425 are largest-axis extent bounds for these midpoint-refined triangles,
not Euclidean longest-edge or projected-size bounds.

Two unresolved costs prevent treating the quoted price as a P3 preflight:

1. **UV mapping:** no explicit runtime UV array does not mean no mapping.
   The A/B/C/C corner order supplies an implicit map. Midpoint triangle children
   do not correspond to four rectangular crops of the parent tile. Reconstruct
   original importer UVs (`surface_vertex`/`render_tile` retain offline UV data),
   or explicitly resample the parent mapping into each child. Verify orientation,
   shared-edge texture continuity and unchanged material/density policy. The
   existing triangle splitter supports divisions=2; two levels mean recursive
   subdivision, not passing divisions=4. Actual child sizes, palettes and dedup
   must be measured after this mapping is defined.
2. **Streaming allocation:** `build_field_chunks.sweep()` reserves the maximum
   count of each size bucket across positions and modes, then sums those maxima.
   Removing this 2048-byte tile may not reduce the 2048-byte bucket's maximum;
   adding children can increase a different bucket's maximum. Thus constant
   aggregate pixels per face does not imply constant reserved pixel VRAM.
   Recompute normal/owl and hysteresis/LOD coverage, palette/slot totals,
   resident vertices/faces and populated-frame command costs for the exact patch.
   721 resident Field faces is not whole-frame use or proof of spare commands.

Neighbor refinement also needs a bounded edge plan: subdividing both neighbors
uniformly creates further unmatched boundary edges. Enumerate the affected
patch, including chunk/LOD seams, before quoting its cost. T-junctions can risk
raster cracks; their existence does not itself prove a visible hole in these
screenshots. Do not recursively expand the patch without an explicit bound.

Recommendation: after human go, start with one midpoint level on the smallest
bounded candidate patch, correct child UVs and unchanged sort/clip/material
policy, in the isolated probe only. Two levels or whole-Field splitting are
not the first experiment. Candidate-to-bad-pixel association and visual benefit
remain hypotheses for that comparison. No P3 code/build authorized by this review.
Shared-tree note: an existing analog diagnostics-chord edit in player_input.c
is present; Astra left it untouched. "No code changed" applies to the offline
face study/review, not to the entire shared working tree.

## Local patch plan (Claude, 2026-10-05, offline, not built)
Mesh Workshop group = ROM display-list object (`tools/mesh-workshop/viewport_scene.py:40,132-141`); real ROM grouping.
Obj17 = 9-triangle ground fan around (0,320,5100) (src 738-746) + 16 cliff-lip strips. Streamer drops the object id and cells
faces by centroid (`build_field_chunks.py:210-217`). Map: obj17 src746 = STM 33/8 (target), src738 = 34/1, src745 = 34/5; obj13 src613 = 33/6.
Patch (one level, no recursion): 33/8 1->4 at midpoints m01 (0,160,4250), m12 (736,360,4675), m20 (736,200,3825);
edge neighbours 1->2 from opposite corner: 33/6 at m20, 34/1 at m01, 34/5 at m12. Vertex-only contacts unchanged.
Crosses pieces 33/34. LOD2 83 does not touch; LOD2 91 already cracks vs 33 when 34 is far (pre-existing; collinear cuts don't change it).
Cost: +6 polys, +5 piece-local verts. Bake sweep: patch resident at 954 positions; worst resident 721/1157 -> 727/1162 (global worst).
Textures (sizes estimated; bake greedy `build_hybrid_scene.py:363-417`): likely 4x32x32 (target), 2x32x32 (33/6), 4x16x16 (34/*).
Bucket peaks (exact method `build_field_chunks.py:298-330`): 717 -> 723 slots; field VRAM 268000 -> ~266656 (halved) or 277408 (parent size). Under 445432.
Implementation correction: those selection/refinement paths are quad-only,
but `split_ground()` at line 564 already implements triangle 1->4 midpoint
subdivision, interpolating the full vertex tuple including UVs. Reuse it through
the existing baker. Edge-selected 1->2 and four-face selection still need wiring.
Not verified: real rebake sizes, owl reserve, per-frame populated draw count, runtime look. Needs human go.

### Astra review of the four-face patch

The proposed topology meets the human's local-only scope: target plus three
edge neighbors, no corner-only contacts, no recursive expansion or distant
faces. Opposite-corner cuts create no new vertices on the outer patch boundary,
provided edge matches are exact and midpoint rounding is identical. Four parent
faces become ten children (+6 faces); +5 piece-local vertices is consistent
with three midpoints in piece 33 and two copies in piece 34.

Recommendation: reasonable isolated one-level experiment after human go, with
these implementation checks:

- Select ROM object/source IDs with parent geometry/asset checks: obj17
  src746/738/745 and obj13 src613. Piece/face indices can change on regeneration.
- Preserve parent chunk membership or explicitly account for every change.
  Centroid repartitioning can move children between cells and invalidate the
  residency estimate. Keep far LODs, outer geometry, sort/clip/material policy
  and unrelated texture density unchanged. Verify non-selected asset content:
  the greedy texture allocator can redistribute savings beyond the patch.
- 727 is Field resident faces alone. Adding the recorded 704-face Link/actor
  allowance gives 1431 against the 2600 table check, before additional owl-mode
  allowance. This does not measure whole-frame emitted commands.
- 723 slots and both VRAM prices are scenarios until actual child tiles and
  normal/owl bucket sweeps establish them. Keep all reserves. Check triangle
  UVs, winding, palette policy and shared-edge continuity. Half-size tiles are
  not yet proved to preserve density/appearance.
- Existing chunk-34 LOD crack is recorded debt, not a verified no-regression
  result. Keep far geometry unchanged; include the 33/34 transition in the
  human comparison and revert this patch if it worsens visibility/seams.

No implementation/build in this review. Claude owns the proposed patch;
human go remains required for P3 and human owns the Kronos comparison.

## P3 patch experiment built (Claude, 2026-10-05, probe image only, NOT run)
Code (probe checkout only, `game/build/probe/oot-sat/game/tools/`): `field_patch()` in `build_hybrid_scene.py`, opt-in
`DOSEI_FIELD_PATCH="746:4,738:2,745:2,613:2"`, runs only for streamed `spot00`, after all tile sizing/compaction.
:4 reuses `split_ground()`; :2 = new edge cut (opposite corner -> midpoint a :4 face creates; errors unless exactly one edge).
Children keep parent cell (`cell_points` record field read in `build_field_chunks.build_pieces`). Parent tile kept in pool.
First attempt applied the hook to every room conversion (fatal, and marked other scenes blocked in the probe's all-scenes
cache); scoped to the Field and the probe cache restored from main before the rebuild.
Bake output: 613 -> 2 (64x64 -> 32x64), 738 -> 2 and 745 -> 2 (32x32 -> 16x32), 746 -> 4 (64x64 -> 32x32).
Freeze check (content-level decode of both STMs): only pieces 33/34 differ; all 1356 baseline tiles present; 10 new tiles.
Other pieces' tile ids shift (pool index), content identical.
Sweep (normal and owl): worst resident 721/1157 -> 727/1162. Slots 717 -> 723. VRAM 268000 -> 268192 of 445432.
Bucket peaks: 256 73->77, 512 92->94, 1024 14->16, 2048 8->6, 128 529 unchanged.
727 + 704 Link allowance = 1431 table polys (not a measured frame-command count). SGL boundary check passed (1840 B).
`spot00 room 0: blocked` in the all-scenes step also appears in older logs (generic bank; Field uses the STM).
LOD2 91 seam: no visual or edge comparison done yet. Runtime look and warp effect unverified.
Image: `game/build/probe/oot-sat/game/build/game.cue` (dev variant, OOT_CORE=1 WARP_PROBE=1).

### Astra review of built probe (2026-10-05)

Read the probe-only `field_patch()`/cell assignment, generated stream report
and successful build log. Field-only hook and post-sizing placement match the
reported design. Budget/report and 1840-byte boundary match the handoff. No new
build/test/emulator run by Astra, and no independent repeat of Claude's decoded
STM freeze comparison. Runtime renderer and main importers remain untouched.

Next is the human comparison at the recorded pose, plus walking/turning/jumping
and crossing the 33/34 LOD boundary. Record texture orientation/stretch, patch
edge gaps, floor visibility and responsiveness. Build success is not a warp fix.
Do not expand the patch or promote it before that result.

Two code-review limits to retain for later cleanup/independent review:
- 1->2 edge matching compares rounded midpoint positions, not both edge
  endpoints. Distinct edges can share a midpoint in general; this four-face
  experiment relies on the earlier exact adjacency reconstruction. Before
  generalizing, match canonical endpoint pairs and reject unsupported split modes.
- Child tile width/height are chosen by split count, with 1->2 always halving
  width after corner reordering. Original UVs are interpolated and rebaked, but
  equal total pixel count is not proof of equal per-axis texel density or edge
  color continuity. "Parent texel density" in the helper docstring is an intent,
  not a verified result. Review actual child UV orientation and sampling.

Suggested bounded task for Grok, relayed by the human: independently inspect
those four faces' winding/UVs/shared edges and the unchanged LOD boundary;
report findings without widening or editing the patch. No direct Grok contact
or delivery is claimed by Astra.
Rebuild 11:26 after Astra's checks: edge match uses both endpoints; child tile size from the child's own 0->1 / 0->2 edges
at the parent's texel density (pow2, 16..parent max). The 11:01 image halved fixed axes and lowered density; superseded.
Tiles: 746 -> 32x64 x3 + 64x32; 613 -> 64x64 x2; 738, 745 -> 32x32 x2. Freeze: still only pieces 33/34 differ, 10 new tiles.
Worst 727/1162 (owl same). Slots 723. VRAM 268000 -> 273312 of 445432. Buckets: 512 92->94, 1024 14->18, others unchanged.

### Grok methodology review (Astra, 2026-10-05)

Human supplied Grok's detailed ROM-face check. It traces the four source faces
through load_faces/quads.build, checks all nine midpoint components, child
normal orientation, all 1639 source faces for shared edges/midpoint incidence,
and both child-centroid migrations prevented by cell_points. This supports the
four geometric checks for the specified full-detail patch. Astra reviewed the
method and current helper source; did not independently rerun Grok's script.
Retain script/output with asset and source hashes for reproducibility.

Limits: continuous UV interpolation is not proof of identical sampled texels,
palettes or visible seam behavior. Full-detail source adjacency does not validate
the generated LOD2 91 boundary or emitted SGL commands. The differing 613 UVs
are a source-coordinate seam; preserve them, without inferring a visible color
seam from UV numbers alone (textures can repeat or differ).

Grok correctly demonstrates that child_size's parent-size cap violates its
chosen scalar density target. However that target is the maximum of two parent
edge densities, not a measurement of the parent's sampling along every possible
child edge. For triangles, interpolate uses ((1-u)(1-v), u(1-v), v), so sampling
also varies across the collapsed square. Falling below the scalar maximum is
not by itself proof of lost original detail at that location.

Astra corrects the earlier unconditional 52->64 / 66->128 recommendation: those
are round-ups for the selected conservative scalar policy, not proved minimum
tile sizes for preserving the original mapping. Uncapping alone cannot certify
image-wide density or isolate geometry from sampling changes. State the chosen
policy honestly and verify actual baked appearance/budget; do not describe the
capped build as "density never down". No new code/build in this review.

### Earlier negative-x human run (2026-10-05; superseded by local report below)

Human now supplies textured/wireframe screenshots from the current probe test;
the earlier "not run" status is historical. Readable Link positions are
(-1129,50,2842), yaw 37339, and (-1432,86,2089), yaw 8710. Original target was
(1192,418,4114), yaw 14082. These are different places, not matched before/after
views. The four selected parent triangles have x bounds [-736,1472], so Link
is outside the patch in both new poses. Some patched geometry might still be
visible; identify actual visible faces before assigning the bad pixels to it.

Large stretched foreground texels remain visible. This confirms the broader
Field complaint persists, but does not establish success/failure of the four-face
patch or justify distant splitting. Grok's source checks support full-detail
patch topology/UV interpolation/cell placement, not runtime visual acceptance.

Opus next:
1. Correct the status to human-run, local result inconclusive. Remove the
   unconditional "parent density preserved" claim: the scalar target is capped.
2. Keep the 11:26 experiment fixed. Locate its exact four-face footprint for the
   human using a map/landmark or coordinates. Compare patch-off/on at the original
   target with the same camera/age/LOD; confirm the split children are resident
   and visible in wireframe before judging the textured surface.
3. Human checks walking/turning/jumping within that patch and the chunk-33/34
   boundary toward +z. If worse, revert the experimental patch; if unchanged,
   inspect that face's projected/UV result before another split level. If better,
   record only local acceptance; no automatic widening or player-image promotion.
4. Record the new negative-x screenshots as a separate location. Do not expand
   this patch to reach them. Further work there needs its own identified local
   Workshop group and scoped decision. No whole-Field threshold splitting.

No additional build is needed merely to compare the current experiment. Grok
can independently check the baseline versus patched generated LOD boundary;
repeating the already-supported source midpoint/winding checks is not the next
visual gate. Stills and CPU~ percentages do not prove movement stability or FPS.

### Current result: severe swim remains in the patch (2026-10-05)

Human returned to the selected area and explicitly reports extreme swimming
after only about +40 Z movement. Accept this as movement evidence: the local
experiment has NOT met visual/playability acceptance. This supersedes the
earlier request to return from the negative-x location. It does not prove the
patch worsened the baseline, or identify the failing rendering stage.

Readable poses include Link (726,285,3810), yaw 9124, with LEGACY 260 camera;
later shots show (23,4,3407) and (158,42,3491). These lie in/near the selected
ground patch. The latter poses are close to the original shared A-C edge of
sources 746/613: A=(0,0,3400), C=(1472,400,4250). That makes these faces/children
useful trace candidates, not a proven pixel-to-face identification. Different
pose readouts in the supplied set are not an exact recorded +40-Z frame pair;
this does not negate the human's movement report. Preserve actual camera mode,
position, yaw/pitch and displayed-frame association in the next evidence.

Opus next: freeze subdivision/material/density settings and trace ONE visible
bad child across a short movement. Record stable source/child identity and
resident LOD, actual view-space corners (including pitch), SGL-produced screen
corners and near-handling outcome, texture address/size/palette and sort order.
Correlate with the displayed frame; the 4 Hz nearest/span HUD is insufficient.
Determine whether the tile binding/LOD changes, projected geometry deforms near
the eye, or otherwise valid large triangles retain unacceptable mapping error.
Choose the next single correction from that evidence; no automatic second
split level, distant expansion, projection rewrite or promotion to Clean.

Grok's useful next review is the installed SGL near/projection path for that
same trace, rather than repeating offline midpoint checks. Keep human testing
focused on a diagnostic that actually captures the needed data, not another
round of the same unreadable/ambiguous nearest-face counters. No agent emulator
run or code/build from this documentation review. If a regression versus the
baseline is established, revert the experimental change per the failure rules.

## Patch-corner trace build (Claude, 2026-10-05; human screenshots now supplied)
Human saw at Link (23,3407) -> (158,3491) floor missing (sky band) vs. giant texels. Astra: near failure plausible,
not established; trace before any change. Trace (`DOSEI_WARP_PROBE`, probe `kokiri_sgl.c` patch_trace_*, `main.c` rows 18-26):
row 18 `pc x,y,z y<yaw> p<pitch> nz<near reject> n<faces>`; rows 19-26 the 8 nearest faces having a vertex at a patch
midpoint: slot, 4 true view depths (yaw+pitch, 32-bit), C=CPU-culled/S=submitted, count of VDP1 sprite commands with
that face's texture address (walked via CTRL JP links), max emitted |X| |Y|. VDP1 list ~1 frame older than depths.
Trace code -Os; SGL boundary 48 B spare (first try was 160 B over; heap untouched). Copied to Debug Mode slot.

### Same-Link-position camera comparison (Astra review)

Human supplied close/far textured and wireframe shots at Link (37,275,4353),
yaw 13714. Trace camera changes from approximately (-91,262,4320), pitch -1820,
to (-214,235,4282), pitch 0; near threshold remains 30. This varies camera
position AND pitch, not just distance. Near view row 657 reads approximately
[-482,86,-28,-28] S0; farther view reads [-407,197,-18,-18] S1, max |X|/|Y|
506/235. A command matching that texture appears in the far view despite
reported corners below near. Do not describe this as established any-corner
whole-face rejection. Near handling is a useful candidate, not a proved cause.

Source audit: depths are 32-bit approximate CPU reconstruction, not captured
SGL vertex outputs. S means only i<visible (kept by CPU partition), not proof
slPutPolygon accepted that individual face. Following count matches CMDSRCA
only against a roughly one-frame-older command list, using current texture
bindings; it is not unique face identity. The display also reduces slot modulo
1000. S0 therefore is not alone proof of a near-plane drop; S1 is not alone
proof which face emitted the command. Max absolute coordinates hide corner
shape and whether near clipping changed it.

Opus next: use this same-position camera pair for a source/child-identified,
frame-associated command comparison (all four screen corners, binding/size,
attribute/sort and true SGL transform/near behavior). Check clipping versus
backface/screen rejection and ordinary perspective mapping. Freeze geometry,
density and global near settings. Camera changes are diagnostic, not a warp fix.
Trace result (human, Kronos, Debug slot 11:51, Link 37,275,4353):
- cam OoT, pc -91,262,4320 p-1820 nz30: faces 657 (-482,86,-98,-98), 656 (-482,270,86,-98), 698 (-98,86,674,674),
  715 (1092,-98,674,674) all S (submitted) with 0 VDP1 commands. 701, 699, 716 (all corners > 30) drawn, max |X| <= 484.
  659 (1870,858,270,270) S0, probably off-screen (unproven). Fits: SGL drops a whole face crossing near -> missing floor.
- cam LEGACY, pc -214,235,4288 p0: 657/656/698 with corners -407/-18 each drew 1 command (max |X| 506). But the screen is
  pitched down while trace says p0, so trace depth (demo_yaw/demo_pitch) is wrong in LEGACY. Untrusted.
Open: compute trace depth from SGL's real matrix (slGetMatrix at forest submit), retest both camera modes.
Handed to Astra 2026-10-05. Probe code + Debug slot image hold the trace; usual Clean untouched; nothing committed.

## Astra controlled build and real-matrix result (2026-10-05)

Implemented under `game/tools/control_probe/`; runtime hooks exist only in
`game/build/astra-control/oot-sat/`. The existing Opus Field STM, four-face patch
and CD tracks are retained. The build boots Field through the existing Level
Select path with Adult and All Items enabled. A bounded low-RAM mailbox supplies
normal pad input for explicit 30 Hz gameplay steps. Rendering continues while
simulation is frozen. Diagnostic pose resets are supported; global world/RNG
determinism is not claimed. No production renderer or input changes here.

Human required the real configured Kronos GUI on the visible desktop. An early
sandbox launch was invisible to the human; it is not the accepted run. Use
`launch.ps1` outside the restricted desktop, with the configured executable and
the isolated disc. No copied emulator, settings or global keyboard injection.

The first pose reset also used eye height as feet height, leaving Link falling.
The human correctly caught this. Opus's small `L` HUD uses eye/collision Y;
`L 37,275,4353` means feet `(37,185,4353)`. The final control HUD labels FEET
explicitly and the reset accepts feet Y. Final verification settles at Y185;
four normal jump steps raise feet to Y212. The GUI is left grounded at
feet `(37,185,4353)`, with close camera `(-91,262,4320), yaw13714, pitch-1820`.

Build/checks:
- WSL `--quick OOT_CORE=1`; old WARP_PROBE HUD disabled. `.bss` ends at
  `0x060829B0`, 5712 bytes below SGL. Heap and actor capacities unchanged.
- Mailbox uses 4164 bytes at low-RAM offset `0x1D800`, bounded by the existing
  gear/save allocations. New diagnostic disassembly has no wide/float helper
  references; existing arithmetic migration debt is unchanged.
- Two ten-step walks from the same grounded pose produce identical Link and
  camera positions, patch world/view corners, command words and texture hashes.
  Endpoint: feet `(26,183,4350), yaw46484`; camera
  `(-167,272,4300), yaw13714, pitch-1820`. A separate settle/jump check passes.
- Actual `slGetMatrix` and `slCalcPoint` are captured at forest submission.
  Host reconstruction agrees within 0.02 units in both camera modes. Commands
  are read after synchronization for the preceding submission, with all four
  corners, attributes, bindings and address-match multiplicity retained.
- Clean/Debug ISO hashes, Opus's four runtime source files and `SAR0.STM`
  remain unchanged. The main tree's earlier stick-chord edit remains separate.

All ten children now have source IDs and stable keys from exact world corners.
Representative frozen-pose records (depths rounded to nearest unit):

| Source / child key | Close OoT view Z | Matches | Far LEGACY view Z | Matches |
| --- | --- | ---: | --- | ---: |
| 738 / b57ca7be816e | -480,87,-97,-97 | 0 | -405,199,-16,-16 | 1 |
| 738 / 968f4e5cad91 | -480,271,87,87 | 0 | -405,414,199,199 | 1 |
| 746 / 3be87c80607e | -97,87,675,675 | 0 | -16,199,803,803 | 1 |
| 613 / 85c9462c084e | 1093,-97,675,675 | 0 | 1193,-16,803,803 | 0 |

Close pose is the camera above. Far pose is `(-214,235,4282), yaw13714, pitch0`.
In this reproduction, LEGACY really has pitch 0 and negative transformed corner
depths. A downward-looking sloped field does not establish a pitch-trace bug.
The earlier claim that LEGACY depths must be wrong is superseded. Close results
still fit rejection, but the far matching commands argue against the universal
"any corner behind means whole face rejected" explanation. Source-address
matching is still not a direct SGL per-face acceptance flag; keep that limit.
Both source-745 children have all corners in front yet no matching command,
so near depth alone cannot explain every omission.

Next at that control-only checkpoint: inspect the installed SGL near/screen/backface decision and emitted corner
mapping for these exact children. Keep geometry, texture density and global
near settings fixed until that trace supports one local correction. No warp
fix, performance improvement, LOD seam acceptance or Clean promotion is claimed.

Evidence lives in `game/build/astra-control/verification/`: `build.json` records
artifact/tool hashes and flags; `summary.json`, `walk-0.json`, `walk-1.json`,
`oot.json`, `legacy.json`, `oot.png`, `legacy.png` and `preserved.json` record
the final checks. Older early-run artifacts are not the accepted verification.

Commands from repository root (Windows host; GUI access outside restricted
desktop). `prepare.py` refuses an existing snapshot. Close the controlled GUI
before rebuilding its mounted disc; preserve other sessions.

```powershell
# Prepare once; then run the generated build script in WSL.
python game/tools/control_probe/prepare.py
wsl.exe -e bash /mnt/d/Workspace-Claude/saturn-homebrew/oot-sat/game/build/astra-control/build.sh
powershell.exe -NoProfile -ExecutionPolicy Bypass -File game/tools/control_probe/launch.ps1
python game/tools/control_probe/control.py status
python game/tools/control_probe/control.py pose --pose 37 185 4353 13714 --camera -91 262 4320 13714 -1820 --legacy 0
python game/tools/control_probe/control.py step --steps 10 --stick 128 190 --buttons b
python game/tools/control_probe/control.py trace --out game/build/astra-control/verification/current.json
python game/tools/control_probe/control.py capture --out game/build/astra-control/verification/current.png
python game/tools/control_probe/replay.py
```

## Local TR implementation checkpoint and square plan

2026-10-05, Astra. Human requested stopping further renderer changes after
"It look really good" and planning square retopology with new collision.
[FIELD_SQUARE_RETOPO_PLAN.md](FIELD_SQUARE_RETOPO_PLAN.md) is the next plan.
No square retopology or collision replacement has been built.

The final controlled candidate is preserved as a complete runnable disc at
`game/build/astra-control/checkpoint-2026-10-05/game.cue`, including all five
audio tracks, ELF/map, source snapshot and verification. ISO SHA-256:
`49bbf7343ce73c02ab31c32ac8f420eb0b15f63fb10e7dc73d4da5f4ed982858`.
`checkpoint.json` records payload/source hashes and unchanged baseline files.
Clean/Debug ISO hashes, Opus's four probe source files and the Field STM match
the preserved baseline. Human subsequently requested a local commit of the
source, tools and notes; runnable images stay in ignored build directories.
The real configured Kronos GUI is
left visible, grounded at feet `(37,185,4353)`, candidate mode 2.

### What is implemented

Only the same ten P3 children from sources 746/613/738/745 use the local raw
sprite path. Exact world corners identify them, independent of VRAM slots.
Offline validation scans every STM piece/LOD and rejects duplicate matches,
unexpected materials, winding or a scope change. Other geometry and collision
remain unchanged. `slCalcPoint` supplies the actual view transform; `slSetSprite`
retains SGL's sort/command/DMA backend. Projection clamps to ±288/±248 for the
320x240 image, with homogeneous side rejection and original Single_Plane culling.

Ordinary faces choose 1/4/16 cells. Only near/guard boundary cells can descend
two further levels, after offscreen children are removed, with a hard 16-leaf
limit per P3 child and 160 total commands. This is a deliberate departure from
the earlier two-level-only proposal: that version left large holes during
turns. This is still ten local inputs, not a runtime world grid. Near-crossing
leaves are dropped at the final bound; no universal hole-free guarantee.

Immutable texture pyramids resample existing parent palette indices. No new
material colours, runtime texture writes, sprite slots or CLUTs. Added bank:
76,800 B; combined reported Field budget 350,112/445,432 B. Geometry residency
stays 727 faces/1162 vertices, 723 slots. At most 150 extra commands relative to
the ten original children; actor allowance remains 704. Target build margin:
1,632 B below SGL. Scratch is bounded inside the existing low-RAM gap, separate
from mailbox, gear and save storage. New transform/projection/constraint paths
have no wide or float helper references in the SH-2 disassembly; old collision
and follow implementations still contain wide-math migration debt.

Main camera source now constrains ordinary follow in both camera modes, including
spawn placement. Previously the ray only constrained traversal transitions.
Ground preserves the requested age/profile height plus pitch rise beneath the
desired eye; walls/ceilings shorten the arm. If terrain raises the eye, the view
turns down toward Link. Simply shortening at a floor hit had left the camera
about one unit above a slope. Tests cover both ages/modes, ignore flags, walls,
slopes and the real Field collision at the recorded corner. Host: 18 camera and
25 follow cases pass. Main Clean ELF boundary: 6,160 B; its existing ISO is not
replaced. The candidate disc includes this camera correction.

### Evidence and limits

`verification/tr-v10/` contains 22 real-window captures and command traces:
11 baseline/candidate pairs, same Link positions, camera matrices and all ten
resident children. Tests include close OoT/far LEGACY, three normal walk
increments, corner/centre standing, jumps and turns. Streaming is warmed before
each pass to avoid comparing different LOD histories. Adult/All Items enabled.
Peak captured commands: 628, below the 2,456 reserved command slots.

The geometric mapping proxy at the original close pose improves from mean
26.615 parent texels to 2.758; centre 17.435 to 0.760. These are errors computed
from emitted corners, not a percentage measurement of visible motion. Lower
viewport coverage checks show no uncovered samples in eight candidate poses;
three others retain 3, 6 and 22 samples after a one-pixel tolerance. That is not
proof of zero cracks or correct occlusion everywhere. Major missing-floor cases
improve and the human reports the current look is good.

Cost remains significant. In a paired 0/2/2/0 run, baseline 90-step walks take
4.735 s; candidate 7.312/7.265 s (about 54% longer), with identical endpoints.
Static cached rendering is approximately 29 frames/s in both modes. This is
controlled-emulator wall time, not a Saturn hardware timing guarantee. Do not
use the static FPS or HUD percentage to claim a free fix. The requested square
bake should reduce the need for expensive runtime work.

Earlier variants are retained as evidence, not recommendations: clamping
behind-eye cells before preserving sidedness could cover Link; dense uniform
base grids cost about 72% longer walking; the smaller two-level-only version
cost about 21% but left turn holes. Final boundary-only refinement restores
most coverage while retaining the 160-command cap. No distant or LOD face
replacement was made, and the preexisting chunk/LOD seam has not been accepted.

BR review is in [BURNING_RANGERS_POLY_NOTES.md](BURNING_RANGERS_POLY_NOTES.md).
Its small regular geometry is useful evidence for the next experiment. The
20x20-cell depth ratio is an example, not a proven bound for all BR faces; the
static study does not prove holes are invisible. Likewise our missing faces
cannot all be attributed to whole-face near rejection: actual SGL near/XY
handling, authored backfaces and a below-ground camera all contributed.
