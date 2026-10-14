# Dosei Legend: full OoT recomp for Sega Saturn

A work-in-progress full OoT recomp using **Jo Engine / SGL**. It runs the real
zeldaret/oot decomp (actors, Player, collision, cutscenes, messages) on the
Saturn, with a Saturn renderer, audio and platform layer. **Requires the 4 MB
RAM expansion cartridge.** Development happens on `oot-core`, which is merged
into `main` at checkpoints.

**Current route (2026-10-13):** new game, Kokiri Forest, the Deku Tree and Gohma,
Lost Woods, Hyrule Field with the owl, Lon Lon Ranch, Hyrule Castle courtyard
and Zelda, Kakariko, Death Mountain Trail, Goron City and Dodongo's Cavern
through King Dodongo. All 101 retail maps load from Level Select, but only this
child route is being made playable. The full route has not been played through
on hardware or an emulator yet (see [Known issues](#known-issues-and-limitations)).

The [full recomp plan](game/docs/RECOMP_PLAN.md) covers every scene, era, actor
and story system. The current route sets implementation order. Whole-game
completion is still pending. See the [current handoff](game/docs/CHILD_ROUTE_STOP_HANDOFF_2026-10-13.md),
[route plan](game/docs/CHILD_ROUTE_DODONGO_PLAN.md) and the full
[bug and feature log](game/docs/BUG_FEATURE_LOG.md).
The older [vertical-slice scope](VERTICALSLICE.md) is historical where superseded.

## Layout

```text
game/
  src/                         Game flow, scene/actor submission and bank selection
  levels/kokiri/assets/static/  Forest geometry, collision container and backdrop
  levels/kokiri/assets/audio/   Kokiri score and sample bank
  assets/dynamic/link/          Actor source recipe (animation/pose/scale)
  disc/                        Checked-in disc metadata, not generated staging
  tools/                       Game-specific asset converters
  tests/                       Active Jo game checks
  build/                       Ignored objects, generated meshes, CD staging, ISOs
shared/
  lib/camera/                  Reusable camera/movement logic
  lib/collision/               Platform-independent collision
  lib/music/                   Bank-agnostic Saturn music player
  assets/static/ui/            Title artwork and prompt
  assets/audio/title/          Shared title score and samples
  tools/                       Shared extraction, mesh and audio export helpers
  build/                       Ignored extraction/source caches
tools/
  launcher/                    Windows GUI: Clean, Standard and hi-res builds
  mesh-workshop/               Non-destructive triangle/quad OBJ exchange
  tests/                       Tool checks
workspace/meshes/               Ignored mesh editing revisions
legacy/libyaul/                 Archived reference only; not an active build target
```

**Static/dynamic describe content:** environment/UI versus movable actors.
**Source/generated describe ownership:** tracked assets/recipes versus disposable
`build/` output. Never edit generated meshes as the source of truth.

## Build and play

Open **[launch-game.bat](launch-game.bat) > Config > Paths and emulator...** first. Select
your tools, validate paths/ROM, and save the local `config.ini`.
[Developer setup](tools/launcher/SETUP.md) explains the Jo Engine SDK, MSYS2,
Python/Pillow, Kronos, BIOS and required US 1.2 ROM/decomp inputs.
Enable a **4 MB RAM expansion cartridge** in Kronos.
Emulator tab switches Run to Mednafen (see [SETUP.md](tools/launcher/SETUP.md#mednafen-optional-most-accurate)).

| Build option | Purpose | Windows command from repository root | Image |
| --- | --- | --- | --- |
| **Clean player test** | Default for play and review: 320x240, no game debug overlays; safety checks remain enabled | `game\build.bat -Variant clean` | `game/build/game-clean.cue` |
| Standard (`normal`) | 320x240 with developer overlays and camera comparison controls; build only when a test needs them | `game\build.bat -Variant normal` | `game/build/game.cue` |
| Hi-res (`hires`) | Experimental 320x480 interlaced output; build only when requested | `game\build.bat -Variant hires` | `game/build/game-hires.cue` |

Clean means a player-facing variant, not deletion of build files. It does not
turn off safety checks or Kronos's own FPS display. Build sequentially: variants
have separate objects/images but share generated assets and disc staging.

| Launcher option | What it does |
| --- | --- |
| **Run selected** | Opens the selected existing image in Kronos; does not rebuild it |
| **Rebuild...** | Opens build selection; select Clean for normal player review |
| **Refresh** | Refreshes image availability and timestamps |
| **Config > Paths...** | Changes local SDK, Python, emulator, BIOS and source-data paths |
| **Config > Developer setup guide** | Opens the dependency/setup guide |

Close Kronos before switching builds **or rebuilding its mounted image**.
Replacing a mounted ISO can leave cached file positions pointing at wrong
assets; cold boot the completed image after a rebuild. Direct launch shortcuts are
`game/run-kronos-clean.bat`, `game/run-kronos.bat` and
`game/run-kronos-hires.bat`. Use the `.cue` to retain the disc's audio tracks.
**Build in WSL Linux only** (not MSYS2/Git Bash). Read
[BUILD.md](game/docs/BUILD.md) first. From `game/` in WSL,
`./build.sh --clean OOT_CORE=1` builds Clean and `./build.sh --quick OOT_CORE=1`
builds Debug (Standard). See [game build notes](game/README.md) for diagnostic
options.

## Controls (current build)

These are **Saturn input names**, not PC keyboard keys. Bind your controller in
Kronos. The System page's label presets change displayed names; they do not
configure Kronos or remap gameplay inputs. The table assumes default Y jump.

| Input | Gameplay action |
| --- | --- |
| Digital D-pad | Camera-relative movement; steer in the air |
| 3D pad stick (analog mode) | Proportional movement; Holding B selects walk speed ceiling; B tap cancels / puts away the stick |
| B | Hold to walk; tap to cancel / put away the stick |
| Y | Manual jump; no double-jump |
| X | Attack with equipped sword; cuts grass and damages enemies |
| Hold R | Guard with equipped shield |
| A | Context action: talk, advance text, interact; roll when no interaction claims it |
| B during dialogue | Cancel/close when the conversation allows it; does not toggle walk/run |
| Hold Z | Lock onto a valid attention target, including NPCs/enemies; release to unlock |
| Tap Z | Recenter when the press did not acquire a lock |
| Z / B + Z in first raised camera | Turn 90 degrees clockwise / counter-clockwise per Z press; replaces targeting in this view |
| Move while holding Z | Strafe/back up while keeping facing |
| Tap L | Show/hide minimap |
| L + R + B | Permanent camera easter egg: normal → far/high → higher → steep overhead → north-up top-down → normal |
| Hold C + D-pad (digital) | N64 C directions; C-Up accepts Navi first, otherwise changes view |
| D-pad (analog gameplay) | N64 C directions without holding C |
| Start | Title/menu flow; open or close pause during gameplay |
| Start during a cutscene | Show skip prompt; press again within two seconds to skip that camera shot |

Camera follows automatically. C-Up enters first-person outdoors when grounded
and free to act. D-pad/stick looks; another action button exits without firing
that action. Navi calls take priority. Houses start in their original panorama;
C-Up toggles the overhead picture and back. The shop keeps its fixed view.
L now toggles the minimap, replacing the temporary hold-L free look.
Release all three buttons before cycling again. The easter egg is available in
Clean during outdoor gameplay; boot starts with the normal camera. Raised views
start facing north and bypass camera obstruction clipping for surveying terrain; Link's
collision stays active. Interiors, first-person and cutscenes retain their views.
The first raised view remembers its quarter-turn heading until reboot. Missing
area warnings stay quiet nearby after dismissal; walk 600 units away to rearm.
These camera/text changes build and pass host checks; Kronos acceptance is pending.
Landing rolls depend on landing conditions.
Find the sword in the maze chest; buy the Deku Shield for 40 rupees in Kokiri
Shop. **Equip both on the Equipment page** to pass Mido's gear check.
Acquisition alone does not equip them.

## Pause pages and item assignment

Press **Start**, use **L/R** to change pages, and **D-pad** to move the cursor
on either controller type. **Start closes pause**. Blue marks the cursor;
gold marks equipped gear or assigned items. Pause freezes the visible world
and lowers music by 6 dB; SFX volume is unchanged.

| Page | Available options |
| --- | --- |
| **Items** | Owned items, stick/seed counts and C-slot bindings. Assign with the chord below |
| **Map** | World map with clouded unvisited regions; the pulsing marker identifies Kokiri Forest, not Link's exact position |
| **Quest Status** | Quest display, including the Emerald when owned; song/quest interactions remain pending |
| **Equipment** | Select an owned sword/shield and press A to equip it |
| **System** | Save, Load, Title, button-label preset, jump binding and Reset defaults |

To assign an item: highlight it on **Items**, then **hold Saturn C and press
Down, Left or Right**. This chord is required in pause on **both digital and
analog pads**; plain D-pad moves the cursor. C-Up remains reserved for Navi/view. Only owned
items can be assigned. Assigning an item elsewhere removes its previous
binding. Bindings persist when you save the adventure. The pause hint names
the modifier as C (Saturn), LB (Xbox), or L1 (PlayStation). N64/GameCube
presets show Sat C: bind that Saturn input in the emulator; those presets
do not define a native modifier.

**Live items are implemented.** Tap the assigned slingshot slot to enter aim;
tap again to fire and use cancel to leave. Releasing the slot keeps aim active.
Hold target (Xbox RB / Saturn Z) and tap the slot to shoot the locked actor
without first person. RT remains shield. Center marks show aim; actor markers
show available/locked targets. Human controller testing remains open.

B opens the save prompt from the four adventure pages. In a prompt, D-pad
changes the choice, A confirms and B cancels. On System, B returns to Equipment.

## System options and saves

| Option | Behavior |
| --- | --- |
| **Save** | Opens confirmation and writes the current adventure slot to backup RAM; reports success/failure |
| **Load** | Confirms leaving unsaved progress, then opens file select; does not automatically save |
| **Title** | Confirms leaving unsaved progress, then returns to title; does not automatically save |
| **Labels** | A cycles Saturn (Auto), Xbox, N64, GameCube and PlayStation PS4/5 names. These describe emulator wiring, not input remapping |
| **Jump** | A cycles Y, A, B, X, C, Z, L, R. Chosen button replaces its former gameplay action; menu confirm/back stay unchanged |
| **Reset defaults** | Restores Saturn automatic labels and Y jump; does not erase adventure saves |

N64 labels hide the manual-jump prompt, but default Y jump still works.
Saturn Auto reflects detected controller mode; a 3D pad switched to digital
mode identifies as digital. Selecting a different label preset does not change
this detection. Avoid binding jump to an action you still need in gameplay.

Preferences save separately from adventure slots; System reports a settings
save failure. Current source writes adventure save v6: v4 added C-slot bindings,
v5 added nuts, and v6 migrates forest pickup flags. Saves v2-v5 still load;
missing older fields receive defaults. Save v6 is included in the 2026-09-28 Clean build; Kronos validation is pending. Use working Saturn backup RAM for persistent saves.

## Optional diagnostics

Standard-only **L + R + Down** switches debug overlay views;
**L + R + Up** switches the developer camera comparison. Clean removes both.

Before pressing Start on the title, enter **Up Up Down Down Left Right Left Right B A Start**
to open level select. Up/Down chooses an area; Left/Right chooses its room;
A enters and B returns. Test runs begin with sword, shield, Slingshot, sticks,
nuts, map and compass, without changing a saved file.

The enemy-map cheat is **Up Up Down Down Left Right Left Right B A Start**;
repeat to turn it off. It shows active hostile enemies/bosses on the current
mapped scene. Its status appears on System only while enabled. It survives
room changes and normal respawn, but clears on new/load game or ending the
session and is never saved. Release the completing Start before pressing
Start again to pause.

Model tool: `tools/mesh-workshop/open-mesh-workshop.bat`. Imported tri/quad
candidates are editing assets, not automatically runtime-ready meshes.

Audio tool: `tools/audio-workshop/open-audio-workshop.bat`. Plays US 1.2 SFX
and music on the PC. No import or export.

## Known issues and limitations

This list covers the main problems. Owners, evidence and smaller items are in the
[bug and feature log](game/docs/BUG_FEATURE_LOG.md).

### Route blockers
- **King Dodongo was invisible, and the bombable floor above his room was missing.**
  Both were caused by the order of the draw lookup tables, the same cause
  as other invisible props. Fixed in Clean `9676d036`, which has not been
  played yet.
- **Sword "air bounce":** after Kakariko, every swing may bounce as if it hit
  something. The cause is still unknown.

### Not yet verified at runtime
- No full route playthrough has been done on any image. Builds and host tests
  pass, but they do not prove gameplay, audio or rendering.
- Not yet player-tested: the memory fit (an offline model says every scene fits),
  Lon Lon Ranch loading, the Zelda escape in Hyrule Field, the Gohma motion and
  the reduced-pose sprites.
- Playing an ocarina song used to crash with `oot-core fatal 41554446 48 0`. This
  is fixed in Clean `97ef4cfe` and later, but not in the older Debug `11244013`.

### Performance
- Speed is usually 10–20 FPS. Moving play is slower than standing still; 20 FPS
  while moving is not reached yet.
- Choppy running is possible with the default two-CPU core. Pause > System >
  Core offers Fast (two CPUs) or Responsive (smoother, slower).

### Saturn adaptations (intentional)
- Every NPC, animal and non-boss enemy is a baked sprite: no 3D models, no head
  tracking. Bosses keep 3D models.
- Some sprites have fewer animation poses to fit memory: child Zelda, Impa, the
  running man and Lizalfos move choppier. Timing and hitboxes are unchanged.
- Gohma's animation is stored at reduced precision (under 0.5 world units of error).
- Player animations load on demand. Item moves for bottles, magic, the hammer,
  the boomerang and the hookshot load when you close the pause menu. If a
  CD-audio fanfare is still playing, the menu stays open until it ends.
- If loading an item's animations fails, using that item silently does nothing
  until a later pause close or scene load. It retries, but recovery is not
  guaranteed.
- The game never reads the CD during play. Loads happen behind loading screens
  and the pause menu.

### Audio
- Nature ambience (river, forest sounds) is silent.
- The cutscene effects sequence (e.g. the Three Goddesses, light rings) is silent.
- The music renderer is simplified: legato, portamento and envelopes are
  approximate. The windmill tempo pitch and the Ganon's Tower filter are missing.
- Rock and pot pickup has no lift sound.

### Gameplay gaps
- Z-targeting and the shield do not yet work against every decomp enemy.
- Elemental hits (burn, freeze, shock) and burning wooden shields are not done.
- Some enemy death effects and the sprite effect renderer are pending.
- Iron Boots walking speed and sink rate underwater are not source-accurate.
- Forest Temple room 9 has no Level Select entry.

## Focused checks

Run tests relevant to the changed feature. Available suite entry points:

```powershell
python -m unittest discover -s game/tests
python -m unittest discover -s tools/tests
powershell.exe -NoProfile -ExecutionPolicy Bypass -File tools/launcher/kronos-launcher.ps1 -Check
```

A build or host test does not prove controller feel, audio or rendering in
Kronos. Latest item/pause fixes still need player review; see the handoff.
