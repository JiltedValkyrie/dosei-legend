# Jo Engine / SGL Kokiri viewer

Isolated port target for [docs/JOENGINE_PORT.md](../title-screen/docs/JOENGINE_PORT.md).
Renders one fixed, textured Kokiri Forest view through Jo Engine's SGL path so
it can be compared against the unchanged libyaul build in `../title-screen/`.

The libyaul build is untouched. This project only reads its `cd/FOREST.BIN`.

## Build and run

```bash
./build.sh          # converts the scene, compiles, makes game.iso + game.cue
```

Then `run-kronos.bat`. It mirrors `title-screen/run-kronos.bat` (same Kronos
build, BIOS and autostart) so both images are measured the same way.

Requires the sibling Jo Engine SDK at `../../joengine` (bundled GCC 9.3.0,
SGL 3.02j, make, mkisofs, JoEngineCueMaker) plus MSYS2 bash and Python.

## What is here

| Path | Role |
| --- | --- |
| `tools/build_sgl_scene.py` | FOREST.BIN (KFR1 v2) -> SGL `POINT`/`POLYGON`/`ATTR` tables |
| `src/kokiri_sgl.c` | Uploads 4bpp tiles + CLUTs to VDP1, binds them to the tables |
| `src/main.c` | Fixed camera, HUD, `jo_core_run()` loop |
| `generated/` | Converter output (derived, not tracked) |
| `tests/` | Host guards over the conversion |

## Conversion notes

`FOREST.BIN` already stores geometry the way SGL wants it, which is why no mesh
rebuild was needed:

- **Shared vertices.** One 1268-entry `POINT` table, indexed by 2060 `POLYGON`
  records. Jo's `jo_3d_create_mesh()` would have allocated four points per
  polygon; `PDATA` indexes a shared pool instead, so the vertices stay shared.
- **Triangles as quads.** Every face record already repeats its third index as
  the fourth corner, which is exactly SGL's degenerate-quad convention. All
  2060 faces were verified to satisfy this, with no degenerate triangles.
- **Face records are 20 bytes** (`>4HIIHH`), not 16.

Attribute fields mirror `jo_3d_set_mesh_polygon_texture()` in
`../../joengine/jo_engine/3d.c`, with `CL16Look` because the 4bpp tiles use
per-texture lookup tables in VDP1 VRAM (not CRAM colour banks), and `colno`
patched at load time to the uploaded CLUT address. `UseNearClip` hands the near
plane to SGL rather than reusing the libyaul build's CPU clipper.

## Budgets (measured, not estimated)

| Item | Size |
| --- | --- |
| VDP1 user area (`JO_VDP1_USER_AREA_SIZE`) | 455.3 KB |
| 1801 unique tiles, 4bpp | 313.2 KB |
| 1801 CLUTs | 56.3 KB |
| **VDP1 total** | **369.5 KB, 85.8 KB spare** |
| Work RAM used (`.text`+`.data`+`.rodata`+`.bss`) | 719 KB of 1024 KB |

Textures are resident, so no tile streaming is needed. The framebuffers live at
`JO_VDP1_FB`, outside the user area. The 4 MB cart is not required.

Two settings had to be raised from the stock sample: `JO_MAX_SPRITE` (255 ->
1802, one slot per tile plus Jo's reserved entry 0; GCC caught the overflow),
and the texture upload reads straight into VRAM via `jo_fs_read_file_ptr()`
rather than `jo_malloc()`'ing a 313 KB staging copy out of the 384 KB pool.

## Camera

Pinned to `(-300, 91, 0)`, yaw and pitch zero -- the libyaul spawn. That pose is
not hardcoded in the baseline: `kokiri_collision_spawn()` searches outward from
`x=-300, z=0` and derives `y` from the floor plus `EYE_HEIGHT` (90). Replaying
that search over the 1692 collision triangles lands on ring 0 with floor `y=1`.
The baseline's own test suite prints the same `-300 91 0`.

Facing is `+Z`, with `+Y` up, taken from the baseline's view transform
(`kokiri_scene.c`), where yaw 0 leaves the Y-rotation as identity and rotated
`z` is used as depth. At this zero-yaw/pitch pose the viewer applies the exact
view transform `(x - eye.x, eye.y - y, z - eye.z)` directly, converting source
Y-up to SGL Y-down, and sets SGL's screen distance to the baseline's
240-pixel focal distance. The
viewer has no collision yet, so the pose is fixed.

## Status

Built and visually checked in Kronos on 2026-09-15. The fixed view now renders
upright, with textured ground, canopy and the central tree structure. The scene
is submitted as two 1030-face lists sharing the original point table; the initial
single 2060-face submission produced a black viewport.

The final screenshot showed VDP1 58 FPS and VDP2 58/60 FPS. This is an emulator
overlay observation, not a controlled renderer benchmark. Full submission
acceptance, winding/culling, transparency and clipping fidelity still need
verification. See [Claude handoff](CLAUDE_HANDOFF.md) for evidence, known policy
mismatches and next steps. Local screenshot: `generated/upright-check.png`.

## Build-system caveats

The stock `jo_engine_makefile` needs three overrides, all in `makefile`:

1. It compiles objects in place via a `.c.o` suffix rule, which would write
   `.o` files into the shared SDK. Objects are redirected to `obj/`.
2. Its `$(TARGET)` prerequisites are expanded while its own rules are read, so
   redefining `OBJS` afterwards is not enough; the SDK object paths are given
   rules that resolve to the `obj/` copies.
3. Its ISO recipe ends in an undefined `$(ENTRYPOINT)`, and the bundled
   msys-1.0 `sh.exe` mangles the resulting argument list (`Missing pathspec`).
   Recipes run under MSYS2 bash and the ISO is built by an explicit rule.
