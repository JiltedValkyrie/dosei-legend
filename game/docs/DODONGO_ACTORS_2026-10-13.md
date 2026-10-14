# Dodongo source actor and boss integration evidence

Implemented in the shared tree, not runtime accepted. The route still needs
matching full packs/assets/heap checks, remaining DMT/Goron actors and human
fresh-file combat/story/save testing. No emulator or image build in this batch.

## Source enemy batch

Dodojr, Dodongo, Armos, Lizalfos, shop scrub, merchant, nut projectile and
scarecrow retain source actions with clip clocks and offline semantic contacts.
Eighteen compressed contact clips use 15,512 sample bytes. The initial eight
actors and helper passed source/action probes and SH-2 compilation; 53 isolated
sprite sheets baked, including both Lizalfos skins and the static nut. Root
subsequently added Beamos/Skulltulas/tokens and integrated Firefly/Tektite; see
the main route plan for their later verification and final archive counts.

## King Dodongo and rewards

The real 48-limb source skeleton, 19 collider spheres, limb callback mouth,
feet and head anchors, bomb consumption, source damage and intro/death actions
remain. Boss pose Draw runs first each update; insufficient graphics scratch
is fatal instead of silently losing hitbox updates. The source profile uses
the canonical Boss_Dodongo actor id: N64's En_Dodongo alias would be miscast by
the Saturn sprite view. Source heart and child warp/Ruby predicates remain.
The boss scene explicitly loads the dynamically spawned heart/warp objects.

Normal mesh bake: all 20 real limb display lists, 628 triangles, 330 tiles,
44,728 bytes. Required arena props now reject converter omissions. The arena
wall's post-title-card XML offsets are resolved for verified US1.2 ROM data.
Source child portal has 24 triangles; its two height layers follow source
timing. The baked lower ring follows the top radius and texture scroll stays
at its primary frame. These are presentation approximations, not action edits.
En_Bdfire uses eight original IA8 fire textures in a 32x32 sprite, 20,548 bytes;
its movement/burn actions remain source. No non-boss mesh fallback was added.

Lava keeps source death-cooling timing. Source texture writes to stripped N64
memory are removed; tagged resident room CLUTs cool in eight stages. No runtime
disc read or extra texture bank. Final gray stone retains the lava pattern;
N64 UV warping is not reproduced. Room reload restores original palettes;
cleared-room entry selects the completed phase, even with no live boss.

Boss arena room detail is bounded at 320 faces and 240,000 pixel bytes, only
by limiting optional subdivision/texture density; source geometry/collision is
retained. Isolated final bank: 319 faces, 299 tiles, 36 tagged lava faces.
`check_dodongo_boss_budget.py` passes a conservative simultaneous full set:
32 meshes, four flowers, both portal layers, all chest variants, the other
room's stair, full 704-face hero, 32 effect views, 32 source sprite slots, all
child tool sheets and 64 additional HUD/held-item commands. Totals: 390,016 of
445,432 VDP1 bytes plus 32,768 reserve; 1,129 of 2,400 sprite slots; 2,191 of
2,200 polygons. This is an isolated-bank measurement; normal staged banks must
pass `make check-dodongo-boss-budget` after rebuilding, before an image.

## Effects and validation

Per-pack effect profiles are generated from admitted actors and recursive
source actor/effect wrapper calls, plus resident child projectile effects.
No fixed six-effect assumption or duplicate boss effect table remains. Current
closure: DC20, boss17, DMT16, Goron15. Fourteen newly imported effect sources
keep original Init/Update physics/lifetimes; Draw becomes bounded host views.
DeadDs's original Draw-owned floor/wall placement executes in Update. Integer
angle expressions avoid overflowing Q16 literals. Source fragments/drops are
not replaced with invented rewards. Newly reached unsupported effects fail
the importer rather than disappearing silently. Host style integration is
owned by root and must be checked with final source packs.

Latest isolated checks: eight boss/material tests, three effect preservation
tests, executable source mouth/heart/warp/Ruby fixture, lava palette fixture,
20 source TUs compiled on host and SH-2. Wide audit: 197 allowed native hardware
multiplies, zero failing helpers. New14 effect objects total 13,150 bytes.
Normal generic mesh pass: 86 meshes; two preexisting gossip-stone converter
omissions remain explicit outside the boss-required set. Full pack link, final
sprite archives, cart-heap admission and runtime/human acceptance are separate.

## Mountain and city props

Seventeen source actors now cover Goron vase/lid/statue/shutter, silver rocks,
large crates, ocarina triggers, cavern entrance bomb stone, bombable walls,
mountain cloud ring, falling-rock spawner/hazards, rolling rocks, grotto holes,
river/ambient sound, bean soil/platform and soil Skulltula trigger. Original
actions, collision, puzzle flags, spawns and drops remain. Falling EnFireRock
uses a static sprite; EnEncount2 exports its source weather particle records.
RiverSound's original audio-only Draw runs after Update so it reaches the
audio backend independently of geometry. Root owns the ambient API sinks and
environment tint snapshot; the latter remains a presentation gap.

Host and SH-2 compile pass for all 17 actors: 54,456 object bytes, 195 native
hardware multiplies, zero forbidden wide helpers. Three preservation/object
closure checks cover source actions, dynamic children and field-keep keys.
Twenty-one isolated meshes and the rock sprite bake pass. Normal import and
mesh bake now produce 106 meshes (the same two preexisting gossip omissions).
Field keep now loads real Bombwall collision and Grotto draw keys; existing
resident keep symbols retain their stable identities. Combined scene memory,
normal archive generation, target full link and human acceptance remain gates.

## Stopped handoff: Three Goddesses and Great Fairy

User stopped work before completion. No agent-owned WSL processes or pending
tool sessions remain. Do not build an image or call this route accepted.

Three Goddesses implementation is in `tools/child_legend_sources.py`,
`tools/build_child_legend_sprites.py` and `tools/child_legend_keep.py`.
Original DemoEffect actions/cues/children and DemoKankyo weather actions remain.
God character bodies and auras use four sprite sheets (46,704 bytes total),
with source rotation/audio formerly owned by Draw advanced after Update.
Selected creation effects, jewels and environment props retain display-list
meshes; character meshes are excluded. Rain's five trail copies become one
to bound draw capacity. Required implicit keep display lists are resolved by
exact ROM/vertex matches; the complete normal pack has not yet linked.

`run_child_legend_probe.sh` passed two preservation tests, host and SH-2
compilation: 22,338 object bytes, 109 hardware multiplies, zero forbidden wide
helpers or Fx-range findings. `run_child_legend_assets.sh` passed four sprite
bakes and 16 required prop/effect meshes. These are isolated checks.
`OotCoreDrawItem.alpha` replaces padding without changing its size;
`oot_core_draw.cpp` carries source primitive alpha, and the host applies
zero-alpha rejection and eight-step temporal coverage. Latest combined target
verification of this transport is still pending.

Great Fairy implementation is in `tools/child_fairy_sources.py`. BgDyYoseizo
uses clip-only sprites; its 200 cosmetic particles are bounded at32 and
exported through `child_route_effect_views.inc`. Source song gate, cue reward,
spell allocation, refill and warp actions remain. EnDyExtra retains source
beam movement/lifetime; source primitive alpha replaces writable N64 vertex
alpha. Both fountain scenes and six source cutscene scripts are imported.
The NPC baker has object_dy_obj eye/mouth segment bindings; generic Fairy
and God snapshots now live in `include/oot_pack_npc_views.inc`, moved by the
NPC agent into source scene packs.

`run_child_fairy_probe.sh` passed the two Fairy source tests, three effect
preservation tests, five host/SH-2 source units and an executable original
reward fixture. Units: Fairy, beam, Extra, FCircle, SolderSrchBall. Total
10,971 bytes;12 hardware multiplies; zero forbidden wide helpers/Fx findings.
The executed fixture covered magic acquisition, spell reward, failed child
allocation, itemGetInf, repeated reward and warp latches. SearchBall retains
its original parent linkDetected collision write and invisible Update.
The new `run_child_fairy_assets.sh` was written but NOT RUN: Fairy sprites and
beam have not yet passed an isolated or complete normal bake.

### Last edits: implemented, NOT tested or built

The successful Fairy probe preceded these final edits:

- `include/oot_core_reward_sync.h` plus `oot_core_api.cpp`: commit newly
  acquired source magic/defense before the next host save mirror. Refill
  health by the source's four units per source frame, including chime/cap.
- `include/oot_core_host.h`, `src/oot_core_host.c`, `src/health_hud.c/.h`:
  existing magic callback now accepts capacity/defense reward commands;
  capacity grows and fills through existing HUD state. No ABI structure grew.
- `child_fairy_fixture.cpp`: added reward-copy/repeat/cap tests, not rerun.
- `oot_core_api.cpp`: source Interface_Update score-delta commit and clear.
- `include/oot_core_effects.h`, `child_route_effect_views.inc`:
  read-only source minigame score snapshot type0xf9.
- `src/kokiri_sgl.c/.h`, `src/oot_core_host.c`: Extra 30/60/100 world popup
  and minigame score use existing resident digit sprites. Source position,
  scale and lifetime remain; typeface uses the Saturn HUD font. The shared
  rupee HUD helper now takes Y explicitly; existing rupee calls retain206.

The latest complete pack attempt reported unresolved legend `gDust5Tex` and
`D_01000000`, boss `Rumble_Override`, and root-owned river-audio source symbols.
They are outstanding link failures, not harmless omissions. No fixes attempted
after the stop instruction. Resume by reviewing these last unverified patches,
rerunning the updated Fairy probe, baking Fairy and complete normal mesh/sprite
assets, closing complete pack links and measuring the combined memory budgets.
Check fountain EnLight ambient torch admission and spell child object closure.
Full current scene packs, room+actor/effect VRAM, heap guard, source cutscene
execution, full target build and human runtime acceptance all remain gates.
