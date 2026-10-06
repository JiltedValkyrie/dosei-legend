# Field landmark retention audit — 2026-10-05

Current request promotes retained landmarks into Clean, adds the complete ranch
enclosure and castle entrance walls, and uses SORT_MIN to avoid depth overflow.
Human owns runtime checks; no far-landmark acceptance yet. See RECOMP_PLAN.md.

Latest blocker: SGL SORT_CEN sums four Q16 depths in signed 32 bits before
dividing by four (v2 MsSBase_CEN 0x06063A58, CEN_N 0x06063B50). The sum
overflows at mean z8192. Far mountain faces at z12615-13869 wrap negative;
the later unsigned Zlimit check can reject them. Default slave Zlimit is32767,
so increasing a window far limit alone does not resolve this. SORT_MIN/MAX
avoid this sum; tagged landmarks now use SORT_MIN. Preserve ordinary occlusion.
Central castle projects to x139-181/y103-129 at z8139, below the threshold;
its smaller captured appearance still needs the v3 targeted command trace.
Evidence: `build/verification/landmarks/source-textures.png`,
`build/square-retopo/r2-184/verification/environment-v2b/central-castle.*`
and `far-mountain.*`. These captures precede the sorting fix.
Source is the extracted NTSC 1.2 Field
room, decoded with the existing `build_hybrid_scene.load_faces` converter.
The texture contact sheet and numeric sizing are under
`build/verification/landmarks/`. These are source face IDs, not runtime polygon
indices, sprite slots, or streaming-piece IDs.

## Implemented candidate

`build_field_chunks.py` now emits four always-resident landmark pieces
(`kind=4`, reserved piece `pad` bit 0 set, near 0/far 65535). The KRM2 version
and struct sizes are unchanged. Their 313 source triangles become 185 draw faces
with 182 independent 16x16 tiles/CLUTs (29,120 bytes before resident removals).
The same source IDs are removed after normal/retopo conversion, and excluded
from the top-down LOD2 input. A missing/mixed source mapping or competing
Workshop LOD override fails the bake. Mountain body uses opaque cutouts;
source smoke keeps authored mesh transparency. A separate pool policy prevents
landmark tiles from sharing fog palettes with terrain.

Current central184 + outer1280 + retained walls sweep passes in both modes:
1249 Field polygons, 1732 vertices, 61 pieces, 1255 slots and 331776/445432 B.
Latest Clean orbit/fade follow-up passes with608 B static RAM spare; staged/ISO landmark counts
and geometry/collision/core bundle pairing match. Runtime wall coverage and
occlusion remain unverified. Human's new world-space dither curtain sits at3200
units and can cover parts of more distant landmarks; retention and ordinary
world depth ordering stay active. Dark sky gradient is human-accepted.

Earlier isolated184 candidate sweep passed in normal and owl modes: 1,023 polygons, 1,478
vertices, 60 pieces, 1,042 slots, 340,512 / 445,432 bytes including existing
actor/effect reserves. Previous values were 993/1,440/59/1,003/334,272. This
is table/residency sizing, not measured frame-command cost. Existing generated
vertex (2,047), polygon (1,916) and tile (1,426) capacities fit; object capacity
was increased from 59 to 60 in the staged image.

Four landmark tests and eight stream tests pass. The actual ROM count, material
policy, palette isolation, complete near-original removal and persistent
residency are checked. Same-host content comparison preserves every unrelated
full-detail face/texture: 54 old hero faces removed, 50 retained faces added;
two LOD2 faces change and five disappear in that Windows comparison. The final
canonical WSL comparison has two changed and seven removed LOD2 faces.
The Windows Python 3.12 baseline differs from the saved WSL bake at ten unrelated
texture sampling boundaries, so use canonical WSL for the image and final freeze
comparison. No geometry/normal/material/size differences occur at those ten faces.

Candidate artifacts and standalone runners are under
`build/environment-landmarks/`. `bake.py --game <isolated-game> --stage` writes
only that isolated image's STM, Field sizing report, manifest row and capacity
header. `freeze.py` compares decoded full-detail content, ignoring pool IDs.
Those isolated artifacts are historical. Main now selects `field-square-184`
and the requested ordinary Clean rebuild regenerates its assets.

## Identified source geometry

| Landmark | ROM object | Source faces | Evidence |
|---|---:|---|---|
| Death Mountain | 6 | 310–319 | Mountain textures `0201F198`, `0201E998`; smoke `0201F598` |
| Hyrule Castle distant card | 35 | 1631–1632 | Castle silhouette texture `02014D98` |
| Market building cards before castle | 35 | 1633–1638 | Building texture `02026998` |
| Lon Lon Ranch buildings/fences | 5 | 244–309 | Barn, roof, tower, gate and fence textures |

Object 5 faces 161–243 are surrounding mound/wall geometry, now retained with
the ranch landmark. Castle wall object34, faces1485–1630, is also retained.
Within the selected ranch range: 244–251 are the
entrance facade; 252–283 the main building and roof; 284–291 the tall stone
tower; 292–297 the distant low structures; 298–309 fence/gate detail. Labels
come from decoded geometry and texture appearance, not symbol names.

Source bounds (X/Y/Z): mountain `(4590,549,-1368)` to `(6415,1356,1573)`;
castle/market `(-720,-23,-1811)` to `(720,866,360)`; selected ranch
`(-4320,100,5712)` to `(-1605,673,8038)`.

The mountain object's source translucent flag is set on every face. Mountain
body textures have only alpha 0/255; smoke has intermediate alpha. Therefore
clearing distance dither alone still leaves the converter's authored MESHon
on the mountain body. Treat opaque cutout coverage separately from actual
smoke translucency; do not clear every authored mesh flag globally.

## Why a fog exemption alone cannot work

The existing Field report contains 116 pieces: 59 full cells and 57 top-down
LOD2 cells, with no object LOD0/LOD1 pieces. `build_field_chunks.py:build_pieces`
puts every untagged object into 2048-unit cells. Beyond the full ring (1536,
plus swap hysteresis), the originals are replaced by 2x2 heightfield quads.
Vertical castle and mountain cards cannot survive that top-down replacement.

Relevant sites:

- `tools/build_field_chunks.py:build_pieces` (line 199): select dedicated
  landmark faces before cell assignment; remove the same source faces from
  the `Surface` inputs used for terrain LOD2. Do not duplicate them near Link.
- `tools/build_field_chunks.py:Pool.add` (line 83): deduplication currently
  ignores palette policy. Add a separate palette ownership class for exempt
  landmark tiles, so a shared terrain texture cannot fog an exempt card.
- `tools/build_field_chunks.py:pack`: currently writes zero piece padding.
  A bounded landmark flag can use a reserved field, with loader validation.
- `src/kokiri_sgl.c:field_rebuild` (line 855): carry that flag into the existing
  per-face byte. Existing bits 1, 2 and 4 already have meanings; use a new bit.
- `src/kokiri_sgl.c` lines 1705, 1766 and 1785: object AABB and both partition
  paths independently reject beyond `FOREST_FAR`. All must honor the same
  landmark range; changing only the first front-of-list test is insufficient.
- Lines 1858–1859 and 1936 onward: tile fog uses the nearest visible reference.
  Force exempt tiles clear within their dedicated palette class, never by
  globally clearing a shared ground CLUT.
- Lines 1910–1912: preserve authored material behavior while bypassing the
  distance-MESHon branch for the tagged landmarks.

Use separate always-resident pieces (`near=0`, `far=FIELD_FAR_INF`) for this
small retained set, or one exclusive near/far group if a cheaper ranch mesh
is later added. The full Field diagonal is about 25,475 units; a separately
bounded landmark draw range around 26,000 covers it without increasing terrain
range. Verify projected depth, SGL command emission and visibility from map
extremes; the current 9000 range is insufficient. Keep ordinary SGL depth
sorting so nearer terrain can occlude landmarks. Do not draw them as HUD.

## Offline sizing: retained source version

The existing quad grouping plus normal `render_tile` bake was run only for the
listed source faces. All child tiles are either 16x16 or 32x32. Sizes below
include 4bpp pixels and one 32-byte CLUT per distinct tile, with no terrain
deduplication. No new image or full positional budget sweep was run.

| Group | Source triangles | Grouped draw faces | Unique vertices | Tiles | 16x16 bytes | 32x32 bytes |
|---|---:|---:|---:|---:|---:|---:|
| Mountain, including smoke | 10 | 9 | 16 | 9 | 1440 | 4896 |
| Castle and market cards | 8 | 4 | 12 | 4 | 640 | 2176 |
| Ranch selected range | 66 | 37 | 68 | 36 | 5760 | 19584 |
| Total | 84 | 50 | 96 | 49 | 7840 | 26656 |

Conservative addition to the 184 candidate, before removing the near originals:
993→1043 resident terrain polygons, 1003→1052 texture slots, and
334272→342112 bytes at 16x16 (or 360928 at 32x32), against 445432 bytes.
Adding the existing 704 Link allowance gives 1747 table polygons. This is not
a measured frame-command count or a new all-actor budget proof. Re-run the
normal and owl sweeps after partitioning/removing the original faces, and
include palette class separation and any changed LOD2 tiles.

The 37-face ranch is already a bounded first comparison, so a new billboard
system is unnecessary to begin. If its measured cost is excessive, a separate
far version can target roughly 8–12 flat cards/box faces preserving the barn,
tower and gate silhouettes, baked from existing textures. That is a design
target, not a built or priced result. Keep its near/far members exclusive and
its range independent of fog; do not retain the whole 149-triangle object.

## Related clock/entrance correctness

`recomp.c:take_door` selects `entrance + oot_core_scene_layer()`. That API returns
the layer frozen when the current scene loaded. After day changes to night in
Field, entering the Market can still choose the daytime scene (entrance group
0x033 day versus 0x034 night). The loaded-layer mask used by
`scene_flow_door_at` is correct for the geometry currently loaded and must stay
fixed; it serves a different purpose.

For destination selection, reproduce `z_play.c:Play_Init` using current age,
day time, cutscene setup and the destination entrance's base scene. Also apply
the source destination exceptions: child Field uses the three-stones story
layer; adult Kokiri Forest uses `EVENTCHKINF_48`. Source BGM continuation still
uses the child-day entrance entry except for cutscene layers. Keep a separate
destination-layer helper rather than changing the current-layer API, and test
day→night and night→day crossings while remaining in one Field load.
