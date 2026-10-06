# Field ground square retopology plan

Current scope update (2026-10-05): human authorized usual Clean promotion and
wider Field coverage. Central 184 patch stays; outer ground now receives
coarser visual subdivisions on unchanged source planes/collision. Fine uniform
whole-map cells exceed current Link/owl budgets. See FIELD_SQUARE_RETOPO_STATUS.md
for the selected 1280-unit outer grid, capacity evidence and remaining human
checks. The local-only requirements below describe the original central patch.

2026-10-05. Human requested stopping the current renderer work, preserving its
good visual result, and planning square ground topology with matching collision.
The accepted checkpoint is local commit `c2655b2`. A concurrent uncommitted
retopology draft now exists in the shared tools and mesh bundles; its presence
does not establish host, target or runtime acceptance. This review verifies the
baseline collision and updates the requirements below, without changing that
draft. Ground coverage and stable texturing take priority over exact texture
appearance.

## Starting point

The current local TR experiment is saved with its full runnable disc, all five
audio tracks, source snapshot and measurements in
`game/build/astra-control/checkpoint-2026-10-05/`. Its `game.cue` is the rollback
image. The working controlled image remains under `build/astra-control/oot-sat/`.
Usual Clean, Debug and Opus's probe are preserved. Main source contains the
camera correction; the local renderer remains isolated.

The human says the current result looks really good. It is not a complete
performance or seam acceptance: matched 90-step walking takes 7.265–7.312 s
against baseline 4.735 s, about 54% longer. See
[TOMB_RAIDER_POLY_NOTES.md](TOMB_RAIDER_POLY_NOTES.md) for the captured evidence.

The sharp triangle fans are a plausible remaining contributor, especially when
encoded as collapsed textured quads. Squares do not make perspective correction
automatic. Face depth span, camera clearance, projection and sorting still
matter. The experiment must test topology independently before replacing the
current renderer.

## Scope and geometry

Start with the selected ground fan in ROM object 17 and only the directly
adjacent ground needed to close its boundary. Retain object/source provenance
for sources 746, 613, 738 and 745 in pieces 33/34. Map their complete Workshop
groups before choosing the exact patch outline. Do not expand to distant groups,
walls, thin cliff strips or the whole Field.

1. Export a preview of the original ground, collision, object boundaries and
   streaming/LOD boundaries. Mark walkable slopes, curbs, cliffs, doors and
   actor/trigger anchors. Visual object IDs are not collision polygon IDs;
   establish that correspondence geometrically.
2. Fit gently simplified planar ground panels, preserving important ridges and
   walkable connections. Tile each panel in its own plane with equal-sided,
   right-angle squares. Measure side lengths, angles, planarity, height error
   and area. Four arbitrary corners, a skewed diamond, or independently lifting
   an XZ grid's corners is not sufficient to call a face a square.
3. Price 256-, 128- and 64-unit square candidates offline. Start with 128 as a
   budget hypothesis, not a decided quality level. Compare camera-depth spans
   and visible density at the recorded test routes. Do not split every distant
   triangle to the smallest size.
4. Reconcile panel and patch borders explicitly. Perfect square tiles cannot
   exactly cover every curved slope and irregular hexagonal boundary. Show any
   small terrain adjustment or limited transition strip in the preview; list
   exceptions rather than hiding new needle triangles. Preserve the outer
   shared positions, cliff height and traversable connections. No overlapping
   coplanar skirts or transparent texture tricks to conceal open seams.

## Preserve squares through the importer

`map_meshes.replacement_faces()` currently turns authored quads into triangle
pairs and relies on later joining. Add an explicit quad-preserving route for
this named layout variant. Four distinct welded corners must reach the final
STM and VDP1 command. Validate winding, nonzero area, no bow ties and no
collapsed C=D corner. Do not replace one fan with many smaller fans.

Use the existing immutable mesh bundle and layout selection workflow. Extend its
schema for the collision replacement and source hashes. The uncommitted draft
adds a `patches` route and both collision hooks; validate those changes before
accepting them. Keep ROM inputs immutable and leave the default build selection
unchanged until a concrete variant is ready.

## Existing texture bake

Reuse the present Field grass/ground texture sources and colours. No new art,
runtime texture painting or material redesign. Prefer a consistent world-space
repeat across adjacent squares over reproducing each stretched triangle's UVs.
Bake each square through the existing palette/4bpp pipeline, deduplicate equal
tiles and share compatible CLUTs. Neighbouring squares must sample the same
shared edge; slight resampling or orientation differences are acceptable.

Report actual tile dimensions, slots, palettes and VRAM bucket peaks after the
bake. Do not assume splitting preserves pixel bytes or density. The current
76,800-byte runtime pyramid bank is a comparison cost, not an allocation the
retopology must retain.

## Collision from the same surface

Generate collision from the final welded ground mesh. A square may use one
render quad and two collision triangles with a consistent diagonal; collision
triangles do not recreate the visual fan. Remove the replaced original ground
collision so no hidden old surface fights the new one. Recompute normals,
bounds and the collision index.

Preserve original surface types, camera/entity/projectile ignore bits,
conveyors, floor sounds, damage, water, camera records and other gameplay
metadata. Keep walls and unrelated collision unchanged. Split patches at a
surface-behavior boundary instead of averaging its flags.

Audit every consumer: the C `SA.COL` bank and the oot-core `SA.OOC` scene collision
payload must describe the same replacement. Updating only the visual STM or
only one collision backend is incomplete. The current `SA.COL` has 1,579
triangles; the baker's 2,321-triangle limit leaves 742 net additions before other
limits. Replace and count, rather than merely appending another mesh.

### Collision review, 2026-10-05

Astra independently repeated Grok's baseline comparison: all 1,579 ordered
triangles, source-derived Q14 normals and info words match `SA.COL` against the
extracted PolyList/VtxList (1,162 vertices). The bank is 60,636 bytes, with 61
surfaces, six waterboxes, four camera records and no camera vectors. Reproduction
and hashes: `game/build/astra-control/verification/field-collision-review/`.

Decoding the staged 40,128-byte `SA.OOC` also gives identical ordered positions,
polygon info and surface words. However, 786 triangles have at least one normal
component differing by one Q14 unit after conversion from their compiled Q15
normal. Source-text reconstruction is therefore not byte-exact compiled-payload
parity. This is a baseline difference, not evidence of a retopology regression.
For new faces, derive Q15 normals and plane distances from the welded integer
geometry once, and define the Q14 conversion explicitly for the COL serializer.
Compare decoded outputs with the chosen quantization rule and verify floor/ray
behavior; preserve unaffected records in each backend. OOC plane distances match
the extracted source in this audit; water and camera payload parity was not
independently decoded here.

The original four-face correspondence is:

| Visual source | Original STM piece/face | Collision polygon | Vertex indices |
| --- | --- | --- | --- |
| 746 | 33/8 | 597 | 223, 367, 227 |
| 613 | 33/6 | 436 | 223, 227, 226 |
| 738 | 34/1 | 589 | 367, 223, 368 |
| 745 | 34/5 | 596 | 370, 227, 367 |

These four polygons use surface 5, words `(0, 0xFC8)`, grass, with no ignore or
conveyor bits. Seven collision polygons meet at `(0,320,5100)`: 589 and 592–597.
Polygons 590/591 are the west pair, not additional triangles at that vertex.
At XZ `(60,3367)`, the only nondegenerate projected triangle containing the feet
is 436, with barycentric weights approximately `(0.95924,0.00097,0.03979)`.
The camera test subsequently queries the moved eye's XZ; its hit must be measured
separately. Do not attribute that eye query to polygon 436 from the feet alone.

Curb polygons 598–613 span X `-20..1472`, Y `100..440`, Z `4330..6800`; the
small lip box covers only part of them. Polygon 600 shares `(1472,400,5950)`
with ground polygon 596. All 16 use surface 15 `(0x80000001,0xFC2)` and camera
ignore. Any required edge cut must use that curb polygon's own vertices and
plane, preserving its flags. Do not project these faces onto the ground or
silently omit boundary closure because the camera ignores them. This is local
seam maintenance, not permission to retopologize distant walls.

Field's default-camera BgCheck allocation selects the spot branch: `0xF000`
and subdivisions `16x4x16`. The `0xB798` custom entry is in the non-spot branch
and does not apply. `0xF000` is the allocation accounting budget, not the node
pool size. Node capacity is the remainder after lookup cells, polygon check
bytes, dynamic nodes/polygons/vertices and `sizeof(CollisionContext)`, divided
by `sizeof(SSNode)`. Use actual target types, not N64 size comments or a 64-bit
host ABI, when calculating it. The separate target THA remains `0x30000`.

Count node usage with the real candidate subdivision build and check capacity
before each node write. `SSNodeList_GetNextNodeIdx` otherwise increments with
only an ASSERT, disabled by the current shim unless `OOT_CORE_ASSERTS` is set.
A count check after `BgCheck_Allocate` cannot prevent an earlier out-of-bounds
write. A host probe's larger arena is not evidence of target headroom. Record
both C collision-index capacity and oot-core node/THA usage; the 742 net triangle
allowance alone does not establish fit.

## Streaming and budgets

Bake and validate visual geometry, collision and metadata from one frozen
variant. Stage them together so an old collision bank cannot accompany a new
floor. Hash unaffected pieces, materials and collision records.

Weld shared vertices across pieces 33/34. Inspect both normal and owl resident
sets and every relevant LOD transition. An old far boundary cannot silently
replace the new seam with different heights; retain a common boundary or make
the smallest required adjacent LOD border change explicit. No distant detail
expansion. Test entry from both directions to catch streamer hysteresis.

Measure resident points/polygons, collision and index RAM, sprite slots,
per-size VRAM buckets, actor/owl reserves and actual frame commands. SGL's 3,750
polygon setting is not the 2,456 reserved VDP1 command slots. Do not increase
limits, shrink actor reserves or silently drop faces to make a candidate fit.

## Comparison and completion

First build the local square variant with ordinary SGL projection, preserving
the new camera collision. Compare against both the original P3 geometry and
the saved TR candidate at identical camera/Link states. Keep runtime subdivision
off for this topology comparison; reintroduce a bounded fallback only if the
measurement demonstrates a remaining need.

Replay Adult/All Items in the visible configured Kronos GUI, then check Child
height. Use feet `(37,185,4353)`, `(23,4,3407)` and `(1192,328,4114)`, both camera
modes, small forward motion, turns, jumps and the +Z chunk crossing. Add wall,
ceiling, slope, landing and projectile collision checks. Never compare a falling
pose against a grounded one or different resident LOD sets.

Completion requires a continuous floor with no new cracks, disappearing wedges,
falls through terrain or camera penetration; substantially reduced swim during
small motion; correct actors/surface behavior; and an acceptable measured frame
cost. Texture fidelity is secondary. Record genuine remaining seams and cost,
not only a successful build or a favourable still. Preserve the checkpoint
until the combined mesh/texture/collision variant passes those checks.

Next implementation task: review the shared draft's preview and exact
visual/collision/texture/node budgets, then verify decoded STM/COL/OOC outputs
from the same frozen bundle. The draft currently describes an XZ square grid
whose slope faces are parallelograms. Report actual in-plane angles and lengths;
that construction does not itself satisfy the requested actual-square criterion.
Retain explicit boundary exceptions and resolve curb seams before runtime
acceptance. This collision review does not certify the draft or change the
saved renderer checkpoint.

Draft status and response to the review (Claude, 2026-10-05):
[FIELD_SQUARE_RETOPO_STATUS.md](FIELD_SQUARE_RETOPO_STATUS.md). In-plane
metrics reported (sides <= 4.4%, corners <= 4.3 deg off at 184); one Q15
normal rule for COL/OOC; curb risers 748/750 and walls 782/1039 fanned on
their own planes; node counts measured in the 0xF000 spot branch.
