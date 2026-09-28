## Clean build update (2026-09-28)

Human authorized the Clean build. Assets and target code rebuilt into the existing
`game/build/game-clean.cue`. Verified map: BSS ends at 0x06082800, leaving
**6,144 bytes below SGL at 0x06084000**. The first link exceeded SGL by 4,752 B.
Moved forest vertex depth, tile depth/fog and mesh flags (10,763 B of arrays)
from high BSS into guarded Low Work RAM carves at offsets 0x5000..0x97FF.
Heap, sprite and polygon limits unchanged. Low RAM performance needs Kronos checks.
No commit or Kronos run. Earlier no-build checkpoints below are historical.

Additional renderer checks exposed an outdated forest host adapter (missing SGL
members/constants) and three room-bank assertions expecting 0x67 instead of the
exported 0x66 sort mode. These checks are not green; no renderer behavior was
changed to satisfy them. PowerShell reports NativeCommandError for compiler stderr,
but the build reached disc creation and the final successful map boundary check.

# M3c/M3d source checkpoint — 2026-09-28

Human assigned the remaining work to Astra, said **do not build**, and confirmed
Claude finished. No target build, disc regeneration, Kronos run or commit occurred.
The existing disc keeps its existing name. Last Claude-built Clean RAM gap was
7,424 B; that is **not** the gap for this source checkpoint.

## Implemented

- `item_drop.c`: original EnItem00 ID/quantity tables, child/inventory/health
  conversion and FLEXIBLE resolution. Grass and small rocks select source tables;
  pots select their authored item/collectible flag. Grants use `save_item_give`.
  Unavailable bombs/magic are suppressed by the source inventory conditions;
  seeds require a slingshot. Fairy result heals eight hearts, capped at capacity.
- `world_props.c`: 32 source placements across forest/interiors, including the
  eight ObjMure2 child rocks, pots, placed hearts, decorative ObjHana rocks/bush,
  and gossip stones. Actor-pool handles own transient props/drops. Sword breaks
  pots, not small rocks. Existing player lift action attaches, puts down and
  throws pots/rocks; impacts release their source rewards. Physical bodies push
  Link through world collision. Carried props survive a forest room unload.
- `world_signs.c`: ten authored sign placements remain outside the actor pool.
  Source messages, facing/range gate, source melee-animation cut masks and eleven
  original mesh pieces. Detached pieces use temporary actor slots; signs restore
  on scene reset. Signs produce no invented rewards.
- `build_world_props.py` / `world_props_draw.c`: ROM pot/rock/bush/gossip models,
  sign pieces, and normal chest skeleton with the source child opening track.
  Models are loaded per scene and uploaded through the existing NPC tile bank.
- Maze sword chest and Mido's four chests: source reward IDs, source scene/flag,
  persistent open state, original chest opening motion and get-item text.
  Full health/wallet does not prevent opening a chest. Get-item display uses
  Link's `link_demo_get_itemA` clip; first nuts/sticks and shop rewards use it too.
- Save **v6**, same 311-byte block as v5: old forest rupee array bits migrate to
  source collectible flags. Temporary green rupees respawn; persistent blue
  rupees and chest flags survive reload. Versions 2–5 still load.
- Preserve Claude's shop flow, cursor, spin/slide and held-stick repeat.
  Heart/nut exporters now bake source primary-texture UV scrolling into `.SCR`
  tracks. Runtime rewrites their animated VDP1 tiles at 20 Hz after draw completion;
  the nut body stays still. Approximately 205 KB additional cart data; no per-frame
  disc reads. Target VRAM/CPU impact remains unmeasured.
- Fado's named type-12 dialogue was previously skipped; it now exports and advances
  from 0x10D7 to 0x10D8. Kokiri/Saria closing flags and house Mido rules are wired.
  `DIALOG.TXT` is 17,051 of 20,480 bytes in an isolated exporter check.
- Automatic standard-build nutsball test emitter removed. Existing diagnostic
  overlays and the human-approved minimap cheat remain.
- Navi's pre-existing one-tick test failure fixed against EnElf `func_80A053F0`:
  opening a hint takes the talking branch, so the idle timer must not increment
  the freshly assigned 3001. Reset the fractional update phase on scene reset.

## Source-parity limits and acceptance

These are not claims of complete M3 acceptance:

- Pot/rock debris, dust and exact thrown-object/water physics remain reduced.
  Drops use source quantities/filtering/lifetime with a simplified visual hop;
  a FLEXIBLE fairy currently reuses fairy artwork/motion rather than a complete
  collectible EnElf port. Gameplay reward is implemented.
- Sign cut selection/geometry is source-based; detached motion is simplified.
  Water-floating/ocarina repair require the later water/song integration.
- Gossip stones have a reduced visible sword-hit wobble and hard collision,
  not the complete source reaction state machine. Mask/bomb/song reactions need
  their later item systems. ObjHana decorations have no invented drops.
- The authored forest grotto is bomb-revealed (DoorAna params 0x012C). It stays
  closed without bombs; grotto destinations remain M6b. No fake open entrance.
  Link-home cow access remains gated by later progression, not granted here.
- Saria's greeting camera/cue sequence remains M3b work. For now closing 0x1001
  marks the greeting complete, so later conversations advance. This is explicitly
  an adaptation of EnSa's cutscene-completion flag, not a port of that cutscene.
- Heart/nut scrolling uses the primary texture. N64 two-layer combiner blending
  is still approximated. Get-item rewards retain the existing billboard display.
- HUD-specific Read/Grab/Throw artwork is not added; context A performs the
  action, but the existing HUD only has Talk/Open/Enter variants.

## Verification and next authorized build

**339 focused host tests passed** in the final combined run (gameplay, drop
tables, save serialization, rupee rendering, temporary prop exporters, item grants,
actor pool, controls, lift and text/recoil). Navi hint test also passed alone.

Host gameplay covers pot sword breaks, rock sword immunity, attachment/release,
throw impact/put-down, sign reading/cuts, gossip reaction, Saria/Fado flags,
placed hearts, five chest rewards and existing shop flow. Drop tests compare all
source table entries and exercise inventory/FLEXIBLE behavior. Save tests cover
v5 migration and v6 round trips. Asset tests export to temporary directories and
validate mesh indices, animated chest poses and changing scroll-track frames.

SH-2 **syntax-only** checks passed for the changed C integration. Temporary actor
headers and placeholder definitions for the not-yet-generated get-item clip were
used for parsing; this does not prove linkage, memory fit or animation residency.

When a build is authorized, run the normal existing build path once: all new assets,
clip headers, dialogue tables and `.SCR` files must be regenerated together. Check
real RAM gap before shipping the image; never use the old 7,424 B as a new result.
Then Kronos: fresh starter route, every Mido chest/reload, grass/pot/rock rewards,
carry/put/throw on both pads, signs from front/back and cuts, first-item pose,
Saria/Fado repeat dialogue, both shop shelves/scrolls, room changes, sprite/VRAM
peaks and frame rate. No game build is authorized by this document.
