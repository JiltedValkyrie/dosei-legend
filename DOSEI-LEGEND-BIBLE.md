# Dosei Legend engineering rules

## CD filesystem handles: count overlapping lifetimes (2026-09-29)

Permanent rule for Claude, Codex and every agent. The hut-exit failure showed
`jo_fs_get_file_size(): GFS_Open() failed` even with only 40% dynamic RAM used.
Do not diagnose a Jo blue screen as heap or VRAM exhaustion without reading
the actual error and tracing the failing resource.

- Jo's `JO_MAX_FS_BACKGROUND_JOBS` also determines `JO_OPEN_MAX`, passed to
  `GFS_Init`. Its default of one is insufficient for this game's music streaming.
  Keep the project setting at least two; do not restore the SDK default.
- Music retains an LVL or PCM file handle across rendered frames. Count that
  handle while opening scene banks, collision, NPCs, cutscene tracks/clips,
  backdrops or any other asset. Single-threaded calls can still have overlapping
  handle lifetimes. Two slots cover one music stream plus one asset read.
- Before adding another retained stream, asynchronous loader or nested file
  read, trace the maximum simultaneous open handles. Adjust the capacity or
  explicitly serialize ownership before shipping. Do not merely add retries,
  suppress errors, or skip required assets/cutscenes.
- Close each successfully opened handle on every success and failure path.
  Do not close another subsystem's handle to make a read succeed.
- Capacity changes must rebuild the SDK filesystem object and pass the target
  RAM boundary check: extra GFS handles consume Work RAM, not just cart RAM.
- Run `game/tests/test_fs_handles.py`: the SDK read path must fail with the old
  one-slot pool and succeed with the configured pool while music remains open.
  For runtime acceptance, check hut exit/Saria and forest room crossings during
  a music-bank change. Host tests and a successful build do not prove Kronos.
- Keep SDK error guards enabled. Preserve the exact error text when reporting
  another failure; distinguish file-not-found, handle-open, read and allocation
  failures. Shared SDK stays unchanged; configure it through the project.

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

2026-09-28 source checkpoint (unbuilt): grass/rock drops now use the original
15x16 ID/quantity tables and inventory/health/FLEXIBLE filtering. Child arrows
convert to seeds; missing slingshot, bomb bag or magic suppress their drops per
source. Hearts, nuts, sticks and seeds use the shared grant path. Fairy healing
works, but fairy color/motion, fragment effects and exact scattered-drop physics
remain visual/source-parity gaps; see `game/docs/M3CD_IMPLEMENTATION.md`.
Never reintroduce the old rupee-only grass shortcut.

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

## VDP1 texture storage: bake small, share duplicates

Frogbull advice, relayed by the user on 2026-09-27: pre-cook textures to
4bpp, use widths divisible by eight, avoid unnecessary power-of-two heights,
and detect exact and mirrored clones to save VRAM.

- Bake VDP1 mesh textures offline to 4bpp with 16-entry CLUTs. This rule
  concerns the mesh texture pipeline; other display paths keep their own formats.
- Width must be a multiple of eight (8..504 pixels). Height may be any integer
  from 1..255; do not round it to a power of two solely for hardware compliance.
  Preserve required detail and account for eight-byte storage alignment.
- Share exact duplicate tiles using dimensions, palette and pixel data.
  Detect horizontal, vertical and combined mirrored duplicates too, preserving
  each face's texture orientation when reusing storage. Palette compatibility
  and transparency must be preserved; matching index bytes alone is insufficient.
- Measure savings including pixels, CLUTs and alignment. Check affected faces
  visually before treating a storage change as complete. The character face-only
  rule above still applies.
- User priority (2026-09-27): lower texture detail is acceptable to prevent
  load failures. Forest baking reserves all resident sprites and a further
  32 KiB of VRAM headroom (`FOREST_VRAM_MARGIN` in `vdp1_budget.py`). Do not
  spend that margin on denser forest tiles or bypass runtime capacity guards.
  Count new resident effects in both byte and sprite-slot budgets.

Status at this audit: the active hybrid mesh baker already emits 4bpp, aligns
widths and deduplicates exact `(width, height, clut, pixels)` matches.
The SGL writer accepts non-power-of-two heights, but baked tile sizing mostly
still uses powers of two. Mirrored-clone reuse and tighter baked heights remain
follow-ups, not implemented savings. References: `game/tools/build_hybrid_scene.py`,
`game/tools/build_sgl_scene.py`, `game/tools/build_room_scene.py` and
`game/tools/vdp1_budget.py`.

## Sound effects: half sample rate by default

Permanent user rule (2026-09-27): all sound effects use half-rate samples to
save sound RAM, unless the human identifies a specific SFX as sounding too bad.

- Apply to existing and new SFX, including voices. For the current 11 kHz
  SFX baseline, store approximately 5.5 kHz samples. Already half-rate sounds
  stay at that rate; do not halve them again on each rebuild.
- Resample offline and set playback rate to match. Preserve original pitch
  and duration; this is not half-speed playback.
- Only raise an individual effect's sample rate when the human requests a
  quality exception for that effect. Record the exception and its RAM cost.
- Music banks: the human chose half rate too (2026-09-27, M2 sound RAM):
  superseded for music on 2026-09-28: human approved +33% over that budget.
  build_title_audio MUSIC_SAMPLE_BUDGET 159,600 samples, banks ~319 KB,
  SFX region from 0x50000. SFX stay half-rate; CD-DA keeps 240,000 samples.
- Include resampled bytes, alignment and playback buffers in sound-RAM
  budgets. Keep capacity guards enabled; half-rate storage is not proof that
  the complete active bank fits.

## Red Book (CD-DA) audio: only while the world is frozen

Human rule (2026-09-27). Playing a CD track moves the drive off the data
track; any file read (room bank, actor asset, save device) must seek back,
which stops the song and stalls the read -- a hitch in live play.

- Play CD-DA only when the world is frozen and no disc read can be pending:
  cutscenes, the chest/get-item show, the death + Game Over screens.
- Never in live gameplay or combat (lock-on, hits, pickups while moving).
- Before a CD track: finish any bank/room load. While it plays: no streaming.
- New CD-DA uses must name their freeze in code (src/cdda.h lists them).

This section records policy, not completion of audio conversion. Human handles
listening checks with the gameplay review.

## Enemy-map cheat lifetime (human directive, 2026-09-27)

Enemy-map cheat applies across the game, not only the forest test actors.
Keep the toggle in transient game-session state across room/map changes.
Never serialize it in save data. Clear it for console boot/reset, a new game,
loading a saved game or ending/restarting the session. Normal in-session
respawn preserves it. Display active hostile enemies/bosses for the current
mapped scene. Selection boxes: current highlight light blue, equipped gold.

## Pause presentation and controller preferences (2026-09-27)

Freeze the visible 3D world under VDP2 pause pages; use a grey transparent
checkerboard backdrop. Duck music by 6 dB while paused and restore on exit;
do not change SFX volume. Hide the enemy-map status unless the cheat is on.
Offer saved Saturn automatic, Xbox, N64, GameCube and PlayStation PS4/5 labels.
Labels describe emulator wiring; selecting a label preset does not remap input.
N64 hides the manual-jump label, but keeps the existing Y input working.
Offer a saved custom jump button and Reset defaults. Binding jump consumes that
button's former gameplay action; menu confirm/back remain unchanged. Store
preferences separately from adventure saves, never serialize the session cheat.
Keep map proportions and sufficient colour/detail for legibility. Unvisited
regions remain clouded. Page-button art must contain no stale baked labels.
Latest menu directive: every page uses full RGB555 colour, not a small shared
palette. Map fog should leave terrain legible. Remove System's SAVE lettering
with matching repeated frame texture. Page changes use VDP2 hardware scaling
and sliding as a carousel; preserve and restore the frozen world/HUD resources.
## Dynamic controller labels in all game text (2026-09-28)

Permanent human directive: every player-facing button reference must resolve
from the user's saved controller-label preset and current control bindings.
This applies everywhere: NPC dialogue, the Know-It-All Brothers' tutorials,
choice boxes, signs, item messages, cutscenes, HUD prompts, menus and help.

- Do not leave original N64 button names or icons hardcoded in dialogue.
  Represent the intended action with a token and resolve it through the shared
  controller-label system when displaying text. Selecting N64 labels remains
  valid; hardcoding N64 labels regardless of settings does not.
- Match the actual action binding, including custom jump and digital/analog
  pad differences. Explain required modifiers and directional combinations
  using the selected platform's labels. Preset changes label existing wiring;
  they do not silently remap input.
- Resolve labels before text wrapping/pagination and width checks. Multi-word
  labels and button combinations must remain complete and readable; never
  show an empty label, clipped instruction or unresolved token.
- Existing dialogue and newly added text follow the same rule. Changing the
  preset must update subsequent displayed instructions without rebuilding
  assets or starting a new adventure. Persist preferences as already specified.
- Verify the three brothers' control lessons and other button-bearing text
  with every supported preset, both pad modes and custom jump bindings.

Implemented in code 2026-09-28: ui_text_expand resolves original action tokens
using preferences and pad mode before dialogue_prepare wraps/paginates them.
Source B means attack (Saturn X), not walk/run. A jump binding that steals
another action is shown as unbound in that action's lesson. Unknown preset
bindings use an explicit Saturn physical-button fallback, never an empty label.
Human verified 2026-09-28: dynamic labels look correct, dialogue no longer
flickers, and interior C-Up switching works. This does not certify every
preset/pad/custom-binding combination or outdoor first-person.

Regression rules: preserve retained dialogue rows; never blank/repaint the
whole visible page every frame. Resolve semantic actions before wrapping;
menu confirm/page/assignment actions must not inherit gameplay jump stealing.
Speaker names use bold glyphs distinct from body text, with modest vertical
padding. Generate bold only into verified unused glyph cells: the source must
contain ink, while its destination must be blank. Do not silently regress
names to plain text by requiring unused cells to already contain a glyph.

# Human review before Git publication (2026-09-27)

Never commit, merge, or push changes before the human has checked them and
explicitly approved those Git actions. A successful build or automated test
run is not human approval. Earlier commit/push instructions do not carry over
to later fixes or follow-up changes. Leave work uncommitted for human review.
This rule supersedes earlier standing instructions to commit when done.

## Shop merchandise: flat colours (human directive 2026-09-28)

All shop item models use flat face colours, not texture artwork. Preserve original
geometry and material colour; do not restore nut/heart scrolling textures. Shelves,
room backdrops and the counter keep their original materials. This rule applies to
merchandise, not the shopkeeper's permitted facial artwork.
