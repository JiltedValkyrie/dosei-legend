# Child route: Field owl through King Dodongo (implementation, 2026-10-13)

Human request 2026-10-12, clarified 2026-10-13: include the Field owl camera,
Lon Lon Ranch, Kakariko Village, all Goron NPCs, Dodongo's Cavern enemies,
King Dodongo, chests and props, plus every cutscene and story step from the
Hyrule Field through the Goron Ruby. Shops, rewards, optional child interactions
and complete chest-jingle playback are included. Performance batch paused
(candidate 12 remains the open perf/repair test). Source behavior via the
real decomp; Saturn adaptations per RECOMP_PLAN and ACTOR_SPRITE_ROLLOUT_PLAN
(non-boss NPC/enemy = baked sprites; bosses keep models/hitboxes).

## Current implementation and remaining gates

**Stopped by human instruction, 2026-10-13.** No more implementation/builds
until resumed. [Exact stop handoff](CHILD_ROUTE_STOP_HANDOFF_2026-10-13.md)
records latest failed packs/atlases, unverified last edits, partial staging
and missing actors. Latest resident core link passes; whole route is unfinished.

Source Player and the core collision world remain authoritative. C0 props and
the earlier Clean 14 image are historical checkpoints below. Route source
implementation and focused tests now cover the following batches. These are
not a claim that final packs, full scene budgets or human traversal pass.

- Real `En_Owl` owns Field first contact, repeat/accept dialogue, departure
  and Death Mountain transport predicates. Host owl ownership is disabled
  only after successful source-profile admission. Ten sprite sheets retain
  every perch/flight clip and source phase clocks without runtime poses.
- Source `z_demo`, complete admitted scene scripts, spline and cutscene flags
  run through validated format-4 scene blobs. Source subcamera lifecycle,
  main/sub view, FOV, roll, letterbox and destination cutscene layer cross
  joined snapshots; the host never queries the running slave. Source
  OnePoint recipes and Unique9/Demo5/Demo9/Unique6 engines live in only the
  scene packs which need them, using validated service callbacks. Core keeps
  shared camera state and the source camera queue. Twelve executing camera
  groups, six complete source-script probes and three admission tests pass;
  isolated SH-2 math audits report no forbidden helpers.
- Zelda, Impa and the courtyard Ganondorf actor retain source talk, letter
  handshakes, Lullaby cues and source camera actions. Every animation is
  baked; Zelda's required root motion uses bounded offline XZ anchors.
  Darunia's dance, courtyard audience, Impa teaching commands, Epona song,
  DC opening and the Three Goddesses script all execute in host fixtures.
  Fixtures drive textbox waits; interactive song/actor tests and human
  presentation acceptance are separate evidence.
- Darunia/Gorons/guards/carpenters/Cucco lady, source shops and fifty stock
  entries, ranch NPCs/animals/timer, common Market/Kakariko villagers and
  optional child reward/mask/minigame actors have source adapters. Shop
  shelf camera, cursor, held browsing input and original purchase rules
  cross bounded views. Source Saria and Castle prerequisites are included
  in integration. Their final scene-local view helper link and combined
  sprite/mesh budgets remain integration gates.
- Source memory-game note generation, all three round lengths, playback,
  strict note failure and source Skull Kid/message choreography execute in
  the ocarina fixture. Saria/Epona/Lullaby lesson playback and retry checks
  preserve source song recognition. Resident metronome clips now include
  the held beat and both one-shots; generated 15/8-tick durations preserve
  source completion waits. Six ocarina and 26 action-audio tests pass.
- DC enemies use original actions, sprite clocks and offline semantic
  contacts: Dodongos, Lizalfos, Armos, Beamos, Keese, Skulltulas/tokens,
  scrubs/merchant/projectile and scarecrow. Mountain/city source props keep
  dynamic collision, puzzles, hazards and drops. Source King Dodongo keeps
  its actual skeleton, mouth/feet/sphere contacts and twenty rendered limb
  meshes. Source fire, heart, child warp/Ruby and lava cooling are wired.
  Isolated source/SH-2 tests and the conservative boss arena budget pass;
  latest full packs and staged scene admission remain required.
- Chest CD export now contains the full 8.56-second sequence and release tail
  (643 sectors); queued item fanfares cannot restart/interrupt it. Source
  fanfares cross a joined master audio queue. Latest root audio batch passes
  43 focused tests. Target image and audible human check pending.

The first expanded DC pack exceeded the former 196,608-byte carve. Scene
carve is now 262,144 bytes at 0x02720000;
core address/capacity remain unchanged. This costs 65,536 cart-heap bytes,
not additional physical RAM. All source blobs and cached objects must be
rebuilt together for API35, scene format 4 and the latest actor-pack service
header. Moving camera engines and NPC presentation into scene packs avoids
expanding the fixed resident core. Generated profile objects must participate
in core export retention as well as actor objects. Final actor/effect/room/
heap and sound-RAM budgets remain open; no actors may be omitted to pass.

On resumption, first fix the exact pack/atlas/range blockers in the stop handoff
and resume the interrupted normal sprite bake (manifest still Oct12). Other
gates: finish source-reachable presentation/backend closure
(including quake and title handling, legend/Great Fairy integration and any
remaining explicit effects); rebuild every core/pack/object and full sprite
archive; validate combined scene memory, VDP1, sound RAM and source admission;
build a matching target image; then human fresh-file traversal, optional
interactions, save/reload and boss/warp/Ruby checks. Optional tomb/well scripts
retain gameplay state but lightning/rain/nature/monochrome presentation still
has explicit unsupported reporting. General recorded scarecrow playback is
outside this child route and remains explicit debt. No route milestone is
accepted from a source import or build alone. Human owns runtime testing.

Camera/story evidence: [source camera and ocarina handoff](CHILD_ROUTE_CAMERAS_2026-10-13.md).
Boss/props evidence: [dungeon actor handoff](DODONGO_ACTORS_2026-10-13.md).

## Initial audit (historical, 2026-10-12; superseded above)

- All route maps registered and structurally reachable; none traversal-tested.
- Story after the Field owl is missing: no Zelda/Impa/Lullaby, letter, gate
  guard, Saria's Song, Darunia, DC opening or Ruby.
- Core has **no cutscene system**: `z_demo` not linked; OnePoint/sub-camera
  stubs. Host `cutscene.c` plays 20 offline-baked scenes ending at the Field.
- Source admission (`oot_core_api.cpp load_room_actors`) is a hardcoded id
  whitelist; `ROOM_ENTRIES_MAX` 64 (Goron L4 has 89 entries).
- `host_give_item` drops Weird Egg 0x21, Letter 0x23, Bomb Bag 0x4D,
  Goron's Bracelet 0x50; core inventory is not copied back to the C save.
  Songs/quest bits already copy back.
- Packs: Z20 (Goron City, 150 KB free of 196 KB carve), Z23 (DC, 104 KB
  free), no SG (boss room) pack. Only Field (SA) has a source enemy pack.
- No source boss exists anywhere (Gohma is host C).

## Waves (each: importer patches, packs, sprites/anchors, budgets, host
## tests, Debug build, human test; update ACTOR_COVERAGE/ENEMY_ROSTER)

| Wave | Deliverable | Gate |
| --- | --- | --- |
| C0 foundations | Data-driven per-scene source admission (generated from the scene pack list, not hardcoded ids); room entry cap raised with Low-RAM budget check; item grants + save copy-back for egg/letter/bomb bag/bombs/bracelet (R1 field groups); source `En_Box` chest end to end | Host tests; Kokiri/Field unchanged (no double owners) |
| C1 core cutscenes | Import `z_demo` (Cutscene_* script processing, actor cues, text, destinations, transitions); export cutscene camera eye/at/fov and letterbox to the Saturn camera; whole-cutscene animation preload (demand-animation rule) | DC opening / Goron intro play from source with camera; no per-shot loads |
| C2 DC traversal props | En_Bombf, Bg_Breakwall, Obj_Bombiwa, Bg_Ddan_Jd/Kd, Bg_Dodoago, Bg_Hidan_Curtain, Obj_Switch, Obj_Hsblock, Obj_Oshihiki, Door_Shutter, En_Holl, Elf_Msg, En_Trap | DC rooms 0-16 traversable with bombs; drops per source |
| C3 DC enemies (sprites) | En_Firefly, En_Dodojr, En_Dodongo, En_Vm, En_Zf, En_Am, En_Sw, En_Shopnuts+En_Dns+En_Nutsball, En_Kakasi2 | Spawn/damage/stun/drop per source; scene budget fits |
| C4 King Dodongo | First source boss import (model + pose hitboxes kept), En_Bdfire sprite, Door_Warp1, Item_B_Heart, Ruby cutscene/blue warp | Boss fight, heart, warp, Ruby flag/save |
| C5 DMT + Goron City | En_Go2 (all types), En_Du, En_Gm, Bg_Spot18_*, Obj_Hamishi, Obj_Kibako2, En_Okarina_Tag, Bg_Spot16_Bombstone, Bg_Gate_Shutter side, DMT En_Tite/En_Owl/En_Bombf; Darunia dance + bracelet | Bracelet given; DC rock opens; Goron talk/roll |
| C6 Field to Kakariko story | Source En_Owl (retire host owl), Bg_Spot00_Hanebasi, Market/entrance NPCs + Heishi4, Castle Heishi2/3 + Rrbox, Malon egg/Talon cucco, courtyard En_Zl4/Demo_Im/Lullaby/letter, Kakariko Heishi2 letter gate, Meadow En_Sa Saria's Song (+ Wf, Dekunuts, Bg_Mjin) | Whole chain on a fresh file |

Order: C0, C1, C2, C3, C4, C5, C6. C6 may start after C1 for actors
without cutscene needs. Debug only until the 20 FPS target; keep candidate-12
Clean/perf work intact. Boss exemption: King Dodongo keeps its model.

## Status

- 2026-10-12: plan written; C0 started (Claude).
- 2026-10-12 C0 code (Claude; host tests + compile/link check, no image,
  no runtime): pack rows carry `OOT_ACTOR_PACK_ADMIT`; source-owned scenes
  (`scene_pack_actors.SOURCE_SCENES`: ddan, ddan_boss, spot18, spot16)
  spawn every pack actor from room lists and admit their transition
  actors. Room entry cap 96; ObjectContext 32 slots, scene objects 30
  (whole scene resident; DC lists 22) plus the scene keep object.
  Item grants: Weird Egg, Letter, bomb bags, bombs, Goron's Bracelet,
  purple/gold rupees, Deku Shield, heart container (host); medallions,
  stones, Agony/Gerudo card, non-Deku map/compass/boss key/small keys
  (core, source `gSaveContext.mapIndex` per Map_Init).
- C0c/C2 first batch (generic mesh path, `SOURCE_ACTORS`): En_Box,
  Bg_Breakwall, Bg_Ddan_Jd/Kd, Bg_Dodoago, Bg_Hidan_Curtain, Obj_Hsblock,
  Obj_Switch, Obj_Oshihiki, En_Bombf, En_Trap, Obj_Bombiwa, Elf_Msg,
  En_Holl. All compile/link; 62 core meshes. Packs: Z23 (DC) 17 actors,
  144,816 B used / 51,792 B free; SG 100,256 / 96,352; Z20 76,560 /
  120,048; Z2S 49,440 / 147,168. DC enemies will need a pack split or
  larger carve.
- C0-only temporary deviations, now partly replaced: DC entrance previously
  used a no-op route bridge; it now requests the complete source script and
  Player halt. Attention-camera/OnePoint replacement remains unfinished.
- Clean built (human request 2026-10-12): `build/game-clean.cue`
  c3bf579b, `build/clean13-build.sh`; .bss 0x06082B10 (5,360 B spare),
  host/core audits 492/1,632 allowed multiplies, 0 failing; budget passes;
  1,464 ISO files match. Includes candidate-11/12 repairs and this C0
  batch. Previous Clean b54638cd in `build/mednafen-test/clean-b54638cd/`;
  Debug 6117a58c unchanged. Not runtime-tested.
- Clean 14 built 2026-10-12 (`build/clean14-build.sh`): `build/game-clean.cue`
  eb25f08b, .bss 0x060831D0 (3,632 B spare), audits 500/1,631 allowed
  multiplies, 0 failing; 1,465 ISO files match. Fixes on c3bf579b reports:
  invisible pots/crates/drops (special keep loaded everywhere), boomerang
  tap-aim, digital B hold = fine aim / tap = cancel, crawlspace first
  person, ocarina C notes, Pause > System > Core Fast/Responsive. Previous
  Clean c3bf579b in `build/mednafen-test/clean-c3bf579b/`; Debug 6117a58c
  unchanged. Sword air bounce still open (needs human detail). Not
  runtime-tested.
- Host Debug high-RAM spare 16 B: keep route logic in the core.
- On human resumption: close remaining backend effects and full integration/
  assets/memory checks, then provide a matching target image for human
  fresh-file traversal and save/reload verification. Keep the C0 and Clean 14
  measurements above as historical evidence only.
