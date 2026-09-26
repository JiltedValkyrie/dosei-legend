# Dosei Legend engineering rules

## World coordinates and handedness -- the permanent reference

This is the convention the whole game uses. Get it wrong and the world renders
MIRRORED, which is exactly what happened: every scene, Kokiri Forest included,
was a mirror image of the original until 2026-09-21. Nothing revealed it for
weeks, because a third-person camera in a forest has no absolute reference.
Link's house did: it is a prerendered room, so its backdrop IS ground truth,
and projecting the room's own collision onto it put the door on the wrong side.

### The convention

World space is the ORIGINAL's, straight from the ROM, and is never rewritten:

    +X, +Y up, +Z          right-handed, as OoT stores it
    yaw is binang, 0 looks along +Z, and is measured atan2(dx, dz)

For a camera with forward `f` and up `+Y`, the on-screen right vector is

    right = f x up = (-cos yaw, 0, sin yaw)

Note the signs. At yaw 0 the camera looks along +Z and **screen right is -X**.
Writing `(cos yaw, 0, -sin yaw)` instead -- the negation -- is the mistake that
caused the mirror, and it was made independently in three places: the renderer,
the movement basis and the look camera.

Consequences that follow from it, all of which are now correct:

  * Pressing RIGHT moves Link along `(-cos yaw, sin yaw)`.
  * Looking RIGHT DECREASES the camera yaw, because increasing yaw rotates the
    forward vector from +Z toward +X, which is toward screen LEFT.
  * A vertex baked as `(x, -y, z)` for SGL's Y-down projection is in a
    LEFT-handed space. That flip is why `src/main.c` applies
    `slScale(-1, 1, 1)` before the rotations: it negates projected X once, for
    geometry, Link and billboards together, instead of requiring every world
    coordinate, facing and model vertex to be negated separately.

### How to check it, rather than reason about it

Do not argue from the matrix maths; it is easy to get a sign wrong twice and
convince yourself. Project a prerendered room's real collision triangles onto
its own backdrop and look:

    the exit polygons must land on the doorway
    the collision boxes must land on the bed, the table and the mat

`game/tools/build_scene_backdrops.py --png` writes the backdrop; the room's
collision comes from `shared/tools/build_kokiri_scene.py collision_surfaces()`.
If those line up, the convention is right. If they mirror, it is not.

## New gameplay actors: check original drops every time

Human rule (2026-09-18): add grass, pots, enemies, breakable props, pickups,
or other gameplay actors, check real OoT drop code and tables in same task.
Aim for 1:1 behavior. Visible actor alone not complete.

- Read actor spawn params, drop routine, selected table and collectible flags.
  Follow indirect/random/FLEXIBLE drops into shared item code too.
- Implement source rewards: rupees, hearts, ammo, magic, items, or no drop.
  Match probabilities, quantities, conditions, cut/break/defeat trigger,
  pickup effect, lifetime and respawn rules where applicable.
- Check inventory, health, age, quest and room conditions from source. No
  invented rewards or silently empty slots for unsupported item types.
- Record source symbols and implemented behavior. If hardware or missing
  systems prevent parity, name exact gap in handoff/progress notes; keep it
  pending. Never call a rupee-only subset the full original drop behavior.
- Verify meaningful cases: source table selection, reward/no-reward branches,
  conditional drops and no duplicate collection. Check visible drop/pickup too.

Current grass gap: only rupee slots implemented. Hearts, ammo, magic and
FLEXIBLE resolution still pending; empty slots are a known approximation.

## Renderer repairs: reproduce movement before changing the pipeline

Read [the foreground-warp failure record](game/docs/FOREGROUND_WARP_FAILURE_2026-09-18.md)
before further warp/clipping work. Its prevention rules are mandatory.
Identify the original clipper and preserve a runnable baseline. Trace the exact
bad face during real movement. Change one stage only. Keep experiments separate
from player images. Revert on visual regression; tests and budgets do not prove
playability. Preserve checker mesh. Do not restart the failed material/grid rewrite.

## Every animated model: vertex owns bone, not triangle

Root motion is a separate contract: if gameplay physics owns actor travel,
do not also apply a clip's authored travel to the mesh. Link FALL carried
2292 -> -3328 model-Y translation (~82 world units downward), making a rising
jump look like sinking. FALL now uses idle-reference root translation while
retaining its rotations. Other clips keep their local bob/crouch; do not erase
all root animation indiscriminately. Test visible mesh bounds against collision
origin across transitions, not just that the skinner matches imported tables.

Link broke because extraction ignored **24 G_MTX commands**. OoT Flex display
lists change matrices within one limb list to join vertices to neighbouring
bones. Assigning the whole face to the drawn limb splits boots, joints and neck.

- Capture matrix ownership at **G_VTX load time**, alongside each cached vertex.
  Later matrix changes must not change already loaded vertices. Cache-slot
  replacement must replace ownership too. A triangle can have three owners.
- Reuse `shared/tools/flex_vertex_owners.py` for OoT Flex actors. The helper
  handles verified segment-D model-view LOAD commands, 64-byte matrix slots,
  and rejects unknown commands, bad alignment, missing owners and bad slots.
  This is NOT a general N64 matrix-stack interpreter. Extend with source-backed
  semantics and tests for other formats; never silently ignore actor transforms.
  The base scene reader also rejects G_MTX unless an importer handles it.
- Build the matrix-slot map from the source skeleton's draw traversal, including
  its display-list/LOD rules. Slots are not necessarily limb indices. Check
  `SkelAnime_DrawFlexLod` / `SkelAnime_DrawFlexLimbLod` in OoT `z_skelanime.c`.
- Keep local coordinates and owner together through baking, deduplication and
  skinning. Do not merge vertices just because rounded bind positions match.
  Do not discard tiny animated faces after integer world rounding.
- Compose parent/joint transforms in source order. Apply scale and axis mapping
  once, at the output boundary. Keep fractional Q16 world coordinates.
- SH-2 has **NO FPU**. Runtime uses integer/fixed-point math. Offline tools may
  use floating point. Check target disassembly for software-float helpers.

Required regression checks for new actor importers: mixed-owner triangle,
matrix switch after vertex load, cache-slot reload, invalid command/slot,
distinct locals with coincident rounded bind positions, and actual C skinning
against an independent pose reference. Then inspect actor in motion in Kronos;
host tests alone cannot prove that seams, face, textures or sorting look right.

Current checks: `game/tests/test_link_geometry_precision.py` and
`game/tests/test_link_animation.py`. Actor inspection: `PERF_PROBE=3`; rebuild
without the option before shipping. Other model formats need their own adapter,
not a claim that Link's segment-D scheme fits every model.

## Character textures: face only

Permanent user rule, updated 2026-09-25 (demo plan): hair is flat too. The
2026-09-22 hair-and-face rule and the earlier quarter-resolution rule are
superseded.

- All characters, including Link, NPCs, enemies, riders and horses: remove
  body, clothes, headwear, equipment and weapon artwork; use flat colours.
- Keep face artwork only (eyes, mouth, nose; enemy/boss eyes count as
  face). Faces keep their imported detail. Hair, manes and sideburns are
  flat colours.
- Enforce in the shared offline writer regardless of an importer's
  `full_texture` setting. New importers must mark facial materials (hair still tagged, not kept)
  from source XML, head limbs and expression bindings before writing.
- Unknown head materials conservatively keep facial detail. Named hats,
  hoods, veils and neck materials do not receive the exemption.
- Scenery, UI, title art, effects and non-character props keep their own rules.

Implementation: `game/tools/character_textures.py` and `build_link_model.py`.
The existing KFR1/SGL path represents flat colours with deduplicated constant
8x2 tiles (40 bytes including palette), not body artwork. Hair widths below
VDP1's eight-pixel minimum use repeated columns. No runtime resampling.
