# Near-camera warping: cause and texture-path plan

## What the warping actually is

Measured, not inferred. A checkerboard diagnostic (`build_sgl_scene.py
--diagnostic-tiles`) renders with square, unfolded, unrotated cells at every
distance — near ground and far treeline alike. That rules out corner ordering,
near-plane clipping and sliver geometry as the cause, and it matches the report
that the distant treeline warps too: the problem is not distance-dependent.

What is left is **texel density**. Every triangle carries its own baked tile,
16 or 32 texels across, regardless of how large the triangle is in the world:

| | world units per texel |
| --- | --- |
| median face | 14.0 |
| 99th percentile | 56.7 |
| worst face | 86.5 |

Link is 62 units tall, so on the worst faces a single texel is taller than the
player. Real artwork cannot survive that magnification; the checkerboard only
survived because its features are 4 texels wide.

Two claims made during the investigation were wrong and are recorded so they
are not repeated: a supposed 90-degree mismatch between the bake's degenerate
axis and the quad's (disproved — the two agree at every corner and at the
centre), and a supposed sprite-size packing bug in `kokiri_sgl.c`
(`(w & 0x1f8) * 32` equals `(w >> 3) << 8` for every width we use).

The checkerboard establishes texel density as a serious problem. It does not
prove no mapping or clipping issue exists for real artwork, and the plan below
keeps the current path available while the new one is proven.

## Why the obvious fixes do not fit

| approach | needs | available |
| --- | --- | --- |
| subdivide ground only, 400-unit limit | 3,683 polygons | 2,600 |
| uniformly larger tiles, 14 units/texel | 1,516 KB | 455 KB |

The per-face bake is itself the limit: 2,060 faces use 1,801 *unique* tiles,
spending 369 KB of VDP1 VRAM to buy 16 texels across per triangle.

## The waste, and the opening

The forest's real artwork is **54 distinct textures totalling 35 KB at 4bpp** —
about a tenth of what the bakes of it cost. One texture is used by 343 faces.
VRAM was never the constraint; the per-face bake was spending it badly.

Triangles also rejoin: **915 of a possible 1,030 adjacent pairs** share an edge
with identical UVs and recombine into their original quads, taking the scene
from 2,060 triangles to 1,145 polygons.

## Plan

Not one technique for every face. Three, chosen per quad:

1. **Direct** — quad whose UVs are an axis-aligned rectangle covering the
   texture once. Draw it as a normal sprite against the shared texture.
2. **Split** — quad whose UVs are rectangular but repeat. Repeats are almost
   all horizontal with integer factors (2x, 4x, 6x, 8x), so the quad is cut
   into N sub-quads that each draw the texture once. No wrap hardware needed
   and full texel density is preserved.
3. **Bake** — quad with genuinely skewed UVs (282 have four distinct s *and*
   four distinct t, so they are arbitrary, not rotated rectangles). These keep
   the existing per-face bake, sized by how large the face is rather than
   uniformly.

SGL/VDP1 exposes no arbitrary per-vertex UVs, so source UVs are preserved in
the converter and mapped into these Saturn-compatible forms rather than being
handed to the hardware.

## Budget

| | value | budget |
| --- | --- | --- |
| polygons, scene | 120 direct + 788 split + 892 baked = 1,800 | |
| polygons, scene + Link | **2,260** | 2,600 |
| shared textures | 40 (28.0 KB) | |
| bakes: 120 worst at 64x64, rest 16x16 | 364.4 KB | |
| VRAM, scene + Link | **444.4 KB** | 455 KB |

The 120 worst faces get 64x64 bakes — 16x their current density — paid for by
sharing 40 real textures instead of baking 1,801.

## Order of work

Prove one ground patch and one treeline patch through the new path first, shown
while approaching and turning, with real polygon and VRAM totals including
Link. Extend across the forest only once that reads correctly. The existing
per-face path stays as the fallback throughout.

Representative patches identified:

- **treeline**: 2,799 units, 64x64 texture, UVs `s=-256..256, t=0..64` —
  rectangular, repeating 8x horizontally, so it is a *split* case.
- **ground**: 1,973 units, 32x32 texture, skewed UVs — a *bake* case.


---

# Historical handoff to Astra (Opus, out of context; superseded below)

Branch `fix/near-camera-warping`, nothing committed. `LICENSE` is the human's
own edit; leave it. 39 game tests pass and both builds are clean.

## What is established

The cause is settled and is **texel density**, not clipping or corner order.
Evidence is the checkerboard above. Treat the checker as supporting evidence
only: it does not prove clipping can never contribute for real artwork.

Two of my claims were **disproved** and must not be revived: a 90-degree
bake/quad mismatch, and a sprite-size packing bug in `kokiri_sgl.c`.

## What exists, untested at runtime

- `game/tools/vdp1_budget.py` — enforced budget. Counts pixels, the 32-byte
  CLUT per tile, 8-byte alignment, a command reserve and Link. **Check its
  `COMMAND_RESERVE`**: I was about to verify whether the SGL command table
  really lives in the VDP1 texture user area or in SpriteBuf (sized by
  `build_sgl_area.py` as `72*(MaxPolygons+5)`). If it is SpriteBuf, the reserve
  is wrong and ~90 KB comes back, which changes every number below.
- `game/tools/build_quads.py` — rejoins triangle pairs and classifies each quad
  DIRECT / SPLIT / BAKE. Verified on the real scene: 49 direct, 80 split,
  1016 bake, 1352 polygons, 22 shared textures. `subdivide()` is written but
  **never rendered** — the treeline split path is unproven.
- `--diagnostic-tiles` in `build_sgl_scene.py` — the checkerboard. Keep it.
- `--flat` in `build_link_model.py` — collapses Link to flat colours except
  eyes/mouth, per the human's instruction. Works (423 faces) but only saved
  62.3 -> 55.8 KB, because `bake()` still emits one tile with a full CLUT per
  face. **Next step there: make flat faces share tiles.** 357 tiles currently
  have 357 distinct contents, so dedup as written saves nothing; the fix is to
  emit one shared tile per distinct colour instead of one per face.

## The open problem

Budget does not close yet. Best fit found was 389.4 KB against 374.8 KB
available, i.e. ~15 KB over, and only by dropping all 64x64 bakes — which
defeats the purpose, since the 120 worst faces are the ones that smear.

Levers, in the order I would try them:
1. Resolve the `COMMAND_RESERVE` question above. Largest single swing.
2. Share flat Link tiles by colour (should take Link well under 20 KB).
3. Density-target scene bakes (`size_for(span, target)`); 30 units/texel was
   the closest fit.

Nothing has been rendered through the new path yet, so the human's requirement
— one ground patch and one treeline patch shown while approaching and turning —
is **not met**. The existing per-face path is still what the game builds and
runs, and remains the fallback.

---

## Astra implementation — 2026-09-16

The hybrid path is now wired into the game, not just a classifier. Earlier
budgets/classification counts above are historical. Nothing was committed in
this pass; the human's `LICENSE` edit was preserved.

### Corrections established during implementation

- **Density was real, but not the complete cause.** The moving close-treeline
  probe made the old path disappear completely despite `rej 0`. Splitting the
  repeating surfaces, then halving their tall edges, retained the trees during
  that same approach/turn path. Therefore the checker did not rule out coverage
  problems. No claim is made that SGL's internal clipping algorithm was traced.
- A Work RAM `SpriteBuf` does **not** remove the VDP1 VRAM command table.
  Local `LIBSGL.A` disassembly of `slInitSprite` writes commands at `0x25C00000`.
  [Sega's VDP1 command-table specification](https://docs.exodusemulator.com/Archives/SSDDV25/segahtml/hard/vdp1/hon/p05_40.htm)
  specifies 32-byte boundaries and fetching from VRAM offset zero.
- The old budget double-subtracted a command reserve from an already-offset
  texture area. Also, Jo's nominal `0x71D38` user-area size disagrees with its
  physical start/end. We now reserve `2600*32 + 8192` bytes from VRAM offset zero,
  start textures at `0x16500`, and stop at `0x7FEF8`: **432,632 bytes** available.
  Build and runtime consume the same generated `vdp1_layout.h`. The CPU SGL work
  area was not changed. Its CommandBuf sizing caveat remains.
- Safe joining checks full sampler/material state, shared attributes, winding,
  convexity and coplanarity. Not all 915 proposed pairs are safe. UV scale/shift,
  origin, mirror/clamp and transposed axes are respected. Split tiles sample
  texel centres rather than repeating the first texel at the last column.
- Link's last uncommitted exporter had shadowed its texture byte buffer with a
  dictionary and still wrote 16x16 descriptors for smaller tiles. Both fixed.
  Flat lit colours now share **8x2** tiles; eyes/mouth retain their textures.
  Signed normals are interpolated as signed values, not wrapped colour bytes.

### Delivered path and budget

`build_hybrid_scene.py` calls the existing verified source extractor, joins safe
pairs, splits repeating rectangles, and bakes skewed mappings with directional
density budgeting. Deduplication savings are spent on walkable ground near the
starting area. Fifty nearby large ground surfaces are subdivided four ways;
this is capped, not a forest-wide polygon explosion. Original triangle UV and
lighting interpolation is retained in quad bakes. Shared tiles use coarse
per-surface static lighting rather than unique per-repetition shading gradients.

| Resource | Forest | Link | Combined / limit |
| --- | ---: | ---: | ---: |
| Polygons | 1,986 | 460 | 2,446 / 2,600 |
| Vertices | 1,790 | 322 | 2,112 / 2,500 |
| Texture tiles | 1,560 | 95 | 1,656 slots including slot zero / 2,400 |
| Pixels + CLUTs | 417,408 B | 7,880 B | 425,288 / 432,632 B |

Texture margin is **7,344 bytes**, after the separate command reservation.
Both normal gameplay launch images build successfully. Hi-res `.bss` ends at
`0x060A1040`, **25,024 bytes** below the unchanged SGL work area.
No collision, movement, title/music or SDK source changes. Y conversion remains
only in the generated POINT table. The budget fails rather than silently dropping
faces or overflowing VRAM. Texture offsets and blob lengths are aligned to eight
bytes and dimensions/byte counts validated.

The manifest also exports connected render-component IDs and bounds. This is
the starting point for the human's hut/tree visibility request. It does not yet
name objects or toggle rendering; collision stays whole and resident. Do not
submit each future chunk against the entire scene vertex pool again.

### Focused verification and reproduction

52 game tests pass, including UV-axis splits, shifted/clamped sampling, winding,
nonplanar/material join rejection, ground subdivision, small Link descriptors,
and hard budgets. Existing baseline asset tests remain in place.

`./build.sh --hires TEXTURE_PROBE=1` runs an approach and turn at:

- Ground: original source faces **377/378**, around **(-294, 0, 132)**.
- Treeline: source faces **1393/1394**, around **(-37, 746, -1761)**.

These are source coordinates. The ground probe was deliberately moved from a
remote largest face to the playable spawn area. Title/Link hiding applies only
to the optional probe. Rebuild without that flag to restore normal play.

Local, ignored window captures under `game/build/generated/`:

- `legacy-probe-*.png`: old path on the same camera trajectory; near treeline
  disappears, though submissions are accepted.
- `bounded-later-*.png`: vertical splitting retains the treeline on approach
  and turns, with zero submission refusals.
- `acceptance-sweep-*.png`: final density + ground-subdivision path.
- `gameplay-standard-final-1.png`: normal camera, Link and forest bank restored
  after title transition, movement and turning in the standard-resolution build.
- `gameplay-hires-final-1.png`: restored normal hi-res gameplay, Link visible,
  title dismissed and forest bank selected. Both launcher images now contain
  the hybrid assets and normal gameplay, not the probe override.

All **2,060 original source faces** are represented in the manifest; no faces
were silently dropped to close the budget. The manifest currently contains
**74 connected render groups**. These are geometric components, not guaranteed
one-component-per-hut semantic objects.

Do not turn emulator FPS overlays into a performance claim. This is a focused
visual check, not hardware validation or proof that every near-plane crossing
in the forest is perfect. Remaining coarse distant bakes/affine distortion must
be distinguished from the severe old smearing; human playability feedback still
matters. Preserve the legacy path with `TEXTURE_PATH=legacy`.
