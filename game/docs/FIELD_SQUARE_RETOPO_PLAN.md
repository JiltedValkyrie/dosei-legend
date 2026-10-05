# Field ground square retopology plan

2026-10-05. Human requested stopping the current renderer work, preserving its
good visual result, and planning square ground topology with matching collision.
This is a plan only. No retopology, replacement textures or collision rebake has
been implemented. Ground coverage and stable texturing take priority over exact
texture appearance.

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
schema for the collision replacement and source hashes; its current schema does
not already support that operation. Keep ROM inputs immutable and leave the
default build selection unchanged until a concrete variant is ready.

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

Audit every consumer: the C `SA.COL` bank and the oot-core scene collision
payload must describe the same replacement. Updating only the visual STM or
only one collision backend is incomplete. The current `SA.COL` has 1,579
triangles; the baker's 2,321-triangle limit leaves 742 net additions before other
limits. Replace and count, rather than merely appending another mesh.

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

Next implementation task: produce the local square-panel preview and an exact
visual/collision/texture budget. No square mesh or collision bake started in
this wrap-up.
