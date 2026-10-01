# Tree Continue, target, fanfare and torch playtest repair - 2026-09-30

Code done in shared tree; 333 focused host checks pass. Human deferred usual Clean
rebuild. No emulator run. Target/aim now use source four-corner reticles, not message glyphs;
white stays at seed-ray centre and Baba's display marker rises to head. Reticle
bank is +8,192 VDP1 bytes / +16 slots and budgeted. Chest/token/major CD tracks
cap/fade at 2.50/2.25/2.75s. C-selected stick stays held with source left-hand
attachment/forward one-hand slash; no ROM touch prompt, tip touch lights flame. Close,
front-facing push blocks now show A: Grab; held A enables push/pull and unsupported
blocks fall. Continue now always reloads saved Tree spawn bank: the prior
same-scene shortcut mixed room spawn and room collision/backdrop, causing sky
fall/crash after circular-web-room Save/Continue. Animated hover arrow remains
open. N64 minimum health now applies at both Continue and Game Over save load:
health below 0x30 restores to three hearts before world load. Wait for human
build word.

# Boss-to-Field route and tunic integration ? 2026-09-30

Usual `game/build/game-clean.cue` / `.iso` rebuilt. No emulator, commit or push.
Human owns acceptance. Whole DEMO_PLAN reconciled; older checkpoints below are
historical and their ?current build / unimplemented? statements are superseded.

- Route: Gohma clear/optional heart -> blue warp -> nine source Tree aftermath
  scripts -> forest entrance 11 -> Saria bridge/Ocarina/C1 -> Field intro/A0 ->
  outside-Kokiri owl/repeat/finish/switch12 -> exploration and Woods return.
  Source cameras/dialogue/principal models and music are wired. Bridge completion
  goes directly to Field spawn 3, as its source destination specifies.
- Resident Field audio uses the source normal/still phrase sets and pitch events;
  owl theme and one-shot Ocarina/Emerald fanfares have explicit ownership. Tree
  death creak at source frame 783. No music streaming from VBlank.
- Save v10 adds Ocarina and cosmetic equipped tunic; migrates v2-v9. Unique Gold
  tokens unlock blue at 1/red at 5. Select unlocked colour on Equipment; green
  stays available. Palette replacement adds no Link VRAM. Ocarina inventory icon
  is visible. Five-token fresh-file reachability is not established; no invented
  spawns or original bomb/song gates were bypassed.
- Core heap still 51,200 bytes, moved to guarded/zeroed low RAM. Directory capacity
  768 in its own low carve; music triggers 90,334/131,072 bytes. SGL3750/3200 and
  sprite2400 unchanged. BSS end 0x0607b640, 35,264 bytes below SGL.
- 334 focused checks pass (`route-final-tests.log`), including production story
  state and music timing. `route-budgets.log` verifies bridge/Field/story banks.
  `route-artifact-audit.log`: all 453 ISO files match staging (455 directory
  entries), 13 changed target objects have no software-float helper matches.
  Build: `route-link-final.log`; no observed runtime-clear claim.

Remaining: human no-skip/skip boss-to-Field run, save/reload/return and listening;
full creation particles/aura colour/scroll, Tree death material fade, Link held
Ocarina, exact Ganon flashback motion and full owl head/eye/departure camera parity.
M7 Ocarina free play/staff/audio, M6 Woods/Meadow, side-content/token reachability
remain required. Registered unsupported Field exits use the explicit boundary;
three other owl placements are omitted. Do not mark all M5-M7 complete.

# M7 Field/owl asset budget passes - 2026-09-30

Human requires natural boss/Emerald/forest/Saria/Field arrival, owl and music.
Whole DEMO_PLAN reconciled. No runtime Field or new Clean build in this checkpoint.
Isolated 32-pixel base tiles + source tessellation fit Field, Link and both owl
texture banks: 411,520 / 445,432 bytes; 2,487 polys / 2,305 vertices with larger owl.
Old scene bake defaults and global budgets unchanged. Original owl models/clips,
bridge and Field cameras, owl theme and Fairy Ocarina fanfare now bake.
291 focused source/assets/boss/gameplay checks pass. Source unknown bridge clips
remain reported, not silently replaced. Source Field music is a phrase controller.

Natural route remains blocked by unimplemented Tree aftermath / Saria handoff,
Field registration/intro, live owl and music ownership. High RAM still only 144
bytes free in current Clean; 379/384 disc entries used. Recover budget before
runtime integration; do not lower heap/SGL or silently omit story to squeeze in.
See game/docs/M7_FIELD_PREFLIGHT.md and build/field-preflight manifests/logs.
Human owns runtime testing. Usual game/build/game-clean.cue remains prior build.

# Feedback / chest and shop fanfare checkpoint (2026-09-30)

Supersedes older current build numbers below. Usual Clean rebuilt; no emulator
run, commit or push. Human visual/listening acceptance pending. Full plan
reconciled; source audit and open parity work: game/docs/FEEDBACK_AUDIO_AUDIT.md.

- Large chest had no opening-song runtime call. Imported child opening clip
  appended as 120; pose/chest/camera presentation runs on independent clock,
  reward text hidden until opening ends; then ITEM_GET CD song. World and disc
  streaming stop before CD starts. Shop fanfare transactions now play ITEM_GET;
  first ammo corrected to ITEM_GET; Gold tokens SMALL_ITEM; minor chests chime.
- Red enemy damage, blue stun and pulsing red Link hurt filters. 256 bytes of
  resident VDP1 shade tables; no added sprite slots. Per-instance state and
  command attributes do not leak; source timing converted to 30 Hz.
- Correct/appear switch cues, shutter open/close, freeze and real landing
  BODY_HIT added. Offline SFX layer calls supported. Tree bank 2 / boss bank 3;
  Tree 78,510 / 88,924 bytes. Source synthesis and full sound coverage remain
  incomplete; audit lists web/fire/platform/boss/story gaps.
- Fixed aim/projection pitch sign mismatch. Camera positive pitch looks down;
  projectile positive pitch goes up. This corrects prior projection test.
- 346 focused checks pass, plus earlier 8 prop-asset checks. Usual Clean BSS
  0x06083f70 (144-byte margin); heap 51,200 and SGL 3,750/3,200 unchanged.
  Cold code size optimization and initialized fog lookup in low work RAM.
  ISO 379 files; boot/LINKANIM/all changed PCM payloads match staging.
  Forest room 1 VRAM spare 34,432; boss room 1 spare 66,064. Fifteen changed
  target objects have no matched soft-float helpers. Logs game/build/feedback-*.

Chest camera is an opening-orbit adaptation, not full source camera/light/
held-item presentation. Hurt tint approximates N64 fog; sparks/hitstop and
Gohma custom materials remain. Do not claim full 1:1 or complete dungeon.
Human next: fresh chest -> opening song/pose -> item song/text, buy shield,
quick/refused purchase, token, enemy hurt/stun, Link hurt, door/switch sounds;
confirm songs finish and bank/input return, then resume full dungeon route.

# Tree playtest fixes: aim, switch carry, scrub and sound (2026-09-30)

Current checkpoint supersedes older build/status values below. Usual Clean
rebuilt at game/build/game-clean.cue / .iso. No emulator run or commit/push.
Human runtime acceptance pending; full dungeon/story milestones remain open.

- Tap assigned slingshot slot enters aim, further taps fire, cancel exits;
  release/neutral axes retain aim. Target held (Xbox RB / Saturn Z) permits
  direct one-press seed toward actor focus, including elevated targets. RT
  remains shield. Center and enemy/POI markers reuse resident message glyphs;
  original animated lock reticle remains a parity gap.
- P1 switch launch: compressed mesh replacement reset DynaPoly history to
  origin; BG_DYNA_POS then carried Link by the entire world transform.
  Stationary floor switches now omit carry. Real offset room-10 regression
  proves no x/y/z carry across depression; moving platforms keep carry.
- Hint Scrub range 0 (70) was inside hide distance 120. Source default range 3
  (350) restores acquisition at spit distance; attention_find checked at
  200/400. Body, flower and nut skip transparent palette zero; no new texture.
- Tree/boss selected bank 0, silencing area effects. New bank 2 SFXTREE.PCM
  adds scrub rise/burrow/spit/walk/reflected-hit/faint, floor/eye click and
  Baba/Skulltula/larva/Gohma hit/death channels. Events persist until consumed
  once; existing reflection/nut impact now have a bank. Reduced PCM rendering
  omits vibrato/glides/legato/shared synthetic layer/reverb; full fidelity open.
- Prop exporter creates generated/ before dependent exporters, fixing fresh
  temporary-directory asset tests. No shared SDK changes.

285 focused tests pass: gameplay 199, mechanisms 29, audio 20, camera 11,
prop assets 8, boss 7, real door collision 4, directory 4, aim/projection 3.
Logs in game/build/: current-gameplay-tests.log, current-prop-tests.log,
final-playtest-checks.log, current-playtest-build.log, current-vram-check.log,
final-artifact-check.log. Full-suite green not claimed.
BSS 0x06083ef0: 272 bytes below SGL. Size-optimized boot/file/level setup and
audio dispatch preserve 51,200-byte heap and SGL 3750 polygons/3200 vertices.
Sound bank 78,264 / 91,874 bytes (13,610 spare). Per-room VRAM checks pass;
boss room 1 retains 66,320 bytes, 2810 vertices/3147 polygons. Eleven changed
SH-2 objects have no matched software-float helpers. ISO has 378 valid names;
boot, S7/S9, scrub BIN/ANM, ACTIONS and SFXTREE match staged bytes.

Next: human checks controls/markers, switch landing, scrub cutouts and sounds.
Agent continues remaining story/boss presentation/route work per DEMO_PLAN.

# First Tree door collision and 1.5x climb camera (2026-09-30)

Human says first upper door still blocks slingshot route; previous lift fix
insufficient. Reproduced with actual S7.COL and real C actor movement: both
sides stop at door-local depth +/-24. ROM has rectangular static aperture
seals, independent of raised shutter artwork/state. build_scene_table.py now
marks only matched shutter seals entity-ignore (34 Tree triangles, 2 boss-room
triangles); actor constrain retains closed/gated blocking. Camera/projectile
flags, frames, lintels, floors and unrelated walls unchanged. This adapts
source scripted passage to existing free-walk shutter handling. Progression
collision exporter uses the same conversion. No new runtime geometry/buffers.

New test_tree_door_collision.py reproduces original failure, verifies real
0<->1 and 1<->2 passage both ways, rejects frame passage, and checks exact
flag-only changes plus staged bytes. Existing gate/portal checks pass. Climb
follow target now 139*3/2 = 208 units, with obstacle clipping retained; exact
stationary distance and normal return pass. 46 focused checks total: collision
4, mechanisms 27, portals 5, camera 10. Human runtime acceptance remains open.

Usual game/build/game-clean.cue rebuilt, exit 0. BSS 0x06083f90, 112 B spare;
initial overrun rejected, then cold speaker-name formatting size optimization
restored fit without reducing heap/SGL. Log slingshot-door-fixes-build.log.
ISO inspection: 377 valid names; 0.BIN, S7.COL and S9.COL match staging.
No emulator launched. Rebuild verified no running Kronos. Prior build notes below
are historical. Current task: human retests first-door/slingshot route and climb.

# Human playtest fixes: death, climb and Tree text (2026-09-30)

Human finished testing and authorized rebuilding. Usual game/build/game-clean.cue
rebuilt successfully; compile/mastering and directory guard pass. BSS 0x06083ff0,
16 B below SGL. Log: game/build/playtest-fixes-build.log. ISO: 377 GFS-safe names;
boot binary, CUTTEXT.TXT and TREEMTH.BIN match staging. No emulator launched.

- Fatal Skulltula/fall landing on chest: held death reaction previously yielded
  to FALL when a later tick lost floor contact, leaving Game Over waiting forever.
  link_anim_state.c now finishes held reactions across airborne ticks. gameplay.c
  checks lethal landing before chest/pause ownership; demo.c requires actual
  ground contact, not zero vertical velocity alone. Exact human repro still pending.
- shared/lib/camera/oot_follow.c retains far follow distance while climbing,
  including idle holds. Normal distance returns on exit; collision still clips.
  This is a visibility adjustment within the existing range, not full Jump2 parity.
- main.c retains unchanged cutscene text instead of wiping every rendered frame;
  outgoing dialogue clears before cutscene text draws. Panel/text appearance
  still requires human review; no emulator evidence of full visual resolution.
- message.c expands tokens through ui_text_expand before wrapping and preserves
  colours/reveal. New bounded 2 KiB cart carve 0xA800..0xB000 stores layout and
  scratch (prepare stack frame 52 B); compile-time overlap/size guards added.
  main.c cold UI and game_over.c size optimization preserves heap/SGL capacities.

310 focused checks pass: gameplay 198, locomotion 26, message 30, traversal
camera 10, follow 36, opening scenery 5, UI preferences 5. New regressions cover
held death losing floor, lethal landing vs chest/pause, stationary climb distance,
and cutscene content/whole labels across all 5 presets, 2 pad modes, 8 jump bindings.
UI preference harness now supplies the existing cdda_volume dependency.
Changed message, animation, demo, follow, gameplay and Game Over objects show no
matched software-float helpers. Full-suite green and runtime acceptance not claimed.

# Usual Clean image and launcher choices (2026-09-30)

User rejects alternate image handoffs. Rebuilt usual game/build/game-clean.cue
with the filename/boot and prior human-route fixes. Compile/mastering exit 0;
BSS 0x06083ea0, 352 B spare. ISO inspection: all 377 names fit GFS; four renamed
assets and 0.BIN match staging. Log: game/build/clean-launcher-update.log.
Launcher and build chooser order: Play Dosei Legend (Standard) [clean/default],
Play Dosei Legend (320x480i) [hires], Debug Mode [normal]. Usual paths unchanged.
GUI smoke and read-only catalog checks pass. Human runtime testing pending;
no emulator launched. Bootfix handoff below is historical and superseded.

# P1 boot filename fix (2026-09-30)

Human screenshot: jo_fs_read_file_ptr cannot find TREEMOUTH.BIN at boot.
Cause: 13-character name exceeds SEGA_GFS.H GFS_FNAME_LEN=12 despite valid ISO.
Renamed runtime/export/staging/budget references to TREEMTH.BIN, BOSSHRT.BIN,
BOSSCLR.PCM and BOSSCLR.LVL. Logical song/bank names unchanged. Build removes
only the four obsolete staged names; directory guard rejects non-8.3 names
in build.sh and direct make mastering. Prevention rule added to project Bible.

Historical alternate image: game/build/game-clean-bootfix.cue (superseded).
Original game-clean image left untouched because human has it mounted.
Compile/mastering exit 0, BSS 0x06083ea0, 352 B spare. Four directory tests and
room budgets pass. Actual ISO: 377 names fit GFS; all renamed payloads and
0.BIN match staging. Logs: bootfix-build.log and bootfix-iso-check.txt.
Human cold-boot verification pending. No emulator launched. Earlier image's
342 host tests/build did not catch its runtime filename failure; not acceptance.

# Human route fixes (2026-09-30)

Human owns play testing. No emulator launched/input for this checkpoint.
- C-item HUD previously baked empty arrows only. Original stick/slingshot/nut
  patches now follow all three saved assignments, preserve Navi and labels,
  and invalidate the HUD cache on reassignment. VDP2 cells 9,344 bytes.
- Sword capsules could never hit normal Baba head/stem capsules: missing
  capsule/capsule dispatch. Added bounded integer finite-segment contact;
  Baba host tests now use a capsule blade rather than a forgiving cylinder.
- Room asset teardown reset shutters closed at the room boundary. Preserve
  lift/hold across room reload; reset on actual scene loads. Crossing check added.
- Added Bg_Treemouth mesh/collision and original meeting/choice/open/refusal
  scripts, chained text, selectable Yes/No, flags, approach/target gates,
  close-range Link relocation and timed mouth movement; original CHAN_24A1
  sound, Tree music and forest return. New scripts append IDs 5-8.
- Human allows existing Baba textures if room VRAM fits; recorded scoped
  exception in DOSEI-LEGEND-BIBLE.md. Outside withered and inside normal Baba
  are different original actors. Forest actor peak with mouth: 53,616 B/564 slots.

342 focused tests pass together. Full asset generation completed; first target
build rejected its RAM overflow. Bounded size optimization (collision, script
player, HUD/text, pause menu) preserves heap/SGL capacities. Final Clean compile,
boundary and mastering pass, exit 0: BSS 0x06083eb0, 336 bytes spare.
Image game/build/game-clean.cue; log game/build/human-fixes-master.log.
Changed collision/mouth/HUD/message/cutscene objects: no matched float helpers.
Human must verify meeting Yes/No/retry, source presentation/Link cue animation,
mouth/entrance, Baba damage/drops and doors both ways. Do not claim 1:1 runtime
acceptance. M4/M5/M6 remain incomplete; aftermath, full route and other plan
requirements remain. No commit. Earlier entries below are historical.

# Boss route, rewards and emulator dependencies (2026-09-30)

Current checkpoint; sections below are historical. DEMO_PLAN.md owns current scope.
Registered both Gohma rooms and original Tree exits/shutter. Added persistent
optional heart container, blue-warp timer and separate Emerald/aftermath flags;
original heart and warp assets, boss/clear BANK music and frozen heart CD fanfare.
Save format unchanged. Source aftermath cutscenes, boss/SFX presentation and
warp texture scrolling/appearance remain required; M4/M5/M6 are incomplete.

282 focused host checks pass. Clean compile/mastering and SGL boundary pass:
BSS 0x06083060, 4,000 bytes spare; game/build/boss-route-clean.log. Wrapper
exit 1 comes from native warning stderr. Budget guards pass, including boss
room 1 at 2,810 vertices/3,147 polygons, 66,320 VRAM bytes spare. Changed runtime
objects show no matched software-float helper references. New image cold-boots
to title in isolated Kronos. OpenAL error fixed by staging 29 installed MSYS2
runtime DLLs plus Qt platform plugin beside isolated and configured emulator;
no system DLL changes/downloads. Title capture: game/build/boss-route-check/title.png.
Background pad injection did not leave title in this run; no boss runtime or
fresh-file progression acceptance. Resolve test input, then validate boss route,
combat and optional rewards; continue Tree aftermath and M4/M6 required work.
Do not rebuild game-clean.cue while this test emulator mounts it. No commit.

# Plan maintenance and shutter ownership (2026-09-30)

Human requires every agent to keep the whole game plan current in the same task
as status changes. Standing rule added to AGENTS.md, CLAUDE.md and DEMO_PLAN.md.
DEMO_PLAN.md fully rewritten to reconcile scope, ownership, current code,
verification, open requirements and next work; old checkpoint evidence stays
in this handoff and M5_M6_IMPLEMENTATION.md.

Dungeon continuation: shutter interaction/collision and drawing now filter
by owning scene, not merely matching room numbers. This prevents cross-scene
doors during boss-room integration. Files: dungeon_doors.c, world_props_draw.c,
test_dungeon_mechanisms.py. Host: 25 mechanism checks and four Gohma checks pass.
Clean compile/mastering and boundary check pass: BSS 0x06082550, 6,832 bytes
below SGL. Log: game/build/plan-refresh-clean.log. Wrapper exit 1 is native
warning stderr; underlying build completed. No new runtime acceptance. Gohma code/render/camera
hooks exist, but boss scene registration, rewards and story remain unfinished.
No M4/M5/M6 completion claimed. Work uncommitted on dev.

## Active unattended dungeon work (2026-09-30, in progress)

User explicitly authorizes continuing through all M4/M5/M6, including Meadow,
without stopping for partial checkpoints. No milestone accepted yet.

Added source puzzle meshes/collision and runtime: floor/eye switches, rising
platforms, timed room-5 water, floating block, spike log, falling ladder,
collapsing platform, and both push blocks (basement solved position flag 16).
Floor-switch artwork is shared across four compression poses; per-room uploads
avoid VRAM overflow. Dynamic water overrides reset with scene/room ownership.

En_St hanging Skulltulas now have native models/clips, front/back damage,
nut stun, death/drop table 14. En_Sw wall/Gold Skulltulas and En_Si token
pickup added with source gold limb replacements, damage table 14, normal drop
table 3, gold source group/mask persistence. Withered Babas now use original
Tree placements and existing stick/regrowth behavior. Save v9 appends 32 token
flag bytes; v2-v8 migrate. Enemy states use guarded cart carves.

Current tests: 196 gameplay, 17 dungeon mechanisms, 28 save serialization pass.
Twelve Tree texture budgets pass; smallest spare is room 3 at 1,384 bytes.
Latest completed target build predates wall-spider/save-v9 changes; its BSS end
was 0x06080f80. New target build and in-dungeon Kronos checks still required.

Remaining required: normal Deku Baba, Hintnuts/projectile/reflection/dialogue
and 2-3-1 puzzle, Gohma larvae/eggs, breakwall, Gohma/boss-room route, dungeon
story/cutscenes/rewards, Woods/bridge/ocarina/Meadow and M6b content; remaining
M4 source/presentation work. Enemy/puzzle particles, sound, attention cameras,
Skulltula sway/bob/death presentation and wall alignment/chase source parity
still need work. Do not equate current host checks with playable-route proof.

# Ydan doors and fire checkpoint (2026-09-30)

Codex/Astra, uncommitted on dev. Human assigns all M4/M5/M6 and explicitly
adds Sacred Forest Meadow gameplay. **All three milestones remain incomplete.**

The screenshot's white shutter is reproducible in the baked asset: four door
faces had only white texels because object_ydan_objects references texture
segment 4 (gameplay_keep), which the prop exporter never bound. Binding it
restores source door artwork; DTDOOR grows from 552 to 1,192 bytes. Added Open
HUD prompt and consumed the pending A press so opening/refusal cannot also roll.
Barred-door refusal now survives gameplay_step's event reset.

Eleven source torch placements/models now load with stick-tip ignition, flame
transfer, 20 Hz timers, two-torch switch gating and water extinguishing. Burning
sticks refresh to 200 source ticks at a flame; new ignition lasts 210. Both
floor webs can burn; all five wall webs now have source meshes and collision,
with full YXZ placement rotation baked offline. Wall burn-switch/stick contact
and 30-source-tick removal persist destruction flags. Source actors
ObjSyokudai_Update, BgYdanSp_* and DoorShutter_* own no collectible drops.

Source temporary switches 0x20..0x3f now work outside serialized save data.
Scene load clears all, room cleanup clears 0x38..0x3f (z_actor func_80031B14).
This fixes the upper torch/shutter's switch 60, formerly always false. Save v8
layout remains unchanged. Original puzzle/enemy gates remain enforced.

Changed files: dungeon_doors/webs and new dungeon_torches modules; demo/input
ownership, minimap HUD prompt, world_props_draw, player_items, save_state,
kokiri_sgl flame rendering/room cleanup; world/shop prop exporters, new
build_dungeon_walls, build budget checks, Makefile and focused tests.

Host: 276 checks pass (196 gameplay, 10 mechanisms, 7 assets, 19 save state,
27 save-file, 5 room portals, 12 HUD). Real Dyna collision tested for wall-web
blocking, fire removal, unload and persistence. All 12 dungeon bank budgets
include every loaded prop: 24,480 B / 153 sprite slots; minimum spare 15,328 B.
Clean target compile/mastering and SGL boundary verification pass:
`game/build/game-clean.cue`, BSS end `0x0607ca30`, 30,160 B below SGL.
All generated assets were rebuilt; after two missing includes were repaired,
compilation/mastering resumed using those assets (`m4-m6-door-fire-link.log`).
PowerShell reports exit 1 for native warning stderr; the underlying make,
mastering and final boundary check completed. SH-2 disassembly of door/web/torch
objects contains no software-float helpers (`door-fire-disassembly.txt`).
Background Kronos reaches the title and renders the forest; capture
`game/build/door-fire-boot-later.png`. Initial capture was black during load.
No player input, dungeon traversal, door/fire visuals or audio listening tested.
The test emulator was closed afterward; the finished image is not mounted.

Required follow-ups: source hand/item models and pose/tip behavior; torch stand
OC/hard-hit colliders; source scrolling flame/particles, ignition/burning/web
and door SFX, web reaction cameras, shutter variants/bars and opening Link/camera
choreography. Current flames are small flat polygons; no source flame fidelity
claimed. Fire-arrow/Din fire interactions are unavailable in this child demo.
Dungeon switches/platforms/logs/blocks, enemies/drops/scrub sequence, Gohma and
story/rewards remain required. M4 compass/targeting/pad acceptance and M6 Woods,
bridge/ocarina, owls/minigames plus newly approved Meadow remain required.
No full route or visual/controller acceptance claimed from host checks.

# Dungeon room/door/floor-web checkpoint (2026-09-30)

Uncommitted on dev. All 12 Deku Tree room banks now registered in the normal
Clean build. Nine source shutters retain type/switch flags; the three En_Holl
passages use the existing streaming path. Shutters have original door geometry,
A-facing activation, lift/hold/close state, closed-door movement rejection and
source front/back clear/switch tests. Clear flags are not fabricated: absent
scrub/enemy/puzzle implementations still block the corresponding route.

Both source floor webs have original mesh/collision/placement and saved destroyed
flags. A central fall over 750 units begins the source-timed break; breaking
webs survive room streaming until their switch is set. Normal room unload removes
collision without granting progress. No source collectible drops for these actors.
Wall webs, fire/torch integration, switches/platforms, enemies, boss and story are
still missing. This is NOT a complete playable dungeon or M5/M6 acceptance.

245 focused checks pass, including real dynamic floor collision, room unload,
web-break persistence, shutter side/flag gates, swept closed-door collision and
all live room-bank files (including base-36 room A/B names). Clean build passes:
BSS 0x0607b510, 35,568 bytes below SGL; disc directory capacity 384. New SH-2
mechanism objects have no software-float references. Kronos boots to file select;
`game/build/dungeon-connected-boot.png` is boot evidence only, not traversal.
Build/test logs: `game/build/dungeon-connected-build.log` and
`game/build/dungeon-connected-tests.log`. Door animation/camera/SFX/A-prompt and
web edge deformation/particles remain presentation gaps; real gameplay testing
still required. Earlier checkpoint measurements and room-0-only status below
are historical.

# Dungeon pause map checkpoint (2026-09-30)

Fixed the map reward/menu mismatch: dungeon scenes now show the five source
Deku floor diagrams, menu directions select floors, visited rooms are blue and
map ownership reveals unexplored rooms. VDP2 only, using the existing page cache.
Save v8 persists visited rooms; v2-v7 migrate with unknown history clear.
Changed pause artwork/renderer, menu controls, gameplay visit recording and save
serialization. 229 focused gameplay/save/renderer checks pass; Clean build passes
with BSS 0x06079cb0 (41,808 bytes below SGL). Source-art preview inspected at
`game/build/dungeon-map-preview.png`; build log `game/build/dungeon-map-build.log`.
No in-game map/controller acceptance claimed. Compass markers and automatic
current-floor selection remain open (BUG-062). Full M5/M6 remains incomplete.
Uncommitted on dev. Earlier checkpoint measurements below are historical.

# Live items / Woods checkpoint (2026-09-29)

Uncommitted on dev. Live ten-room Woods streaming, source area music, C-item
stick/seed/nut combat, six dungeon chest exports and v7 map/compass saves added.
Final Clean BSS 0x06079850: 42,928 bytes below SGL.
341 focused checks pass. Low-RAM sprite/music relocation frees work RAM; disc
capacity 320 covers 293 entries. Foreground boot/title rendering verified.
**Full M5/M6 remains unfinished:** dungeon puzzles/enemies/Gohma/story, Woods
encounters/minigames and bridge/ocarina progression still required. No debug
item grants or open-door substitutes. Detailed limits and bug records:
[implementation checkpoint](game/docs/M5_M6_IMPLEMENTATION.md).

Earlier sections below are historical.

# M5/M6 autonomous checkpoint (2026-09-29)

Codex owns M5/M6 by current human instruction. Partial implementation: all 24
source rooms inventoried and independently baked; invisible room portals now
scene-aware with source vertical/horizontal bands; post-Emerald exit guard and
Mido departure/house population behavior implemented and host-tested. Room
metadata moved to guarded low RAM after a measured 128-byte SGL overrun.
Normal player disc still exposes the existing dungeon room-0 shell. Full M5/M6
gameplay is NOT complete. Required actors, puzzles, boss, story, Woods encounters
and runtime acceptance remain. Details: [checkpoint](game/docs/M5_M6_IMPLEMENTATION.md).
205 focused tests and Clean build pass; BSS 0x06083720, 2,272 B below SGL.
Foreground Kronos boot/title/forest render verified after launching outside the
sandbox; NPC/transition gameplay remains unverified. No commit/push.

## Song dictionary / Music Workshop (2026-09-29)

Game music now uses stable NA_BGM_* IDs through a tracked BANK/CD dictionary.
Workshop edits song routes by name; physical CD positions remain in the disc
manifest. Reordered-track audio cache and cue generation fixed. Help updated.
53 focused tests and GUI checks pass. Final Clean built with 288 B below SGL
(BSS 0x06083ee0); no Kronos listening check. No commit/push for this work.

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

# Vertical slice progress

## M3c/M3d Astra source checkpoint (2026-09-28, unbuilt)

- Human released shared files after Claude finished; requested no build.
- Source drop tables/filtering, pots/rocks/carry/throw, signs, placed hearts,
  decorative props/gossip hit reaction, five animated chests and get-item pose.
- Save v6 migrates forest collectible bits; prior saves remain readable.
- Claude shop preserved; primary-texture heart/nut scrolling added. Fado and
  conversation flags wired; old Navi timer branch bug fixed.
- Last built Clean gap 7,424 B predates these changes. Current RAM/VRAM unknown.
- No disc regeneration, Kronos test or commit. Exact coverage, tests and remaining
  source-parity work: [M3c/M3d checkpoint](game/docs/M3CD_IMPLEMENTATION.md).


## M3b Astra integration checkpoint (2026-09-27, uncommitted)

- Four remaining Kokiri interiors wired; six interiors total with Link home/shop.
- Scene-aware NPCs: 17 placements, including three child Know-It-All brothers.
  Fixed the rotZ adult-variant filter and preserved original forest identities.
- ROM meshes and initial source clips for Mido, Saria and all 13 Kokiri types;
  per-vertex flex ownership, flat body/hair, textured faces. Room-safe transient
  VDP1 bank, source head pivots and animated attention focus. Exit guard follows
  its source 80-unit ring. Full tracking/talk-animation/fade/blink parity pending.
- Original house/shop sequences, seven cart trigger banks; fixed carve 0x7C000.
- BUG-006 ledge-before-talk fixed in code. Clean RAM gap 7,152 B.
- Host checks pass for gameplay, actors, model tracks/head math, actor pool,
  character materials, area music and ledge priority. Opening-audio harness still
  has pre-existing missing camera/menu-duck stubs. No Kronos acceptance claimed.
- Disc keeps the normal `game/build/game-clean.cue` name. Nothing committed.

## M3a contracts (2026-09-27, uncommitted)

- Full child-day actor manifest for forest + 6 interiors (docs/M3A_ACTOR_MANIFEST.md);
  30 unported kinds listed, none hidden.
- One Item_Give/shop-buy path; save v5 adds Deku Nuts (older saves migrate).
- Generic 2/3-choice text with En_Ko branches. Death Save No / Continue fixed
  in code; RAM freed (SGL gap 13,616 B). Kronos checks pending.

## M2b.1 starter route (2026-09-26, uncommitted)

- Ground sword/shield gone. Sword from maze chest (En_Box 0x04E0), shield
  bought in new Kokiri Shop scene for 40 rupees (VDP2 Buy/Don't buy choice).
- Rupees before sword: source En_Item00 + En_Wonder_Item triggers, 43 total.
- Mido blocks the Deku Tree path until sword AND shield equipped, then walks
  aside; flags persist. Gear is owned on grant, equipped on the pause screen.
- 75 gameplay tests pass. Clean built; work-RAM gap 5,488 B (BUG-033).
  Human route check passed (2026-09-26). Stand-ins BUG-031 and boulder
  BUG-032 remain pending; BUG-033 memory work is next priority.

## M1l traversal camera core (2026-09-26, uncommitted)

- Hang/climb framing, eased return and traversal camera collision added;
  malformed crawl-camera paths fall back without hiding Link. Normal follow
  behavior preserved. Source adaptation gaps remain BUG-027/017/025.
- 161 focused tests pass. Clean built; SGL gap 16,592 B. Human camera check pending.
- Human has no available pond test; water acceptance remains pending.
- Dialogue special-character rendering and VDP2 dither backdrop logged separately
  as BUG-026, per human request. No dialogue UI change this turn.

## Astra continuation through M1k water core (2026-09-26, uncommitted)

- BUG-021 grass pass-through and pickup height fixed; human test passed.
  Rustle FX/SFX follow-up is BUG-024.
- M1g turn/bonk human pass. M1h push core, M1i lift hooks/strengthless bush
  failure, M1j slope motion/fall policy added; remaining live actor and health
  integration is explicit in BUG-020/022/023. Push-block live fixture deferred.
- M1k swim, A-held dive/release, float and sloped-bank exits wired; six clips
  in cart animation data. 14 water tests and 210 affected tests pass. Real
  forest pond-to-bank and ydan water-room filtering tested on source geometry.
- Clean image built, SGL gap 18,144 B. New water runtime needs human check.
  BUG-025 tracks source subset gaps and M2/M5 drowning/dungeon dependencies;
  full M1 is not complete. Remaining traversal camera modes come next.

## Demo M1f crawlspaces (2026-09-26, uncommitted)

- A at a crawlspace hole enters; crawl forward/back; exits at the far wall
  or backs out. Real sword-maze tunnel host-tested both ways.
- Fixed grounded ceiling range (BUG-016) and still-standing wall contact.
- Clean image built. Kronos check pending.

## Demo M1e ladder and vine climbing (2026-09-26, uncommitted)

- func_8083EC18 starts (walk into a ladder / vines / FLAG_2 top, jump onto a
  tall climbable wall, walk off onto vines); Player_Action_8084BF1C climbs by
  the clips' root motion (15-unit rungs), stick speed, vine sideways, A lets
  go; ladder top/bottom step-offs, vine top pull-up.
- Link's house ladder climbed up onto the porch and the forest vine wall
  (host tests on S1.COL). Climb-down from the porch: see BUG-015.
- Source point-in-poly slack (BUG-013) fixed; BUG-012 fixed.
- 12 new host tests. Clean image built. Kronos check pending.

## Demo M1d ledge hang, pull-up, let go (2026-09-26, uncommitted)

- Walking off a drop deeper than 45 hangs on the face just left
  (func_8083A6AC); a descending jump or fall grabs a ledge ahead
  (Player_Action_8084411C), including the 250 jump from M1c.
- Hanging: stick pushed pulls up (fall_up / jump_climb_up), A held lets go.
  Six new clips; LINKANIM 103,752 B.
- BUG-011 fixed (released pad no longer interrupts a climb).
- 10 new host tests (test_player_bg 37, controls 53). Clean image built.
  Kronos check pending.

## Demo M1c step-up, wall/ledge probe, ledge climbs (2026-09-26, uncommitted)

- Link's movement follows Actor_UpdateBgCheckInfo's order: wall sphere
  (r14 at +26), ceiling headroom 40, floor ray from +50. Steps up to 24
  are walked up (before: walked through, or blocked at 15+); 25+ block at
  the wall. Roofs lower than 40 stop him.
- Player_ProcessSceneCollision wall/ledge probe + Player_ActionHandler_12:
  hop (25-26), 100 step up (27-38), 150 step up (39-46), 250 jump start
  (47+; mid-air grab is M1d, he lands back). Timer 9 steps, or A.
- Child root x0.64 in every gameplay clip (source); ground shift +18.
  New clips step100/step150/jump250. CLIMB_END voice added.
- 28 new host tests (incl. real S1.COL ledges). Clean image built. Kronos
  check pending.

## Demo M1b gravity + automatic ledge jump (2026-09-26, uncommitted)

- Source gravity (-171 Q8, terminal -20/step). Y jump keeps 51 apex.
- Running off an edge auto-jumps per func_8083AA10/func_8083A4A8 (run_jump
  or jump clip, run_jump_end landing). Walking off falls. Floor property
  7/8 and swinging block leaving.
- 13 new host tests. Clean image built. Kronos check pending.

## Demo M1a world-collision contract (2026-09-25, uncommitted)

- S<n>.COL now KBG2: raw SurfaceType words, poly ignore/conveyor flags, water
  boxes, bgCams. `.SUR` retired. Runtime `bg_*` queries report hit poly,
  owner (static 50 / dyna id), surface bits; D_80119D90 wall flags.
- DynaPoly slots (cart carve): register/set/enable/remove/carry; real
  gPushBlockCol mesh host-tested. Old movement API unchanged, sees dyna.
- Link clip frames moved to LINKANIM.BIN in cart: clean SGL gap
  4,624 -> 49,568 bytes.
- 19 new contract tests on real S1/S0/PUSHBLK. Clean image built.
  Kronos check pending (no emulator run).

## Save crash repair and permanent shot skip (2026-09-25, uncommitted)

- Save crash traced to stale save_device.o: 220-byte v1 stack buffer called
  the 300-byte v2 packer. Compiler header dependencies now rebuild consumers;
  makefile edits invalidate all objects, including SDK configuration.
- Permanent Start confirmation: "Skip? Press Start Again", two-second window,
  current source camera shot only. Final shot follows normal sequence cleanup.
- Work-RAM malloc arena now 51,200 bytes; cart remains allocator fallback.
- Focused host tests pass. Fixed save/skip still need a player replay in Kronos.

## Demo M0 foundations (2026-09-25, uncommitted)

- Face-only character textures (hair flat); Link 143 tiles.
- Base-36 scene/room asset names (36 scenes x 36 rooms, still 8.3).
- Save v2 with 11 scenes; old saves rejected as older version.
- Actor pool (cart carve) + actor collision check skeleton, host tested.
- Area SFX banks: core + swappable area slot; forest bank holds grass cut.
- Builds: all three images; Kronos check still pending.

## Opening freeze, sound and close-up (2026-09-22)

- Reproduced nightmare stall at Kronos's 2048-command guard; project-local
  emulator fixes it and launcher config selects that executable. Replay passed
  into scene 2. See `game/docs/OPENING_FREEZE_2026-09-22.md`.
- Rain geometry now survives SGL's deferred slave reads. Automatic text uses
  source post-reveal delay without the added length-based wait.
- Nine source-derived opening effects use a 32,836-byte bank in the existing
  action-SFX tail. Music starts at Ganon's frame-330 cue; music fades leave SFX
  slots audible. Source layers/envelopes are reduced; audible mix remains
  unreviewed, not claimed as exact original sound parity.
- Nightmare Link uses source scale/origin. Bridge fly-by gets a smooth side
  arc and head aim, visually checked at frame 185 without face clipping.
- 86 focused tests pass. Normal/clean builds pass SGL boundaries with
  8,544 / 19,248 bytes spare. Player discs contain no camera-test frame hold.

## Opening readability and scenery (2026-09-22)

- Text/NONE commands no longer erase an unread message at its hold boundary.
  Automatic fade pages retain the source delay after reveal; the extra
  length-based hold was removed after feedback. Button pages retain marks.
- Cutscene panels use a small padded charcoal mesh fill and bright cyan text.
  Overlay depth follows the shot near plane; separate X/Y sprite scaling fixes
  the oversized panel. Full-cover narration keeps UI sprites visible.
- `CS_TRANS_TRIGGER_INSTANCE` is no longer an opaque black fade. In original
  `z_demo.c` it changes transition control, not screen-fill alpha; the old mapping
  hid the Deku Tree from frame 70 through his speech.
- House shots use the four original `vr_LHVR_static` pre-rendered panorama faces,
  with source palette order and cube orientation. Ordinary house gameplay keeps
  its fixed JPEG. Kronos showed the doorway/Navi and sleeping Link against the
  panorama with zero rejected draws.
- Navi's flight uses banks derived from all three streamed forest room meshes,
  retaining trees and huts across room boundaries. Banks cover 100 camera frames;
  textures outside the span's possible fog view are omitted, distant faces are
  flat fog colour, and runtime faces beyond fog range draw flat. This is bounded
  per-shot residency, not a new per-frame VRAM allocator. Forest bank textures
  occupy 54,656–307,488 bytes; the house panorama uses 135,168 bytes.
- 72 focused cutscene/message/room tests pass. Final colour/panel sizing and the
  complete forest bank-switch flight still need a player check; the background
  emulator later entered BIOS setup. No global input or desktop capture used.

## Lock camera, rupee melody and pause controls (2026-09-18)

- Target camera now eases behind Link on acquire and tracks target-facing yaw
  while idle/strafe/backing up. Facing refreshed after movement. Release returns
  to normal follow. Full KeepOn1 framing/collision still pending.
- Added missing source rupee melody, BF4/F4/BF4 +24, over quieter backing layer.
  Looping source wave uses 64 bytes; 96-tick/sec sequence scheduled at vblank.
  Bank 39,832 bytes, 104 spare. Envelope/sample-duration approximation remains.
- Pause lists gameplay, lock/re-centre, look, roll and menu controls. C items
  explicitly pending; diagnostics chord shown only in diagnostic builds.
- Normal, clean and hi-res discs rebuilt. 278 tests pass, one skip.
  Emulator visual/listening confirmation still pending.

## Rupee HUD and pickup feedback repair (2026-09-18)

- Counter was rejected by SGL: screen-space sprite depth 1 was inside near
  limit 30. Depth 31 fixes submission; host test now checks actual SDK limit.
- Hi-res HUD doubles screen Y/height explicitly.
- Rupee collection routes original OoT sample layer to dedicated SCSP slot 29.
  Reduced single-layer chime; full original layered sequence still absent.
- Exact silent tails trimmed to fit bank: existing audible PCM unchanged.
  39,764 bytes; 172 sound-RAM bytes remain.
- Normal, clean and hi-res discs rebuilt. 274 tests pass, one skip.
  Emulator visual/listening confirmation still pending.

## Rupees and grass drops (2026-09-18)

- Eight original room rupees; green +1, blue +5, child wallet caps at 99.
- Cut grass rolls rupee subset of real source drop tables. Hidden until cut,
  visible hop before pickup, no repeated credit. Non-rupee drops still absent.
- Original rupee HUD art and digits; world billboards share icon silhouette.
  Source green tint, blue recolour. +3,584 VDP1 bytes, guarded offline.
- Both discs rebuilt. 273 tests: 272 pass, one skip. No new emulator capture.

## Grass sprites and movement audio (2026-09-18)

- Original OoT grass cutout now renders as VDP1 sprite at each grass actor.
  Room/distance culling, shared texture, and cut-state hiding implemented.
- Successful jump voice, roll voice/body sounds, walking/running footsteps
  wired to physics/animation events. Idle, blocked movement and airborne travel
  produce no footsteps. Forest uses one footstep material for now.
- Music unchanged. Action bank 39,168 bytes; 768 sound-RAM bytes spare.
- Both player discs rebuilt. 264 tests: 263 pass, one skip. No new emulator
  visual/listening confirmation.

## Equipped limbs and sound effects (2026-09-18)

- Original OoT hand display lists now show equipped sword/shield on correct
  bones. No gear before pickup; no duplicate back sword/shield. Equipped gear
  stays in hands for baseline play. Full draw/sheath transitions still absent.
- Swing, guard, cut, equip and dialogue/menu effects wired to events; sword
  attacks rotate four real child Link voice samples. Effects are reduced
  single-layer sample adaptations, not complete N64 sequencing.
- Separate SCSP slots/tail bank preserve music resources; offline/runtime
  boundary guards retained. 33,486-byte effect bank fits with 3,378 bytes spare.
- 261 tests: 260 pass, one skip. Background Kronos capture blank; runtime visual
  and listening confirmation still needed. Player discs contain no probe mode.

## Combat/menu repair (2026-09-18)

- Sword and shield state now drive imported OoT slash/recovery and guard poses.
  Previous code only chose locomotion clips, so combat had no visible pose.
  Slice attack timing remains approximate; held-gear geometry and SFX pending.
- Gameplay action clock now runs per 30 Hz step, including catch-up. Menu input
  blocks look/action leakage; closing frame suppresses movement/jump. Debug HUD
  no longer paints over dialogue/inventory. Menu clears its full text area.
- Clean player display includes pickup/equip instructions, controls and action
  feedback. Streaming enabled by default; binary room-bank policy checks added.
- 256 tests: 255 pass, one legacy single-bank suite skips; separate binary-bank
  check passes. In-emulator action/menu visual verification still outstanding.

## Latest: textures restored; overlap unresolved

User stopped experiments. Floor/water texture sampling restored; failed
actor-order probe disabled. [Claude Opus instructions and evidence](game/docs/CLAUDE_OPUS_FLOOR_OCCLUSION.md).

## N64 room streaming and texture warp: prototype, not finished (2026-09-18)

User-approved direction and future-session checkpoint:
[real N64 rooms, object culling, tunnel loading](game/docs/N64_ROOM_STREAMING.md).
Experimental room build succeeds in isolated workspace. Root player images not
promoted. Latest water-order fix and tunnel traversal still unverified; only
2864 bytes remain below work area in latest probe. Older test/budget claims below
not validation of this prototype. Next session must read checkpoint before changes.

## Saturn pad control remap (2026-09-18)

- Approved layout landed: D-pad moves, B toggles walk/run, Y jumps, A interacts,
  X attacks, L recenters, R shields, hold C + D-pad emits the four N64 C
  buttons, hold Z + D-pad aims a bounded look camera. Start still toggles title.
- One VBlank snapshot feeds one mapping layer (`game/src/player_input.c`); the
  fixed step only applies its decisions. Priority is Z, then C, then movement,
  and a consumed direction never leaks into locomotion.
- Walk is 3 units/step vs run's 5.5; both normalize diagonals, and the walk clip
  is chosen from distance actually travelled.
- PENDING, no system to drive yet: A interact, X attack, R shield, the C item
  interface, pause on Start, and full Z-targeting. Each is routed and counted in
  the diagnostic overlay, never substituted with other behavior.
- L+R diagnostics chord is compiled out of the clean player image so targeting
  and shielding can be pressed together there.
- 186 host tests pass (39 new); standard and clean images built. Controller feel
  and the look-camera rates still need Kronos confirmation.

- Fixed jump/fall visual sinking: remove FALL clip's ~82-world-unit authored
  root descent, keeping rotations. Physics alone owns airborne travel. Added
  actual-skinned-mesh bounds/run-transition regression, not just data parity.

## Manual jump (custom feature)

- Y jumps only from ground (was A before the 2026-09-18 remap); one jump per press, no airborne retry or held repeat.
- Existing gravity/air steering/airborne clip; roughly 52-unit jump height.
  Swept head clearance stops upward motion at low ceilings.
- Host physics checks pass; controller feel still needs runtime confirmation.
- Development moves to `dev` after the main checkpoint.

- Clean player-test image: `game/build/game-clean.cue` (`./game/build.sh --clean`).
  No in-game diagnostic HUD; independent objects/image, safety checks retained.

## Title flights (2026-09-16)

- Replaced low tunnel routes with eight elevated main-village fairy shots:
  clearing traverses, pull-back reveals, rising cranes and diagonal flybys.
  Ten seconds each, eased travel, cuts between subjects. No stationary swivels.
- Subjects frame beside the logo at x=60/260, not behind its centre. Baked aim
  replaces rounded path-tangent steering. Runtime remains integer-only.
- Builder checks flight segments and sampled sight lines against collision.
  Native test runs actual camera C across every tick of all eight shots,
  checks travel, bounded changes and subject projection outside logo centre.
- Both images rebuilt; 141 tests pass. Existing world clipping is separate.

## Link model ownership and face (2026-09-16)

- Fixed 24 ignored matrix loads: bone ownership captured per vertex, not limb.
- Shared OoT Flex ownership helper rejects unsupported transforms. Import rules
  and regression requirements now in DOSEI-LEGEND-BIBLE.md, linked from CLAUDE.md.
- Preserve local precision, tiny animated faces and fractional world output;
  use native near head with artwork. Background actor capture shows joined
  limbs and coherent face. All poses/sorting cases not visually certified.
- 140 tests pass; normal/hi-res images rebuilt without inspection mode.
- Actor texture growth reduces adaptive forest texture budget by 7392 bytes;
  geometry unchanged. Floor penetration and large-plane clipping still open.

## FPS regression and camera height (2026-09-16)

- Removed SH-2 software float in skinning: measured ~97 ms -> ~7 ms.
- Forest partition avoids redundant copies; invisible fog palettes untouched;
  channel lookup preserves colors; stationary view reuses preparation.
  Fog samples ~17 ms -> ~3-4 ms. Fixed-view 15 -> 20 VDP1 FPS. Moving samples
  reach 19 but fluctuate; sustained 30/60 is NOT verified.
- Corrected FRT conversion/accounting and added nested stage timing.
- Follow aim = feet + height + offset, verified in decomp. Background capture
  frames Link; camera/terrain collision remains absent.
- Animated Link no longer culls against stale bind-pose normals. Flat baking
  and sorting artifacts are separate remaining issues.
- Human's repeatable floor penetration OPEN: nearby host replay did not
  reproduce it. HUD records Y now. Nearby-safe recovery retained.
- No-FPU rule in CLAUDE.md; testing stays background-only.
- Down no longer chases opposite facing; rear-half-plane yaw held unless L
  recenters. Host regression passes; interactive feel check pending.
- 125 tests pass; normal and hi-res discs rebuilt without autonomous probes.
  Last moving capture: VDP1 19, WORK 31.3 ms, sync 18.8 ms. Not a full FPS fix.

## Low-FPS lost button presses

- Background capture confirms VDP1 8 / VDP2 58, zero submission refusals.
- Start/L now latch rising edges at VBlank until slow gameplay consumes them.
  100 host tests pass. No speculative camera/render optimization applied.
- FPS bottleneck still open. Existing emulator was not restarted or disturbed;
  runtime confirmation of rebuilt latch fix remains pending.

## Gameplay controls supersede the viewer

- Removed R orbit from gameplay; actor-mode controller ignores both shoulder
  orbit bits. 87 host tests pass, including shoulder yaw invariance.
- Settled digital-pad layout and real OoT camera implementation assignment
  recorded for Claude at the top of OPUS_HANDOFF.md. Only orbit removal landed
  in this change; the remaining actions/camera parity are explicitly pending.

## Digital-pad speed and camera follow-up

- Child outdoor run speed corrected to 165 native world units/s, including
  fractional travel and normalized diagonals; free camera unchanged.
- Animation slowed to a tuned 20 source frames/s with pose interpolation and
  decimated-fall timing corrected. Exact N64 action-specific cadence remains
  outside this change; gameplay feel still needs confirmation.
- L recenters behind Link; full targeting is not implemented. Remaining pad
  remap is a proposal in OPUS_HANDOFF.md, not silently applied.
- Standard and hi-res images rebuilt; 81 host tests pass. No claim of runtime
  visual verification; user's desktop/game focus was not touched.

## Animation frame decoder correction

- Fixed player animation record stride: 134 bytes, not 132. The missing
  trailing face word corrupted every nonzero frame's root and limb data.
- Added independent nonzero/decimated-frame regression fixtures; 75 tests pass.
- Rebuilt standard and hi-res images. Runtime blinking/tumbling and smoothness
  still need gameplay confirmation; no controls or physics changed.

Scope: [VERTICALSLICE.md](VERTICALSLICE.md). Update this file as work changes;
older handoff snapshots are not the current checklist.

## Snapshot — 2026-09-16

Layout update: active Jo project is now `game/`; the performance reorganization
is integrated into main. See [Opus's next task](game/docs/OPUS_HANDOFF.md).
Shared code/assets are under `shared/`; launcher and tri/quad workshop recovered
under root `tools/`. Legacy libyaul work is archived and excluded from active
builds. Standard/hi-res builds and 39 game plus 10 workshop tests pass after moves.
The workshop still produces editing candidates, not runtime-ready quads.

| Area | Status | Next useful step |
| --- | --- | --- |
| Forest | Hybrid textures and capped close-ground/treeline subdivision implemented; moving Kronos probe checked | Human close-view playability check; remaining affine distortion is not declared eliminated |
| Title/prompt | Implemented and observed in Kronos | Preserve |
| Playable Link, camera, collision | Implemented; 30 Hz gravity follows ramp/ledge departures | Confirm fall feel in Kronos |
| Animation | Runtime skinning; idle/walk/run/fall/landing/roll driven by actual motion | Human check of the walk/run read and landing feel in Kronos |
| Music | Two banks and reusable player in `b8e1642`; later streaming/timing edits included in this checkpoint | Good enough; no timing gate |
| NPC/dialogue | Not implemented | One complete proximity conversation |
| Menus | Title toggle exists; gameplay menu not implemented | Functional navigation/confirm/cancel |
| Sound effects | Not implemented | Movement, interaction and menu feedback |
| Hi-res | Separate 320x480i image built; forest/title observed in Kronos | Human visual comparison; not a warping fix |

## Acceptance boundaries

- Earlier captures showed title/gameplay with zero submission refusals; that does
  not prove warping fixed or all collision/camera cases correct.
- Music timing diagnostics are not an acceptance gate.
- Native hardware hi-res appearance is unverified.
- Bosses and dungeons are excluded.

## Next

1. One NPC with prompt and advance/dismiss dialogue.
2. Menus and sound effects, then a short slice playthrough.

## Update convention

Record date, behavior delivered, brief evidence and user-visible limitations.
Do not turn this into a benchmark checklist.

- 2026-09-16: Human confirmed the near-camera warping is playable, closing that
  priority. Link is now animated: idle, walk, run, fall, landing and roll are
  baked from the US 1.2 animations and posed at runtime by a skeletal skinner
  (`game/src/link_anim.c`), rather than pre-baked per frame -- one POINT table
  is ~3.9 KB and only ~9.4 KB of .bss was free. Locomotion is driven by the
  distance collision actually moved Link, so walking into a wall idles instead
  of running on the spot. Landing follows OoT's own branch, verified against
  z_player.c: short landing under 80 units, landing roll under 800 with forward
  motion. The roll is a landing behavior, not an automatic mid-air roll.
  Jo's malloc arena was trimmed 221,184 -> 180,224 bytes to pay for the clip
  tables; measured demand is ~17 KB and the A overlay now prints heap usage.
  Both images build (27,088 / 26,864 bytes of .bss headroom) and 69 tests pass,
  including a check that re-posing the bind pose from the skinning tables
  reproduces LINK.BIN's own vertices. Not yet confirmed in Kronos: how the
  walk/run threshold and the landing transitions actually read in motion.

- 2026-09-16: Astra took over the texture work. Source-UV hybrid rendering is
  now active, with shared repeating tiles, larger ground bakes and limited
  geometry splits. Old near-treeline disappearance reproduced; new split path
  retains it on the approach/turn probe with zero refusals. 52 game tests pass.
  Total with Link: 2,446 polygons / 2,112 vertices / 425,288 VDP1 texture+CLUT
  bytes. Collision and title/music unchanged. Render-component metadata exists
  for future hut/tree visibility; runtime culling is not implemented.
  Details/evidence/fallback: [texture handoff](game/docs/TEXTURE_PLAN.md).

- 2026-09-16: Established scope/progress tracking. Preserved current Link,
  collision and music-transition work for the main-branch checkpoint. Added
  a separate hi-res comparison path without replacing the standard launcher.
  Both builds passed their link-time memory checks; 39 viewer tests passed.
  Hi-res boot capture: `game/build/generated/hires-check.png` (local/ignored).

- 2026-09-16: Added persistent vertical velocity and floor landing for Link.
- 2026-09-16: Added map-wide void recovery to Link's most recent grounded
  position, and made gravity probe from his feet so overhead bridges cannot
  mask the ground below him.
- 2026-09-16: Added OoT's 11-unit grounded floor tolerance to downhill actor
  movement. Link now follows walkable ramp geometry continuously without the
  gravity/landing bounce, while larger ledges still start a fall.
- 2026-09-16: Replaced the title's fixed-position spin with the former hybrid
  texture probe's 12-second ground and Great Deku Tree camera tour. The route
  is driven by VBlank time and does not alter the gameplay follow camera.
- 2026-09-16: Expanded the title attract sequence to five shots covering the
  village, central field, Great Deku Tree room, and Lost Woods/training room.
  Added an OoT daytime blue horizon gradient on the Saturn back screen and
  animated fairy billboards at the ten original Kokiri/Saria/Mido homes; NPC
  models remain deliberately absent.
  Gravity is fixed-point and time-scaled from OoT's normal -1 acceleration and
  -20 terminal velocity at 20 Hz to this slice's 30 Hz update. Link now falls
  after leaving ramps and ledges instead of remaining at the ramp's peak.

- 2026-09-16: Split Link's scene clearance from the old free-camera sphere.
  Child Link now uses OoT-sized wall/ceiling checks (radius 14 at 26 units
  above his feet), allowing him under the low Kokiri bridge while preserving
  the free camera's larger collision volume.

- 2026-09-16: Fixed the missing title by moving the sky table away from SGL's
  fixed B1 font storage. Replaced direct back-screen register overrides with
  slBackColTable; padded the table and final scanline black for the border.
  Added yellow-olive palette fog, checkerboard fading, and a 1,310-unit cutoff
  (50% of the original forest renderer range). Replaced the five straight/probe
  shots with wider, slower collision-validated routes, with passage-centre
  preference and checked corner smoothing. Background PrintWindow capture now
  allows emulator inspection without desktop capture or taking keyboard focus.
  Standard/hi-res images rebuilt; 59 existing tests passed. All five generated
  routes passed dense segment-clearance checks. Standard and hi-res background captures
  show the restored title, black surround, and olive haze. Shared-tile fog is
  a conservative approximation, not per-pixel N64 fog.

- 2026-09-16: User assigned Claude walking/running/falling/rolling animation next.
  Current handoff and constraints are in `game/docs/OPUS_HANDOFF.md`; root
  `CLAUDE.md` points there. Conditional landing-roll behavior located in the
  original player source for Claude to verify. Implementation not started by
  this handoff; no Claude invocation tool/CLI was available to launch it here.

## Item counts, assignment and text recoil (2026-09-27)

Items shows live stick/seed counts and Down/Left/Right bindings. Plain D-pad
navigates; hold Saturn C + Down/Left/Right assigns an owned item on either pad.
Gold marks assigned items; blue marks cursor. Save v4 appends bindings; v2/v3
migrate with empty slots. Live stick/slingshot weapon actions remain pending.
Baba events are per-step and consumed once: first-stick fanfare no longer
restarts during text. Text/menu blocks knockback and weapon recoil, clearing
residual push. 265 focused host checks pass; Clean build passes, .bss ends
0x06083E40 (448 B below SGL with concurrent UI changes). No Kronos run or commit.
Human review: first-stick sound, text after hurt/rebound, counts, all assignment
directions on digital/analog pads, save/reload. Preserve concurrent UI edits.
## 2026-09-29 forest capacity repair

Screenshot follow-up: GFS open-handle exhaustion identified. Music holds one
handle across frames; project now reserves two. Clean rebuilt, 976 B below SGL;
host regression reproduces old failure and passes new capacity. Runtime pending.
Permanent all-agent CD-handle rule added to DOSEI-LEGEND-BIBLE.md.

Clean rebuilt with explicit NPC/prop texture reservation, staged budget gate,
and atomic actor-bank cache completion. Saria startup now stops gameplay
catch-up. 213 focused checks pass; minimum forest VRAM spare 33,504 B, high RAM
gap 1,232 B. First-exit greeting and walking blue-screen fix await Kronos review.
Existing save greeting flags unchanged. Work uncommitted.
## 2026-09-29 music exports and CD mix

Music Workshop can replace seven existing game music banks directly; house/shop
source overrides survive builds. Offline Help documents the workflow. CD playback
now mutes background music, then restores it over 0.5 seconds while retaining
SFX/CD sends. Clean built: 512 B below SGL. 38 focused tests plus GUI checks pass;
CD/BGM listening acceptance pending. No game music assets replaced during testing.

## Read-only Level viewport ? 2026-09-29

Mesh Workshop now opens Level viewport: Kokiri Forest rooms 0?2 and Deku entry.
UE-style RMB/WASD/QE flight, RMB-wheel speed, Alt-LMB orbit, MMB pan, F frame,
G overlays and F11 immersive; preference saved in Bible. Searchable Outliner
and native-coordinate Details show baked mesh objects plus original main-header
actors/enemies, collision, exit surfaces, spawns and transitions. Read-only; no
textures, edit gizmos, camera volumes, alternate headers or gameplay simulation.
Host palette-average painter rendering is not Saturn fidelity. See Workshop Help.
Validation: 6 viewport tests + 17 mesh tests pass; all four real rooms load with
no metadata warnings. Tk smoke passed navigation, speed, focus/capture release,
immersive, overlay and actor picking. Measured forest draw 42?46 ms, Deku 32 ms.
Screen capture unavailable in this session; manual visual/gameplay comparison
remains. No runtime changes or new disc build for this tool-only step.

## Named ROM-relative layout variants (2026-09-29)

Level viewport now defaults to raw Original ROM triangles, independent of baked
meshes. Save/Save as creates tracked named variants under assets/layouts; Reset
to original retains saved variants. Use for next build persists a separate
selection. Clean validates/freezes it before generation; build_actors applies
verified room/actor deltas and room_imports bypasses legacy meshes in named mode.
Current baked + Use for next build returns to legacy mesh publishing.
Editing scope: forest grass/sign/chest XYZ, signs/chests native yaw. Grass yaw
is locked because runtime ignores it. Other entities, meshes and collision
remain read-only. No params/IDs/drop flags/count changes. Alternate source
fingerprints prevent stale edits; ROM/decomp bytes are untouched.
Validation: 33 focused tests pass, temporary GUI edit/save/reset/build-choice
smoke passed, actual actor generator original-vs-alternate comparison changed
only the intended grass X coordinate. All four rooms decode raw ROM geometry.
Clean image built (layout-variants-clean.log), BSS 0x06083ee0: 288 bytes below
SGL work area. Wrapper returned 1 for native stderr warnings; build completed.
No actual alternate or changed live build choice saved during tests. No commit.
Manual viewport visual review and in-game edited placement check remain.

## Map Workshop object/material tools (2026-09-29)

User corrected product scope: Map Workshop is the room/layout editor; Mesh
Workshop remains an asset utility. Standalone launcher is tools/map-workshop/
open-map-workshop.bat; Mesh Workshop also opens it. F1 shows full offline Help.
Original rooms now retain actual ROM display-list object IDs (Forest room 0: 18).
Selected object supports XYZ/yaw-degrees/scale, individual OBJ replacement,
OBJ/MTL/atlas export, re-import, texture PNG preview/export/replacement and source
code opening. Original actor links are separate from converters/known runtime
paths. Mesh replacement uses immutable content-hashed bundles in layouts/meshes;
named layouts can combine actor placements and mesh overrides. Original object
transforms preserve source UVs. Imported geometry follows the existing hybrid
UV converter; no runtime renderer or collision changes. Unsupported build modes
fail instead of dropping mesh edits. Textured CPU preview uses affine patches
and switches to Solid while navigating. It is not N64/Saturn rendering fidelity.
Validation: 41 focused tests pass, Map/Mesh UI smoke passes, object/material/code
panels and textured view checked, build dialog TestOnly passes. Real forest
object replacement preserves other object geometry and passes production UV/
budget bake (1602 room polygons; 33440 bytes VRAM spare after reserved actors).
A translated original object also passes. Baseline Clean image built, BSS end
0x06083ee0 (288 bytes below SGL); log game/build/map-workshop-clean.log.
Textured frame inspected at game/build/map-textured-preview.png. Actual edited
Kronos placement/visual acceptance remains pending; no live variant selected or
saved during tests. Dialogue, triggers, collision edits, gizmos and undo remain
unimplemented. No commit/push.
