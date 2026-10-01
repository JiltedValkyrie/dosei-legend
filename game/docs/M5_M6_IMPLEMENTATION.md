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

## Plan reconciliation and shutter scene ownership (2026-09-30)

DEMO_PLAN.md now gives one reconciled current plan instead of conflicting
historical snapshots. AGENTS.md and CLAUDE.md require every agent to maintain
the whole plan in the same task as status changes.

Shutter interaction/collision and drawing now check the portal's owning scene,
preventing unrelated scenes with the same room numbers from sharing doors.
25 mechanism tests and four boss tests pass. Clean compile/mastering and boundary check pass: BSS 0x06082550, 6,832 bytes
below SGL (game/build/plan-refresh-clean.log). No new dungeon runtime acceptance. Existing Gohma loading/drawing/combat/camera
hooks remain partial: boss rooms are not registered in the live scene table,
and rewards/story remain unfinished. M4/M5/M6 remain incomplete.

The following dated sections are historical evidence. Their remaining-work
lists describe those checkpoints; use DEMO_PLAN.md for current status.

## Active unattended dungeon work (2026-09-30, in progress)

Latest: secret title level select uses Up Up Down Down Left Right Left Right
B A Start, shared with enemy-map code. Test entry equips sword/shield/C items
without attaching a save slot. File rows and save prompt show area names.

User-reported SFX fixed: CHAN_6520 uses `(transpose << 6) + semitone`,
so Navi hello/talk select effects 104/124 (samples 212/213), not Link effects
41/61. Recovery-heart world/shop pickups now request NA_SE_SY_HP_RECOVER's
CHAN_596D sine/glide; ordinary drops request get-item instead of equipment.
Source envelope/glide baked at half rate, within existing sound RAM budget.
214 audio/gameplay checks pass; listening deferred to user as requested.
Hint Scrub projectile export now marks source cutout alpha; rebuilt HINTBALL
has transparent-pixel skipping and 192 clear texels. Clean BSS now 0x06081a70,
9,616 bytes below SGL. No boss or whole-dungeon completion claimed.
Code success freezes for Small Item Get CDDA; last-track end now uses lead-out
instead of the invalid next-track TOC entry that left Kronos in PLAY forever.
Reproduced and verified fix live: fanfare ends, Right selects room 1, A enters.
51 focused menu/CD/input checks passed. Fairy Fountain sequence 40 bank now
starts after the title-code fanfare; B restores title bank. Built, no listening
test requested. Added source volexp scaling needed by this sequence.

Normal Deku Babas, five Hint Scrubs/reflected nuts/ordered puzzle, and three
room-7 Gohma eggs/larvae now integrated with original meshes/animations.
Larvae preserve egg no-drop and hatched random drop table 3. 248 gameplay,
mechanism and save checks passed. New low-RAM carves keep cold GFS directory,
SDK quad lookup and larvae state out of high RAM; shared SDK stays untouched.
Clean build BSS ends 0x060819d0, 9,776 bytes below SGL. Full dungeon traversal,
boss/story, source presentation/SFX gaps, Woods and Meadow remain incomplete.

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

# M5/M6 implementation checkpoint - 2026-09-29

User authorized autonomous implementation and foreground testing. Work remains
uncommitted on `dev`. **Neither milestone is complete.** This is the current
status; earlier checkpoints below other handoff sections are historical.

## Live implementation

- Source manifest covers 12 Deku Tree rooms, two boss rooms and ten Woods rooms,
  including actors, objects, rotation/params, transitions, exits, water/cameras,
  spawn-to-room mappings and source hashes. See M5_M6_SOURCE_ROOMS.md.
- Live scene IDs: existing Deku Tree shell 7 (room 0); Lost Woods 8 (all ten
  rooms). Boss 9 remains an isolated preflight proposal, not a live registration.
  All 24 original room banks also pass the separate KRM1/KBG2 preflight.
- Woods' nine En_Holl tunnels now stream the resident scene. Source entrance
  table resolves forest/bridge returns and wrong-turn respawns. Kind 0 uses a
  single resident bank at the crossing, not source dual-room prefetch/fading.
  Invisible kinds 2/4/6 preserve source cylinder/width/height/load bands. Actual
  shutters still fail closed; no puzzle doors or debug warps were fabricated.
- C-item use: sticks swing with DMG_DEKU_STICK and break on accepted actor hits;
  X puts the stick away for the sword. Slingshot press draws the first-person
  aim view, release spends one seed and fires. Nuts spend one nut and throw a
  downward projectile, then flash/stun through the source DMG_DEKU_NUT mask.
  Swept seeds stop at geometry and actors; targets before a wall remain hittable.
  Ammo/ownership/pool limits are enforced; pause/dialogue freeze the world.
  Projectiles clear on room changes, held stick/fire survives room streaming,
  and scene reset/death clears transient items. No debug inventory grants.
- Stick fire has a 210-source-frame lifetime (315 fixed steps), extinguishes on
  putaway and consumes one on expiry. Torch/web ignition integration is pending.
  Seed/nut/stick visuals are compact flat stand-ins, not imported source models.
- Nut C assignment, source icon, ammo and assignment markers now work in pause.
  Existing save C IDs stay stable; nut is ID 3. Save v7 appends Deku map/compass
  bits and migrates v2-v6. Slingshot/map/compass and all six source dungeon
  chests are exported with source reward/text/treasure flags. Only room-0 map
  chest is on the current live dungeon route; other treasures await rooms.
- Dungeon and Woods area music route through NA_BGM_DUNGEON (24) and
  NA_BGM_SARIA_THEME (62), with original sequence banks. No gameplay CD reads.
  Audio bake supports long instruments under the SCSP per-sample limit,
  per-instrument source sample-rate overrides and zero-decay releases.
  Seed shot/impact and nut flash have resident source-sample SFX; these remain
  reduced single-layer playback, not full N64 effects sequencing.
- Post-Emerald exit guard uses the original moved endpoint. Mido blocks,
  speaks 0x1045, walks his source path and sets EVENTCHKINF_1C on arrival;
  then forest disappearance/house population follows existing source filters.

## Capacity and build

Sprite definition/picture/hash arrays moved to a guarded NOLOAD low-RAM section,
zeroed before jo_core_init, using a project-local SDK wrapper/linker script.
Shared SDK remains unchanged. Low RAM also holds streamed room metadata and
29,288 bytes of music triggers. Neither malloc nor SGL/sprite limits were cut.
Disc directory grew to 293 entries; guarded capacity increased 288 -> 320.
The normal Clean build includes these assets and retains all refusal checks.

## Verification

341 focused checks passed across gameplay, collision/item lifecycle, chest/save
migration, controls, pause, audio, room banks/portals, source manifests, directory,
filesystem handles and allocator. Full discovery initially ran 1,023 tests with
15 failures and five setup errors; updated equipment/room tests now pass. Four
unrelated stale extraction harnesses remain recorded in BUG_FEATURE_LOG.
Foreground boot/title/world rendering observed in Kronos:
`game/build/m5-m6-items-woods-boot.png`. This is not proof of a dungeon playthrough
or controller acceptance. Final Clean BSS ends at 0x06079850, 42,928 bytes below SGL.
The final image is game/build/game-clean.cue; build details are in m5-m6-build.log.

## Required work still open

M5: full dungeon room/shutter integration, mouth/intro, webs/torches/switches,
blocks/platforms/water mechanisms, map/compass display, dungeon enemies with
source models/AI/damage/drops, ordered scrub puzzle, Gohma/eggs/minions, heart
container/warp, Emerald/death/flashback story and dungeon/boss resume acceptance.

M6: Woods enemies/drops, placed pickups/grass, target and Skull Kid games, owls,
source tunnel fading, Saria bridge/ocarina chain, Field handoff and boundary
policy for Meadow/Goron/River. Unregistered source destinations are still
reported by the exporter; no invented gates added. M6b/M7 remain distinct.

Items: source hand/weapon models and animations, precise nut throw-frame timing,
stick wall-break/ignition/water behavior, source jump-stick damage classification,
slingshot targeting/reticle and digital-pad aiming acceptance, acquisition
presentation and runtime item/room-churn checks. See BUG-058 onward.

## Reproduce

```powershell
python game/tools/build_progression_manifest.py --notes game/docs/M5_M6_SOURCE_ROOMS.md
python game/tools/build_progression_rooms.py
python -m unittest game.tests.test_gameplay game.tests.test_save_file game.tests.test_player_controls game.tests.test_interior_audio game.tests.test_room_portal -q
powershell -NoProfile -ExecutionPolicy Bypass -File tools/launcher/build-game.ps1 -Variant clean
```
