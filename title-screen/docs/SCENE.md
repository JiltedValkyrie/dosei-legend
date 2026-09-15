# Scene and camera

## Status

The missing-floor/stuck-camera regression was traced to camera spawn being
inside an assertion: disabling DEBUG omitted the call and left the camera at
`(0,0,0)`. Initialization now calls spawn regardless of DEBUG and stops on
failure. A target-object test checks that the call survives compilation. The
host collision test reproduces blocked movement at zero. Kronos confirmation
of the rebuilt image is still required, including the reported turning issue.

The renderer reached 7 FPS and raised an SH-2 invalid opcode while rotating
without input. The user subsequently reported **no crash on the last run of the
reorganized build**. The underlying intermittent failure remains unexplained;
that successful run has no reported duration or updated FPS measurement. See
[DEBUGGING.md](DEBUGGING.md) for exact addresses and the matching saved build.

## Source map

| File under `src/scene/` | Responsibility |
| --- | --- |
| `kokiri_scene.c` | Disc loading, view transform, sorting, VDP1 commands |
| `kokiri_camera.c` / `.h` | Manual controls and editable speed constants |
| `kokiri_clip.c` / `.h` | Frustum clipping, projection, clipped texture sampling |
| `kokiri_collision.c` / `.h` | Static sphere collision and initial camera position |

`src/main.c` owns title visibility and SMPC polling. Completed controller input
is processed in VBlank-out before another INTBACK request; main consumes a
button snapshot. Audio runs independently in VBlank-in.

## Controls

Start toggles the title. With no manual input, a visible title automatically
yaws 90 angle units per rendered frame. Camera controls work whether the title
is visible or hidden:

| Input | Action |
| --- | --- |
| D-pad | Forward/back and strafe relative to yaw |
| L / R | Subtract/add yaw; both held cancel |
| X / Z | Raise/lower camera |
| Y + Up / Down | Pitch; horizontal movement is suspended |
| C | Level pitch |

Edit `src/scene/kokiri_camera.h`: movement 16, diagonal movement 12, yaw 360,
pitch 240, pitch limit 14500. These are **per rendered frame**, so low FPS slows
controls. Manual speeds were doubled; automatic turning remains unchanged.
Opposite L/R increments pass native tests and compiled SH-2 inspection, but the
user's earlier same-direction observation has not been independently reproduced.

Collision uses a 24-unit sphere swept in steps of at most four units, sliding
along blocked axes. Eye height stays at least 90 above eligible floor surfaces.
The starting position is `(-300, 91, 0)`. There is no gravity, actor collision,
or N64 per-entity collision filtering yet.

## Rendering and assets

The verified **US 1.2 ROM** supplies three Kokiri room meshes: 1,268 positions,
2,060 visual triangles, and 1,692 collision triangles. Coordinates retain their
original scale. `cd/FOREST.BIN` is the version-2 runtime asset;
`assets/generated/kokiri_scene_manifest.json` records its metadata.

The viewport is 320x240. Each triangle is a VDP1 A/B/C/C distorted sprite with a
baked 16x16 or 32x32, 4bpp CLUT texture. Offscreen faces are rejected before depth
sorting; shared vertices are projected once using the SH-2 divider. Original
tiles are retained within a bounded offscreen region. Near-plane/extreme cases
are CPU-clipped and resampled into 16x16 scratch tiles. No flat-color fallback
is active. VDP1 variable-interval synchronization waits for draw completion.

Limits: 3,072 command entries, 256 scratch tiles, 512 KiB VDP1 VRAM. The current
216-view host sweep peaks at 764 draws and 29 scratch tiles. This verifies sampled
memory bounds, not performance or stability in Kronos.

Remaining visual limitations: low-resolution baked tiles, affine mapping,
triangle depth sorting, approximate lighting and meshed translucency. Quad
conversion is not implemented and is not a demonstrated fix for the frame rate.

## Build and tests

From the repository root:

```powershell
python title-screen/tools/build_kokiri_scene.py --oot-root D:/Workspace-Claude/game-decomps/n64/oot
python -m unittest discover -s title-screen/tests -p "test_*.py"
```

Run the Saturn `make` build before the tests so linked audio assets can be checked.
Tests require the local MinGW compiler and extracted US 1.2 audio source.
`tests/test_kokiri_scene.py` can also be run directly to generate the host preview.
It is a reference rasterizer, not a screenshot of VDP1 output.

Superseded implementation notes are retained in [history/SCENE.md](history/SCENE.md).
