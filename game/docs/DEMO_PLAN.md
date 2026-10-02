# Dosei Legend public demo plan

Authoritative scope and delivery plan. Approved 2026-09-25; fully reconciled
2026-09-30 on `dev`. This replaces the accumulated status snapshots in this
file. Historical evidence remains in OPUS_HANDOFF.md and M5_M6_IMPLEMENTATION.md.
Supersedes the no-dungeon endpoint in VERTICALSLICE.md and
KOKIRI_VERTICAL_SLICE_PLAN.md. OOT_PROGRESSION_PLAN.md retains the source gate
and flag research. Implementation is not runtime acceptance.

## Deadline and current assignment

Maintenance rule for every agent: update this plan in the same task whenever
status changes. Reconcile all affected sections, remove contradictory current
claims and keep next actions aligned with the shared tree. A new top checkpoint
alone is insufficient. Separate implementation, tests, builds and runtime
acceptance; retain historical evidence in the handoff/checkpoint documents.

Human requests full dungeon work, with this entire plan updated first.
Codex/Astra owns M4, M5 and M6, including Sacred Forest Meadow (approved
2026-09-30). Continue through required work without stopping for partial
checkpoints. No exact deadline date/time was supplied; do not invent one.
Prioritize blocked progression, then remaining required gameplay and story.
Log minor defects in BUG_FEATURE_LOG.md and continue. Do not cut scope silently.
Human assigned M7 to Codex/Astra on 2026-09-30: start Field budget/source
preflight, then gameplay registration, intro/owl and ocarina free play. M4-M6
remain incomplete; their acceptance is not implied by starting M7. M6b and
M8-M9 remain required, with ownership unassigned.

Work on `dev`; preserve shared uncommitted edits. No commit, merge or push
without explicit human review and approval. Human relays cross-agent messages.
Update OPUS_HANDOFF.md and VSLICEPROGRESS.md with changed files, checks and gaps.
Do not rebuild a mounted ISO or audio track; cold boot the completed image.
Human deferred the next Clean rebuild on 2026-09-30. Do not rebuild until a
new explicit human build request.
Runtime testing remains human-owned; agents must not launch/input an emulator.

Newest playtest repair is implemented and host-checked in the shared tree, but
is not rebuilt per human direction. Game Over Continue now always reloads the
saved entrance's scene bank, even when the Deku Tree scene id is already
resident. This prevents a room-8-style spawn over another Tree room's
collision/backdrop, which put Link in sky and crashed after death. Target/aim UI now uses four source
`gLockOnReticleTriangleDL` corners instead of message glyphs; the white aim
reticle stays on the seed ray centre. Enemy is yellow, NPC blue and POI green.
Human rejected Baba marker placement again on 2026-10-01: the screenshot shows
the lock far below the actor. Attention projection had reversed camera pitch;
the current repair matches the positive-up live camera and removes Karebaba's
old +80 display compensation. Baba source-focus changes remain. Projection
repair passes 48 focused host tests; target build and human acceptance remain
pending. The 16px RGB555 reticle bank
costs 8,192 VDP1 bytes and 16 slots and is budgeted. Player fanfare tracks now
cap/fade: chest 2.50s, token/small item 2.25s, major item 2.75s. This shortens
the player lock, not a claim of original track length. A C-selected Deku Stick
stays held, uses the source left-hand attach transform and only its forward
one-hand slash; it does not reuse sword direction/combo/charge/spin behavior.
ROM has no touch prompt: tip contact with a lit torch flame ignites it. Close,
front-facing push-block contact now shows `A: Grab`; holding A enters push/pull
and block gravity is implemented. Human reports the basement room-3 block
cannot complete its ledge descent; actual push/drop route is blocked and
assigned to Claude for real-room collision tracing. 333 prior focused host
checks did not establish that route. Clean target
build and all human runtime acceptance remain pending.

Game Over follows both source health protections: Continue sets Link to exactly
three hearts, and opening a Game Over save raises any lower saved health to the
same three-heart minimum before the world loads. This prevents a saved zero-heart
file from entering another death loop.

## Deliverable and scope

Downloadable emulator demo: original opening, Kokiri Forest with homes/shop/
NPCs and starter equipment, full Deku Tree and Gohma, heart container and
Kokiri Emerald, Deku Tree death/flashbacks, post-Emerald forest, Lost Woods and
Sacred Forest Meadow, Saria bridge/Fairy Ocarina, Hyrule Field intro/owl/explore.
Include reachable grottos, Gold Skulltula tokens and scrub shops. All ten Woods
rooms exist; access follows original child story gates. No child Mido Meadow
gate. Bomb rocks and unavailable song gates stay source-correct.

Target Kronos, SSF and Mednafen with required 4 MB expansion cart. Real hardware
is not an acceptance gate. Field is child day only: no day/night cycle,
Stalchildren, Peahats or expansion past Field. Other Field exits use explicit
demo boundary messages; document this adaptation. Goron/River boundary handling
still needs a concrete source-aware decision; do not invent additional gates.
Optional: decorative butterflies/fish and an end-card/credits screen.

## Active route implementation (human directive)

Finish boss defeat -> blue warp -> Tree aftermath -> Saria bridge/Fairy Ocarina
-> Field introduction -> outside-Kokiri owl -> Field exploration, including
source music and save/skip/return ownership. Do not stop at isolated asset
checkpoints. Build the usual Clean when integrated; human owns playtesting.
User-approved Easter egg: collecting 1 Gold Skulltula token unlocks blue tunic;
5 tokens unlock red. Persist through the token/save state and expose selection.
These cosmetic child tunics are an explicit exception to original-game behavior.

## M7 integration status

Original child-day Field: one room, 1,579 collision triangles, 73 placed
actors, four owls; exit 4 returns to Woods spawn 8. Isolated Field now bakes
with a 32-pixel base tile cap and source tessellation (no extra forest floor
refinement). Field + Link + both owl texture banks use 411,520 / 445,432 VRAM
bytes; 2,487 polygons and 2,305 vertices include the larger owl skeleton.
No global limits changed, source faces intentionally removed, or old scenes
switched to the new policy. Worst-view/runtime acceptance remains open.

Field per-mesh LOD (Claude, 2026-10-01): Map Workshop per-mesh LOD0 import /
remove and LOD0/cull distances; bank LOD rows in cart carve; runtime integer
Link-distance select (LOD0 / original / skip). Code + host tests only.
BUG-071 fixed in tree (wall split limit restored from reset 494b9b4): Field
bakes 1,258 polys again; Clean image rebuilt OK after the BUG-074 fix.
BUG-074 (P0) fixed in tree: LINKMESH.BIN (791 polys) overran its 0x4800 cart
carve and broke Link drawing; carve moved to 0x7C000 (0x6400) with size guards.
Human Kronos check pending (full Link, Navi glow, Deku Baba, LOD).
Slingshot first-person arm removed again, VDP2 "+" crosshair, ZDSP level 3.
Field distance streaming (Claude, 2026-10-01, plan approved by human): Field
is no longer a KRM1 bank. tools/build_field_chunks.py bakes SAR0.STM (KRM2):
2048-unit cells, each a full piece (<1536 XZ to cell) or LOD2 far piece (2x2
top-down baked quads); Workshop LOD objects become LOD0/LOD1 pieces. Whole file
in one cart block; runtime (field_stream.h + kokiri_sgl.c) swaps pieces with 384
hysteresis while VDP1 idle, fixed per-size VRAM tile pools, tables rebuilt from
cart. Owl mode keeps LOD0 off while the owl is out. Bake sweeps every 256 units
and fails the build over 2,600 polys / 2,500 verts / VRAM, both modes. Field
draw distance now 9,000 (was FOREST_FAR 2,600) through LOD2.
Status: code + host tests (test_field_stream) + Clean image built 20:17 with
selection `original`: 116 pieces, worst 721 polys / 1,157 verts, 267 KB VRAM.
hyrule-alt (human 994-face KokiriExit LOD0) host bake fits: 2,354 polys with
Link, 2,471 verts, 409 KB; not the selected layout in this image. Kronos
pending (human): cell-edge pops/hitch, far LOD2 look, fog at 9,000, owl
intro/leave, interiors and exits, Continue in Field.
Not done: Map Workshop chunk overlay/budget heatmap (optional, P3).
Character mesh exchange (Claude, 2026-10-01): Mesh Workshop exports Link /
Zelda / Impa / Ganon as named OBJ (assets/dynamic/<actor>/LOD0/), imports edited
(decimated) OBJ with nearest-vertex limb ownership via recipe mesh_override
(game/tools/actor_meshes.py, both model builders). Unedited round trip
byte-identical for all four; synthetic 1/3-decimated Link builds. Host tests
only; no override installed, no Clean image rebuilt; Kronos check of an edited
character pending (human).

The integrated route is implemented, host-tested and target-built in the usual
Clean image: Gohma death/optional heart/blue warp -> all nine Tree aftermath
scripts -> forest entrance 11 -> Saria bridge -> Fairy Ocarina -> Field intro
-> outside-Kokiri owl -> day Field exploration and return to Woods. Bridge C1,
intro A0, owl event 6F/switch 12 and item ownership persist. Shot skipping retains
the mandatory grants/destinations. Field uses resident source musical phrases;
Ocarina/Emerald fanfares finish once and resume background music. Pause shows
Fairy Ocarina ownership; playable instrument context remains a separate M7 task.

Save v10 adds equipped cosmetic tunic and Fairy Ocarina, migrating v2-v9.
One persistent Gold token unlocks blue; five unlock red; Equipment allows
selection and keeps green available. Thresholds count unique collected flags.
No new Skulltula placements or bypasses were invented: five-token reachability
is NOT established in the current day-only content, and remains a side-content
requirement before advertising red as obtainable in a fresh demo file.

334 focused checks pass, including production story-state and score-timing
fixtures. High-RAM recovery relocates the unchanged 51,200-byte SDK heap and
expanded 768-entry directory to guarded/zeroed low-RAM carves. Music trigger
tables use a separate 128-KiB low-RAM carve. Final build/artifact evidence below.
No emulator run; human full-route acceptance remains open.

The nine source camera/dialogue/music tracks and principal source meshes are
present; cinematic visual parity is not complete. Ganon currently reuses the
nightmare motion; goddess aura colours/scroll, creation particles/light effects,
Tree death material fade, Link's held Ocarina and full owl head/eye/departure
camera behavior still need polish. Tree death source creak is wired at frame
783. Empty creation-story scenes use a dark background. Owl conversation uses
the source opening/conversation camera offsets with fixed-clock easing.
Other three Field owls are omitted in this day-only checkpoint, not silently
reported as implemented. Registered unsupported Field exits show an explicit
demo boundary; actor/grotto entrances remain part of the side-content backlog.

## Current feedback/audio follow-up

Implemented, host-tested and rebuilt in usual Clean; human acceptance pending.
Enemy red damage / blue stun filters and Link hurt pulses now make contact
visible. Chest opening song previously had no runtime call: large chests now
run imported child opening pose/chest animation and a bounded opening camera,
hide reward text, then play the major-item fanfare. Shop fanfare transactions,
first ammo and Gold tokens also have source-selected songs; minor chest rewards
use their pickup chime. Puzzle success/reveal, shutters, stun and landing impact
have additional source effects. World and disc streaming freeze during CD songs;
the capped player fanfares then restore bank/input. Aim camera/projectile pitch signs
now agree. Read [source audit and remaining gaps](FEEDBACK_AUDIO_AUDIT.md).
Full original chest camera/light/held-item models, hit particles, boss/warp and
mechanism ambience remain required; this is not full 1:1 presentation acceptance.

## Latest human playtest fixes

2026-10-01c (Claude, host tests + SH-2 syntax; runtime pending): roll gets
OoT damage-only dodge frames; jump attack untouchable in air + 1 s (human rule).

2026-10-01b (Claude, code + host tests + SH-2 syntax; no Clean build, runtime
pending): room-3 push block reaches the drop (wall ray 50 -> source 49.5; real
S7 route, switch 16, lock and reload tested). Slingshot shot pitch sign fixed,
same-step look before fire, seed from camera eye, live-FOV cursor depth, rimmed
aim marker, sparkle seed + impact. Z+A without a usable sword rolls standing.
First-person arm (shoulder + slingshot) added; SGL near lowered to level 5 for
all play by human decision (warp comparison pending). OPEN: Gohma evade cause (debug `ev` readout; human value needed).

Title level-select controls now unlock 2.5 seconds after the cheat opens the
menu (150 normalized 60 Hz ticks, PAL/NTSC independent). The title path keeps
resident title music and uses a rupee SFX instead of a CD fanfare followed by
a Fairy-bank load; music_busy no longer blocks this menu. Early menu actions
are discarded. 18 focused delay/minimap host checks pass. Clean rebuild and
human timing acceptance remain pending; scene loading after confirmation is
separate from this menu-opening delay.

2026-10-01 (Claude, code + host tests; Clean rebuild and human runtime pending):
hover arrow now `focus + arrow_y + 17` (Attention_Draw); Deku Baba sets source
focus (first stem step back from head, home+40 while swaying, actor while
retracted) and arrow 15; Kokiri NPC arrow 0, owl 5. Actor-focus host tests did
not catch the screen-projection pitch reversal; the subsequent screenshot
reopened marker acceptance. The corrected projection and removal of the +80
Karebaba compensation are host-tested, not target-built or runtime-accepted.
Child Deku Stick line is hand +X, base (0,400,0) / tip (5000,400,0)
(z_player_lib.c) so ignition, draw rod and hit use the real tip. Z+A jump slash,
sidehop, backflip and roll are no longer Forest-only: refused only in
ROOM_TYPE_INDOORS scenes (houses/shop, `scene_room_type.h`), floor type 7 or
floor effect 1. B: hold walks, short tap cancels/puts the stick away (claimed
presses never act twice). Playtest cheat Up x4 Down x4 B A Start refills hearts,
rupees, owned sticks/nuts/seeds (gameplay only; resets elsewhere; rupee SFX).

Implemented, host-tested and rebuilt in the usual Clean image; human runtime
acceptance remains pending. Switch collision replacement no longer carries Link
by the switch's entire world position. Slingshot uses tap-to-enter aim, subsequent
slot taps fire, release retains aim, and cancel exits. Aim pitch stays where set;
a center cursor is visible. Holding target permits direct slot-tap fire at actor
focus without entering first person. Xbox RB targets (Saturn Z); RT shields.
Enemy/POI hover and locked markers use a static four-corner source reticle;
the original rotating 3D hover arrow remains a presentation gap. First-person
seed aim has a persistent white four-corner centre reticle.
Hint Scrubs now use source default attention range 3 (350 units), beyond their
120-unit hide radius; body/flower/nut artwork skips transparent palette zero.
Tree/boss scenes select separate area banks for scrub movement/spit/reflected hit,
floor/eye switch clicks, and Baba/Skulltula/larva/Gohma damage/death. Existing
shield reflection/nut impact also become audible there. Reduced SFX renderer
still omits full N64 synthesis/modulation/reverb; listening acceptance is open.

## Current implementation and evidence

- Title, file select, opening, house/forest/interiors/shop, starter sword,
  40-rupee shield purchase and equipped-both Mido gate exist. Forest progression,
  Saria greeting, interior and save acceptance remain incomplete.
- Traversal, combat, damage/death, attention, pause pages, controller preferences
  and shared actor/drop systems exist. Held death animation survives lost floor
  contact; lethal landings outrank chest/pause actions and zero vertical speed
  alone no longer counts as grounded. Continue now reloads the saved Tree
  entrance room bank even if its scene is resident, avoiding the sky/crash from
  a mismatched room spawn. Continue and Game Over-save file loading both enforce
  the source three-heart minimum. Focused host checks pass; exact human
  reproduction remains unverified on the replacement image.
- Climb camera now holds the far end of the existing follow range while on
  vines/ladders, including stationary holds; collision clipping remains active.
  Camera checks pass, but human rejects current distance. New requirement:
  climb distance 1.5 times farther than that build. Implemented target is 208
  source units (139 * 3 / 2, integer); exact distance and return checks pass.
  Obstruction clipping still applies; new distance awaits human acceptance.
- Live C-item stick, nut and slingshot use exists. A selected stick stays held,
  uses the source left-hand attachment/one-hand slash rather than the sword
  line, ignites by touching a lit torch flame, extinguishes in water and burns
  webs. There is no invented touch prompt. Tap aim, target quick-shot,
  source-corner aim reticle and attention markers exist in code. Human now
  reports no visible first-person aim cursor, hand/slingshot or projectile;
  usable slingshot aiming is NOT accepted. Claude's current handoff requires
  tracing cursor load/submission at the live FOV, correcting camera/shot pitch
  and origin agreement, first-person weapon limbs and readable seed/impact.
  Full animated hover/reticle presentation and controller acceptance remain.
  C-slot HUD previously drew only empty arrows; assignment-aware original icon
  patches pass host checks. Human deferred the next Clean build.
- All twelve Tree rooms and ten Woods rooms are registered. Nine shutters,
  two floor webs, five wall webs and eleven torches have source placements.
  Door artwork and interaction/roll conflict were repaired. Human reports
  passage still blocked: room asset teardown reset shutter lift. Fix now
  preserves lift across room swaps; host crossing check and Clean build pass.
  Human retest FAILED: first upper room-0 door beside wall Skulltulas still
  blocked the slingshot route. Real S7 collision reproduced the stop at depth
  +/-24: static rectangular door seals remained after the actor lifted. Export
  now marks only aperture seals entity-ignore; the shutter actor retains closed
  gating and source clear/switch rules. Real collision checks pass for rooms
  0<->1<->2 in both directions; frames still block. Human retest pending.
- Floor/eye switches, rising/collapsing platforms, timed water, floating block,
  spike log, falling ladder and both push blocks have runtime implementations.
  Push-block contact now feeds `A: Grab`; the same front-facing dyna contact
  starts held-A push/pull, including an unsupported floor/water drop. Floor-
  switch rider launch is repaired and regressed; floor/eye clicks now fire at
  animation endpoints. Full traversal/puzzle acceptance remains open.
- Withered/normal Babas, hanging/wall/Gold Skulltulas, five Hint Scrubs with
  reflected projectiles and ordered puzzle, and room-7 eggs/larvae are present.
  Source damage/drop paths exist; scrub target range/cutouts and dungeon
  hit/death SFX routing now pass focused tests. Exact AI, full presentation/audio
  fidelity and live route acceptance remain required. Human confirms outside withered Baba combat;
  normal inside Baba sword failure traced to missing capsule/capsule contacts.
  Integer contact fix passes mechanism checks with a capsule sword and the
  Clean build; human combat verification remains pending. Eggs have no drop; hatched larvae use table 3.
- Six dungeon chest exports, dungeon map floors and visited-room persistence
  exist. Compass markers/current-floor selection and all reward reachability
  remain pending. Do not retain the obsolete claim that only room 0 is live.
- Tree meeting, repeat-choice, mouth opening and refusal scripts now bake from
  Bg_Treemouth. Original chained text/Yes-No, event flags, approach/target gates,
  close-range Link relocation, mouth mesh/moving collision, 100-tick opening,
  source wood-door sound and music cues are implemented and target-built.
  Human story/presentation acceptance is pending; source player cue animation,
  camera/target behavior and entrance passage need visual review. This does
  not complete the Tree aftermath or dungeon introduction story. Human reached
  the meeting but reported first-camera text obscured by the panel and hardcoded
  [C-Up] under Xbox labels. Cutscene text now retains unchanged rows, clears
  outgoing dialogue first, and expands shared controller tokens before wrapping
  while preserving colour/reveal. All label/pad/jump combinations pass host
  checks. Visual text/panel acceptance still needs the human retest.
- Gohma importer, combat module, pose loading, rendering and gameplay/camera
  hooks exist. Both boss rooms are now registered in the source scene table,
  with the original Tree exit/return and connecting shutter. Heart-container
  flag 0x1F, optional pickup, blue-warp timing and separate Emerald grant are
  implemented; seven focused boss checks pass. Original heart/warp artwork and
  boss/clear BANK music plus frozen heart fanfare are wired. Clean target build passes;
  runtime route/reward acceptance remains pending. Warp scrolling/appearance,
  full boss presentation/SFX remain required. The nine-part Tree aftermath chain
  is now integrated; full material/particle parity remains open.
- Shutters now match their owning scene for interaction, collision and drawing,
  preventing room-number overlap from leaking doors into another scene.
  All 29 mechanism checks pass, including scrub targeting/audio, switch carry,
  scene ownership, open-door crossing
  and capsule contacts (crossing, parallel, endpoint and point segments).
- Post-Emerald forest Mido/guard behavior and Woods routing/music exist.
  Woods encounters, minigames, pickups, Woods owls and Meadow remain. Saria bridge
  and the Field handoff are now integrated.
- Save v10 preserves token flags, adds tunic/Ocarina and migrates v2-v9. Scene location labels and a
  title-code test level selector exist. Test entry grants equipment without a
  save slot; this is not evidence for fresh-file progression.

Prior P1 boot failure (`TREEMOUTH.BIN`) was fixed with GFS-safe names
`TREEMTH.BIN`, `BOSSHRT.BIN`, `BOSSCLR.PCM/.LVL`; pre-master validation rejects
non-8.3 names. Current usual `game/build/game-clean.cue` includes all prior
player/audio fixes plus the integrated post-boss route and cosmetic tunics.
Latest compile/mastering: `game/build/route-link-final.log`; test evidence:
`route-final-tests.log`; story/Field/bridge budget evidence: `route-budgets.log`.
Artifact audit: all 453 ISO files match staging; 455/768 directory entries.
Thirteen changed target objects have no software-float helper matches.
Final BSS end is 0x0607b640, 35,264 bytes below SGL.
Heap remains 51,200 bytes; SGL 3,750 polygons/3,200 vertices; sprites 2,400.
No global capacity was reduced. Core heap and filesystem are separately bounded
low-RAM linker sections; final map must remain below SGL. MUSICTRG.BIN is 90,334
bytes in a 128-KiB carve. OPENING.PCM is 72,388 bytes including Tree death.
Gameplay Field plus Link/owl retains 33,912 VRAM bytes spare; story bank 23 has
25,080 bytes spare with Link and three goddesses, bridge has 105,768 spare.
Earlier alternate images are superseded; hand off only usual Clean.

Launcher and build chooser now list, in order: `Play Dosei Legend (Standard)`
(Clean, default), `Play Dosei Legend (320x480i)` (Hi-Res), `Debug Mode` (normal).
Existing GUI smoke and read-only catalog checks pass; internal variant IDs and
usual output paths remain unchanged. Reopen launcher to load changed labels.

Prior route-focused verification: 334 checks passed for saves, gameplay,
cutscenes/skip, progression, source assets, owl/bridge state, score timing,
interior/opening audio, item aim, feedback, disc and UI. This is not a full-suite
or runtime-clear claim. Earlier feedback evidence (346 checks) is historical;
stale unrelated full-suite harness failures remain BUG-060.
Actor+room upload and SGL budgets pass for Forest, Tree, boss, bridge, Field and
story banks; `check_forest_budget.py` now enforces the added story banks too.
Changed target code is inspected for software-float helpers. Removed an existing
floating-point degree conversion from cutscene actor yaw in favour of direct
source binary-angle rotation. HUD uses VDP2, tunic recolouring adds no VDP1 art.

Title-code fanfare completion and level-selection input were observed live.
Dungeon traversal, boss clear, full story, item controls and audio listening
are not accepted. Human earlier accepted hearts, plant transparency, carry
animation, instructions, dialogue stability and tested interior C-Up behavior;
these do not certify every preset, pad mode or progression path.

## Milestone ownership and remaining acceptance

| Milestone | Owner | Current state and exit requirement |
|---|---|---|
| M0 foundations | Claude | Policy, naming, actor pool and SFX foundations implemented; preserve boot/cart/bank validation |
| M1 traversal | Claude; Astra water/camera/reviews | Core exists; verify forest and Tree crawl, climb, hang, swim, push, lift and moving collision without stuck/bypass states |
| M2 combat/death | Claude; Astra review/fixes | Core exists; Tree Continue reloads exact saved room bank and Game Over saves reopen at source 3-heart minimum; verify death/save/continue and source combat on live actors |
| M3 forest | Claude; Astra reviewed fixes | Interiors/shop/props/dialogue implemented in part; finish greeting/source gaps and fresh-file equipment/save route |
| M4 items/pause | Codex/Astra | Tap aim, quick-shot, static source-corner reticle, bounded player fanfares and source-attached one-hand Deku Stick built; finish animated hover/reticle, compass and both-pad acceptance |
| M5 Tree/Gohma/Emerald | Codex/Astra | Boss/warp/rewards and nine-part aftermath integrated; presentation parity and human fresh-file clear remain |
| M6 Woods/Meadow/bridge | Codex/Astra | Woods streaming/music and aftermath rules exist; finish actors, games, Woods owls and Meadow; bridge/Ocarina story integrated |
| M6b side content | Unassigned | Dungeon Gold Skulltula foundation exists; reachable grottos and scrub shops remain |
| M7 Field | Codex/Astra | Live route/intro/owl/music built; human traversal/listening acceptance and ocarina free play remain. Per-mesh LOD code (Claude) Clean built (BUG-071 + BUG-074 fixed in tree); awaits Kronos check |
| M8 polish | Unassigned | Required presentation/audio/help/release diagnostics remain |
| M9 release | Unassigned | Complete playthrough, second-emulator check and package remain |

## Execution order for current assignment

Current human steering: finish the playable post-boss route, all cutscenes/music,
and 1/5-token tunic rewards before handoff.
Integrated route and tunic selection are built. Next human run covers natural
boss clear, warp, each aftermath segment, Saria grant, Field intro, owl repeat /
finish, music restoration and return loop. Repeat with shot skip and save/reload.
Keep cinematic fidelity and full M7 instrument/side-content work explicit;
implementation and host tests do not substitute for human acceptance.

1. Claude: resolve the basement room-3 block's refused ledge descent, checking
   the source 85-unit drop, landing/switch 16 and real room collision. Also
   resolve the human-reported first-person slingshot visibility/aim
   blocker using OPUS_HANDOFF.md (cursor, camera/shot agreement, weapon and seed).
   Wait for human build request. Then build current Tree Continue, reticle
   pitch-projection repair (including removal of the Karebaba +80 offset),
   short-CD, source-attached held-stick and push-block Grab repair. Human then retests
   switch landing without launch, tap aim/cursor/target quick-shot,
   scrub acquisition/cutouts/spit/reflect sounds, floor/eye clicks and enemy
   hit/death feedback. Verify chest opening pose/song -> item fanfare/text,
   shop reward/refusal/quick-purchase songs, shortened chest/token/item fanfares,
   held-stick torch contact without a jump/swing, Grab then push/pull block into
   water, Link pulse and
   red damage / blue stun; CD completion restores music and control. Also
   verify first Tree door/slingshot route 0<->1<->2,
   1.5x climb distance, fatal chest landing through Game Over, circular-web
   room death -> Save/Continue exact room reload (no sky/crash), Tree text/Xbox
   labels, Game Over Save Yes -> cold file load at 3 hearts (no death loop),
   inside Baba sword hits and Tree meeting/mouth. Fix failures first.
   Human owns runtime testing; do not launch/input an emulator for acceptance.
   Then verify Gohma combat, optional heart, blue warp/Emerald, persistence,
   room streaming and boss/dungeon save/continue. No full route accepted yet.
2. Complete Tree aftermath material/particle/held-item parity and remaining boss/warp presentation
   and SFX (see FEEDBACK_AUDIO_AUDIT), and verify safe boss/dungeon save/continue behavior.
3. Close route blockers across all twelve Tree rooms: shutters and room clear,
   webs/fire, switches, platforms/water, blocks/ladder, scrub 2-3-1 dialogue,
   chest access and enemy lifecycle. Inspect Bg_Breakwall's actual attack and
   gate requirements; do not assume a nut breaks it. Preserve source gates.
4. Complete remaining M4 models/poses, HUD/compass, targeting and source SFX
   alongside dungeon users. Finish Tree meeting/mouth acceptance and dungeon intro story.
5. Continue M6 encounters/pickups/minigames/Woods owls and Meadow. Finish M7
   Ocarina free play and M6b reachable token content; preserve integrated bridge/Field route.
6. Bounded fresh-file progression, death/save/reload and room-churn checks.
   Fix crashes/corruption/progression blockers immediately; log minor issues.

## Full milestone requirements

### M0: foundations

Face-only character texture policy; stable scene/room filenames beyond nine;
versioned save scene flags; shared bounded actor pool and contact channels;
core/area SFX banks; guarded cart tables and boot loading. Existing modules
are the foundation: extend them rather than replacing architecture.

### M1: traversal

Source floor/wall/ceiling metadata, owner/bgId and clearance queries; dynamic
moving/removable collision; water boxes; source wall-type mapping. Ledge hop,
step-up, grab/hang/pull-up/drop with source rejects and timing; ladder/vine
climb; crawl enter/reverse/exit; turn, roll wall bonk; push/pull; lift/carry/
throw; slopes, fall damage, wade/swim/dive/drown and matching cameras. Physics
owns travel; do not apply authored root travel twice. Verify in real forest
and dungeon geometry, including moving platforms and restricted crawl gaps.

### M2: combat and death

Source slash/combo, thrust, jump slash, nonmagic spin, crouch stab and rebound;
guard/reflect/recoil; shared attention/Navi and battle camera; sidehop/backflip;
hurt/knockback/invincibility/hearts; death/Game Over/save/continue. Dungeon
continue returns to its entrance and reloads that entrance's streamed room
bank. No bottle fairy revival required at this
story point. Starter equipment must be earned without debug grants.

### M3: living Kokiri Forest

Original Kokiri/Mido/Saria/shopkeeper models and animation, source child
population/paths/head tracking; all homes/shop and transitions; Link-house
ladder, source cow/pot content; signs, pots, rocks/rings, grass, hidden/placed
pickups, decor and gossip-stone hit response; persistent animated chests and
get-item sequence; maze boulder; withered Babas and source drops. Full shop
shelves/camera/choices/prices/capacity/ownership refusals and no ground gear
substitute. Source dialogue trees/flag writes, Navi hints, indoor music and
Saria greeting. Acceptance: earn rupees, maze sword, buy/equip shield, pass
Mido, save/reload retains purchases/chests, all without debug grants.

### M4: items and pause

Digital C+directions and analog-pad C-direction behavior; saved C assignments;
stick swing/burn/break, nut flash/stun and slingshot tap-to-aim/fire, target quick-shot, ammo/eye hits;
source ownership-dependent drops and capacity. Complete held models, poses,
projectile/target interaction, feedback and sound. Pause Items/Equipment/
Quest/Map/System on VDP2; dungeon map/compass, Emerald, heart pieces and token
counts. Preserve full-colour carousel, frozen world and music ducking.
Controller labels follow saved presets/custom bindings before wrapping.
Ocarina free play arrives in M7. Check both pad modes and preference reload.

### M5: full Deku Tree and Gohma

Tree meeting/choice/mouth opening/ask-again and dungeon intro; twelve Tree and
two boss rooms; source shutters/clear/switch gates and invisible transitions;
dungeon/boss/clear music. Webs, torches, floor/eye switches, bridges/platforms,
water/log/ladder, push blocks and applicable breakwalls. Source Babas,
Skulltulas/Skullwalltulas/Gold tokens, larvae/eggs and Hint Scrubs/projectile
reflection/ordered 2-3-1 puzzle; Keese only if source placement requires them.
Reachable Map/Compass/Slingshot and minor chests; Navi hint volumes.
Gohma ceiling/floor behavior, eye weakness, seed/nut stun, damage, eggs/minions,
death, Item_B_Heart and Door_Warp1. Emerald and Tree death/flashback chain.
Acceptance: fresh-file full clear without debug grants/gate bypasses; rewards
once only; death/save/continue works before, during and after boss defeat.

### M6: post-Emerald forest, Woods and Meadow

Post-Emerald dialogue/flags, Mido departure and exit guard; ten Woods rooms
with source wrong-way exits and child/day access. Grass/pickups, Octoroks,
Skull Kid dialogue, business scrubs, target game, source minigames and owls
including room 2/8 talk/fly-away. Song-dependent branches stay gated until
available. Sacred Forest Meadow gameplay is required; original child actors,
collision and route, with no invented Mido block. Saria bridge cutscene,
Fairy Ocarina get-item and persistent flag C1; Field intro handoff.

### M6b: side content

Reachable Kokiri/Woods grottos (Door_Ana parameters determine availability),
chests/scrubs/gossip content; bomb/song-blocked entrances remain blocked.
Gold Skulltulas with source spawn conditions, token collection/persistence
and Quest count. User-approved cosmetic rewards: 1 token unlocks blue tunic, 5 unlock red;
retain green and allow unlocked selection. Night-only forest actors are unavailable in the day-only
scope. Scrub prices/choices/rewards/upgrades follow original actor tables.

### M7: Hyrule Field

Original field geometry/collision, measured culling/texture budgets; intro
cutscene; outside-Kokiri owl (0x004C) dialogue/repeat/fly-away; record handling
of other owl placements. Day music, free exploration, static drawbridge,
explicit demo boundaries except return to Woods. Ocarina free play with the source five basic note inputs and verified pitch
modifiers, staff UI and sound, without song progression. Earlier "six-note"
wording is not permission to invent a sixth note button; see M7 input contract.

### M8: required polish

Scene fades/loading feedback; enemy/chest/door/item/heart/damage/low-health/
Game Over audio coverage. Demo version/build hash, controls help and
README-DEMO with emulator/cart setup, known issues and bug/save report steps.
Crash PC/PR/build hash; compatible save migrations and invalid-save rejection.
Clean player image, no diagnostic overlays. Minor polish never hides blockers.

### M9: release

Bounded title-to-Field/owl fresh-file run; continue/save and forest/dungeon
Game Over routes. Check known warp/floor-over-Link/opening-crash cases; fix
playability blockers, document lesser issues. Second-emulator boot and five
minutes play. Pass budget/boundary/cart/no-software-float gates. Package
ISO/CUE and README; publication still requires explicit human approval.

## Source and implementation contracts

Reference: `D:/Workspace-Claude/game-decomps/n64/oot`, US ntsc-1.2.
Extracted scene lists define actors, layers, spawns, exits and collisions.
Kokiri has 3 rooms; Woods 10 (room 5 bridge); Tree 12; boss 2; Field 1.
Forest exit 2 leads to LOST_WOODS_9; Woods exit 8 to HYRULE_FIELD_3.
Bridge conditional trigger grants Fairy Ocarina only before EVENTCHKINF_C1.
Tree source story flags/gates remain in OOT_PROGRESSION_PLAN.md; do not replace
scripted progression with unconditional grants.

Reuse scene_flow/kokiri_sgl streaming, gameplay/save_state rules, actor_sys,
collide, player modules, shared drops, message/choice, cutscene baked tracks,
actor importers, flex_vertex_owners and vdp1_budget. Preserve original
coordinates/handedness and immutable ROM baseline. Map Workshop overrides
change visuals, not collision. Stable song IDs live in songs.json.

Every actor task includes original damage/drop routines, spawn-selected tables,
conditional rewards and persistence. Trace Item_DropCollectibleRandom and
FLEXIBLE filtering; record any unsupported behavior. Character artwork only
on faces (enemy eyes count); bodies/hair/equipment flat. Human permits existing Deku Baba textures when the complete room VRAM budget
fits (2026-09-30 exception). Vertex bone ownership
is captured on vertex load, not inferred from the face's drawing limb.

SH-2 runtime math is integer/fixed point. Keep memory and capacity guards;
work-RAM heap remains 51,200 bytes and sprite limit 2400. Historical heap peak
50,692 bytes is not a current measurement. Guard low-RAM/cart carves, actor
poses, per-room uploads and VDP1 byte/slot budgets; preserve forest headroom.
Music follows approved budget; SFX half-rate, pitch/duration preserved.
CD-DA only with world frozen and disc reads finished: mute background bank,
retain it, restore over 0.5 seconds on actual end/failure/interruption.

## Verification and unresolved risks

Build Clean only (`game/build.bat -Variant clean`) at the usual `game-clean.cue`
path. Launcher calls this `Play Dosei Legend (Standard)`. Build `Debug Mode`
(normal variant) only for a needed developer feature; Hi-Res on request.
Do not create alternate image names unless explicitly requested. Run focused host checks appropriate to
changed gameplay/save/collision/import paths, asset/dialogue validation and
SGL/VDP1/cart gates; inspect changed hot paths for software-float helpers.
Human may use `game/run-kronos-clean.bat` for the completed player image.
Runtime playtesting is human-owned; agents must not launch/input an emulator.
State host, target-build and observed runtime evidence separately.

Priority regression review: BUG-052 death-save reload, BUG-048 Save No,
BUG-049/070 Continue room-bank sky/crash, BUG-053 pause corruption (cold unchanged-image
check), moved cart-table boot/music, NPC ledge-versus-talk, room transitions,
controller labels/item assignment matrix. Consult BUG_FEATURE_LOG.md for
current individual status; do not infer a fix from an old checkpoint.
BUG-035 heap measurement and BUG-050 death voice are deferred nonblockers.
Camera/text core changes are implemented, with partial human acceptance;
CAMERA_TEXT_PLAN.md is no longer an entirely unimplemented proposal.

Main risks: tight high RAM and per-room VRAM, enemy/boss poly cost, streaming
and sound ownership, large Field geometry, emulator command limits, and
unfinished story content. Resolve measured failures without broad speculative
renderer rewrites. Renderer repairs must follow FOREGROUND_WARP_FAILURE_2026-09-18.md.
Do not equate builds, isolated banks or host tests with a playable full route.

## Supporting plans

[M2 combat](M2_COMBAT_PLAN.md), [M3 forest](M3_KOKIRI_PLAN.md),
[M4 items](M4_ITEMS_PLAN.md), [M5 dungeon](M5_DEKU_TREE_PLAN.md),
[M6 Woods](M6_LOST_WOODS_PLAN.md), [M6b side content](M6B_SIDE_CONTENT_PLAN.md),
[M7 Field](M7_HYRULE_FIELD_PLAN.md), [M8 polish](M8_POLISH_PLAN.md),
[M9 release](M9_RELEASE_PLAN.md). M5_SOLO_GUIDE.md and
M5_CODE_AND_SOURCE_MAP.md are references, not a human-only ownership rule.
This plan's current assignments, scope and Clean-build rule supersede stale
instructions in those drafts. Keep implementation detail/evidence in
[M5/M6 checkpoint](M5_M6_IMPLEMENTATION.md), not duplicated status histories here.
